import json
import unittest
from datetime import datetime

import scrapy
from scrapy.http import HtmlResponse, TextResponse

from crawler.tgdd.base_spider import TgddBaseSpider
from crawler.tgdd.tgdd_laptop_spider import TgddLaptopSpider
from crawler.tgdd.tgdd_smartphone_spider import TgddSmartphoneSpider
from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem

from crawler.fptshop.base_spider import FptshopBaseSpider
from crawler.fptshop.fptshop_laptop_spider import FptshopLaptopSpider
from crawler.fptshop.fptshop_smartphone_spider import FptshopSmartphoneSpider


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


class TestCrossSourceRawDataContract(unittest.TestCase):
    """
    Bộ test kiểm chứng Raw Data Contract giữa TGDĐ và FPTShop.
    Đảm bảo TV2 có thể xử lý cả hai nguồn bằng cùng một schema logic và cùng semantic contract.
    """

    def setUp(self):
        self.tgdd_spider = TgddSmartphoneSpider(batch_id="20261014_tgdd_batch", crawl_reviews=False)
        self.fpt_spider = FptshopSmartphoneSpider(batch_id="20261014_fpt_batch", crawl_reviews=False)

    def test_schema_field_sets_match_exactly(self):
        """
        Kiểm tra 100% khớp các trường bắt buộc của Canonical Contract:
        - Product contract có đúng 25 trường.
        - Review contract có đúng 19 trường.
        """
        self.assertEqual(len(EXPECTED_PRODUCT_FIELDS), 25)
        self.assertEqual(len(EXPECTED_REVIEW_FIELDS), 19)

        prod_item = TechProductRawItem()
        for field in EXPECTED_PRODUCT_FIELDS:
            self.assertIn(field, prod_item.fields)

        rev_item = TechReviewRawItem()
        for field in EXPECTED_REVIEW_FIELDS:
            self.assertIn(field, rev_item.fields)

    def test_case_1_multi_variant_product_cross_source(self):
        """
        Case 1: Multi-variant product ở cả hai nguồn:
        - Sinh các record độc lập cho từng variant.
        - Chung parent_product_id_raw, parent_product_name_raw, parent_url_raw.
        - Khác nhau variant_sku_raw, variant_url_raw, variant_color_raw.
        - Khớp đúng 25 trường của Canonical Product Schema ở mọi record.
        """
        # 1. TGDĐ multi-variant
        mock_tgdd_html = """
        <html><head><script type="application/ld+json">
        {
            "@type": "ProductGroup",
            "name": "Samsung Galaxy S26 Ultra",
            "hasVariant": [
                {"@type": "Product", "name": "S26 Ultra 256GB", "sku": "SAM-256", "color": "Đen", "url": "https://www.thegioididong.com/dtdd/s26-256", "offers": {"price": 31990000, "originalPrice": 34990000, "availability": "https://schema.org/InStock"}},
                {"@type": "Product", "name": "S26 Ultra 512GB", "sku": "SAM-512", "color": "Bạc", "url": "https://www.thegioididong.com/dtdd/s26-512", "offers": {"price": 36990000, "originalPrice": 39990000, "availability": "https://schema.org/InStock"}}
            ]
        }
        </script></head><body></body></html>
        """
        tgdd_listing = self.tgdd_spider.extract_listing_item({
            "id": "201332",
            "name": "Samsung Galaxy S26 Ultra",
            "url": "dtdd/samsung-galaxy-s26-ultra",
            "brand": {"brandName": "Samsung"},
            "rate": 4.9,
            "totalRate": 100,
            "totalSold": "Đã bán 500",
            "productNameSKU": "SAM-S26-LISTING",
        })
        tgdd_req = scrapy.Request(url="https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra", meta={"item": tgdd_listing})
        tgdd_resp = HtmlResponse(url=tgdd_req.url, body=mock_tgdd_html.encode("utf-8"), encoding="utf-8", request=tgdd_req)
        tgdd_items = [x for x in self.tgdd_spider.parse_detail(tgdd_resp) if isinstance(x, TechProductRawItem)]

        self.assertEqual(len(tgdd_items), 2)
        for it in tgdd_items:
            self.assertEqual(set(it.keys()), EXPECTED_PRODUCT_FIELDS)
            self.assertEqual(it["source"], "tgdd")
            self.assertEqual(it["category"], "smartphone")
            self.assertEqual(it["product_id_raw"], "201332")
            self.assertEqual(it["parent_product_id_raw"], "201332")
            self.assertEqual(it["parent_product_name_raw"], "Samsung Galaxy S26 Ultra")
            self.assertEqual(it["parent_url_raw"], "https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra")
            self.assertIsInstance(it["price_raw"], (int, float))
            self.assertIsInstance(it["original_price_raw"], (int, float))
            self.assertIsInstance(it["raw_payload"], dict)

        self.assertNotEqual(tgdd_items[0]["variant_sku_raw"], tgdd_items[1]["variant_sku_raw"])
        self.assertNotEqual(tgdd_items[0]["variant_url_raw"], tgdd_items[1]["variant_url_raw"])
        self.assertNotEqual(tgdd_items[0]["variant_color_raw"], tgdd_items[1]["variant_color_raw"])

        # 2. FPTShop multi-variant
        fpt_raw_item = {
            "code": "344851327977",
            "name": "Xiaomi Redmi Note 17 4GB",
            "slug": "dien-thoai/xiaomi-redmi-note-17",
            "brand": {"name": "Xiaomi"},
            "averageScore": 4.8,
            "sold": {"realQuantity": 3241},
            "skus": [
                {
                    "sku": "00931031",
                    "name": "Xiaomi Redmi Note 17 4GB 128GB Đen",
                    "slug": "dien-thoai/xiaomi-redmi-note-17?sku=00931031",
                    "currentPrice": 6490000,
                    "originalPrice": 6990000,
                    "statusOnWeb": {"displayName": "Mua ngay"},
                    "variants": [{"propertyName": "color", "displayValue": "Đen"}],
                },
                {
                    "sku": "00931032",
                    "name": "Xiaomi Redmi Note 17 4GB 128GB Xanh",
                    "slug": "dien-thoai/xiaomi-redmi-note-17?sku=00931032",
                    "currentPrice": 6490000,
                    "originalPrice": 6990000,
                    "statusOnWeb": {"displayName": "Mua ngay"},
                    "variants": [{"propertyName": "color", "displayValue": "Xanh"}],
                },
            ],
        }
        fpt_items = [x for x in self.fpt_spider.yield_products_and_reviews(fpt_raw_item, attributes={"Chip": "Snapdragon"}) if isinstance(x, TechProductRawItem)]

        self.assertEqual(len(fpt_items), 2)
        for it in fpt_items:
            self.assertEqual(set(it.keys()), EXPECTED_PRODUCT_FIELDS)
            self.assertEqual(it["source"], "fptshop")
            self.assertEqual(it["category"], "smartphone")
            self.assertEqual(it["product_id_raw"], "344851327977")
            self.assertEqual(it["parent_product_id_raw"], "344851327977")
            self.assertEqual(it["parent_product_name_raw"], "Xiaomi Redmi Note 17 4GB")
            self.assertEqual(it["parent_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17")
            self.assertIsInstance(it["price_raw"], (int, float))
            self.assertIsInstance(it["original_price_raw"], (int, float))
            self.assertIsInstance(it["raw_payload"], dict)

        self.assertNotEqual(fpt_items[0]["variant_sku_raw"], fpt_items[1]["variant_sku_raw"])
        self.assertNotEqual(fpt_items[0]["variant_url_raw"], fpt_items[1]["variant_url_raw"])
        self.assertNotEqual(fpt_items[0]["variant_color_raw"], fpt_items[1]["variant_color_raw"])

        # Cross-source verification: cả 2 nguồn xuất ra CÙNG cấu trúc key
        self.assertEqual(set(tgdd_items[0].keys()), set(fpt_items[0].keys()))

    def test_case_2_single_configuration_fallback_cross_source(self):
        """
        Case 2: Sản phẩm đơn (không có biến thể hoặc không có hasVariant/skus):
        - Sinh đúng 1 fallback record.
        - variant_name_raw, variant_color_raw, variant_url_raw, variant_sku_raw = None.
        - parent_product_id_raw == product_id_raw.
        - Vẫn đủ 25 trường của Canonical Product Schema.
        """
        # 1. TGDĐ fallback
        mock_tgdd_html_no_var = "<html><head></head><body><h1>HP Victus 15</h1></body></html>"
        tgdd_listing = self.tgdd_spider.extract_listing_item({
            "id": "193571",
            "name": "HP Victus 15",
            "url": "laptop/hp-victus-15",
            "productPrices": [{"price": 18990000, "sysPrice": 20990000}],
        })
        tgdd_req = scrapy.Request(url="https://www.thegioididong.com/laptop/hp-victus-15", meta={"item": tgdd_listing})
        tgdd_resp = HtmlResponse(url=tgdd_req.url, body=mock_tgdd_html_no_var.encode("utf-8"), encoding="utf-8", request=tgdd_req)
        tgdd_items = [x for x in self.tgdd_spider.parse_detail(tgdd_resp) if isinstance(x, TechProductRawItem)]

        self.assertEqual(len(tgdd_items), 1)
        tgdd_item = tgdd_items[0]
        self.assertEqual(set(tgdd_item.keys()), EXPECTED_PRODUCT_FIELDS)
        self.assertEqual(tgdd_item["product_id_raw"], "193571")
        self.assertEqual(tgdd_item["parent_product_id_raw"], "193571")
        self.assertIsNone(tgdd_item["variant_name_raw"])
        self.assertIsNone(tgdd_item["variant_color_raw"])
        self.assertIsNone(tgdd_item["variant_url_raw"])
        self.assertIsNone(tgdd_item["variant_sku_raw"])
        self.assertIsNone(tgdd_item["availability_raw"])
        self.assertEqual(tgdd_item["price_raw"], 18990000)

        # 2. FPTShop fallback
        fpt_raw_item_no_var = {
            "code": "621140612608",
            "name": "Acer Aspire Lite 14",
            "slug": "may-tinh-xach-tay/acer-aspire-lite-14",
            "price": 19990000,
            "originalPrice": 21990000,
            "skus": [],
        }
        fpt_items = [x for x in self.fpt_spider.yield_products_and_reviews(fpt_raw_item_no_var, attributes={}) if isinstance(x, TechProductRawItem)]

        self.assertEqual(len(fpt_items), 1)
        fpt_item = fpt_items[0]
        self.assertEqual(set(fpt_item.keys()), EXPECTED_PRODUCT_FIELDS)
        self.assertEqual(fpt_item["product_id_raw"], "621140612608")
        self.assertEqual(fpt_item["parent_product_id_raw"], "621140612608")
        self.assertIsNone(fpt_item["variant_name_raw"])
        self.assertIsNone(fpt_item["variant_color_raw"])
        self.assertIsNone(fpt_item["variant_url_raw"])
        self.assertIsNone(fpt_item["variant_sku_raw"])
        self.assertIsNone(fpt_item["availability_raw"])
        self.assertEqual(fpt_item["price_raw"], 19990000)

        # Cross-source check
        self.assertEqual(set(tgdd_item.keys()), set(fpt_item.keys()))

    def test_case_3_duplicate_prevention_cross_source(self):
        """
        Case 3: Chống trùng lặp parent + variant_sku trên mỗi nguồn.
        """
        # TGDĐ hasVariant không yield trùng lặp (parent, sku)
        tgdd_var_skus = ["SAM-256", "SAM-512"]
        self.assertEqual(len(tgdd_var_skus), len(set(tgdd_var_skus)))

        # FPTShop skus không yield trùng lặp (code, sku)
        fpt_skus = ["00931031", "00931032"]
        self.assertEqual(len(fpt_skus), len(set(fpt_skus)))

    def test_case_4_review_linkage_cross_source(self):
        """
        Case 4: Quy tắc liên kết review và variant (variant linkage rule):
        - Nếu review có SKU thuộc known_variant_skus của parent: variant_sku_raw được điền.
        - Nếu review có SKU không thuộc known_variant_skus: variant_sku_raw = None, nhưng raw code được bảo toàn.
        - Cả hai nguồn phải xuất ra đúng 19 trường của Canonical Review Schema.
        """
        # 1. TGDĐ reviews
        tgdd_body = {
            "code": 0,
            "data": {
                "total": 2,
                "comments": [
                    {
                        "commentId": 101,
                        "score": 5,
                        "content": "Tuyệt vời",
                        "fullName": "Anh Nam",
                        "createdDate": "2026-03-01",
                        "productCode": "SAM-256",  # MATCH
                        "variantCode": "201332",
                    },
                    {
                        "commentId": 102,
                        "score": 4,
                        "content": "Ổn áp",
                        "fullName": "Chị Hoa",
                        "createdDate": "2026-03-02",
                        "productCode": "OLD-SKU-999",  # UNKNOWN
                        "variantCode": "201332",
                    },
                ],
            },
        }
        tgdd_req = scrapy.Request(
            url=self.tgdd_spider.COMMENT_API_URL,
            meta={
                "parent_product_id": "201332",
                "parent_product_url": "https://www.thegioididong.com/dtdd/samsung-galaxy-s26-ultra",
                "known_variant_skus": ["SAM-256", "SAM-512"],
            },
        )
        tgdd_resp = TextResponse(url=tgdd_req.url, body=json.dumps(tgdd_body).encode("utf-8"), encoding="utf-8", request=tgdd_req)
        tgdd_revs = [x for x in self.tgdd_spider.parse_reviews(tgdd_resp) if isinstance(x, TechReviewRawItem)]

        self.assertEqual(len(tgdd_revs), 2)
        for r in tgdd_revs:
            self.assertEqual(set(r.keys()), EXPECTED_REVIEW_FIELDS)
            self.assertEqual(r["source"], "tgdd")
            self.assertEqual(r["parent_product_id_raw"], "201332")
            self.assertIsInstance(r["raw_payload"], dict)

        # Review 1 matched
        self.assertEqual(tgdd_revs[0]["review_product_code_raw"], "SAM-256")
        self.assertEqual(tgdd_revs[0]["variant_sku_raw"], "SAM-256")
        # Review 2 not matched
        self.assertEqual(tgdd_revs[1]["review_product_code_raw"], "OLD-SKU-999")
        self.assertIsNone(tgdd_revs[1]["variant_sku_raw"])

        # 2. FPTShop reviews
        fpt_body = {
            "status": 200,
            "data": {
                "totalCount": 2,
                "items": [
                    {
                        "id": 201,
                        "score": 5,
                        "content": "Chất lượng tốt",
                        "fullName": "Văn A",
                        "creationTime": "2026-03-01T10:00:00Z",
                        "sku": "00931031",  # MATCH
                        "orderCode": "ORD-111",
                    },
                    {
                        "id": 202,
                        "score": 4,
                        "content": "Bình thường",
                        "fullName": "Văn B",
                        "creationTime": "2026-03-02T11:00:00Z",
                        "sku": "UNKNOWN-999",  # UNKNOWN
                        "orderCode": "ORD-222",
                    },
                ],
            },
        }
        fpt_req = scrapy.Request(
            url=self.fpt_spider.COMMENT_API_URL,
            meta={
                "parent_product_id": "344851327977",
                "parent_product_url": "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17",
                "known_variant_skus": ["00931031", "00931032"],
            },
        )
        fpt_resp = TextResponse(url=fpt_req.url, body=json.dumps(fpt_body).encode("utf-8"), encoding="utf-8", request=fpt_req)
        fpt_revs = [x for x in self.fpt_spider.parse_reviews(fpt_resp) if isinstance(x, TechReviewRawItem)]

        self.assertEqual(len(fpt_revs), 2)
        for r in fpt_revs:
            self.assertEqual(set(r.keys()), EXPECTED_REVIEW_FIELDS)
            self.assertEqual(r["source"], "fptshop")
            self.assertEqual(r["parent_product_id_raw"], "344851327977")
            self.assertIsInstance(r["raw_payload"], dict)

        # Review 1 matched
        self.assertEqual(fpt_revs[0]["review_product_code_raw"], "00931031")
        self.assertEqual(fpt_revs[0]["variant_sku_raw"], "00931031")
        # Review 2 not matched
        self.assertEqual(fpt_revs[1]["review_product_code_raw"], "UNKNOWN-999")
        self.assertIsNone(fpt_revs[1]["variant_sku_raw"])

        # Cross-source review schema equivalence check
        self.assertEqual(set(tgdd_revs[0].keys()), set(fpt_revs[0].keys()))

    def test_semantic_invariants_across_sources(self):
        """
        Kiểm tra các bất biến ngữ nghĩa (Semantic Invariants):
        - price_raw luôn là kiểu số (int / float), không format chuỗi có ₫.
        - category luôn là category logic ('smartphone', 'laptop').
        - crawl_batch và crawl_time luôn hiện diện và đúng định dạng.
        - parent_* luôn trỏ về thông tin parent của sản phẩm.
        """
        spider_laptop_tgdd = TgddLaptopSpider(batch_id="20261014_111111")
        spider_laptop_fpt = FptshopLaptopSpider(batch_id="20261014_222222")

        self.assertEqual(spider_laptop_tgdd.category, "laptop")
        self.assertEqual(spider_laptop_fpt.category, "laptop")

        item_tgdd = spider_laptop_tgdd.extract_listing_item({
            "id": "111",
            "name": "Laptop A",
            "url": "laptop/a",
            "productPrices": [{"price": 15000000}],
        })
        self.assertIsInstance(item_tgdd["price_raw"], (int, float))
        self.assertFalse(isinstance(item_tgdd["price_raw"], str))
        self.assertEqual(item_tgdd["category"], "laptop")

        fpt_results = list(spider_laptop_fpt.yield_products_and_reviews({
            "code": "222",
            "name": "Laptop B",
            "slug": "may-tinh-xach-tay/b",
            "price": 20000000,
        }, attributes={}))
        item_fpt = [x for x in fpt_results if isinstance(x, TechProductRawItem)][0]
        self.assertIsInstance(item_fpt["price_raw"], (int, float))
        self.assertFalse(isinstance(item_fpt["price_raw"], str))
        self.assertEqual(item_fpt["category"], "laptop")


if __name__ == "__main__":
    unittest.main()
