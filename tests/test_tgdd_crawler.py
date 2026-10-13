import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import scrapy
from scrapy.dupefilters import RFPDupeFilter
from scrapy.http import HtmlResponse, TextResponse

from crawler.run_crawler import generate_batch_id, get_snapshot_path
from crawler.tgdd.base_spider import TgddBaseSpider
from crawler.tgdd.items import TechProductRawItem
from crawler.tgdd.tgdd_laptop_spider import TgddLaptopSpider
from crawler.tgdd.tgdd_smartphone_spider import TgddSmartphoneSpider

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
            "price_raw",
            "original_price_raw",
            "seller_raw",
            "rating_raw",
            "review_count_raw",
            "attributes_raw",
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


if __name__ == "__main__":
    unittest.main()
