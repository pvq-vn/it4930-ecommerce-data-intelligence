import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy.http import HtmlResponse, Request, TextResponse

from crawler.viettelStore.base_spider import (
    GET_USER_CONTROL_ASYNC_URL,
    ViettelstoreBaseSpider,
)
from crawler.viettelStore.items import TechProductRawItem, TechReviewRawItem
from crawler.viettelStore.pipelines import ViettelstoreReviewExportPipeline
from crawler.viettelStore.viettelstore_laptop_spider import ViettelstoreLaptopSpider
from crawler.viettelStore.viettelstore_smartphone_spider import ViettelstoreSmartphoneSpider

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

# ---------------------------------------------------------------------------
# MOCK FIXTURES (dựa trên cấu trúc thực tế của Viettel Store)
# ---------------------------------------------------------------------------

MOCK_VIETTEL_LISTING_HTML = """
<div class="product-item">
    <a href="/dien-thoai/samsung-galaxy-s25-ultra-pid343211.html">
        <h3 class="name">Samsung Galaxy S25 Ultra 12GB 256GB</h3>
    </a>
    <div class="price">23.990.000 ₫</div>
    <div class="price-old">33.380.000 ₫</div>
</div>
<div class="product-item">
    <a href="/dien-thoai/iphone-17-pro-max-pid355082.html">
        <h3 class="name">iPhone 17 Pro Max 256GB</h3>
    </a>
    <div class="price">38.490.000 ₫</div>
    <div class="price-old">41.990.000 ₫</div>
</div>
<div class="product-item">
    <a href="/laptop/mtxt-dell15-dc15250-cph995-pid371092.html">
        <h3 class="name">MTXT DELL 15 DC15250 Core 3-100U (CPH995)</h3>
    </a>
    <div class="price">20.590.000 ₫</div>
    <div class="price-old">22.990.000 ₫</div>
</div>
"""

MOCK_VIETTEL_DETAIL_PHONE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Samsung Galaxy S25 Ultra ưu đãi - ViettelStore.vn</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org/",
      "@type": "Product",
      "name": "Samsung Galaxy S25 Ultra 12GB 256GB",
      "brand": {
        "@type": "Brand",
        "name": "Samsung"
      },
      "sku": "343211",
      "offers": {
        "@type": "Offer",
        "priceCurrency": "VND",
        "price": "23990000",
        "availability": "https://schema.org/InStock"
      },
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": 4.87,
        "reviewCount": 63
      },
      "additionalProperty": [
        {"type": "PropertyValue", "name": "Chipset", "value": "Snapdragon 8 Elite"},
        {"type": "PropertyValue", "name": "RAM", "value": "12GB"},
        {"type": "PropertyValue", "name": "Bộ nhớ trong", "value": "256GB"},
        {"type": "PropertyValue", "name": "Kích thước màn hình", "value": "6.9 inches"}
      ],
      "review": [
        {
          "@type": "Review",
          "author": {"@type": "Person", "name": "Nguyễn Văn A"},
          "reviewRating": {"@type": "Rating", "ratingValue": 5},
          "reviewBody": "Máy dùng rất mượt và pin trâu",
          "datePublished": "2026-02-15"
        }
      ]
    }
    </script>
</head>
<body>
    <div class="product-name">Samsung Galaxy S25 Ultra 12GB 256GB</div>
    <div class="price">23.990.000 ₫</div>
    <div class="price-old">33.380.000 ₫</div>
    <div class="detail-rating-chart">
        <div class="rating-item"><span class="rating-level">Tuyệt vời</span><span class="rating-counter">61</span></div>
        <div class="rating-item"><span class="rating-level">Rất tốt</span><span class="rating-counter">0</span></div>
        <div class="rating-item"><span class="rating-level">Bình thường</span><span class="rating-counter">0</span></div>
        <div class="rating-item"><span class="rating-level">Tạm được</span><span class="rating-counter">0</span></div>
        <div class="rating-item"><span class="rating-level">Không thích</span><span class="rating-counter">2</span></div>
    </div>
    <div class="promotion">
        Trả góp 0% tính trên mức giá 24.990.000 ₫
    </div>
