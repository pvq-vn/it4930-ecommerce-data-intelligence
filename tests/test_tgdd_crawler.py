import json
import unittest
from pathlib import Path

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

    def test_pilot_jsonl_files_exist_and_valid(self):
        """Kiểm tra 2 file pilot.jsonl (nếu đã crawl) đọc được và đạt tiêu chuẩn."""
        laptop_file = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop" / "pilot.jsonl"
        phone_file = PROJECT_ROOT / "data" / "raw" / "tgdd" / "smartphone" / "pilot.jsonl"

        for fpath, min_expected in [(laptop_file, 45), (phone_file, 45)]:
            if fpath.exists():
                count = 0
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            self.assertIn("source", record)
                            self.assertIn("category", record)
                            self.assertIn("product_id_raw", record)
                            self.assertIn("product_url_raw", record)
                            self.assertIn("attributes_raw", record)
                            count += 1
                self.assertGreaterEqual(count, min_expected)


if __name__ == "__main__":
    unittest.main()
