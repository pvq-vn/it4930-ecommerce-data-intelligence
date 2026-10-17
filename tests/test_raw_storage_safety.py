"""
Regression test suite ensuring that:
1. No import of crawler modules creates files or directories in data/raw.
2. No runner or test path logic generates or writes fixed 'pilot.jsonl'.
3. 'data/raw' is strictly protected from test-generated files.
4. Git index does not track any 'pilot.jsonl' file.
"""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"


class TestRawStorageSafety(unittest.TestCase):
    """Kiểm tra an toàn cho thư mục data/raw/ và ngăn chặn regression pilot.jsonl."""

    def test_pilot_jsonl_does_not_exist_in_data_raw(self):
        """Khẳng định không tồn tại bất kỳ file pilot.jsonl nào trong data/raw/."""
        pilot_files = list(RAW_DIR.rglob("*pilot*.jsonl"))
        self.assertEqual(
            pilot_files,
            [],
            f"Phát hiện file pilot.jsonl tồn tại trong data/raw/: {pilot_files}. "
            "File này không được phép tồn tại hoặc tự động phục hồi.",
        )

    def test_git_does_not_track_pilot_jsonl(self):
        """Khẳng định Git index không còn track bất kỳ file pilot.jsonl nào."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "data/raw"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            tracked_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            tracked_pilot = [f for f in tracked_files if "pilot" in f.lower()]
            self.assertEqual(
                tracked_pilot,
                [],
                f"Git index vẫn đang track file pilot: {tracked_pilot}. "
                "Cần chạy 'git rm' để xóa khỏi index, tránh git checkout/restore tự phục hồi file.",
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            self.skipTest("Git command không khả dụng trong môi trường này.")

    def test_import_crawler_modules_does_not_touch_data_raw(self):
        """Khẳng định việc import tất cả crawler modules KHÔNG tạo bất kỳ file nào trong data/raw/."""
        files_before = set(RAW_DIR.rglob("*")) if RAW_DIR.exists() else set()

        modules_to_import = [
            "crawler.run_crawler",
            "crawler.tgdd",
            "crawler.tgdd.base_spider",
            "crawler.tgdd.tgdd_laptop_spider",
            "crawler.tgdd.tgdd_smartphone_spider",
            "crawler.tgdd.pipelines",
            "crawler.fptshop",
            "crawler.fptshop.base_spider",
            "crawler.fptshop.fptshop_laptop_spider",
            "crawler.fptshop.fptshop_smartphone_spider",
            "crawler.fptshop.pipelines",
            "crawler.cellphoneS",
            "crawler.cellphoneS.base_spider",
            "crawler.cellphoneS.cellphones_laptop_spider",
            "crawler.cellphoneS.cellphones_smartphone_spider",
            "crawler.cellphoneS.pipelines",
            "crawler.viettelStore",
            "crawler.viettelStore.base_spider",
            "crawler.viettelStore.viettelstore_laptop_spider",
            "crawler.viettelStore.viettelstore_smartphone_spider",
            "crawler.viettelStore.pipelines",
            "crawler.hoanghamobile",
            "crawler.hoanghamobile.base_spider",
            "crawler.hoanghamobile.hoanghamobile_laptop_spider",
            "crawler.hoanghamobile.hoanghamobile_smartphone_spider",
            "crawler.hoanghamobile.pipelines",
        ]

        for mod_name in modules_to_import:
            with self.subTest(module=mod_name):
                mod = importlib.import_module(mod_name)
                self.assertIsNotNone(mod)

        files_after = set(RAW_DIR.rglob("*")) if RAW_DIR.exists() else set()
        new_files = files_after - files_before
        self.assertEqual(
            new_files,
            set(),
            f"Import modules đã tạo file/thư mục mới trong data/raw: {new_files}",
        )

    def test_runner_snapshot_path_is_batch_timestamp_never_pilot(self):
        """Khẳng định hàm get_snapshot_path và get_review_snapshot_path luôn dùng batch_id, không bao giờ dùng 'pilot'."""
        from crawler.run_crawler import (
            get_snapshot_path,
            get_review_snapshot_path,
            SOURCE_REGISTRY,
        )

        dummy_batch = "20261017_999999"
        for source in SOURCE_REGISTRY:
            for category in ["laptop", "smartphone"]:
                prod_path = get_snapshot_path(category, dummy_batch, source=source)
                rev_path = get_review_snapshot_path(category, dummy_batch, source=source)

                self.assertNotIn(
                    "pilot",
                    prod_path.name.lower(),
                    f"Product snapshot path không được chứa 'pilot': {prod_path}",
                )
                self.assertEqual(
                    prod_path.name,
                    f"{dummy_batch}.jsonl",
                    f"Product snapshot filename phải là {dummy_batch}.jsonl, nhận được: {prod_path.name}",
                )

                self.assertNotIn(
                    "pilot",
                    rev_path.name.lower(),
                    f"Review snapshot path không được chứa 'pilot': {rev_path}",
                )
                self.assertEqual(
                    rev_path.name,
                    f"{dummy_batch}.jsonl",
                    f"Review snapshot filename phải là {dummy_batch}.jsonl, nhận được: {rev_path.name}",
                )

    def test_pipelines_isolate_output_in_temp_directory(self):
        """Khẳng định mọi pipeline (TGDĐ, FPTShop, CellphoneS, Viettel Store, Hoàng Hà Mobile) ghi đúng temp directory khi được cấu hình."""
        from crawler.tgdd.pipelines import TgddReviewExportPipeline
        from crawler.fptshop.pipelines import FptshopReviewExportPipeline
        from crawler.cellphoneS.pipelines import CellphonesReviewExportPipeline
        from crawler.viettelStore.pipelines import ViettelstoreReviewExportPipeline
        from crawler.hoanghamobile.pipelines import HoanghamobileReviewExportPipeline

        pipelines = [
            ("tgdd", TgddReviewExportPipeline),
            ("fptshop", FptshopReviewExportPipeline),
            ("cellphones", CellphonesReviewExportPipeline),
            ("viettelstore", ViettelstoreReviewExportPipeline),
            ("hoanghamobile", HoanghamobileReviewExportPipeline),
        ]

        class DummySpider:
            def __init__(self, review_output_path):
                self.review_output = str(review_output_path)
                self.category = "smartphone"
                self.batch_id = "test_batch"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            files_before = set(RAW_DIR.rglob("*")) if RAW_DIR.exists() else set()

            for name, pipe_cls in pipelines:
                with self.subTest(pipeline=name):
                    target_file = tmppath / f"{name}_review.jsonl"
                    pipe = pipe_cls()
                    spider = DummySpider(target_file)
                    pipe.open_spider(spider)
                    self.assertIsNotNone(pipe.file)
                    self.assertEqual(pipe.review_output_path, target_file)
                    pipe.close_spider(spider)
                    self.assertTrue(target_file.exists())

            files_after = set(RAW_DIR.rglob("*")) if RAW_DIR.exists() else set()
            new_files = files_after - files_before
            self.assertEqual(
                new_files,
                set(),
                f"Pipeline execution in test created files in data/raw: {new_files}",
            )


if __name__ == "__main__":
    unittest.main()
