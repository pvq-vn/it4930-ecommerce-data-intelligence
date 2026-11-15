"""Match laptop listings with Notebookcheck CPU/GPU performance ratings.

Reads ``data/market_graph/products_llm_cleaned.jsonl`` (or the CSV equivalent),
keeps ``category_clean == "laptop"`` and enriches each row with the matched
Notebookcheck benchmark model and ``perf_rating``.

Outputs (originals are never modified):
  - data/market_graph/laptop_benchmarks.csv
  - data/market_graph/laptop_benchmarks.jsonl
  - data/market_graph/benchmarks/match_report.csv

Matching policy is tiered and always records ``match_method`` /
``match_confidence`` so ambiguous aliases can be audited. Apple GPUs are
intentionally skipped because the Notebookcheck GPU snapshot has no
``Perf. Rating`` for any Apple GPU.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from src.market_graph.benchmark_extract import (
    CPU_CSV,
    GPU_CSV,
    clean_text,
    cpu_match_key,
    gpu_match_key,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORK_DIR = PROJECT_ROOT / "data" / "market_graph"
BENCHMARK_DIR = WORK_DIR / "benchmarks"
DEFAULT_INPUT = WORK_DIR / "products_llm_cleaned.jsonl"
DEFAULT_OUTPUT_CSV = WORK_DIR / "laptop_benchmarks.csv"
DEFAULT_OUTPUT_JSONL = WORK_DIR / "laptop_benchmarks.jsonl"
DEFAULT_REPORT_CSV = BENCHMARK_DIR / "match_report.csv"

APPLE_FAMILY_RE = re.compile(r"^(apple (?:m\d+|a\d+)(?: pro| max| ultra)?)")
APPLE_GPU_CORE_RE = re.compile(r"(\d+)\s*-\s*core\s*gpu")

GENERIC_CPU_KEYS = {
    "",
    "unknown",
    "intel",
    "amd",
    "intel core",
    "intel core ultra",
    "amd ryzen",
    "amd ryzen ai",
    "ryzen ai",
    "snapdragon x",
    "qualcomm snapdragon",
    "intel ai boost",
    "intel ai boost npu",
    "amd xdna npu",
    "core i3",
    "core i5",
    "core i7",
    "core i9",
    "core ultra 5",
    "core ultra 7",
    "core ultra 9",
    "celeron",
    "pentium",
    "athlon",
}
GENERIC_CPU_PATTERNS = [
    re.compile(r"^core i[3579](?:\s+\d+(?:\.\d+)?ghz)?$"),
    re.compile(r"^ryzen [3579]$"),
    re.compile(r"^core ultra [3579]$"),
]

APPLE_CPU_VARIANT_BY_GPU_CORE: dict[tuple[str, int], str] = {
    ("apple m5", 10): "apple m5 10-core",
    ("apple m5", 8): "apple m5 9-core",
    ("apple m4", 10): "apple m4 10-core",
    ("apple m4", 9): "apple m4 9-core",
    ("apple m4", 8): "apple m4 8-core",
    ("apple m3", 10): "apple m3",
    ("apple m3", 8): "apple m3",
    ("apple m2", 10): "apple m2",
    ("apple m2", 8): "apple m2",
    ("apple m1", 8): "apple m1",
    ("apple m1", 7): "apple m1",
    ("apple m1 pro", 16): "apple m1 pro",
    ("apple m1 pro", 14): "apple m1 pro",
    ("apple m2 pro", 19): "apple m2 pro",
    ("apple m2 pro", 16): "apple m2 pro 10-core",
    ("apple m3 pro", 18): "apple m3 pro 12-core",
    ("apple m3 pro", 14): "apple m3 pro 11-core",
    ("apple m4 pro", 20): "apple m4 pro 14-core",
    ("apple m4 pro", 16): "apple m4 pro 12-core",
    ("apple m5 pro", 20): "apple m5 pro 18-core",
    ("apple m5 pro", 16): "apple m5 pro 15-core",
    ("apple m1 max", 32): "apple m1 max",
    ("apple m1 max", 24): "apple m1 max",
    ("apple m2 max", 38): "apple m2 max",
    ("apple m2 max", 30): "apple m2 max",
    ("apple m3 max", 40): "apple m3 max 16-core",
    ("apple m3 max", 30): "apple m3 max 14-core",
    ("apple m4 max", 40): "apple m4 max 16-core",
    ("apple m4 max", 32): "apple m4 max 14-core",
    ("apple m5 max", 40): "apple m5 max",
    ("apple m5 max", 32): "apple m5 max",
    ("apple a18 pro", 5): "apple a18 pro",
}

GPU_ARC_KEYS = {
    "intel arc 130v": "intel arc graphics 130v",
    "intel arc 140v": "intel arc graphics 140v",
    "intel arc 130t": "intel arc graphics 130t",
    "intel arc 140t": "intel arc graphics 140t",
}


def _clean_bool(value: Any) -> bool:
    return bool(value) if not pd.isna(value) else False


def _clean_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _is_generic_cpu(key: str) -> bool:
    if key in GENERIC_CPU_KEYS:
        return True
    return any(pattern.match(key) for pattern in GENERIC_CPU_PATTERNS)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _load_products(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
        return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")
    return _load_jsonl(path)


def _bench_row_weight(row: dict[str, Any]) -> tuple[int, float, float]:
    has_perf = 1 if _clean_float(row.get("perf_rating")) is not None else 0
    coverage = _clean_float(row.get("perf_rating_coverage_pct")) or 0.0
    perf = _clean_float(row.get("perf_rating")) or 0.0
    return has_perf, coverage, perf


def _load_benchmark_index(csv_path: Path) -> dict[str, dict[str, Any]]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    index: dict[str, dict[str, Any]] = {}
    for row in df.to_dict(orient="records"):
        key = clean_text(row.get("match_key"))
        if not key:
            continue
        if key not in index or _bench_row_weight(row) > _bench_row_weight(index[key]):
            index[key] = row
    return index


def _build_apple_variants(cpu_index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, row in cpu_index.items():
        match = APPLE_FAMILY_RE.match(key)
        if match:
            families[match.group(1)].append(row)
    return families


def _result(
    row: dict[str, Any],
    method: str,
    confidence: str,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "bench_model": row.get("model"),
        "perf_rating": _clean_float(row.get("perf_rating")),
        "perf_rating_is_approx": _clean_bool(row.get("perf_rating_is_approx")),
        "perf_rating_coverage_pct": _clean_float(row.get("perf_rating_coverage_pct")),
        "match_method": method,
        "match_confidence": confidence,
        "match_note": note,
    }


def match_cpu(
    cpu_model: Any,
    gpu_model: Any,
    cpu_index: dict[str, dict[str, Any]],
    apple_variants: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    key = cpu_match_key(str(cpu_model or ""))
    if not key or _is_generic_cpu(key):
        return None, "generic_or_non_cpu"

    if key in cpu_index:
        return _result(cpu_index[key], "exact", "high"), None

    family_match = APPLE_FAMILY_RE.match(key)
    if family_match:
        family = family_match.group(1)
        variants = apple_variants.get(family, [])
        if variants:
            gpu_core_match = APPLE_GPU_CORE_RE.search(clean_text(str(gpu_model or "")).lower())
            gpu_cores = int(gpu_core_match.group(1)) if gpu_core_match else None
            if gpu_cores is not None:
                target_key = APPLE_CPU_VARIANT_BY_GPU_CORE.get((family, gpu_cores))
                if target_key and target_key in cpu_index:
                    return (
                        _result(
                            cpu_index[target_key],
                            "apple_gpu_core",
                            "high",
                            f"{family} + {gpu_cores}-core GPU",
                        ),
                        None,
                    )

            if len(variants) == 1:
                return _result(variants[0], "apple_family_single", "medium"), None

            best = max(
                variants,
                key=lambda row: (
                    _clean_float(row.get("perf_rating_coverage_pct")) or 0.0,
                    _clean_float(row.get("perf_rating")) or 0.0,
                ),
            )
            return (
                _result(
                    best,
                    "apple_family_best_coverage",
                    "low",
                    f"{family}: chọn biến thể có coverage cao nhất",
                ),
                None,
            )

    return None, "not_in_benchmark"


def _choose_integrated_gpu(key: str, cpu_key: str) -> tuple[str | None, str | None, str]:
    """Return (target_key, method, confidence) for known generic GPU aliases."""
    if key in {"intel iris xe", "intel iris xe graphics"}:
        if re.search(r"i[79]-", cpu_key):
            return "intel iris xe graphics g7 96eus", "alias_cpu_eu", "medium"
        return "intel iris xe graphics g7 80eus", "alias_cpu_eu", "medium"

    if key in {"intel uhd graphics", "intel uhd"}:
        if re.search(r"i3-(?:1115g4|1125g4)", cpu_key):
            return "intel uhd graphics xe g4 48eus", "alias_cpu_tier", "medium"
        if re.search(r"i[579]-11\d{3}h", cpu_key):
            return "intel uhd graphics xe 32eus (tiger lake-h)", "alias_cpu_tier", "medium"
        if re.search(r"(?:i[3579]-1[23]\d{3}|core [357] \d{3})", cpu_key):
            return "intel uhd graphics 64eus (alder lake 12th gen)", "alias_cpu_tier", "medium"
        if re.search(r"(?:n[56]\d{3}|celeron n[56]|pentium n[56])", cpu_key):
            return "intel uhd graphics 24eus (alder lake-n)", "alias_cpu_tier", "low"
        return None, None, "generic_integrated_no_match"

    if key in {"intel graphics", "intel integrated"}:
        if re.search(r"core ultra [579] 2\d{2}v", cpu_key):
            if re.search(r"core ultra 5 2(?:26|28)v", cpu_key):
                return "intel arc graphics 130v", "alias_cpu_tier", "medium"
            return "intel arc graphics 140v", "alias_cpu_tier", "medium"
        if re.search(r"core ultra [579] 2\d{2}h", cpu_key):
            if re.search(r"core ultra 5 2(?:25|35)h", cpu_key):
                return "intel arc graphics 130t", "alias_cpu_tier", "medium"
            return "intel arc graphics 140t", "alias_cpu_tier", "medium"
        if re.search(r"core ultra [579] (?:1\d{2}[hu]|2\d{2}u)", cpu_key):
            return "intel graphics 4-core igpu (meteor / arrow lake)", "alias_generation", "medium"
        if re.search(r"core ultra x[79] 3\d{2}h", cpu_key):
            return "intel graphics 4 xe3 panther lake igpu", "alias_generation", "medium"
        return None, None, "generic_integrated_no_match"

    if key in {"intel arc graphics", "intel arc"}:
        if re.search(r"core ultra [579] 2\d{2}v", cpu_key):
            if re.search(r"core ultra 5 2(?:26|28)v", cpu_key):
                return "intel arc graphics 130v", "alias_cpu_tier", "medium"
            return "intel arc graphics 140v", "alias_cpu_tier", "medium"
        if re.search(r"core ultra [579] 2\d{2}h", cpu_key):
            if re.search(r"core ultra 5 2(?:25|35)h", cpu_key):
                return "intel arc graphics 130t", "alias_cpu_tier", "medium"
            return "intel arc graphics 140t", "alias_cpu_tier", "medium"
        return None, None, "generic_integrated_no_match"

    if key in {"qualcomm adreno", "adreno", "adreno gpu"}:
        if "snapdragon x" in cpu_key:
            return "sd x adreno x1-85 3.8 tflops", "alias_family", "low"
        return None, None, "generic_integrated_no_match"

    if key in {"amd radeon graphics", "radeon graphics", "amd radeon", "radeon"}:
        if "ryzen" in cpu_key or "athlon" in cpu_key:
            if re.search(r"hx\s*37[0-9]|ai\s*9\s*hx", cpu_key):
                return "radeon 890m", "alias_ryzen_ai", "high"
            if re.search(r"365\b|ai\s*9\s*3", cpu_key):
                return "radeon 880m", "alias_ryzen_ai", "high"
            if re.search(r"ryzen\s*[79]\s*7\d35", cpu_key):
                return "radeon 680m", "alias_ryzen_gen", "high"
            if re.search(r"ryzen\s*5\s*7\d35", cpu_key):
                return "radeon 660m", "alias_ryzen_gen", "medium"
            if re.search(r"ryzen\s*[79]\s*[78]\d{3}", cpu_key):
                return "radeon 780m", "alias_ryzen_gen", "high"
            if re.search(r"ryzen\s*5\s*[78]\d{3}", cpu_key):
                if re.search(r"ryzen\s*5\s*7520", cpu_key):
                    return "radeon 610m", "alias_ryzen_gen", "medium"
                if re.search(r"ryzen\s*5\s*7530", cpu_key):
                    return "radeon rx vega 7", "alias_ryzen_gen", "medium"
                return "radeon 760m", "alias_ryzen_gen", "medium"
            if re.search(r"ryzen\s*[79]\s*6\d{3}", cpu_key):
                return "radeon 680m", "alias_ryzen_gen", "high"
            if re.search(r"ryzen\s*5\s*6\d{3}", cpu_key):
                return "radeon 660m", "alias_ryzen_gen", "medium"
            if re.search(r"ryzen\s*7\s*(?:5\d{3}|7730)", cpu_key):
                return "radeon rx vega 8 (ryzen 4000/5000)", "alias_ryzen_gen", "medium"
            if re.search(r"ryzen\s*5\s*5\d{3}", cpu_key):
                return "radeon rx vega 7", "alias_ryzen_gen", "medium"
            if re.search(r"ryzen\s*3\s*(?:4|5|7)\d{3}", cpu_key):
                return "radeon rx vega 6 (ryzen 4000/5000)", "alias_ryzen_gen", "medium"
            return "radeon rx vega 7", "alias_ryzen_default", "low"
        return None, None, "generic_integrated_no_match"

    return None, None, "not_in_benchmark"


def match_gpu(
    cpu_model: Any,
    gpu_model: Any,
    gpu_index: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    cpu_key = cpu_match_key(str(cpu_model or ""))
    if cpu_key.startswith("apple "):
        return None, "apple_gpu_skipped"

    key = gpu_match_key(str(gpu_model or ""))
    if not key or key in {"unknown", "discrete"}:
        return None, "generic_or_missing"

    if key in gpu_index:
        return _result(gpu_index[key], "exact", "high"), None

    # Fallback: strip VRAM suffix like "6gb", "8gb", "12gb", "16gb"
    vram_stripped = re.sub(r"\s+\d+\s*gb$", "", key)
    if vram_stripped != key and vram_stripped in gpu_index:
        return _result(gpu_index[vram_stripped], "alias_vram_stripped", "high", f"{key} -> {vram_stripped}"), None

    if key in GPU_ARC_KEYS:
        target = GPU_ARC_KEYS[key]
        if target in gpu_index:
            return _result(gpu_index[target], "alias_arc", "high"), None

    if key == "rtx 3050":
        for target in ("rtx 3050 6gb", "rtx 3050 4gb"):
            if target in gpu_index:
                return _result(gpu_index[target], "alias_vram_default", "medium", "ưu tiên bản 6GB"), None

    if key == "mx570a" and "mx570" in gpu_index:
        return _result(gpu_index["mx570"], "alias_variant", "low", "MX570A -> MX570"), None

    target_key, method, confidence = _choose_integrated_gpu(key, cpu_key)
    if target_key and target_key in gpu_index:
        return _result(gpu_index[target_key], method or "alias", confidence), None

    if method == "generic_integrated_no_match":
        return None, method

    if re.search(r"\d", key) or "max" in key:
        prefix_matches = [candidate for candidate in gpu_index if candidate.startswith(key + " ")]
        if len(prefix_matches) == 1:
            return _result(gpu_index[prefix_matches[0]], "unique_prefix", "medium"), None

    return None, "not_in_benchmark"


def match_laptops(
    input_path: Path = DEFAULT_INPUT,
    output_csv: Path = DEFAULT_OUTPUT_CSV,
    output_jsonl: Path = DEFAULT_OUTPUT_JSONL,
    report_csv: Path = DEFAULT_REPORT_CSV,
    cpu_csv: Path = CPU_CSV,
    gpu_csv: Path = GPU_CSV,
) -> Path:
    if not cpu_csv.exists() or not gpu_csv.exists():
        raise FileNotFoundError(
            f"Missing benchmark CSVs. Run `python -m src.market_graph.benchmark_extract` first "
            f"(expected {cpu_csv} and {gpu_csv})."
        )

    products = _load_products(input_path)
    laptops = [row for row in products if clean_text(str(row.get("category_clean") or "")) == "laptop"]
    if not laptops:
        print(f"[Match] Warning: No laptop rows found in {input_path}. Creating empty benchmark outputs.")
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(columns=["listing_record_id", "cpu_bench_model", "cpu_perf_rating", "gpu_bench_model", "gpu_perf_rating"]).to_csv(output_csv, index=False, encoding="utf-8-sig")
        output_jsonl.write_text("", encoding="utf-8")
        pd.DataFrame(columns=["field", "value", "count", "reason"]).to_csv(report_csv, index=False, encoding="utf-8-sig")
        return output_csv

    cpu_index = _load_benchmark_index(cpu_csv)
    gpu_index = _load_benchmark_index(gpu_csv)
    apple_variants = _build_apple_variants(cpu_index)

    enriched: list[dict[str, Any]] = []
    cpu_methods: Counter[str] = Counter()
    gpu_methods: Counter[str] = Counter()
    cpu_unmatched: Counter[str] = Counter()
    gpu_unmatched: Counter[str] = Counter()
    cpu_reasons: dict[str, str] = {}
    gpu_reasons: dict[str, str] = {}

    for row in laptops:
        cpu_model = row.get("cpu_model")
        gpu_model = row.get("gpu_model")

        cpu_match, cpu_reason = match_cpu(cpu_model, gpu_model, cpu_index, apple_variants)
        gpu_match, gpu_reason = match_gpu(cpu_model, gpu_model, gpu_index)

        out = dict(row)
        if cpu_match:
            out.update(
                {
                    "cpu_bench_model": cpu_match["bench_model"],
                    "cpu_perf_rating": cpu_match["perf_rating"],
                    "cpu_perf_rating_is_approx": cpu_match["perf_rating_is_approx"],
                    "cpu_perf_rating_coverage_pct": cpu_match["perf_rating_coverage_pct"],
                    "cpu_match_method": cpu_match["match_method"],
                    "cpu_match_confidence": cpu_match["match_confidence"],
                    "cpu_match_note": cpu_match["match_note"],
                }
            )
            cpu_methods[cpu_match["match_method"]] += 1
        else:
            out.update(
                {
                    "cpu_bench_model": None,
                    "cpu_perf_rating": None,
                    "cpu_perf_rating_is_approx": None,
                    "cpu_perf_rating_coverage_pct": None,
                    "cpu_match_method": "unmatched",
                    "cpu_match_confidence": "none",
                    "cpu_match_note": cpu_reason,
                }
            )
            cpu_unmatched[str(cpu_model)] += 1
            cpu_reasons.setdefault(str(cpu_model), cpu_reason or "unknown")

        if gpu_match:
            out.update(
                {
                    "gpu_bench_model": gpu_match["bench_model"],
                    "gpu_perf_rating": gpu_match["perf_rating"],
                    "gpu_perf_rating_is_approx": gpu_match["perf_rating_is_approx"],
                    "gpu_perf_rating_coverage_pct": gpu_match["perf_rating_coverage_pct"],
                    "gpu_match_method": gpu_match["match_method"],
                    "gpu_match_confidence": gpu_match["match_confidence"],
                    "gpu_match_note": gpu_match["match_note"],
                }
            )
            gpu_methods[gpu_match["match_method"]] += 1
        else:
            out.update(
                {
                    "gpu_bench_model": None,
                    "gpu_perf_rating": None,
                    "gpu_perf_rating_is_approx": None,
                    "gpu_perf_rating_coverage_pct": None,
                    "gpu_match_method": "skipped" if gpu_reason == "apple_gpu_skipped" else "unmatched",
                    "gpu_match_confidence": "none",
                    "gpu_match_note": gpu_reason,
                }
            )
            if gpu_reason == "apple_gpu_skipped":
                gpu_methods[f"skipped:{gpu_reason}"] += 1
            else:
                gpu_unmatched[str(gpu_model)] += 1
                gpu_reasons.setdefault(str(gpu_model), gpu_reason or "unknown")
                gpu_methods[f"unmatched:{gpu_reason}"] += 1

        enriched.append(out)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(enriched).to_csv(output_csv, index=False, encoding="utf-8-sig")
    with output_jsonl.open("w", encoding="utf-8") as handle:
        for row in enriched:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_rows = [
        {"field": "cpu", "value": value, "count": count, "reason": cpu_reasons.get(value, "unknown")}
        for value, count in cpu_unmatched.most_common()
    ] + [
        {"field": "gpu", "value": value, "count": count, "reason": gpu_reasons.get(value, "unknown")}
        for value, count in gpu_unmatched.most_common()
    ]
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows, columns=["field", "value", "count", "reason"]).to_csv(
        report_csv, index=False, encoding="utf-8-sig"
    )

    cpu_rated = sum(1 for row in enriched if row.get("cpu_perf_rating") is not None)
    gpu_rated = sum(1 for row in enriched if row.get("gpu_perf_rating") is not None)
    print(
        f"[Match] Laptop: {len(enriched)} dòng | CPU perf_rating: {cpu_rated} "
        f"({cpu_rated / len(enriched):.1%}) | GPU perf_rating: {gpu_rated} "
        f"({gpu_rated / len(enriched):.1%})"
    )
    print(f"[Match] CPU methods: {dict(cpu_methods)}")
    print(f"[Match] GPU methods: {dict(gpu_methods)}")
    print(f"[Match] Outputs: {output_csv} & {output_jsonl}; report: {report_csv}")
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.market_graph.laptop_benchmark_match",
        description="Enrich laptop listings with Notebookcheck CPU/GPU perf_rating.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument("--output-jsonl", type=Path, default=DEFAULT_OUTPUT_JSONL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_CSV)
    parser.add_argument("--cpu-benchmarks", type=Path, default=CPU_CSV)
    parser.add_argument("--gpu-benchmarks", type=Path, default=GPU_CSV)
    args = parser.parse_args()

    match_laptops(
        input_path=args.input,
        output_csv=args.output_csv,
        output_jsonl=args.output_jsonl,
        report_csv=args.report,
        cpu_csv=args.cpu_benchmarks,
        gpu_csv=args.gpu_benchmarks,
    )


if __name__ == "__main__":
    main()
