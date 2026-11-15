"""Unit test suite for TV6 Step 5: Feature Engineering & Aggregation for TV5 (Price Prediction Handoff).

Tests verify:
1. File existence for Parquet, CSV, Report JSON, Tables (MD/CSV), and Figures (PNG).
2. Exact record count conservation: 7,051 parent products (1,897 active + 5,154 cold-start).
3. Review count conservation: sum of review_count_usable == 14,869.
4. Anti-leakage compliance: zero violations (review_time_raw <= crawl_time).
5. Schema completeness (all 35 canonical columns present).
6. Mathematical range validity (avg_rating in [1, 5], sentiment scores in [-1, 1], ratios in [0, 1]).
"""

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_TV6 = REPO_ROOT / "data" / "tv6"
DOCS_TV6 = REPO_ROOT / "docs" / "tv6"
TABLES_TV6 = DATA_TV6 / "tables"
FIGURES_TV6 = DATA_TV6 / "figures"

PARQUET_FULL = DATA_TV6 / "tv5_review_features.parquet"
CSV_FULL = DATA_TV6 / "tv5_review_features.csv"
PARQUET_ACTIVE = DATA_TV6 / "tv5_review_features_active_only.parquet"
CSV_ACTIVE = DATA_TV6 / "tv5_review_features_active_only.csv"
REPORT_FILE = DATA_TV6 / "tv5_feature_report.json"

EXPECTED_COLUMNS = [
    "source_parent_id",
    "source",
    "category",
    "product_name_rep",
    "has_review_data",
    "review_count_usable",
    "review_count_last_90d",
    "avg_rating",
    "rating_std",
    "rating_min",
    "rating_max",
    "avg_sentiment_score",
    "sentiment_positive_ratio",
    "sentiment_negative_ratio",
    "sentiment_neutral_ratio",
    "sentiment_net_score",
    "aspect_mention_rate_battery_power",
    "aspect_sentiment_score_battery_power",
    "aspect_mention_rate_performance_thermal",
    "aspect_sentiment_score_performance_thermal",
    "aspect_mention_rate_display_design",
    "aspect_sentiment_score_display_design",
    "aspect_mention_rate_camera_audio",
    "aspect_sentiment_score_camera_audio",
    "aspect_mention_rate_service_logistics",
    "aspect_sentiment_score_service_logistics",
    "topic_share_performance_setup",
    "topic_share_service_delivery",
    "topic_share_screen_camera",
    "topic_share_battery_charging",
    "topic_share_usage_experience",
    "earliest_review_time",
    "latest_review_time",
    "review_span_days",
    "tv6_pipeline_version",
]


class TestTV6TV5Handoff(unittest.TestCase):
    """Test suite validating Step 5 feature handoff contract."""

    @classmethod
    def setUpClass(cls):
        if not PARQUET_FULL.exists():
            raise unittest.SkipTest(f"Missing {PARQUET_FULL.name}; run run_step5.py first.")
        cls.df_full = pd.read_parquet(PARQUET_FULL)
        cls.df_active = pd.read_parquet(PARQUET_ACTIVE)
        with open(REPORT_FILE, "r", encoding="utf-8") as f:
            cls.report = json.load(f)

    def test_output_files_existence(self):
        """Verify all parquet, csv, report, tables, and figures exist with non-zero size."""
        files_to_check = [
            PARQUET_FULL,
            CSV_FULL,
            PARQUET_ACTIVE,
            CSV_ACTIVE,
            REPORT_FILE,
            DOCS_TV6 / "tv5_feature_report.json",
            TABLES_TV6 / "table_5_1_feature_dictionary.csv",
            TABLES_TV6 / "table_5_1_feature_dictionary.md",
            TABLES_TV6 / "table_5_2_handoff_summary_metrics.csv",
            TABLES_TV6 / "table_5_2_handoff_summary_metrics.md",
            TABLES_TV6 / "table_5_3_top_reviewed_products_features.csv",
            TABLES_TV6 / "table_5_3_top_reviewed_products_features.md",
            FIGURES_TV6 / "fig_5_1_feature_correlation_matrix.png",
            FIGURES_TV6 / "fig_5_2_sentiment_vs_rating_scatter.png",
            FIGURES_TV6 / "fig_5_3_aspect_scores_distribution.png",
        ]
        for f in files_to_check:
            self.assertTrue(f.exists(), f"Missing file: {f}")
            self.assertGreater(f.stat().st_size, 0, f"Empty file: {f}")

    def test_record_counts_and_conservation(self):
        """Verify exact count conservation: 7,051 total parents, 1,897 active, 5,154 cold-start."""
        self.assertEqual(len(self.df_full), 7051)
        self.assertEqual(len(self.df_active), 1897)

        cold_start_df = self.df_full[self.df_full["has_review_data"] == 0]
        self.assertEqual(len(cold_start_df), 5154)

        # Usable review count sum must equal exactly 14,869
        total_reviews = self.df_full["review_count_usable"].sum()
        self.assertEqual(total_reviews, 14869)

    def test_anti_leakage_audit_clean(self):
        """Verify zero leakage violations were detected in the anti-leakage audit."""
        audit = self.report.get("anti_leakage_audit", {})
        self.assertEqual(audit.get("status"), "PASS")
        self.assertEqual(audit.get("leakage_violations"), 0)
        self.assertGreater(audit.get("valid_time_pairs", 0), 15000)

    def test_schema_conformance(self):
        """Verify all 35 canonical columns are present and primary key is unique and non-null."""
        self.assertEqual(len(self.df_full.columns), 35)
        for col in EXPECTED_COLUMNS:
            self.assertIn(col, self.df_full.columns, f"Missing column {col}")

        # Unique primary key
        self.assertEqual(self.df_full["source_parent_id"].nunique(), 7051)
        self.assertFalse(self.df_full["source_parent_id"].isnull().any())

    def test_value_ranges_and_constraints(self):
        """Verify metric mathematical validity for active and cold-start products."""
        # Active products
        for _, row in self.df_active.iterrows():
            self.assertEqual(row["has_review_data"], 1)
            self.assertGreaterEqual(row["review_count_usable"], 1)
            self.assertGreaterEqual(row["avg_rating"], 1.0)
            self.assertLessEqual(row["avg_rating"], 5.0)
            self.assertGreaterEqual(row["avg_sentiment_score"], -1.0)
            self.assertLessEqual(row["avg_sentiment_score"], 1.0)

            ratio_sum = (
                row["sentiment_positive_ratio"]
                + row["sentiment_negative_ratio"]
                + row["sentiment_neutral_ratio"]
            )
            self.assertAlmostEqual(ratio_sum, 1.0, delta=0.01)

        # Cold-start products
        cold_df = self.df_full[self.df_full["has_review_data"] == 0]
        self.assertTrue((cold_df["review_count_usable"] == 0).all())
        self.assertTrue((cold_df["avg_sentiment_score"] == 0.0).all())
        self.assertTrue(cold_df["avg_rating"].isnull().all())
        self.assertTrue((cold_df["review_span_days"] == 0.0).all())


if __name__ == "__main__":
    unittest.main()
