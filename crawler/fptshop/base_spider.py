import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.fptshop.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    from items import TechProductRawItem, TechReviewRawItem


_UNSET = object()


class FptshopBaseSpider(scrapy.Spider):
    """
    Base spider cho sàn FPT Shop (FPTShop).
    Thu thập dữ liệu theo chuẩn TV1 (Web Crawling & Data Acquisition).
    Tuân thủ tuyệt đối Canonical Product & Review Raw Data Contract:
    - Cùng schema, cùng semantic invariants với TGDĐ.
    - Không thực hiện normalize hay clean semantic tại TV1 (thuộc TV2).
    """

    name = "fptshop_base"
    allowed_domains = [
        "fptshop.com.vn",
        "www.fptshop.com.vn",
        "papi.fptshop.com.vn",
    ]

    CATEGORY_API_URL = "https://papi.fptshop.com.vn/gw/v1/public/fulltext-search-service/category"
    COMMENT_API_URL = "https://papi.fptshop.com.vn/gw/v1/public/bff-before-order/comment/list"

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    slug: str = "may-tinh-xach-tay"

    # Default limits
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
            "crawler.fptshop.pipelines.FptshopReviewExportPipeline": 300,
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

        # Review observability metrics
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
    # 1. START REQUESTS
    # ---------------------------------------------------------

    async def start(self):
        self.logger.info(
            "Khởi động spider %s [category=%s, max_products=%s, batch=%s]",
            self.name,
            self.category,
            self.max_products,
            self.batch_id,
        )
        yield self.make_listing_request(page=0, skip_count=0)

    # ---------------------------------------------------------
    # 2. MAKE LISTING REQUEST & ERRBACK
    # ---------------------------------------------------------

    def make_listing_request(self, page: int, skip_count: int = 0):
        payload = {
            "slug": self.slug,
            "categoryType": "category",
            "skipCount": skip_count,
            "maxResultCount": 24,
            "sortMethod": "noi-bat",
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://fptshop.com.vn",
            "Referer": f"https://fptshop.com.vn/{self.slug}",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

        return scrapy.Request(
            url=self.CATEGORY_API_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_listing,
            errback=self.errback_listing,
            meta={"page": page, "skip_count": skip_count},
        )

    def errback_listing(self, failure):
        req = failure.request
        page = req.meta.get("page", 0) if req.meta else 0
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
        page = response.meta.get("page", 0)
        skip_count = response.meta.get("skip_count", 0)
        self.last_listing_page = page
        self.logger.info("Parsing FPTShop listing page=%s (status=%s)", page, response.status)

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error("Không decode được JSON ở listing page=%s (status=%s): %s", page, response.status, exc)
            self.listing_failures += 1
            if self.stop_reason == "in_progress":
                self.stop_reason = "error/failure"
            return

        self.listing_pages_processed += 1
        items = body.get("items", []) if isinstance(body, dict) else []
        total_count = body.get("totalCount", 0) if isinstance(body, dict) else 0

        if not items:
            self.logger.info("Không còn sản phẩm ở page=%s. Kết thúc listing.", page)
            if self.stop_reason == "in_progress":
                self.stop_reason = "no_more_products"
            return

        # Pagination guard: kiểm tra lặp page signature
        page_signature = tuple(str(it.get("code") or it.get("slug") or "") for it in items)
        if page_signature in self.seen_page_signatures:
            self.logger.warning(
                "Phát hiện page signature bị lặp lại tại page=%s. Dừng pagination.",
                page,
            )
            self.stop_reason = "repeated_page_signature"
            return

        self.seen_page_signatures.add(page_signature)
        self.logger.info("Tìm thấy %s sản phẩm trong response page=%s", len(items), page)

        for it in items:
            if self.max_products is not None and self.scheduled_products >= self.max_products:
                self.logger.info(
                    "Đạt giới hạn scheduled_products=%s. Dừng lên lịch sản phẩm mới.",
                    self.max_products,
                )
                self.stop_reason = "max_products_reached"
                break

            self.scheduled_products += 1
            slug = it.get("slug") or ""
            detail_url = urljoin("https://fptshop.com.vn/", slug) if slug else None

            if detail_url:
                yield scrapy.Request(
                    url=detail_url,
                    callback=self.parse_detail,
                    meta={"listing_data": it},
                    errback=self.errback_detail,
                )
            else:
                yield from self.yield_products_and_reviews(it, attributes={}, detail_url=None)

        # Phân trang
        if len(items) > 0 and (
            self.max_products is None or self.scheduled_products < self.max_products
        ) and (skip_count + len(items) < total_count):
            next_page = page + 1
            next_skip = next_page * 24
            self.logger.info("Tiếp tục crawl listing page=%s (skipCount=%s)", next_page, next_skip)
            yield self.make_listing_request(page=next_page, skip_count=next_skip)

    # ---------------------------------------------------------
    # 4. PARSE DETAIL & ATTRIBUTES
    # ---------------------------------------------------------

    def parse_detail(self, response):
        it = response.meta["listing_data"]
        product_code = it.get("code", "unknown")
        self.logger.info("Parsing detail page: %s [code=%s, status=%s]", response.url, product_code, response.status)
        self.detail_successes += 1

        try:
            attributes = self.extract_attributes(response.text)
        except Exception as exc:
            self.logger.error("Lỗi khi trích xuất attributes tại detail url=%s: %s", response.url, exc)
            attributes = {}

        if attributes:
            self.attribute_extraction_successes += 1
            self.logger.info("Trích xuất thành công %s thuộc tính kỹ thuật tại %s", len(attributes), response.url)
        else:
            self.attribute_extraction_failures += 1
            self.logger.warning("Không tìm thấy thuộc tính kỹ thuật nào tại detail url=%s", response.url)

        yield from self.yield_products_and_reviews(it, attributes, detail_url=response.url)

    def extract_attributes(self, html_text: str) -> Dict[str, Any]:
        """
        Trích xuất thông số kỹ thuật (attributes_raw) từ trang chi tiết FPTShop:
        1. Ưu tiên Schema.org Product additionalProperty
        2. Fallback sang HTML table DOM
        """
        attributes: Dict[str, Any] = {}
        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Schema.org LD+JSON
        ld_scripts = soup.find_all("script", type="application/ld+json")
        for s in ld_scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
                objs = data if isinstance(data, list) else [data]
                for obj in objs:
                    if isinstance(obj, dict) and obj.get("@type") == "Product":
                        props = obj.get("additionalProperty")
                        if isinstance(props, list):
                            for p in props:
                                if isinstance(p, dict):
                                    name = p.get("name")
                                    val = p.get("value")
                                    if name and val is not None:
                                        self._add_attribute(attributes, str(name).strip(), str(val).strip())
                            if attributes:
                                return attributes
            except Exception:
                pass

        # 2. DOM Table Fallback
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = tr.find_all(["th", "td"])
                if len(cells) >= 2:
                    k = cells[0].get_text(strip=True)
                    v = cells[1].get_text(strip=True)
                    if k and v and k not in ("Thông số", "Tiêu chí", "Chi tiết"):
                        self._add_attribute(attributes, k, v)

        return attributes

    @staticmethod
    def _add_attribute(attributes: Dict[str, Any], key: str, value: Any):
        if key not in attributes:
            attributes[key] = value
        elif isinstance(attributes[key], list):
            if value not in attributes[key]:
                attributes[key].append(value)
        elif attributes[key] != value:
            attributes[key] = [attributes[key], value]

    # ---------------------------------------------------------
    # 5. YIELD PRODUCTS & SCHEDULE REVIEWS (Canonical Contract)
    # ---------------------------------------------------------

    def yield_products_and_reviews(
        self,
        it: Dict[str, Any],
        attributes: Dict[str, Any],
        detail_url: Optional[str] = None,
    ):
        code = str(it.get("code") or "").strip()
        name = it.get("name") or it.get("displayName") or ""
        slug = it.get("slug") or ""
        parent_url = urljoin("https://fptshop.com.vn/", slug) if slug else (detail_url or "")

        brand_info = it.get("brand") or {}
        brand_raw = brand_info.get("name") if isinstance(brand_info, dict) else (str(brand_info) if brand_info else None)
        seller_raw = "FPT Shop"
        rating_raw = it.get("averageScore") or it.get("score")
        review_count_raw = None

        sold_info = it.get("sold")
        total_sold_raw = (
            str(sold_info.get("realQuantity") or sold_info.get("totalQuantity") or "")
            if isinstance(sold_info, dict)
            else (str(sold_info) if sold_info else None)
        )
        if total_sold_raw == "":
            total_sold_raw = None

        skus = it.get("skus") or []
        known_variant_skus = set()

        if skus and isinstance(skus, list):
            for s in skus:
                if not isinstance(s, dict):
                    continue

                sku_val = str(s.get("sku") or "").strip()
                if sku_val:
                    known_variant_skus.add(sku_val)

                item = TechProductRawItem()
                item["source"] = "fptshop"
                item["category"] = self.category
                item["crawl_batch"] = self.batch_id
                item["crawl_time"] = datetime.now().astimezone().isoformat(timespec="seconds")

                # Product / Model level identifiers
                item["product_id_raw"] = code
                item["product_name_raw"] = name
                item["product_url_raw"] = parent_url

                # Hierarchy trỏ về parent
                item["parent_product_id_raw"] = code
                item["parent_product_name_raw"] = name
                item["parent_url_raw"] = parent_url

                # Variant level particulars
                item["sku_raw"] = sku_val or None
                item["variant_sku_raw"] = sku_val or None
                item["variant_name_raw"] = s.get("name") or s.get("displayName") or None

                # Extract color from variants array
                var_color = None
                for v in s.get("variants") or []:
                    if isinstance(v, dict) and v.get("propertyName") == "color":
                        var_color = v.get("displayValue") or v.get("value")
                        break
                item["variant_color_raw"] = var_color

                sku_slug = s.get("slug")
                item["variant_url_raw"] = urljoin("https://fptshop.com.vn/", sku_slug) if sku_slug else None

                # Availability
                status_web = s.get("statusOnWeb")
                avail = status_web.get("displayName") if isinstance(status_web, dict) else None
                if not avail:
                    p_status = s.get("productStatus")
                    avail = p_status.get("displayName") if isinstance(p_status, dict) else None
                item["availability_raw"] = avail

                # Pricing: numeric int
                price_val = s.get("currentPrice") if s.get("currentPrice") is not None else s.get("price")
                item["price_raw"] = price_val
                item["original_price_raw"] = s.get("originalPrice")

                # Brand, Seller, Stats
                item["brand_raw"] = brand_raw
                item["seller_raw"] = seller_raw
                item["rating_raw"] = rating_raw
                item["review_count_raw"] = review_count_raw
                item["total_sold_raw"] = total_sold_raw

                item["attributes_raw"] = attributes
                item["raw_payload"] = s

                self.scraped_items_count += 1
                self.variant_items_yielded += 1
                yield item
        else:
            # Single configuration fallback (variant_* = None)
            item = TechProductRawItem()
            item["source"] = "fptshop"
            item["category"] = self.category
            item["crawl_batch"] = self.batch_id
            item["crawl_time"] = datetime.now().astimezone().isoformat(timespec="seconds")

            item["product_id_raw"] = code
            item["product_name_raw"] = name
            item["product_url_raw"] = parent_url

            item["parent_product_id_raw"] = code
            item["parent_product_name_raw"] = name
            item["parent_url_raw"] = parent_url

            item["sku_raw"] = None
            item["variant_sku_raw"] = None
            item["variant_name_raw"] = None
            item["variant_color_raw"] = None
            item["variant_url_raw"] = None
            item["availability_raw"] = None

            price_val = it.get("currentPrice") if it.get("currentPrice") is not None else it.get("price")
            item["price_raw"] = price_val
            item["original_price_raw"] = it.get("originalPrice")

            item["brand_raw"] = brand_raw
            item["seller_raw"] = seller_raw
            item["rating_raw"] = rating_raw
            item["review_count_raw"] = review_count_raw
            item["total_sold_raw"] = total_sold_raw

            item["attributes_raw"] = attributes
            item["raw_payload"] = it

            self.scraped_items_count += 1
            yield item

        # Review scheduling: đúng 1 request cho parent product
        if getattr(self, "crawl_reviews", False) and code:
            yield self.make_review_request(
                product_id=code,
                product_url=parent_url,
                page_index=0,
                known_variant_skus=known_variant_skus,
            )

    # ---------------------------------------------------------
    # 6. ERRBACK DETAIL
    # ---------------------------------------------------------

    def errback_detail(self, failure):
        req = failure.request
        it = req.meta.get("listing_data") if req.meta else {}
        code = it.get("code", "unknown")
        self.detail_failures += 1
        self.attribute_extraction_failures += 1
        self.logger.error("Detail request thất bại: url=%s [code=%s, error=%s]", req.url, code, failure.value)
        if it:
            self.logger.warning("Lưu fallback item từ listing do detail request thất bại [code=%s, url=%s]", code, req.url)
            yield from self.yield_products_and_reviews(it, attributes={}, detail_url=req.url)

    # ---------------------------------------------------------
    # 7. MAKE & PARSE REVIEWS
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
            "content": {"id": str(product_id), "type": "PRODUCT"},
            "state": ["ACTIVE"],
            "score": ["5", "4", "3", "2", "1"],
            "skipCount": page_index * page_size,
            "maxResultCount": page_size,
            "sortMethod": 1,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": "https://fptshop.com.vn",
            "Referer": product_url or "https://fptshop.com.vn/",
            "order-channel": "1",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
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
        self.logger.error("Review request thất bại cho product %s (page=%s): %s", parent_product_id, page_index, failure.value)

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
            self.logger.error("Không decode được JSON ở review response cho product %s (page=%s): %s", parent_product_id, page_index, exc)
            self.review_failures += 1
            return

        data_obj = body.get("data") if isinstance(body, dict) else {}
        if not isinstance(data_obj, dict):
            return

        total = data_obj.get("totalCount", 0) or 0
        comments = data_obj.get("items", [])
        if not isinstance(comments, list):
            comments = []

        for c in comments:
            if not isinstance(c, dict):
                continue

            comment_id = str(c.get("id") or "")
            if not comment_id:
                continue

            if comment_id in self.seen_review_ids:
                continue
            self.seen_review_ids.add(comment_id)

            review_item = TechReviewRawItem()
            review_item["source"] = "fptshop"
            review_item["category"] = self.category
            review_item["crawl_batch"] = self.batch_id
            review_item["crawl_time"] = datetime.now().astimezone().isoformat(timespec="seconds")

            review_item["parent_product_id_raw"] = parent_product_id
            review_item["parent_product_url_raw"] = parent_product_url

            review_item["review_id_raw"] = comment_id
            review_item["rating_raw"] = c.get("score")
            review_item["review_text_raw"] = c.get("content")
            review_item["author_raw"] = c.get("fullName")
            review_item["review_time_raw"] = c.get("creationTime")
            review_item["like_count_raw"] = c.get("like")

            raw_sku = str(c.get("sku")).strip() if c.get("sku") else None
            order_code = str(c.get("orderCode")).strip() if c.get("orderCode") else None

            review_item["review_product_code_raw"] = raw_sku
            review_item["variant_code_raw"] = order_code

            # Linkage rule: chỉ gán variant_sku_raw khi raw_sku match known_variant_skus
            if raw_sku and (raw_sku in known_variant_skus):
                review_item["variant_sku_raw"] = raw_sku
            else:
                review_item["variant_sku_raw"] = None

            review_item["buy_date_raw"] = None
            review_item["reply_raw"] = c.get("children")
            review_item["attached_files_raw"] = c.get("media")
            review_item["raw_payload"] = c

            self.reviews_yielded += 1
            yield review_item

        # Pagination
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
    # 8. SPIDER CLOSED SUMMARY
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
