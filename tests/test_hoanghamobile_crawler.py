import json
import re
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import scrapy
from scrapy.http import HtmlResponse

from crawler.hoanghamobile.base_spider import (
    BASE_WEB_URL,
    HoanghamobileBaseSpider,
)
from crawler.hoanghamobile.hoanghamobile_laptop_spider import HoanghamobileLaptopSpider
from crawler.hoanghamobile.hoanghamobile_smartphone_spider import HoanghamobileSmartphoneSpider
from crawler.hoanghamobile.items import TechProductRawItem, TechReviewRawItem
from crawler.hoanghamobile.pipelines import HoanghamobileReviewExportPipeline

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
# MOCK FIXTURES (dựa trên cấu trúc thực tế của Hoàng Hà Mobile)
# ---------------------------------------------------------------------------

MOCK_HOANGHA_LISTING_HTML = """
<div class="v5-list-items">
    <div class="pj16-item-info">
        <h3>
            <a class="text-limit" href="/laptop/asus-zenbook-14-ux3405ca-st1713w" title="Laptop ASUS Zenbook 14 UX3405CA-ST1713W">
                Laptop ASUS Zenbook 14 UX3405CA-ST1713W
            </a>
        </h3>
        <div class="price-tags">
            <div class="price">
                <strong>29,290,000 ₫</strong>
            </div>
        </div>
        <div class="price price-last">
            <strike>38,990,000 ₫</strike>
            <span>- 25%</span>
        </div>
        <p class="price-tags price-tags-member">
            <span>Hoàng Hà Member chỉ từ</span>
            <strong>28,939,000 ₫</strong>
        </p>
    </div>

    <!-- Cùng một sản phẩm nhưng xuất hiện dưới tiền tố /lap-top/ để test dedup & URL normalization -->
    <div class="pj16-item-info">
        <h3>
            <a class="text-limit" href="/lap-top/asus-zenbook-14-ux3405ca-st1713w" title="Laptop ASUS Zenbook 14 UX3405CA-ST1713W">
                Laptop ASUS Zenbook 14 UX3405CA-ST1713W
            </a>
        </h3>
        <div class="price-tags">
            <div class="price">
                <strong>29,290,000 ₫</strong>
            </div>
        </div>
    </div>

    <div class="pj16-item-info">
        <h3>
            <a class="text-limit" href="/laptop/macbook-air-m1-2020-256gb" title="MacBook Air M1 2020 256GB">
                MacBook Air M1 2020 256GB
            </a>
        </h3>
        <div class="price-tags">
            <div class="price">
                <strong>18,490,000 ₫</strong>
            </div>
        </div>
        <div class="price price-last">
            <strike>19,990,000 ₫</strike>
        </div>
        <p class="price-tags price-tags-member">
            <strong>18,200,000 ₫</strong>
        </p>
    </div>
</div>

<div class="v5-more-product" id="page-pager">
    <a href="/laptop?p=2">Xem thêm 57 sản phẩm</a>
</div>
"""

MOCK_HOANGHA_DETAIL_LAPTOP_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Laptop ASUS Zenbook 14 UX3405CA-ST1713W - Hoàng Hà Mobile</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Laptop ASUS Zenbook 14 UX3405CA-ST1713W",
        "url": "https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w",
        "sku": "ST1713W",
        "brand": {
            "@type": "Brand",
            "name": "ASUS"
        },
        "offers": {
            "@type": "Offer",
            "priceCurrency": "VND",
            "price": "29290000",
            "availability": "https://schema.org/InStock"
        }
    }
    </script>
