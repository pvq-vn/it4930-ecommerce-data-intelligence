import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import scrapy
from scrapy.dupefilters import RFPDupeFilter
from scrapy.http import HtmlResponse, TextResponse

from crawler.run_crawler import generate_batch_id, get_snapshot_path, get_review_snapshot_path
from crawler.tgdd.base_spider import TgddBaseSpider
from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem
from crawler.tgdd.pipelines import TgddReviewExportPipeline
from crawler.tgdd.tgdd_laptop_spider import TgddLaptopSpider
from crawler.tgdd.tgdd_smartphone_spider import TgddSmartphoneSpider
from scrapy.exceptions import DropItem

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestTgddCrawler(unittest.TestCase):
    def setUp(self):
        self.spider = TgddBaseSpider(max_products=10)

    def test_item_fields_exist(self):
        """Kiểm tra schema TechProductRawItem có đầy đủ các trường TV1 yêu cầu."""
        expected_fields = [
            "source",
            "category",
            "crawl_batch",
            "crawl_time",
            "product_id_raw",
            "product_url_raw",
            "product_name_raw",
            "parent_product_id_raw",
            "parent_product_name_raw",
            "parent_url_raw",
            "variant_name_raw",
            "variant_color_raw",
            "variant_url_raw",
            "variant_sku_raw",
            "availability_raw",
            "price_raw",
            "original_price_raw",
            "seller_raw",
            "rating_raw",
            "review_count_raw",
            "attributes_raw",
            "brand_raw",
            "total_sold_raw",
            "sku_raw",
            "raw_payload",
        ]
        item = TechProductRawItem()
        for field in expected_fields:
            self.assertIn(field, item.fields)

    def test_extract_listing_item_preserves_raw_data(self):
        """Kiểm tra trích xuất dữ liệu listing bảo toàn giá trị gốc (số nguyên, không chuẩn hóa chuỗi)."""
        mock_product = {
            "id": "193688",
            "name": "HP Gaming VICTUS 15 fa2731TX i5 13420H (B85LNPA)",
            "url": "laptop/hp-victus-15-fa2731tx-i5-b85lnpa",
            "productPrices": [
                {
                    "price": 27990000,
                    "sysPrice": 32490000,
                }
            ],
            "rate": 4.9,
            "totalRate": 703,
            "brand": {"brandName": "Hp"},
            "totalSold": "Đã bán 702",
            "productNameSKU": "Laptop HP Gaming VICTUS 15 fa2731TX - B85LNPA",
        }

        item = self.spider.extract_listing_item(mock_product)

        self.assertEqual(item["source"], "tgdd")
        self.assertEqual(item["product_id_raw"], "193688")
        self.assertEqual(item["product_name_raw"], "HP Gaming VICTUS 15 fa2731TX i5 13420H (B85LNPA)")
        # Kiểm tra giá phải giữ nguyên số nguyên 27990000, KHÔNG biến thành '27.99 triệu'
        self.assertEqual(item["price_raw"], 27990000)
        self.assertEqual(item["original_price_raw"], 32490000)
        self.assertEqual(item["seller_raw"], "Thế Giới Di Động")
        self.assertEqual(item["rating_raw"], 4.9)
        self.assertEqual(item["review_count_raw"], 703)
        self.assertTrue(item["product_url_raw"].startswith("https://www.thegioididong.com/laptop/"))

    def test_extract_attributes_from_ld_json(self):
        """Kiểm tra trích xuất thuộc tính kỹ thuật từ LD+JSON additionalProperty."""
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Test Laptop",
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "Loại CPU", "value": "13420H"},
                    {"@type": "PropertyValue", "name": "RAM", "value": "16 GB"},
                    {"@type": "PropertyValue", "name": "Ổ cứng", "value": "512 GB SSD"}
                ]
            }
            </script>
        </head>
        <body></body>
        </html>
        """

        attrs = self.spider.extract_attributes(mock_html)
        self.assertEqual(attrs.get("Loại CPU"), "13420H")
        self.assertEqual(attrs.get("RAM"), "16 GB")
        self.assertEqual(attrs.get("Ổ cứng"), "512 GB SSD")

    def test_extract_attributes_dom_fallback(self):
        """Kiểm tra trích xuất thuộc tính fallback từ DOM khi không có LD+JSON."""
        mock_html = """
        <html>
        <body>
            <section class="spec">
                <h2>Thông số kỹ thuật</h2>
                <div>
                    <div>Công nghệ CPU: Intel Core i5</div>
                    <div>RAM: 16 GB</div>
                </div>
            </section>
        </body>
        </html>
        """
        attrs = self.spider.extract_attributes(mock_html)
        self.assertEqual(attrs.get("Công nghệ CPU"), "Intel Core i5")
        self.assertEqual(attrs.get("RAM"), "16 GB")

    def test_spider_subclasses_configuration(self):
        """Kiểm tra config category cho Laptop và Smartphone spider."""
        laptop_spider = TgddLaptopSpider()
        self.assertEqual(laptop_spider.name, "tgdd_laptop")
        self.assertEqual(laptop_spider.category, "laptop")
        self.assertEqual(laptop_spider.url_cate, "laptop")
        self.assertEqual(laptop_spider.cate_id, "17")

        phone_spider = TgddSmartphoneSpider()
        self.assertEqual(phone_spider.name, "tgdd_smartphone")
        self.assertEqual(phone_spider.category, "smartphone")
        self.assertEqual(phone_spider.url_cate, "dtdd")
        self.assertEqual(phone_spider.cate_id, "42")

    def test_politeness_settings(self):
        """Kiểm tra cấu hình politeness tuân thủ robots.txt (ROBOTSTXT_OBEY=True, delay >= 5s)."""
        settings = self.spider.custom_settings
        self.assertTrue(settings.get("ROBOTSTXT_OBEY"), "ROBOTSTXT_OBEY phải được bật là True")
        self.assertGreaterEqual(settings.get("DOWNLOAD_DELAY", 0), 5.0, "DOWNLOAD_DELAY phải >= 5.0 giây theo Crawl-delay")
        self.assertEqual(settings.get("CONCURRENT_REQUESTS"), 1, "CONCURRENT_REQUESTS phải bằng 1 để tuần tự hóa")
        self.assertEqual(settings.get("CONCURRENT_REQUESTS_PER_DOMAIN"), 1, "CONCURRENT_REQUESTS_PER_DOMAIN phải bằng 1")
        self.assertTrue(settings.get("AUTOTHROTTLE_ENABLED"), "AUTOTHROTTLE_ENABLED phải được bật")
        self.assertGreaterEqual(settings.get("AUTOTHROTTLE_START_DELAY", 0), 5.0, "AUTOTHROTTLE_START_DELAY phải >= 5.0 giây")

    def test_pilot_snapshots_integrity_and_validity(self):
        """
        Kiểm tra tính toàn vẹn và hợp lệ của các file snapshot pilot hiện có:
        - Đúng 50 records mục tiêu.
        - Không trùng product_id_raw.
        - Không trùng product_url_raw.
        - Category, source, tên, id, url không rỗng.
        - price_raw tồn tại ở các record listing hợp lệ.
        - attributes_raw đúng kiểu dict.
        - crawl_batch và crawl_time đầy đủ.
        """
        laptop_file = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop" / "pilot.jsonl"
        phone_file = PROJECT_ROOT / "data" / "raw" / "tgdd" / "smartphone" / "pilot.jsonl"

        snapshots = [("laptop", laptop_file), ("smartphone", phone_file)]

        for category, file_path in snapshots:
            if not file_path.exists():
                continue

            records = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))

            # 1. Số lượng records đúng mục tiêu 50 đối với pilot hiện tại
            self.assertEqual(
                len(records),
                50,
                f"File {file_path.name} của {category} phải có đúng 50 records pilot.",
            )

            product_ids = [r.get("product_id_raw") for r in records]
            product_urls = [r.get("product_url_raw") for r in records]

            # 2. product_id_raw không trùng
            self.assertEqual(
                len(product_ids),
                len(set(product_ids)),
                f"Phát hiện product_id_raw trùng lặp trong snapshot {category}.",
            )

            # 3. product_url_raw không trùng
            self.assertEqual(
                len(product_urls),
                len(set(product_urls)),
                f"Phát hiện product_url_raw trùng lặp trong snapshot {category}.",
            )

            # 4. Kiểm tra từng record
            for idx, r in enumerate(records):
                self.assertEqual(r.get("source"), "tgdd", f"Record {idx} sai source")
                self.assertEqual(r.get("category"), category, f"Record {idx} sai category")

                self.assertTrue(bool(r.get("product_id_raw")), f"Record {idx} thiếu product_id_raw")
                self.assertTrue(bool(r.get("product_name_raw")), f"Record {idx} thiếu product_name_raw")
                self.assertTrue(bool(r.get("product_url_raw")), f"Record {idx} thiếu product_url_raw")

                # price_raw phải tồn tại trong record
                self.assertIn("price_raw", r, f"Record {idx} thiếu key price_raw")
                if r.get("price_raw") is not None:
                    self.assertIsInstance(
                        r["price_raw"],
                        (int, float),
                        f"Record {idx} price_raw phải giữ kiểu số gốc, không normalize",
                    )

                # attributes_raw phải là dict
                self.assertIsInstance(
                    r.get("attributes_raw"),
                    dict,
                    f"Record {idx} attributes_raw phải là dict",
                )

                # Metadata provenance
                self.assertTrue(bool(r.get("crawl_batch")), f"Record {idx} thiếu crawl_batch")
                self.assertTrue(bool(r.get("crawl_time")), f"Record {idx} thiếu crawl_time")

    def test_duplicate_request_control(self):
        """
        Kiểm tra cơ chế duplicate request control:
        - make_listing_request và detail request không bật dont_filter=True.
        - RFPDupeFilter chặn duplicate request có cùng fingerprint.
        - RFPDupeFilter không chặn các trang listing khác nhau (khác pageIndex trong body).
        """
        # 1. Listing request không có dont_filter
        req_page1 = self.spider.make_listing_request(page=1)
        self.assertFalse(
            req_page1.dont_filter,
            "make_listing_request không được đặt dont_filter=True để Scrapy dupefilter hoạt động.",
        )

        req_page2 = self.spider.make_listing_request(page=2)
        self.assertFalse(req_page2.dont_filter)

        # 2. RFPDupeFilter phân biệt được page 1 và page 2 qua body
        dupe_filter = RFPDupeFilter()
        dupe_filter.open()

        self.assertFalse(dupe_filter.request_seen(req_page1), "Request page 1 lần đầu không bị filter")
        self.assertFalse(dupe_filter.request_seen(req_page2), "Request page 2 khác body không bị filter")

        # Gửi lặp lại page 1 phải bị filter
        req_page1_dup = self.spider.make_listing_request(page=1)
        self.assertTrue(dupe_filter.request_seen(req_page1_dup), "Request page 1 trùng lặp phải bị filter")

        # 3. Detail request sinh từ parse_listing không có dont_filter
        mock_response_data = {
            "data": {
                "products": [
                    {
                        "id": "111",
                        "name": "Test Laptop A",
                        "url": "laptop/test-a",
                        "productPrices": [{"price": 10000000}],
                    }
                ]
            }
        }
        mock_req = scrapy.Request(url=self.spider.API_URL, meta={"page": 1})
        mock_response = TextResponse(
            url=self.spider.API_URL,
            body=json.dumps(mock_response_data).encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )
        yielded = list(self.spider.parse_listing(mock_response))
        detail_reqs = [
            r for r in yielded
            if isinstance(r, scrapy.Request) and r.callback == self.spider.parse_detail
        ]
        self.assertEqual(len(detail_reqs), 1)
        self.assertFalse(
            detail_reqs[0].dont_filter,
            "Detail request không được đặt dont_filter=True để tránh tải lặp trang chi tiết.",
        )

        # Kiểm tra dupe filter trên detail request
        self.assertFalse(dupe_filter.request_seen(detail_reqs[0]), "Detail request lần đầu không bị filter")
        self.assertTrue(dupe_filter.request_seen(detail_reqs[0]), "Detail request trùng URL phải bị filter")

    def test_error_observability_and_metrics(self):
        """
        Kiểm tra observability:
        - Các bộ đếm lỗi và metrics được khởi tạo đầy đủ.
        - errback_listing ghi nhận listing_failures.
        - errback_detail ghi nhận detail_failures, attribute_extraction_failures và yield fallback item.
        - Không nuốt lỗi silently khi parse script JSON-LD lỗi.
        """
        self.assertEqual(self.spider.listing_failures, 0)
        self.assertEqual(self.spider.detail_failures, 0)
        self.assertEqual(self.spider.attribute_extraction_failures, 0)
        self.assertEqual(self.spider.listing_pages_processed, 0)

        # 1. errback_listing
        mock_failure = MagicMock()
        mock_failure.request = scrapy.Request(url="https://api.thegioididong.com/test", meta={"page": 1})
        mock_failure.value = Exception("Connection timeout")
        self.spider.errback_listing(mock_failure)
        self.assertEqual(self.spider.listing_failures, 1)

        # 2. errback_detail
        test_item = TechProductRawItem()
        test_item["product_id_raw"] = "999"
        test_item["product_name_raw"] = "Fail Item"
        test_item["attributes_raw"] = {}

        mock_detail_failure = MagicMock()
        mock_detail_failure.request = scrapy.Request(
            url="https://www.thegioididong.com/fail-url",
            meta={"item": test_item},
        )
        mock_detail_failure.value = Exception("HTTP 500 Internal Server Error")

        results = list(self.spider.errback_detail(mock_detail_failure))
        self.assertEqual(self.spider.detail_failures, 1)
        self.assertEqual(self.spider.attribute_extraction_failures, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["product_id_raw"], "999")

        # 3. extract_attributes với JSON-LD malformed không gây crash và xử lý êm
        malformed_html = """
        <html><head>
        <script type="application/ld+json">{ broken json }</script>
        </head><body></body></html>
        """
        attrs = self.spider.extract_attributes(malformed_html)
        self.assertEqual(attrs, {})

        # 4. spider closed summary chạy không lỗi
        self.spider.closed("finished")

    def test_runner_batch_id_and_immutable_snapshot_path(self):
        """
        Kiểm tra runner tạo snapshot bất biến và deterministic helpers:
        - generate_batch_id tạo định dạng YYYYMMDD_HHMMSS chuẩn.
        - get_snapshot_path tạo đường dẫn riêng biệt cho các batch khác nhau.
        - File crawler/run_crawler.py không có logic unlink/xóa file cũ.
        """
        fixed_time = datetime(2026, 10, 13, 8, 15, 0)
        batch_id = generate_batch_id(fixed_time)
        self.assertEqual(batch_id, "20261013_081500")

        path1 = get_snapshot_path("laptop", "20261013_081500")
        path2 = get_snapshot_path("laptop", "20261013_081900")
        self.assertNotEqual(path1, path2, "Các batch khác nhau phải có output path khác nhau")
        self.assertTrue(str(path1).endswith("20261013_081500.jsonl"))

        # Kiểm tra file run_crawler.py không chứa mã xóa file (unlink hoặc os.remove)
        runner_source = (PROJECT_ROOT / "crawler" / "run_crawler.py").read_text(encoding="utf-8")
        self.assertNotIn(".unlink()", runner_source, "Runner không được xóa snapshot cũ")
        self.assertNotIn("os.remove(", runner_source, "Runner không được xóa snapshot cũ")

    @unittest.mock.patch("subprocess.run")
    def test_crawl_category_subprocess_and_batch_propagation(self, mock_subproc):
        """Kiểm tra crawl_category truyền đúng tham số batch_id, max_products và target output vào Scrapy."""
        from crawler.run_crawler import crawl_category

        mock_subproc.return_value = MagicMock(returncode=0)
        custom_out = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop" / "fake_test.jsonl"

        crawl_category(
            category="laptop",
            limit=5,
            output_file=str(custom_out),
            batch_id="20261013_999999",
        )

        self.assertTrue(mock_subproc.called)
        called_cmd = mock_subproc.call_args[0][0]
        self.assertIn("batch_id=20261013_999999", called_cmd)
        self.assertIn("max_products=5", called_cmd)
        self.assertIn(str(custom_out), called_cmd)

    @unittest.mock.patch("subprocess.run")
    def test_crawl_category_subprocess_failure_handling(self, mock_subproc):
        """Kiểm tra crawl_category trả về 0 và xử lý lỗi khi subprocess trả về mã thoát khác 0."""
        from crawler.run_crawler import crawl_category

        mock_subproc.return_value = MagicMock(returncode=1)
        custom_out = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop" / "fake_test.jsonl"

        count = crawl_category(
            category="laptop",
            limit=5,
            output_file=str(custom_out),
            batch_id="20261013_999999",
        )
        self.assertEqual(count, 0, "Khi subprocess lỗi, crawl_category phải trả về 0")

    def test_existing_snapshot_is_rejected(self):
        """
        Không cho phép crawl vào output snapshot đã tồn tại.
        """
        from crawler.run_crawler import ensure_output_path_available

        existing_file = (
            PROJECT_ROOT
            / "data"
            / "raw"
            / "tgdd"
            / "laptop"
            / "existing_snapshot.jsonl"
        )

        existing_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing_file.write_text("existing data\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                ensure_output_path_available(existing_file)

        finally:
            if existing_file.exists():
                existing_file.unlink()

    @unittest.mock.patch("subprocess.run")
    def test_crawl_category_rejects_existing_output(self, mock_subproc):
        """
        Nếu output đã tồn tại thì crawl_category phải dừng trước khi gọi Scrapy.
        """
        from crawler.run_crawler import crawl_category

        existing_file = (
            PROJECT_ROOT
            / "data"
            / "raw"
            / "tgdd"
            / "laptop"
            / "existing_snapshot.jsonl"
        )

        existing_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            existing_file.write_text("existing data\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                crawl_category(
                    category="laptop",
                    limit=5,
                    output_file=str(existing_file),
                    batch_id="20261013_999999",
                )

            mock_subproc.assert_not_called()

        finally:
            if existing_file.exists():
                existing_file.unlink()

    def test_spider_max_products_initialization(self):
        """
        Kiểm tra khởi tạo max_products:
        - Mặc định là 50 (pilot mode).
        - max_products=None hoặc 'none' biểu diễn unlimited (full mode).
        - max_products=100 nhận đúng số nguyên.
        """
        spider_default = TgddBaseSpider()
        self.assertEqual(spider_default.max_products, 50, "Mặc định không truyền phải là 50")

        spider_pilot = TgddBaseSpider(max_products=50)
        self.assertEqual(spider_pilot.max_products, 50)

        spider_full_none = TgddBaseSpider(max_products=None)
        self.assertIsNone(spider_full_none.max_products, "max_products=None phải là unlimited")

        spider_full_str = TgddBaseSpider(max_products="none")
        self.assertIsNone(spider_full_str.max_products, "max_products='none' phải là unlimited")

        spider_custom = TgddBaseSpider(max_products="100")
        self.assertEqual(spider_custom.max_products, 100)

    def test_full_mode_cli_parsing(self):
        """Kiểm tra xử lý đối số dòng lệnh CLI cho chế độ --full và ràng buộc mutually exclusive với --limit."""
        from crawler.run_crawler import build_argument_parser

        parser = build_argument_parser()

        # 1. Chạy với --full
        args_full = parser.parse_args(["--category", "laptop", "--full"])
        self.assertTrue(args_full.full)
        self.assertIsNone(args_full.limit)

        # 2. Chạy mặc định pilot mode (không --full, không --limit)
        args_default = parser.parse_args(["--category", "laptop"])
        self.assertFalse(args_default.full)
        self.assertIsNone(args_default.limit)
        # Kiểm tra logic xác định limit: nếu không truyền gì thì limit mặc định là 50
        effective_limit_default = None if args_default.full else (args_default.limit or 50)
        self.assertEqual(effective_limit_default, 50)

        # 3. Chạy với --limit 100
        args_limit = parser.parse_args(["--category", "laptop", "--limit", "100"])
        self.assertFalse(args_limit.full)
        self.assertEqual(args_limit.limit, 100)
        effective_limit_custom = None if args_limit.full else (args_limit.limit or 50)
        self.assertEqual(effective_limit_custom, 100)

        # 4. Truyền đồng thời --full và --limit phải bị từ chối trực tiếp bởi argparse mutually exclusive group
        with self.assertRaises(SystemExit):
            parser.parse_args(["--category", "laptop", "--full", "--limit", "50"])

        with self.assertRaises(SystemExit):
            parser.parse_args(["--category", "laptop", "--limit", "50", "--full"])

    def test_full_crawl_does_not_stop_at_50_and_continues_pagination(self):
        """Kiểm tra chế độ full crawl (max_products=None) không dừng ở 50 sản phẩm mà tiếp tục phân trang."""
        spider = TgddBaseSpider(max_products=None)

        def make_mock_response(page: int, start_idx: int, count: int):
            products = [
                {
                    "id": str(start_idx + i),
                    "name": f"Product {start_idx + i}",
                    "url": f"laptop/p-{start_idx + i}",
                    "productPrices": [{"price": 10000000}],
                }
                for i in range(count)
            ]
            body_data = {"data": {"products": products}}
            req = scrapy.Request(url=spider.API_URL, meta={"page": page})
            return TextResponse(
                url=spider.API_URL,
                body=json.dumps(body_data).encode("utf-8"),
                encoding="utf-8",
                request=req,
            )

        # Page 1: 30 sản phẩm (scheduled = 30)
        resp1 = make_mock_response(page=1, start_idx=1, count=30)
        yielded1 = list(spider.parse_listing(resp1))
        pagination_reqs1 = [r for r in yielded1 if isinstance(r, scrapy.Request) and r.callback == spider.parse_listing]
        self.assertEqual(len(pagination_reqs1), 1)
        self.assertEqual(pagination_reqs1[0].meta["page"], 2)
        self.assertEqual(spider.scheduled_products, 30)

        # Page 2: 30 sản phẩm tiếp (scheduled = 60 > 50)
        resp2 = make_mock_response(page=2, start_idx=31, count=30)
        yielded2 = list(spider.parse_listing(resp2))
        pagination_reqs2 = [r for r in yielded2 if isinstance(r, scrapy.Request) and r.callback == spider.parse_listing]
        self.assertEqual(len(pagination_reqs2), 1)
        self.assertEqual(pagination_reqs2[0].meta["page"], 3)
        self.assertEqual(spider.scheduled_products, 60, "Full crawl phải vượt qua mốc 50 sản phẩm")

    def test_pagination_stops_when_products_empty(self):
        """Kiểm tra crawler dừng pagination khi API trả về danh sách sản phẩm rỗng."""
        spider = TgddBaseSpider(max_products=None)

        body_data = {"data": {"products": []}}
        req = scrapy.Request(url=spider.API_URL, meta={"page": 5})
        resp = TextResponse(
            url=spider.API_URL,
            body=json.dumps(body_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        yielded = list(spider.parse_listing(resp))
        self.assertEqual(len(yielded), 0, "Không còn sản phẩm thì không yield thêm item hay request nào")
        self.assertEqual(spider.stop_reason, "no_more_products")

    def test_repeated_page_signature_guard(self):
        """Kiểm tra pagination guard phát hiện page signature trùng lặp và dừng crawler an toàn."""
        spider = TgddBaseSpider(max_products=None)

        products = [
            {
                "id": "item-101",
                "name": "Repeat Product",
                "url": "laptop/repeat-101",
                "productPrices": [{"price": 15000000}],
            }
        ]
        body_data = {"data": {"products": products}}

        # Page 1 nhận sản phẩm bình thường
        req1 = scrapy.Request(url=spider.API_URL, meta={"page": 1})
        resp1 = TextResponse(
            url=spider.API_URL,
            body=json.dumps(body_data).encode("utf-8"),
            encoding="utf-8",
            request=req1,
        )
        yielded1 = list(spider.parse_listing(resp1))
        self.assertGreater(len(yielded1), 0)

        # Page 2 nhận lại y nguyên danh sách sản phẩm của Page 1
        req2 = scrapy.Request(url=spider.API_URL, meta={"page": 2})
        resp2 = TextResponse(
            url=spider.API_URL,
            body=json.dumps(body_data).encode("utf-8"),
            encoding="utf-8",
            request=req2,
        )
        yielded2 = list(spider.parse_listing(resp2))
        self.assertEqual(len(yielded2), 0, "Khi gặp repeated page signature, dừng pagination ngay lập tức")
        self.assertEqual(spider.stop_reason, "repeated_page_signature")

    @unittest.mock.patch("subprocess.run")
    def test_full_crawl_subprocess_command(self, mock_subproc):
        """Kiểm tra crawl_category ở chế độ full crawl (limit=None) truyền max_products=none vào Scrapy."""
        from crawler.run_crawler import crawl_category

        mock_subproc.return_value = MagicMock(returncode=0)
        custom_out = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop" / "fake_full.jsonl"

        crawl_category(
            category="laptop",
            limit=None,
            output_file=str(custom_out),
            batch_id="20261013_fulltest",
        )

        self.assertTrue(mock_subproc.called)
        called_cmd = mock_subproc.call_args[0][0]
        self.assertIn("max_products=none", called_cmd)
        self.assertIn("batch_id=20261013_fulltest", called_cmd)

    def test_start_requests_from_page_zero(self):
        """Pagination của TGDĐ phải bắt đầu từ pageIndex=0."""
        import asyncio

        spider = TgddBaseSpider(max_products=None)

        async def collect_first_request():
            async for request in spider.start():
                return request
            return None

        request = asyncio.run(collect_first_request())

        self.assertIsNotNone(request)
        self.assertEqual(request.meta["page"], 0)

        payload = json.loads(request.body.decode("utf-8"))
        self.assertEqual(payload["pageIndex"], 0)

    def test_parse_detail_with_multiple_variants(self):
        """
        Kiểm tra parse detail khi có ProductGroup.hasVariant (ít nhất 2 variants):
        - Yield đúng 2 variant items.
        - Không double count (không yield parent item thừa).
        - Kiểm tra đầy đủ: parent_product_id_raw, parent_product_name_raw, parent_url_raw,
          variant_name_raw, variant_color_raw, variant_url_raw, sku_raw, price_raw, availability_raw.
        """
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "ProductGroup",
                "name": "iPhone 17 Pro Max",
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "RAM", "value": "12 GB"},
                    {"@type": "PropertyValue", "name": "Chip", "value": "Apple A19 Pro"}
                ],
                "hasVariant": [
                    {
                        "@type": "Product",
                        "name": "iPhone 17 Pro Max 256GB",
                        "color": "Xanh Đậm",
                        "sku": "0131491004723",
                        "url": "https://www.thegioididong.com/dtdd/iphone-17-pro-max?code=0131491004723",
                        "offers": {
                            "@type": "Offer",
                            "price": 34990000,
                            "priceCurrency": "VND",
                            "availability": "https://schema.org/InStock"
                        }
                    },
                    {
                        "@type": "Product",
                        "name": "iPhone 17 Pro Max 512GB",
                        "color": "Cam Vũ Trụ",
                        "sku": "0131491004728",
                        "url": "https://www.thegioididong.com/dtdd/iphone-17-pro-max-512gb?code=0131491004728",
                        "offers": {
                            "@type": "Offer",
                            "price": 41490000,
                            "priceCurrency": "VND",
                            "availability": "https://schema.org/InStock"
                        }
                    }
                ]
            }
            </script>
        </head>
        <body>
            <h1>iPhone 17 Pro Max</h1>
        </body>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["source"] = "tgdd"
        listing_item["category"] = "smartphone"
        listing_item["crawl_batch"] = "20261013_test"
        listing_item["crawl_time"] = "2026-10-13T12:00:00"
        listing_item["product_id_raw"] = "342680"
        listing_item["product_name_raw"] = "iPhone 17 Pro Max"
        listing_item["product_url_raw"] = "https://www.thegioididong.com/dtdd/iphone-17-pro-max"
        listing_item["price_raw"] = 34990000
        listing_item["seller_raw"] = "Thế Giới Di Động"
        listing_item["sku_raw"] = "IPHONE-17-PM-LISTING-SKU"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/dtdd/iphone-17-pro-max",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/dtdd/iphone-17-pro-max",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        items = list(self.spider.parse_detail(mock_resp))

        # Phải yield đúng 2 items (chỉ variant items, không double-count item cha)
        self.assertEqual(len(items), 2)

        # Variant 1:
        v1 = items[0]
        # 1. product_name_raw != variant_name_raw khi variant có tên riêng
        self.assertNotEqual(v1["product_name_raw"], v1["variant_name_raw"])
        self.assertEqual(v1["product_name_raw"], "iPhone 17 Pro Max")
        self.assertEqual(v1["parent_product_name_raw"], "iPhone 17 Pro Max")
        self.assertEqual(v1["variant_name_raw"], "iPhone 17 Pro Max 256GB")

        # 2. product_url_raw vẫn là parent URL
        self.assertEqual(v1["product_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max")
        self.assertEqual(v1["parent_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max")

        # 3. variant_url_raw là URL variant
        self.assertEqual(v1["variant_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max?code=0131491004723")

        # 4. sku_raw vẫn giữ productNameSKU cũ từ listing
        self.assertEqual(v1["sku_raw"], "IPHONE-17-PM-LISTING-SKU")

        # 5. variant_sku_raw chứa variant.sku
        self.assertEqual(v1["variant_sku_raw"], "0131491004723")

        self.assertEqual(v1["parent_product_id_raw"], "342680")
        self.assertEqual(v1["product_id_raw"], "342680")
        self.assertEqual(v1["variant_color_raw"], "Xanh Đậm")
        self.assertEqual(v1["price_raw"], 34990000)
        self.assertIsNone(v1["original_price_raw"])
        self.assertEqual(v1["availability_raw"], "https://schema.org/InStock")
        self.assertEqual(v1["attributes_raw"]["RAM"], "12 GB")

        # Variant 2:
        v2 = items[1]
        # 1. product_name_raw != variant_name_raw khi variant có tên riêng
        self.assertNotEqual(v2["product_name_raw"], v2["variant_name_raw"])
        self.assertEqual(v2["product_name_raw"], "iPhone 17 Pro Max")
        self.assertEqual(v2["parent_product_name_raw"], "iPhone 17 Pro Max")
        self.assertEqual(v2["variant_name_raw"], "iPhone 17 Pro Max 512GB")

        # 2. product_url_raw vẫn là parent URL
        self.assertEqual(v2["product_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max")
        self.assertEqual(v2["parent_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max")

        # 3. variant_url_raw là URL variant
        self.assertEqual(v2["variant_url_raw"], "https://www.thegioididong.com/dtdd/iphone-17-pro-max-512gb?code=0131491004728")

        # 4. sku_raw vẫn giữ productNameSKU cũ từ listing
        self.assertEqual(v2["sku_raw"], "IPHONE-17-PM-LISTING-SKU")

        # 5. variant_sku_raw chứa variant.sku
        self.assertEqual(v2["variant_sku_raw"], "0131491004728")

        self.assertEqual(v2["parent_product_id_raw"], "342680")
        self.assertEqual(v2["product_id_raw"], "342680")
        self.assertEqual(v2["variant_color_raw"], "Cam Vũ Trụ")
        self.assertEqual(v2["price_raw"], 41490000)
        self.assertIsNone(v2["original_price_raw"])
        self.assertEqual(v2["availability_raw"], "https://schema.org/InStock")
        self.assertEqual(v2["attributes_raw"]["RAM"], "12 GB")

    def test_parse_detail_without_variants_fallback(self):
        """
        Kiểm tra parse detail khi không có ProductGroup.hasVariant (sản phẩm đơn cấu hình):
        - Yield đúng 1 item fallback cấp product.
        - parent_* được gán đúng thông tin sản phẩm.
        - variant_* để None phù hợp quy ước.
        """
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "HP Gaming VICTUS 15 fa2731TX",
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "CPU", "value": "i5 13420H"}
                ]
            }
            </script>
        </head>
        <body>
            <h1>HP Gaming VICTUS 15 fa2731TX</h1>
        </body>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["source"] = "tgdd"
        listing_item["category"] = "laptop"
        listing_item["product_id_raw"] = "193688"
        listing_item["product_name_raw"] = "HP Gaming VICTUS 15 fa2731TX"
        listing_item["product_url_raw"] = "https://www.thegioididong.com/laptop/hp-victus-15"
        listing_item["price_raw"] = 27990000
        listing_item["original_price_raw"] = 32490000
        listing_item["sku_raw"] = "HP-VICTUS-LISTING-SKU"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/laptop/hp-victus-15",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/laptop/hp-victus-15",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        items = list(self.spider.parse_detail(mock_resp))

        self.assertEqual(len(items), 1)
        res = items[0]
        self.assertEqual(res["product_id_raw"], "193688")
        self.assertEqual(res["parent_product_id_raw"], "193688")
        self.assertEqual(res["parent_product_name_raw"], "HP Gaming VICTUS 15 fa2731TX")
        self.assertEqual(res["parent_url_raw"], "https://www.thegioididong.com/laptop/hp-victus-15")
        self.assertEqual(res["product_name_raw"], "HP Gaming VICTUS 15 fa2731TX")
        self.assertEqual(res["product_url_raw"], "https://www.thegioididong.com/laptop/hp-victus-15")
        self.assertEqual(res["sku_raw"], "HP-VICTUS-LISTING-SKU")
        self.assertIsNone(res["variant_name_raw"])
        self.assertIsNone(res["variant_color_raw"])
        self.assertIsNone(res["variant_url_raw"])
        self.assertIsNone(res["variant_sku_raw"])
        self.assertIsNone(res["availability_raw"])
        self.assertEqual(res["price_raw"], 27990000)
        self.assertEqual(res["original_price_raw"], 32490000)
        self.assertEqual(res["attributes_raw"]["CPU"], "i5 13420H")

    def test_variant_prices_different_from_listing_baseline(self):
        """
        Đảm bảo không lấy chung productPrices[0] từ listing cho mọi variant.
        Mỗi item variant phải lấy đúng offers.price của chính variant đó.
        """
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "ProductGroup",
                "name": "MacBook Air M3",
                "hasVariant": [
                    {
                        "@type": "Product",
                        "name": "MacBook Air M3 8-core GPU / 16GB / 256GB",
                        "sku": "MAC-M3-256",
                        "offers": {"price": 27990000}
                    },
                    {
                        "@type": "Product",
                        "name": "MacBook Air M3 10-core GPU / 16GB / 512GB",
                        "sku": "MAC-M3-512",
                        "offers": {"price": 32990000}
                    }
                ]
            }
            </script>
        </head>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["product_id_raw"] = "55555"
        listing_item["product_name_raw"] = "MacBook Air M3"
        listing_item["product_url_raw"] = "https://www.thegioididong.com/laptop/macbook-air-m3"
        listing_item["price_raw"] = 99999999  # Baseline placeholder khác biệt
        listing_item["sku_raw"] = "MACBOOK-LISTING-SKU"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/laptop/macbook-air-m3",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/laptop/macbook-air-m3",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        items = list(self.spider.parse_detail(mock_resp))
        self.assertEqual(len(items), 2)
        # Variant 1 nhận giá 27990000 và variant_sku_raw tương ứng
        self.assertEqual(items[0]["price_raw"], 27990000)
        self.assertEqual(items[0]["variant_sku_raw"], "MAC-M3-256")
        self.assertEqual(items[0]["sku_raw"], "MACBOOK-LISTING-SKU")
        self.assertEqual(items[0]["product_name_raw"], "MacBook Air M3")

        # Variant 2 nhận giá 32990000 và variant_sku_raw tương ứng
        self.assertEqual(items[1]["price_raw"], 32990000)
        self.assertEqual(items[1]["variant_sku_raw"], "MAC-M3-512")
        self.assertEqual(items[1]["sku_raw"], "MACBOOK-LISTING-SKU")
        self.assertEqual(items[1]["product_name_raw"], "MacBook Air M3")

        # Không có item nào bị gán nhầm giá baseline 99999999
        self.assertNotIn(99999999, [items[0]["price_raw"], items[1]["price_raw"]])

    def test_attributes_preserved_across_variants(self):
        """
        Kiểm tra attributes_raw vẫn được giữ đầy đủ cho từng variant,
        không làm mất hoặc biến đổi semantic.
        """
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "ProductGroup",
                "name": "Samsung Galaxy S25 Ultra",
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "Độ phân giải màn hình", "value": "2K+ (1440 x 3120)"},
                    {"@type": "PropertyValue", "name": "Pin, Sạc", "value": "5000 mAh, 45 W"}
                ],
                "hasVariant": [
                    {
                        "@type": "Product",
                        "name": "Galaxy S25 Ultra 256GB",
                        "sku": "SAM-S25U-256",
                        "offers": {"price": 31990000}
                    },
                    {
                        "@type": "Product",
                        "name": "Galaxy S25 Ultra 512GB",
                        "sku": "SAM-S25U-512",
                        "offers": {"price": 35990000}
                    }
                ]
            }
            </script>
        </head>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["product_id_raw"] = "88888"
        listing_item["product_name_raw"] = "Samsung Galaxy S25 Ultra"
        listing_item["price_raw"] = 31990000
        listing_item["sku_raw"] = "SAM-LISTING-SKU"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/dtdd/samsung-galaxy-s25-ultra",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/dtdd/samsung-galaxy-s25-ultra",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        items = list(self.spider.parse_detail(mock_resp))
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIn("Độ phân giải màn hình", item["attributes_raw"])
            self.assertEqual(item["attributes_raw"]["Độ phân giải màn hình"], "2K+ (1440 x 3120)")
            self.assertEqual(item["attributes_raw"]["Pin, Sạc"], "5000 mAh, 45 W")
            self.assertEqual(item["sku_raw"], "SAM-LISTING-SKU")
            self.assertIsNotNone(item["variant_sku_raw"])

    def test_parse_detail_malformed_variants_graceful_fallback(self):
        """
        Kiểm tra khi hasVariant bị malformed (chuỗi thay vì list):
        Spider không bị crash, log cảnh báo và fallback về 1 item cấp product.
        """
        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "ProductGroup",
                "name": "Malformed Variant Product",
                "hasVariant": "invalid_string_not_list"
            }
            </script>
        </head>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["product_id_raw"] = "77777"
        listing_item["product_name_raw"] = "Malformed Variant Product"
        listing_item["price_raw"] = 15000000
        listing_item["sku_raw"] = "MALFORMED-LISTING-SKU"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/dtdd/malformed-product",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/dtdd/malformed-product",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        items = list(self.spider.parse_detail(mock_resp))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_id_raw"], "77777")
        self.assertEqual(items[0]["sku_raw"], "MALFORMED-LISTING-SKU")
        self.assertIsNone(items[0]["variant_name_raw"])
        self.assertIsNone(items[0]["variant_sku_raw"])



    # ---------------------------------------------------------
    # REVIEW EXTRACTION, PAGINATION, PIPELINE & LINKAGE TESTS
    # ---------------------------------------------------------

    def test_tech_review_raw_item_schema(self):
        """Kiểm tra schema TechReviewRawItem có đầy đủ các trường raw metadata và provenance."""
        expected_fields = [
            "source",
            "category",
            "crawl_batch",
            "crawl_time",
            "parent_product_id_raw",
            "parent_product_url_raw",
            "review_id_raw",
            "rating_raw",
            "review_text_raw",
            "author_raw",
            "review_time_raw",
            "like_count_raw",
            "review_product_code_raw",
            "variant_sku_raw",
            "variant_code_raw",
            "buy_date_raw",
            "reply_raw",
            "attached_files_raw",
            "raw_payload",
        ]
        item = TechReviewRawItem()
        for field in expected_fields:
            self.assertIn(field, item.fields)

    def test_parse_reviews_success_and_preserves_raw_data(self):
        """
        Kiểm tra parse_reviews thành công từ fixture phản hồi thực tế của TGDĐ.
        Bảo toàn text tiếng Việt nguyên gốc, số sao, author, like count và raw payload.
        """
        mock_response_data = {
            "code": 0,
            "message": "",
            "data": {
                "total": 1,
                "comments": [
                    {
                        "site": 1,
                        "commentId": 59825818,
                        "content": "Sản phẩm tốt . Nhân viên tư vấn , hỗ trợ nhiệt tình . sẽ ủng hộ shop lần sau .",
                        "likeCount": 3,
                        "score": 5,
                        "createdDate": "2026-08-21T18:54:06",
                        "fullName": "Tran Ngoc Phu",
                        "modelId": "201327",
                        "isAnonymous": False,
                        "gender": 2,
                        "commentAttachedFileBOList": [],
                        "variantCode": "10054294",
                        "productCode": "0131491005083",
                        "hasRecommendProduct": True,
                        "isApprove": 1,
                        "deliveryDate": "2026-08-18T16:01:18",
                        "supportStatus": 0,
                        "responseContent": "Dạ cảm ơn anh đã tin tưởng mua sắm tại Thế Giới Di Động",
                        "cbuyDate": "2026-08-18T16:01:18",
                        "state": 1,
                    }
                ],
                "commentSta": {
                    "totalRating": 706,
                    "scoreRating": 4.9,
                },
            },
        }

        req = scrapy.Request(
            url="https://api.thegioididong.com/gw/bus-tgdd-tmdt/api/Comment/Product/Code",
            meta={
                "parent_product_id": "201327",
                "parent_product_url": "https://www.thegioididong.com/dtdd/xiaomi-17",
                "page_index": 0,
                "page_size": 20,
                "known_variant_skus": ["0131491005083"],
            },
        )
        resp = TextResponse(
            url="https://api.thegioididong.com/gw/bus-tgdd-tmdt/api/Comment/Product/Code",
            body=json.dumps(mock_response_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(self.spider.parse_reviews(resp))
        review_items = [r for r in results if isinstance(r, TechReviewRawItem)]
        self.assertEqual(len(review_items), 1)

        rev = review_items[0]
        self.assertEqual(rev["source"], "tgdd")
        self.assertEqual(rev["parent_product_id_raw"], "201327")
        self.assertEqual(rev["parent_product_url_raw"], "https://www.thegioididong.com/dtdd/xiaomi-17")
        self.assertEqual(rev["review_id_raw"], "59825818")
        self.assertEqual(rev["rating_raw"], 5)
        self.assertEqual(
            rev["review_text_raw"],
            "Sản phẩm tốt . Nhân viên tư vấn , hỗ trợ nhiệt tình . sẽ ủng hộ shop lần sau .",
        )
        self.assertEqual(rev["author_raw"], "Tran Ngoc Phu")
        self.assertEqual(rev["review_time_raw"], "2026-08-21T18:54:06")
        self.assertEqual(rev["like_count_raw"], 3)
        self.assertEqual(rev["review_product_code_raw"], "0131491005083")
        self.assertEqual(rev["variant_sku_raw"], "0131491005083")
        self.assertEqual(rev["variant_code_raw"], "10054294")
        self.assertEqual(rev["buy_date_raw"], "2026-08-18T16:01:18")
        self.assertEqual(
            rev["reply_raw"],
            "Dạ cảm ơn anh đã tin tưởng mua sắm tại Thế Giới Di Động",
        )
        self.assertIsNotNone(rev["raw_payload"])
        self.assertEqual(rev["raw_payload"]["commentId"], 59825818)

    def test_parse_reviews_pagination_and_stop_condition(self):
        """
        Kiểm tra phân trang review:
        - Page 0 (20 items, total=35) -> yield 20 review items + 1 request page 1.
        - Page 1 (15 items, total=35) -> (1+1)*20 = 40 >= total 35 -> dừng phân trang (không yield thêm request).
        """
        spider = TgddBaseSpider(crawl_reviews=True)

        def make_page_response(page: int, num_items: int, total: int):
            comments = [
                {
                    "commentId": 1000 + page * 100 + i,
                    "content": f"Review {page}-{i}",
                    "score": 5,
                    "fullName": f"User {i}",
                }
                for i in range(num_items)
            ]
            body_data = {
                "code": 0,
                "data": {
                    "total": total,
                    "comments": comments,
                },
            }
            req = scrapy.Request(
                url=spider.COMMENT_API_URL,
                meta={
                    "parent_product_id": "201300",
                    "parent_product_url": "https://www.thegioididong.com/dtdd/iphone-17-pro-max",
                    "page_index": page,
                    "page_size": 20,
                },
            )
            return TextResponse(
                url=spider.COMMENT_API_URL,
                body=json.dumps(body_data).encode("utf-8"),
                encoding="utf-8",
                request=req,
            )

        # 1. Page 0
        resp0 = make_page_response(page=0, num_items=20, total=35)
        res0 = list(spider.parse_reviews(resp0))
        items0 = [x for x in res0 if isinstance(x, TechReviewRawItem)]
        reqs0 = [x for x in res0 if isinstance(x, scrapy.Request)]
        self.assertEqual(len(items0), 20)
        self.assertEqual(len(reqs0), 1)
        next_req = reqs0[0]
        self.assertEqual(next_req.meta["page_index"], 1)
        req_payload = json.loads(next_req.body.decode("utf-8"))
        self.assertEqual(req_payload["pageIndex"], 1)
        self.assertEqual(req_payload["modelCode"], "201300")

        # 2. Page 1
        resp1 = make_page_response(page=1, num_items=15, total=35)
        res1 = list(spider.parse_reviews(resp1))
        items1 = [x for x in res1 if isinstance(x, TechReviewRawItem)]
        reqs1 = [x for x in res1 if isinstance(x, scrapy.Request)]
        self.assertEqual(len(items1), 15)
        self.assertEqual(len(reqs1), 0, "Khi đã hết sản phẩm theo total, không được lên lịch tiếp")

    def test_parse_reviews_malformed_response_does_not_crash(self):
        """
        Kiểm tra khi review API trả về dữ liệu hỏng:
        - HTML lỗi 500
        - JSON code khác 0
        Spider không bị crash, ghi nhận failure và tiếp tục hoạt động.
        """
        spider = TgddBaseSpider(crawl_reviews=True)

        # 1. Non-JSON response
        req = scrapy.Request(
            url=spider.COMMENT_API_URL,
            meta={"parent_product_id": "999", "page_index": 0},
        )
        bad_resp = TextResponse(
            url=spider.COMMENT_API_URL,
            body="<html><body>502 Bad Gateway</body></html>".encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        res = list(spider.parse_reviews(bad_resp))
        self.assertEqual(len(res), 0)
        self.assertEqual(spider.review_failures, 1)

        # 2. Error code response
        error_resp = TextResponse(
            url=spider.COMMENT_API_URL,
            body=json.dumps({"code": 10004, "message": "Tham số không hợp lệ"}).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        res2 = list(spider.parse_reviews(error_resp))
        self.assertEqual(len(res2), 0)
        self.assertEqual(spider.review_failures, 2)

    def test_review_duplicate_id_guard(self):
        """Kiểm tra trùng lặp review ID được lọc bỏ để tránh ghi duplicate records."""
        spider = TgddBaseSpider(crawl_reviews=True)

        body_data = {
            "code": 0,
            "data": {
                "total": 2,
                "comments": [
                    {"commentId": 55555, "content": "Lần 1", "score": 5},
                    {"commentId": 55555, "content": "Lần 2 trùng ID", "score": 5},
                ],
            },
        }
        req = scrapy.Request(
            url=spider.COMMENT_API_URL,
            meta={"parent_product_id": "201300", "page_index": 0},
        )
        resp = TextResponse(
            url=spider.COMMENT_API_URL,
            body=json.dumps(body_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        res = list(spider.parse_reviews(resp))
        items = [x for x in res if isinstance(x, TechReviewRawItem)]
        self.assertEqual(len(items), 1, "Chỉ yield 1 item khi phát hiện duplicate commentId")
        self.assertEqual(items[0]["review_id_raw"], "55555")

    def test_review_linkage_to_parent_and_variant(self):
        """
        Kiểm tra linkage đúng semantics:
        1. ProductGroup có variant:
           - review_product_code_raw = raw productCode từ TGDĐ.
           - variant_sku_raw CHỈ được gán khi productCode match một variant.sku trong hasVariant.
           - Nếu productCode không match hoặc bằng None -> variant_sku_raw = None.
        2. Product không có variant (như 193571):
           - review_product_code_raw = raw productCode (vd: 0220042002667).
           - variant_sku_raw = None (không tự gán làm variant SKU).
           - variant_code_raw = variantCode (vd: 193571).
        """
        spider = TgddBaseSpider(crawl_reviews=True)

        # -------------------------------------------------------------
        # Case 1: ProductGroup có variants (known_variant_skus = {"SKU-VARIANT-256"})
        # -------------------------------------------------------------
        body_with_variants = {
            "code": 0,
            "data": {
                "total": 3,
                "comments": [
                    {
                        "commentId": 111,
                        "content": "Mua bản 256GB màu Đen",
                        "score": 5,
                        "productCode": "SKU-VARIANT-256",
                        "variantCode": "CODE-VAR-1",
                    },
                    {
                        "commentId": 222,
                        "content": "Review mua cấu hình ngoài hoặc mã không match",
                        "score": 4,
                        "productCode": "UNKNOWN-SKU-999",
                        "variantCode": "CODE-VAR-9",
                    },
                    {
                        "commentId": 333,
                        "content": "Review chung cho dòng máy không có productCode",
                        "score": 4,
                        "productCode": None,
                        "variantCode": None,
                    },
                ],
            },
        }
        req_var = scrapy.Request(
            url=spider.COMMENT_API_URL,
            meta={
                "parent_product_id": "PARENT-PROD-99",
                "parent_product_url": "https://www.thegioididong.com/dtdd/phone-99",
                "page_index": 0,
                "known_variant_skus": ["SKU-VARIANT-256"],
            },
        )
        resp_var = TextResponse(
            url=spider.COMMENT_API_URL,
            body=json.dumps(body_with_variants).encode("utf-8"),
            encoding="utf-8",
            request=req_var,
        )

        items_var = [x for x in spider.parse_reviews(resp_var) if isinstance(x, TechReviewRawItem)]
        self.assertEqual(len(items_var), 3)

        # Review 1: match variant SKU thực tế
        self.assertEqual(items_var[0]["parent_product_id_raw"], "PARENT-PROD-99")
        self.assertEqual(items_var[0]["review_product_code_raw"], "SKU-VARIANT-256")
        self.assertEqual(items_var[0]["variant_sku_raw"], "SKU-VARIANT-256")
        self.assertEqual(items_var[0]["variant_code_raw"], "CODE-VAR-1")

        # Review 2: có productCode nhưng KHÔNG match variant SKU nào -> variant_sku_raw = None
        self.assertEqual(items_var[1]["parent_product_id_raw"], "PARENT-PROD-99")
        self.assertEqual(items_var[1]["review_product_code_raw"], "UNKNOWN-SKU-999")
        self.assertIsNone(items_var[1]["variant_sku_raw"])
        self.assertEqual(items_var[1]["variant_code_raw"], "CODE-VAR-9")

        # Review 3: không có productCode
        self.assertEqual(items_var[2]["parent_product_id_raw"], "PARENT-PROD-99")
        self.assertIsNone(items_var[2]["review_product_code_raw"])
        self.assertIsNone(items_var[2]["variant_sku_raw"])
        self.assertIsNone(items_var[2]["variant_code_raw"])

        # -------------------------------------------------------------
        # Case 2: Product không có hasVariant (ví dụ thực tế: laptop 193571)
        # -------------------------------------------------------------
        body_no_variants = {
            "code": 0,
            "data": {
                "total": 1,
                "comments": [
                    {
                        "commentId": 444,
                        "content": "Máy dùng tốt cho học tập",
                        "score": 5,
                        "productCode": "0220042002667",
                        "variantCode": "193571",
                    }
                ],
            },
        }
        req_no_var = scrapy.Request(
            url=spider.COMMENT_API_URL,
            meta={
                "parent_product_id": "193571",
                "parent_product_url": "https://www.thegioididong.com/laptop/hp-victus-193571",
                "page_index": 0,
                "known_variant_skus": [],  # Không có variant
            },
        )
        resp_no_var = TextResponse(
            url=spider.COMMENT_API_URL,
            body=json.dumps(body_no_variants).encode("utf-8"),
            encoding="utf-8",
            request=req_no_var,
        )

        items_no_var = [x for x in spider.parse_reviews(resp_no_var) if isinstance(x, TechReviewRawItem)]
        self.assertEqual(len(items_no_var), 1)
        self.assertEqual(items_no_var[0]["parent_product_id_raw"], "193571")
        # Bảo toàn raw productCode từ TGDĐ
        self.assertEqual(items_no_var[0]["review_product_code_raw"], "0220042002667")
        # variant_sku_raw PHẢI là None vì sản phẩm không có biến thể
        self.assertIsNone(items_no_var[0]["variant_sku_raw"])
        # variant_code_raw giữ nguyên raw variantCode từ TGDĐ
        self.assertEqual(items_no_var[0]["variant_code_raw"], "193571")

    def test_product_group_yields_variants_and_schedules_single_review_request(self):
        """
        Đảm bảo khi crawl_reviews=True:
        - ProductGroup vẫn yield đúng các variant records độc lập.
        - Chỉ schedule đúng 1 review request cho parent product (không schedule lặp cho mỗi variant).
        - Truyền danh sách known_variant_skus vào request meta để đối soát linkage review.
        """
        spider = TgddBaseSpider(crawl_reviews=True)

        mock_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "ProductGroup",
                "name": "Samsung Galaxy S26 Ultra",
                "hasVariant": [
                    {
                        "@type": "Product",
                        "name": "Galaxy S26 Ultra 256GB",
                        "sku": "SAM-S26-256",
                        "offers": {"price": 31990000}
                    },
                    {
                        "@type": "Product",
                        "name": "Galaxy S26 Ultra 512GB",
                        "sku": "SAM-S26-512",
                        "offers": {"price": 35990000}
                    }
                ]
            }
            </script>
        </head>
        </html>
        """
        listing_item = TechProductRawItem()
        listing_item["product_id_raw"] = "201332"
        listing_item["product_name_raw"] = "Samsung Galaxy S26 Ultra"
        listing_item["product_url_raw"] = "https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra"

        mock_req = scrapy.Request(
            url="https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra",
            meta={"item": listing_item},
        )
        mock_resp = HtmlResponse(
            url="https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra",
            body=mock_html.encode("utf-8"),
            encoding="utf-8",
            request=mock_req,
        )

        results = list(spider.parse_detail(mock_resp))
        product_items = [x for x in results if isinstance(x, TechProductRawItem)]
        requests = [x for x in results if isinstance(x, scrapy.Request)]

        # 2 variants yielded đúng chuẩn
        self.assertEqual(len(product_items), 2)
        self.assertEqual(product_items[0]["variant_sku_raw"], "SAM-S26-256")
        self.assertEqual(product_items[1]["variant_sku_raw"], "SAM-S26-512")

        # Đúng 1 review request được tạo cho parent product
        self.assertEqual(len(requests), 1)
        rev_req = requests[0]
        self.assertEqual(rev_req.url, spider.COMMENT_API_URL)
        payload = json.loads(rev_req.body.decode("utf-8"))
        self.assertEqual(payload["modelCode"], "201332")
        self.assertEqual(payload["pageIndex"], 0)
        # Kiểm tra known_variant_skus đã được chuyển sang meta
        self.assertEqual(set(rev_req.meta.get("known_variant_skus", [])), {"SAM-S26-256", "SAM-S26-512"})

    def test_pipeline_separates_product_and_review_items(self):
        """
        Kiểm tra TgddReviewExportPipeline:
        - TechProductRawItem đi qua pipeline bình thường để vào feed product (-o target_out).
        - TechReviewRawItem được ghi vào file review riêng và raise DropItem (không bị lẫn vào product).
        """
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            rev_file = Path(tmpdir) / "test_reviews.jsonl"

            pipeline = TgddReviewExportPipeline()
            spider = TgddBaseSpider(crawl_reviews=True, review_output=str(rev_file))

            pipeline.open_spider(spider)
            try:
                # 1. Product item không bị drop
                prod = TechProductRawItem(product_id_raw="111", product_name_raw="Test Laptop")
                processed = pipeline.process_item(prod, spider)
                self.assertIs(processed, prod)

                # 2. Review item bị drop và ghi vào review file
                rev = TechReviewRawItem(
                    review_id_raw="999",
                    review_text_raw="Đánh giá tuyệt vời",
                    rating_raw=5,
                )
                with self.assertRaises(DropItem):
                    pipeline.process_item(rev, spider)

            finally:
                pipeline.close_spider(spider)

            self.assertTrue(rev_file.exists())
            rev_lines = rev_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rev_lines), 1)
            saved_rev = json.loads(rev_lines[0])
            self.assertEqual(saved_rev["review_id_raw"], "999")
            self.assertEqual(saved_rev["review_text_raw"], "Đánh giá tuyệt vời")

    def test_get_review_snapshot_path_convention(self):
        """Kiểm tra naming convention và tính độc lập của file review snapshot."""
        path_phone = get_review_snapshot_path("smartphone", "20261013_120000")
        self.assertTrue(str(path_phone).endswith("smartphone_reviews\\20261013_120000.jsonl") or str(path_phone).endswith("smartphone_reviews/20261013_120000.jsonl"))

        path_laptop = get_review_snapshot_path("laptop", "20261013_120000")
        self.assertTrue(str(path_laptop).endswith("laptop_reviews\\20261013_120000.jsonl") or str(path_laptop).endswith("laptop_reviews/20261013_120000.jsonl"))


if __name__ == "__main__":
    unittest.main()
