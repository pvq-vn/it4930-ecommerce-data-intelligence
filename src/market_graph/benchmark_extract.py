"""Extract Notebookcheck CPU/GPU benchmark tables from local HTML into CSVs.

The local pages are saved snapshots of:
  - Mobile Processors - Benchmark List
  - Mobile Graphics Cards - Benchmark List

Outputs:
  - data/market_graph/benchmarks/cpu_benchmarks.csv
  - data/market_graph/benchmarks/gpu_benchmarks.csv

Each output keeps the hardware specs and parses ``Perf. Rating`` into a numeric
column plus approximation/coverage metadata. GPU 3DMark scores are parsed as
well, but ``perf_rating`` remains the primary GPU metric.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = PROJECT_ROOT / "data" / "market_graph" / "benchmarks"
CPU_HTML = BENCHMARK_DIR / "notebookcheck_cpu.html"
GPU_HTML = BENCHMARK_DIR / "notebookcheck_gpu.html"
PHONE_CPU_HTML = BENCHMARK_DIR / "notebookcheck_cpu_phone.html"
CPU_CSV = BENCHMARK_DIR / "cpu_benchmarks.csv"
GPU_CSV = BENCHMARK_DIR / "gpu_benchmarks.csv"
PHONE_CPU_CSV = BENCHMARK_DIR / "cpu_phone_benchmarks.csv"

CPU_TABLE_COLUMNS = [
    "pos_raw",
    "model",
    "codename",
    "l2_l3_cache_raw",
    "slc_cache_raw",
    "tdp_w_raw",
    "tdp_turbo_w_raw",
    "mhz_turbo_raw",
    "cores_threads_raw",
    "perf_rating_raw",
    "cinebench_r15_single_raw",
    "cinebench_r15_multi_raw",
    "cinebench_r23_single_raw",
    "cinebench_r23_multi_raw",
    "x265_raw",
    "blender_v3_3_classroom_cpu_raw",
    "blender_v4_3_barbershop_cpu_raw",
    "7zip_single_raw",
    "7zip_multi_raw",
    "geekbench_5_5_multi_raw",
    "geekbench_6_7_single_raw",
    "geekbench_6_7_multi_raw",
    "geekbench_7_0_single_raw",
    "geekbench_7_0_multi_raw",
    "webxprt_4_overall_raw",
    "crossmark_overall_raw",
]

CPU_SCORE_COLUMNS = [
    "cinebench_r15_single",
    "cinebench_r15_multi",
    "cinebench_r23_single",
    "cinebench_r23_multi",
    "x265",
    "blender_v3_3_classroom_cpu",
    "blender_v4_3_barbershop_cpu",
    "7zip_single",
    "7zip_multi",
    "geekbench_5_5_multi",
    "geekbench_6_7_single",
    "geekbench_6_7_multi",
    "geekbench_7_0_single",
    "geekbench_7_0_multi",
    "webxprt_4_overall",
    "crossmark_overall",
]

GPU_TABLE_COLUMNS = [
    "pos_raw",
    "model",
    "architecture",
    "pixel_shaders_raw",
    "vertex_shaders_raw",
    "core_speed_mhz_raw",
    "memory_speed_raw",
    "memory_bus_raw",
    "memory_type",
    "perf_rating_raw",
    "3dmark_cloud_gate_raw",
    "3dmark11_p_raw",
    "3dmark_fire_strike_raw",
    "3dmark_time_spy_raw",
]

GPU_3DMARK_COLUMNS = [
    "3dmark_cloud_gate",
    "3dmark11_p",
    "3dmark_fire_strike",
    "3dmark_time_spy",
]

PHONE_CPU_TABLE_COLUMNS = [
    "pos_raw",
    "model",
    "codename",
    "mhz_turbo_raw",
    "cores_threads_raw",
    "architecture",
    "is_64bit_raw",
    "geekbench_2_raw",
    "geekbench_3_single_raw",
    "geekbench_3_multi_raw",
    "geekbench_4_single_raw",
    "geekbench_4_multi_raw",
    "geekbench_5_single_raw",
    "geekbench_5_multi_raw",
    "passmark_raw",
    "sunspider_raw",
]

PHONE_CPU_SCORE_COLUMNS = [
    "geekbench_2",
    "geekbench_3_single",
    "geekbench_3_multi",
    "geekbench_4_single",
    "geekbench_4_multi",
    "geekbench_5_single",
    "geekbench_5_multi",
    "passmark",
    "sunspider",
]

PHONE_VENDOR_RE = re.compile(
    r"^(qualcomm|mediatek|samsung|unisoc|hisilicon|huawei|google|spreadtrum|rockchip|nvidia|"
    r"texas instruments|broadcom|allwinner|marvell|xiaomi|nxp)\s+"
)
PHONE_PARENS_RE = re.compile(r"\(([^)]*)\)")

WHITESPACE_RE = re.compile(r"\s+")
DASH_SPLIT_RE = re.compile(r"\s*[‑–—-]\s*")
RATING_RE = re.compile(r"^(~)?\s*([\d.]+)\s*(?:(\d+(?:\.\d+)?)%)?$")
SCORE_RE = re.compile(r"^(~)?\s*([\d.]+)\s*(?:n(\d+))?$")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def clean_text(value: Any) -> str:
    """Normalize NBSP/unicode dashes and collapse whitespace."""
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value).replace("\xa0", " ")
    text = re.sub(r"[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]", "-", text)
    text = text.replace("®", "").replace("™", "")
    return WHITESPACE_RE.sub(" ", text).strip()


def cpu_match_key(model: str) -> str:
    """Normalized key used to join product ``cpu_model`` with benchmark rows."""
    key = clean_text(model).lower()
    key = re.sub(r"^(intel|amd|qualcomm)\s+", "", key)
    key = re.sub(r"\s+(cpu|processor)$", "", key)
    # Core Ultra (including X-series): "core ultra x7-358h" -> "core ultra x7 358h"
    key = re.sub(r"^(core\s+ultra\s+x?[3579])-(\d+[a-z0-9]*)", r"\1 \2", key)
    # Core non-i series: "core 5-120u" -> "core 5 120u"
    key = re.sub(r"^(core\s+[3579])-(\d+[a-z0-9]*)", r"\1 \2", key)
    # Ryzen (including AI HX / PRO): "ryzen ai 9 hx-370" -> "ryzen ai 9 hx 370"
    key = re.sub(r"^(ryzen\s+(?:ai\s+)?[3579](?:\s+hx|\s+pro)?)-(\d+[a-z0-9]*)", r"\1 \2", key)
    # Core i-series: standardize to hyphen, e.g. "core i5 13420h" -> "core i5-13420h"
    key = re.sub(r"^(core\s+i[3579])\s+(\d+[a-z0-9]*)", r"\1-\2", key)
    return WHITESPACE_RE.sub(" ", key).strip()


def gpu_match_key(model: str) -> str:
    """Normalized key used to join product ``gpu_model`` with benchmark rows."""
    key = clean_text(model).lower()
    key = re.sub(r"^(nvidia|amd|qualcomm)\s+", "", key)
    key = re.sub(r"\bgeforce\b", "", key)
    key = re.sub(r"\b(laptop gpu|laptop|mobile|gpu)\b", "", key)
    return WHITESPACE_RE.sub(" ", key).strip()


def phone_cpu_match_key(model: str) -> str:
    """Normalized key for smartphone CPU names across product and Notebookcheck."""
    key = clean_text(model).lower()
    key = PHONE_PARENS_RE.sub(" ", key)
    key = PHONE_VENDOR_RE.sub("", key)
    key = re.sub(r"\bplus\b", "+", key)
    key = re.sub(r"\s*\+\s*", "+ ", key)
    key = re.sub(r"\bgen\s*(\d)\b", r"gen \1", key)
    key = re.sub(r"\b(4g|5g)\b", " ", key)
    key = key.replace("-", " ")
    key = re.sub(r"\s+", " ", key).strip(" ,")
    return key


def phone_cpu_match_keys(model: str) -> tuple[str, list[str]]:
    """Return the main key plus parenthetical/prefix aliases."""
    raw = clean_text(model)
    main_key = phone_cpu_match_key(raw)
    aliases = {
        alias
        for inner in PHONE_PARENS_RE.findall(raw)
        if (alias := phone_cpu_match_key(inner))
    }
    if main_key.startswith("tiger "):
        aliases.add(main_key.removeprefix("tiger ").strip())
    if main_key.startswith("mtk "):
        aliases.add(f"helio {main_key.removeprefix('mtk ').strip()}")
    return main_key, sorted(alias for alias in aliases if alias)


def _split_mhz_range(value: str) -> tuple[float | None, float | None]:
    text = clean_text(value)
    if not text:
        return None, None
    parts = DASH_SPLIT_RE.split(text)
    if len(parts) == 2:
        return _parse_float(parts[0]), _parse_float(parts[1])
    if text.startswith("-"):
        return None, _parse_float(text)
    return _parse_float(text), None


def parse_perf_rating(value: str) -> tuple[float | None, bool, float | None]:
    """Parse ``39.5`` or ``~39.5 94%`` into (rating, is_approx, coverage_pct)."""
    text = clean_text(value)
    if not text or text in {"-", "n/a", "N/A"}:
        return None, False, None
    match = RATING_RE.match(text)
    if not match:
        return None, False, None
    approx, rating, coverage = match.groups()
    return float(rating), bool(approx), float(coverage) if coverage else None


def parse_score(value: str) -> tuple[float | None, int | None, bool]:
    """Parse ``3430.5 n2`` into (score, sample_count, is_approx)."""
    text = clean_text(value)
    if not text or text in {"-", "n/a", "N/A"}:
        return None, None, False
    match = SCORE_RE.match(text)
    if match:
        approx, score, samples = match.groups()
        return float(score), int(samples) if samples else None, bool(approx)
    number = NUMBER_RE.search(text)
    if number:
        return float(number.group(0)), None, False
    return None, None, False


def _parse_float(value: str) -> float | None:
    number = NUMBER_RE.search(clean_text(value))
    return float(number.group(0)) if number else None


def _parse_int(value: str) -> int | None:
    number = NUMBER_RE.search(clean_text(value))
    return int(float(number.group(0))) if number else None


def _parse_pos(value: str) -> tuple[int | None, bool]:
    text = clean_text(value)
    match = re.match(r"^(\d+)\s*(\*)?$", text)
    if not match:
        return None, False
    return int(match.group(1)), bool(match.group(2))


def _split_dash(value: str) -> tuple[float | None, float | None]:
    return _split_mhz_range(value)


def _split_cache(value: str) -> tuple[str | None, str | None]:
    parts = [part.strip() for part in clean_text(value).split("+") if part.strip()]
    if not parts:
        return None, None
    return parts[0], parts[1] if len(parts) > 1 else None


def _split_cores(value: str) -> tuple[int | None, int | None]:
    parts = [part for part in clean_text(value).split("/") if part]
    cores = _parse_int(parts[0]) if parts else None
    threads = _parse_int(parts[1]) if len(parts) > 1 else cores
    return cores, threads


def _load_table_rows(html_path: Path, expected_cells: int) -> list[list[str]]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    table = soup.find("table", class_="sortable")
    if table is None:
        raise ValueError(f"No sortable benchmark table found in {html_path}")

    rows: list[list[str]] = []
    for tr in table.find_all("tr")[1:]:
        cells = [clean_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if len(cells) != expected_cells:
            continue
        if cells[1] in {"", "Model"}:
            continue
        rows.append(cells)
    return rows


def parse_cpu_benchmarks(html_path: Path = CPU_HTML) -> pd.DataFrame:
    raw_rows = _load_table_rows(html_path, expected_cells=len(CPU_TABLE_COLUMNS))
    records: list[dict[str, Any]] = []

    for cells in raw_rows:
        row = dict(zip(CPU_TABLE_COLUMNS, cells))
        pos, pos_note = _parse_pos(row["pos_raw"])
        l2_cache, l3_cache = _split_cache(row["l2_l3_cache_raw"])
        base_mhz, turbo_mhz = _split_dash(row["mhz_turbo_raw"])
        cores, threads = _split_cores(row["cores_threads_raw"])
        rating, is_approx, coverage = parse_perf_rating(row["perf_rating_raw"])

        record: dict[str, Any] = {
            "model": row["model"],
            "codename": row["codename"] or None,
            "pos": pos,
            "pos_note": pos_note,
            "l2_cache": l2_cache,
            "l3_cache": l3_cache,
            "slc_cache": row["slc_cache_raw"] or None,
            "tdp_w": _parse_float(row["tdp_w_raw"]),
            "tdp_turbo_w": _parse_float(row["tdp_turbo_w_raw"]),
            "base_mhz": base_mhz,
            "turbo_mhz": turbo_mhz,
            "cores": cores,
            "threads": threads,
            "perf_rating": rating,
            "perf_rating_is_approx": is_approx,
            "perf_rating_coverage_pct": coverage,
        }
        for column in CPU_SCORE_COLUMNS:
            record[column] = parse_score(row[f"{column}_raw"])[0]
        record["match_key"] = cpu_match_key(row["model"])
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"No CPU benchmark rows parsed from {html_path}")
    return df


def parse_gpu_benchmarks(html_path: Path = GPU_HTML) -> pd.DataFrame:
    raw_rows = _load_table_rows(html_path, expected_cells=len(GPU_TABLE_COLUMNS))
    records: list[dict[str, Any]] = []

    for cells in raw_rows:
        row = dict(zip(GPU_TABLE_COLUMNS, cells))
        pos, pos_note = _parse_pos(row["pos_raw"])
        rating, is_approx, coverage = parse_perf_rating(row["perf_rating_raw"])

        record: dict[str, Any] = {
            "model": row["model"],
            "architecture": row["architecture"] or None,
            "pos": pos,
            "pos_note": pos_note,
            "pixel_shaders": _parse_int(row["pixel_shaders_raw"]),
            "vertex_shaders": _parse_int(row["vertex_shaders_raw"]),
            "core_speed_mhz": _parse_float(row["core_speed_mhz_raw"]),
            # The saved GPU table omits the Boost/Turbo column for every data row.
            "boost_mhz": None,
            "memory_speed": _parse_float(row["memory_speed_raw"]),
            "memory_bus": _parse_int(row["memory_bus_raw"]),
            "memory_type": row["memory_type"] or None,
            "perf_rating": rating,
            "perf_rating_is_approx": is_approx,
            "perf_rating_coverage_pct": coverage,
        }
        for column in GPU_3DMARK_COLUMNS:
            score, samples, _ = parse_score(row[f"{column}_raw"])
            record[column] = score
            record[f"{column}_samples"] = samples
        record["match_key"] = gpu_match_key(row["model"])
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"No GPU benchmark rows parsed from {html_path}")
    return df


def parse_phone_cpu_benchmarks(html_path: Path = PHONE_CPU_HTML) -> pd.DataFrame:
    raw_rows = _load_table_rows(html_path, expected_cells=len(PHONE_CPU_TABLE_COLUMNS))
    records: list[dict[str, Any]] = []

    for cells in raw_rows:
        row = dict(zip(PHONE_CPU_TABLE_COLUMNS, cells))
        pos, pos_note = _parse_pos(row["pos_raw"])
        base_mhz, turbo_mhz = _split_mhz_range(row["mhz_turbo_raw"])
        cores, threads = _split_cores(row["cores_threads_raw"])
        main_key, alias_keys = phone_cpu_match_keys(row["model"])

        record: dict[str, Any] = {
            "model": row["model"],
            "codename": row["codename"] or None,
            "pos": pos,
            "pos_note": pos_note,
            "architecture": row["architecture"] or None,
            "base_mhz": base_mhz,
            "turbo_mhz": turbo_mhz,
            "cores": cores,
            "threads": threads,
            "is_64bit": row["is_64bit_raw"] == "1",
            # The saved phone CPU table does not enable the Perf. Rating column.
            "perf_rating": None,
            "perf_rating_is_approx": False,
            "perf_rating_coverage_pct": None,
            "benchmark_score": None,
            "benchmark_metric": None,
        }
        for column in PHONE_CPU_SCORE_COLUMNS:
            record[column] = parse_score(row[f"{column}_raw"])[0]

        if record["geekbench_5_multi"] is not None:
            record["benchmark_score"] = float(record["geekbench_5_multi"])
            record["benchmark_metric"] = "geekbench_5_multi_core"
        elif record.get("geekbench_4_multi") is not None:
            # Calibrated conversion factor (median GB5/GB4 ratio = 0.2475, corr = 0.966)
            record["benchmark_score"] = round(float(record["geekbench_4_multi"]) * 0.2475, 1)
            record["benchmark_metric"] = "geekbench_4_converted_gb5"
        else:
            record["benchmark_score"] = None
            record["benchmark_metric"] = None

        record["match_key"] = main_key
        record["match_alias_keys"] = ";".join(alias_keys)
        records.append(record)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"No phone CPU benchmark rows parsed from {html_path}")
    return df


def extract_all(
    cpu_html: Path = CPU_HTML,
    gpu_html: Path = GPU_HTML,
    phone_cpu_html: Path = PHONE_CPU_HTML,
    cpu_csv: Path = CPU_CSV,
    gpu_csv: Path = GPU_CSV,
    phone_cpu_csv: Path = PHONE_CPU_CSV,
) -> tuple[Path, Path, Path]:
    cpu_df = parse_cpu_benchmarks(cpu_html)
    gpu_df = parse_gpu_benchmarks(gpu_html)
    phone_cpu_df = parse_phone_cpu_benchmarks(phone_cpu_html)

    cpu_csv.parent.mkdir(parents=True, exist_ok=True)
    cpu_df.to_csv(cpu_csv, index=False, encoding="utf-8-sig")
    gpu_df.to_csv(gpu_csv, index=False, encoding="utf-8-sig")
    phone_cpu_df.to_csv(phone_cpu_csv, index=False, encoding="utf-8-sig")

    print(
        f"[Benchmarks] CPU: {len(cpu_df)} dòng, "
        f"{cpu_df['perf_rating'].notna().sum()} có perf_rating -> {cpu_csv}"
    )
    print(
        f"[Benchmarks] GPU: {len(gpu_df)} dòng, "
        f"{gpu_df['perf_rating'].notna().sum()} có perf_rating -> {gpu_csv}"
    )
    print(
        f"[Benchmarks] Phone CPU: {len(phone_cpu_df)} dòng, "
        f"{phone_cpu_df['benchmark_score'].notna().sum()} có benchmark_score "
        f"({phone_cpu_df['geekbench_5_multi'].notna().sum()} GB5, "
        f"{phone_cpu_df['benchmark_metric'].eq('geekbench_4_converted_gb5').sum()} GB4 converted) -> {phone_cpu_csv}"
    )
    return cpu_csv, gpu_csv, phone_cpu_csv


if __name__ == "__main__":
    extract_all()