</head>
<body>
    <input type="hidden" name="quickOrder_productId" id="quickOrder_productId" value="9257" />
    <input type="hidden" name="ModelID" id="ModelID" value="9257" />

    <h1>Laptop ASUS Zenbook 14 UX3405CA-ST1713W (Ultra 5 255H/16GB/512GB)</h1>

    <div class="price-tags">
        <div class="price">
            <strong>29,290,000 ₫</strong>
        </div>
    </div>
    <div class="price price-last">
        <strike>38,990,000 ₫</strike>
    </div>
    <p class="price-tags price-tags-member">
        <span>Hoàng Hà Member chỉ từ</span>
        <strong>28,939,000 ₫</strong>
    </p>

    <div class="installment-text">
        Hoặc 3,745,000 ₫ x 6T
    </div>

    <!-- Khối phụ kiện mua kèm (Tuyệt đối không lấy nhầm giá này làm price_raw) -->
    <div class="accessory-bundle">
        <span class="acc-name">Miếng dán màn hình</span>
        <span class="acc-price">250,000 ₫</span>
    </div>

    <!-- Bảng thông số kỹ thuật chi tiết -->
    <table class="table-specs">
        <tr><th>Thông số</th><th>Chi tiết</th></tr>
        <tr><td>CPU</td><td>Intel Core Ultra 5 225H</td></tr>
        <tr><td>Bộ nhớ RAM</td><td>16GB LPDDR5X</td></tr>
        <tr><td>Ổ cứng</td><td>SSD 512GB M.2 NVMe</td></tr>
        <tr><td>Màn hình</td><td>14 inch, OLED, 3K (2880x1800)</td></tr>
        <tr><td>Khối lượng</td><td>1.20kg</td></tr>
        <tr><td>Màu sắc</td><td>Xanh lam trầm</td></tr>
    </table>

    <!-- Luồng bình luận / Q&A hỏi đáp có reply của Admin -->
    <div class="box-comment">
        <div class="comment-item">
            <span class="author">T. Tâm</span>
            <span class="time">10 tháng trước (02/01/2026)</span>
            <div class="comment-content">Máy này có sẵn tại Hà Nội không ạ?</div>
            <div class="reply-admin">
                <span class="admin-name">Quản trị viên</span>
                <div class="reply-content">Dạ Hoàng Hà Mobile xin chào anh/chị, sản phẩm đang sẵn hàng tại Hà Nội ạ!</div>
            </div>
        </div>
    </div>
