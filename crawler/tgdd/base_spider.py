import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    from items import TechProductRawItem, TechReviewRawItem


_UNSET = object()


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
    COMMENT_API_URL = "https://api.thegioididong.com/gw/bus-tgdd-tmdt/api/Comment/Product/Code"

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    url_cate: str = "laptop"
    cate_id: str = "17"
    referer: str = "https://www.thegioididong.com"

    # Default limits (pilot mode = 50, full crawl mode = None)
    max_products: Optional[int] = 50
    crawl_reviews: bool = False
    max_review_pages: int = 50

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
        "ITEM_PIPELINES": {
            "crawler.tgdd.pipelines.TgddReviewExportPipeline": 300,
        },
    }

    def __init__(
        self,
        max_products: Any = _UNSET,
        batch_id: Optional[str] = None,
        crawl_reviews: Any = _UNSET,
        max_review_pages: Any = _UNSET,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        if max_products is _UNSET:
            self.max_products = 50
        elif max_products is None or (
            isinstance(max_products, str)
            and max_products.strip().lower() in ("none", "null", "unlimited", "")
        ):
            self.max_products = None
        else:
            self.max_products = int(max_products)

        now = datetime.now().astimezone()
        self.batch_id = batch_id or now.strftime("%Y%m%d_%H%M%S")
        self.scheduled_products = 0
        self.scraped_items_count = 0
        self.variant_items_yielded = 0
        self.listing_pages_processed = 0
        self.listing_failures = 0
        self.detail_successes = 0
        self.detail_failures = 0
        self.attribute_extraction_successes = 0
        self.attribute_extraction_failures = 0
        self.last_listing_page = 0
        self.stop_reason = "in_progress"
        self.seen_page_signatures = set()

        # Metrics và trạng thái thu thập review
        self.review_requests_scheduled = 0
        self.review_pages_processed = 0
        self.review_failures = 0
        self.reviews_yielded = 0
        self.seen_review_ids = set()

        if crawl_reviews is not _UNSET:
            if isinstance(crawl_reviews, str):
                self.crawl_reviews = crawl_reviews.strip().lower() in ("true", "1", "yes")
            else:
                self.crawl_reviews = bool(crawl_reviews)
        else:
            self.crawl_reviews = getattr(self, "crawl_reviews", False)

        if max_review_pages is not _UNSET and max_review_pages is not None:
            self.max_review_pages = int(max_review_pages)
        else:
            self.max_review_pages = getattr(self, "max_review_pages", 50)

        self.review_output = kwargs.get("review_output")

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
        yield self.make_listing_request(page=0)

    # ---------------------------------------------------------
    # 2. MAKE LISTING REQUEST & ERRBACK
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

        # Không dùng dont_filter=True: Scrapy RFPDupeFilter tự động nhận diện
        # các trang khác nhau dựa trên POST body (chứa pageIndex khác nhau)
        # đồng thời chặn gửi lặp request cho cùng một page.
        return scrapy.Request(
            url=self.API_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_listing,
            errback=self.errback_listing,
            meta={"page": page},
        )

    def errback_listing(self, failure):
        req = failure.request
        page = req.meta.get("page", 1) if req.meta else 1
        self.listing_failures += 1
        if self.stop_reason == "in_progress":
            self.stop_reason = "error/failure"
        self.logger.error(
            "Listing request thất bại tại page=%s [url=%s]: %s",
            page,
            req.url,
            failure.value,
        )

    # ---------------------------------------------------------
    # 3. PARSE LISTING RESPONSE
    # ---------------------------------------------------------

    def parse_listing(self, response):
        page = response.meta.get("page", 1)
        self.last_listing_page = page
        self.logger.info("Parsing listing page=%s (status=%s)", page, response.status)

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error("Không decode được JSON ở listing page=%s (status=%s): %s", page, response.status, exc)
            self.listing_failures += 1
            if self.stop_reason == "in_progress":
                self.stop_reason = "error/failure"
            return

        self.listing_pages_processed += 1
        data = body.get("data", {})
        products = data.get("products", [])

        if not products:
            self.logger.info("Không còn sản phẩm ở page=%s. Kết thúc listing.", page)
            if self.stop_reason == "in_progress":
                self.stop_reason = "no_more_products"
            return

        # Pagination guard: kiểm tra page signature để tránh infinite loop
        page_signature = tuple(
            str(p.get("id") or p.get("productCode") or p.get("url") or "")
            for p in products
        )
        if page_signature in self.seen_page_signatures:
            self.logger.warning(
                "Phát hiện page signature bị lặp lại tại page=%s (danh sách sản phẩm giống hệt page trước). "
                "Dừng pagination để bảo vệ an toàn HTTP crawler.",
                page,
            )
            self.stop_reason = "repeated_page_signature"
            return

        self.seen_page_signatures.add(page_signature)

        self.logger.info(
            "Tìm thấy %s sản phẩm trong response page=%s",
            len(products),
            page,
        )

        for p in products:
            if self.max_products is not None and self.scheduled_products >= self.max_products:
                self.logger.info(
                    "Đạt giới hạn scheduled_products=%s. Dừng lên lịch sản phẩm mới.",
                    self.max_products,
                )
                self.stop_reason = "max_products_reached"
                break

            item = self.extract_listing_item(p)
            self.scheduled_products += 1

            product_url = item.get("product_url_raw")
            if product_url:
                # Không dùng dont_filter=True: tránh gửi lặp HTTP request tới cùng URL sản phẩm
                yield scrapy.Request(
                    url=product_url,
                    callback=self.parse_detail,
                    meta={"item": item},
                    errback=self.errback_detail,
                )
            else:
                self.logger.warning(
                    "Sản phẩm listing không có URL [product_id=%s]: %s",
                    item.get("product_id_raw"),
                    item.get("product_name_raw"),
                )
                yield item

        # Phân trang: tiếp tục khi còn sản phẩm và (chưa đạt max_products hoặc đang chạy full crawl)
        if len(products) > 0 and (
            self.max_products is None or self.scheduled_products < self.max_products
        ):
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

        # Hierarchy & Variant placeholders (mặc định phản ánh sản phẩm listing)
        item["parent_product_id_raw"] = item["product_id_raw"]
        item["parent_product_name_raw"] = item["product_name_raw"]
        item["parent_url_raw"] = product_url
        item["variant_name_raw"] = None
        item["variant_color_raw"] = None
        item["variant_url_raw"] = None
        item["variant_sku_raw"] = None
        item["availability_raw"] = None

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
        item["raw_payload"] = p

        return item

    # ---------------------------------------------------------
    # 5. PARSE PRODUCT DETAIL PAGE & EXTRACT VARIANTS
    # ---------------------------------------------------------

    def parse_detail(self, response):
        item = response.meta["item"]
        product_id = item.get("product_id_raw", "unknown")
        self.logger.info("Parsing detail page: %s [product_id=%s, status=%s]", response.url, product_id, response.status)
        self.detail_successes += 1

        # Lấy thông số kỹ thuật chung (attributes_raw)
        try:
            attributes = self.extract_attributes(response.text)
        except Exception as exc:
            self.logger.error(
                "Ngoại lệ khi trích xuất attributes tại detail url=%s [product_id=%s]: %s",
                response.url,
                product_id,
                exc,
            )
            attributes = {}

        if attributes:
            self.attribute_extraction_successes += 1
            self.logger.info("Trích xuất thành công %s thuộc tính kỹ thuật tại %s", len(attributes), response.url)
        else:
            self.attribute_extraction_failures += 1
            self.logger.warning("Không tìm thấy thuộc tính kỹ thuật nào tại detail url=%s [product_id=%s]", response.url, product_id)

        # Nếu tên ở listing bị thiếu, lấy fallback từ h1 detail
        parent_name = item.get("product_name_raw")
        if not parent_name:
            h1 = response.css("h1::text").get()
            if h1:
                parent_name = h1.strip()
                item["product_name_raw"] = parent_name

        parent_product_id = item.get("product_id_raw")
        parent_url = item.get("product_url_raw") or response.url

        # Đồng bộ thông tin parent trên item
        item["parent_product_id_raw"] = parent_product_id
        item["parent_product_name_raw"] = parent_name
        item["parent_url_raw"] = parent_url

        # Trích xuất danh sách biến thể từ Schema.org ProductGroup.hasVariant
        try:
            raw_variants = self.extract_variants(response.text)
        except Exception as exc:
            self.logger.error(
                "Ngoại lệ khi trích xuất variants tại detail url=%s [product_id=%s]: %s",
                response.url,
                product_id,
                exc,
            )
            raw_variants = []

        known_variant_skus = set()
        if raw_variants:
            self.logger.info(
                "Trích xuất %s variants từ ProductGroup tại url=%s [product_id=%s]",
                len(raw_variants),
                response.url,
                product_id,
            )
            for v in raw_variants:
                var_item = TechProductRawItem()
                # Kế thừa dữ liệu metadata và parent từ listing
                for k, val in item.items():
                    var_item[k] = val

                var_item["attributes_raw"] = attributes

                # Giữ nguyên semantics các trường cấp product/parent
                var_item["product_id_raw"] = parent_product_id
                var_item["product_name_raw"] = parent_name
                var_item["product_url_raw"] = parent_url
                var_item["parent_product_id_raw"] = parent_product_id
                var_item["parent_product_name_raw"] = parent_name
                var_item["parent_url_raw"] = parent_url

                # sku_raw giữ nguyên raw value cũ từ listing (productNameSKU)
                var_item["sku_raw"] = item.get("sku_raw")

                # Thông tin đặc thù của variant
                var_name = v.get("name")
                var_color = v.get("color")
                var_url = v.get("url")
                var_sku = v.get("sku")
                if var_sku is not None:
                    known_variant_skus.add(str(var_sku).strip())

                offers = v.get("offers")
                var_price = None
                var_avail = None
                var_orig_price = None
                if isinstance(offers, dict):
                    var_price = offers.get("price")
                    var_avail = offers.get("availability")
                    var_orig_price = offers.get("sysPrice") or offers.get("originalPrice")
                elif isinstance(offers, list) and len(offers) > 0 and isinstance(offers[0], dict):
                    var_price = offers[0].get("price")
                    var_avail = offers[0].get("availability")
                    var_orig_price = offers[0].get("sysPrice") or offers[0].get("originalPrice")

                var_item["variant_name_raw"] = var_name
                var_item["variant_color_raw"] = var_color
                var_item["variant_url_raw"] = var_url
                var_item["variant_sku_raw"] = str(var_sku) if var_sku is not None else None
                var_item["availability_raw"] = var_avail

                # price_raw: giá của chính variant
                if var_price is not None:
                    var_item["price_raw"] = var_price

                # original_price_raw: chỉ gán nếu có evidence từ variant/source; không tự suy diễn
                var_item["original_price_raw"] = var_orig_price
                var_item["raw_payload"] = v

                self.scraped_items_count += 1
                self.variant_items_yielded += 1
                yield var_item
        else:
            # Fallback về đúng 1 item cấp product khi không có hasVariant
            item["attributes_raw"] = attributes
            item["variant_name_raw"] = None
            item["variant_color_raw"] = None
            item["variant_url_raw"] = None
            item["variant_sku_raw"] = None
            item["availability_raw"] = None
            item["raw_payload"] = item.get("raw_payload") or {}

            self.scraped_items_count += 1
            yield item

        # Schedule review request cho parent product (chỉ 1 request đầu tiên, không duplicate theo variant)
        if getattr(self, "crawl_reviews", False) and parent_product_id:
            yield self.make_review_request(
                product_id=str(parent_product_id),
                product_url=parent_url,
                page_index=0,
                known_variant_skus=known_variant_skus,
            )

    # ---------------------------------------------------------
    # 6. EXTRACT VARIANTS (Schema.org ProductGroup hasVariant)
    # ---------------------------------------------------------

    def extract_variants(self, html_text: str) -> List[Dict[str, Any]]:
        """
        Trích xuất danh sách biến thể từ Schema.org ProductGroup có hasVariant.
        Bảo toàn cấu trúc và giá trị gốc, xử lý an toàn nếu JSON-LD malformed.
        """
        variants: List[Dict[str, Any]] = []
        soup = BeautifulSoup(html_text, "html.parser")
        ld_scripts = soup.find_all("script", type="application/ld+json")
        for s in ld_scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                objects = []
                if isinstance(data, dict):
                    if "@graph" in data and isinstance(data["@graph"], list):
                        objects.extend(data["@graph"])
                    else:
                        objects.append(data)
                elif isinstance(data, list):
                    objects.extend(data)

                for obj in objects:
                    if isinstance(obj, dict) and obj.get("@type") == "ProductGroup":
                        has_var = obj.get("hasVariant")
                        if isinstance(has_var, list) and has_var:
                            for v in has_var:
                                if isinstance(v, dict):
                                    variants.append(v)
                            if variants:
                                return variants
            except json.JSONDecodeError as exc:
                self.logger.warning("Lỗi decode JSON-LD script khi trích xuất variants: %s", exc)
            except Exception as exc:
                self.logger.warning("Lỗi không mong muốn khi trích xuất variants: %s", exc)

        return variants

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
            except json.JSONDecodeError as exc:
                self.logger.warning("Lỗi decode JSON-LD script tại detail page: %s", exc)
            except Exception as exc:
                self.logger.warning("Lỗi không mong muốn khi xử lý JSON-LD script: %s", exc)

        # 2. Fallback sang DOM section "Thông số kỹ thuật" nếu LD+JSON không có
        if not attributes:
            try:
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
            except Exception as exc:
                self.logger.warning("Lỗi khi fallback DOM thông số kỹ thuật: %s", exc)

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
        item = req.meta.get("item") if req.meta else None
        product_id = item.get("product_id_raw", "unknown") if item else "unknown"
        product_name = item.get("product_name_raw", "unknown") if item else "unknown"

        self.detail_failures += 1
        self.attribute_extraction_failures += 1
        self.logger.error(
            "Detail request thất bại: url=%s [product_id=%s, name=%s, error=%s]",
            req.url,
            product_id,
            product_name,
            failure.value,
        )
        if item:
            self.logger.warning(
                "Lưu fallback item từ listing do detail request thất bại [product_id=%s, url=%s]",
                product_id,
                req.url,
            )
            item["parent_product_id_raw"] = item.get("product_id_raw")
            item["parent_product_name_raw"] = item.get("product_name_raw")
            item["parent_url_raw"] = item.get("product_url_raw") or req.url
            item["variant_name_raw"] = None
            item["variant_color_raw"] = None
            item["variant_url_raw"] = None
            item["variant_sku_raw"] = None
            item["availability_raw"] = None
            item["raw_payload"] = item.get("raw_payload") or {}

            self.scraped_items_count += 1
            yield item

    # ---------------------------------------------------------
    # 8. MAKE & PARSE REVIEWS (Comment API & Pagination)
    # ---------------------------------------------------------

    def make_review_request(
        self,
        product_id: str,
        product_url: str,
        page_index: int = 0,
        page_size: int = 20,
        known_variant_skus: Optional[Any] = None,
    ) -> scrapy.Request:
        payload = {
            "modelCode": str(product_id),
            "pageIndex": page_index,
            "pageSize": page_size,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Referer": product_url or self.referer,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Os": "WebTGDD",
            "Platform": "1",
            "Provinceid": "3",
            "Siteid": "1",
        }
        self.review_requests_scheduled += 1
        return scrapy.Request(
            url=self.COMMENT_API_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_reviews,
            errback=self.errback_reviews,
            meta={
                "parent_product_id": str(product_id),
                "parent_product_url": product_url,
                "page_index": page_index,
                "page_size": page_size,
                "known_variant_skus": list(known_variant_skus) if known_variant_skus else [],
            },
        )

    def errback_reviews(self, failure):
        req = failure.request
        meta = req.meta or {}
        parent_product_id = meta.get("parent_product_id", "unknown")
        page_index = meta.get("page_index", 0)
        self.review_failures += 1
        self.logger.error(
            "Review request thất bại cho product %s (page=%s): %s",
            parent_product_id,
            page_index,
            failure.value,
        )

    def parse_reviews(self, response):
        self.review_pages_processed += 1
        meta = response.meta or {}
        parent_product_id = meta.get("parent_product_id")
        parent_product_url = meta.get("parent_product_url")
        page_index = meta.get("page_index", 0)
        page_size = meta.get("page_size", 20)
        known_variant_skus = set(meta.get("known_variant_skus") or [])

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error(
                "Không decode được JSON ở review response cho product %s (page=%s): %s",
                parent_product_id,
                page_index,
                exc,
            )
            self.review_failures += 1
            return

        if not isinstance(body, dict) or body.get("code") != 0:
            msg = body.get("message") if isinstance(body, dict) else str(body)
            self.logger.warning(
                "Review API trả về mã lỗi hoặc format không hợp lệ cho product %s (page=%s): code=%s, msg=%s",
                parent_product_id,
                page_index,
                body.get("code") if isinstance(body, dict) else None,
                msg,
            )
            self.review_failures += 1
            return

        data_obj = body.get("data")
        if not isinstance(data_obj, dict):
            return

        total = data_obj.get("total", 0) or 0
        comments = data_obj.get("comments", [])
        if not isinstance(comments, list):
            comments = []

        for c in comments:
            if not isinstance(c, dict):
                continue

            comment_id = str(c.get("commentId") or "")
            if not comment_id:
                continue

            # Duplicate review guard
            if comment_id in self.seen_review_ids:
                continue
            self.seen_review_ids.add(comment_id)

            review_item = TechReviewRawItem()
            review_item["source"] = "tgdd"
            review_item["category"] = self.category
            review_item["crawl_batch"] = self.batch_id
            review_item["crawl_time"] = datetime.now().astimezone().isoformat(timespec="seconds")

            review_item["parent_product_id_raw"] = parent_product_id
            review_item["parent_product_url_raw"] = parent_product_url

            review_item["review_id_raw"] = comment_id
            review_item["rating_raw"] = c.get("score")
            review_item["review_text_raw"] = c.get("content")
            review_item["author_raw"] = c.get("fullName")
            review_item["review_time_raw"] = c.get("createdDate")
            review_item["like_count_raw"] = c.get("likeCount")

            # Raw source fields đúng semantics
            product_code = c.get("productCode")
            product_code_raw = str(product_code).strip() if product_code is not None else None
            variant_code = c.get("variantCode")
            variant_code_raw = str(variant_code).strip() if variant_code is not None else None

            review_item["review_product_code_raw"] = product_code_raw
            review_item["variant_code_raw"] = variant_code_raw

            # Chỉ điền variant_sku_raw khi có evidence rằng productCode match một variant.sku
            # thuộc hasVariant của parent product
            if product_code_raw and (product_code_raw in known_variant_skus):
                review_item["variant_sku_raw"] = product_code_raw
            else:
                review_item["variant_sku_raw"] = None

            # Raw attributes bổ sung từ source
            review_item["buy_date_raw"] = c.get("cbuyDate") or c.get("deliveryDate")
            review_item["reply_raw"] = c.get("responseContent")
            review_item["attached_files_raw"] = c.get("commentAttachedFileBOList")
            review_item["raw_payload"] = c

            self.reviews_yielded += 1
            yield review_item

        # Pagination: tiếp tục nếu còn trang
        max_review_pages = getattr(self, "max_review_pages", 50)
        if len(comments) > 0 and ((page_index + 1) * page_size < total) and ((page_index + 1) < max_review_pages):
            next_page = page_index + 1
            yield self.make_review_request(
                product_id=parent_product_id,
                product_url=parent_product_url,
                page_index=next_page,
                page_size=page_size,
                known_variant_skus=known_variant_skus,
            )

    # ---------------------------------------------------------
    # 9. SPIDER CLOSED SUMMARY
    # ---------------------------------------------------------

    def closed(self, reason: str):
        if self.stop_reason == "in_progress":
            self.stop_reason = reason or "finished"

        self.logger.info(
            "====================================================\n"
            "CRAWL SUMMARY [%s]:\n"
            "  - finish_reason: %s\n"
            "  - stop_reason: %s\n"
            "  - last_listing_page: %s\n"
            "  - listing_pages_processed: %s\n"
            "  - listing_failures: %s\n"
            "  - scheduled_products: %s\n"
            "  - scraped_items_count: %s\n"
            "  - variant_items_yielded: %s\n"
            "  - detail_successes: %s\n"
            "  - detail_failures: %s\n"
            "  - attribute_extraction_successes: %s\n"
            "  - attribute_extraction_failures: %s\n"
            "  - review_requests_scheduled: %s\n"
            "  - review_pages_processed: %s\n"
            "  - review_failures: %s\n"
            "  - reviews_yielded: %s\n"
            "====================================================",
            self.name,
            reason,
            self.stop_reason,
            self.last_listing_page,
            self.listing_pages_processed,
            self.listing_failures,
            self.scheduled_products,
            self.scraped_items_count,
            self.variant_items_yielded,
            self.detail_successes,
            self.detail_failures,
            self.attribute_extraction_successes,
            self.attribute_extraction_failures,
            self.review_requests_scheduled,
            self.review_pages_processed,
            self.review_failures,
            self.reviews_yielded,
        )
