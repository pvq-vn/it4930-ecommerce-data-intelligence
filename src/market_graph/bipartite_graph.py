"""Step 2: Entity Resolution (<=20% price spread) & Bipartite Market Graph.

Computes canonical_product_id = hash(brand + model_clean + cpu_model) split
when price spread exceeds 20%, builds a NetworkX Bipartite Graph (Retailers <->
Canonical Products), classifies Exclusive (degree=1) vs Competitive (degree>1),
and computes the 5x5 Retailer Jaccard Similarity matrix.

The module also owns two cross-cutting pieces kept here to avoid extra modules:

* the shared analysis price floor (``MIN_PRICE_BY_CATEGORY``/``filter_min_price``);
* the price-free TV5/TV8 handoff builder (``build_price_free_handoff``), which never
  reads prices and therefore cannot leak the prediction target.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "market_graph"
DEFAULT_INPUT = DEFAULT_WORK_DIR / "products_llm_cleaned.jsonl"

NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
GPU_VENDOR_PREFIX_RE = re.compile(r"^(?:nvidia|amd|qualcomm|intel)\s+")
GPU_STOPWORDS_RE = re.compile(r"\b(?:geforce|laptop\s+gpu|laptop|mobile|gpu|graphics)\b")
GPU_VRAM_SUFFIX_RE = re.compile(r"\b\d+\s*gb\b")

# --- Shared analysis price floor ------------------------------------------------
# Below these prices a listing is almost always an accessory or a 2G feature phone.
# The floor is applied to analysis artifacts only (Step 2 per-category views,
# Step 3 graphs, Step 4 gaps); ``canonical_products.csv`` keeps every row so that
# TV5/TV7/TV8 can still trace any listing back to its canonical product.
# Thresholds match TV3/TV5/TV7.
MIN_PRICE_BY_CATEGORY: dict[str, float] = {
    "smartphone": 1_000_000.0,
    "laptop": 3_000_000.0,
}

# A single hardware configuration sold 3x above the cheapest seller is treated as an
# entity-resolution anomaly, not as a real price premium (e.g. accessory rows whose
# price is 70k while the phone itself is 10.49M).
MAX_PLAUSIBLE_PREMIUM_RATIO = 3.0


def min_price_for(category: str | None) -> float:
    """Return the analysis price floor for a category (0.0 when unregulated)."""
    if category is None:
        return 0.0
    return MIN_PRICE_BY_CATEGORY.get(str(category).strip().lower(), 0.0)


def filter_min_price(
    df: pd.DataFrame,
    category_col: str = "category",
    price_col: str = "price_median",
    log_prefix: str | None = None,
) -> pd.DataFrame:
    """Drop rows whose known price is below the category floor.

    Rows with a missing price are kept: the floor only targets known low prices and
    must never silently remove rows that were previously included.
    """
    if df.empty or category_col not in df.columns or price_col not in df.columns:
        return df.copy()

    prices = pd.to_numeric(df[price_col], errors="coerce")
    floors = df[category_col].map(min_price_for).astype(float)
    below_floor = prices.notna() & (prices < floors)

    filtered = df.loc[~below_floor].copy()
    if log_prefix and int(below_floor.sum()) > 0:
        removed = df.loc[below_floor].groupby(category_col).size().to_dict()
        floors_txt = ", ".join(
            f"{cat}<{floor / 1e6:.1f}M" for cat, floor in sorted(MIN_PRICE_BY_CATEGORY.items())
        )
        print(
            f"{log_prefix} price floor ({floors_txt}): removed {int(below_floor.sum())} rows "
            f"by category {removed}; kept {len(filtered)}/{len(df)}"
        )
    return filtered



def _norm_token(value: str | None) -> str:
    if not value:
        return ""
    return NON_ALNUM_RE.sub(" ", value.lower()).strip()


def _norm_spec_val(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    try:
        ival = int(float(val))
        return str(ival) if ival > 0 else ""
    except (ValueError, TypeError):
        return ""


def _norm_screen_size(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    try:
        fval = round(float(val), 1)
        return str(fval) if fval > 0 else ""
    except (ValueError, TypeError):
        return ""


def _norm_gpu(val: Any) -> str:
    if val is None or pd.isna(val):
        return ""
    text = NON_ALNUM_RE.sub(" ", str(val).lower()).strip()
    text = GPU_VENDOR_PREFIX_RE.sub("", text)
    text = GPU_VRAM_SUFFIX_RE.sub(" ", text)
    text = GPU_STOPWORDS_RE.sub(" ", text)
    return " ".join(text.split())


def _is_positive_price(value: Any) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def compute_base_hash(
    brand: str,
    model_clean: str,
    cpu_model: str,
    ram_gb: Any = None,
    storage_gb: Any = None,
    gpu_model: Any = None,
    screen_size_inch: Any = None,
    category: Any = None,
) -> str:
    """Hash normalized hardware specs to a 16-char hex ID."""
    r_str = _norm_spec_val(ram_gb)
    s_str = _norm_spec_val(storage_gb)
    cat_norm = _norm_token(category)
    # Ignore GPU for smartphone as GPU is fixed by SoC (cpu_model)
    g_str = "" if cat_norm in {"smartphone", "dien thoai", "phone"} else _norm_gpu(gpu_model)
    sc_str = _norm_screen_size(screen_size_inch)
    payload = (
        f"{_norm_token(brand)}|{_norm_token(model_clean)}|{_norm_token(cpu_model)}|"
        f"{r_str}|{s_str}|{g_str}|{sc_str}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cluster_by_price_spread(
    rows: list[dict[str, Any]],
    max_spread: float = 0.20,
) -> list[list[dict[str, Any]]]:
    """Split a hash-colliding group into sub-clusters where (max-min)/min <= max_spread."""
    valid = [r for r in rows if (r.get("price_vnd") or 0) > 0]
    if not valid:
        return []
    valid.sort(key=lambda r: float(r["price_vnd"]))

    clusters: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = [valid[0]]
    cluster_min = float(valid[0]["price_vnd"])

    for row in valid[1:]:
        price = float(row["price_vnd"])
        if (price - cluster_min) / cluster_min <= max_spread:
            current.append(row)
        else:
            clusters.append(current)
            current = [row]
            cluster_min = price
    clusters.append(current)
    return clusters


def _specs_compatible(target: dict[str, Any], donor: dict[str, Any]) -> bool:
    """Check whether known hardware specifications of target and donor do not conflict."""
    t_cat = _norm_token(target.get("category_clean", target.get("category", "")))
    d_cat = _norm_token(donor.get("category_clean", donor.get("category", "")))
    if t_cat and d_cat and t_cat != d_cat:
        return False

    # CPU
    t_cpu = _norm_token(target.get("cpu_model"))
    d_cpu = _norm_token(donor.get("cpu_model"))
    if t_cpu and t_cpu != "unknown" and d_cpu and d_cpu != "unknown":
        if t_cpu != d_cpu:
            return False

    # RAM
    t_ram = _norm_spec_val(target.get("ram_gb"))
    d_ram = _norm_spec_val(donor.get("ram_gb"))
    if t_ram and d_ram and t_ram != d_ram:
        return False

    # Storage
    t_storage = _norm_spec_val(target.get("storage_gb"))
    d_storage = _norm_spec_val(donor.get("storage_gb"))
    if t_storage and d_storage and t_storage != d_storage:
        return False

    # GPU (only relevant for laptops; smartphone GPU is determined by SoC)
    if t_cat not in {"smartphone", "dien thoai", "phone"} and d_cat not in {"smartphone", "dien thoai", "phone"}:
        t_gpu = _norm_gpu(target.get("gpu_model"))
        d_gpu = _norm_gpu(donor.get("gpu_model"))
        if t_gpu and d_gpu and t_gpu != d_gpu:
            return False

    # Screen size
    t_screen = _norm_screen_size(target.get("screen_size_inch"))
    d_screen = _norm_screen_size(donor.get("screen_size_inch"))
    if t_screen and d_screen and t_screen != d_screen:
        return False

    return True


def _impute_unknown_cpu(rows: list[dict[str, Any]], max_price_diff: float = 0.10) -> list[dict[str, Any]]:
    """If cpu_model is Unknown and a unique known-CPU match exists for same (cat, brand, model) within 10% price, reuse it.

    Ties are broken with ``min`` so the result does not depend on set iteration order
    (PYTHONHASHSEED); the pipeline must be byte-reproducible.
    """
    known_by_model: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        cpu = str(r.get("cpu_model") or "").strip()
        price = float(r.get("price_vnd") or 0)
        if cpu and cpu.lower() != "unknown" and price > 0:
            key = (
                _norm_token(r.get("category_clean", r.get("category", ""))),
                _norm_token(r.get("brand", "")),
                _norm_token(r.get("model_clean", "")),
            )
            known_by_model[key].append(r)

    out: list[dict[str, Any]] = []
    for r in rows:
        cpu = str(r.get("cpu_model") or "").strip()
        price = float(r.get("price_vnd") or 0)
        if (not cpu or cpu.lower() == "unknown") and price > 0:
            key = (
                _norm_token(r.get("category_clean", r.get("category", ""))),
                _norm_token(r.get("brand", "")),
                _norm_token(r.get("model_clean", "")),
            )
            candidates = {
                d["cpu_model"]
                for d in known_by_model.get(key, [])
                if abs(float(d["price_vnd"]) - price) / min(float(d["price_vnd"]), price) <= max_price_diff
                and _specs_compatible(r, d)
            }
            if len(candidates) == 1:
                r = {**r, "cpu_model": min(candidates)}
        out.append(r)
    return out


def _impute_unknown_specs(rows: list[dict[str, Any]], max_price_diff: float = 0.10) -> list[dict[str, Any]]:
    """If cpu_model, ram_gb, storage_gb, gpu_model, or screen_size_inch is unknown, impute from compatible donors within 10% price."""
    rows = _impute_unknown_cpu(rows, max_price_diff=max_price_diff)

    known_donors: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        price = float(r.get("price_vnd") or 0)
        if price > 0:
            key = (
                _norm_token(r.get("category_clean", r.get("category", ""))),
                _norm_token(r.get("brand", "")),
                _norm_token(r.get("model_clean", "")),
            )
            known_donors[key].append(r)

    out: list[dict[str, Any]] = []
    for r in rows:
        price = float(r.get("price_vnd") or 0)
        cat_norm = _norm_token(r.get("category_clean", r.get("category", "")))
        is_laptop = cat_norm not in {"smartphone", "dien thoai", "phone"}
        ram_norm = _norm_spec_val(r.get("ram_gb"))
        storage_norm = _norm_spec_val(r.get("storage_gb"))
        gpu_norm = _norm_gpu(r.get("gpu_model"))
        screen_norm = _norm_screen_size(r.get("screen_size_inch"))

        needs_impute = (
            (not ram_norm)
            or (not storage_norm)
            or (is_laptop and not gpu_norm)
            or (not screen_norm)
        )
        if needs_impute and price > 0:
            key = (
                cat_norm,
                _norm_token(r.get("brand", "")),
                _norm_token(r.get("model_clean", "")),
            )
            candidates = [
                d
                for d in known_donors.get(key, [])
                if abs(float(d["price_vnd"]) - price) / min(float(d["price_vnd"]), price) <= max_price_diff
                and _specs_compatible(r, d)
            ]
            updated = dict(r)
            if not ram_norm:
                ram_vals = {d["ram_gb"] for d in candidates if _norm_spec_val(d.get("ram_gb"))}
                unique_rams = {_norm_spec_val(v): v for v in ram_vals}
                if len(unique_rams) == 1:
                    updated["ram_gb"] = min(unique_rams.values())
            if not storage_norm:
                storage_vals = {d["storage_gb"] for d in candidates if _norm_spec_val(d.get("storage_gb"))}
                unique_storages = {_norm_spec_val(v): v for v in storage_vals}
                if len(unique_storages) == 1:
                    updated["storage_gb"] = min(unique_storages.values())
            if is_laptop and not gpu_norm:
                gpu_vals = {d["gpu_model"] for d in candidates if _norm_gpu(d.get("gpu_model"))}
                unique_gpus = {_norm_gpu(v): v for v in gpu_vals}
                if len(unique_gpus) == 1:
                    updated["gpu_model"] = min(unique_gpus.values())
            if not screen_norm:
                screen_vals = {d["screen_size_inch"] for d in candidates if _norm_screen_size(d.get("screen_size_inch"))}
                unique_screens = {_norm_screen_size(v): v for v in screen_vals}
                if len(unique_screens) == 1:
                    updated["screen_size_inch"] = min(unique_screens.values())
            r = updated
        out.append(r)
    return out


def resolve_canonical_products(
    rows: list[dict[str, Any]],
    max_spread: float = 0.20,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Assign canonical_product_id to each listing and aggregate product-level table."""
    rows = [r for r in rows if _is_positive_price(r.get("price_vnd"))]
    rows = _impute_unknown_specs(rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cat = row.get("category_clean", row.get("category", "unknown"))
        b_hash = compute_base_hash(
            row.get("brand", ""),
            row.get("model_clean", ""),
            row.get("cpu_model", ""),
            row.get("ram_gb"),
            row.get("storage_gb"),
            row.get("gpu_model"),
            row.get("screen_size_inch"),
            category=cat,
        )
        grouped[b_hash].append(row)

    enriched_rows: list[dict[str, Any]] = []
    product_records: list[dict[str, Any]] = []

    for b_hash, grp in grouped.items():
        # Separate by category_clean first so laptop & smartphone never collide
        by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in grp:
            by_cat[r.get("category_clean", r.get("category", "unknown"))].append(r)

        for cat, cat_grp in by_cat.items():
            # Check if this group has any specific hardware specs known
            has_specs = any(
                bool(
                    _norm_spec_val(r.get("ram_gb"))
                    or _norm_spec_val(r.get("storage_gb"))
                    or _norm_gpu(r.get("gpu_model"))
                    or _norm_screen_size(r.get("screen_size_inch"))
                )
                for r in cat_grp
            )
            if not has_specs:
                sub_clusters = cluster_by_price_spread(cat_grp, max_spread=max_spread)
            else:
                sub_clusters = [cat_grp]
            multi = len(sub_clusters) > 1 or len(by_cat) > 1
            for idx, cluster in enumerate(sub_clusters, start=1):
                cid = f"{b_hash}_{cat[:1]}{idx}" if multi else b_hash
                prices = [float(r["price_vnd"]) for r in cluster]
                sellers = sorted({r["seller_name"] for r in cluster})
                reviews = [float(r["review_count_normalized"]) for r in cluster if pd.notna(r.get("review_count_normalized"))]
                ratings = [float(r["rating_norm"]) for r in cluster if pd.notna(r.get("rating_norm"))]
                rams = [float(r["ram_gb"]) for r in cluster if pd.notna(r.get("ram_gb"))]
                storages = [float(r["storage_gb"]) for r in cluster if pd.notna(r.get("storage_gb"))]

                rep = cluster[0]
                for r in cluster:
                    enriched_rows.append({**r, "canonical_product_id": cid})

                product_records.append(
                    {
                        "canonical_product_id": cid,
                        "category": cat,
                        "brand": rep["brand"],
                        "model_clean": rep["model_clean"],
                        "cpu_model": rep["cpu_model"],
                        "ram_gb": int(pd.Series(rams).median()) if rams else None,
                        "storage_gb": int(pd.Series(storages).median()) if storages else None,
                        "gpu_model": next((r.get("gpu_model") for r in cluster if r.get("gpu_model")), None),
                        "screen_size_inch": next(
                            (float(r["screen_size_inch"]) for r in cluster if pd.notna(r.get("screen_size_inch"))),
                            None,
                        ),
                        "price_min": min(prices),
                        "price_median": float(pd.Series(prices).median()),
                        "price_max": max(prices),
                        "listing_count": len(cluster),
                        "retailer_count": len(sellers),
                        "retailers": "|".join(sellers),
                        "total_reviews": sum(reviews),
                        "avg_rating": sum(ratings) / len(ratings) if ratings else None,
                    }
                )

    PRODUCT_COLUMNS = [
        "canonical_product_id",
        "category",
        "brand",
        "model_clean",
        "cpu_model",
        "ram_gb",
        "storage_gb",
        "gpu_model",
        "screen_size_inch",
        "price_min",
        "price_median",
        "price_max",
        "listing_count",
        "retailer_count",
        "retailers",
        "total_reviews",
        "avg_rating",
    ]
    products_df = pd.DataFrame(
        product_records, columns=PRODUCT_COLUMNS if not product_records else None
    )
    return enriched_rows, products_df


def build_bipartite_graph(
    enriched_rows: list[dict[str, Any]],
    products_df: pd.DataFrame,
) -> nx.Graph:
    """Build NetworkX bipartite graph between Retailers (bipartite=0) and Canonical Products (bipartite=1)."""
    G = nx.Graph()
    retailers = sorted({r["seller_name"] for r in enriched_rows})
    for ret in retailers:
        G.add_node(ret, bipartite=0, node_type="retailer", label=ret)

    for _, prod in products_df.iterrows():
        cid = prod["canonical_product_id"]
        G.add_node(
            cid,
            bipartite=1,
            node_type="product",
            label=f"{prod['brand']} {prod['model_clean']}",
            category=prod["category"],
            brand=prod["brand"],
            model_clean=prod["model_clean"],
            cpu_model=prod["cpu_model"],
            price_median=float(prod["price_median"]),
        )

    # Aggregate edges (retailer, canonical_product_id)
    edge_agg: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in enriched_rows:
        edge_agg[(r["seller_name"], r["canonical_product_id"])].append(float(r["price_vnd"]))

    for (ret, cid), prices in edge_agg.items():
        G.add_edge(
            ret,
            cid,
            price_min=min(prices),
            price_median=float(pd.Series(prices).median()),
            listing_count=len(prices),
        )

    # Annotate degree & exclusivity on product nodes
    for cid in products_df["canonical_product_id"]:
        deg = G.degree(cid)
        G.nodes[cid]["degree"] = deg
        G.nodes[cid]["exclusivity"] = "exclusive" if deg == 1 else "competitive"

    return G


def compute_jaccard_matrix(G: nx.Graph, retailers: list[str] | None = None) -> pd.DataFrame:
    """Compute pairwise Jaccard Similarity between retailer product sets."""
    if retailers is None:
        retailers = sorted([n for n, d in G.nodes(data=True) if d.get("bipartite") == 0])

    neighbor_sets = {ret: set(G.neighbors(ret)) for ret in retailers}
    matrix = pd.DataFrame(index=retailers, columns=retailers, dtype=float)
    for r1 in retailers:
        for r2 in retailers:
            s1, s2 = neighbor_sets[r1], neighbor_sets[r2]
            union = len(s1 | s2)
            matrix.loc[r1, r2] = (len(s1 & s2) / union) if union > 0 else 0.0
    return matrix


def compute_retailer_degree_stats(G: nx.Graph, products_df: pd.DataFrame) -> pd.DataFrame:
    """Compute exclusive (degree=1) vs competitive (degree>1) counts and price leadership per retailer.

    ``avg_price_premium_pct`` keeps its name for downstream compatibility but is now a
    *guarded* mean: pairs whose price is more than ``MAX_PLAUSIBLE_PREMIUM_RATIO`` times
    the cheapest seller are excluded as entity-resolution anomalies instead of being
    averaged in. ``median_price_premium_pct`` is reported alongside it, and
    ``price_premium_pairs_excluded`` makes the exclusion auditable.
    """
    deg_map = {n: G.degree(n) for n, d in G.nodes(data=True) if d.get("bipartite") == 1}
    products_df["degree"] = products_df["canonical_product_id"].map(deg_map)
    products_df["exclusivity"] = products_df["degree"].apply(lambda d: "exclusive" if d == 1 else "competitive")

    # Floor price for each competitive product across retailers
    competitive_floor_price: dict[str, float] = {}
    for p, deg in deg_map.items():
        if deg > 1:
            competitive_floor_price[p] = min(
                float(G[ret][p]["price_median"]) for ret in G.neighbors(p)
            )

    retailers = sorted([n for n, d in G.nodes(data=True) if d.get("bipartite") == 0])
    records: list[dict[str, Any]] = []
    for ret in retailers:
        prods = list(G.neighbors(ret))
        excl = sum(1 for p in prods if deg_map.get(p, 0) == 1)
        comp = len(prods) - excl

        # Price leadership & price premium on competitive products
        wins = 0
        premiums: list[float] = []
        excluded = 0
        for p in prods:
            if deg_map.get(p, 0) > 1 and p in competitive_floor_price:
                ret_price = float(G[ret][p]["price_median"])
                min_price = competitive_floor_price[p]
                if ret_price <= min_price + 1e-4:
                    wins += 1
                if min_price > 0:
                    ratio = ret_price / min_price
                    if ratio > MAX_PLAUSIBLE_PREMIUM_RATIO:
                        excluded += 1
                    else:
                        premiums.append((ratio - 1.0) * 100.0)

        win_rate = round(wins / comp * 100.0, 2) if comp > 0 else 0.0
        avg_premium = round(float(pd.Series(premiums).mean()), 2) if premiums else 0.0
        median_premium = round(float(pd.Series(premiums).median()), 2) if premiums else 0.0

        records.append(
            {
                "retailer": ret,
                "total_canonical_products": len(prods),
                "exclusive_count": excl,
                "competitive_count": comp,
                "exclusive_pct": round(excl / len(prods) * 100, 2) if prods else 0.0,
                "price_leader_win_rate_pct": win_rate,
                "avg_price_premium_pct": avg_premium,
                "median_price_premium_pct": median_premium,
                "price_premium_pairs_used": len(premiums),
                "price_premium_pairs_excluded": excluded,
            }
        )
    return pd.DataFrame(records)



def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


# Closed whitelist of the TV5/TV8 handoff. Adding a column here requires updating the
# leakage contract test and docs section 7. Nothing in this list may be derived from
# price: no community_id/segment_label/price_band/price_*/retailer_count/degree.
HANDOFF_COLUMNS: list[str] = [
    "listing_record_id",
    "source",
    "category",
    "canonical_product_id",
    "brand",
    "model_clean",
    "ram_gb",
    "storage_gb",
    "cpu_model",
    "cpu_perf_rating",
    "gpu_perf_rating",
    "cpu_benchmark_score",
    "cpu_geekbench_5_multi",
    "cpu_perf_percentile",
    "hw_seller_count",
    "hw_listing_count",
    "hw_key_complete",
    "pipeline_run_id",
]

# Columns that exist only to join/lineage, never as model features.
HANDOFF_LINEAGE_ONLY: frozenset[str] = frozenset(
    {"listing_record_id", "canonical_product_id", "pipeline_run_id"}
)

HANDOFF_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "price",
    "community",
    "segment",
    "band",
    "retailer_count",
    "degree",
)