</body>
</html>
"""

MOCK_HOANGHA_DETAIL_HIDDEN_PRICE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>MacBook Air M1 2020 256GB - Hoàng Hà Mobile</title>
</head>
<body>
    <input type="hidden" name="quickOrder_productId" value="5432" />
    <h1>MacBook Air M1 2020 256GB</h1>

    <!-- Giá sản phẩm chính bị ẩn do hết hàng tại khu vực chọn -->
    <div class="out-of-stock-notice">
        Sản phẩm tạm dừng đặt hàng trực tuyến tại khu vực đã chọn
    </div>

    <!-- Vẫn hiển thị giá phụ kiện mua kèm -->
    <div class="accessory-bundle">
        <span class="acc-name">Phủ phím Innostyle</span>
        <div class="price"><strong>79,000 ₫</strong></div>
    </div>

    <table>
        <tr><td>Màn hình</td><td>13.3 inch Retina</td></tr>
        <tr><td>Chipset</td><td>Apple M1</td></tr>
    </table>
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


class TestHoanghamobileCrawler(unittest.TestCase):
    """Bộ test toàn diện cho crawler Hoàng Hà Mobile."""

    def setUp(self):
        self.laptop_spider = HoanghamobileLaptopSpider(batch_id="20261017_hhm_laptop", crawl_reviews=True)
        self.phone_spider = HoanghamobileSmartphoneSpider(batch_id="20261017_hhm_phone", crawl_reviews=True)

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
    # 2. SPIDER CONFIGURATION & URL NORMALIZATION
    # ---------------------------------------------------------
    def test_spider_configuration(self):
        """Kiểm tra cấu hình category và slug cho laptop và smartphone."""
        self.assertEqual(self.laptop_spider.category, "laptop")
        self.assertEqual(self.laptop_spider.slug, "laptop")
        self.assertEqual(self.laptop_spider.name, "hoanghamobile_laptop")

        self.assertEqual(self.phone_spider.category, "smartphone")
        self.assertEqual(self.phone_spider.slug, "dien-thoai-di-dong")
        self.assertEqual(self.phone_spider.name, "hoanghamobile_smartphone")

    def test_url_normalization_laptop_and_lap_top(self):
        """Kiểm tra chuẩn hóa tiền tố /lap-top/ về /laptop/ và canonical slug."""
        url1 = "https://hoanghamobile.com/lap-top/asus-zenbook-14-ux3405ca-st1713w"
        url2 = "https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w/"
        url3 = "/lap-top/macbook-air-m1"

        norm1 = HoanghamobileBaseSpider.normalize_url(url1)
        norm2 = HoanghamobileBaseSpider.normalize_url(url2)
        norm3 = HoanghamobileBaseSpider.normalize_url(url3)

        self.assertEqual(norm1, "https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w")
        self.assertEqual(norm2, "https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w")
        self.assertEqual(norm3, "https://hoanghamobile.com/laptop/macbook-air-m1")

        slug1 = HoanghamobileBaseSpider.extract_canonical_slug(norm1)
        slug2 = HoanghamobileBaseSpider.extract_canonical_slug(norm2)
        self.assertEqual(slug1, "asus-zenbook-14-ux3405ca-st1713w")
        self.assertEqual(slug1, slug2)

    # ---------------------------------------------------------
    # 3. LISTING PARSING, DEDUPLICATION & PAGINATION
    # ---------------------------------------------------------
    def test_parse_listing_deduplicates_laptop_vs_lap_top(self):
        """Kiểm tra cùng sản phẩm dưới /laptop/ và /lap-top/ chỉ được lên lịch 1 lần duy nhất."""
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop",
            body=MOCK_HOANGHA_LISTING_HTML,
            meta={"page": 1},
        )
        requests = list(self.laptop_spider.parse_listing(res))
        detail_reqs = [r for r in requests if r.callback == self.laptop_spider.parse_detail]

        # Trong mock có 3 thẻ nhưng thẻ 1 và 2 cùng sản phẩm asus-zenbook -> chỉ lên lịch 2 sản phẩm!
        self.assertEqual(len(detail_reqs), 2)
        slugs = [r.meta["slug"] for r in detail_reqs]
        self.assertEqual(slugs, ["asus-zenbook-14-ux3405ca-st1713w", "macbook-air-m1-2020-256gb"])

        # Kiểm tra next page request
        next_page_reqs = [r for r in requests if r.callback == self.laptop_spider.parse_listing]
        self.assertEqual(len(next_page_reqs), 1)
        self.assertEqual(next_page_reqs[0].meta["page"], 2)

    def test_pagination_termination_when_no_pager(self):
        """Kiểm tra dừng phân trang an toàn khi không còn nút #page-pager."""
        html_no_pager = """
        <div class="v5-list-items">
            <div class="pj16-item-info">
                <h3><a href="/laptop/final-product">Final Laptop</a></h3>
            </div>
        </div>
        """
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop?p=5",
            body=html_no_pager,
            meta={"page": 5},
        )
        requests = list(self.laptop_spider.parse_listing(res))
        next_page_reqs = [r for r in requests if r.callback == self.laptop_spider.parse_listing]
        self.assertEqual(len(next_page_reqs), 0)
        self.assertEqual(self.laptop_spider.stop_reason, "no_more_products")

    # ---------------------------------------------------------
    # 4. DETAIL PARSING & PRICE EXTRACTION
    # ---------------------------------------------------------
    def test_parse_detail_laptop_all_25_fields_and_price_separation(self):
        """Kiểm tra parse detail laptop đầy đủ 25 fields và loại bỏ giá Member, giá trả góp."""
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w",
            body=MOCK_HOANGHA_DETAIL_LAPTOP_HTML,
            meta={"slug": "asus-zenbook-14-ux3405ca-st1713w", "listing_data": {"price": "29,290,000 ₫"}},
        )
        items = list(self.laptop_spider.parse_detail(res))
        self.assertEqual(len(items), 1)
        it = items[0]

        # Kiểm tra 25 trường
        self.assertEqual(set(it.keys()), EXPECTED_PRODUCT_FIELDS)
        self.assertEqual(it["source"], "hoanghamobile")
        self.assertEqual(it["category"], "laptop")
        self.assertEqual(it["product_id_raw"], "9257")
        self.assertEqual(it["parent_product_id_raw"], "9257")
        self.assertEqual(it["product_name_raw"], "Laptop ASUS Zenbook 14 UX3405CA-ST1713W (Ultra 5 255H/16GB/512GB)")
        self.assertEqual(it["product_url_raw"], "https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w")

        # Giá bán hiện tại
        self.assertEqual(it["price_raw"], "29,290,000 ₫")
        self.assertEqual(it["original_price_raw"], "38,990,000 ₫")

        # Giá Member và giá trả góp được tách riêng, không làm nhiễm bẩn price_raw
        self.assertEqual(it["attributes_raw"].get("member_price_raw"), "28,939,000 ₫")
        self.assertEqual(it["attributes_raw"].get("installment_monthly_raw"), "3,745,000 ₫")
        self.assertNotEqual(it["price_raw"], it["attributes_raw"]["member_price_raw"])
        self.assertNotEqual(it["price_raw"], "250,000 ₫")  # Không lấy giá phụ kiện!

        # SKU / MPN Windows laptop
        self.assertEqual(it["sku_raw"], "ST1713W")
        self.assertEqual(it["variant_sku_raw"], "ST1713W")

        # Technical attributes từ specs table
        self.assertEqual(it["attributes_raw"].get("CPU"), "Intel Core Ultra 5 225H")
        self.assertEqual(it["attributes_raw"].get("Bộ nhớ RAM"), "16GB LPDDR5X")
        self.assertEqual(it["attributes_raw"].get("Ổ cứng"), "SSD 512GB M.2 NVMe")

        # Brand & Seller
        self.assertEqual(it["brand_raw"], "ASUS")
        self.assertEqual(it["seller_raw"], "Hoàng Hà Mobile")

        # Hoàng Hà không có rating sao
        self.assertIsNone(it["rating_raw"])
        self.assertIsNone(it["review_count_raw"])

    def test_qa_comments_not_yielded_as_tech_review_raw_item(self):
        """HARD RULE: Tuyệt đối không map Q&A / hỏi đáp của Hoàng Hà Mobile vào TechReviewRawItem."""
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop/asus-zenbook-14-ux3405ca-st1713w",
            body=MOCK_HOANGHA_DETAIL_LAPTOP_HTML,
            meta={"slug": "asus-zenbook-14-ux3405ca-st1713w"},
        )
        items = list(self.laptop_spider.parse_detail(res))
        rev_items = [it for it in items if isinstance(it, TechReviewRawItem)]
        self.assertEqual(len(rev_items), 0, "Hoàng Hà Mobile Q&A không được coi là customer review")

    def test_detail_hidden_price_fallback_to_listing(self):
        """Khi trang Detail ẩn giá chính do hết hàng khu vực, kích hoạt fallback sang Listing."""
        listing_info = {
            "slug": "macbook-air-m1-2020-256gb",
            "title": "MacBook Air M1 2020 256GB",
            "price": "18,490,000 ₫",
            "original_price": "19,990,000 ₫",
            "stock": "Sẵn hàng",
        }
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop/macbook-air-m1-2020-256gb",
            body=MOCK_HOANGHA_DETAIL_HIDDEN_PRICE_HTML,
            meta={"slug": "macbook-air-m1-2020-256gb", "listing_data": listing_info},
        )
        items = list(self.laptop_spider.parse_detail(res))
        self.assertEqual(len(items), 1)
        it = items[0]

        # Giá chính được fallback từ Listing, không bị lấy nhầm giá phụ kiện 79,000 ₫!
        self.assertEqual(it["price_raw"], "18,490,000 ₫")
        self.assertEqual(it["original_price_raw"], "19,990,000 ₫")
        self.assertNotEqual(it["price_raw"], "79,000 ₫")
        self.assertEqual(it["raw_payload"].get("price_source"), "listing_fallback")

    def test_inaccessible_detail_page_handles_fallback_cleanly(self):
        """Khi trang Detail bị HTTP 404/403, xây dựng item an toàn từ listing_data."""
        listing_info = {
            "slug": "old-discontinued-laptop",
            "title": "Old Discontinued Laptop",
            "price": "10,000,000 ₫",
            "original_price": "12,000,000 ₫",
            "stock": "Liên hệ",
        }
        res = _make_html_response(
            url="https://hoanghamobile.com/laptop/old-discontinued-laptop",
            body="<html><body>404 Not Found</body></html>",
            meta={"slug": "old-discontinued-laptop", "listing_data": listing_info},
            status=404,
        )
        items = list(self.laptop_spider.parse_detail(res))
        self.assertEqual(len(items), 1)
        it = items[0]
        self.assertIsInstance(it, TechProductRawItem)
        self.assertEqual(it["product_name_raw"], "Old Discontinued Laptop")
        self.assertEqual(it["price_raw"], "10,000,000 ₫")
        self.assertEqual(it["raw_payload"].get("price_source"), "listing_only")
        self.assertEqual(it["raw_payload"].get("detail_http_status"), 404)

    # ---------------------------------------------------------
    # 6. AVAILABILITY, PRICE, PRODUCT ID & VARIANT SEMANTICS
    # ---------------------------------------------------------
    def test_availability_semantics_in_stock_and_out_of_stock(self):
        """Kiểm tra InStock -> Sẵn hàng, OutOfStock / out-of-stock notice -> Tạm hết hàng."""
        in_stock_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "offers": {"availability": "https://schema.org/InStock", "price": "20000000"}}
        </script></head><body><div class="price"><strong>20,000,000 ₫</strong></div></body></html>
        """
        res_in = _make_html_response("https://hoanghamobile.com/phone-a", in_stock_html)
        it_in = list(self.phone_spider.parse_detail(res_in))[0]
        self.assertEqual(it_in["availability_raw"], "Sẵn hàng")

        out_stock_html = """
        <html><body>
            <div class="out-of-stock-notice">Sản phẩm tạm dừng đặt hàng trực tuyến</div>
            <div class="price"><strong>20,000,000 ₫</strong></div>
        </body></html>
        """
        res_out = _make_html_response("https://hoanghamobile.com/phone-b", out_stock_html)
        it_out = list(self.phone_spider.parse_detail(res_out))[0]
        self.assertEqual(it_out["availability_raw"], "Tạm hết hàng")

    def test_availability_no_evidence_remains_none(self):
        """BUG FIX #1: Không có evidence tồn kho thì availability_raw phải là None, không default Sẵn hàng."""
        no_evidence_html = """
        <html><head><script type="application/ld+json">
        {"@type": "Product", "offers": {"price": "20000000"}}
        </script></head><body><div class="price"><strong>20,000,000 ₫</strong></div></body></html>
        """
        res = _make_html_response("https://hoanghamobile.com/phone-c", no_evidence_html, meta={"listing_data": {}})
        it = list(self.phone_spider.parse_detail(res))[0]
        self.assertIsNone(it["availability_raw"], "Không có bằng chứng tồn kho thì availability_raw phải là None")

    def test_availability_listing_stock_fallback_and_irrelevant_badge_ignored(self):
        """Listing có stock hợp lệ thì fallback, badge khuyến mãi/giảm giá không được coi là stock."""
        listing_with_valid_stock = {
            "title": "Phone D", "price": "15,000,000 ₫", "stock": "Sắp diễn ra"
        }
        res1 = _make_html_response("https://hoanghamobile.com/phone-d", "<html><body><div class='price'><strong>15,000,000 ₫</strong></div></body></html>", meta={"listing_data": listing_with_valid_stock})
        it1 = list(self.phone_spider.parse_detail(res1))[0]
        self.assertEqual(it1["availability_raw"], "Sắp diễn ra")

        # Listing với text không liên quan
        listing_with_irrelevant = {
            "title": "Phone E", "price": "15,000,000 ₫", "stock": None
        }
        res2 = _make_html_response("https://hoanghamobile.com/phone-e", "<html><body><div class='price'><strong>15,000,000 ₫</strong></div></body></html>", meta={"listing_data": listing_with_irrelevant})
        it2 = list(self.phone_spider.parse_detail(res2))[0]
        self.assertIsNone(it2["availability_raw"])

    def test_price_tightening_excludes_related_and_member(self):
        """BUG FIX #2: Giá từ sản phẩm liên quan, phụ kiện và member không ghi đè price_raw."""
        html_complex = """
        <html><body>
            <div class="product-details">
                <h1>Laptop Cao Cấp</h1>
                <div class="price"><strong>35,000,000 ₫</strong></div>
                <div class="price price-last"><strike>40,000,000 ₫</strike></div>
                <p class="price-tags-member"><span>Hoàng Hà Member:</span><strong>34,500,000 ₫</strong></p>
                <div class="installment">Hoặc 5,000,000 ₫ x 6T</div>
            </div>
            <div class="similar-products">
                <div class="item">
                    <div class="price"><strong>12,000,000 ₫</strong></div>
                </div>
            </div>
            <div class="accessory-bundle">
                <div class="price"><strong>199,000 ₫</strong></div>
            </div>
        </body></html>
        """
        res = _make_html_response("https://hoanghamobile.com/laptop/laptop-cao-cap", html_complex)
        it = list(self.laptop_spider.parse_detail(res))[0]
        self.assertEqual(it["price_raw"], "35,000,000 ₫")
        self.assertEqual(it["original_price_raw"], "40,000,000 ₫")
        self.assertEqual(it["attributes_raw"].get("member_price_raw"), "34,500,000 ₫")
        self.assertEqual(it["attributes_raw"].get("installment_monthly_raw"), "5,000,000 ₫")
        self.assertNotEqual(it["price_raw"], "34,500,000 ₫")
        self.assertNotEqual(it["price_raw"], "12,000,000 ₫")
        self.assertNotEqual(it["price_raw"], "199,000 ₫")

    def test_original_price_semantic_guard_candidate_smaller_than_price_rejected(self):
        """
        REGRESSION TEST 1: price_raw = 38.490.000, candidate 550.000 -> original_price_raw is None.
        Candidate từ detail nhỏ hơn price_raw (nhầm giá phụ kiện/khuyến mãi/trả góp) phải bị loại bỏ.
        """
        html = """
        <html><body>
            <div class="product-details">
                <h1>Smartphone Flagship</h1>
                <div class="price"><strong>38.490.000 ₫</strong></div>
                <div class="price price-last"><strike>550.000 ₫</strike></div>
            </div>
        </body></html>
        """
        res = _make_html_response("https://hoanghamobile.com/dien-thoai/flagship", html, meta={"listing_data": {}})
        it = list(self.phone_spider.parse_detail(res))[0]
        self.assertEqual(it["price_raw"], "38.490.000 ₫")
        self.assertIsNone(
            it["original_price_raw"],
            "Candidate 550.000 ₫ nhỏ hơn giá bán 38.490.000 ₫ nên phải bị loại bỏ, original_price_raw phải là None",
        )

    def test_original_price_prioritizes_valid_listing_over_confused_detail(self):
        """
        REGRESSION TEST 2: listing có original_price = 46.990.000 trong khi detail nhầm 13.690.000
        -> kết quả phải là 46.990.000 (ưu tiên listing hợp lệ).
        """
        html = """
        <html><body>
            <div class="product-details">
                <h1>Samsung Galaxy Z Fold7 5G 12GB/256GB</h1>
                <div class="price"><strong>37.990.000 ₫</strong></div>
            </div>
            <div class="accessory-section">
                <div class="price-last"><strike>13.690.000 ₫</strike></div>
            </div>
        </body></html>
        """
        listing_info = {
            "title": "Samsung Galaxy Z Fold7 5G 12GB/256GB",
            "price": "37,990,000 ₫",
            "original_price": "46,990,000 ₫",
        }
        res = _make_html_response(
            "https://hoanghamobile.com/dien-thoai/samsung-galaxy-z-fold7",
            html,
            meta={"listing_data": listing_info},
        )
        it = list(self.phone_spider.parse_detail(res))[0]
        self.assertEqual(it["price_raw"], "37.990.000 ₫")
        self.assertEqual(
            it["original_price_raw"],
            "46,990,000 ₫",
            "Phải ưu tiên listing_data['original_price'] hợp lệ (46,990,000 ₫) thay vì nhầm candidate 13.690.000 ₫ ở detail",
        )

    def test_product_id_hierarchy(self):
        """Kiểm tra hierarchy của product_id_raw: hidden input -> URL -p{id} -> None."""
        # 1. Hidden input
        html_hidden = '<html><body><input type="hidden" name="quickOrder_productId" value="8888" /></body></html>'
        res1 = _make_html_response("https://hoanghamobile.com/laptop/some-lap", html_hidden)
        it1 = list(self.laptop_spider.parse_detail(res1))[0]
        self.assertEqual(it1["product_id_raw"], "8888")

        # 2. URL có -p{id} (máy cũ/đổi trả)
        res2 = _make_html_response("https://hoanghamobile.com/kho-san-pham-cu/may-cu-p82479", "<html><body></body></html>")
        it2 = list(self.phone_spider.parse_detail(res2))[0]
        self.assertEqual(it2["product_id_raw"], "82479")

        # 3. Không có hidden input và URL không có -p{id} -> None, không invent ID từ slug
        res3 = _make_html_response("https://hoanghamobile.com/laptop/no-id-laptop", "<html><body></body></html>")
        it3 = list(self.laptop_spider.parse_detail(res3))[0]
        self.assertIsNone(it3["product_id_raw"])

    def test_variant_semantics_ui_selector_does_not_duplicate(self):
        """BUG FIX #4: Trang có nhiều bộ chọn màu/bộ nhớ UI không tự nhân bản variant records."""
        multi_ui_html = """
        <html><body>
            <div class="product-details">
                <h1>MacBook Pro M3</h1>
                <div class="price"><strong>45,000,000 ₫</strong></div>
                <div class="color-selector">
                    <span class="opt">Space Gray</span>
                    <span class="opt">Silver</span>
                </div>
                <div class="storage-selector">
                    <span class="opt">512GB</span>
                    <span class="opt">1TB</span>
                </div>
            </div>
        </body></html>
        """
        res = _make_html_response("https://hoanghamobile.com/laptop/macbook-pro-m3", multi_ui_html)
        items = list(self.laptop_spider.parse_detail(res))
        prod_items = [i for i in items if isinstance(i, TechProductRawItem)]
        self.assertEqual(len(prod_items), 1)
        self.assertIsNone(prod_items[0]["variant_name_raw"])
        self.assertIsNone(prod_items[0]["variant_color_raw"])

    # ---------------------------------------------------------
    # 7. PIPELINE & SNAPSHOT ISOLATION
    # ---------------------------------------------------------
    def test_hoanghamobile_pipeline_isolation(self):
        """Pipeline mở và ghi đúng thư mục snapshot data/raw/hoanghamobile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rev_path = Path(tmpdir) / "reviews.jsonl"
            spider = self.phone_spider
            spider.review_output = str(rev_path)

            pipeline = HoanghamobileReviewExportPipeline()
            pipeline.open_spider(spider)

            rev_item = TechReviewRawItem()
            rev_item["source"] = "hoanghamobile"
            rev_item["category"] = "smartphone"
            rev_item["crawl_batch"] = "test"
            rev_item["crawl_time"] = datetime.now().isoformat()
            rev_item["review_id_raw"] = "rev_hhm_01"

            from scrapy.exceptions import DropItem
            with self.assertRaises(DropItem):
                pipeline.process_item(rev_item, spider)

            pipeline.close_spider(spider)
            self.assertTrue(rev_path.exists())


if __name__ == "__main__":
    unittest.main()
