"""Step 4: Structural Holes Detection & Visual Reporting.

Cross-tabulates retailer catalogs against Louvain communities, detects market
gaps (retailer blind spots and underserved high-demand segments), and exports
3 primary visualizations:
  1. Jaccard Similarity Heatmap (`jaccard_similarity_heatmap.png`)
  2. Per-category Interactive Bipartite Market Graphs
     (`bipartite_market_graph_{laptop,smartphone}.html` via PyVis)
  3. Price Segment Distribution Heatmap (`segment_price_heatmap.png`)
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import seaborn as sns
from pyvis.network import Network

from src.market_graph.louvain_segments import PRICE_BANDS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "market_graph"


def build_retailer_community_matrix(df_seg: pd.DataFrame) -> pd.DataFrame:
    """Build Retailer x Louvain Community count matrix."""
    exploded = df_seg.assign(retailer=df_seg["retailers"].str.split("|")).explode("retailer")
    ct = pd.crosstab(exploded["segment_label"], exploded["retailer"])
    return ct


def _format_perf_recommendation(seg: pd.Series | dict[str, Any]) -> str:
    category = seg.get("category")
    cpu_med = seg.get("cpu_perf_median")
    cpu_min = seg.get("cpu_perf_min")
    cpu_max = seg.get("cpu_perf_max")
    gpu_med = seg.get("gpu_perf_median")

    has_cpu = pd.notna(cpu_med) and cpu_med is not None
    has_gpu = pd.notna(gpu_med) and gpu_med is not None

    if category == "laptop":
        if has_cpu and has_gpu:
            return (
                f"Cần nhập laptop có CPU quanh mức {float(cpu_med):.1f} "
                f"({float(cpu_min):.1f}-{float(cpu_max):.1f}), GPU quanh mức {float(gpu_med):.1f}"
            )
        elif has_cpu:
            return (
                f"Cần nhập laptop có CPU quanh mức {float(cpu_med):.1f} "
                f"({float(cpu_min):.1f}-{float(cpu_max):.1f})"
            )
        return "Chưa có dữ liệu benchmark cho phân khúc này"
    elif category == "smartphone":
        if has_cpu:
            return (
                f"Cần nhập smartphone có điểm CPU benchmark quanh mức {float(cpu_med):.0f} "
                f"({float(cpu_min):.0f}-{float(cpu_max):.0f})"
            )
        return "Chưa có dữ liệu benchmark cho phân khúc này"
    return "N/A"


def detect_structural_holes(
    df_seg: pd.DataFrame,
    segments_df: pd.DataFrame,
    min_segment_size: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Identify retailer blind spots and market-wide underserved segments with performance benchmarks."""
    ct = build_retailer_community_matrix(df_seg)
    retailers = list(ct.columns)

    # 1. Retailer-specific blind spots (0 products in an active community)
    blind_spots: list[dict[str, Any]] = []
    active_segs = segments_df[
        (~segments_df["community_id"].str.contains("_niche", na=False))
        & (segments_df["product_count"] >= min_segment_size)
    ]
    for _, seg in active_segs.iterrows():
        label = seg["segment_label"]
        if label not in ct.index:
            continue
        row_counts = ct.loc[label]
        cpu_med = seg.get("cpu_perf_median") if pd.notna(seg.get("cpu_perf_median")) else None
        cpu_min = seg.get("cpu_perf_min") if pd.notna(seg.get("cpu_perf_min")) else None
        cpu_max = seg.get("cpu_perf_max") if pd.notna(seg.get("cpu_perf_max")) else None
        gpu_med = seg.get("gpu_perf_median") if pd.notna(seg.get("gpu_perf_median")) else None
        rec = _format_perf_recommendation(seg)

        for ret in retailers:
            cnt = int(row_counts.get(ret, 0))
            if cnt == 0:
                blind_spots.append(
                    {
                        "gap_type": "retailer_blind_spot",
                        "retailer": ret,
                        "segment_label": label,
                        "category": seg["category"],
                        "segment_total_products": int(seg["product_count"]),
                        "retailer_products": 0,
                        "price_range_m": f"{seg['price_min_m']}-{seg['price_max_m']}M",
                        "top_brands": seg["top_brands"],
                        "cpu_perf_median": cpu_med,
                        "cpu_perf_min": cpu_min,
                        "cpu_perf_max": cpu_max,
                        "gpu_perf_median": gpu_med,
                        "perf_recommendation": rec,
                    }
                )

    # 2. Market-wide underserved segments (high reviews per product, low competition)
    underserved: list[dict[str, Any]] = []
    if not active_segs.empty:
        seg_copy = active_segs.copy()
        seg_copy["reviews_per_product"] = seg_copy["total_reviews"] / seg_copy["product_count"].clip(lower=1)
        for cat, cat_segs in seg_copy.groupby("category"):
            med_rev = cat_segs["reviews_per_product"].median()
            med_cnt = cat_segs["product_count"].median()
            for _, seg in cat_segs.iterrows():
                if seg["reviews_per_product"] > 0 and seg["reviews_per_product"] >= med_rev and (
                    seg["product_count"] <= med_cnt or seg.get("avg_retailer_degree", 0) <= 1.25
                ):
                    cpu_med = seg.get("cpu_perf_median") if pd.notna(seg.get("cpu_perf_median")) else None
                    cpu_min = seg.get("cpu_perf_min") if pd.notna(seg.get("cpu_perf_min")) else None
                    cpu_max = seg.get("cpu_perf_max") if pd.notna(seg.get("cpu_perf_max")) else None
                    gpu_med = seg.get("gpu_perf_median") if pd.notna(seg.get("gpu_perf_median")) else None
                    rec = _format_perf_recommendation(seg)

                    underserved.append(
                        {
                            "gap_type": "underserved_high_demand",
                            "retailer": "ALL_MARKET",
                            "segment_label": seg["segment_label"],
                            "category": seg["category"],
                            "segment_total_products": int(seg["product_count"]),
                            "retailer_products": int(seg["product_count"]),
                            "price_range_m": f"{seg['price_min_m']}-{seg['price_max_m']}M",
                            "top_brands": seg["top_brands"],
                            "cpu_perf_median": cpu_med,
                            "cpu_perf_min": cpu_min,
                            "cpu_perf_max": cpu_max,
                            "gpu_perf_median": gpu_med,
                            "perf_recommendation": rec,
                        }
                    )

    holes_df = pd.DataFrame(blind_spots + underserved)
    return ct, holes_df


