import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy.exceptions import DropItem
from scrapy.http import HtmlResponse, TextResponse

from crawler.cellphoneS.base_spider import (
    CellphonesBaseSpider,
    CELLPHONES_DEFAULT_PROVINCE_ID,
    CATALOG_GRAPHQL_URL,
    REVIEW_GRAPHQL_URL,
)
from crawler.cellphoneS.cellphones_laptop_spider import CellphonesLaptopSpider
from crawler.cellphoneS.cellphones_smartphone_spider import CellphonesSmartphoneSpider
from crawler.cellphoneS.items import TechProductRawItem, TechReviewRawItem
from crawler.cellphoneS.pipelines import CellphonesReviewExportPipeline
from crawler.run_crawler import (
    ensure_output_path_available,
    get_snapshot_path,
    get_review_snapshot_path,
    build_argument_parser,
)


EXPECTED_PRODUCT_FIELDS = {
    "source",
    "category",
    "crawl_batch",
    "crawl_time",
    "product_id_raw",
    "product_name_raw",
    "product_url_raw",
    "parent_product_id_raw",
    "parent_product_name_raw",
    "parent_url_raw",
    "sku_raw",
    "variant_name_raw",
    "variant_color_raw",
    "variant_url_raw",
    "variant_sku_raw",
    "availability_raw",
    "price_raw",
    "original_price_raw",
    "brand_raw",
    "seller_raw",
    "rating_raw",
    "review_count_raw",
    "total_sold_raw",
    "attributes_raw",
    "raw_payload",
}

EXPECTED_REVIEW_FIELDS = {
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
    "variant_code_raw",
    "variant_sku_raw",
    "buy_date_raw",
    "reply_raw",
    "attached_files_raw",
    "raw_payload",
}