def observed_hw_key(row: dict[str, Any]) -> tuple[str, bool]:
    """Build the price-free hardware key from *observed* specs only.

    Returns ``(key, complete)``. ``complete`` is False when any of
    category/brand/model/ram/storage is missing, because a partial key would collapse
    otherwise different configurations.
    """
    category = _norm_token(row.get("category_clean") or row.get("category"))
    brand = _norm_token(row.get("brand"))
    model = _norm_token(row.get("model_clean"))
    ram = _norm_spec_val(row.get("ram_gb"))
    storage = _norm_spec_val(row.get("storage_gb"))
    complete = bool(category and brand and model and ram and storage)
    return "|".join([category, brand, model, ram, storage]), complete


def compute_hw_seller_stats(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Count sellers per observed hardware key (price is never read)."""
    records = []
    for row in rows:
        key, complete = observed_hw_key(row)
        records.append(
            {
                "hw_key": key,
                "hw_key_complete": complete,
                "seller_name": row.get("seller_name"),
            }
        )
    if not records:
        return pd.DataFrame(
            columns=["hw_key", "hw_key_complete", "hw_seller_count", "hw_listing_count"]
        )

    df = pd.DataFrame(records)
    complete_keys = df[df["hw_key_complete"]]
    aggregated = (
        complete_keys.groupby("hw_key")
        .agg(hw_seller_count=("seller_name", "nunique"), hw_listing_count=("seller_name", "size"))
        .reset_index()
    )
    keys = df[["hw_key", "hw_key_complete"]].drop_duplicates()
    merged = keys.merge(aggregated, on="hw_key", how="left")
    incomplete = ~merged["hw_key_complete"]
    merged.loc[incomplete, ["hw_seller_count", "hw_listing_count"]] = pd.NA
    return merged


def _benchmark_handoff_rows(
    laptop_rows: list[dict[str, Any]],
    smartphone_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in laptop_rows:
        records.append(
            {
                "listing_record_id": row.get("listing_record_id"),
                "cpu_perf_rating": row.get("cpu_perf_rating"),
                "gpu_perf_rating": row.get("gpu_perf_rating"),
                "cpu_benchmark_score": None,
                "cpu_geekbench_5_multi": None,
            }
        )
    for row in smartphone_rows:
        records.append(
            {
                "listing_record_id": row.get("listing_record_id"),
                "cpu_perf_rating": row.get("cpu_perf_rating"),
                "gpu_perf_rating": None,
                "cpu_benchmark_score": row.get("cpu_benchmark_score"),
                "cpu_geekbench_5_multi": row.get("cpu_geekbench_5_multi"),
            }
        )
    frame = pd.DataFrame(
        records,
        columns=[
            "listing_record_id",
            "cpu_perf_rating",
            "gpu_perf_rating",
            "cpu_benchmark_score",
            "cpu_geekbench_5_multi",
        ],
    )
    if frame.empty:
        return frame
    numeric = [
        "cpu_perf_rating",
        "gpu_perf_rating",
        "cpu_benchmark_score",
        "cpu_geekbench_5_multi",
    ]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.drop_duplicates(subset=["listing_record_id"], keep="first")


def build_price_free_handoff(
    work_dir: Path = DEFAULT_WORK_DIR,
    listings: list[dict[str, Any]] | None = None,
    observed_rows: list[dict[str, Any]] | None = None,
    laptop_benchmarks: list[dict[str, Any]] | None = None,
    smartphone_benchmarks: list[dict[str, Any]] | None = None,
    pipeline_run_id: str | None = None,
) -> pd.DataFrame:
    """Assemble the price-free TV5/TV8 feature table.

    Every argument is injectable so tests can prove that price never enters the output.
    Specs are taken from ``products_llm_cleaned.jsonl`` (Step 1, *before* imputation)
    because ``_impute_unknown_specs`` fills values through a +/-10% price window.
    """
    if listings is None:
        listings = _read_jsonl_records(work_dir / "canonical_listings.jsonl")
    if observed_rows is None:
        observed_rows = _read_jsonl_records(work_dir / "products_llm_cleaned.jsonl")
    if laptop_benchmarks is None:
        laptop_benchmarks = _read_jsonl_records(work_dir / "laptop_benchmarks.jsonl")
    if smartphone_benchmarks is None:
        smartphone_benchmarks = _read_jsonl_records(work_dir / "smartphone_benchmarks.jsonl")
    run_id = pipeline_run_id or os.environ.get("TV4_RUN_ID", "tv4-20261123")

    listings_df = pd.DataFrame(listings)
    if listings_df.empty:
        return pd.DataFrame(columns=HANDOFF_COLUMNS)

    observed_df = pd.DataFrame(observed_rows)
    if observed_df.empty:
        observed_df = pd.DataFrame(columns=["listing_record_id"])
    observed_keys = []
    for row in observed_rows:
        key, complete = observed_hw_key(row)
        observed_keys.append(
            {
                "listing_record_id": row.get("listing_record_id"),
                "obs_category": row.get("category_clean") or row.get("category"),
                "obs_brand": row.get("brand"),
                "obs_model_clean": row.get("model_clean"),
                "obs_cpu_model": row.get("cpu_model"),
                "obs_ram_gb": row.get("ram_gb"),
                "obs_storage_gb": row.get("storage_gb"),
                "hw_key": key,
                "hw_key_complete": complete,
            }
        )
    observed_df = pd.DataFrame(observed_keys).drop_duplicates(subset=["listing_record_id"])

    base_cols = [
        "listing_record_id",
        "source",
        "canonical_product_id",
        "category_clean",
        "brand",
        "model_clean",
        "cpu_model",
        "ram_gb",
        "storage_gb",
    ]
    base = listings_df[[c for c in base_cols if c in listings_df.columns]].copy()

    merged = base.merge(
        observed_df[
            [
                "listing_record_id",
                "obs_category",
                "obs_brand",
                "obs_model_clean",
                "obs_cpu_model",
                "obs_ram_gb",
                "obs_storage_gb",
                "hw_key",
                "hw_key_complete",
            ]
        ],
        on="listing_record_id",
        how="left",
    )

    # Category/brand/model are never imputed through price, so a listings fallback is
    # harmless there. Spec columns are NOT allowed to fall back: Step 2 imputes
    # ram/storage/cpu inside a +/-10% price window, so a fallback value would smuggle
    # price back into a "price-free" feature. Missing observed spec stays NaN.
    merged["category"] = merged["obs_category"].where(merged["obs_category"].notna(), merged.get("category_clean"))
    merged["brand"] = merged["obs_brand"].where(merged["obs_brand"].notna(), merged.get("brand"))
    merged["model_clean"] = merged["obs_model_clean"].where(
        merged["obs_model_clean"].notna(), merged.get("model_clean")
    )
    merged["cpu_model"] = merged["obs_cpu_model"]
    merged["ram_gb"] = merged["obs_ram_gb"]
    merged["storage_gb"] = merged["obs_storage_gb"]
    merged["hw_key_complete"] = merged["hw_key_complete"].fillna(False).astype(bool)

    hw_stats = compute_hw_seller_stats(observed_rows).drop(columns=["hw_key_complete"])
    merged = merged.merge(hw_stats, on="hw_key", how="left")

    bench = _benchmark_handoff_rows(laptop_benchmarks, smartphone_benchmarks)
    if not bench.empty:
        merged = merged.merge(bench, on="listing_record_id", how="left")
    else:
        for column in ("cpu_perf_rating", "gpu_perf_rating", "cpu_benchmark_score", "cpu_geekbench_5_multi"):
            merged[column] = pd.NA

    ratings = pd.to_numeric(merged["cpu_perf_rating"], errors="coerce")
    merged["cpu_perf_percentile"] = (
        ratings.groupby(merged["category"]).rank(pct=True).mul(100).round(2)
    )
    merged["pipeline_run_id"] = run_id

    for column in HANDOFF_COLUMNS:
        if column not in merged.columns:
            merged[column] = pd.NA

    handoff = merged[HANDOFF_COLUMNS].sort_values("listing_record_id").reset_index(drop=True)
    return handoff


def export_price_free_handoff(work_dir: Path = DEFAULT_WORK_DIR) -> Path:
    """Build and write the price-free handoff CSV (single artifact for TV5/TV8)."""
    out_dir = work_dir / "handoff"
    out_dir.mkdir(parents=True, exist_ok=True)
    handoff = build_price_free_handoff(work_dir=work_dir)
    out_path = out_dir / "tv5_tv8_price_free_features.csv"
    handoff.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(
        f"[Handoff] {len(handoff)} listings -> {out_path} | "
        f"hw_seller_count coverage {int(handoff['hw_seller_count'].notna().sum())}/{len(handoff)} | "
        f"cpu_perf_rating coverage {int(pd.to_numeric(handoff['cpu_perf_rating'], errors='coerce').notna().sum())}/{len(handoff)}"
    )
    return out_path


def run_step2(
    input_path: Path = DEFAULT_INPUT,
    work_dir: Path = DEFAULT_WORK_DIR,
    max_spread: float = 0.20,
) -> tuple[nx.Graph, pd.DataFrame, dict[str, pd.DataFrame]]:
    work_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    enriched_rows, products_df = resolve_canonical_products(rows, max_spread=max_spread)
    G = build_bipartite_graph(enriched_rows, products_df)

    # Keep overall degree/exclusivity columns on canonical_products.csv for Step 3.
    compute_retailer_degree_stats(G, products_df)

    # Persist listing-level and product-level outputs.
    listings_out = work_dir / "canonical_listings.jsonl"
    with listings_out.open("w", encoding="utf-8") as f:
        for r in enriched_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    products_df.to_csv(work_dir / "canonical_products.csv", index=False, encoding="utf-8-sig")

    retailers = sorted(
        n for n, d in G.nodes(data=True) if d.get("bipartite") == 0
    )
    jaccard_by_cat: dict[str, pd.DataFrame] = {}

    print(f"[Step 2] Resolved {len(enriched_rows)} listings -> {len(products_df)} canonical products.")
    for cat in ("laptop", "smartphone"):
        products_all_cat = products_df[products_df["category"] == cat].copy()
        # Floor applies to the per-category analysis view only; the full canonical
        # table above keeps every row for TV5/TV7/TV8 lineage.
        products_df_cat = filter_min_price(products_all_cat, log_prefix=f"[Step 2] {cat.title()}")
        product_ids = products_df_cat["canonical_product_id"].tolist()
        G_cat = G.subgraph(retailers + product_ids).copy()

        retailer_stats_cat = compute_retailer_degree_stats(G_cat, products_df_cat)
        jaccard_cat = compute_jaccard_matrix(G_cat, retailers)
        jaccard_by_cat[cat] = jaccard_cat

        jaccard_cat.to_csv(work_dir / f"jaccard_matrix_{cat}.csv", encoding="utf-8-sig")
        retailer_stats_cat.to_csv(
            work_dir / f"retailer_degree_stats_{cat}.csv",
            index=False,
            encoding="utf-8-sig",
        )
        nx.write_gexf(G_cat, work_dir / f"bipartite_market_graph_{cat}.gexf")

        excl_total = int((products_df_cat["degree"] == 1).sum())
        comp_total = int((products_df_cat["degree"] > 1).sum())
        print(
            f"[Step 2] {cat.title()}: {len(products_df_cat)} canonical products "
            f"| Exclusive (degree=1): {excl_total} | Competitive (degree>1): {comp_total}"
        )
        print(f"[Step 2] {cat.title()} retailer degree stats:\n" + retailer_stats_cat.to_string(index=False))
        print(f"[Step 2] {cat.title()} Jaccard matrix:\n" + jaccard_cat.round(4).to_string())

    return G, products_df, jaccard_by_cat
