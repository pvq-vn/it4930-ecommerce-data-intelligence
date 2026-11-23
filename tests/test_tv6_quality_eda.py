"""Unit tests for Step 1 Quality EDA and Profiling."""

import json
from pathlib import Path
import unittest

from src.review_nlp.config import (
    DOCS_QUALITY_REPORT_FILE,
    FIGURES_TV6_DIR,
    QUALITY_REPORT_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)


class TestTV6QualityEDA(unittest.TestCase):
    """Test suite verifying Step 1 outputs, artifacts, and consistency."""

    @classmethod
    def setUpClass(cls):
        """Ensure Step 1 artifacts exist."""
        cls.report_file = QUALITY_REPORT_FILE
        cls.docs_report_file = DOCS_QUALITY_REPORT_FILE
        cls.tables_dir = TABLES_TV6_DIR
        cls.figures_dir = FIGURES_TV6_DIR

        if not cls.report_file.exists():
            from src.review_nlp.eda_quality import run_step1_quality_eda

            run_step1_quality_eda()

    def test_quality_report_existence_and_schema(self):
        """Verify quality_report.json exists and adheres to schema."""
        self.assertTrue(self.report_file.exists(), "quality_report.json must exist in data/tv6")
        self.assertTrue(self.docs_report_file.exists(), "quality_report.json must exist in docs/tv6")

        with self.report_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["pipeline_version"], TV6_PIPELINE_VERSION)
        self.assertEqual(data["step"], "step1_quality_eda")
        self.assertIn("metrics", data)
        self.assertIn("artifacts_generated", data)

    def test_metric_mathematical_consistency(self):
        """Verify consistency between review counts and parent product coverage."""
        with self.report_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        m = data["metrics"]
        ratings = m["ratings_and_usability"]
        self.assertEqual(ratings["total_reviews"], 15805)
        self.assertEqual(ratings["usable_reviews"], 14869)
        self.assertEqual(ratings["unusable_reviews"], 936)
        self.assertEqual(ratings["usable_reviews"] + ratings["unusable_reviews"], 15805)

        cov = m["tv5_product_coverage"]
        self.assertEqual(cov["total_parent_products"], 7051)
        self.assertEqual(cov["parents_with_reviews"], 1897)
        self.assertEqual(cov["parents_zero_reviews"], 5154)
        self.assertEqual(cov["parents_with_reviews"] + cov["parents_zero_reviews"], 7051)
        self.assertAlmostEqual(cov["coverage_rate_pct"] + cov["cold_start_rate_pct"], 100.0, places=1)

    def test_tables_generation(self):
        """Verify all 7 expected tabular files exist in both CSV and Markdown."""
        expected_bases = [
            "table_1_1_rating_source_distribution",
            "table_1_2_usable_retention_by_source",
            "table_1_3_text_length_percentiles",
            "table_1_4_top_duplicate_texts",
            "table_1_5_rating_text_mismatch_audit",
            "table_1_6_product_coverage_audit",
            "table_1_7_temporal_distribution",
        ]
        for base in expected_bases:
            csv_f = self.tables_dir / f"{base}.csv"
            md_f = self.tables_dir / f"{base}.md"
            self.assertTrue(csv_f.exists(), f"Missing table CSV: {csv_f}")
            self.assertTrue(md_f.exists(), f"Missing table MD: {md_f}")
            self.assertGreater(csv_f.stat().st_size, 0, f"Empty CSV file: {csv_f}")
            self.assertGreater(md_f.stat().st_size, 0, f"Empty MD file: {md_f}")

    def test_figures_generation(self):
        """Verify all 5 visualization figures are generated with valid image sizes."""
        expected_figs = [
            "fig_1_1_rating_distribution_by_source.png",
            "fig_1_2_usable_vs_unusable_breakdown.png",
            "fig_1_3_text_length_distribution.png",
            "fig_1_4_temporal_trend_reviews.png",
            "fig_1_5_product_review_coverage.png",
        ]
        for fig_name in expected_figs:
            fig_path = self.figures_dir / fig_name
            self.assertTrue(fig_path.exists(), f"Missing figure: {fig_path}")
            # Figure should be a non-trivial PNG (at least 20 KB for 300 DPI)
            self.assertGreater(fig_path.stat().st_size, 20_000, f"Figure too small: {fig_path}")


if __name__ == "__main__":
    unittest.main()
