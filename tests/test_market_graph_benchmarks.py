"""Tests for Notebookcheck benchmark extraction and laptop matching."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.market_graph.benchmark_extract import (
    CPU_CSV,
    GPU_CSV,
    PHONE_CPU_CSV,
    cpu_match_key,
    gpu_match_key,
    parse_cpu_benchmarks,
    parse_gpu_benchmarks,
    parse_perf_rating,
    parse_phone_cpu_benchmarks,
    parse_score,
    phone_cpu_match_key,
    phone_cpu_match_keys,
)
from src.market_graph.laptop_benchmark_match import (
    _build_apple_variants,
    _load_benchmark_index,
    match_cpu,
    match_gpu,
    match_laptops,
)
from src.market_graph.smartphone_benchmark_match import (
    _load_phone_index,
    match_phone_cpu,
    match_smartphones,
)

BENCHMARKS_AVAILABLE = CPU_CSV.exists() and GPU_CSV.exists()
PHONE_BENCHMARKS_AVAILABLE = PHONE_CPU_CSV.exists()
requires_benchmarks = pytest.mark.skipif(
    not BENCHMARKS_AVAILABLE,
    reason="Run `python -m src.market_graph.benchmark_extract` first.",
)
requires_phone_benchmarks = pytest.mark.skipif(
    not PHONE_BENCHMARKS_AVAILABLE,
    reason="Run `python -m src.market_graph.benchmark_extract` first.",
)


def test_parse_perf_rating() -> None:
    assert parse_perf_rating("39.5") == (39.5, False, None)
    assert parse_perf_rating("~39.5 94%") == (39.5, True, 94.0)
    assert parse_perf_rating("–") == (None, False, None)
    assert parse_perf_rating("") == (None, False, None)


def test_parse_score() -> None:
    assert parse_score("3430.5 n2") == (3430.5, 2, False)
    assert parse_score("148173 n11") == (148173.0, 11, False)
    assert parse_score("–") == (None, None, False)


def test_match_key_normalization() -> None:
    assert cpu_match_key("Intel Core i5-13420H") == "core i5-13420h"
    assert cpu_match_key("Core 7-150U") == "core 7 150u"
    assert cpu_match_key("AMD Ryzen 9 8940HX") == "ryzen 9 8940hx"
    assert gpu_match_key("NVIDIA GeForce RTX 4050 Laptop GPU") == "rtx 4050"
    assert gpu_match_key("Intel Iris Xe Graphics") == "intel iris xe graphics"


@requires_benchmarks
def test_parse_benchmark_row_counts() -> None:
    cpu_df = parse_cpu_benchmarks()
    gpu_df = parse_gpu_benchmarks()
    assert len(cpu_df) == 1267
    assert len(gpu_df) == 251
    assert cpu_df["perf_rating"].notna().sum() == 999
    assert gpu_df["perf_rating"].notna().sum() == 186
    assert cpu_df["match_key"].is_unique
    assert gpu_df["match_key"].is_unique


@requires_benchmarks
def test_apple_cpu_and_gpu_matching() -> None:
    cpu_index = _load_benchmark_index(CPU_CSV)
    gpu_index = _load_benchmark_index(GPU_CSV)
    apple_variants = _build_apple_variants(cpu_index)

    cpu_match, reason = match_cpu("Apple M4 Max", "Apple 32-core GPU", cpu_index, apple_variants)
    assert reason is None
    assert cpu_match is not None
    assert cpu_match["bench_model"] == "Apple M4 Max 14-Core"
    assert cpu_match["match_method"] == "apple_gpu_core"

    cpu_match, reason = match_cpu("Apple M5", "Apple 10-core GPU", cpu_index, apple_variants)
    assert reason is None
    assert cpu_match is not None
    assert cpu_match["bench_model"] == "Apple M5 10-Core"

    gpu_match, reason = match_gpu("Apple M5", "Apple 10-core GPU", gpu_index)
    assert gpu_match is None
    assert reason == "apple_gpu_skipped"


@requires_benchmarks
def test_gpu_alias_matching() -> None:
    gpu_index = _load_benchmark_index(GPU_CSV)

    exact, reason = match_gpu("Core i5-13420H", "RTX 4050", gpu_index)
    assert reason is None
    assert exact is not None
    assert exact["bench_model"] == "NVIDIA GeForce RTX 4050 Laptop GPU"
    assert exact["perf_rating"] == 26.2

    alias, reason = match_gpu("Core i5-11400H", "RTX 3050", gpu_index)
    assert reason is None
    assert alias is not None
    assert alias["bench_model"] == "NVIDIA GeForce RTX 3050 6GB Laptop GPU"
    assert alias["match_confidence"] == "medium"

    i5, _ = match_gpu("Core i5-1135G7", "Intel Iris Xe", gpu_index)
    i7, _ = match_gpu("Core i7-1165G7", "Intel Iris Xe", gpu_index)
    assert i5 is not None and i5["bench_model"] == "Intel Iris Xe Graphics G7 80EUs"
    assert i7 is not None and i7["bench_model"] == "Intel Iris Xe Graphics G7 96EUs"


@requires_benchmarks
def test_match_laptops_output(tmp_path: Path) -> None:
    input_path = tmp_path / "products.jsonl"
    rows = [
        {
            "listing_record_id": "l1",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "TUF A15",
            "cpu_model": "Core i5-13420H",
            "gpu_model": "RTX 4050",
        },
        {
            "listing_record_id": "l2",
            "category_clean": "laptop",
            "brand": "Apple",
            "model_clean": "MacBook Pro 14 M4 Max",
            "cpu_model": "Apple M4 Max",
            "gpu_model": "Apple 32-core GPU",
        },
        {
            "listing_record_id": "s1",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "cpu_model": "Exynos 1480",
            "gpu_model": None,
        },
    ]
    input_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    output_csv = tmp_path / "laptop_benchmarks.csv"
    output_jsonl = tmp_path / "laptop_benchmarks.jsonl"
    report_csv = tmp_path / "match_report.csv"
    match_laptops(
        input_path=input_path,
        output_csv=output_csv,
        output_jsonl=output_jsonl,
        report_csv=report_csv,
    )

    df = pd.read_csv(output_csv, encoding="utf-8-sig")
    assert len(df) == 2
    assert set(df["listing_record_id"]) == {"l1", "l2"}
    assert df.loc[df["listing_record_id"] == "l1", "cpu_perf_rating"].iloc[0] == 39.7
    assert df.loc[df["listing_record_id"] == "l1", "gpu_perf_rating"].iloc[0] == 26.2
    assert pd.isna(df.loc[df["listing_record_id"] == "l2", "gpu_perf_rating"].iloc[0])
    assert output_jsonl.exists() and report_csv.exists()


def test_phone_cpu_match_keys() -> None:
    assert phone_cpu_match_key("MediaTek Helio G85") == "helio g85"
    assert phone_cpu_match_key("Qualcomm Snapdragon 680 4G") == "snapdragon 680"
    assert phone_cpu_match_key("Snapdragon 8 Plus Gen 1") == "snapdragon 8+ gen 1"
    assert phone_cpu_match_key("MediaTek Dimensity 8300-Ultra") == "dimensity 8300 ultra"

    main, aliases = phone_cpu_match_keys("Unisoc T7200 (T606)")
    assert main == "t7200"
    assert aliases == ["t606"]

    main, aliases = phone_cpu_match_keys("MTK G36")
    assert main == "mtk g36"
    assert "helio g36" in aliases


@requires_phone_benchmarks
def test_parse_phone_benchmarks() -> None:
    phone_df = parse_phone_cpu_benchmarks()
    assert len(phone_df) == 549
    assert phone_df["benchmark_score"].notna().sum() == 325
    # The saved phone snapshot does not enable the Perf. Rating column.
    assert phone_df["perf_rating"].isna().all()
    assert set(phone_df["benchmark_metric"].dropna().unique()) == {
        "geekbench_5_multi_core",
        "geekbench_4_converted_gb5",
    }


@requires_phone_benchmarks
def test_phone_cpu_matching() -> None:
    main_index, alias_index = _load_phone_index(PHONE_CPU_CSV)

    match, reason = match_phone_cpu("Snapdragon 8 Gen 3", main_index, alias_index)
    assert reason is None
    assert match is not None
    assert match["bench_model"] == "Qualcomm Snapdragon 8 Gen 3"
    assert match["match_method"] == "exact"

    match, reason = match_phone_cpu("Apple A15", main_index, alias_index)
    assert reason is None
    assert match is not None
    assert match["bench_model"] == "Apple A15 Bionic"
    assert match["match_method"] == "unique_prefix"

    match, reason = match_phone_cpu("Unisoc T606", main_index, alias_index)
    assert reason is None
    assert match is not None
    assert match["bench_model"] == "Unisoc T7200 (T606)"
    assert match["match_method"] == "parenthetical_alias"

    match, reason = match_phone_cpu("Helio G99 Ultimate", main_index, alias_index)
    assert reason is None
    assert match is not None
    assert match["bench_model"] == "Mediatek Helio G99"
    assert match["match_method"] == "variant_base"

    match, reason = match_phone_cpu("MTK G36", main_index, alias_index)
    assert reason is None
    assert match is not None
    assert match["bench_model"] == "Mediatek Helio G36"
    assert match["match_method"] == "product_alias"


@requires_phone_benchmarks
def test_match_smartphones_output(tmp_path: Path) -> None:
    input_path = tmp_path / "products.jsonl"
    rows = [
        {
            "listing_record_id": "s1",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy S24",
            "cpu_model": "Exynos 1480",
        },
        {
            "listing_record_id": "s2",
            "category_clean": "smartphone",
            "brand": "Xiaomi",
            "model_clean": "Redmi Note",
            "cpu_model": "Unknown",
        },
        {
            "listing_record_id": "l1",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "TUF A15",
            "cpu_model": "Core i5-13420H",
        },
    ]
    input_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    output_csv = tmp_path / "smartphone_benchmarks.csv"
    output_jsonl = tmp_path / "smartphone_benchmarks.jsonl"
    report_csv = tmp_path / "smartphone_match_report.csv"
    match_smartphones(
        input_path=input_path,
        output_csv=output_csv,
        output_jsonl=output_jsonl,
        report_csv=report_csv,
    )

    df = pd.read_csv(output_csv, encoding="utf-8-sig")
    assert len(df) == 2
    assert set(df["listing_record_id"]) == {"s1", "s2"}
    assert df.loc[df["listing_record_id"] == "s1", "cpu_benchmark_score"].iloc[0] == 3349.0
    assert pd.isna(df.loc[df["listing_record_id"] == "s2", "cpu_benchmark_score"].iloc[0])
    assert output_jsonl.exists() and report_csv.exists()


@requires_benchmarks
def test_vram_suffix_gpu_matching() -> None:
    gpu_index = _load_benchmark_index(GPU_CSV)
    # RTX 4050 6GB -> should match RTX 4050 Laptop GPU
    match_4050, reason_4050 = match_gpu(None, "RTX 4050 6GB", gpu_index=gpu_index)
    assert reason_4050 is None
    assert match_4050 is not None
    assert "4050" in match_4050["bench_model"]

    # RTX 4060 8GB -> should match RTX 4060 Laptop GPU
    match_4060, reason_4060 = match_gpu(None, "RTX 4060 8GB", gpu_index=gpu_index)
    assert reason_4060 is None
    assert match_4060 is not None
    assert "4060" in match_4060["bench_model"]


@requires_benchmarks
def test_amd_integrated_gpu_matching_by_cpu() -> None:
    gpu_index = _load_benchmark_index(GPU_CSV)

    # Ryzen 7 7840HS + AMD Radeon Graphics -> Radeon 780M (Zen 4 / RDNA3)
    match_780m, reason_780m = match_gpu("Ryzen 7 7840HS", "AMD Radeon Graphics", gpu_index=gpu_index)
    assert reason_780m is None
    assert match_780m is not None
    assert "780M" in match_780m["bench_model"]

    # Ryzen 7 7735HS + AMD Radeon Graphics -> Radeon 680M (Rembrandt-R / RDNA2)
    match_680m, reason_680m = match_gpu("AMD Ryzen 7 7735HS", "AMD Radeon Graphics", gpu_index=gpu_index)
    assert reason_680m is None
    assert match_680m is not None
    assert "680M" in match_680m["bench_model"]

    # Ryzen 5 7535HS + Radeon Graphics -> Radeon 660M (Rembrandt-R / RDNA2)
    match_660m, reason_660m = match_gpu("Ryzen 5 7535HS", "Radeon Graphics", gpu_index=gpu_index)
    assert reason_660m is None
    assert match_660m is not None
    assert "660M" in match_660m["bench_model"]

    # Ryzen 5 5500U + Radeon Graphics -> Radeon RX Vega 7 (Zen 2/3 / Vega)
    match_vega, reason_vega = match_gpu("AMD Ryzen 5 5500U", "Radeon Graphics", gpu_index=gpu_index)
    assert reason_vega is None
    assert match_vega is not None
    assert "Vega 7" in match_vega["bench_model"]


@requires_benchmarks
def test_intel_core_ultra_u_series_integrated_gpu() -> None:
    gpu_index = _load_benchmark_index(GPU_CSV)

    # Core Ultra 5 125U + Intel Graphics
    m_125u, r_125u = match_gpu("Intel Core Ultra 5 125U", "Intel Graphics", gpu_index=gpu_index)
    assert r_125u is None
    assert m_125u is not None
    assert "4-Core" in m_125u["bench_model"] or "Meteor" in m_125u["bench_model"]

    # Core Ultra 7 155U + Intel Graphics
    m_155u, r_155u = match_gpu("Core Ultra 7 155U", "Intel Graphics", gpu_index=gpu_index)
    assert r_155u is None
    assert m_155u is not None
    assert "4-Core" in m_155u["bench_model"] or "Meteor" in m_155u["bench_model"]


def test_cpu_match_key_hyphen_normalization() -> None:
    # Intel Core Ultra (standardizes to space matching Notebookcheck)
    assert cpu_match_key("Intel Core Ultra 7 155H") == "core ultra 7 155h"
    assert cpu_match_key("Core Ultra 7-155H") == "core ultra 7 155h"

    # Intel Core non-i (Core 5 120U)
    assert cpu_match_key("Intel Core 5 120U") == "core 5 120u"
    assert cpu_match_key("Core 5-120U") == "core 5 120u"

    # Intel Core i-series (standardizes to hyphen matching Notebookcheck)
    assert cpu_match_key("Core i5 13420H") == "core i5-13420h"
    assert cpu_match_key("Core i5-13420H") == "core i5-13420h"

    # AMD Ryzen
    assert cpu_match_key("AMD Ryzen 7 7840HS") == "ryzen 7 7840hs"
    assert cpu_match_key("Ryzen 7-7840HS") == "ryzen 7 7840hs"