</body>
</html>
"""

MOCK_VIETTEL_DETAIL_LAPTOP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Laptop Asus Vivobook - ViettelStore.vn</title>
    <script type="application/ld+json">
    {
      "@context": "https://schema.org/",
      "@type": "Product",
      "name": "MTXT ASUS Vivobook 14 (X1404MA-EB027W)",
      "brand": "ASUS",
      "sku": "370913",
      "offers": {
        "@type": "Offer",
        "priceCurrency": "VND",
        "price": "17990000",
        "availability": "https://schema.org/InStock"
      },
      "additionalProperty": [
        {"type": "PropertyValue", "name": "CPU", "value": "Core 3-304"},
        {"type": "PropertyValue", "name": "RAM", "value": "8GB"}
      ]
    }
    </script>
</head>
<body>
    <div class="product-name">MTXT ASUS Vivobook 14 (X1404MA-EB027W)</div>
    <div class="price">17.990.000 ₫</div>
    <div class="price-old">22.990.000 ₫</div>
    <div class="promotion-detail">
        Trả góp 0% kỳ hạn 6 tháng tính trên mức giá 18.990.000 ₫
    </div>
</body>
</html>
"""

MOCK_VIETTEL_DETAIL_LIEN_HE_HTML = """
<!DOCTYPE html>
<html>
<body>
    <div class="product-name">Samsung Galaxy Z Fold7 5G 1TB</div>
    <div class="price">Liên hệ</div>
</body>
</html>
"""


def _make_html_response(url: str, body: str, meta: dict = None, status: int = 200) -> HtmlResponse:
    req = scrapy.Request(url=url, meta=meta or {})
    return HtmlResponse(
        url=url,
        status=status,
        body=body.encode("utf-8") if isinstance(body, str) else body,
        encoding="utf-8",
        request=req,
    )


