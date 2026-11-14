"""Unit tests for Step 4: Topic Modeling (LDA & NMF) & Aspect-Based Sentiment Mining (ABSA)."""

import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DOCS_TOPIC_ASPECT_REPORT_FILE,
    FIGURES_TV6_DIR,
    REVIEWS_TV6_ASPECTS_FILE,
    TABLES_TV6_DIR,
    TOPIC_ASPECT_REPORT_FILE,
    TV6_PIPELINE_VERSION,
)


class TestTV6TopicAspectMining(unittest.TestCase):
    """Test suite verifying Step 4 topic and aspect mining outputs, schema, and metric consistency."""

    @classmethod
    def setUpClass(cls):
        cls.output_file = REVIEWS_TV6_ASPECTS_FILE
        cls.report_file = TOPIC_ASPECT_REPORT_FILE
        cls.docs_report_file = DOCS_TOPIC_ASPECT_REPORT_FILE
        cls.tables_dir = TABLES_TV6_DIR
        cls.figures_dir = FIGURES_TV6_DIR

    def test_output_files_existence(self):
        """Verify that aspects dataset and report JSON exist (or skip if not executed)."""
        if not self.output_file.exists():
            self.skipTest("Step 4 pipeline has not been executed yet. Run python src/review_nlp/run_step4.py first.")
        self.assertTrue(self.output_file.exists())
        self.assertTrue(self.report_file.exists())
        self.assertTrue(self.docs_report_file.exists())

    def test_record_count_preservation(self):
        """Verify exactly 14,869 usable reviews are retained with 0 data loss."""
        if not self.output_file.exists():
            self.skipTest("Step 4 pipeline has not been executed yet.")
        with self.output_file.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        self.assertEqual(count, 14869)

    def test_record_schema_and_aspect_conformance(self):
        """Verify schema fields, dominant_topic, aspect_mentions, and aspect_sentiments structure."""
        if not self.output_file.exists():
            self.skipTest("Step 4 pipeline has not been executed yet.")

        required_fields = {
            "review_record_id",
            "source_parent_id",
            "source",
            "category",
            "rating_raw",
            "sentiment_pred",
            "sentiment_score",
            "dominant_topic_id",
            "dominant_topic_name",
            "aspect_mentions",
            "aspect_sentiments",
            "aspect_count",
            "tv6_pipeline_version",
        }

        with self.output_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if not line.strip():
                    continue
                record = json.loads(line)
                self.assertTrue(required_fields.issubset(record.keys()))
                self.assertEqual(record["tv6_pipeline_version"], TV6_PIPELINE_VERSION)
                self.assertIn(record["sentiment_pred"], {"POSITIVE", "NEUTRAL", "NEGATIVE"})
                self.assertIsInstance(record["aspect_mentions"], list)
                self.assertIsInstance(record["aspect_sentiments"], dict)
                self.assertEqual(len(record["aspect_mentions"]), record["aspect_count"])
                self.assertGreaterEqual(record["dominant_topic_id"], 0)
                self.assertLessEqual(record["dominant_topic_id"], 4)

                for asp in record["aspect_mentions"]:
                    self.assertIn(asp, record["aspect_sentiments"])
                    self.assertIn(record["aspect_sentiments"][asp], {"POSITIVE", "NEUTRAL", "NEGATIVE"})

                if idx >= 200:
                    break

    def test_tables_and_figures_generated(self):
        """Verify all Step 4 tables and figures are generated with non-zero size."""
        if not self.output_file.exists():
            self.skipTest("Step 4 pipeline has not been executed yet.")

        expected_tables = [
            "table_4_1_lda_topics",
            "table_4_2_nmf_topics",
            "table_4_3_aspect_sentiment_distribution",
            "table_4_4_category_aspect_comparison",
        ]
        for tbl in expected_tables:
            csv_file = self.tables_dir / f"{tbl}.csv"
            md_file = self.tables_dir / f"{tbl}.md"
            self.assertTrue(csv_file.exists(), f"Missing {csv_file}")
            self.assertTrue(md_file.exists(), f"Missing {md_file}")
            self.assertGreater(csv_file.stat().st_size, 0)
            self.assertGreater(md_file.stat().st_size, 0)

        expected_figures = [
            "fig_4_1_wordclouds_by_sentiment.png",
            "fig_4_2_topic_distribution.png",
            "fig_4_3_aspect_sentiment_matrix.png",
            "fig_4_4_aspect_by_category.png",
        ]
        for fig in expected_figures:
            fig_file = self.figures_dir / fig
            self.assertTrue(fig_file.exists(), f"Missing {fig_file}")
            self.assertGreater(fig_file.stat().st_size, 5000)

    def test_report_metric_sanity(self):
        """Verify report metrics are consistent and valid."""
        if not self.report_file.exists():
            self.skipTest("Step 4 pipeline has not been executed yet.")

        with self.report_file.open("r", encoding="utf-8") as f:
            report = json.load(f)

        self.assertEqual(report["step"], "step4_topic_aspect_mining")
        self.assertEqual(report["total_reviews_analyzed"], 14869)
        self.assertGreater(report["aspect_coverage_rate"], 30.0)  # Significant aspect coverage
        self.assertEqual(len(report["lda_topics"]), 5)
        self.assertEqual(len(report["nmf_topics"]), 5)
        self.assertEqual(len(report["aspect_distribution"]), 5)


if __name__ == "__main__":
    unittest.main()
