"""Unit tests for Step 2 Vietnamese Text Preprocessing & Tokenization."""

import json
from pathlib import Path
import unittest

from src.review_nlp.config import (
    DOCS_PREPROCESSING_REPORT_FILE,
    FIGURES_TV6_DIR,
    PREPROCESSING_REPORT_FILE,
    REVIEWS_TV6_PREPROCESSED_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)
from src.review_nlp.vietnamese_nlp_utils import preprocess_text


class TestTV6Preprocessing(unittest.TestCase):
    """Test suite verifying Step 2 text normalization, tokenization, and schema integrity."""

    @classmethod
    def setUpClass(cls):
        """Ensure Step 2 output artifacts exist."""
        cls.preprocessed_file = REVIEWS_TV6_PREPROCESSED_FILE
        cls.report_file = PREPROCESSING_REPORT_FILE
        cls.docs_report_file = DOCS_PREPROCESSING_REPORT_FILE
        cls.tables_dir = TABLES_TV6_DIR
        cls.figures_dir = FIGURES_TV6_DIR

        if not cls.preprocessed_file.exists():
            from src.review_nlp.preprocess import run_text_preprocessing

            run_text_preprocessing()

    def test_output_file_existence(self):
        """Verify preprocessed file and reports exist."""
        self.assertTrue(self.preprocessed_file.exists(), "preprocessed JSONL file must exist")
        self.assertTrue(self.report_file.exists(), "preprocessing_report.json must exist in data/tv6")
        self.assertTrue(self.docs_report_file.exists(), "preprocessing_report.json must exist in docs/tv6")

    def test_record_count_preservation(self):
        """Verify exactly 14,869 usable reviews are preprocessed with 0 loss."""
        with self.preprocessed_file.open("r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        self.assertEqual(count, 14869, "Must retain exactly 14,869 preprocessed reviews")

    def test_schema_and_token_count_validity(self):
        """Verify each record contains preprocessed fields and positive token count."""
        expected_fields = {
            "text_cleaned",
            "text_tokenized",
            "text_stopwords_removed",
            "tokens_list",
            "token_count",
            "step2_version",
        }
        with self.preprocessed_file.open("r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                if idx > 300:  # Sample 300 records
                    break
                rec = json.loads(line)
                self.assertTrue(expected_fields.issubset(set(rec.keys())))
                self.assertGreater(rec["token_count"], 0, f"Line {idx} token_count must be > 0")
                self.assertEqual(len(rec["tokens_list"]), rec["token_count"])
                self.assertEqual(rec["step2_version"], TV6_PIPELINE_VERSION)

    def test_teencode_expansion(self):
        """Verify teencode tokens are accurately expanded."""
        sample = "đt dùng ok ko shop ơi"
        res = preprocess_text(sample)
        tokens = res["tokens_list"]
        self.assertIn("điện_thoại", tokens, "'đt' must expand to 'điện_thoại'")
        self.assertIn("không", tokens, "'ko' must expand to 'không'")
        self.assertIn("shop", tokens, "'shop' must be preserved as natural e-commerce term")

    def test_contextual_disambiguation(self):
        """Verify polysemous tokens like 'bh', 'cam', 'kg', 'kh', 'cn', 'mh', 'sd', 'bt', 'kb' are disambiguated."""
        # 1. 'bh' as 'bao giờ' vs 'bảo hành' vs 'bây giờ'
        r1 = preprocess_text("Shop ơi bh hàng về")
        self.assertIn("bao_giờ", r1["tokens_list"], "'bh hàng về' must resolve to 'bao_giờ'")

        r2 = preprocess_text("máy hết BH rồi có được hỗ trợ ko")
        self.assertIn("bảo_hành", r2["tokens_list"], "'hết BH' must resolve to 'bảo_hành'")

        r3 = preprocess_text("Hiện tại bh mình mới dùng thử")
        self.assertIn("bây_giờ", r3["tokens_list"], "'hiện tại bh' must resolve to 'bây_giờ'")

        # 2. 'kg' as mass vs negation
        r_mass = preprocess_text("Laptop mỏng nhẹ 1.6 kg mang đi tiện")
        self.assertTrue(any("kilogram" in t for t in r_mass["tokens_list"]), "'1.6 kg' must preserve kilogram spec")
        r_neg_kg = preprocess_text("Máy kg bị quá nóng")
        self.assertIn("không", r_neg_kg["tokens_list"], "Standalone 'kg' before verb must resolve to 'không'")

        # 3. 'kh' as khách_hàng vs không
        r_kh_cust = preprocess_text("Tư vấn đúng nhu cầu của KH")
        self.assertIn("khách_hàng", r_kh_cust["tokens_list"], "'nhu cầu của KH' must resolve to 'khách_hàng'")
        r_kh_neg = preprocess_text("Máy kh lên nguồn")
        self.assertIn("không", r_kh_neg["tokens_list"], "'kh lên' must resolve to 'không'")

        # 4. 'cn' as chủ nhật vs chi nhánh
        r_cn_sun = preprocess_text("Giao hàng trừ CN")
        self.assertIn("chủ_nhật", r_cn_sun["tokens_list"], "'trừ CN' must resolve to 'chủ_nhật'")
        r_cn_branch = preprocess_text("Mua ở CN Bình Tân")
        self.assertIn("chi_nhánh", r_cn_branch["tokens_list"], "'CN Bình Tân' must resolve to 'chi_nhánh'")

        # 5. 'mh' as màn hình vs mình
        r_mh_screen = preprocess_text("Phải tắt mh mở lại")
        self.assertTrue(any("màn_hình" in t for t in r_mh_screen["tokens_list"]), "'tắt mh' must resolve to 'màn_hình'")
        r_mh_me = preprocess_text("Huỷ giúp mh đơn hàng")
        self.assertIn("mình", r_mh_me["tokens_list"], "'giúp mh' must resolve to 'mình'")

        # 6. 'sd' as thẻ SD vs sử dụng
        r_sd_card = preprocess_text("Dùng thẻ sd 128gb")
        self.assertIn("thẻ_sd", r_sd_card["tokens_list"], "'thẻ sd' must resolve to 'thẻ_sd'")
        r_sd_use = preprocess_text("Máy rất dể sd")
        self.assertIn("sử_dụng", r_sd_use["tokens_list"], "'dể sd' must resolve to 'sử_dụng'")

        # 7. 'bt' as biết vs bình thường
        r_bt_know = preprocess_text("Chưa bt chất lượng thế nào")
        self.assertIn("biết", r_bt_know["tokens_list"], "'chưa bt' must resolve to 'biết'")
        r_bt_norm = preprocess_text("Máy dùng bt rất ổn")
        self.assertIn("bình_thường", r_bt_norm["tokens_list"], "'dùng bt' must resolve to 'bình_thường'")

        # 8. 'kb' as kilobyte vs không biết
        r_kb_byte = preprocess_text("Dung lượng vài chục kb")
        self.assertTrue(any("kilobyte" in t for t in r_kb_byte["tokens_list"]), "'chục kb' must resolve to 'kilobyte'")
        r_kb_dontknow = preprocess_text("Kb shop còn hàng ko")
        self.assertIn("không_biết", r_kb_dontknow["tokens_list"], "'kb' at start must resolve to 'không_biết'")

        # 9. Hardware specs preserved (no accidental 'anh' or 'chị')
        s_hw = "CPU dưới 80 độ C, cổng Type C và mặt A nhôm"
        r_hw = preprocess_text(s_hw)
        self.assertNotIn("chị", r_hw["tokens_list"], "'độ C' or 'Type C' must not convert to 'chị'")
        self.assertNotIn("anh", r_hw["tokens_list"], "'mặt A' must not convert to 'anh'")

        # 10. Tech compounds preserved
        s_comp = "Máy bị hở sáng và sọc màn, pin trâu sập nguồn"
        r_comp = preprocess_text(s_comp)
        self.assertIn("hở_sáng", r_comp["tokens_list"])
        self.assertIn("sọc_màn", r_comp["tokens_list"])
        self.assertIn("pin_trâu", r_comp["tokens_list"])
        self.assertIn("sập_nguồn", r_comp["tokens_list"])

    def test_negation_preservation(self):
        """Verify critical negation words are NEVER stripped as stopwords."""
        sample = "máy không tốt, chẳng mượt tí nào"
        res = preprocess_text(sample)
        tokens = res["tokens_list"]
        self.assertIn("không", tokens, "Negation 'không' must be preserved")
        self.assertIn("chẳng", tokens, "Negation 'chẳng' must be preserved")
        self.assertIn("tốt", tokens, "Adjective 'tốt' must be preserved")

    def test_emoji_mapping(self):
        """Verify sentiment emojis are converted into structured tokens."""
        sample = "rất hài lòng 👍👍 nhưng sạc hơi chậm 👎"
        res = preprocess_text(sample)
        cleaned = res["text_cleaned"]
        self.assertIn("pos_emoji", cleaned, "Positive emoji must be mapped to pos_emoji")
        self.assertIn("neg_emoji", cleaned, "Negative emoji must be mapped to neg_emoji")

    def test_tables_and_figures_generated(self):
        """Verify all Step 2 tables and figures exist."""
        expected_tables = [
            "table_2_1_preprocessing_pipeline_stages",
            "table_2_2_teencode_dictionary",
            "table_2_3_token_frequency_top50",
        ]
        for base in expected_tables:
            csv_f = self.tables_dir / f"{base}.csv"
            md_f = self.tables_dir / f"{base}.md"
            self.assertTrue(csv_f.exists(), f"Missing table CSV: {csv_f}")
            self.assertTrue(md_f.exists(), f"Missing table MD: {md_f}")

        fig_f = self.figures_dir / "fig_2_1_top_tokens_frequency.png"
        self.assertTrue(fig_f.exists(), f"Missing figure: {fig_f}")
        self.assertGreater(fig_f.stat().st_size, 20_000, f"Figure too small: {fig_f}")


if __name__ == "__main__":
    unittest.main()