class TestCellphonesCrawler(unittest.TestCase):
    """
    Bộ test toàn diện cho crawler CellphoneS tuân thủ:
    - 25 fields Canonical Product Schema
    - 19 fields Canonical Review Schema
    - Các quy tắc về Pagination, Invariant, Variant, Technical Attributes, Immutable Snapshot
    """

    def setUp(self):
        self.phone_spider = CellphonesSmartphoneSpider(batch_id="20261014_test_batch", crawl_reviews=False)
        self.laptop_spider = CellphonesLaptopSpider(batch_id="20261014_test_batch", crawl_reviews=False)

    # ---------------------------------------------------------
    # 1. PAGINATION STARTS AT 1
    # ---------------------------------------------------------
    def test_01_pagination_starts_at_1(self):
        """Kiểm tra request khởi động pagination bắt đầu chính xác từ page=1 (không bao giờ bắt đầu từ 0)."""
        req = self.phone_spider.make_listing_request(page=1)
        self.assertEqual(req.url, CATALOG_GRAPHQL_URL)
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.meta["page"], 1)

        payload = json.loads(req.body.decode("utf-8"))
        self.assertIn("page: 1,", payload["query"])

    # ---------------------------------------------------------
    # 2. PAGE 0 REJECTED / EMPTY
    # ---------------------------------------------------------
    def test_02_page_0_is_rejected_or_empty(self):
        """Kiểm tra page=0 trả về rỗng theo đặc tính của CellphoneS GraphQL và spider dừng đúng đắn."""
        mock_response_data = {"data": {"products": []}}
        req = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 0})
        res = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_response_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(self.phone_spider.parse_listing(res))
        self.assertEqual(len(results), 0)
        self.assertEqual(self.phone_spider.stop_reason, "no_more_products")

    # ---------------------------------------------------------
    # 3. PAGE 1 PARSING
    # ---------------------------------------------------------
    def test_03_page_1_parsing(self):
        """Kiểm tra parse page 1 nhận diện đúng các sản phẩm và lên lịch child requests."""
        mock_response_data = {
            "data": {
                "products": [
                    {
                        "general": {
                            "product_id": "1001",
                            "name": "Samsung Galaxy S24 Ultra",
                            "sku": "SAM-S24U",
                            "manufacturer": "Samsung",
                            "url_path": "samsung-galaxy-s24-ultra.html",
                            "child_product": ["2001", "2002"],
                            "review": {"total_count": 15, "average_rating": 4.9},
                            "attributes": {"ram": "12GB"},
                        },
                        "filterable": {
                            "price": 31990000,
                            "special_price": 28990000,
                            "stock": 10,
                        },
                    }
                ]
            }
        }
        req = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 1})
        res = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_response_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(self.phone_spider.parse_listing(res))
        self.assertEqual(self.phone_spider.listing_pages_processed, 1)
        self.assertEqual(self.phone_spider.scheduled_products, 1)
        self.assertEqual(self.phone_spider.unique_parents_collected, 1)
        self.assertEqual(len(results), 1)  # 1 child variant request được yield

        child_req = results[0]
        self.assertEqual(child_req.meta["child_ids"], ["2001", "2002"])

    # ---------------------------------------------------------
    # 4. PAGE 2 PARSING & CONTINUATION
    # ---------------------------------------------------------
    def test_04_page_2_parsing_and_continuation(self):
        """Kiểm tra khi page 1 đủ page_size, spider lên lịch page 2."""
        spider = CellphonesSmartphoneSpider(max_products=100)
        spider.page_size = 2  # đặt kích thước nhỏ để test pagination

        mock_page1_data = {
            "data": {
                "products": [
                    {"general": {"product_id": "101", "name": "Phone 1", "child_product": []}},
                    {"general": {"product_id": "102", "name": "Phone 2", "child_product": []}},
                ]
            }
        }
        req1 = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 1})
        res1 = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_page1_data).encode("utf-8"),
            encoding="utf-8",
            request=req1,
        )

        results1 = list(spider.parse_listing(res1))
        # 2 detail requests cho 2 sản phẩm + 1 listing request cho page 2
        listing_reqs = [r for r in results1 if r.callback == spider.parse_listing]
        self.assertEqual(len(listing_reqs), 1)
        self.assertEqual(listing_reqs[0].meta["page"], 2)

    # ---------------------------------------------------------
    # 5. EMPTY-PAGE STOP
    # ---------------------------------------------------------
    def test_05_empty_page_stop(self):
        """Kiểm tra khi gặp page rỗng products=[] thì dừng pagination ngay lập tức."""
        spider = CellphonesSmartphoneSpider()
        mock_empty_data = {"data": {"products": []}}
        req = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 3})
        res = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_empty_data).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(spider.parse_listing(res))
        self.assertEqual(len(results), 0)
        self.assertEqual(spider.stop_reason, "no_more_products")

    # ---------------------------------------------------------
    # 6. REPEATED PAGE GUARD
    # ---------------------------------------------------------
    def test_06_repeated_page_guard(self):
        """Kiểm tra phát hiện lặp lại danh sách sản phẩm giữa các page và kích hoạt guard dừng."""
        spider = CellphonesSmartphoneSpider(max_products=100)
        mock_data = {
            "data": {
                "products": [
                    {"general": {"product_id": "999", "name": "Repeated Phone", "child_product": []}}
                ]
            }
        }
        req1 = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 1})
        res1 = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_data).encode("utf-8"),
            encoding="utf-8",
            request=req1,
        )
        list(spider.parse_listing(res1))

        # Page 2 trả về y hệt sản phẩm của page 1
        req2 = scrapy.Request(url=CATALOG_GRAPHQL_URL, meta={"page": 2})
        res2 = TextResponse(
            url=CATALOG_GRAPHQL_URL,
            body=json.dumps(mock_data).encode("utf-8"),
            encoding="utf-8",
            request=req2,
        )
        list(spider.parse_listing(res2))
        self.assertEqual(spider.stop_reason, "repeated_page_detected")

    # ---------------------------------------------------------
    # 7. PARENT IDENTITY
    # ---------------------------------------------------------
    def test_07_parent_identity(self):
        """Kiểm tra thông tin parent product được gán chính xác vào canonical item."""
        parent_meta = {
            "parent_id": "8888",
            "parent_name": "iPhone 16 Pro Max",
            "parent_sku": "APP-IP16PM",
            "brand": "Apple",
            "parent_url": "https://cellphones.com.vn/iphone-16-pro-max.html",
            "rating": 5.0,
            "review_count": 100,
            "general_attrs": {},
            "parent_filt": {"price": 34990000, "special_price": 31990000, "stock": 5},
            "raw_payload": {"id": 8888},
        }

        items = list(self.phone_spider.yield_product_items(parent_meta, child_variants=None, attributes={"Màn hình": "6.9 inches"}))
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["product_id_raw"], "8888")
        self.assertEqual(it["parent_product_id_raw"], "8888")
        self.assertEqual(it["product_name_raw"], "iPhone 16 Pro Max")
        self.assertEqual(it["parent_product_name_raw"], "iPhone 16 Pro Max")
        self.assertEqual(it["product_url_raw"], "https://cellphones.com.vn/iphone-16-pro-max.html")
        self.assertEqual(it["parent_url_raw"], "https://cellphones.com.vn/iphone-16-pro-max.html")
        self.assertEqual(it["brand_raw"], "Apple")
        self.assertEqual(it["sku_raw"], "APP-IP16PM")

    # ---------------------------------------------------------
    # 8. CHILD VARIANT EXTRACTION
    # ---------------------------------------------------------
    def test_08_child_variant_extraction(self):
        """Kiểm tra trích xuất biến thể con sinh ra các records độc lập với đầy đủ tên và màu sắc."""
        parent_meta = {
            "parent_id": "8888",
            "parent_name": "iPhone 16 Pro Max",
            "parent_sku": "APP-IP16PM",
            "brand": "Apple",
            "parent_url": "https://cellphones.com.vn/iphone-16-pro-max.html",
            "rating": 5.0,
            "review_count": 100,
            "general_attrs": {},
            "raw_payload": {},
        }

        mock_children = [
            {
                "general": {
                    "product_id": "8889",
                    "name": "iPhone 16 Pro Max 256GB - Titan Sa Mạc",
                    "sku": "APP-IP16PM-256-DESERT",
                    "url_path": "iphone-16-pro-max-256gb-desert.html",
                    "attributes": {"color": "Titan Sa Mạc"},
                },
                "filterable": {"price": 34990000, "special_price": 31990000, "stock": 20},
            },
            {
                "general": {
                    "product_id": "8890",
                    "name": "iPhone 16 Pro Max 256GB - Titan Đen",
                    "sku": "APP-IP16PM-256-BLACK",
                    "url_path": "iphone-16-pro-max-256gb-black.html",
                    "attributes": {"color": "Titan Đen"},
                },
                "filterable": {"price": 34990000, "special_price": 31990000, "stock": 15},
            },
        ]

        items = list(self.phone_spider.yield_product_items(parent_meta, child_variants=mock_children, attributes={"Chip": "A18 Pro"}))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["variant_sku_raw"], "APP-IP16PM-256-DESERT")
        self.assertEqual(items[0]["variant_color_raw"], "Titan Sa Mạc")
        self.assertEqual(items[1]["variant_sku_raw"], "APP-IP16PM-256-BLACK")
        self.assertEqual(items[1]["variant_color_raw"], "Titan Đen")

    # ---------------------------------------------------------
    # 9. IS_PARENT=FALSE CHILD QUERY
    # ---------------------------------------------------------
    def test_09_is_parent_false_child_query(self):
        """Kiểm tra child variants query bắt buộc có static.is_parent='false'."""
        parent_meta = {
            "parent_id": "8888",
            "parent_url": "https://cellphones.com.vn/iphone-16-pro-max.html",
        }
        req = self.phone_spider.make_child_variants_request(["8889", "8890"], parent_meta)
        payload = json.loads(req.body.decode("utf-8"))
        query_text = payload["query"]
        self.assertIn('is_parent: "false"', query_text)
        self.assertIn('"8889"', query_text)
        self.assertIn('"8890"', query_text)
        self.assertIn(f"province_id: {CELLPHONES_DEFAULT_PROVINCE_ID}", query_text)

    # ---------------------------------------------------------
    # 10. VARIANT SKU MAPPING
    # ---------------------------------------------------------
    def test_10_variant_sku_mapping(self):
        """Kiểm tra variant_sku_raw lấy đúng từ child sku, còn sku_raw giữ parent sku."""
        parent_meta = {
            "parent_id": "777",
            "parent_name": "Laptop Dell XPS",
            "parent_sku": "DELL-XPS-BASE",
            "brand": "Dell",
            "parent_url": "https://cellphones.com.vn/laptop-dell-xps.html",
            "rating": None,
            "review_count": None,
            "general_attrs": {},
            "raw_payload": {},
        }
        child = [
            {
                "general": {
                    "product_id": "778",
                    "name": "Laptop Dell XPS 13 i7",
                    "sku": "DELL-XPS-13-I7",
                    "url_path": "laptop-dell-xps-13-i7.html",
                    "attributes": {},
                },
                "filterable": {"price": 45000000, "special_price": 42000000, "stock": 3},
            }
        ]
        items = list(self.laptop_spider.yield_product_items(parent_meta, child, {}))
        self.assertEqual(items[0]["sku_raw"], "DELL-XPS-BASE")
        self.assertEqual(items[0]["variant_sku_raw"], "DELL-XPS-13-I7")

    # ---------------------------------------------------------
    # 11. VARIANT PRICE MAPPING
    # ---------------------------------------------------------
    def test_11_variant_price_mapping(self):
        """Kiểm tra mapping giá: current price lấy special_price (nếu có) hoặc price; original price lấy price."""
        parent_meta = {
            "parent_id": "1",
            "parent_name": "P",
            "parent_sku": "SKU",
            "brand": "B",
            "parent_url": "https://cellphones.com.vn/p.html",
            "rating": 5,
            "review_count": 1,
            "general_attrs": {},
            "raw_payload": {},
        }

        # Case A: Có special_price
        child_with_discount = [
            {
                "general": {"product_id": "2", "name": "V1", "sku": "SKU-1"},
                "filterable": {"price": 20000000, "special_price": 18000000, "stock": 5},
            }
        ]
        items_a = list(self.phone_spider.yield_product_items(parent_meta, child_with_discount, {}))
        self.assertEqual(items_a[0]["price_raw"], 18000000)
        self.assertEqual(items_a[0]["original_price_raw"], 20000000)
        self.assertIsInstance(items_a[0]["price_raw"], (int, float))

        # Case B: Không có special_price (hoặc bằng 0/None)
        child_no_discount = [
            {
                "general": {"product_id": "3", "name": "V2", "sku": "SKU-2"},
                "filterable": {"price": 20000000, "special_price": 0, "stock": 5},
            }
        ]
        items_b = list(self.phone_spider.yield_product_items(parent_meta, child_no_discount, {}))
        self.assertEqual(items_b[0]["price_raw"], 20000000)
        self.assertEqual(items_b[0]["original_price_raw"], 20000000)

    # ---------------------------------------------------------
    # 12. STOCK MAPPING
    # ---------------------------------------------------------
    def test_12_stock_mapping(self):
        """Kiểm tra availability_raw giữ nguyên raw numeric stock từ API, không normalize ở TV1."""
        parent_meta = {
            "parent_id": "1",
            "parent_name": "P",
            "parent_sku": "SKU",
            "brand": "B",
            "parent_url": "https://cellphones.com.vn/p.html",
            "rating": 5,
            "review_count": 1,
            "general_attrs": {},
            "raw_payload": {},
        }
        child = [
            {
                "general": {"product_id": "2", "name": "V", "sku": "SKU-V"},
                "filterable": {"price": 1000, "stock": 42},
            }
        ]
        items = list(self.phone_spider.yield_product_items(parent_meta, child, {}))
        self.assertEqual(items[0]["availability_raw"], 42)

    # ---------------------------------------------------------
    # 13. JSON-LD ATTRIBUTES
    # ---------------------------------------------------------
    def test_13_jsonld_attributes(self):
        """Kiểm tra trích xuất technical attributes từ Schema.org JSON-LD additionalProperty."""
        mock_html = """
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Test Laptop",
                "additionalProperty": [
                    {"name": "Dung lượng RAM", "value": "16 GB"},
                    {"name": "Kích thước màn hình", "value": "15.6 inches"},
                    {"name": "Ổ cứng", "value": "512 GB SSD"}
                ]
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        attrs = self.laptop_spider.extract_jsonld_attributes(mock_html)
        self.assertEqual(attrs.get("Dung lượng RAM"), "16 GB")
        self.assertEqual(attrs.get("Kích thước màn hình"), "15.6 inches")
        self.assertEqual(attrs.get("Ổ cứng"), "512 GB SSD")

    # ---------------------------------------------------------
    # 14. GRAPHQL ATTRIBUTES FALLBACK
    # ---------------------------------------------------------
    def test_14_graphql_attributes_fallback(self):
        """Kiểm tra fallback sang general.attributes khi JSON-LD không có additionalProperty."""
        general_attrs = {
            "laptop_cpu": "Intel Core i7-13620H",
            "laptop_ram": "16GB",
            "laptop_hard_drive": "512GB SSD",
        }
        attrs = self.laptop_spider.extract_graphql_attributes(general_attrs)
        self.assertEqual(attrs.get("laptop_cpu"), "Intel Core i7-13620H")
        self.assertEqual(attrs.get("laptop_ram"), "16GB")

    # ---------------------------------------------------------
    # 15. DOM ATTRIBUTES FALLBACK
    # ---------------------------------------------------------
    def test_15_dom_attributes_fallback(self):
        """Kiểm tra fallback sang DOM parser khi JSON-LD và GraphQL đều rỗng."""
        mock_html = """
        <html>
        <body>
            <div class="technical-content">
                <div class="technical-content-item">Màn hình: 6.7 inches OLED</div>
                <div class="technical-content-item">Camera: 48 MP</div>
            </div>
        </body>
        </html>
        """
        attrs = self.phone_spider.extract_dom_attributes(mock_html)
        self.assertEqual(attrs.get("Màn hình"), "6.7 inches OLED")
        self.assertEqual(attrs.get("Camera"), "48 MP")

    # ---------------------------------------------------------
    # 16. REVIEW PARSING
    # ---------------------------------------------------------
    def test_16_review_parsing(self):
        """Kiểm tra parse review response tạo TechReviewRawItem với các trường đầy đủ."""
        mock_review_response = {
            "data": {
                "reviews": {
                    "matches": [
                        {
                            "id": "rev_101",
                            "content": "Máy dùng rất mượt và pin trâu",
                            "rating_id": 5,
                            "created_at": "2026-09-10 14:30:00",
                            "customer": {"id": 555, "fullname": "Nguyễn Văn A"},
                            "children": [],
                            "photos": ["https://cdn.cellphones.com.vn/photo1.jpg"],
                        }
                    ],
                    "total": 1,
                }
            }
        }
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "1001", "parent_url": "https://cellphones.com.vn/p1001.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_review_response).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        items = list(self.phone_spider.parse_reviews(res))
        self.assertEqual(len(items), 1)
        rev = items[0]
        self.assertEqual(rev["review_id_raw"], "rev_101")
        self.assertEqual(rev["author_raw"], "Nguyễn Văn A")
        self.assertEqual(rev["rating_raw"], 5)
        self.assertEqual(rev["review_text_raw"], "Máy dùng rất mượt và pin trâu")
        self.assertEqual(rev["attached_files_raw"], ["https://cdn.cellphones.com.vn/photo1.jpg"])
        self.assertIsNone(rev["like_count_raw"])

    # ---------------------------------------------------------
    # 17. REVIEW PAGINATION 1-BASED
    # ---------------------------------------------------------
    def test_17_review_pagination_1_based(self):
        """Kiểm tra review request bắt đầu từ page 1 và tiếp tục page 2 khi total > 5."""
        spider = CellphonesSmartphoneSpider(batch_id="test", crawl_reviews=True)
        # 5 items trên page 1, total = 8 -> cần request page 2
        mock_matches = [{"id": f"rev_{i}", "content": "Ok", "rating_id": 5} for i in range(1, 6)]
        mock_resp = {"data": {"reviews": {"matches": mock_matches, "total": 8}}}

        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "1001", "parent_url": "https://cellphones.com.vn/p1001.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(spider.parse_reviews(res))
        rev_items = [r for r in results if isinstance(r, TechReviewRawItem)]
        next_reqs = [r for r in results if isinstance(r, scrapy.Request)]

        self.assertEqual(len(rev_items), 5)
        self.assertEqual(len(next_reqs), 1)
        self.assertEqual(next_reqs[0].meta["page"], 2)

    # ---------------------------------------------------------
    # 18. REVIEW PAGE SIZE 5
    # ---------------------------------------------------------
    def test_18_review_page_size_5(self):
        """Kiểm tra CellphoneS review phân trang với bước cố định 5 reviews/page."""
        self.assertEqual(self.phone_spider.review_page_size, 5)
        # Khi page 1 có 5 items và total = 5 thì KHÔNG lên lịch page 2
        mock_matches = [{"id": f"r_{i}", "content": "test"} for i in range(5)]
        mock_resp = {"data": {"reviews": {"matches": mock_matches, "total": 5}}}
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "1001", "parent_url": "https://cellphones.com.vn/p1001.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        results = list(self.phone_spider.parse_reviews(res))
        next_reqs = [r for r in results if isinstance(r, scrapy.Request)]
        self.assertEqual(len(next_reqs), 0)

    # ---------------------------------------------------------
    # 19. REVIEW PARENT LINKAGE
    # ---------------------------------------------------------
    def test_19_review_parent_linkage(self):
        """Kiểm tra review được liên kết chính xác với parent product ID và parent URL."""
        mock_resp = {
            "data": {
                "reviews": {
                    "matches": [{"id": "r_99", "content": "Good"}],
                    "total": 1,
                }
            }
        }
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "parent_xyz", "parent_url": "https://cellphones.com.vn/parent_xyz.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        items = list(self.phone_spider.parse_reviews(res))
        self.assertEqual(items[0]["parent_product_id_raw"], "parent_xyz")
        self.assertEqual(items[0]["parent_product_url_raw"], "https://cellphones.com.vn/parent_xyz.html")

    # ---------------------------------------------------------
    # 20. REVIEW VARIANT SKU REMAINS NONE (INVARIANT MANDATORY)
    # ---------------------------------------------------------
    def test_20_review_variant_sku_remains_none(self):
        """Kiểm tra bất biến: CellphoneS review không có reliable variant SKU, 3 trường linkage biến thể phải là None."""
        mock_resp = {
            "data": {
                "reviews": {
                    "matches": [{"id": "r_linkage_test", "content": "Review content"}],
                    "total": 1,
                }
            }
        }
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "123", "parent_url": "https://cellphones.com.vn/123.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        items = list(self.phone_spider.parse_reviews(res))
        rev = items[0]
        self.assertIsNone(rev["review_product_code_raw"])
        self.assertIsNone(rev["variant_code_raw"])
        self.assertIsNone(rev["variant_sku_raw"])

    # ---------------------------------------------------------
    # 21. PRODUCT SCHEMA = 25 FIELDS
    # ---------------------------------------------------------
    def test_21_product_schema_25_fields(self):
        """Kiểm tra TechProductRawItem có đúng 25 fields canonical."""
        parent_meta = {
            "parent_id": "1",
            "parent_name": "P",
            "parent_sku": "SKU",
            "brand": "B",
            "parent_url": "https://cellphones.com.vn/p.html",
            "rating": 5,
            "review_count": 1,
            "general_attrs": {},
            "raw_payload": {},
        }
        items = list(self.phone_spider.yield_product_items(parent_meta, None, {}))
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(len(it.fields), 25)
        for f in EXPECTED_PRODUCT_FIELDS:
            self.assertIn(f, it.fields)

    # ---------------------------------------------------------
    # 22. REVIEW SCHEMA = 19 FIELDS
    # ---------------------------------------------------------
    def test_22_review_schema_19_fields(self):
        """Kiểm tra TechReviewRawItem có đúng 19 fields canonical."""
        rev = TechReviewRawItem()
        self.assertEqual(len(rev.fields), 19)
        for f in EXPECTED_REVIEW_FIELDS:
            self.assertIn(f, rev.fields)

    # ---------------------------------------------------------
    # 23. IMMUTABLE OUTPUT BEHAVIOR
    # ---------------------------------------------------------
    def test_23_immutable_output_behavior(self):
        """Kiểm tra ensure_output_path_available từ chối ghi đè lên file snapshot đã tồn tại."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            self.assertTrue(tmp_path.exists())
            with self.assertRaises(FileExistsError):
                ensure_output_path_available(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    # ---------------------------------------------------------
    # 24. DUPLICATE VARIANT KEY DETECTION
    # ---------------------------------------------------------
    def test_24_duplicate_variant_key_detection(self):
        """Kiểm tra tính duy nhất của cặp (parent_product_id_raw, variant_sku_raw)."""
        parent_meta = {
            "parent_id": "100",
            "parent_name": "Multi Phone",
            "parent_sku": "PARENT-SKU",
            "brand": "Apple",
            "parent_url": "https://cellphones.com.vn/p100.html",
            "rating": 5,
            "review_count": 1,
            "general_attrs": {},
            "raw_payload": {},
        }
        children = [
            {"general": {"product_id": "101", "name": "V1", "sku": "SKU-A"}, "filterable": {"price": 1000}},
            {"general": {"product_id": "102", "name": "V2", "sku": "SKU-B"}, "filterable": {"price": 2000}},
        ]
        items = list(self.phone_spider.yield_product_items(parent_meta, children, {}))
        keys = [(it["parent_product_id_raw"], it["variant_sku_raw"]) for it in items]
        self.assertEqual(len(keys), len(set(keys)))

    # ---------------------------------------------------------
    # 25. DUPLICATE REVIEW ID DETECTION
    # ---------------------------------------------------------
    def test_25_duplicate_review_id_detection(self):
        """Kiểm tra seen_review_ids lọc bỏ các review bị lặp lại."""
        spider = CellphonesSmartphoneSpider(crawl_reviews=True)
        mock_resp = {
            "data": {
                "reviews": {
                    "matches": [
                        {"id": "duplicate_id", "content": "Review 1"},
                        {"id": "duplicate_id", "content": "Review 1 duplicate"},
                    ],
                    "total": 2,
                }
            }
        }
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "1001", "parent_url": "https://cellphones.com.vn/p.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        items = list(spider.parse_reviews(res))
        self.assertEqual(len(items), 1)  # Chỉ có 1 review được yield

    # ---------------------------------------------------------
    # 26. SOURCE ALL INCLUDES CELLPHONES
    # ---------------------------------------------------------
    def test_26_source_all_includes_cellphones(self):
        """Kiểm tra CLI runner: --source all bao gồm ['tgdd', 'fptshop', 'cellphones'] và choices chỉ dùng canonical."""
        parser = build_argument_parser()

        # Kiểm tra choices có canonical 'cellphones' và các nguồn đã đăng ký
        source_action = [a for a in parser._actions if a.dest == "source"][0]
        self.assertIn("cellphones", source_action.choices)
        self.assertTrue({"tgdd", "fptshop", "cellphones", "all"}.issubset(set(source_action.choices)))

        # Phân giải --source all (chỉ gồm các nguồn đã implemented)
        from crawler.run_crawler import SOURCE_REGISTRY
        args_all = parser.parse_args(["--source", "all"])
        sources_all = [s for s, meta in SOURCE_REGISTRY.items() if meta["implemented"]] if args_all.source == "all" else [args_all.source]
        self.assertEqual(sources_all, ["tgdd", "fptshop", "cellphones"])
        self.assertIn("cellphones", sources_all)
        self.assertNotIn("viettelstore", sources_all)
        self.assertNotIn("hoanghamobile", sources_all)

        # Phân giải --source cellphones
        args_cellphones = parser.parse_args(["--source", "cellphones"])
        self.assertEqual(args_cellphones.source, "cellphones")

    # ---------------------------------------------------------
    # 27. REVIEW LIKE COUNT RAW IS NONE
    # ---------------------------------------------------------
    def test_27_review_like_count_raw_is_none(self):
        """Kiểm tra like_count_raw của CellphoneS luôn là None vì nguồn không cung cấp trực tiếp (không ép thành 0)."""
        spider = CellphonesSmartphoneSpider(crawl_reviews=True)
        mock_resp = {
            "data": {
                "reviews": {
                    "matches": [
                        {
                            "id": "rev_999",
                            "content": "Máy rất đẹp và mượt",
                            "rating_id": 5,
                            "created_at": "2026-10-14 12:00:00",
                            "customer": {"fullname": "Lê Văn B"},
                        }
                    ],
                    "total": 1,
                }
            }
        }
        req = scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            meta={"parent_id": "8888", "parent_url": "https://cellphones.com.vn/p8888.html", "page": 1},
        )
        res = TextResponse(
            url=REVIEW_GRAPHQL_URL,
            body=json.dumps(mock_resp).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )
        items = list(spider.parse_reviews(res))
        self.assertEqual(len(items), 1)
        rev = items[0]
        self.assertIsNone(rev["like_count_raw"], "like_count_raw phải là None khi nguồn không cung cấp")

    # ---------------------------------------------------------
    # 28. CANONICAL SCHEMAS FIELDS COUNT AND KEYS
    # ---------------------------------------------------------
    def test_28_canonical_schemas_fields_count_and_keys(self):
        """Kiểm tra nghiêm ngặt Product schema = đúng 25 fields và Review schema = đúng 19 fields."""
        prod = TechProductRawItem()
        rev = TechReviewRawItem()

        self.assertEqual(len(prod.fields), 25, "Product schema phải có chính xác 25 fields")
        self.assertEqual(set(prod.fields.keys()), EXPECTED_PRODUCT_FIELDS)

        self.assertEqual(len(rev.fields), 19, "Review schema phải có chính xác 19 fields")
        self.assertEqual(set(rev.fields.keys()), EXPECTED_REVIEW_FIELDS)

    # ---------------------------------------------------------
    # 29. FALLBACK PARENT VARIANT SEMANTICS
    # ---------------------------------------------------------
    def test_29_fallback_parent_variant_semantics(self):
        """
        Kiểm tra semantic của fallback parent khi không có child_product:
        1. fallback parent có variant_sku_raw is None
        2. fallback parent có variant_name_raw is None
        3. fallback parent có variant_color_raw is None
        4. fallback parent có variant_url_raw is None
        5. fallback parent vẫn giữ sku_raw của parent
        """
        parent_meta = {
            "parent_id": "9999",
            "parent_name": "Laptop Acer Swift 3",
            "parent_sku": "ACER-SWIFT-3-SKU",
            "brand": "Acer",
            "parent_url": "https://cellphones.com.vn/laptop-acer-swift-3.html",
            "rating": 4.5,
            "review_count": 12,
            "general_attrs": {},
            "parent_filt": {"price": 18990000, "special_price": 16990000, "stock": 4},
            "raw_payload": {"general": {"product_id": 9999}, "filterable": {"stock": 4}},
        }

        items = list(self.laptop_spider.yield_product_items(parent_meta, child_variants=None, attributes={"CPU": "Core i5"}))
        self.assertEqual(len(items), 1)
        item = items[0]

        # 1. fallback parent có variant_sku_raw is None
        self.assertIsNone(item["variant_sku_raw"], "fallback parent có variant_sku_raw is None")

        # 2. fallback parent có variant_name_raw is None
        self.assertIsNone(item["variant_name_raw"], "fallback parent có variant_name_raw is None")

        # 3. fallback parent có variant_color_raw is None
        self.assertIsNone(item["variant_color_raw"], "fallback parent có variant_color_raw is None")

        # 4. fallback parent có variant_url_raw is None
        self.assertIsNone(item["variant_url_raw"], "fallback parent có variant_url_raw is None")

        # 5. fallback parent vẫn giữ sku_raw của parent
        self.assertEqual(item["sku_raw"], "ACER-SWIFT-3-SKU", "fallback parent vẫn giữ sku_raw của parent")

        # Ràng buộc định danh và contract khác
        self.assertEqual(item["product_id_raw"], "9999")
        self.assertEqual(item["parent_product_id_raw"], "9999")
        self.assertEqual(item["product_name_raw"], "Laptop Acer Swift 3")
        self.assertEqual(item["parent_product_name_raw"], "Laptop Acer Swift 3")
        self.assertEqual(item["product_url_raw"], "https://cellphones.com.vn/laptop-acer-swift-3.html")
        self.assertEqual(item["parent_url_raw"], "https://cellphones.com.vn/laptop-acer-swift-3.html")
        self.assertEqual(item["availability_raw"], 4)
        self.assertEqual(item["price_raw"], 16990000)
        self.assertEqual(item["original_price_raw"], 18990000)
        self.assertEqual(item["raw_payload"], parent_meta["raw_payload"])

    # ---------------------------------------------------------
    # 30. START REQUESTS & ASYNC START COMPATIBILITY
    # ---------------------------------------------------------
    def test_30_start_requests_and_async_start_compatibility(self):
        """
        Kiểm tra start_requests() tương thích Scrapy version cũ và start() async generator:
        - start_requests() sinh đúng 1 request ban đầu với page=1 (không bắt đầu từ page 0).
        - start() async generator delegate đúng đến start_requests().
        """
        import asyncio

        # 1. start_requests() đồng bộ (chuẩn Scrapy Spider)
        reqs = list(self.phone_spider.start_requests())
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].meta["page"], 1)
        self.assertEqual(reqs[0].method, "POST")
        self.assertFalse(reqs[0].dont_filter, "start request không đặt dont_filter=True")

        # 2. start() async generator (Scrapy 2.13+)
        async def _collect():
            res = []
            async for req in self.phone_spider.start():
                res.append(req)
            return res

        async_reqs = asyncio.run(_collect())
        self.assertEqual(len(async_reqs), 1)
        self.assertEqual(async_reqs[0].meta["page"], 1)
        self.assertEqual(async_reqs[0].url, reqs[0].url)

    # ---------------------------------------------------------
    # 31. SPECIAL_PRICE SEVEN CASES
    # ---------------------------------------------------------
    def test_31_price_special_price_seven_cases(self):
        """
        Kiểm tra xử lý special_price cho đủ 7 trường hợp:
        1. int > 0
        2. float > 0
        3. numeric string > 0
        4. "0"
        5. None
        6. invalid string
        7. bool (True/False không được coi là price)
        """
        from crawler.cellphoneS.base_spider import CellphonesBaseSpider

        # Kiểm tra helper _parse_positive_price
        self.assertEqual(CellphonesBaseSpider._parse_positive_price(18000000), 18000000)
        self.assertEqual(CellphonesBaseSpider._parse_positive_price(18000000.5), 18000000.5)
        self.assertEqual(CellphonesBaseSpider._parse_positive_price("18000000"), 18000000)
        self.assertEqual(CellphonesBaseSpider._parse_positive_price("18000000.5"), 18000000.5)
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price("0"))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price(0))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price(None))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price("invalid_price"))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price(""))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price(True))
        self.assertIsNone(CellphonesBaseSpider._parse_positive_price(False))

        # Kiểm tra áp dụng trong yield_product_items cho cả 7 trường hợp
        parent_meta = {
            "parent_id": "1",
            "parent_name": "Test Phone",
            "parent_sku": "SKU-P",
            "brand": "BrandX",
            "parent_url": "https://cellphones.com.vn/test-phone.html",
            "rating": 5.0,
            "review_count": 10,
            "general_attrs": {},
            "raw_payload": {},
        }
        list_price = 20000000

        cases = [
            (18000000, 18000000, "1. int"),
            (18500000.5, 18500000.5, "2. float"),
            ("17000000", 17000000, "3. numeric string"),
            ("0", list_price, "4. string 0"),
            (None, list_price, "5. None"),
            ("not_a_number", list_price, "6. invalid string"),
            (True, list_price, "7. bool True"),
            (False, list_price, "7. bool False"),
        ]

        for special_val, expected_current, label in cases:
            child = [
                {
                    "general": {"product_id": "c1", "name": f"Variant {label}", "sku": "SKU-C"},
                    "filterable": {"price": list_price, "special_price": special_val, "stock": 10},
                }
            ]
            items = list(self.phone_spider.yield_product_items(parent_meta, child, {}))
            self.assertEqual(
                items[0]["price_raw"],
                expected_current,
                f"Trường hợp {label} phải cho current_price={expected_current}, thực tế: {items[0]['price_raw']}",
            )
            self.assertEqual(
                items[0]["original_price_raw"],
                list_price,
                f"Trường hợp {label} original_price phải là list_price={list_price}",
            )

    # ---------------------------------------------------------
    # 32. JSON-LD ATTRIBUTES @GRAPH SUPPORT
    # ---------------------------------------------------------
    def test_32_jsonld_attributes_graph_support(self):
        """
        Kiểm tra extract_jsonld_attributes hỗ trợ:
        - Object trực tiếp có additionalProperty
        - List JSON-LD
        - @graph chứa Product/ProductGroup có additionalProperty
        - Thứ tự ưu tiên: 1. JSON-LD > 2. GraphQL general.attributes > 3. DOM
        """
        # Case A: Object trực tiếp
        html_direct = """
        <html><head>
        <script type="application/ld+json">
        {
            "@type": "Product",
            "additionalProperty": [
                {"name": "RAM", "value": "16 GB"},
                {"name": "CPU", "value": "Apple M4"}
            ]
        }
        </script>
        </head></html>
        """
        attrs_direct = self.laptop_spider.extract_jsonld_attributes(html_direct)
        self.assertEqual(attrs_direct.get("RAM"), "16 GB")
        self.assertEqual(attrs_direct.get("CPU"), "Apple M4")

        # Case B: List JSON-LD
        html_list = """
        <html><head>
        <script type="application/ld+json">
        [
            {"@type": "BreadcrumbList"},
            {
                "@type": "Product",
                "additionalProperty": [
                    {"name": "Màn hình", "value": "14 inch OLED"}
                ]
            }
        ]
        </script>
        </head></html>
        """
        attrs_list = self.laptop_spider.extract_jsonld_attributes(html_list)
        self.assertEqual(attrs_list.get("Màn hình"), "14 inch OLED")

        # Case C: @graph chứa Product
        html_graph = """
        <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "name": "CellphoneS"},
                {
                    "@type": "ProductGroup",
                    "name": "Asus Zenbook 14",
                    "additionalProperty": [
                        {"name": "Bộ vi xử lý", "value": "Intel Core Ultra 7"},
                        {"name": "Ổ cứng", "value": "1 TB SSD"}
                    ]
                }
            ]
        }
        </script>
        </head></html>
        """
        attrs_graph = self.laptop_spider.extract_jsonld_attributes(html_graph)
        self.assertEqual(attrs_graph.get("Bộ vi xử lý"), "Intel Core Ultra 7")
        self.assertEqual(attrs_graph.get("Ổ cứng"), "1 TB SSD")

    # ---------------------------------------------------------
    # 33. SEMANTIC PARENT DEDUP REGRESSION
    # ---------------------------------------------------------
    def test_33_semantic_parent_dedup_regression(self):
        """
        Kiểm tra regression chống duplicate semantic parent:
        - Parent xuất hiện ở Page 1 được dispatch downstream request.
        - Nếu parent đó lại xuất hiện ở Page 2, nó bị bỏ qua ngay tại parse_listing.
        - Không tạo duplicate downstream child_variants / detail / review request.
        - unique_parents_collected không bị double count.
        """
        spider = CellphonesSmartphoneSpider(batch_id="20261016_dedup_test", crawl_reviews=True)

        # Page 1: chứa Parent 1001 và 1002
        page1_body = {
            "data": {
                "products": [
                    {"general": {"product_id": 1001, "name": "Phone A", "child_product": [2001]}},
                    {"general": {"product_id": 1002, "name": "Phone B", "child_product": [2002]}},
                ]
            }
        }
        req1 = scrapy.Request(url="https://api.cellphones.com.vn/v2/graphql/query", meta={"page": 1})
        resp1 = TextResponse(
            url=req1.url,
            body=json.dumps(page1_body).encode("utf-8"),
            encoding="utf-8",
            request=req1,
        )
        yielded_page1 = list(spider.parse_listing(resp1))

        # Kiểm tra Page 1 yield 2 child requests
        child_reqs_p1 = [r for r in yielded_page1 if r.callback == spider.parse_child_variants]
        self.assertEqual(len(child_reqs_p1), 2)
        self.assertEqual(spider.unique_parents_collected, 2)
        self.assertIn("1001", spider.seen_parent_ids)
        self.assertIn("1002", spider.seen_parent_ids)

        # Page 2: lặp lại Parent 1001 và có thêm Parent mới 1003
        page2_body = {
            "data": {
                "products": [
                    {"general": {"product_id": 1001, "name": "Phone A Repeat", "child_product": [2001]}},
                    {"general": {"product_id": 1003, "name": "Phone C New", "child_product": [2003]}},
                ]
            }
        }
        req2 = scrapy.Request(url="https://api.cellphones.com.vn/v2/graphql/query", meta={"page": 2})
        resp2 = TextResponse(
            url=req2.url,
            body=json.dumps(page2_body).encode("utf-8"),
            encoding="utf-8",
            request=req2,
        )
        yielded_page2 = list(spider.parse_listing(resp2))

        # Kiểm tra Page 2 CHỈ yield child request cho Parent 1003 mới, KHÔNG lặp lại 1001
        child_reqs_p2 = [r for r in yielded_page2 if r.callback == spider.parse_child_variants]
        self.assertEqual(len(child_reqs_p2), 1)
        self.assertEqual(child_reqs_p2[0].meta["child_ids"], ["2003"])
        self.assertEqual(spider.unique_parents_collected, 3)


