"""Match smartphone listings with Notebookcheck phone CPU benchmarks.

The saved ``notebookcheck_cpu_phone.html`` snapshot does not include the
``Perf. Rating`` column, so ``cpu_perf_rating`` is *derived* here from
``cpu_benchmark_score``: ``100 * score / max(score)`` on the phone benchmark table.
The proportional (through-origin) scale is deliberate: it keeps the relative gaps
used by Step 3 edges exactly unchanged, so the Louvain graph does not churn when the
column is populated. ``cpu_perf_percentile`` gives a rank view for models that want
one, and ``cpu_perf_rating_is_approx`` marks the value as derived.

Outputs (originals are never modified):
  - data/market_graph/smartphone_benchmarks.csv
  - data/market_graph/smartphone_benchmarks.jsonl
  - data/market_graph/benchmarks/smartphone_match_report.csv
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.market_graph.benchmark_extract import (
    PHONE_CPU_CSV,
    clean_text,
    phone_cpu_match_keys,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = PROJECT_ROOT / "data" / "market_graph"
BENCHMARK_DIR = WORK_DIR / "benchmarks"
DEFAULT_INPUT = WORK_DIR / "products_llm_cleaned.jsonl"
DEFAULT_OUTPUT_CSV = WORK_DIR / "smartphone_benchmarks.csv"
DEFAULT_OUTPUT_JSONL = WORK_DIR / "smartphone_benchmarks.jsonl"
DEFAULT_REPORT_CSV = BENCHMARK_DIR / "smartphone_match_report.csv"

GENERIC_PHONE_CPU_KEYS = {
    "",
    "unknown",
    "snapdragon",
    "exynos",
    "helio",
    "dimensity",
    "kirin",
    "tensor",
    "mediatek",
    "unisoc",
    "qualcomm",
    "samsung",
    "google",
    "hisilicon",
    "spreadtrum",
    "rockchip",
    "intel",
    "apple",
}
SCORE_COLUMNS = [
    "geekbench_5_single",
    "geekbench_5_multi",
    "geekbench_4_single",
    "geekbench_4_multi",
    "passmark",
    "sunspider",
]


def _clean_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _load_products(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
        return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}: {exc}") from exc
    return rows


def _row_weight(row: dict[str, Any]) -> tuple[float, int]:
    score = _clean_float(row.get("benchmark_score")) or _clean_float(row.get("geekbench_5_multi")) or 0.0
    filled = sum(1 for column in SCORE_COLUMNS if _clean_float(row.get(column)) is not None)
    return score, filled


def _add_to_index(index: dict[str, dict[str, Any]], key: str, row: dict[str, Any]) -> None:
    if not key:
        return
    if key not in index or _row_weight(row) > _row_weight(index[key]):
        index[key] = row


def _load_phone_index(csv_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    main_index: dict[str, dict[str, Any]] = {}
    alias_index: dict[str, dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        main_key = clean_text(row.get("match_key"))
        _add_to_index(main_index, main_key, row)
        aliases = str(row.get("match_alias_keys") or "")
        for alias in aliases.split(";"):
            alias_key = clean_text(alias)
            if alias_key and alias_key != main_key:
                _add_to_index(alias_index, alias_key, row)
    return main_index, alias_index


def _result(
    row: dict[str, Any],
    method: str,
    confidence: str,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "bench_model": row.get("model"),
        "benchmark_score": _clean_float(row.get("benchmark_score")),
        "benchmark_metric": row.get("benchmark_metric"),
        "geekbench_5_single": _clean_float(row.get("geekbench_5_single")),
        "geekbench_5_multi": _clean_float(row.get("geekbench_5_multi")),
        "geekbench_4_multi": _clean_float(row.get("geekbench_4_multi")),
        "passmark": _clean_float(row.get("passmark")),
        "match_method": method,
        "match_confidence": confidence,
        "match_note": note,
    }


def match_phone_cpu(
    cpu_model: Any,
    main_index: dict[str, dict[str, Any]],
    alias_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    key, product_aliases = phone_cpu_match_keys(str(cpu_model or ""))
    if not key or key in GENERIC_PHONE_CPU_KEYS:
        return None, "generic_or_non_cpu"

    if key in main_index:
        return _result(main_index[key], "exact", "high"), None

    if key in alias_index:
        return _result(alias_index[key], "parenthetical_alias", "medium"), None

    for alias in product_aliases:
        if alias in main_index:
            return _result(main_index[alias], "product_alias", "medium"), None
        if alias in alias_index:
            return _result(alias_index[alias], "product_alias", "medium"), None

    suffix_variants = [
        (f" {suffix}", suffix) for suffix in ("ultimate", "ultra", "energy", "aie")
    ] + [("+", "+")]
    for suffix, label in suffix_variants:
        if key.endswith(suffix):
            base_key = key[: -len(suffix)].strip()
            if base_key in main_index:
                return (
                    _result(
                        main_index[base_key],
                        "variant_base",
                        "low",
                        f"bỏ hậu tố '{label}' để khớp model gốc",
                    ),
                    None,
                )

    prefix_matches = [candidate for candidate in main_index if candidate.startswith(key + " ")]
    if len(prefix_matches) == 1:
        return _result(main_index[prefix_matches[0]], "unique_prefix", "medium"), None

    return None, "not_in_benchmark"



def _rating_scale(table: pd.DataFrame) -> tuple[float | None, np.ndarray]:
    """Return (max benchmark score, sorted scores) used to derive ratings."""
    if "benchmark_score" not in table.columns:
        return None, np.array([])
    scores = pd.to_numeric(table["benchmark_score"], errors="coerce").dropna()
    if scores.empty:
        return None, np.array([])
    return float(scores.max()), np.sort(scores.to_numpy(dtype=float))


def derive_cpu_perf_rating(
    score: float | None,
    max_score: float | None,
    sorted_scores: np.ndarray,
) -> tuple[float | None, float | None]:
    """Map a raw benchmark score to a 0-100 rating plus a 0-100 percentile."""
    if score is None or max_score is None or max_score <= 0 or sorted_scores.size == 0:
        return None, None
    rating = round(100.0 * float(score) / max_score, 6)
    percentile = round(100.0 * float(np.searchsorted(sorted_scores, score, side="right")) / sorted_scores.size, 2)
    return rating, percentile


def match_smartphones(
    input_path: Path = DEFAULT_INPUT,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    output_jsonl: Path = DEFAULT_OUTPUT_JSONL,
    report_csv: Path = DEFAULT_REPORT_CSV,
    phone_cpu_csv: Path = PHONE_CPU_CSV,
) -> Path:
    if not phone_cpu_csv.exists():
        raise FileNotFoundError(
            f"Missing {phone_cpu_csv}. Run `python -m src.market_graph.benchmark_extract` first."
        )

    products = _load_products(input_path)
    smartphones = [
        row for row in products if clean_text(str(row.get("category_clean") or "")) == "smartphone"
    ]
    if not smartphones:
        print(f"[Match] Warning: No smartphone rows found in {input_path}. Creating empty benchmark outputs.")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["listing_record_id", "cpu_bench_model", "cpu_benchmark_score", "cpu_benchmark_metric"]).to_csv(output_csv, index=False, encoding="utf-8-sig")
        output_jsonl.write_text("", encoding="utf-8")
        pd.DataFrame(columns=["field", "value", "count", "reason"]).to_csv(report_csv, index=False, encoding="utf-8-sig")
        return output_csv

    main_index, alias_index = _load_phone_index(phone_cpu_csv)
    max_score, sorted_scores = _rating_scale(pd.read_csv(phone_cpu_csv, encoding="utf-8-sig"))

    enriched: list[dict[str, Any]] = []
    methods: Counter[str] = Counter()
    unmatched: Counter[str] = Counter()
    reasons: dict[str, str] = {}

    for row in smartphones:
        cpu_model = row.get("cpu_model")
        matched, reason = match_phone_cpu(cpu_model, main_index, alias_index)

        out = dict(row)
        if matched:
            rating, percentile = derive_cpu_perf_rating(
                matched["benchmark_score"], max_score, sorted_scores
            )
            out.update(
                {
                    "cpu_bench_model": matched["bench_model"],
                    "cpu_perf_rating": rating,
                    "cpu_perf_rating_is_approx": True if rating is not None else None,
                    "cpu_perf_rating_coverage_pct": 100.0 if rating is not None else None,
                    "cpu_perf_rating_source": "derived_proportional_cpu_benchmark_score" if rating is not None else None,
                    "cpu_perf_percentile": percentile,
                    "cpu_benchmark_score": matched["benchmark_score"],
                    "cpu_benchmark_metric": matched["benchmark_metric"],
                    "cpu_geekbench_5_single": matched["geekbench_5_single"],
                    "cpu_geekbench_5_multi": matched["geekbench_5_multi"],
                    "cpu_geekbench_4_multi": matched["geekbench_4_multi"],
                    "cpu_passmark": matched["passmark"],
                    "cpu_match_method": matched["match_method"],
                    "cpu_match_confidence": matched["match_confidence"],
                    "cpu_match_note": matched["match_note"],
                }
            )
            methods[matched["match_method"]] += 1
        else:
            out.update(
                {
                    "cpu_bench_model": None,
                    "cpu_perf_rating": None,
                    "cpu_perf_rating_is_approx": None,
                    "cpu_perf_rating_coverage_pct": None,
                    "cpu_perf_rating_source": None,
                    "cpu_perf_percentile": None,
                    "cpu_benchmark_score": None,
                    "cpu_benchmark_metric": None,
                    "cpu_geekbench_5_single": None,
                    "cpu_geekbench_5_multi": None,
                    "cpu_geekbench_4_multi": None,
                    "cpu_passmark": None,
                    "cpu_match_method": "unmatched",
                    "cpu_match_confidence": "none",
                    "cpu_match_note": reason,
                }
            )
            unmatched[str(cpu_model)] += 1
            reasons.setdefault(str(cpu_model), reason or "unknown")

        enriched.append(out)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(enriched).to_csv(output_csv, index=False, encoding="utf-8-sig")
    with output_jsonl.open("w", encoding="utf-8") as handle:
        for row in enriched:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_rows = [
        {"field": "cpu", "value": value, "count": count, "reason": reasons.get(value, "unknown")}
        for value, count in unmatched.most_common()
    ]
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows, columns=["field", "value", "count", "reason"]).to_csv(
        report_csv, index=False, encoding="utf-8-sig"
    )

    scored = sum(1 for row in enriched if row.get("cpu_benchmark_score") is not None)
    rated = sum(1 for row in enriched if row.get("cpu_perf_rating") is not None)
    print(
        f"[Match] Smartphone: {len(enriched)} dòng | có benchmark score: {scored} "
        f"({scored / len(enriched):.1%}) | cpu_perf_rating suy ra: {rated} "
        f"({rated / len(enriched):.1%})"
    )
    print(f"[Match] CPU methods: {dict(methods)}")
    print(f"[Match] Outputs: {output_csv} & {output_jsonl}; report: {report_csv}")
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.market_graph.smartphone_benchmark_match",
        description="Enrich smartphone listings with Notebookcheck phone CPU benchmark scores.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_CSV)
    parser.add_argument("--phone-cpu-benchmarks", type=Path, default=PHONE_CPU_CSV)
    args = parser.parse_args()

    match_smartphones(
        input_path=args.input,
        output_csv=args.output_csv,
        output_jsonl=args.output_jsonl,
        report_csv=args.report,
        phone_cpu_csv=args.phone_cpu_benchmarks,
    )


if __name__ == "__main__":
    main()