def plot_jaccard_heatmap(
    jaccard_by_cat: dict[str, pd.DataFrame],
    reports_dir: Path,
) -> Path:
    """Plot per-category Retailer x Retailer Jaccard similarity heatmaps."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))

    pct_by_cat: dict[str, pd.DataFrame] = {}
    vmax = 30.0
    for cat, jaccard_df in jaccard_by_cat.items():
        if jaccard_df is None or jaccard_df.empty:
            continue
        pct_df = jaccard_df.astype(float) * 100.0
        pct_by_cat[cat] = pct_df
        candidate = pct_df.where(pct_df < 99.9).max().max()
        if pd.notna(candidate):
            vmax = max(vmax, float(candidate))

    for ax, cat, label in zip(
        axes,
        ("laptop", "smartphone"),
        ("Laptop", "Smartphone"),
    ):
        title = f"{label}: Ma trận Jaccard Trùng lặp Danh mục (%)"
        pct_df = pct_by_cat.get(cat)
        if pct_df is None or pct_df.empty:
            ax.set_title(f"{title} (Không có dữ liệu)", fontsize=12, fontweight="bold", pad=12)
            ax.axis("off")
            continue
        sns.heatmap(
            pct_df,
            annot=True,
            fmt=".1f",
            cmap="YlGnBu",
            vmin=0,
            vmax=vmax,
            linewidths=0.5,
            cbar_kws={"label": "Độ trùng lặp danh mục (%)"},
            ax=ax,
        )
        ax.set_title(title, fontsize=12, fontweight="bold", pad=12)
        ax.set_xlabel("")
        ax.set_ylabel("")

    fig.suptitle(
        "Ma trận Jaccard Trùng lặp Danh mục giữa 5 Nhà bán lẻ (%)",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    out_path = reports_dir / "jaccard_similarity_heatmap.png"
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_segment_price_heatmap(df_seg: pd.DataFrame, reports_dir: Path) -> Path:
    """Plot Retailer x Price Band heatmap split by Laptop and Smartphone."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    exploded = df_seg.assign(retailer=df_seg["retailers"].str.split("|")).explode("retailer")
    band_order = [b[2] for b in PRICE_BANDS]
    all_retailers = sorted(exploded["retailer"].dropna().unique())

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), sharey=True)
    for ax, cat, title in zip(
        axes,
        ["laptop", "smartphone"],
        ["Laptop: Số mẫu máy theo Sàn & Dải giá", "Smartphone: Số mẫu máy theo Sàn & Dải giá"],
    ):
        sub = exploded[exploded["category"] == cat]
        if sub.empty:
            ax.set_title(f"{title} (Không có dữ liệu)", fontsize=12, fontweight="bold")
            ax.axis("off")
            continue
        ct = (
            pd.crosstab(sub["price_band"], sub["retailer"])
            .reindex(index=band_order, columns=all_retailers, fill_value=0)
            .astype(int)
        )
        sns.heatmap(
            ct,
            annot=True,
            fmt="d",
            cmap="OrRd",
            linewidths=0.5,
            cbar_kws={"label": "Số lượng Canonical Products"},
            ax=ax,
        )
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_xlabel("Nhà bán lẻ")
        ax.set_ylabel("Dải giá (VNĐ)")

    plt.tight_layout()
    out_path = reports_dir / "segment_price_heatmap.png"
    plt.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return out_path


