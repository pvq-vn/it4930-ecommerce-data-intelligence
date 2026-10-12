import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.tgdd.items import TechProductRawItem
except ImportError:
    from items import TechProductRawItem


class TgddBaseSpider(scrapy.Spider):
    """
    Base spider cho sàn Thế Giới Di Động (TGDĐ).
    Thu thập dữ liệu theo chuẩn TV1 (Web Crawling & Data Acquisition).
    Bảo toàn toàn bộ raw data, không thực hiện normalize/clean semantic.
    """

    name = "tgdd_base"
    allowed_domains = [
        "thegioididong.com",
        "www.thegioididong.com",
        "api.thegioididong.com",
    ]

    API_URL = "https://api.thegioididong.com/gw/bus-tgdd-tmdt/api/Cate/GetproductCateV2"

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    url_cate: str = "laptop"
    cate_id: str = "17"
    referer: str = "https://www.thegioididong.com"

    # Default limits
    max_products: int = 50

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 5.0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5.0,
        "AUTOTHROTTLE_MAX_DELAY": 60.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
        "LOG_LEVEL": "INFO",
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }

    def __init__(
        self,
        max_products: Optional[int] = None,
        batch_id: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        if max_products is not None:
            self.max_products = int(max_products)

        now = datetime.now().astimezone()
        self.batch_id = batch_id or now.strftime("%Y%m%d_%H%M%S")
        self.scheduled_products = 0
        self.scraped_items_count = 0

    # ---------------------------------------------------------
    # 1. START REQUESTS (Async generator theo chuẩn Scrapy 2.13+)
    # ---------------------------------------------------------

    async def start(self):
        self.logger.info(
            "Khởi động spider %s [category=%s, max_products=%s, batch=%s]",
            self.name,
            self.category,
            self.max_products,
            self.batch_id,
        )
        yield self.make_listing_request(page=1)

    # ---------------------------------------------------------
    # 2. MAKE LISTING REQUEST
    # ---------------------------------------------------------

    def make_listing_request(self, page: int):
        payload = {
            "pageIndex": page,
            "pageSize": 20,
            "provinceId": 1000,
            "urlCate": self.url_cate,
            "cateId": self.cate_id,
            "filters": [
                {
                    "filterId": 1,
                    "filterTypeId": 6,
                    "sortName": "FEATURED_PRODUCTS",
                    "url": "",
                }
            ],
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": self.referer,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Os": "WebTGDD",
            "Platform": "1",
            "Provinceid": "1000",
            "Siteid": "1",
            "Isverify": "0",
        }

        return scrapy.Request(
            url=self.API_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_listing,
            meta={"page": page},
            dont_filter=True,
        )

    # ---------------------------------------------------------
    # 3. PARSE LISTING RESPONSE
    # ---------------------------------------------------------

    def parse_listing(self, response):
        page = response.meta.get("page", 1)
        self.logger.info("Parsing listing page=%s (status=%s)", page, response.status)

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error("Không decode được JSON ở page=%s: %s", page, exc)
            return

        data = body.get("data", {})
        products = data.get("products", [])

        if not products:
            self.logger.info("Không còn sản phẩm ở page=%s. Kết thúc listing.", page)
            return

        self.logger.info(
            "Tìm thấy %s sản phẩm trong response page=%s",
            len(products),
            page,
        )

        for p in products:
            if self.scheduled_products >= self.max_products:
                self.logger.info(
                    "Đạt giới hạn scheduled_products=%s. Dừng lên lịch sản phẩm mới.",
                    self.max_products,
                )
                break

            item = self.extract_listing_item(p)
            self.scheduled_products += 1

            product_url = item.get("product_url_raw")
            if product_url:
                yield scrapy.Request(
                    url=product_url,
                    callback=self.parse_detail,
                    meta={"item": item},
                    errback=self.errback_detail,
                    dont_filter=True,
                )
            else:
                yield item

        # Phân trang
        if len(products) > 0 and self.scheduled_products < self.max_products:
            next_page = page + 1
            self.logger.info("Tiếp tục crawl listing page=%s", next_page)
            yield self.make_listing_request(page=next_page)

    # ---------------------------------------------------------
    # 4. EXTRACT RAW ITEM FROM LISTING JSON
    # ---------------------------------------------------------

    def extract_listing_item(self, p: Dict[str, Any]) -> TechProductRawItem:
        """
        Trích xuất các trường từ JSON sản phẩm của TGDĐ.
        Bảo toàn kiểu dữ liệu gốc (số nguyên, chuỗi, dict) và không chuẩn hóa.
        """
        raw_prices = p.get("productPrices") or []
        price_raw = None
        original_price_raw = None
        if raw_prices and isinstance(raw_prices, list):
            first_price = raw_prices[0]
            if isinstance(first_price, dict):
                price_raw = first_price.get("price")
                original_price_raw = first_price.get("sysPrice")

        url_path = p.get("url") or ""
        product_url = (
            urljoin("https://www.thegioididong.com/", url_path)
            if url_path
            else ""
        )

        brand_info = p.get("brand") or {}
        brand_raw = (
            brand_info.get("brandName")
            if isinstance(brand_info, dict)
            else str(brand_info)
        )

        item = TechProductRawItem()
        item["source"] = "tgdd"
        item["category"] = self.category
        item["crawl_batch"] = self.batch_id
        item["crawl_time"] = datetime.now().astimezone().isoformat(timespec="seconds")

        item["product_id_raw"] = str(p.get("id") or p.get("productCode") or "")
        item["product_url_raw"] = product_url
        item["product_name_raw"] = p.get("name") or ""

        item["price_raw"] = price_raw
        item["original_price_raw"] = original_price_raw

        item["seller_raw"] = "Thế Giới Di Động"
        item["rating_raw"] = p.get("rate")
        item["review_count_raw"] = p.get("totalRate")

        item["attributes_raw"] = {}

        # Các trường phụ trợ bổ ích bảo toàn dạng raw
        item["brand_raw"] = brand_raw
        item["total_sold_raw"] = p.get("totalSold")
        item["sku_raw"] = p.get("productNameSKU")

        return item

    # ---------------------------------------------------------
    # 5. PARSE PRODUCT DETAIL PAGE
    # ---------------------------------------------------------

    def parse_detail(self, response):
        item = response.meta["item"]
        self.logger.info("Parsing detail page: %s", response.url)

        # Lấy thông số kỹ thuật (attributes_raw)
        attributes = self.extract_attributes(response.text)
        item["attributes_raw"] = attributes

        # Nếu tên ở listing bị thiếu, lấy fallback từ h1 detail
        if not item.get("product_name_raw"):
            h1 = response.css("h1::text").get()
            if h1:
                item["product_name_raw"] = h1.strip()

        self.scraped_items_count += 1
        yield item

    # ---------------------------------------------------------
    # 6. EXTRACT ATTRIBUTES (LD+JSON + DOM Fallback)
    # ---------------------------------------------------------

    def extract_attributes(self, html_text: str) -> Dict[str, Any]:
        """
        Trích xuất toàn bộ đặc tính kỹ thuật từ detail page.
        Ưu tiên cấu trúc additionalProperty trong Schema.org LD+JSON.
        Fallback sang khối thông số kỹ thuật trong DOM HTML nếu cần.
        Bảo toàn tên thuộc tính và giá trị gốc, không normalize.
        """
        attributes: Dict[str, Any] = {}
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Trích xuất từ LD+JSON (Product hoặc ProductGroup)
        ld_scripts = soup.find_all("script", type="application/ld+json")
        for s in ld_scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                if isinstance(data, dict):
                    if data.get("@type") in ("Product", "ProductGroup"):
                        props = data.get("additionalProperty") or []
                        for prop in props:
                            if isinstance(prop, dict):
                                name = prop.get("name")
                                val = prop.get("value")
                                if name and val is not None:
                                    self._add_attribute(
                                        attributes,
                                        str(name).strip(),
                                        str(val).strip(),
                                    )
            except Exception:
                pass

        # 2. Fallback sang DOM section "Thông số kỹ thuật" nếu LD+JSON không có
        if not attributes:
            for sec in soup.find_all("section"):
                sec_text = sec.get_text()
                if "thông số kỹ thuật" in sec_text.lower():
                    for el in sec.find_all(["li", "div", "tr", "p"], recursive=True):
                        # Bỏ qua element cha chứa element con cùng loại để tránh trùng lặp text
                        if el.find(["li", "div", "tr", "p"]):
                            continue
                        txt = el.get_text(strip=True)
                        if ":" in txt and len(txt) < 150:
                            parts = txt.split(":", 1)
                            k, v = parts[0].strip(), parts[1].strip()
                            if k and v:
                                self._add_attribute(attributes, k, v)

        return attributes

    @staticmethod
    def _add_attribute(attributes: Dict[str, Any], key: str, value: Any):
        """
        Xử lý khi một thuộc tính xuất hiện nhiều lần (không ghi đè âm thầm).
        """
        if key not in attributes:
            attributes[key] = value
        elif isinstance(attributes[key], list):
            if value not in attributes[key]:
                attributes[key].append(value)
        elif attributes[key] != value:
            attributes[key] = [attributes[key], value]

    # ---------------------------------------------------------
    # 7. ERRBACK HANDLER
    # ---------------------------------------------------------

    def errback_detail(self, failure):
        req = failure.request
        self.logger.error("Lỗi khi request detail URL: %s (%s)", req.url, failure.value)
        item = req.meta.get("item")
        if item:
            self.logger.warning("Yield item từ listing dù detail page gặp lỗi: %s", req.url)
            self.scraped_items_count += 1
            yield item