class TestViettelstoreCrawler(unittest.TestCase):
    """Bộ test toàn diện cho crawler Viettel Store."""

    def setUp(self):
        self.phone_spider = ViettelstoreSmartphoneSpider(batch_id="20261017_vts_phone", crawl_reviews=True)
        self.laptop_spider = ViettelstoreLaptopSpider(batch_id="20261017_vts_laptop", crawl_reviews=True)

    # ---------------------------------------------------------
    # 1. CANONICAL CONTRACT & SCHEMA FIELD SETS
    # ---------------------------------------------------------
    def test_canonical_product_contract_25_fields(self):
        """Đảm bảo TechProductRawItem có đúng 25 trường chuẩn tắc."""
        self.assertEqual(len(EXPECTED_PRODUCT_FIELDS), 25)
        item = TechProductRawItem()
        for f in EXPECTED_PRODUCT_FIELDS:
            self.assertIn(f, item.fields)

    def test_canonical_review_contract_19_fields(self):
        """Đảm bảo TechReviewRawItem có đúng 19 trường chuẩn tắc."""
        self.assertEqual(len(EXPECTED_REVIEW_FIELDS), 19)
        item = TechReviewRawItem()
        for f in EXPECTED_REVIEW_FIELDS:
            self.assertIn(f, item.fields)

    # ---------------------------------------------------------
    # 2. SPIDER SUBCLASSES CONFIGURATION
    # ---------------------------------------------------------
    def test_subclasses_configuration(self):
        """Kiểm tra cấu hình category và cat_id cho smartphone và laptop."""
        self.assertEqual(self.phone_spider.category, "smartphone")
        self.assertEqual(self.phone_spider.cat_id, "010001")
        self.assertEqual(self.phone_spider.name, "viettelstore_smartphone")

        self.assertEqual(self.laptop_spider.category, "laptop")
        self.assertEqual(self.laptop_spider.cat_id, "010002")
        self.assertEqual(self.laptop_spider.name, "viettelstore_laptop")

    # ---------------------------------------------------------
    # 3. PAGINATION REQUEST GENERATION
    # ---------------------------------------------------------
    def test_make_listing_request_parameters(self):
        """Kiểm tra request phân trang gửi đúng endpoint XHR và POST formdata."""
        req = self.phone_spider.make_listing_request(page=1)
        self.assertEqual(req.url, GET_USER_CONTROL_ASYNC_URL)
        self.assertEqual(req.method, "POST")
        self.assertIn(b"CatID=010001", req.body)
        self.assertIn(b"CurrentPage=1", req.body)
        self.assertIn(b"ProductList5Col2026", req.body)
        self.assertEqual(req.meta["page"], 1)

    def test_start_requests_and_async_start_compatibility(self):
        """
        Kiểm tra start_requests() và start() async generator tương thích Scrapy 2.19:
        - start_requests() sinh đúng 1 request ban đầu với page=1.
        - start() async generator sinh đúng 1 request ban đầu với page=1.
        """
        import asyncio

        # 1. start_requests() đồng bộ (fallback/test)
        reqs = list(self.phone_spider.start_requests())
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs[0].meta["page"], 1)
        self.assertEqual(reqs[0].method, "POST")
        self.assertIn(b"CatID=010001", reqs[0].body)

        # 2. start() async generator (Scrapy 2.19)
        async def _collect():
            res = []
            async for req in self.phone_spider.start():
                res.append(req)
            return res

        async_reqs = asyncio.run(_collect())
        self.assertEqual(len(async_reqs), 1)
        self.assertEqual(async_reqs[0].meta["page"], 1)
        self.assertEqual(async_reqs[0].method, "POST")
        self.assertIn(b"CatID=010001", async_reqs[0].body)

    # ---------------------------------------------------------
    # 4. LISTING PARSING & DEDUPLICATION
    # ---------------------------------------------------------
    def test_parse_listing_extracts_items_and_schedules_details(self):
        """Kiểm tra parse_listing trích xuất đúng sản phẩm và lên lịch detail request."""
        res = _make_html_response(
            url=GET_USER_CONTROL_ASYNC_URL,
            body=MOCK_VIETTEL_LISTING_HTML,
            meta={"page": 1},
        )
        requests = list(self.phone_spider.parse_listing(res))
        detail_reqs = [r for r in requests if r.callback == self.phone_spider.parse_detail]
        next_page_reqs = [r for r in requests if r.callback == self.phone_spider.parse_listing]

        self.assertEqual(len(detail_reqs), 3)
        self.assertEqual(self.phone_spider.scheduled_products, 3)

        # Kiểm tra pid và metadata
        pids = [r.meta["pid"] for r in detail_reqs]
        self.assertEqual(pids, ["343211", "355082", "371092"])
        self.assertTrue(all(pid in self.phone_spider.seen_pids for pid in pids))

        # Kiểm tra next page request
        self.assertEqual(len(next_page_reqs), 1)
        self.assertEqual(next_page_reqs[0].meta["page"], 2)

    def test_listing_deduplication_gate_prevents_duplicates(self):
        """Kiểm tra duplicate pid bị loại bỏ, không lên lịch request trùng."""
        self.phone_spider.seen_pids.add("343211")  # giả lập đã thấy pid 343211

        res = _make_html_response(
            url=GET_USER_CONTROL_ASYNC_URL,
            body=MOCK_VIETTEL_LISTING_HTML,
            meta={"page": 1},
        )
        requests = list(self.phone_spider.parse_listing(res))
        detail_reqs = [r for r in requests if r.callback == self.phone_spider.parse_detail]

        # Chỉ lên lịch 2 sản phẩm còn lại (355082 và 371092)
        self.assertEqual(len(detail_reqs), 2)
        pids = [r.meta["pid"] for r in detail_reqs]
        self.assertNotIn("343211", pids)

    def test_pagination_termination_on_empty_page(self):
        """Kiểm tra phân trang kết thúc an toàn khi trang rỗng."""
        empty_res = _make_html_response(
            url=GET_USER_CONTROL_ASYNC_URL,
            body="<div>Khong tim thay san pham nao</div>",
            meta={"page": 5},
        )
        results = list(self.phone_spider.parse_listing(empty_res))
        self.assertEqual(len(results), 0)
        self.assertEqual(self.phone_spider.stop_reason, "no_more_products")

    def test_pagination_termination_on_repeated_signature(self):
        """Kiểm tra phân trang kết thúc an toàn khi page signature bị lặp."""
        res = _make_html_response(
            url=GET_USER_CONTROL_ASYNC_URL,
            body=MOCK_VIETTEL_LISTING_HTML,
            meta={"page": 1},
        )
        list(self.phone_spider.parse_listing(res))
        # Lần 2 gửi lại đúng trang có cùng signature
        results2 = list(self.phone_spider.parse_listing(res))
        self.assertEqual(len(results2), 0)
        self.assertEqual(self.phone_spider.stop_reason, "repeated_page_signature")

    # ---------------------------------------------------------
    # 5. DETAIL PARSING & CANONICAL MAPPING
    # ---------------------------------------------------------
    def test_parse_detail_phone_all_25_fields(self):
        """Kiểm tra parse detail smartphone đầy đủ 25 trường và review liên kết."""
        res = _make_html_response(
            url="https://viettelstore.vn/dien-thoai/samsung-galaxy-s25-ultra-pid343211.html",
            body=MOCK_VIETTEL_DETAIL_PHONE_HTML,
            meta={"pid": "343211", "listing_data": {"price": "23.990.000 ₫"}},
        )
        items = list(self.phone_spider.parse_detail(res))

        prod_items = [it for it in items if isinstance(it, TechProductRawItem)]
        rev_items = [it for it in items if isinstance(it, TechReviewRawItem)]

        self.assertEqual(len(prod_items), 1)
        it = prod_items[0]

        # Kiểm tra đúng 25 fields
        self.assertEqual(set(it.keys()), EXPECTED_PRODUCT_FIELDS)
        self.assertEqual(it["source"], "viettelstore")
        self.assertEqual(it["category"], "smartphone")
        self.assertEqual(it["product_id_raw"], "343211")
        self.assertEqual(it["product_name_raw"], "Samsung Galaxy S25 Ultra 12GB 256GB")
        self.assertEqual(it["parent_product_id_raw"], "343211")
        self.assertEqual(it["price_raw"], "23.990.000 ₫")
        self.assertEqual(it["original_price_raw"], "33.380.000 ₫")
        self.assertEqual(it["brand_raw"], "Samsung")
        self.assertEqual(it["seller_raw"], "Viettel Store")
        self.assertEqual(it["availability_raw"], "Còn hàng")

        # Rating summary tính từ rating chart: 61 5-star + 2 1-star = 63, avg = 4.87
        self.assertEqual(it["review_count_raw"], 63)
        self.assertEqual(it["rating_raw"], 4.87)

        # Smartphone không forge SKU
        self.assertIsNone(it["sku_raw"])
        self.assertIsNone(it["variant_sku_raw"])

        # Technical attributes từ JSON-LD
        self.assertEqual(it["attributes_raw"]["Chipset"], "Snapdragon 8 Elite")
        self.assertEqual(it["attributes_raw"]["RAM"], "12GB")

        # Giá trả góp không làm nhiễm bẩn price_raw
        self.assertIn("installment_base_price_raw", it["attributes_raw"])
        self.assertNotEqual(it["price_raw"], it["attributes_raw"]["installment_base_price_raw"])

        # Review items
        self.assertEqual(len(rev_items), 1)
        rev = rev_items[0]
        self.assertEqual(set(rev.keys()), EXPECTED_REVIEW_FIELDS)
        self.assertEqual(rev["source"], "viettelstore")
        self.assertEqual(rev["parent_product_id_raw"], "343211")
        self.assertEqual(rev["author_raw"], "Nguyễn Văn A")
        self.assertEqual(rev["rating_raw"], 5)
        self.assertIsNone(rev["variant_sku_raw"])

    def test_parse_detail_laptop_mpn_sku_extraction(self):
        """Laptop bóc tách MPN ở cuối tên vào sku_raw và variant_sku_raw."""
        res = _make_html_response(
            url="https://viettelstore.vn/laptop/mtxt-asus-vivobook-14-pid370913.html",
            body=MOCK_VIETTEL_DETAIL_LAPTOP_HTML,
            meta={"pid": "370913"},
        )
        items = list(self.laptop_spider.parse_detail(res))
        prod_items = [it for it in items if isinstance(it, TechProductRawItem)]
        self.assertEqual(len(prod_items), 1)
        it = prod_items[0]

        self.assertEqual(it["sku_raw"], "X1404MA-EB027W")
        self.assertEqual(it["variant_sku_raw"], "X1404MA-EB027W")
        self.assertEqual(it["price_raw"], "17.990.000 ₫")
        self.assertEqual(it["original_price_raw"], "22.990.000 ₫")
        # Installment base price 18.990.000đ được bảo toàn riêng trong attributes
        self.assertEqual(it["attributes_raw"].get("installment_base_price_raw"), "18.990.000 ₫")
        self.assertNotEqual(it["price_raw"], "18.990.000 ₫")

    def test_parse_detail_lien_he_yields_none_price(self):
        """Sản phẩm 'Liên hệ' phải có price_raw=None và availability_raw='Liên hệ'."""
        res = _make_html_response(
            url="https://viettelstore.vn/dien-thoai/samsung-galaxy-z-fold7-pid368604.html",
            body=MOCK_VIETTEL_DETAIL_LIEN_HE_HTML,
            meta={"pid": "368604"},
        )
        items = list(self.phone_spider.parse_detail(res))
        it = [i for i in items if isinstance(i, TechProductRawItem)][0]

        self.assertIsNone(it["price_raw"])
        self.assertIsNone(it["original_price_raw"])
        self.assertEqual(it["availability_raw"], "Liên hệ")

    def test_malformed_detail_page_does_not_crash(self):
        """Trang detail thiếu thẻ hoặc hỏng HTML xử lý an toàn và bảo toàn dữ liệu từ listing."""
        res = _make_html_response(
            url="https://viettelstore.vn/dien-thoai/broken-page-pid999999.html",
            body="<html><body>Empty page</body></html>",
            meta={"pid": "999999", "listing_data": {"name": "Broken Phone", "price": "5.000.000 ₫"}},
        )
        items = list(self.phone_spider.parse_detail(res))
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertEqual(it["product_id_raw"], "999999")
        self.assertEqual(it["product_name_raw"], "Broken Phone")
        self.assertEqual(it["price_raw"], "5.000.000 ₫")
        self.assertIsNone(it["availability_raw"])

    # ---------------------------------------------------------
    # 6. AVAILABILITY, PRICE, PRODUCT ID & VARIANT SEMANTICS
    # ---------------------------------------------------------
    def test_availability_semantics_in_stock_and_out_of_stock(self):
        """Kiểm tra InStock -> Còn hàng, OutOfStock -> Tạm hết hàng."""
        in_stock_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "offers": {"availability": "https://schema.org/InStock", "price": "10000000"}}
        </script></head><body><div class="price">10.000.000 ₫</div></body></html>
        """
        res_in = _make_html_response("https://viettelstore.vn/phone-pid111.html", in_stock_html, meta={"pid": "111"})
        it_in = list(self.phone_spider.parse_detail(res_in))[0]
        self.assertEqual(it_in["availability_raw"], "Còn hàng")

        out_stock_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "offers": {"availability": "https://schema.org/OutOfStock", "price": "10000000"}}
        </script></head><body><div class="price">10.000.000 ₫</div></body></html>
        """
        res_out = _make_html_response("https://viettelstore.vn/phone-pid222.html", out_stock_html, meta={"pid": "222"})
        it_out = list(self.phone_spider.parse_detail(res_out))[0]
        self.assertEqual(it_out["availability_raw"], "Tạm hết hàng")

    def test_availability_no_evidence_remains_none(self):
        """BUG FIX #1: Không tìm thấy evidence tồn kho thì availability_raw là None, không default Còn hàng."""
        no_evidence_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "offers": {"price": "10000000"}}
        </script></head><body><div class="price">10.000.000 ₫</div></body></html>
        """
        res = _make_html_response("https://viettelstore.vn/phone-pid333.html", no_evidence_html, meta={"pid": "333"})
        it = list(self.phone_spider.parse_detail(res))[0]
        self.assertIsNone(it["availability_raw"], "Không có bằng chứng tồn kho thì availability_raw phải là None")

    def test_availability_listing_fallback_and_irrelevant_badge_ignored(self):
        """Listing có stock hợp lệ thì fallback, badge khuyến mãi/giảm giá không được coi là stock."""
        listing_with_valid_stock = {
            "name": "Phone A", "price": "5.000.000 ₫", "stock": "Số lượng có hạn"
        }
        res1 = _make_html_response("https://viettelstore.vn/phone-pid444.html", "<html><body><div class='price'>5.000.000 ₫</div></body></html>", meta={"pid": "444", "listing_data": listing_with_valid_stock})
        it1 = list(self.phone_spider.parse_detail(res1))[0]
        self.assertEqual(it1["availability_raw"], "Số lượng có hạn")

        # Listing với text không liên quan
        listing_with_irrelevant = {
            "name": "Phone B", "price": "5.000.000 ₫", "stock": None
        }
        res2 = _make_html_response("https://viettelstore.vn/phone-pid555.html", "<html><body><div class='price'>5.000.000 ₫</div></body></html>", meta={"pid": "555", "listing_data": listing_with_irrelevant})
        it2 = list(self.phone_spider.parse_detail(res2))[0]
        self.assertIsNone(it2["availability_raw"])

    def test_price_tightening_excludes_accessories_and_installments(self):
        """BUG FIX #2: Giá từ khối accessory và khối installment không được ghi đè price_raw."""
        html_complex_prices = """
        <html><body>
            <div class="box-installment">
                <span class="label">Trả góp 0%</span>
                <div class="price">1.500.000 ₫ / tháng</div>
            </div>
            <div class="accessories">
                <h4>Phụ kiện mua cùng</h4>
                <div class="price">150.000 ₫</div>
            </div>
            <div class="product-info">
                <h1>Điện thoại Test</h1>
                <div class="price">15.990.000 ₫</div>
                <div class="price-old">18.990.000 ₫</div>
            </div>
        </body></html>
        """
        res = _make_html_response("https://viettelstore.vn/phone-pid666.html", html_complex_prices, meta={"pid": "666"})
        it = list(self.phone_spider.parse_detail(res))[0]
        self.assertEqual(it["price_raw"], "15.990.000 ₫")
        self.assertEqual(it["original_price_raw"], "18.990.000 ₫")
        self.assertNotEqual(it["price_raw"], "1.500.000 ₫ / tháng")
        self.assertNotEqual(it["price_raw"], "150.000 ₫")

    def test_product_id_hierarchy(self):
        """Kiểm tra hierarchy của product_id_raw: pid URL -> sku numeric -> None."""
        # 1. pid từ URL
        res1 = _make_html_response("https://viettelstore.vn/phone-pid123456.html", "<html><body></body></html>", meta={"pid": "123456"})
        it1 = list(self.phone_spider.parse_detail(res1))[0]
        self.assertEqual(it1["product_id_raw"], "123456")

        # 2. Không có pid từ URL nhưng có JSON-LD sku numeric
        json_sku_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "sku": "789101"}
        </script></head><body></body></html>
        """
        res2 = _make_html_response("https://viettelstore.vn/phone-no-pid.html", json_sku_html, meta={"pid": None})
        it2 = list(self.phone_spider.parse_detail(res2))[0]
        self.assertEqual(it2["product_id_raw"], "789101")

        # 3. Không có pid hợp lệ -> None, không invent ID từ slug
        res3 = _make_html_response("https://viettelstore.vn/phone-unknown.html", "<html><body></body></html>", meta={"pid": None})
        it3 = list(self.phone_spider.parse_detail(res3))[0]
        self.assertIsNone(it3["product_id_raw"])

    def test_variant_semantics_ui_selector_does_not_duplicate(self):
        """BUG FIX #4: Trang có nhiều nút chọn màu/dung lượng UI không tự nhân bản variant records."""
        multi_ui_html = """
        <html><body>
            <div class="product-info">
                <h1>Điện thoại Flagship</h1>
                <div class="price">20.000.000 ₫</div>
                <div class="color-options">
                    <button class="btn-color">Titan Xanh</button>
                    <button class="btn-color">Titan Xám</button>
                    <button class="btn-color">Titan Đen</button>
                </div>
                <div class="storage-options">
                    <button class="btn-storage">256GB</button>
                    <button class="btn-storage">512GB</button>
                </div>
            </div>
        </body></html>
        """
        res = _make_html_response("https://viettelstore.vn/phone-pid777.html", multi_ui_html, meta={"pid": "777"})
        items = list(self.phone_spider.parse_detail(res))
        # Chỉ được sinh ĐÚNG 1 bản ghi TechProductRawItem
        prod_items = [i for i in items if isinstance(i, TechProductRawItem)]
        self.assertEqual(len(prod_items), 1)
        self.assertIsNone(prod_items[0]["variant_name_raw"])
        self.assertIsNone(prod_items[0]["variant_color_raw"])
        self.assertIsNone(prod_items[0]["variant_sku_raw"])

    # ---------------------------------------------------------
    # 6. PIPELINE & SNAPSHOT ISOLATION
    # ---------------------------------------------------------
    def test_viettelstore_pipeline_separates_product_and_reviews(self):
        """Pipeline ghi review ra file riêng và drop item để không trộn vào file product."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rev_path = Path(tmpdir) / "reviews.jsonl"
            spider = self.phone_spider
            spider.review_output = str(rev_path)

            pipeline = ViettelstoreReviewExportPipeline()
            pipeline.open_spider(spider)

            rev_item = TechReviewRawItem()
            rev_item["source"] = "viettelstore"
            rev_item["category"] = "smartphone"
            rev_item["crawl_batch"] = "test"
            rev_item["crawl_time"] = datetime.now().isoformat()
            rev_item["review_id_raw"] = "rev_01"
            rev_item["rating_raw"] = 5

            from scrapy.exceptions import DropItem
            with self.assertRaises(DropItem):
                pipeline.process_item(rev_item, spider)

            pipeline.close_spider(spider)

            self.assertTrue(rev_path.exists())
            with open(rev_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), 1)
            saved = json.loads(lines[0])
            self.assertEqual(saved["review_id_raw"], "rev_01")


if __name__ == "__main__":
    unittest.main()
