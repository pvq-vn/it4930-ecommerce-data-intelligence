"""Unit and integration tests for src/market_graph (Steps 1-4 without live API calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.market_graph import cli
from src.market_graph.llm_clean import load_valid_price_rows, stratified_sample
from src.market_graph.bipartite_graph import (
    HANDOFF_COLUMNS,
    HANDOFF_FORBIDDEN_TOKENS,
    HANDOFF_LINEAGE_ONLY,
    build_bipartite_graph,
    build_price_free_handoff,
    cluster_by_price_spread,
    compute_base_hash,
    compute_jaccard_matrix,
    compute_retailer_degree_stats,
    export_price_free_handoff,
    filter_min_price,
    min_price_for,
    resolve_canonical_products,
    run_step2,
)
from src.market_graph.louvain_segments import detect_louvain_segments, extract_cpu_tier
from src.market_graph.gaps_and_reports import detect_structural_holes, run_step4


def test_skip_missing_price_and_sample(tmp_path: Path) -> None:
    jsonl = tmp_path / "products.jsonl"
    rows = [
        {
            "listing_record_id": "id1",
            "source": "tgdd",
            "seller_raw": "Thế Giới Di Động",
            "category": "laptop",
            "brand_norm": "HP",
            "price_vnd": 0.0,
            "is_price_missing": True,
            "product_name": "Laptop HP 15",
        },
        {
            "listing_record_id": "id2",
            "source": "tgdd",
            "seller_raw": "Thế Giới Di Động",
            "category": "laptop",
            "brand_norm": "HP",
            "price_vnd": 15_000_000.0,
            "is_price_missing": False,
            "product_name": "Laptop HP 15s (9Q970PA)",
            "cpu_norm": "Intel Core i5-1335U",
        },
        {
            "listing_record_id": "id3",
            "source": "fptshop",
            "seller_raw": "FPT Shop",
            "category": "smartphone",
            "brand_norm": "Apple",
            "price_vnd": 29_000_000.0,
            "is_price_missing": False,
            "product_name": "iPhone 15 Pro Max 256GB",
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    valid, skipped = load_valid_price_rows(jsonl)
    assert skipped == 1
    assert len(valid) == 2

    sampled = stratified_sample(valid, sample_size=2)
    assert len(sampled) == 2


def test_price_spread_clustering() -> None:
    # 15M and 17.5M -> (17.5 - 15)/15 = 16.67% <= 20% -> same cluster
    # 22M -> (22 - 15)/15 = 46.7% > 20% -> split into second cluster
    items = [
        {"price_vnd": 15_000_000.0, "seller_name": "TGDĐ"},
        {"price_vnd": 17_500_000.0, "seller_name": "FPT"},
        {"price_vnd": 22_000_000.0, "seller_name": "CellphoneS"},
    ]
    clusters = cluster_by_price_spread(items, max_spread=0.20)
    assert len(clusters) == 2
    assert len(clusters[0]) == 2
    assert len(clusters[1]) == 1


def test_bipartite_degree_and_jaccard() -> None:
    h1 = compute_base_hash("Apple", "iPhone 15 Pro Max", "Apple A17 Pro")
    h2 = compute_base_hash("apple", "iPhone 15 Pro Max!", "Apple A17 Pro")
    assert h1 == h2

    cleaned_rows = [
        {
            "listing_record_id": "1",
            "seller_name": "TGDĐ",
            "category_clean": "smartphone",
            "brand": "Apple",
            "model_clean": "iPhone 15 Pro Max",
            "cpu_model": "Apple A17 Pro",
            "ram_gb": 8,
            "storage_gb": 256,
            "price_vnd": 29_000_000.0,
            "review_count_normalized": 50,
            "rating_norm": 4.9,
        },
        {
            "listing_record_id": "2",
            "seller_name": "FPT",
            "category_clean": "smartphone",
            "brand": "Apple",
            "model_clean": "iPhone 15 Pro Max",
            "cpu_model": "Apple A17 Pro",
            "ram_gb": 8,
            "storage_gb": 256,
            "price_vnd": 30_000_000.0,
            "review_count_normalized": 20,
            "rating_norm": 4.8,
        },
        {
            "listing_record_id": "3",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "HP",
            "model_clean": "Pavilion 15",
            "cpu_model": "Core i5-1335U",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 16_000_000.0,
            "review_count_normalized": 10,
            "rating_norm": 4.5,
        },
    ]

    enriched, products_df = resolve_canonical_products(cleaned_rows, max_spread=0.20)
    assert len(products_df) == 2

    G = build_bipartite_graph(enriched, products_df)
    stats = compute_retailer_degree_stats(G, products_df)
    tgdd_row = stats[stats["retailer"] == "TGDĐ"].iloc[0]
    assert tgdd_row["exclusive_count"] == 1
    assert tgdd_row["competitive_count"] == 1

    jaccard = compute_jaccard_matrix(G)
    # TGDĐ has {iphone, hp}, FPT has {iphone} -> intersection=1, union=2 -> 0.5
    assert abs(jaccard.loc["TGDĐ", "FPT"] - 0.5) < 1e-6


def test_louvain_and_step4_reports(tmp_path: Path) -> None:
    assert extract_cpu_tier("Intel Core i5-13420H") == "tier_mid_5"
    assert extract_cpu_tier("Snapdragon 8 Gen 3") == "sd_flagship"
    assert extract_cpu_tier("Snapdragon 8s Gen 3") == "sd_flagship"
    assert extract_cpu_tier("Apple A13 Bionic") == "apple_a_older"
    assert extract_cpu_tier("Snapdragon X Plus") == "snapdragon_x"

    # Build synthetic dataset with enough nodes for Louvain & structural holes
    rows = []
    for i in range(6):
        rows.append(
            {
                "listing_record_id": f"l{i}",
                "seller_name": "TGDĐ" if i < 4 else "FPT",
                "category_clean": "laptop",
                "brand": "ASUS",
                "model_clean": f"Vivobook {i}",
                "cpu_model": "Core i5-13500H",
                "ram_gb": 16,
                "storage_gb": 512,
                "price_vnd": 16_000_000.0 + i * 200_000,
                "review_count_normalized": 15,
                "rating_norm": 4.7,
            }
        )
    for i in range(5):
        rows.append(
            {
                "listing_record_id": f"s{i}",
                "seller_name": "CellphoneS",
                "category_clean": "smartphone",
                "brand": "Samsung",
                "model_clean": f"Galaxy S24 {i}",
                "cpu_model": "Exynos 2400",
                "ram_gb": 8,
                "storage_gb": 256,
                "price_vnd": 20_000_000.0 + i * 300_000,
                "review_count_normalized": 30,
                "rating_norm": 4.8,
            }
        )

    input_path = tmp_path / "rows.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    _, products_df, jaccard_by_cat = run_step2(input_path=input_path, work_dir=tmp_path)
    assert set(jaccard_by_cat) == {"laptop", "smartphone"}
    expected_retailers = {"TGDĐ", "FPT", "CellphoneS"}
    assert set(jaccard_by_cat["laptop"].columns) == expected_retailers
    assert set(jaccard_by_cat["smartphone"].columns) == expected_retailers

    df_seg, segments_df, _ = detect_louvain_segments(products_df)
    assert not segments_df.empty

    ct, holes = detect_structural_holes(df_seg, segments_df, min_segment_size=5)
    assert not holes.empty

    df_seg.to_csv(tmp_path / "canonical_products_segmented.csv", index=False)
    segments_df.to_csv(tmp_path / "louvain_segments.csv", index=False)

    laptop_stats = pd.read_csv(tmp_path / "retailer_degree_stats_laptop.csv")
    phone_stats = pd.read_csv(tmp_path / "retailer_degree_stats_smartphone.csv")
    assert laptop_stats.loc[laptop_stats["retailer"] == "CellphoneS", "total_canonical_products"].iloc[0] == 0
    assert phone_stats.loc[phone_stats["retailer"] == "TGDĐ", "total_canonical_products"].iloc[0] == 0

    run_step4(work_dir=tmp_path)
    reports = tmp_path / "reports"
    assert (reports / "jaccard_similarity_heatmap.png").exists()
    assert (reports / "segment_price_heatmap.png").exists()
    assert (reports / "bipartite_market_graph_laptop.html").exists()
    assert (reports / "bipartite_market_graph_smartphone.html").exists()
    assert (reports / "market_gaps_report.md").exists()


def test_nan_ram_and_unknown_cpu_imputation() -> None:
    rows = [
        {
            "listing_record_id": "a1",
            "seller_name": "TGDĐ",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy A35",
            "cpu_model": "Exynos 1380",
            "ram_gb": float("nan"),
            "storage_gb": 128,
            "price_vnd": 6_190_000.0,
            "review_count_normalized": 10,
            "rating_norm": float("nan"),
        },
        {
            "listing_record_id": "a2",
            "seller_name": "Viettel",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy A35",
            "cpu_model": "Unknown",
            "ram_gb": None,
            "storage_gb": None,
            "price_vnd": 6_390_000.0,
            "review_count_normalized": 5,
            "rating_norm": 4.6,
        },
    ]
    _, products_df = resolve_canonical_products(rows)
    assert len(products_df) == 1
    assert products_df.iloc[0]["cpu_model"] == "Exynos 1380"
    assert pd.isna(products_df.iloc[0]["ram_gb"])


def test_entity_resolution_hardware_specs_separation_and_deep_discount() -> None:
    # 1. Same model, different RAM (8GB vs 16GB) within 20% price difference -> MUST be separate entities
    rows_ram_diff = [
        {
            "listing_record_id": "r1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "Vivobook 15",
            "cpu_model": "Core i5-13500H",
            "ram_gb": 8,
            "storage_gb": 512,
            "price_vnd": 16_500_000.0,
        },
        {
            "listing_record_id": "r2",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "Vivobook 15",
            "cpu_model": "Core i5-13500H",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 18_500_000.0,
        },
    ]
    _, df_ram = resolve_canonical_products(rows_ram_diff)
    assert len(df_ram) == 2, "8GB and 16GB models must be separate canonical products"

    # 2. Same model and same RAM/storage with deep discount (>20% spread) -> MUST remain 1 entity
    rows_deep_discount = [
        {
            "listing_record_id": "d1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "Vivobook 15",
            "cpu_model": "Core i5-13500H",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 18_000_000.0,
        },
        {
            "listing_record_id": "d2",
            "seller_name": "CellphoneS",
            "category_clean": "laptop",
            "brand": "ASUS",
            "model_clean": "Vivobook 15",
            "cpu_model": "Core i5-13500H",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 13_500_000.0,  # 25% discount!
        },
    ]
    _, df_disc = resolve_canonical_products(rows_deep_discount, max_spread=0.20)
    assert len(df_disc) == 1, "Deep-discounted identical spec model should NOT be split"

    # 3. Missing both RAM and storage with >20% price gap -> fallback splits by price spread
    rows_no_specs = [
        {
            "listing_record_id": "n1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron 15",
            "cpu_model": "Core i5-1235U",
            "ram_gb": None,
            "storage_gb": None,
            "price_vnd": 12_000_000.0,
        },
        {
            "listing_record_id": "n2",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron 15",
            "cpu_model": "Core i5-1235U",
            "ram_gb": None,
            "storage_gb": None,
            "price_vnd": 17_000_000.0,  # >20% gap
        },
    ]
    _, df_nospec = resolve_canonical_products(rows_no_specs, max_spread=0.20)
    assert len(df_nospec) == 2, "Unknown spec models with >20% price spread must be split"


def test_retailer_price_leadership_and_premium() -> None:
    # 2 retailers competing on 2 products:
    # Product P1: TGDĐ at 10M (wins), FPT at 12M (premium = 20%)
    # Product P2: TGDĐ at 20M (tied), FPT at 20M (tied, both win, premium = 0%)
    cleaned_rows = [
        {
            "listing_record_id": "l1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron A",
            "cpu_model": "Core i5",
            "ram_gb": 8,
            "storage_gb": 256,
            "price_vnd": 10_000_000.0,
        },
        {
            "listing_record_id": "l2",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron A",
            "cpu_model": "Core i5",
            "ram_gb": 8,
            "storage_gb": 256,
            "price_vnd": 12_000_000.0,
        },
        {
            "listing_record_id": "l3",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron B",
            "cpu_model": "Core i7",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 20_000_000.0,
        },
        {
            "listing_record_id": "l4",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron B",
            "cpu_model": "Core i7",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 20_000_000.0,
        },
    ]
    enriched, products_df = resolve_canonical_products(cleaned_rows)
    assert len(products_df) == 2

    G = build_bipartite_graph(enriched, products_df)
    stats = compute_retailer_degree_stats(G, products_df)

    tgdd = stats[stats["retailer"] == "TGDĐ"].iloc[0]
    fpt = stats[stats["retailer"] == "FPT"].iloc[0]

    # TGDĐ won both competitive products (P1 at 10M <= 10M, P2 at 20M <= 20M) -> 100% win rate, 0% premium
    assert tgdd["price_leader_win_rate_pct"] == 100.0
    assert tgdd["avg_price_premium_pct"] == 0.0

    # FPT won 1 of 2 (P2 at 20M <= 20M) -> 50% win rate
    # FPT premium on P1: (12-10)/10 = 20%, on P2: 0% -> avg = 10%
    assert fpt["price_leader_win_rate_pct"] == 50.0
    assert fpt["avg_price_premium_pct"] == 10.0


def test_m5_cpu_tier_extraction() -> None:
    assert extract_cpu_tier("Apple M5") == "apple_m_base"
    assert extract_cpu_tier("Apple M5 Pro") == "apple_m_pro"
    assert extract_cpu_tier("Apple M5 Max") == "apple_m_pro"
    assert extract_cpu_tier("Apple M4") == "apple_m_base"


def test_cli_benchmarks_subparser() -> None:
    from src.market_graph.cli import build_parser

    parser = build_parser()
    args1 = parser.parse_args(["step1_5"])
    assert args1.command == "step1_5"

    args2 = parser.parse_args(["benchmarks"])
    assert args2.command == "benchmarks"


def test_gpu_and_screen_size_canonical_separation() -> None:
    # 1. Same brand, model, CPU, RAM, storage, but RTX 2050 vs RTX 4050 -> must NOT be merged
    rows_gpu = [
        {
            "listing_record_id": "g1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Acer",
            "model_clean": "Nitro V ANV15-51",
            "cpu_model": "Core i5-13420H",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": "RTX 2050",
            "screen_size_inch": 15.6,
            "price_vnd": 17_000_000.0,
        },
        {
            "listing_record_id": "g2",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "Acer",
            "model_clean": "Nitro V ANV15-51",
            "cpu_model": "Core i5-13420H",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": "RTX 4050",
            "screen_size_inch": 15.6,
            "price_vnd": 24_000_000.0,
        },
    ]
    _, df_gpu = resolve_canonical_products(rows_gpu)
    assert len(df_gpu) == 2, "Different GPU models must produce different canonical products"
    assert "screen_size_inch" in df_gpu.columns
    assert set(df_gpu["gpu_model"].dropna().unique()) == {"RTX 2050", "RTX 4050"}

    # 2. Same model, but 13.6 inch vs 15.3 inch screen -> must NOT be merged
    rows_screen = [
        {
            "listing_record_id": "s1",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Apple",
            "model_clean": "MacBook Air M3",
            "cpu_model": "Apple M3",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": None,
            "screen_size_inch": 13.6,
            "price_vnd": 32_000_000.0,
        },
        {
            "listing_record_id": "s2",
            "seller_name": "CellphoneS",
            "category_clean": "laptop",
            "brand": "Apple",
            "model_clean": "MacBook Air M3",
            "cpu_model": "Apple M3",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": None,
            "screen_size_inch": 15.3,
            "price_vnd": 36_000_000.0,
        },
    ]
    _, df_screen = resolve_canonical_products(rows_screen)
    assert len(df_screen) == 2, "Different screen sizes must produce different canonical products"


def test_compatible_imputation_does_not_mix_incompatible_specs() -> None:
    # Target has unknown CPU, but known RAM=16GB
    # Donor 1 has RAM=8GB, CPU=Core i5 (incompatible on RAM!)
    # Donor 2 has RAM=16GB, CPU=Core i7 (compatible on RAM!)
    rows = [
        {
            "listing_record_id": "target",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron 15",
            "cpu_model": "Unknown",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 20_000_000.0,
        },
        {
            "listing_record_id": "donor1",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron 15",
            "cpu_model": "Core i5-1235U",
            "ram_gb": 8,
            "storage_gb": 512,
            "price_vnd": 19_000_000.0,  # within 5% price!
        },
        {
            "listing_record_id": "donor2",
            "seller_name": "CellphoneS",
            "category_clean": "laptop",
            "brand": "Dell",
            "model_clean": "Inspiron 15",
            "cpu_model": "Core i7-1255U",
            "ram_gb": 16,
            "storage_gb": 512,
            "price_vnd": 21_000_000.0,  # within 5% price!
        },
    ]
    enriched, products_df = resolve_canonical_products(rows)
    target_row = next(r for r in enriched if r["listing_record_id"] == "target")
    assert target_row["cpu_model"] == "Core i7-1255U", "Must impute from compatible 16GB donor, not 8GB donor"


def test_category_specific_structural_holes() -> None:
    # Construct a dataset where smartphones have 10,000 reviews and laptops have 50 reviews
    # Laptop segment should NOT be suppressed by the smartphone review scale
    df_seg = pd.DataFrame(
        [
            # Smartphone listings
            {"canonical_product_id": f"p_s{i}", "segment_label": "Phone High End", "retailers": "TGDĐ|FPT"}
            for i in range(10)
        ]
        + [
            # Laptop listings
            {"canonical_product_id": f"p_l{i}", "segment_label": "Laptop Gaming", "retailers": "CellphoneS"}
            for i in range(5)
        ]
    )
    segments_df = pd.DataFrame(
        [
            {
                "community_id": "phone_c1",
                "segment_label": "Phone High End",
                "category": "smartphone",
                "product_count": 10,
                "total_reviews": 50_000,  # 5000 reviews/product
                "avg_retailer_degree": 2.0,
                "price_min_m": 25.0,
                "price_max_m": 35.0,
                "top_brands": "Apple, Samsung",
                "cpu_perf_median": 5000.0,
                "cpu_perf_min": 4500.0,
                "cpu_perf_max": 5500.0,
                "gpu_perf_median": None,
            },
            {
                "community_id": "laptop_c1",
                "segment_label": "Laptop Gaming",
                "category": "laptop",
                "product_count": 5,
                "total_reviews": 250,  # 50 reviews/product (far below phone's 5000, but high for laptop)
                "avg_retailer_degree": 1.0,  # low competition
                "price_min_m": 20.0,
                "price_max_m": 28.0,
                "top_brands": "Acer, ASUS",
                "cpu_perf_median": 65.0,
                "cpu_perf_min": 60.0,
                "cpu_perf_max": 70.0,
                "gpu_perf_median": 75.0,
            },
        ]
    )

    ct, holes_df = detect_structural_holes(df_seg, segments_df, min_segment_size=5)
    underserved = holes_df[holes_df["gap_type"] == "underserved_high_demand"]
    assert not underserved.empty
    assert "Laptop Gaming" in underserved["segment_label"].values, "Laptop segment must be detected as underserved"


def test_norm_gpu_unification() -> None:
    # 1. RTX 4050 variations with vendor, stopwords, vram suffix
    h1 = compute_base_hash("Acer", "Nitro V", "Core i5-13420H", 16, 512, "NVIDIA GeForce RTX 4050 Laptop GPU", 15.6, "laptop")
    h2 = compute_base_hash("Acer", "Nitro V", "Core i5-13420H", 16, 512, "RTX 4050 6GB", 15.6, "laptop")
    h3 = compute_base_hash("Acer", "Nitro V", "Core i5-13420H", 16, 512, "RTX 4050", 15.6, "laptop")
    assert h1 == h2 == h3

    # 2. Intel Iris Xe Graphics vs Intel Iris Xe
    h4 = compute_base_hash("HP", "Pavilion", "Core i5-1335U", 16, 512, "Intel Iris Xe Graphics", 15.6, "laptop")
    h5 = compute_base_hash("HP", "Pavilion", "Core i5-1335U", 16, 512, "Intel Iris Xe", 15.6, "laptop")
    assert h4 == h5


def test_smartphone_ignores_gpu_in_hash_and_resolution() -> None:
    # Smartphone with Adreno 750 vs smartphone with null GPU -> same hash & single canonical product
    h1 = compute_base_hash("Samsung", "Galaxy S24 Ultra", "Snapdragon 8 Gen 3", 12, 256, "Adreno 750", 6.8, "smartphone")
    h2 = compute_base_hash("Samsung", "Galaxy S24 Ultra", "Snapdragon 8 Gen 3", 12, 256, None, 6.8, "smartphone")
    assert h1 == h2

    rows = [
        {
            "listing_record_id": "p1",
            "seller_name": "TGDĐ",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy S24 Ultra",
            "cpu_model": "Snapdragon 8 Gen 3",
            "ram_gb": 12,
            "storage_gb": 256,
            "gpu_model": "Adreno 750",
            "screen_size_inch": 6.8,
            "price_vnd": 30_000_000.0,
        },
        {
            "listing_record_id": "p2",
            "seller_name": "FPT",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy S24 Ultra",
            "cpu_model": "Snapdragon 8 Gen 3",
            "ram_gb": 12,
            "storage_gb": 256,
            "gpu_model": None,  # unextracted on this retailer
            "screen_size_inch": 6.8,
            "price_vnd": 30_500_000.0,
        },
    ]
    enriched, products_df = resolve_canonical_products(rows)
    assert len(products_df) == 1, "Smartphones with identical specs must not be fragmented by null GPU"


def test_impute_gpu_and_screen_size() -> None:
    # Retailer A has complete specs: Intel Iris Xe, 15.6 inch
    # Retailer B omitted both GPU and screen size
    rows = [
        {
            "listing_record_id": "l_tgdd",
            "seller_name": "TGDĐ",
            "category_clean": "laptop",
            "brand": "HP",
            "model_clean": "Pavilion 15",
            "cpu_model": "Core i5-1335U",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": "Intel Iris Xe",
            "screen_size_inch": 15.6,
            "price_vnd": 16_000_000.0,
        },
        {
            "listing_record_id": "l_fpt",
            "seller_name": "FPT",
            "category_clean": "laptop",
            "brand": "HP",
            "model_clean": "Pavilion 15",
            "cpu_model": "Core i5-1335U",
            "ram_gb": 16,
            "storage_gb": 512,
            "gpu_model": None,  # missing on FPT raw specs
            "screen_size_inch": None,  # missing on FPT raw specs
            "price_vnd": 16_500_000.0,
        },
    ]
    enriched, products_df = resolve_canonical_products(rows)
    assert len(products_df) == 1, "Missing GPU and screen size must be imputed from compatible donor"
    prod = products_df.iloc[0]
    assert prod["retailer_count"] == 2
    assert prod["gpu_model"] == "Intel Iris Xe"
    assert prod["screen_size_inch"] == 15.6

    G = build_bipartite_graph(enriched, products_df)
    stats = compute_retailer_degree_stats(G, products_df)
    for _, ret_row in stats.iterrows():
        assert ret_row["competitive_count"] == 1
        assert ret_row["exclusive_count"] == 0


# --- Review fixes: analysis price floor ---------------------------------------


def test_filter_min_price_drops_low_known_prices_and_keeps_missing() -> None:
    df = pd.DataFrame(
        [
            {"category": "smartphone", "price_median": 999_999.0},
            {"category": "smartphone", "price_median": 1_000_000.0},
            {"category": "laptop", "price_median": 2_999_999.0},
            {"category": "laptop", "price_median": 3_000_000.0},
            {"category": "smartphone", "price_median": float("nan")},
            {"category": "tablet", "price_median": 10.0},
        ]
    )
    filtered = filter_min_price(df)
    assert len(filtered) == 4
    assert min_price_for("tablet") == 0.0
    assert min_price_for(None) == 0.0


def test_step2_keeps_full_canonical_table_but_floors_category_views(tmp_path: Path) -> None:
    rows = [
        {
            "listing_record_id": "low1",
            "seller_name": "CellphoneS",
            "category_clean": "smartphone",
            "brand": "Masstel",
            "model_clean": "Izi 20",
            "cpu_model": "Unisoc T107",
            "ram_gb": 0.5,
            "storage_gb": 0.128,
            "price_vnd": 390_000.0,
        },
        {
            "listing_record_id": "ok1",
            "seller_name": "CellphoneS",
            "category_clean": "smartphone",
            "brand": "Samsung",
            "model_clean": "Galaxy A57 5G",
            "cpu_model": "Exynos 1680",
            "ram_gb": 8,
            "storage_gb": 128,
            "price_vnd": 10_490_000.0,
        },
    ]
    input_path = tmp_path / "rows.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    _, products_df, _ = run_step2(input_path=input_path, work_dir=tmp_path)
    assert len(products_df) == 2
    canonical = pd.read_csv(tmp_path / "canonical_products.csv")
    assert len(canonical) == 2
    stats = pd.read_csv(tmp_path / "retailer_degree_stats_smartphone.csv")
    assert int(stats.loc[stats["retailer"] == "CellphoneS", "total_canonical_products"].iloc[0]) == 1


# --- Review fixes: robust price premium ---------------------------------------


def test_price_premium_guard_excludes_implausible_pairs() -> None:
    enriched = [
        {"seller_name": "CellphoneS", "canonical_product_id": "p_bad", "price_vnd": 10_490_000.0},
        {"seller_name": "FPT", "canonical_product_id": "p_bad", "price_vnd": 70_000.0},
        {"seller_name": "CellphoneS", "canonical_product_id": "p_ok", "price_vnd": 12_000_000.0},
        {"seller_name": "FPT", "canonical_product_id": "p_ok", "price_vnd": 12_000_000.0},
    ]
    products = pd.DataFrame(
        [
            {
                "canonical_product_id": "p_bad",
                "category": "smartphone",
                "brand": "Samsung",
                "model_clean": "Galaxy A57 5G",
                "cpu_model": "Exynos 1680",
                "price_median": 5_000_000.0,
            },
            {
                "canonical_product_id": "p_ok",
                "category": "smartphone",
                "brand": "Xiaomi",
                "model_clean": "Redmi Note 17",
                "cpu_model": "Snapdragon 6s Gen 2",
                "price_median": 12_000_000.0,
            },
        ]
    )
    G = build_bipartite_graph(enriched, products)
    stats = compute_retailer_degree_stats(G, products)

    cellphones = stats[stats["retailer"] == "CellphoneS"].iloc[0]
    # The 10.49M vs 70k pair is an ER anomaly: excluded, not averaged in.
    assert cellphones["price_premium_pairs_excluded"] == 1
    assert cellphones["price_premium_pairs_used"] == 1
    assert cellphones["avg_price_premium_pct"] == 0.0
    assert cellphones["median_price_premium_pct"] == 0.0

    fpt = stats[stats["retailer"] == "FPT"].iloc[0]
    assert fpt["price_premium_pairs_excluded"] == 0


# --- Review fixes: price-free TV5/TV8 handoff ---------------------------------


def _handoff_listing(lid: str, seller: str, price: float = 12_000_000.0) -> dict:
    return {
        "listing_record_id": lid,
        "seller_name": seller,
        "source": "cellphones",
        "category_clean": "smartphone",
        "canonical_product_id": f"cid_{lid}",
        "brand": "Samsung",
        "model_clean": "Galaxy A57 5G",
        "cpu_model": "Exynos 1680",
        "ram_gb": 8,
        "storage_gb": 128,
        "price_vnd": price,
    }


def _handoff_observed(lid: str, seller: str, ram: float | None = 8) -> dict:
    return {
        "listing_record_id": lid,
        "seller_name": seller,
        "category_clean": "smartphone",
        "brand": "Samsung",
        "model_clean": "Galaxy A57 5G",
        "cpu_model": "Exynos 1680",
        "ram_gb": ram,
        "storage_gb": 128,
        "price_vnd": 12_000_000.0,
    }


def test_price_free_handoff_exposes_only_whitelisted_columns() -> None:
    handoff = build_price_free_handoff(
        listings=[_handoff_listing("a", "CellphoneS")],
        observed_rows=[_handoff_observed("a", "CellphoneS")],
        laptop_benchmarks=[],
        smartphone_benchmarks=[
            {
                "listing_record_id": "a",
                "cpu_perf_rating": 55.0,
                "cpu_benchmark_score": 3000.0,
                "cpu_geekbench_5_multi": 2900.0,
            }
        ],
    )
    assert list(handoff.columns) == HANDOFF_COLUMNS
    lowered = [column.lower() for column in handoff.columns]
    for token in HANDOFF_FORBIDDEN_TOKENS:
        assert not any(token in column for column in lowered), token
    assert HANDOFF_LINEAGE_ONLY.issubset(set(handoff.columns))


def test_price_free_handoff_is_invariant_to_price() -> None:
    listings = [_handoff_listing("a", "CellphoneS"), _handoff_listing("b", "FPT")]
    observed = [_handoff_observed("a", "CellphoneS"), _handoff_observed("b", "FPT")]
    bench = [
        {"listing_record_id": "a", "cpu_perf_rating": 55.0, "cpu_benchmark_score": 3000.0},
        {"listing_record_id": "b", "cpu_perf_rating": 55.0, "cpu_benchmark_score": 3000.0},
    ]
    base = build_price_free_handoff(
        listings=listings, observed_rows=observed, laptop_benchmarks=[], smartphone_benchmarks=bench
    )
    scaled = build_price_free_handoff(
        listings=[{**row, "price_vnd": row["price_vnd"] * 1.37} for row in listings],
        observed_rows=[{**row, "price_vnd": row["price_vnd"] * 1.37} for row in observed],
        laptop_benchmarks=[],
        smartphone_benchmarks=bench,
    )
    pd.testing.assert_frame_equal(base, scaled)


def test_hw_seller_count_uses_observed_specs_not_imputed_cids() -> None:
    listings = [
        _handoff_listing("a", "CellphoneS"),
        _handoff_listing("b", "FPT"),  # RAM 8 here is imputed by Step 2
    ]
    observed = [
        _handoff_observed("a", "CellphoneS"),
        _handoff_observed("b", "FPT", ram=None),  # observed RAM is actually missing
    ]
    handoff = build_price_free_handoff(
        listings=listings, observed_rows=observed, laptop_benchmarks=[], smartphone_benchmarks=[]
    )
    by_id = handoff.set_index("listing_record_id")
    assert by_id.loc["a", "hw_seller_count"] == 1
    assert pd.isna(by_id.loc["b", "hw_seller_count"])
    assert bool(by_id.loc["b", "hw_key_complete"]) is False
    # The imputed RAM must not appear as a feature either.
    assert by_id.loc["a", "ram_gb"] == 8
    assert pd.isna(by_id.loc["b", "ram_gb"])


def test_hw_seller_count_counts_distinct_sellers() -> None:
    observed = [
        _handoff_observed("a", "CellphoneS"),
        _handoff_observed("b", "FPT"),
        _handoff_observed("c", "CellphoneS"),
    ]
    listings = [_handoff_listing("a", "CellphoneS"), _handoff_listing("b", "FPT"), _handoff_listing("c", "CellphoneS")]
    handoff = build_price_free_handoff(
        listings=listings, observed_rows=observed, laptop_benchmarks=[], smartphone_benchmarks=[]
    )
    assert set(handoff["hw_seller_count"]) == {2}
    assert set(handoff["hw_listing_count"]) == {3}


@pytest.mark.parametrize("has_stale_default", [False, True])
def test_handoff_cli_uses_custom_observed_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, has_stale_default: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    observed_path = Path("sample_100_cleaned.jsonl")
    work_dir = tmp_path / "work"
    rows = [
        _handoff_listing("a", "CellphoneS"),
        {**_handoff_listing("b", "FPT"), "ram_gb": None, "cpu_model": "Unknown"},
    ]
    observed_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    cli.main(["step2", "--input", str(observed_path), "--work-dir", str(work_dir)])
    if has_stale_default:
        stale = [{**row, "ram_gb": 32, "cpu_model": "Stale CPU"} for row in rows]
        (work_dir / "products_llm_cleaned.jsonl").write_text(
            "\n".join(json.dumps(row) for row in stale), encoding="utf-8"
        )

    cli.main(["handoff", "--input", str(observed_path), "--work-dir", str(work_dir)])

    handoff = pd.read_csv(work_dir / "handoff" / "tv5_tv8_price_free_features.csv").set_index("listing_record_id")
    assert set(handoff.index) == {"a", "b"}
    assert handoff.loc["a", "ram_gb"] == 8
    assert handoff.loc["a", "cpu_model"] == "Exynos 1680"
    assert handoff.loc["a", "hw_seller_count"] == 1
    assert pd.isna(handoff.loc["b", "ram_gb"])
    assert pd.isna(handoff.loc["b", "hw_seller_count"])
    assert handoff.loc["b", "cpu_model"] == "Unknown"


def test_handoff_default_observed_input_remains_supported(tmp_path: Path) -> None:
    listing = _handoff_listing("a", "CellphoneS")
    (tmp_path / "canonical_listings.jsonl").write_text(json.dumps(listing), encoding="utf-8")
    (tmp_path / "products_llm_cleaned.jsonl").write_text(
        json.dumps(_handoff_observed("a", "CellphoneS")), encoding="utf-8"
    )
    expected = build_price_free_handoff(work_dir=tmp_path)

    cli.main(["handoff", "--work-dir", str(tmp_path)])

    actual = pd.read_csv(tmp_path / "handoff" / "tv5_tv8_price_free_features.csv")
    pd.testing.assert_frame_equal(
        actual.astype(object).where(actual.notna(), None),
        expected.astype(object).where(expected.notna(), None),
    )


def test_handoff_injected_observed_rows_take_precedence_over_path(tmp_path: Path) -> None:
    handoff = build_price_free_handoff(
        listings=[_handoff_listing("a", "CellphoneS")],
        observed_rows=[_handoff_observed("a", "CellphoneS")],
        observed_input_path=tmp_path / "missing.jsonl",
        laptop_benchmarks=[],
        smartphone_benchmarks=[],
    )
    assert handoff.loc[0, "ram_gb"] == 8


@pytest.mark.parametrize("explicit_input", [False, True])
def test_handoff_missing_observed_input_preserves_existing_output(
    tmp_path: Path, explicit_input: bool
) -> None:
    (tmp_path / "canonical_listings.jsonl").write_text(
        json.dumps(_handoff_listing("a", "CellphoneS")), encoding="utf-8"
    )
    missing = tmp_path / ("missing.jsonl" if explicit_input else "products_llm_cleaned.jsonl")
    if explicit_input:
        (tmp_path / "products_llm_cleaned.jsonl").write_text(
            json.dumps(_handoff_observed("a", "CellphoneS")), encoding="utf-8"
        )
    output = tmp_path / "handoff" / "tv5_tv8_price_free_features.csv"
    output.parent.mkdir()
    output.write_bytes(b"previous handoff\n")

    with pytest.raises(FileNotFoundError) as error:
        export_price_free_handoff(
            work_dir=tmp_path, observed_input_path=missing if explicit_input else None
        )

    assert str(missing) in str(error.value)
    assert "handoff --input" in str(error.value)
    assert output.read_bytes() == b"previous handoff\n"


def test_run_all_handoff_uses_cleaned_path_returned_by_step1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cleaned_path = tmp_path / "custom_cleaned.jsonl"
    cleaned_path.write_text(json.dumps(_handoff_listing("a", "CellphoneS")), encoding="utf-8")
    work_dir = tmp_path / "work"
    monkeypatch.setattr(cli, "run_step1", lambda **kwargs: cleaned_path)
    for stage in ("run_step1_5", "run_step3", "run_step4"):
        monkeypatch.setattr(cli, stage, lambda **kwargs: None)

    cli.main(["run-all", "--input", str(tmp_path / "raw.jsonl"), "--work-dir", str(work_dir)])

    handoff = pd.read_csv(work_dir / "handoff" / "tv5_tv8_price_free_features.csv")
    assert list(handoff["listing_record_id"]) == ["a"]
    assert handoff.loc[0, "ram_gb"] == 8
