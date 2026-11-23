"""Step 3: Product-Product Similarity Graph & Louvain Market Segmentation.

Builds separate Product-Product similarity graphs for `laptop` and `smartphone`.
Products are connected across brands when their price is close and their
benchmark-backed CPU (and laptop GPU) performance is within ``perf_tol``.
Runs Louvain community detection, profiles each segment, and plots the
distribution across segments and price bands.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

from src.market_graph.perf_scores import enrich_perf_scores

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "market_graph"

PRICE_BANDS = [
    (0, 10_000_000, "<10M"),
    (10_000_000, 15_000_000, "10-15M"),
    (15_000_000, 20_000_000, "15-20M"),
    (20_000_000, 30_000_000, "20-30M"),
    (30_000_000, float("inf"), ">30M"),
]
DEFAULT_RESOLUTIONS = (1.0, 1.5, 2.0, 2.5)


def assign_price_band(price_vnd: float) -> str:
    for low, high, label in PRICE_BANDS:
        if low <= price_vnd < high:
            return label
    return ">30M"


def extract_cpu_tier(cpu_model: str | None) -> str:
    """Map detailed CPU model string to a core tier for imputation/fallback."""
    if not cpu_model or str(cpu_model).lower() == "unknown":
        return "unknown"
    s = str(cpu_model).lower()
    patterns = [
        (r"\b(i9|ultra 9|ryzen 9)\b", "tier_high_9"),
        (r"\b(i7|core 7|ultra 7|ryzen 7)\b", "tier_midhigh_7"),
        (r"\b(i5|core 5|ultra 5|ryzen 5)\b", "tier_mid_5"),
        (r"\b(i3|core 3|ryzen 3|celeron|pentium|athlon)\b", "tier_entry_3"),
        (r"\bm[1-5]\s*(pro|max|ultra)\b", "apple_m_pro"),
        (r"\bm[1-5]\b", "apple_m_base"),
        (r"\ba1[5-9]\b", "apple_a_flagship"),
        (r"\ba1[1-4]\b", "apple_a_older"),
        (r"\bsnapdragon\s*x\b", "snapdragon_x"),
        (r"\bsnapdragon\s*8s?\b", "sd_flagship"),
        (r"\bsnapdragon\s*[67]\b", "sd_mid"),
        (r"\bsnapdragon\s*4\b", "sd_entry"),
        (r"\bdimensity\s*[89]\d{3}\b", "dimensity_high"),
        (r"\bdimensity\s*[67]\d{3}\b", "dimensity_mid"),
        (r"\bhelio\b", "helio_entry"),
        (r"\bexynos\b", "exynos"),
    ]
    for pat, label in patterns:
        if re.search(pat, s):
            return label
    return "other_cpu"


def _isna(value: Any) -> bool:
    return value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value)


def _node_value(value: Any) -> Any:
    if _isna(value):
        return None
    return value


def _add_nodes(G: nx.Graph, df_cat: pd.DataFrame) -> None:
    for rec in df_cat.to_dict(orient="records"):
        G.add_node(
            rec["canonical_product_id"],
            brand=rec["brand"],
            model_clean=rec["model_clean"],
            cpu_model=rec["cpu_model"],
            cpu_tier=rec.get("cpu_tier"),
            price_median=float(rec["price_median"]),
            cpu_perf_score=_node_value(rec.get("cpu_perf_score")),
            gpu_perf_score=_node_value(rec.get("gpu_perf_score")),
            cpu_perf_norm=_node_value(rec.get("cpu_perf_norm")),
            gpu_perf_norm=_node_value(rec.get("gpu_perf_norm")),
            cpu_score_source=rec.get("cpu_score_source"),
            gpu_score_source=rec.get("gpu_score_source"),
            gpu_type=rec.get("gpu_type"),
        )


def _legacy_edges(G: nx.Graph, df_cat: pd.DataFrame, price_tol: float) -> None:
    """Old same-brand cpu_tier/RAM logic, used with --no-benchmarks."""
    by_brand: dict[str, list[dict[str, Any]]] = {}
    for rec in df_cat.to_dict(orient="records"):
        by_brand.setdefault(str(rec["brand"]), []).append(rec)

    for brand_recs in by_brand.values():
        n = len(brand_recs)
        for i in range(n):
            r1 = brand_recs[i]
            p1 = float(r1["price_median"])
            for j in range(i + 1, n):
                r2 = brand_recs[j]
                p2 = float(r2["price_median"])
                min_p, max_p = min(p1, p2), max(p1, p2)
                if min_p <= 0 or (max_p - min_p) / min_p > price_tol:
                    continue

                t1, t2 = r1.get("cpu_tier"), r2.get("cpu_tier")
                cpu_match = (t1 == t2) and t1 != "unknown"
                ram1, ram2 = r1.get("ram_gb"), r2.get("ram_gb")
                ram_match = pd.notna(ram1) and pd.notna(ram2) and int(ram1) == int(ram2)

                if not (cpu_match or (ram_match and (t1 == "unknown" or t2 == "unknown"))):
                    continue

                price_sim = 1.0 - (max_p - min_p) / max_p
                spec_sim = 0.7 * (1.0 if cpu_match else 0.5) + 0.3 * (1.0 if ram_match else 0.3)
                weight = round(0.5 * price_sim + 0.5 * spec_sim, 4)
                G.add_edge(
                    r1["canonical_product_id"],
                    r2["canonical_product_id"],
                    weight=weight,
                    price_sim=round(price_sim, 4),
                    cpu_sim=None,
                    gpu_sim=None,
                    perf_match="legacy",
                )


def _perf_edges(G: nx.Graph, df_cat: pd.DataFrame, price_tol: float, perf_tol: float) -> None:
    df = df_cat.sort_values("price_median").reset_index(drop=True)
    is_laptop = str(df["category"].iloc[0]) == "laptop"

    def numeric_column(name: str) -> np.ndarray:
        if name not in df.columns:
            return np.full(len(df), np.nan)
        return pd.to_numeric(df[name], errors="coerce").to_numpy(dtype=float)

    ids = df["canonical_product_id"].to_numpy()
    brands = df["brand"].astype(str).to_numpy()
    tiers = df["cpu_tier"].astype(str).to_numpy()
    prices = numeric_column("price_median")
    ram = numeric_column("ram_gb")
    cpu_scores = numeric_column("cpu_perf_score")
    cpu_norms = numeric_column("cpu_perf_norm")
    gpu_scores = numeric_column("gpu_perf_score")
    gpu_norms = numeric_column("gpu_perf_norm")
    cpu_sources = (
        df["cpu_score_source"].fillna("missing").astype(str).to_numpy()
        if "cpu_score_source" in df.columns
        else np.full(len(df), "missing", dtype=object)
    )
    gpu_types = (
        df["gpu_type"].fillna("unknown").astype(str).to_numpy()
        if "gpu_type" in df.columns
        else np.full(len(df), "unknown", dtype=object)
    )

    for i in range(len(df)):
        p1 = prices[i]
        if not np.isfinite(p1) or p1 <= 0:
            continue
        hi = int(np.searchsorted(prices, p1 * (1.0 + price_tol) + 1e-9, side="right"))
        if hi <= i + 1:
            continue

        sl = slice(i + 1, hi)
        p2 = prices[sl]
        price_sim = 1.0 - (p2 - p1) / p2

        c2 = cpu_scores[sl]
        cpu_valid = ~np.isnan(cpu_scores[i]) & ~np.isnan(c2)
        with np.errstate(invalid="ignore", divide="ignore"):
            cpu_rel = np.abs(cpu_scores[i] - c2) / np.maximum(np.maximum(cpu_scores[i], c2), 1e-9)
        cpu_ok = cpu_valid & (cpu_rel <= perf_tol)
        cpu_sim = 1.0 - np.abs(cpu_norms[i] - cpu_norms[sl])

        gpu_used = np.zeros(len(p2), dtype=bool)
        gpu_sim = np.full(len(p2), np.nan)
        gpu_ok = np.ones(len(p2), dtype=bool)
        mismatch = np.zeros(len(p2), dtype=bool)

        if is_laptop:
            g2 = gpu_scores[sl]
            gpu_valid = ~np.isnan(gpu_scores[i]) & ~np.isnan(g2)
            t1 = gpu_types[i]
            t2 = gpu_types[sl]
            mismatch = ((t1 == "discrete") & (t2 != "discrete")) | (
                (t2 == "discrete") & (t1 != "discrete")
            )
            with np.errstate(invalid="ignore", divide="ignore"):
                gpu_rel = np.abs(gpu_scores[i] - g2) / np.maximum(np.maximum(gpu_scores[i], g2), 1e-9)
            gpu_ok = np.where(gpu_valid, gpu_rel <= perf_tol, True)
            gpu_ok &= ~mismatch
            gpu_used = gpu_valid & ~mismatch
            gpu_sim[gpu_used] = 1.0 - np.abs(gpu_norms[i] - gpu_norms[sl])[gpu_used]

        final_ok = cpu_ok & gpu_ok

        for rel_idx in np.nonzero(final_ok)[0]:
            if gpu_used[rel_idx]:
                spec_sim = 0.7 * cpu_sim[rel_idx] + 0.3 * gpu_sim[rel_idx]
            else:
                spec_sim = cpu_sim[rel_idx]
            weight = round(0.5 * float(price_sim[rel_idx]) + 0.5 * float(spec_sim), 4)
            j = i + 1 + int(rel_idx)
            perf_match = "imputed" if "tier_median" in (cpu_sources[i], cpu_sources[j]) else "benchmark"
            G.add_edge(
                ids[i],
                ids[j],
                weight=weight,
                price_sim=round(float(price_sim[rel_idx]), 4),
                cpu_sim=round(float(cpu_sim[rel_idx]), 4),
                gpu_sim=round(float(gpu_sim[rel_idx]), 4) if gpu_used[rel_idx] else None,
                perf_match=perf_match,
            )

        cpu_missing = np.isnan(cpu_scores[i]) | np.isnan(c2)
        if not cpu_missing.any():
            continue

        same_brand = brands[sl] == brands[i]
        ram_match = (
            ~np.isnan(ram[i]) & ~np.isnan(ram[sl]) & (ram[i] == ram[sl])
        )
        t1 = tiers[i]
        t2 = tiers[sl]
        tier_match = (t1 == t2) & (t1 != "unknown")
        unknown_ok = ram_match & ((t1 == "unknown") | (t2 == "unknown"))
        fallback = ~final_ok & cpu_missing & same_brand & (tier_match | unknown_ok)
        if is_laptop:
            fallback &= ~mismatch

        for rel_idx in np.nonzero(fallback)[0]:
            j = i + 1 + int(rel_idx)
            baseline_spec = 0.5 if tier_match[rel_idx] else 0.4
            weight = round(0.5 * float(price_sim[rel_idx]) + 0.5 * baseline_spec, 4)
            G.add_edge(
                ids[i],
                ids[j],
                weight=weight,
                price_sim=round(float(price_sim[rel_idx]), 4),
                cpu_sim=None,
                gpu_sim=None,
                perf_match="fallback",
            )


def build_product_similarity_graph(
    df_cat: pd.DataFrame,
    price_tol: float = 0.20,
    perf_tol: float = 0.15,
    use_benchmarks: bool = True,
) -> nx.Graph:
    """Build Product-Product similarity graph within a single category."""
    G = nx.Graph()
    _add_nodes(G, df_cat)
    has_perf_scores = (
        use_benchmarks
        and "cpu_perf_score" in df_cat.columns
        and pd.to_numeric(df_cat["cpu_perf_score"], errors="coerce").notna().any()
    )
    if has_perf_scores:
        _perf_edges(G, df_cat, price_tol=price_tol, perf_tol=perf_tol)
    else:
        _legacy_edges(G, df_cat, price_tol=price_tol)
    return G


def _community_stats(communities: list[set[str]], total_nodes: int) -> dict[str, float]:
    sizes = [len(comm) for comm in communities]
    largest = max(sizes) if sizes else 0
    return {
        "communities": len(communities),
        "meaningful": sum(1 for size in sizes if size >= 5),
        "singleton_share": sum(1 for size in sizes if size == 1) / max(total_nodes, 1),
        "largest_share": largest / max(total_nodes, 1),
        "largest_size": largest,
    }


def _select_resolution(
    G: nx.Graph,
    resolution: float | str,
    seed: int,
) -> tuple[float, list[set[str]]]:
    total_nodes = G.number_of_nodes()
    if isinstance(resolution, (int, float)):
        chosen = float(resolution)
        communities = nx.community.louvain_communities(
            G, weight="weight", resolution=chosen, seed=seed
        )
        return chosen, communities

    candidates: list[tuple[float, list[set[str]], dict[str, float]]] = []
    for candidate in DEFAULT_RESOLUTIONS:
        communities = nx.community.louvain_communities(
            G, weight="weight", resolution=candidate, seed=seed
        )
        stats = _community_stats(communities, total_nodes)
        candidates.append((candidate, communities, stats))
        print(
            f"  [Step 3] resolution={candidate:.1f}: communities={stats['communities']}, "
            f"meaningful={stats['meaningful']}, largest={stats['largest_size']} "
            f"({stats['largest_share']:.1%}), singletons={stats['singleton_share']:.1%}"
        )

    positive = [item for item in candidates if item[2]["meaningful"] > 0]
    feasible = [item for item in positive if item[2]["largest_share"] <= 0.25]
    pool = feasible or positive
    if pool:
        best = max(
            pool,
            key=lambda item: (
                item[2]["meaningful"],
                -item[2]["largest_share"],
                -item[2]["singleton_share"],
                item[0],
            ),
        )
    else:
        best = min(
            candidates,
            key=lambda item: (item[2]["largest_share"], -item[2]["meaningful"], item[0]),
        )
    return best[0], best[1]


def detect_louvain_segments(
    products_df: pd.DataFrame,
    price_tol: float = 0.20,
    perf_tol: float = 0.15,
    resolution: float | str = "auto",
    seed: int = 42,
    work_dir: Path | None = None,
    use_benchmarks: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, nx.Graph]]:
    """Run Louvain community detection per category and summarize segments."""
    df = products_df.copy()
    df["price_band"] = df["price_median"].apply(assign_price_band)
    df["cpu_tier"] = df["cpu_model"].apply(extract_cpu_tier)

    if work_dir is not None and use_benchmarks:
        df = enrich_perf_scores(df, work_dir=work_dir, use_benchmarks=True)
    else:
        for column in (
            "cpu_perf_score",
            "gpu_perf_score",
            "cpu_perf_metric",
            "gpu_perf_metric",
            "cpu_score_source",
            "gpu_score_source",
            "cpu_perf_norm",
            "gpu_perf_norm",
            "gpu_type",
        ):
            if column not in df.columns:
                df[column] = None

    community_map: dict[str, str] = {}
    segment_profiles: list[dict[str, Any]] = []
    graphs: dict[str, nx.Graph] = {}
    resolution_map: dict[str, float] = {}

    for cat, df_cat in df.groupby("category"):
        G_pp = build_product_similarity_graph(
            df_cat,
            price_tol=price_tol,
            perf_tol=perf_tol,
            use_benchmarks=use_benchmarks,
        )
        chosen_resolution, communities = _select_resolution(G_pp, resolution, seed)
        resolution_map[str(cat)] = chosen_resolution
        G_pp.graph["resolution_used"] = chosen_resolution
        graphs[str(cat)] = G_pp
        communities = sorted(communities, key=len, reverse=True)

        band_by_id = dict(zip(df_cat["canonical_product_id"], df_cat["price_band"]))
        for idx, comm in enumerate(communities):
            if len(comm) >= 3:
                cid_label = f"{cat}_c{idx}"
                for node_id in comm:
                    community_map[node_id] = cid_label
            else:
                for node_id in comm:
                    band = band_by_id.get(node_id, "unknown")
                    community_map[node_id] = f"{cat}_niche_{band}"

    df["community_id"] = df["canonical_product_id"].map(community_map)

    label_map: dict[str, str] = {}
    for comm_id, grp in df.groupby("community_id"):
        cat = grp["category"].iloc[0]
        p_min_m = grp["price_median"].min() / 1e6
        p_max_m = grp["price_median"].max() / 1e6
        p_med_m = grp["price_median"].median() / 1e6
        top_brands = ", ".join([b for b, _ in Counter(grp["brand"]).most_common(2)])
        if "_niche" in str(comm_id):
            band_name = grp["price_band"].iloc[0]
            base_label = f"{cat.title()} Niche {band_name}"
        else:
            base_label = f"{cat.title()} {p_min_m:.0f}-{p_max_m:.0f}M ({top_brands})"
        seg_label = base_label if base_label not in label_map.values() else f"{base_label} [{comm_id}]"
        label_map[str(comm_id)] = seg_label

        cpu_scores = pd.to_numeric(grp.get("cpu_perf_score"), errors="coerce")
        gpu_scores = pd.to_numeric(grp.get("gpu_perf_score"), errors="coerce")
        segment_profiles.append(
            {
                "community_id": comm_id,
                "segment_label": seg_label,
                "category": cat,
                "product_count": len(grp),
                "price_min_m": round(p_min_m, 2),
                "price_median_m": round(p_med_m, 2),
                "price_max_m": round(p_max_m, 2),
                "top_brands": top_brands,
                "avg_retailer_degree": round(float(grp["retailer_count"].mean()), 2),
                "total_reviews": float(grp["total_reviews"].sum()),
                "cpu_perf_median": round(float(cpu_scores.median()), 2)
                if cpu_scores.notna().any()
                else None,
                "cpu_perf_min": round(float(cpu_scores.min()), 2) if cpu_scores.notna().any() else None,
                "cpu_perf_max": round(float(cpu_scores.max()), 2) if cpu_scores.notna().any() else None,
                "gpu_perf_median": round(float(gpu_scores.median()), 2)
                if gpu_scores.notna().any()
                else None,
                "resolution_used": resolution_map.get(str(cat)),
            }
        )

    df["segment_label"] = df["community_id"].map(label_map)
    segments_df = pd.DataFrame(segment_profiles).sort_values(
        ["category", "product_count"], ascending=[True, False]
    )
    return df, segments_df, graphs


def plot_segment_distributions(
    df: pd.DataFrame,
    segments_df: pd.DataFrame,
    reports_dir: Path,
) -> Path:
    """Plot product distribution by Louvain segment (top 12 per category) and price band."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    band_order = [b[2] for b in PRICE_BANDS]
    ct_band = pd.crosstab(df["price_band"], df["category"]).reindex(band_order).fillna(0)
    ct_band.plot(kind="bar", ax=axes[0], color=["#2b6cb0", "#ed8936"], edgecolor="white")
    axes[0].set_title("Phân bố mẫu máy theo Dải giá & Ngành hàng", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Dải giá (Triệu VNĐ)")
    axes[0].set_ylabel("Số lượng Canonical Products")
    axes[0].tick_params(axis="x", rotation=0)
    axes[0].grid(axis="y", linestyle="--", alpha=0.4)

    top_segs = segments_df[~segments_df["community_id"].str.contains("_niche", na=False)].head(12)
    if top_segs.empty:
        top_segs = segments_df.head(12)
    top_segs_sorted = top_segs.sort_values("product_count", ascending=True)
    colors = ["#2b6cb0" if c == "laptop" else "#ed8936" for c in top_segs_sorted["category"]]
    axes[1].barh(top_segs_sorted["segment_label"], top_segs_sorted["product_count"], color=colors)
    axes[1].set_title("Top Phân khúc Thị trường (Louvain Communities)", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("Số lượng Canonical Products")
    axes[1].grid(axis="x", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out_path = reports_dir / "segment_distribution.png"
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def run_step3(
    work_dir: Path = DEFAULT_WORK_DIR,
    price_tol: float = 0.20,
    perf_tol: float = 0.15,
    resolution: float | str = "auto",
    use_benchmarks: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    products_path = work_dir / "canonical_products.csv"
    products_df = pd.read_csv(products_path)
    df_segmented, segments_df, graphs = detect_louvain_segments(
        products_df,
        price_tol=price_tol,
        perf_tol=perf_tol,
        resolution=resolution,
        work_dir=work_dir,
        use_benchmarks=use_benchmarks,
    )

    cpu_scored = int(df_segmented["cpu_perf_score"].notna().sum())
    gpu_scored = int(df_segmented["gpu_perf_score"].notna().sum())
    print(
        f"[Step 3] Perf coverage: CPU {cpu_scored}/{len(df_segmented)}, "
        f"GPU {gpu_scored}/{len(df_segmented)}"
    )
    for cat, graph in graphs.items():
        brands = {node: graph.nodes[node].get("brand") for node in graph.nodes}
        cross_brand = sum(1 for u, v in graph.edges if brands[u] != brands[v])
        total_edges = graph.number_of_edges()
        share = cross_brand / total_edges if total_edges else 0.0
        print(
            f"[Step 3] {cat}: {graph.number_of_nodes()} nodes, {total_edges} edges "
            f"({cross_brand} cross-brand, {share:.1%}), "
            f"resolution={graph.graph.get('resolution_used')}"
        )

    df_segmented.to_csv(work_dir / "canonical_products_segmented.csv", index=False, encoding="utf-8-sig")
    segments_df.to_csv(work_dir / "louvain_segments.csv", index=False, encoding="utf-8-sig")
    chart_path = plot_segment_distributions(df_segmented, segments_df, work_dir / "reports")

    print(f"[Step 3] Detected {len(segments_df)} Louvain segments across laptop & smartphone.")
    print(f"[Step 3] Saved segment distribution chart -> {chart_path}")
    print("[Step 3] Top segments:\n" + segments_df.head(10).to_string(index=False))
    return df_segmented, segments_df
