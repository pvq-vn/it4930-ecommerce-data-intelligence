"""Tests for benchmark-based Step 3 product similarity graph."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.market_graph.louvain_segments import build_product_similarity_graph
from src.market_graph.perf_scores import (
    enrich_perf_scores,
    is_discrete_gpu,
    perf_close,
    relative_perf_diff,
)


def _laptop(
    product_id: str,
    brand: str,
    cpu_score: float | None,
    gpu_score: float | None,
    gpu_model: str,
    price: float = 20_000_000.0,
    ram: int = 16,
) -> dict:
    return {
        "canonical_product_id": product_id,
        "category": "laptop",
        "brand": brand,
        "model_clean": f"Model {product_id}",
        "cpu_model": "Core i5-13420H",
        "cpu_tier": "tier_mid_5",
        "ram_gb": ram,
        "price_median": price,
        "cpu_perf_score": cpu_score,
        "cpu_perf_norm": (cpu_score / 100.0) if cpu_score is not None else None,
        "gpu_perf_score": gpu_score,
        "gpu_perf_norm": (gpu_score / 100.0) if gpu_score is not None else None,
        "cpu_score_source": "listing_median",
        "gpu_score_source": "listing_median",
        "gpu_type": gpu_model,
    }


def test_relative_perf_diff_and_close() -> None:
    assert relative_perf_diff(100, 85) == 0.15
    assert perf_close(100, 85, tol=0.15)
    assert not perf_close(100, 84, tol=0.15)
    assert relative_perf_diff(None, 10) is None


def test_gpu_type_classification() -> None:
    assert is_discrete_gpu("RTX 4050") == "discrete"
    assert is_discrete_gpu("GTX 1650 Ti") == "discrete"
    assert is_discrete_gpu("Intel Iris Xe") == "integrated"
    assert is_discrete_gpu("Intel Iris Xe Graphics") == "integrated"
    assert is_discrete_gpu("Intel Iris Xe MAX") == "discrete"
    assert is_discrete_gpu("Iris Xe Max") == "discrete"
    assert is_discrete_gpu("Intel Arc 140V") == "integrated"
    assert is_discrete_gpu("Intel Arc 130V") == "integrated"
    assert is_discrete_gpu("Arc 140V") == "integrated"
    assert is_discrete_gpu("Arc 140T") == "integrated"
    assert is_discrete_gpu("Intel Arc A370M") == "discrete"
    assert is_discrete_gpu("Intel Arc B580") == "discrete"
    assert is_discrete_gpu("AMD Radeon Graphics") == "integrated"
    assert is_discrete_gpu("AMD Radeon RX Vega 7") == "integrated"
    assert is_discrete_gpu("Radeon RX Vega 8") == "integrated"
    assert is_discrete_gpu("NVIDIA GeForce MX570A") == "discrete"
    assert is_discrete_gpu("GeForce MX550") == "discrete"
    assert is_discrete_gpu(None) == "unknown"


def test_cross_brand_perf_edge() -> None:
    rows = [
        _laptop("a", "ASUS", 50.0, 30.0, "discrete"),
        _laptop("b", "Lenovo", 52.0, 31.0, "discrete"),
        _laptop("c", "HP", 70.0, 30.0, "discrete"),
    ]
    G = build_product_similarity_graph(pd.DataFrame(rows), price_tol=0.20, perf_tol=0.15)
    assert G.has_edge("a", "b")
    assert not G.has_edge("a", "c")
    assert G["a"]["b"]["perf_match"] == "benchmark"


def test_discrete_integrated_gpu_blocked() -> None:
    rows = [
        _laptop("a", "ASUS", 50.0, 30.0, "discrete"),
        _laptop("b", "Lenovo", 50.0, 30.5, "integrated"),
        _laptop("c", "Acer", 50.0, None, "unknown"),
    ]
    G = build_product_similarity_graph(pd.DataFrame(rows), perf_tol=0.15)
    assert not G.has_edge("a", "b"), "Discrete and Integrated must not connect"
    assert not G.has_edge("a", "c"), "Discrete and Unknown GPU must not connect"


def test_price_and_perf_thresholds() -> None:
    rows = [
        _laptop("a", "ASUS", 50.0, 30.0, "discrete", price=10_000_000.0),
        _laptop("b", "Lenovo", 52.0, 30.0, "discrete", price=13_000_000.0),
        _laptop("c", "HP", 70.0, 30.0, "discrete", price=10_000_000.0),
    ]
    G = build_product_similarity_graph(pd.DataFrame(rows), price_tol=0.20, perf_tol=0.15)
    assert not G.has_edge("a", "b")
    assert not G.has_edge("a", "c")


def test_enrich_perf_scores_imputes_tier_median(tmp_path: Path) -> None:
    listings = [
        {"listing_record_id": "l1", "canonical_product_id": "p1"},
        {"listing_record_id": "l2", "canonical_product_id": "p2"},
        {"listing_record_id": "l3", "canonical_product_id": "p3"},
        {"listing_record_id": "l4", "canonical_product_id": "p4"},
    ]
    benchmarks = [
        {"listing_record_id": "l1", "cpu_perf_rating": 10.0, "gpu_perf_rating": 5.0},
        {"listing_record_id": "l2", "cpu_perf_rating": 20.0, "gpu_perf_rating": 5.0},
        {"listing_record_id": "l3", "cpu_perf_rating": 30.0, "gpu_perf_rating": 5.0},
    ]
    (tmp_path / "canonical_listings.jsonl").write_text(
        "\n".join(json.dumps(row) for row in listings), encoding="utf-8"
    )
    (tmp_path / "laptop_benchmarks.jsonl").write_text(
        "\n".join(json.dumps(row) for row in benchmarks), encoding="utf-8"
    )

    products = pd.DataFrame(
        [
            {
                "canonical_product_id": f"p{i}",
                "category": "laptop",
                "brand": "ASUS",
                "model_clean": f"M{i}",
                "cpu_model": "Core i5-13420H",
                "cpu_tier": "tier_mid_5",
                "gpu_model": "RTX 4050",
                "ram_gb": 16,
                "price_median": 20_000_000.0,
            }
            for i in range(1, 5)
        ]
    )
    enriched = enrich_perf_scores(products, work_dir=tmp_path)
    p4 = enriched.loc[enriched["canonical_product_id"] == "p4"].iloc[0]
    assert p4["cpu_perf_score"] == 20.0
    assert p4["cpu_score_source"] == "tier_median"
    assert enriched["cpu_perf_norm"].between(0.0, 1.0).all()


def test_scores_from_products_metric_propagation(tmp_path: Path) -> None:
    from src.market_graph.perf_scores import _scores_from_products

    # Create dummy benchmark directory without jsonl listings
    bench_dir = tmp_path / "benchmarks"
    bench_dir.mkdir(parents=True)
    (bench_dir / "cpu_benchmarks.csv").write_text("model,perf_rating\nCore i5-13420H,35.0\n", encoding="utf-8")
    (bench_dir / "gpu_benchmarks.csv").write_text("model,perf_rating\nRTX 4050,45.0\n", encoding="utf-8")
    (bench_dir / "cpu_phone_benchmarks.csv").write_text(
        "model,match_key,benchmark_score,benchmark_metric,match_alias_keys\nMediaTek Helio G85,helio g85,1250.0,geekbench_4_converted_gb5,\n",
        encoding="utf-8",
    )

    df = pd.DataFrame(
        [
            {
                "canonical_product_id": "phone1",
                "category": "smartphone",
                "cpu_model": "Helio G85",
            }
        ]
    )
    scores = _scores_from_products(df, work_dir=tmp_path)
    assert not scores.empty
    assert "listing_cpu_metric" in scores.columns
    assert scores.iloc[0]["listing_cpu_metric"] == "geekbench_4_converted_gb5"

    enriched = enrich_perf_scores(df, work_dir=tmp_path)
    assert enriched.iloc[0]["cpu_perf_metric"] == "geekbench_4_converted_gb5"
