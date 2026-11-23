"""Unit tests for Step 3.2 PhoBERT Sentiment Classification Fine-Tuning."""

import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DOCS_SENTIMENT_PHOBERT_REPORT_FILE,
    FIGURES_TV6_DIR,
    PHOBERT_MODEL_DIR,
    REVIEWS_TV6_SENTIMENT_PHOBERT_FILE,
    SENTIMENT_PHOBERT_REPORT_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)


class TestTV6PhoBERTSentiment(unittest.TestCase):
    """Test suite verifying Step 3.2 PhoBERT model outputs, schema, and metric sanity."""

    @classmethod
    def setUpClass(cls):
        cls.output_file = REVIEWS_TV6_SENTIMENT_PHOBERT_FILE
        cls.report_file = SENTIMENT_PHOBERT_REPORT_FILE
        cls.docs_report_file = DOCS_SENTIMENT_PHOBERT_REPORT_FILE
        cls.tables_dir = TABLES_TV6_DIR
        cls.figures_dir = FIGURES_TV6_DIR
        cls.model_dir = PHOBERT_MODEL_DIR / "best_model"

    def test_output_files_existence(self):
        """Verify PhoBERT scored dataset and report exist (or skip if not executed yet)."""
        if not self.output_file.exists():
            self.skipTest("PhoBERT pipeline has not been executed yet. Run python src/review_nlp/run_step3_2.py first.")
        self.assertTrue(self.output_file.exists())
        self.assertTrue(self.report_file.exists())
        self.assertTrue(self.docs_report_file.exists())

    def test_record_count_preservation(self):
        """Verify exactly 14,869 usable reviews are scored with 0 loss."""
        if not self.output_file.exists():
            self.skipTest("PhoBERT pipeline has not been executed yet.")
        with self.output_file.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        self.assertEqual(count, 14869)

    def test_sentiment_score_and_schema_validity(self):
        """Verify sentiment_pred, sentiment_score, and probabilities conform to contract."""
        if not self.output_file.exists():
            self.skipTest("PhoBERT pipeline has not been executed yet.")
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
        with self.output_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx > 300:
                    break
                rec = json.loads(line)
                self.assertTrue(expected_fields.issubset(set(rec.keys())))
                self.assertIn(rec["sentiment_label_groundtruth"], ["POSITIVE", "NEUTRAL", "NEGATIVE"])
                self.assertIn(rec["sentiment_pred"], ["POSITIVE", "NEUTRAL", "NEGATIVE"])
                self.assertGreaterEqual(rec["sentiment_score"], -1.0)
                self.assertLessEqual(rec["sentiment_score"], 1.0)
                self.assertGreaterEqual(rec["sentiment_confidence"], 0.0)
                self.assertLessEqual(rec["sentiment_confidence"], 1.0)
                prob_sum = rec["prob_negative"] + rec["prob_neutral"] + rec["prob_positive"]
                self.assertAlmostEqual(prob_sum, 1.0, delta=0.01)

    def test_report_metric_sanity(self):
        """Verify report metrics are mathematically consistent."""
        if not self.report_file.exists():
            self.skipTest("PhoBERT pipeline has not been executed yet.")
        with self.report_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["step"], "step3_2_phobert_sentiment")
        metrics = data["test_metrics"]
        self.assertGreater(metrics["test_macro_f1"], 0.40)
        self.assertGreater(metrics["test_weighted_f1"], 0.70)
        self.assertGreater(metrics["test_accuracy"], 0.75)

    def test_tables_and_figures_generated(self):
        """Verify comparative tables and training curves exist."""
        if not self.output_file.exists():
            self.skipTest("PhoBERT pipeline has not been executed yet.")
        self.assertTrue((self.tables_dir / "table_3_4_phobert_vs_baseline.csv").exists())
        self.assertTrue((self.tables_dir / "table_3_4_phobert_vs_baseline.md").exists())
        self.assertTrue((self.tables_dir / "table_3_5_phobert_confusion_matrix.csv").exists())
        self.assertTrue((self.tables_dir / "table_3_5_phobert_confusion_matrix.md").exists())
        self.assertTrue((self.figures_dir / "fig_3_4_phobert_training_curves.png").exists())
        self.assertTrue((self.figures_dir / "fig_3_5_phobert_vs_baseline_comparison.png").exists())


if __name__ == "__main__":
    unittest.main()