def export_pyvis_bipartite(
    gexf_path: Path,
    reports_dir: Path,
    output_name: str = "bipartite_market_graph.html",
    title: str | None = None,
    max_products: int = 180,
) -> Path:
    """Export an interactive PyVis HTML of the Bipartite Market Graph (top competitive + sample exclusive)."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    G = nx.read_gexf(gexf_path)

    retailer_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "retailer"]
    product_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "product"]

    # Prioritize competitive products (degree > 1) plus top-priced/representative exclusive nodes
    competitive = sorted(
        [n for n in product_nodes if G.degree(n) > 1],
        key=lambda n: G.degree(n),
        reverse=True,
    )
    selected = set(competitive[:max_products])
    if len(selected) < max_products:
        remaining = max_products - len(selected)
        per_ret = max(1, remaining // max(1, len(retailer_nodes)))
        for ret in retailer_nodes:
            excl = [n for n in G.neighbors(ret) if G.degree(n) == 1 and n not in selected]
            selected.update(excl[:per_ret])

    subG = G.subgraph(set(retailer_nodes) | selected).copy()

    net = Network(
        height="780px",
        width="100%",
        bgcolor="#0f172a",
        font_color="#f8fafc",
        directed=False,
        heading=title or "",
    )
    net.barnes_hut(gravity=-4500, central_gravity=0.35, spring_length=140, spring_strength=0.04)

    for n, d in subG.nodes(data=True):
        if d.get("node_type") == "retailer":
            net.add_node(
                n,
                label=str(n),
                color="#f59e0b",
                size=38,
                shape="diamond",
                title=f"Nhà bán lẻ: {n} (Tổng SP hiển thị: {subG.degree(n)})",
            )
        else:
            deg = G.degree(n)
            color = "#38bdf8" if deg > 1 else "#94a3b8"
            price_m = float(d.get("price_median", 0)) / 1e6
            safe_label = html.escape(str(d.get("label", n)))
            safe_cpu = html.escape(str(d.get("cpu_model", "N/A")))
            net.add_node(
                n,
                label=str(d.get("label", n))[:28],
                color=color,
                size=10 + deg * 4,
                shape="dot",
                title=(
                    f"{safe_label}<br/>"
                    f"CPU: {safe_cpu}<br/>"
                    f"Giá TB: {price_m:.1f}M VNĐ<br/>"
                    f"Số sàn bán (Degree): {deg}"
                ),
            )

    for u, v in subG.edges():
        net.add_edge(u, v, color="rgba(148,163,184,0.35)", width=1.2)

    out_path = reports_dir / output_name
    net.save_graph(str(out_path))
    return out_path


def write_gaps_markdown(
    ct: pd.DataFrame,
    holes_df: pd.DataFrame,
    jaccard_by_cat: dict[str, pd.DataFrame],
    stats_by_cat: dict[str, pd.DataFrame],
    reports_dir: Path,
) -> Path:
    """Write a concise Vietnamese markdown summary of market gaps & metrics."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "market_gaps_report.md"

    lines: list[str] = [
        "# Báo cáo Phân tích Đồ thị Sản phẩm & Khoảng trống Thị trường (IT4930)",
        "",
        "## 1. Thống kê Độc quyền vs Cạnh tranh theo Nhà bán lẻ",
        "",
    ]

    wrote_stats = False
    for cat, label in (("laptop", "Laptop"), ("smartphone", "Smartphone")):
        stats_df = stats_by_cat.get(cat)
        if stats_df is None or stats_df.empty:
            continue
        lines.extend([f"### Mảng {label}", "", stats_df.to_markdown(index=False), ""])
        wrote_stats = True
    if not wrote_stats:
        lines.extend(["Không có dữ liệu thống kê nhà bán lẻ.", ""])

    lines.extend(["## 2. Ma trận Jaccard Trùng lặp Danh mục", ""])
    wrote_jaccard = False
    for cat, label in (("laptop", "Laptop"), ("smartphone", "Smartphone")):
        jaccard_df = jaccard_by_cat.get(cat)
        if jaccard_df is None or jaccard_df.empty:
            continue
        lines.extend(
            [
                f"### Mảng {label}",
                "",
                (jaccard_df.astype(float) * 100).round(2).to_markdown(),
                "",
            ]
        )
        wrote_jaccard = True
    if not wrote_jaccard:
        lines.extend(["Không có dữ liệu Jaccard.", ""])

    lines.extend(["## 3. Khoảng trống Thị trường (Structural Holes)", ""])

    if holes_df.empty:
        lines.append("Không phát hiện khoảng trống rõ rệt theo ngưỡng lọc hiện tại.")
    else:
        blind = holes_df[holes_df["gap_type"] == "retailer_blind_spot"]
        underserved = holes_df[holes_df["gap_type"] == "underserved_high_demand"]
        lines.append(f"- **Điểm mù theo nhà bán lẻ (Retailer Blind Spots):** {len(blind)} phân khúc bỏ ngỏ.")
        lines.append(f"- **Phân khúc nhu cầu cao ít cạnh tranh (Underserved):** {len(underserved)} phân khúc.")
        lines.append("")

        display_cols = [
            c
            for c in [
                "retailer",
                "segment_label",
                "category",
                "price_range_m",
                "top_brands",
                "cpu_perf_median",
                "gpu_perf_median",
                "perf_recommendation",
            ]
            if c in holes_df.columns
        ]
        if not blind.empty:
            lines.append("### 3.1 Điểm mù của từng sàn (Retailer Blind Spots)")
            lines.append("")
            lines.append(blind[display_cols].head(15).to_markdown(index=False))
            lines.append("")
        if not underserved.empty:
            lines.append("### 3.2 Phân khúc thiếu cung toàn thị trường (Underserved High Demand)")
            lines.append("")
            lines.append(underserved[display_cols].head(15).to_markdown(index=False))
            lines.append("")

        if not blind.empty:
            lines.extend(
                [
                    "",
                    "### 3.3 Khuyến nghị Cấu hình Nhập hàng để Lấp Điểm Mù (Hardware Procurement Targets)",
                    "",
                ]
            )
            for ret, r_grp in blind.groupby("retailer"):
                lines.append(f"#### Nhà bán lẻ: {ret}")
                for _, r_row in r_grp.head(5).iterrows():
                    lines.append(
                        f"- **{r_row['segment_label']}** ({r_row['price_range_m']}): "
                        f"{r_row.get('perf_recommendation', 'N/A')}"
                    )
                lines.append("")

    lines.extend(
        [
            "",
            "## 4. Phân bố Cộng đồng Louvain theo Nhà bán lẻ",
            "",
            ct.head(20).to_markdown(),
        ]
    )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def run_step4(work_dir: Path = DEFAULT_WORK_DIR) -> None:
    reports_dir = work_dir / "reports"
    df_seg = pd.read_csv(work_dir / "canonical_products_segmented.csv")
    segments_df = pd.read_csv(work_dir / "louvain_segments.csv")

    categories = ("laptop", "smartphone")
    jaccard_by_cat: dict[str, pd.DataFrame] = {}
    stats_by_cat: dict[str, pd.DataFrame] = {}
    for cat in categories:
        jaccard_path = work_dir / f"jaccard_matrix_{cat}.csv"
        stats_path = work_dir / f"retailer_degree_stats_{cat}.csv"
        if jaccard_path.exists():
            jaccard_by_cat[cat] = pd.read_csv(jaccard_path, index_col=0)
        if stats_path.exists():
            stats_by_cat[cat] = pd.read_csv(stats_path)

    ct, holes_df = detect_structural_holes(df_seg, segments_df)
    ct.to_csv(work_dir / "retailer_community_matrix.csv", encoding="utf-8-sig")
    holes_df.to_csv(work_dir / "structural_holes.csv", index=False, encoding="utf-8-sig")

    jaccard_png = plot_jaccard_heatmap(jaccard_by_cat, reports_dir)
    price_png = plot_segment_price_heatmap(df_seg, reports_dir)

    pyvis_paths: list[Path] = []
    for cat in categories:
        gexf_path = work_dir / f"bipartite_market_graph_{cat}.gexf"
        if not gexf_path.exists():
            continue
        pyvis_paths.append(
            export_pyvis_bipartite(
                gexf_path,
                reports_dir,
                output_name=f"bipartite_market_graph_{cat}.html",
                title=f"{cat.title()} Market Graph",
            )
        )

    md_path = write_gaps_markdown(ct, holes_df, jaccard_by_cat, stats_by_cat, reports_dir)

    print(f"[Step 4] Detected {len(holes_df)} structural hole entries -> {work_dir / 'structural_holes.csv'}")
    print(f"[Step 4] Exported Jaccard Heatmap -> {jaccard_png}")
    print(f"[Step 4] Exported Segment Price Heatmap -> {price_png}")
    for path in pyvis_paths:
        print(f"[Step 4] Exported Interactive Bipartite Graph -> {path}")
    if not pyvis_paths:
        print("[Step 4] Warning: no category GEXF files found; skipped PyVis export.")
    print(f"[Step 4] Exported Markdown Report -> {md_path}")
