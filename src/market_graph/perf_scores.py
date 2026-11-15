"""Performance-score enrichment for Step 3 canonical products.

Canonical products are built at listing level. This module aggregates the
benchmark scores produced by Step 1.5 back to ``canonical_product_id``,
imputes missing CPU scores from the same category + ``cpu_tier`` median, and
normalizes scores to [0, 1] per category.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = PROJECT_ROOT / "data" / "market_graph"

DISCRETE_GPU_RE = re.compile(
    r"\b(?:rtx|gtx|mx\s?\d{3}[a-z]?|max-q|quadro|rtx\s+pro|radeon\s+rx\s+(?!vega)|radeon\s+pro|"
    r"arc\s+[ab]\d{3}m?|iris\s+xe\s+max)\b"
)
INTEGRATED_GPU_RE = re.compile(
    r"\b(?:intel\s+(?:uhd|hd|iris|graphics)|intel\s+arc\s+(?:graphics|1[34]0[vt])|arc\s+1[34]0[vt]|"
    r"amd\s+radeon\s+graphics|radeon\s+graphics|radeon\s+(?:rx\s+)?vega|radeon\s+\d{3}m\b|"
    r"apple\s+\d+-core\s+gpu|qualcomm\s+adreno|adreno)\b"
)


def is_discrete_gpu(gpu_model: Any) -> str:
    """Classify a GPU string as discrete, integrated, or unknown."""
    text = str(gpu_model or "").strip().lower()
    if not text or text in {"nan", "none", "unknown"}:
        return "unknown"
    if re.search(r"\biris\s+xe\s+max\b", text):
        return "discrete"
    if "igpu" in text or "vega" in text or INTEGRATED_GPU_RE.search(text):
        return "integrated"
    if DISCRETE_GPU_RE.search(text):
        return "discrete"
    return "unknown"


def relative_perf_diff(score_a: Any, score_b: Any) -> float | None:
    """Relative performance difference: |a-b| / max(a,b)."""
    if score_a is None or score_b is None or pd.isna(score_a) or pd.isna(score_b):
        return None
    a, b = float(score_a), float(score_b)
    denominator = max(a, b)
    if denominator <= 0:
        return None
    return abs(a - b) / denominator


def perf_close(score_a: Any, score_b: Any, tol: float = 0.15) -> bool:
    diff = relative_perf_diff(score_a, score_b)
    return diff is not None and diff <= tol


def _read_jsonl(path: Path) -> pd.DataFrame:
    try:
        return pd.read_json(path, lines=True)
    except ValueError:
        return pd.DataFrame()


def _empty_scores() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["canonical_product_id", "listing_cpu_score", "listing_gpu_score", "listing_cpu_metric"]
    )


def _scores_from_listings(work_dir: Path) -> pd.DataFrame | None:
    listings_path = work_dir / "canonical_listings.jsonl"
    laptop_path = work_dir / "laptop_benchmarks.jsonl"
    phone_path = work_dir / "smartphone_benchmarks.jsonl"
    if not listings_path.exists():
        return None
    if not laptop_path.exists() and not phone_path.exists():
        return None

    listings = _read_jsonl(listings_path)
    if "canonical_product_id" not in listings.columns:
        return None
    merged = listings[["listing_record_id", "canonical_product_id"]].copy()

    if laptop_path.exists():
        laptop = _read_jsonl(laptop_path)
        if "listing_record_id" in laptop.columns:
            keep = [
                column
                for column in ("listing_record_id", "cpu_perf_rating", "gpu_perf_rating")
                if column in laptop.columns
            ]
            merged = merged.merge(laptop[keep], on="listing_record_id", how="left")

    if phone_path.exists():
        phone = _read_jsonl(phone_path)
        if "listing_record_id" in phone.columns:
            keep = [
                column
                for column in ("listing_record_id", "cpu_benchmark_score", "cpu_benchmark_metric")
                if column in phone.columns
            ]
            merged = merged.merge(phone[keep], on="listing_record_id", how="left")

    if "cpu_perf_rating" in merged.columns and "cpu_benchmark_score" in merged.columns:
        merged["listing_cpu_score"] = merged["cpu_perf_rating"].fillna(merged["cpu_benchmark_score"])
    elif "cpu_perf_rating" in merged.columns:
        merged["listing_cpu_score"] = merged["cpu_perf_rating"]
    elif "cpu_benchmark_score" in merged.columns:
        merged["listing_cpu_score"] = merged["cpu_benchmark_score"]
    else:
        merged["listing_cpu_score"] = np.nan

    merged["listing_gpu_score"] = (
        merged["gpu_perf_rating"] if "gpu_perf_rating" in merged.columns else np.nan
    )

    if merged["listing_cpu_score"].isna().all() and merged["listing_gpu_score"].isna().all():
        return None

    agg_dict: dict[str, tuple[str, str]] = {
        "listing_cpu_score": ("listing_cpu_score", "median"),
        "listing_gpu_score": ("listing_gpu_score", "median"),
    }
    if "cpu_benchmark_metric" in merged.columns:
        agg_dict["listing_cpu_metric"] = ("cpu_benchmark_metric", "first")

    aggregated = (
        merged.groupby("canonical_product_id", as_index=False)
        .agg(**agg_dict)
    )
    return aggregated


def _scores_from_products(df: pd.DataFrame, work_dir: Path) -> pd.DataFrame:
    """Fallback: match canonical cpu_model/gpu_model directly to benchmark CSVs."""
    bench_dir = work_dir / "benchmarks"
    cpu_csv = bench_dir / "cpu_benchmarks.csv"
    gpu_csv = bench_dir / "gpu_benchmarks.csv"
    phone_csv = bench_dir / "cpu_phone_benchmarks.csv"
    if not phone_csv.exists() and not (cpu_csv.exists() and gpu_csv.exists()):
        return _empty_scores()

    cpu_index = gpu_index = phone_main = phone_alias = None
    apple_variants = None
    match_cpu = match_gpu = match_phone_cpu = None

    if cpu_csv.exists() and gpu_csv.exists():
        from src.market_graph.laptop_benchmark_match import (
            _build_apple_variants,
            _load_benchmark_index,
            match_cpu,
            match_gpu,
        )

        cpu_index = _load_benchmark_index(cpu_csv)
        gpu_index = _load_benchmark_index(gpu_csv)
        apple_variants = _build_apple_variants(cpu_index)

    if phone_csv.exists():
        from src.market_graph.smartphone_benchmark_match import (
            _load_phone_index,
            match_phone_cpu,
        )

        phone_main, phone_alias = _load_phone_index(phone_csv)

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        cpu_score = None
        gpu_score = None
        cpu_metric = None
        if row.get("category") == "laptop" and cpu_index is not None:
            matched, _ = match_cpu(row.get("cpu_model"), row.get("gpu_model"), cpu_index, apple_variants)
            if matched:
                cpu_score = matched["perf_rating"]
                cpu_metric = "notebookcheck_perf_rating"
            matched_gpu, _ = match_gpu(row.get("cpu_model"), row.get("gpu_model"), gpu_index)
            if matched_gpu:
                gpu_score = matched_gpu["perf_rating"]
        elif row.get("category") == "smartphone" and phone_main is not None:
            matched, _ = match_phone_cpu(row.get("cpu_model"), phone_main, phone_alias)
            if matched:
                cpu_score = matched["benchmark_score"]
                cpu_metric = matched.get("benchmark_metric") or "geekbench_5_multi_core"
        rows.append(
            {
                "canonical_product_id": row.get("canonical_product_id"),
                "listing_cpu_score": cpu_score,
                "listing_gpu_score": gpu_score,
                "listing_cpu_metric": cpu_metric,
            }
        )
    return pd.DataFrame(rows)


def _normalize(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    minimum = numeric.min()
    maximum = numeric.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return numeric.where(numeric.isna(), 0.0)
    return ((numeric - minimum) / (maximum - minimum)).clip(0.0, 1.0)


def enrich_perf_scores(
    products_df: pd.DataFrame,
    work_dir: Path = DEFAULT_WORK_DIR,
    use_benchmarks: bool = True,
) -> pd.DataFrame:
    """Attach raw/normalized CPU & GPU performance scores to canonical products."""
    df = products_df.reset_index(drop=True).copy()
    score_columns = [
        "cpu_perf_score",
        "gpu_perf_score",
        "cpu_perf_metric",
        "gpu_perf_metric",
        "cpu_score_source",
        "gpu_score_source",
        "cpu_perf_norm",
        "gpu_perf_norm",
        "gpu_type",
    ]
    for column in score_columns:
        if column not in df.columns:
            df[column] = None

    if not use_benchmarks:
        return df

    scores = _scores_from_listings(work_dir)
    if scores is None:
        scores = _scores_from_products(df, work_dir)

    if not scores.empty:
        df = df.merge(scores, on="canonical_product_id", how="left")
    else:
        df["listing_cpu_score"] = np.nan
        df["listing_gpu_score"] = np.nan

    df["cpu_perf_score"] = pd.to_numeric(df["listing_cpu_score"], errors="coerce")
    df["gpu_perf_score"] = pd.to_numeric(df["listing_gpu_score"], errors="coerce")
    df["cpu_score_source"] = np.where(df["cpu_perf_score"].notna(), "listing_median", "missing")
    df["gpu_score_source"] = np.where(df["gpu_perf_score"].notna(), "listing_median", "missing")

    laptop_mask = df["category"] == "laptop"
    df.loc[laptop_mask, "cpu_perf_metric"] = "notebookcheck_perf_rating"
    df.loc[laptop_mask, "gpu_perf_metric"] = "notebookcheck_perf_rating"
    if "listing_cpu_metric" in df.columns:
        df.loc[~laptop_mask, "cpu_perf_metric"] = df.loc[~laptop_mask, "listing_cpu_metric"].fillna("geekbench_5_multi_core")
    else:
        df.loc[~laptop_mask, "cpu_perf_metric"] = "geekbench_5_multi_core"

    missing_cpu = df["cpu_perf_score"].isna()
    if missing_cpu.any() and "cpu_tier" in df.columns:
        known = df[df["cpu_perf_score"].notna()]
        medians = known.groupby(["category", "cpu_tier"])["cpu_perf_score"].median()
        counts = known.groupby(["category", "cpu_tier"])["cpu_perf_score"].count()
        valid_tiers = counts[counts >= 3].index
        for idx, row in df[missing_cpu].iterrows():
            tier = row.get("cpu_tier")
            key = (row.get("category"), tier)
            if tier not in (None, "", "unknown") and key in valid_tiers:
                df.at[idx, "cpu_perf_score"] = float(medians.loc[key])
                df.at[idx, "cpu_score_source"] = "tier_median"
                df.at[idx, "cpu_perf_metric"] = (
                    "notebookcheck_perf_rating"
                    if row.get("category") == "laptop"
                    else "geekbench_5_multi_core"
                )

    df["gpu_type"] = df["gpu_model"].apply(is_discrete_gpu) if "gpu_model" in df.columns else "unknown"
    for _, group in df.groupby("category"):
        df.loc[group.index, "cpu_perf_norm"] = _normalize(group["cpu_perf_score"])
        df.loc[group.index, "gpu_perf_norm"] = _normalize(group["gpu_perf_score"])

    return df.drop(columns=["listing_cpu_score", "listing_gpu_score", "listing_cpu_metric"], errors="ignore")
