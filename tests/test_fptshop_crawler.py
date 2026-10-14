import json
import unittest
from pathlib import Path
import tempfile

import scrapy
from scrapy.exceptions import DropItem
from scrapy.http import HtmlResponse, TextResponse

from crawler.fptshop.base_spider import FptshopBaseSpider
from crawler.fptshop.fptshop_laptop_spider import FptshopLaptopSpider
from crawler.fptshop.fptshop_smartphone_spider import FptshopSmartphoneSpider
from crawler.fptshop.items import TechProductRawItem, TechReviewRawItem
from crawler.fptshop.pipelines import FptshopReviewExportPipeline


class TestFptshopCrawler(unittest.TestCase):
    def test_spider_configuration_and_categories(self):
        """Kiểm tra khởi tạo spider và các thuộc tính category/slug của FPTShop."""
        spider_laptop = FptshopLaptopSpider()
        self.assertEqual(spider_laptop.name, "fptshop_laptop")
        self.assertEqual(spider_laptop.category, "laptop")
        self.assertEqual(spider_laptop.slug, "may-tinh-xach-tay")
        self.assertTrue(spider_laptop.crawl_reviews)

        spider_phone = FptshopSmartphoneSpider()
        self.assertEqual(spider_phone.name, "fptshop_smartphone")
        self.assertEqual(spider_phone.category, "smartphone")
        self.assertEqual(spider_phone.slug, "dien-thoai")
        self.assertTrue(spider_phone.crawl_reviews)

    def test_make_listing_request_structure(self):
        """Kiểm tra cấu trúc request listing của FPTShop."""
        spider = FptshopBaseSpider()
        req = spider.make_listing_request(page=1, skip_count=24)
        self.assertEqual(req.url, spider.CATEGORY_API_URL)
        self.assertEqual(req.method, "POST")
        payload = json.loads(req.body.decode("utf-8"))
        self.assertEqual(payload["skipCount"], 24)
        self.assertEqual(payload["maxResultCount"], 24)
        self.assertEqual(payload["categoryType"], "category")
        self.assertEqual(req.meta["page"], 1)
        self.assertEqual(req.meta["skip_count"], 24)

    def test_extract_variants_from_skus_listing(self):
        """Kiểm tra trích xuất biến thể từ mảng skus[] trong response listing của FPTShop."""
        spider = FptshopSmartphoneSpider(batch_id="20261014_120000", crawl_reviews=False)

        mock_item_data = {
            "code": "344851327977",
            "name": "Xiaomi Redmi Note 17 4GB",
            "slug": "dien-thoai/xiaomi-redmi-note-17",
            "brand": {"code": "352", "name": "Xiaomi"},
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
                    "variants": [
                        {"propertyName": "color", "displayValue": "Đen", "value": "Đen"},
                        {"propertyName": "rom", "displayValue": "128 GB", "value": "128"},
                    ],
                },
                {
                    "sku": "00931032",
                    "name": "Xiaomi Redmi Note 17 4GB 128GB Xanh",
                    "slug": "dien-thoai/xiaomi-redmi-note-17?sku=00931032",
                    "currentPrice": 6490000,
                    "originalPrice": 6990000,
                    "statusOnWeb": {"displayName": "Mua ngay"},
                    "variants": [
                        {"propertyName": "color", "displayValue": "Xanh", "value": "Xanh"},
                        {"propertyName": "rom", "displayValue": "128 GB", "value": "128"},
                    ],
                },
            ],
        }

        results = list(spider.yield_products_and_reviews(mock_item_data, attributes={"RAM": "4 GB"}))
        items = [x for x in results if isinstance(x, TechProductRawItem)]
        self.assertEqual(len(items), 2)

        # Kiểm tra item 1
        it1 = items[0]
        self.assertEqual(it1["source"], "fptshop")
        self.assertEqual(it1["category"], "smartphone")
        self.assertEqual(it1["product_id_raw"], "344851327977")
        self.assertEqual(it1["parent_product_id_raw"], "344851327977")
        self.assertEqual(it1["product_name_raw"], "Xiaomi Redmi Note 17 4GB")
        self.assertEqual(it1["parent_product_name_raw"], "Xiaomi Redmi Note 17 4GB")
        self.assertEqual(it1["product_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17")
        self.assertEqual(it1["parent_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17")
        self.assertEqual(it1["sku_raw"], "00931031")
        self.assertEqual(it1["variant_sku_raw"], "00931031")
        self.assertEqual(it1["variant_name_raw"], "Xiaomi Redmi Note 17 4GB 128GB Đen")
        self.assertEqual(it1["variant_color_raw"], "Đen")
        self.assertEqual(it1["variant_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17?sku=00931031")
        self.assertEqual(it1["availability_raw"], "Mua ngay")
        self.assertEqual(it1["price_raw"], 6490000)
        self.assertEqual(it1["original_price_raw"], 6990000)
        self.assertEqual(it1["brand_raw"], "Xiaomi")
        self.assertEqual(it1["seller_raw"], "FPT Shop")
        self.assertEqual(it1["rating_raw"], 4.8)
        self.assertIsNone(it1["review_count_raw"])
        self.assertEqual(it1["total_sold_raw"], "3241")
        self.assertEqual(it1["attributes_raw"], {"RAM": "4 GB"})
        self.assertIsInstance(it1["raw_payload"], dict)

        # Kiểm tra item 2
        it2 = items[1]
        self.assertEqual(it2["product_id_raw"], "344851327977")
        self.assertEqual(it2["parent_product_id_raw"], "344851327977")
        self.assertEqual(it2["variant_sku_raw"], "00931032")
        self.assertEqual(it2["variant_color_raw"], "Xanh")
        self.assertEqual(it2["variant_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17?sku=00931032")

    def test_single_configuration_fallback(self):
        """Kiểm tra sản phẩm không có biến thể sinh đúng 1 fallback item với variant_* = None."""
        spider = FptshopLaptopSpider(batch_id="20261014_120000", crawl_reviews=False)

        mock_item_data = {
            "code": "621140612608",
            "name": "Acer Aspire Lite 14",
            "slug": "may-tinh-xach-tay/acer-aspire-lite-14",
            "brand": {"name": "Acer"},
            "price": 19990000,
            "originalPrice": 21990000,
            "skus": [],  # Không có skus
        }

        results = list(spider.yield_products_and_reviews(mock_item_data, attributes={"CPU": "AMD R7"}))
        items = [x for x in results if isinstance(x, TechProductRawItem)]
        self.assertEqual(len(items), 1)

        it = items[0]
        self.assertEqual(it["source"], "fptshop")
        self.assertEqual(it["category"], "laptop")
        self.assertEqual(it["product_id_raw"], "621140612608")
        self.assertEqual(it["parent_product_id_raw"], "621140612608")
        self.assertEqual(it["product_name_raw"], "Acer Aspire Lite 14")
        self.assertEqual(it["parent_product_name_raw"], "Acer Aspire Lite 14")
        self.assertEqual(it["product_url_raw"], "https://fptshop.com.vn/may-tinh-xach-tay/acer-aspire-lite-14")
        self.assertEqual(it["parent_url_raw"], "https://fptshop.com.vn/may-tinh-xach-tay/acer-aspire-lite-14")
        self.assertIsNone(it["sku_raw"])
        self.assertIsNone(it["variant_name_raw"])
        self.assertIsNone(it["variant_color_raw"])
        self.assertIsNone(it["variant_url_raw"])
        self.assertIsNone(it["variant_sku_raw"])
        self.assertIsNone(it["availability_raw"])
        self.assertEqual(it["price_raw"], 19990000)
        self.assertEqual(it["original_price_raw"], 21990000)
        self.assertEqual(it["brand_raw"], "Acer")
        self.assertEqual(it["seller_raw"], "FPT Shop")
        self.assertEqual(it["attributes_raw"], {"CPU": "AMD R7"})
        self.assertEqual(it["raw_payload"], mock_item_data)

    def test_extract_attributes_ldjson_and_dom_table(self):
        """Kiểm tra trích xuất thông số kỹ thuật qua LD+JSON và DOM table fallback."""
        spider = FptshopBaseSpider()

        # 1. LD+JSON additionalProperty
        html_ldjson = """
        <!DOCTYPE html>
        <html>
        <head>
            <script type="application/ld+json">
            {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": "Test Laptop",
                "additionalProperty": [
                    {"@type": "PropertyValue", "name": "CPU", "value": "Intel Core i7"},
                    {"@type": "PropertyValue", "name": "RAM", "value": "16 GB"}
                ]
            }
            </script>
        </head>
        <body></body>
        </html>
        """
        attrs1 = spider.extract_attributes(html_ldjson)
        self.assertEqual(attrs1.get("CPU"), "Intel Core i7")
        self.assertEqual(attrs1.get("RAM"), "16 GB")

        # 2. DOM table fallback
        html_table = """
        <!DOCTYPE html>
        <html>
        <body>
            <table>
                <tr><th>Thông số</th><th>Chi tiết</th></tr>
                <tr><td>Ổ cứng</td><td>512 GB SSD</td></tr>
                <tr><td>Màn hình</td><td>15.6 inch FHD</td></tr>
            </table>
        </body>
        </html>
        """
        attrs2 = spider.extract_attributes(html_table)
        self.assertEqual(attrs2.get("Ổ cứng"), "512 GB SSD")
        self.assertEqual(attrs2.get("Màn hình"), "15.6 inch FHD")

    def test_parse_reviews_and_variant_linkage(self):
        """Kiểm tra parse review và semantic variant linkage của FPTShop."""
        spider = FptshopSmartphoneSpider(batch_id="20261014_revbatch")

        mock_body = {
            "status": 200,
            "data": {
                "totalCount": 2,
                "items": [
                    {
                        "id": 181598,
                        "orderCode": "ORD-123456",
                        "sku": "00931031",  # Match known variant
                        "creationTime": "2026-02-21T12:03:34.339Z",
                        "content": "Máy dùng rất mượt",
                        "score": 5,
                        "like": 3,
                        "fullName": "Nguyễn Văn A",
                        "media": {"images": ["img1.jpg"]},
                        "children": [{"content": "Cảm ơn bạn"}],
                    },
                    {
                        "id": 181599,
                        "orderCode": "ORD-789012",
                        "sku": "UNKNOWN-SKU-999",  # Does NOT match known variants
                        "creationTime": "2026-02-22T08:00:00.000Z",
                        "content": "Giao hàng hơi chậm",
                        "score": 3,
                        "like": 0,
                        "fullName": "Trần Thị B",
                        "media": {},
                        "children": [],
                    },
                ],
            },
        }

        req = scrapy.Request(
            url=spider.COMMENT_API_URL,
            meta={
                "parent_product_id": "344851327977",
                "parent_product_url": "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17",
                "page_index": 0,
                "page_size": 20,
                "known_variant_skus": ["00931031", "00931032"],
            },
        )
        resp = TextResponse(
            url=spider.COMMENT_API_URL,
            body=json.dumps(mock_body).encode("utf-8"),
            encoding="utf-8",
            request=req,
        )

        results = list(spider.parse_reviews(resp))
        review_items = [x for x in results if isinstance(x, TechReviewRawItem)]
        self.assertEqual(len(review_items), 2)

        # Review 1: SKU matches known variant
        r1 = review_items[0]
        self.assertEqual(r1["source"], "fptshop")
        self.assertEqual(r1["category"], "smartphone")
        self.assertEqual(r1["crawl_batch"], "20261014_revbatch")
        self.assertEqual(r1["parent_product_id_raw"], "344851327977")
        self.assertEqual(r1["parent_product_url_raw"], "https://fptshop.com.vn/dien-thoai/xiaomi-redmi-note-17")
        self.assertEqual(r1["review_id_raw"], "181598")
        self.assertEqual(r1["rating_raw"], 5)
        self.assertEqual(r1["review_text_raw"], "Máy dùng rất mượt")
        self.assertEqual(r1["author_raw"], "Nguyễn Văn A")
        self.assertEqual(r1["review_time_raw"], "2026-02-21T12:03:34.339Z")
        self.assertEqual(r1["like_count_raw"], 3)
        self.assertEqual(r1["review_product_code_raw"], "00931031")
        self.assertEqual(r1["variant_code_raw"], "ORD-123456")
        self.assertEqual(r1["variant_sku_raw"], "00931031")  # Linked!
        self.assertIsNone(r1["buy_date_raw"])
        self.assertEqual(r1["reply_raw"], [{"content": "Cảm ơn bạn"}])
        self.assertEqual(r1["attached_files_raw"], {"images": ["img1.jpg"]})
        self.assertIsInstance(r1["raw_payload"], dict)

        # Review 2: SKU does NOT match known variants
        r2 = review_items[1]
        self.assertEqual(r2["review_id_raw"], "181599")
        self.assertEqual(r2["review_product_code_raw"], "UNKNOWN-SKU-999")  # Preserved!
        self.assertIsNone(r2["variant_sku_raw"])  # NOT linked!

    def test_pipeline_separates_product_and_review(self):
        """Kiểm tra FptshopReviewExportPipeline tách biệt file sản phẩm và file đánh giá."""
        with tempfile.TemporaryDirectory() as tmpdir:
            rev_file = Path(tmpdir) / "fpt_reviews.jsonl"
            pipeline = FptshopReviewExportPipeline()
            spider = FptshopBaseSpider(crawl_reviews=True, review_output=str(rev_file))

            pipeline.open_spider(spider)
            try:
                prod = TechProductRawItem(product_id_raw="123", product_name_raw="Test Laptop")
                processed = pipeline.process_item(prod, spider)
                self.assertIs(processed, prod)

                rev = TechReviewRawItem(review_id_raw="888", review_text_raw="Tốt", rating_raw=5)
                with self.assertRaises(DropItem):
                    pipeline.process_item(rev, spider)
            finally:
                pipeline.close_spider(spider)

            self.assertTrue(rev_file.exists())
            lines = rev_file.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            saved = json.loads(lines[0])
            self.assertEqual(saved["review_id_raw"], "888")


if __name__ == "__main__":
    unittest.main()
