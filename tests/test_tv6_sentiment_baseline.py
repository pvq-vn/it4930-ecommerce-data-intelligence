"""Unit tests for Step 3.1: Classical ML Sentiment Classification Baseline."""

import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DOCS_SENTIMENT_BASELINE_REPORT_FILE,
    FIGURES_TV6_DIR,
    REVIEWS_TV6_SENTIMENT_BASELINE_FILE,
    SENTIMENT_BASELINE_REPORT_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)


class TestTV6SentimentBaseline(unittest.TestCase):
    """Test suite verifying Step 3.1 model evaluation outputs, schema, and metric sanity."""

    @classmethod
    def setUpClass(cls):
        """Reference output paths."""
        cls.baseline_file = REVIEWS_TV6_SENTIMENT_BASELINE_FILE
        cls.report_file = SENTIMENT_BASELINE_REPORT_FILE
        cls.docs_report_file = DOCS_SENTIMENT_BASELINE_REPORT_FILE
        cls.tables_dir = TABLES_TV6_DIR
        cls.figures_dir = FIGURES_TV6_DIR

    def test_output_files_existence(self):
        """Verify baseline scored dataset and metadata report files exist."""
        if not self.baseline_file.exists():
            self.skipTest("Intermediate JSONL is gitignored on clean checkout. Run python src/review_nlp/run_step3_1.py first.")
        self.assertTrue(self.baseline_file.exists(), "reviews_tv6_sentiment_baseline.jsonl must exist")
        self.assertTrue(self.report_file.exists(), "sentiment_baseline_report.json must exist in data/tv6")
        self.assertTrue(self.docs_report_file.exists(), "sentiment_baseline_report.json must exist in docs/tv6")

    def test_record_count_preservation(self):
        """Verify exactly 14,869 usable reviews are scored with 0 loss."""
        if not self.baseline_file.exists():
            self.skipTest("Intermediate JSONL is gitignored on clean checkout.")
        with self.baseline_file.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        self.assertEqual(count, 14869, "Must retain exactly 14,869 scored reviews")

    def test_sentiment_score_and_schema_validity(self):
        """Verify sentiment_pred, sentiment_score, and probabilities conform to contract."""
        if not self.baseline_file.exists():
            self.skipTest("Intermediate JSONL is gitignored on clean checkout.")
        expected_fields = {
            "review_record_id",
            "source_parent_id",
            "rating_raw",
            "sentiment_label_groundtruth",
            "sentiment_pred",
            "sentiment_score",
            "sentiment_confidence",
            "prob_negative",
            "prob_neutral",
            "prob_positive",
            "sentiment_model",
            "sentiment_step_version",
        }
        with self.baseline_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx > 300:  # Sample 300 records
                    break
                rec = json.loads(line)
                self.assertTrue(expected_fields.issubset(set(rec.keys())))
                self.assertIn(rec["sentiment_label_groundtruth"], ["POSITIVE", "NEUTRAL", "NEGATIVE"])
                self.assertIn(rec["sentiment_pred"], ["POSITIVE", "NEUTRAL", "NEGATIVE"])

                # Continuous score in [-1.0, 1.0]
                self.assertGreaterEqual(rec["sentiment_score"], -1.0)
                self.assertLessEqual(rec["sentiment_score"], 1.0)

                # Confidence in [0.0, 1.0]
                self.assertGreaterEqual(rec["sentiment_confidence"], 0.0)
                self.assertLessEqual(rec["sentiment_confidence"], 1.0)

                # Probabilities sum ~ 1.0
                prob_sum = rec["prob_negative"] + rec["prob_neutral"] + rec["prob_positive"]
                self.assertAlmostEqual(prob_sum, 1.0, delta=0.01)

                self.assertEqual(rec["sentiment_step_version"], TV6_PIPELINE_VERSION)

    def test_report_metric_sanity(self):
        """Verify report metrics are mathematically consistent and non-trivial."""
        with self.report_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["step"], "step3_1_sentiment_baseline")
        self.assertIn("best_model_selected", data)
        self.assertIn(data["best_model_selected"], data["model_results"])

        best_m = data["model_results"][data["best_model_selected"]]
        self.assertGreater(best_m["test_macro_f1"], 0.40, "Macro F1 must exceed random guessing threshold")
        self.assertGreater(best_m["test_weighted_f1"], 0.70, "Weighted F1 must exceed 0.70")
        self.assertGreater(best_m["test_accuracy"], 0.75, "Accuracy must exceed 0.75")

    def test_tables_and_figures_generated(self):
        """Verify all Step 3.1 tables and figures exist."""
        expected_tables = [
            "table_3_1_model_comparison",
            "table_3_2_confusion_matrices",
            "table_3_3_top_polar_features",
        ]
        for base in expected_tables:
            csv_f = self.tables_dir / f"{base}.csv"
            md_f = self.tables_dir / f"{base}.md"
            self.assertTrue(csv_f.exists(), f"Missing table CSV: {csv_f}")
            self.assertTrue(md_f.exists(), f"Missing table MD: {md_f}")

        expected_figures = [
            "fig_3_1_model_comparison_metrics.png",
            "fig_3_2_confusion_matrices.png",
            "fig_3_3_top_polar_words.png",
        ]
        for fig_name in expected_figures:
            fig_f = self.figures_dir / fig_name
            self.assertTrue(fig_f.exists(), f"Missing figure: {fig_f}")
            self.assertGreater(fig_f.stat().st_size, 20_000, f"Figure too small: {fig_f}")


if __name__ == "__main__":
    unittest.main()
