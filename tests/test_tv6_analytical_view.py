"""Unit tests for TV6 Analytical View Generation (Step 0)."""

import json
from pathlib import Path
import unittest

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DOCS_STEP0_MANIFEST_FILE,
    REVIEWS_TV6_ALL_FILE,
    REVIEWS_TV6_UNUSABLE_FILE,
    REVIEWS_TV6_USABLE_FILE,
    STEP0_MANIFEST_FILE,
    TV6_CANONICAL_FIELDS,
    TV6_PIPELINE_VERSION,
)


class TestTV6AnalyticalView(unittest.TestCase):
    """Test suite verifying Step 0 analytical view integrity and data contracts."""

    @classmethod
    def setUpClass(cls):
        """Ensure Step 0 output files exist before running tests."""
        cls.all_file = REVIEWS_TV6_ALL_FILE
        cls.usable_file = REVIEWS_TV6_USABLE_FILE
        cls.unusable_file = REVIEWS_TV6_UNUSABLE_FILE
        cls.manifest_file = STEP0_MANIFEST_FILE
        cls.docs_manifest_file = DOCS_STEP0_MANIFEST_FILE

        if not cls.all_file.exists() or not cls.usable_file.exists():
            from src.review_nlp.build_view import run_build_analytical_view

            run_build_analytical_view()

    def test_file_existence(self):
        """Verify all analytical output artifacts exist."""
        self.assertTrue(self.all_file.exists(), "reviews_tv6_all.jsonl must exist")
        self.assertTrue(self.usable_file.exists(), "reviews_tv6_usable.jsonl must exist")
        self.assertTrue(self.unusable_file.exists(), "reviews_tv6_unusable.jsonl must exist")
        self.assertTrue(self.manifest_file.exists(), "view_manifest_step0.json must exist in data/tv6")
        self.assertTrue(self.docs_manifest_file.exists(), "view_manifest_step0.json must exist in docs/tv6")

    def test_record_counts_conservation(self):
        """Verify zero data loss: total_reviews == usable_reviews + unusable_reviews."""
        with self.all_file.open("r", encoding="utf-8") as f:
            total_count = sum(1 for line in f if line.strip())

        with self.usable_file.open("r", encoding="utf-8") as f:
            usable_count = sum(1 for line in f if line.strip())

        with self.unusable_file.open("r", encoding="utf-8") as f:
            unusable_count = sum(1 for line in f if line.strip())

        self.assertEqual(total_count, 15805, "Total reviews must equal Gold v2 count (15,805)")
        self.assertEqual(usable_count, 14869, "Usable reviews count must equal 14,869")
        self.assertEqual(unusable_count, 936, "Unusable reviews count must equal 936")
        self.assertEqual(total_count, usable_count + unusable_count, "Conservation law must hold")

    def test_schema_conformance(self):
        """Verify every record contains all required canonical fields."""
        expected_fields = set(TV6_CANONICAL_FIELDS)

        # Check sample of records
        with self.all_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx > 200:  # Sample 200 lines
                    break
                rec = json.loads(line)
                rec_fields = set(rec.keys())
                self.assertTrue(
                    expected_fields.issubset(rec_fields),
                    f"Line {idx} missing fields: {expected_fields - rec_fields}",
                )

    def test_usable_reviews_data_validity(self):
        """Verify that usable reviews strictly satisfy NLP preconditions."""
        with self.usable_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                rec = json.loads(line)
                self.assertTrue(rec["review_usable"], "review_usable must be True")
                text = rec.get("review_text_normalized")
                self.assertIsNotNone(text, "Text must not be None")
                self.assertGreater(len(text.strip()), 0, "Text must not be whitespace")
                self.assertIn(rec["rating_raw"], [1, 2, 3, 4, 5], "Rating must be 1-5")
                self.assertIsNotNone(rec["product_name"], "Product name should be enriched")
                self.assertEqual(rec["tv6_pipeline_version"], TV6_PIPELINE_VERSION)

    def test_unusable_reviews_isolation(self):
        """Verify unusable reviews are appropriately flagged."""
        with self.unusable_file.open("r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.assertFalse(rec["review_usable"], "review_usable must be False")
                self.assertIn(rec["review_text_status"], ["NULL", "EMPTY_OR_WHITESPACE"])

    def test_manifest_integrity(self):
        """Verify manifest content matches actual dataset metrics."""
        with self.manifest_file.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest["pipeline_version"], TV6_PIPELINE_VERSION)
        self.assertEqual(manifest["summary"]["total_input_reviews"], 15805)
        self.assertEqual(manifest["summary"]["usable_nlp_reviews"], 14869)
        self.assertEqual(manifest["summary"]["unusable_reviews"], 936)
        self.assertIn("cellphones", manifest["breakdown_by_source"])
        self.assertIn("characters", manifest["text_length_distribution"])
        self.assertIn("words", manifest["text_length_distribution"])


if __name__ == "__main__":
    unittest.main()
