"""
TV1 - Multi-Source Crawler Routing & Isolation Test Suite.
Kiểm tra tính độc lập nguồn, định tuyến spider chính xác, runner registry,
và cơ chế bảo vệ source chưa implement (Viettel Store, Hoàng Hà Mobile).

Tuyệt đối KHÔNG gọi mạng, KHÔNG spawn Scrapy thật, KHÔNG ghi vào data/raw.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

from crawler.run_crawler import (
    SOURCE_REGISTRY,
    build_argument_parser,
    crawl_category,
    get_review_snapshot_path,
    get_snapshot_path,
    main,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_fake_proc(returncode: int = 0):
    proc = MagicMock()
    proc.pid = 99999
    proc.poll.return_value = returncode
    proc.wait.return_value = returncode
    proc.kill = MagicMock()
    return proc


class TestRunCrawlerRouting(unittest.TestCase):
    """Bộ test định tuyến và cách ly source trong crawler runner."""

    # -----------------------------------------------------------------------
    # 1. SOURCE REGISTRY INTEGRITY
    # -----------------------------------------------------------------------
    def test_source_registry_structure_and_sources(self):
        """Kiểm tra SOURCE_REGISTRY chứa đúng các source hiện tại và tương lai."""
        expected_sources = {"tgdd", "fptshop", "cellphones", "viettelstore", "hoanghamobile"}
        self.assertEqual(set(SOURCE_REGISTRY.keys()), expected_sources)

        # Implemented sources
        self.assertTrue(SOURCE_REGISTRY["tgdd"]["implemented"])
        self.assertTrue(SOURCE_REGISTRY["fptshop"]["implemented"])
        self.assertTrue(SOURCE_REGISTRY["cellphones"]["implemented"])

        # Future/planned sources
        self.assertFalse(SOURCE_REGISTRY["viettelstore"]["implemented"])
        self.assertFalse(SOURCE_REGISTRY["hoanghamobile"]["implemented"])

        # Spider files của implemented sources phải tồn tại trên đĩa
        for src in ("tgdd", "fptshop", "cellphones"):
            spiders = SOURCE_REGISTRY[src]["spiders"]
            self.assertIn("laptop", spiders)
            self.assertIn("smartphone", spiders)
            self.assertTrue(spiders["laptop"].exists(), f"Thiếu file spider laptop của {src}")
            self.assertTrue(spiders["smartphone"].exists(), f"Thiếu file spider smartphone của {src}")

    # -----------------------------------------------------------------------
    # 2. OUTPUT SNAPSHOT PATH SOURCE ISOLATION
    # -----------------------------------------------------------------------
    def test_snapshot_path_source_isolation(self):
        """Kiểm tra đường dẫn raw snapshot được phân định rõ ràng theo source."""
        p_tgdd = get_snapshot_path("laptop", "20261016_000000", source="tgdd")
        p_fpt = get_snapshot_path("laptop", "20261016_000000", source="fptshop")
        p_cps = get_snapshot_path("laptop", "20261016_000000", source="cellphones")

        self.assertIn("tgdd", str(p_tgdd).lower())
        self.assertIn("fptshop", str(p_fpt).lower())
        self.assertIn("cellphones", str(p_cps).lower())

        # Review paths
        r_tgdd = get_review_snapshot_path("smartphone", "20261016_000000", source="tgdd")
        r_fpt = get_review_snapshot_path("smartphone", "20261016_000000", source="fptshop")
        r_cps = get_review_snapshot_path("smartphone", "20261016_000000", source="cellphones")

        self.assertIn("tgdd", str(r_tgdd).lower())
        self.assertIn("fptshop", str(r_fpt).lower())
        self.assertIn("cellphones", str(r_cps).lower())

    # -----------------------------------------------------------------------
    # 3. DIRECT CRAWL_CATEGORY ROUTING
    # -----------------------------------------------------------------------
    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_cellphones_laptop_routes_to_cellphones_spider(self, mock_popen):
        """crawl_category source='cellphones', category='laptop' chỉ gọi cellphones_laptop_spider."""
        mock_popen.return_value = _make_fake_proc(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            crawl_category(category="laptop", source="cellphones", output_file=str(out))

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            self.assertIn("cellphones_laptop_spider.py", " ".join(cmd))
            self.assertNotIn("tgdd", " ".join(cmd).lower())
            self.assertNotIn("fptshop", " ".join(cmd).lower())

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_cellphones_smartphone_routes_to_cellphones_spider(self, mock_popen):
        """crawl_category source='cellphones', category='smartphone' chỉ gọi cellphones_smartphone_spider."""
        mock_popen.return_value = _make_fake_proc(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            crawl_category(category="smartphone", source="cellphones", output_file=str(out))

            self.assertTrue(mock_popen.called)
            cmd = mock_popen.call_args[0][0]
            self.assertIn("cellphones_smartphone_spider.py", " ".join(cmd))
            self.assertNotIn("tgdd", " ".join(cmd).lower())
            self.assertNotIn("fptshop", " ".join(cmd).lower())

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_tgdd_routes_only_to_tgdd(self, mock_popen):
        """crawl_category source='tgdd' chỉ gọi tgdd spider, không đụng đến FPTShop hay CellphoneS."""
        mock_popen.return_value = _make_fake_proc(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            crawl_category(category="laptop", source="tgdd", output_file=str(out))

            cmd = mock_popen.call_args[0][0]
            self.assertIn("tgdd_laptop_spider.py", " ".join(cmd))
            self.assertNotIn("fptshop", " ".join(cmd).lower())
            self.assertNotIn("cellphone", " ".join(cmd).lower())

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_fptshop_routes_only_to_fptshop(self, mock_popen):
        """crawl_category source='fptshop' chỉ gọi fptshop spider, không đụng đến TGDĐ hay CellphoneS."""
        mock_popen.return_value = _make_fake_proc(0)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            crawl_category(category="smartphone", source="fptshop", output_file=str(out))

            cmd = mock_popen.call_args[0][0]
            self.assertIn("fptshop_smartphone_spider.py", " ".join(cmd))
            self.assertNotIn("tgdd", " ".join(cmd).lower())
            self.assertNotIn("cellphone", " ".join(cmd).lower())

    # -----------------------------------------------------------------------
    # 4. FUTURE SOURCES: NO FALLBACK, EXPLICIT NOT IMPLEMENTED
    # -----------------------------------------------------------------------
    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_viettelstore_raises_not_implemented(self, mock_popen):
        """Source 'viettelstore' chưa implement crawler -> raise NotImplementedError, KHÔNG fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            with self.assertRaises(NotImplementedError) as ctx:
                crawl_category(category="laptop", source="viettelstore", output_file=str(out))
            self.assertIn("Viettel Store", str(ctx.exception))
            self.assertIn("chưa được implement", str(ctx.exception))
            mock_popen.assert_not_called()

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_hoanghamobile_raises_not_implemented(self, mock_popen):
        """Source 'hoanghamobile' chưa implement crawler -> raise NotImplementedError, KHÔNG fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            with self.assertRaises(NotImplementedError) as ctx:
                crawl_category(category="smartphone", source="hoanghamobile", output_file=str(out))
            self.assertIn("Hoàng Hà Mobile", str(ctx.exception))
            self.assertIn("chưa được implement", str(ctx.exception))
            mock_popen.assert_not_called()

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_unsupported_source_raises_value_error(self, mock_popen):
        """Source không tồn tại -> raise ValueError, không fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            with self.assertRaises(ValueError):
                crawl_category(category="laptop", source="tiki", output_file=str(out))
            mock_popen.assert_not_called()

    @mock.patch("crawler.run_crawler.subprocess.Popen")
    def test_crawl_category_unsupported_category_raises_value_error(self, mock_popen):
        """Category không hỗ trợ -> raise ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.jsonl"
            with self.assertRaises(ValueError):
                crawl_category(category="tablet", source="cellphones", output_file=str(out))
            mock_popen.assert_not_called()

    # -----------------------------------------------------------------------
    # 5. CLI MAIN ROUTING & ISOLATION
    # -----------------------------------------------------------------------
    def test_cli_main_cellphones_source_isolation(self):
        """main() với --source cellphones chỉ chạy cellphones."""
        test_argv = ["run_crawler.py", "--source", "cellphones", "--category", "all", "--limit", "10"]
        called_sources = []

        def fake_crawl(cat, limit=None, output_file=None, batch_id=None, source="tgdd", run_lock=None):
            called_sources.append(source)
            return 1

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.crawl_category", side_effect=fake_crawl), \
             mock.patch("crawler.run_crawler.RunnerLock"), \
             redirect_stdout(io.StringIO()):
            main()

        self.assertEqual(called_sources, ["cellphones", "cellphones"])
        self.assertNotIn("tgdd", called_sources)
        self.assertNotIn("fptshop", called_sources)

    def test_cli_main_tgdd_source_isolation(self):
        """main() với --source tgdd chỉ chạy tgdd."""
        test_argv = ["run_crawler.py", "--source", "tgdd", "--category", "laptop", "--limit", "10"]
        called_sources = []

        def fake_crawl(cat, limit=None, output_file=None, batch_id=None, source="tgdd", run_lock=None):
            called_sources.append(source)
            return 1

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.crawl_category", side_effect=fake_crawl), \
             mock.patch("crawler.run_crawler.RunnerLock"), \
             redirect_stdout(io.StringIO()):
            main()

        self.assertEqual(called_sources, ["tgdd"])

    def test_cli_main_fptshop_source_isolation(self):
        """main() với --source fptshop chỉ chạy fptshop."""
        test_argv = ["run_crawler.py", "--source", "fptshop", "--category", "smartphone", "--limit", "10"]
        called_sources = []

        def fake_crawl(cat, limit=None, output_file=None, batch_id=None, source="tgdd", run_lock=None):
            called_sources.append(source)
            return 1

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.crawl_category", side_effect=fake_crawl), \
             mock.patch("crawler.run_crawler.RunnerLock"), \
             redirect_stdout(io.StringIO()):
            main()

        self.assertEqual(called_sources, ["fptshop"])

    def test_cli_main_source_all_runs_only_implemented_sources(self):
        """main() với --source all chỉ chạy tgdd, fptshop, cellphones (KHÔNG chạy viettelstore / hoanghamobile)."""
        test_argv = ["run_crawler.py", "--source", "all", "--category", "laptop", "--limit", "10"]
        called_sources = []

        def fake_crawl(cat, limit=None, output_file=None, batch_id=None, source="tgdd", run_lock=None):
            called_sources.append(source)
            return 1

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.crawl_category", side_effect=fake_crawl), \
             mock.patch("crawler.run_crawler.RunnerLock"), \
             redirect_stdout(io.StringIO()):
            main()

        self.assertEqual(called_sources, ["tgdd", "fptshop", "cellphones"])
        self.assertNotIn("viettelstore", called_sources)
        self.assertNotIn("hoanghamobile", called_sources)

    def test_cli_main_viettelstore_rejected_cleanly(self):
        """main() với --source viettelstore báo lỗi chưa implement và exit(1), không spawn Scrapy."""
        test_argv = ["run_crawler.py", "--source", "viettelstore", "--category", "laptop"]

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.subprocess.Popen") as mock_popen, \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)
            mock_popen.assert_not_called()

    def test_cli_main_hoanghamobile_rejected_cleanly(self):
        """main() với --source hoanghamobile báo lỗi chưa implement và exit(1), không spawn Scrapy."""
        test_argv = ["run_crawler.py", "--source", "hoanghamobile", "--category", "smartphone"]

        with mock.patch("sys.argv", test_argv), \
             mock.patch("crawler.run_crawler.subprocess.Popen") as mock_popen, \
             redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 1)
            mock_popen.assert_not_called()

    def test_cli_output_restricted_to_single_source_and_category(self):
        """--output chỉ được phép khi crawl 1 source và 1 category cụ thể."""
        parser = build_argument_parser()

        # 1 source + 1 category: hợp lệ
        args1 = parser.parse_args(["--source", "cellphones", "--category", "laptop", "--output", "out.jsonl"])
        self.assertEqual(args1.output, "out.jsonl")

        # --category all + --output: bị reject trong main
        test_argv_cat_all = ["run_crawler.py", "--source", "cellphones", "--category", "all", "--output", "out.jsonl"]
        with mock.patch("sys.argv", test_argv_cat_all), \
             self.assertRaises(SystemExit):
            main()

        # --source all + --output: bị reject trong main
        test_argv_src_all = ["run_crawler.py", "--source", "all", "--category", "laptop", "--output", "out.jsonl"]
        with mock.patch("sys.argv", test_argv_src_all), \
             self.assertRaises(SystemExit):
            main()


if __name__ == "__main__":
    unittest.main()
