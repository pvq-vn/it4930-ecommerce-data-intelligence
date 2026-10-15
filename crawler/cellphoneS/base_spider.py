import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.cellphoneS.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    from items import TechProductRawItem, TechReviewRawItem


_UNSET = object()

# Cấu hình hằng số nguồn CellphoneS (Single Source of Truth)
CELLPHONES_DEFAULT_PROVINCE_ID: int = 30  # TP. Hồ Chí Minh (id: 30)
CATALOG_GRAPHQL_URL: str = "https://api.cellphones.com.vn/v2/graphql/query"
REVIEW_GRAPHQL_URL: str = "https://api.cellphones.com.vn/graphql-customer/graphql/query"
BASE_WEB_URL: str = "https://cellphones.com.vn"


class CellphonesBaseSpider(scrapy.Spider):
    """
    Base spider cho sàn CellphoneS.
    Thu thập dữ liệu theo chuẩn TV1 (Web Crawling & Data Acquisition).
    Tuân thủ tuyệt đối Canonical Product (25 fields) & Review (19 fields) Raw Data Contract.

    Kiến trúc thu thập:
    LISTING (GraphQL GetProductsByCateId, page=1-based)
      ↓
    PARENT (general.product_id, child_product[])
      ↓
    CHILD VARIANTS (GraphQL getDataProductChild, is_parent="false")
      ↓
    DETAIL (SSR HTML / Schema.org JSON-LD additionalProperty)
      ↓
    ATTRIBUTES (1. JSON-LD -> 2. GraphQL general.attributes -> 3. DOM fallback)
      ↓
    PRODUCT ITEMS (Yield TechProductRawItem cho từng variant)
      ↓
    REVIEWS (GraphQL Customer reviews, 5 reviews/page, linkage strictly at parent level)
    """

    name = "cellphones_base"
    allowed_domains = [
        "cellphones.com.vn",
        "api.cellphones.com.vn",
    ]

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    cate_id: str = "3"
    canonical_url: str = "https://cellphones.com.vn"

    # Default limits & configurations
    max_products: Optional[int] = 50
    province_id: int = CELLPHONES_DEFAULT_PROVINCE_ID
    page_size: int = 50
    crawl_reviews: bool = True
    max_review_pages: int = 50
    review_page_size: int = 5

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 3.0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 3.0,
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
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        "ITEM_PIPELINES": {
            "crawler.cellphoneS.pipelines.CellphonesReviewExportPipeline": 300,
        },
    }

    def __init__(
        self,
        max_products: Any = _UNSET,
        batch_id: Optional[str] = None,
        province_id: Any = _UNSET,
        crawl_reviews: Any = _UNSET,
        max_review_pages: Any = _UNSET,
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)

        # Parse max_products
        if max_products is _UNSET:
            self.max_products = 50
        elif max_products is None or (
            isinstance(max_products, str)
            and max_products.strip().lower() in ("none", "null", "unlimited", "")
        ):
            self.max_products = None
        else:
            self.max_products = int(max_products)

        # Parse province_id
        if province_id is not _UNSET and province_id is not None:
            self.province_id = int(province_id)
        else:
            self.province_id = getattr(self, "province_id", CELLPHONES_DEFAULT_PROVINCE_ID)

        # Parse review options
        if crawl_reviews is not _UNSET:
            if isinstance(crawl_reviews, str):
                self.crawl_reviews = crawl_reviews.strip().lower() in ("true", "1", "yes")
            else:
                self.crawl_reviews = bool(crawl_reviews)
        else:
            self.crawl_reviews = getattr(self, "crawl_reviews", True)

        if max_review_pages is not _UNSET and max_review_pages is not None:
            self.max_review_pages = int(max_review_pages)
        else:
            self.max_review_pages = getattr(self, "max_review_pages", 50)

        now = datetime.now().astimezone()
        self.batch_id = batch_id or now.strftime("%Y%m%d_%H%M%S")
        self.review_output = kwargs.get("review_output")

        # Observability counters
        self.listing_pages_processed = 0
        self.listing_failures = 0
        self.scheduled_products = 0
        self.unique_parents_collected = 0
        self.child_variant_requests = 0
        self.scraped_items_count = 0
        self.variant_items_yielded = 0
        self.detail_pages_processed = 0
        self.detail_successes = 0
        self.detail_failures = 0
        self.attribute_extraction_successes = 0
        self.attribute_fallback_used = 0
        self.attribute_extraction_failures = 0
        self.attributes_missing = 0
        self.last_listing_page = 0
        self.stop_reason = "in_progress"

        # Review observability metrics
        self.review_requests_scheduled = 0
        self.review_pages_processed = 0
        self.review_failures = 0
        self.reviews_yielded = 0

        # Anti-loop & uniqueness guards
        self.seen_page_signatures: Set[tuple] = set()
        self.seen_parent_ids: Set[str] = set()
        self.seen_review_ids: Set[str] = set()

    # ---------------------------------------------------------
    # 1. START REQUESTS
    # ---------------------------------------------------------

    async def start(self):
        self.logger.info(
            "Khởi động spider %s [category=%s, cate_id=%s, max_products=%s, province_id=%s, batch=%s]",
            self.name,
            self.category,
            self.cate_id,
            self.max_products,
            self.province_id,
            self.batch_id,
        )
        # Bắt đầu pagination từ page=1 (CellphoneS GraphQL là 1-based pagination, page 0 trả về rỗng)
        yield self.make_listing_request(page=1)

    # ---------------------------------------------------------
    # 2. LISTING REQUEST BUILDER & ERRBACK
    # ---------------------------------------------------------

    def make_listing_request(self, page: int):
        """
        Tạo GraphQL request lấy danh sách sản phẩm theo categoryId.
        Pagination là 1-based (page=1, 2, ...).
        """
        query = f"""
        query GetProductsByCateId {{
            products(
                filter: {{
                    static: {{
                        categories: ["{self.cate_id}"],
                        province_id: {self.province_id},
                        stock: {{from: 0}}
                    }}
                }},
                page: {page},
                size: {self.page_size},
                sort: [{{view: desc}}]
            ) {{
                general {{
                    product_id
                    name
                    attributes
                    sku
                    doc_quyen
                    manufacturer
                    url_key
                    url_path
                    child_product
                    categories {{
                        categoryId
                        name
                        uri
                    }}
                    review {{
                        total_count
                        average_rating
                    }}
                }}
                filterable {{
                    is_installment
                    stock_available_id
                    company_stock_id
                    stock
                    is_parent
                    price
                    prices
                    special_price
                    promotion_information
                    thumbnail
                    is_new_arrival
                    display_root_price
                    display_price
                }}
            }}
        }}
        """
        payload = {
            "query": query,
            "variables": {},
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": BASE_WEB_URL,
            "Referer": self.canonical_url,
        }

        return scrapy.Request(
            url=CATALOG_GRAPHQL_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_listing,
            errback=self.errback_listing,
            meta={"page": page},
            dont_filter=True,
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
        self.logger.info("Parsing CellphoneS listing page=%s (status=%s)", page, response.status)

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error("Không decode được JSON ở listing page=%s (status=%s): %s", page, response.status, exc)
            self.listing_failures += 1
            if self.stop_reason == "in_progress":
                self.stop_reason = "error/failure"
            return

        self.listing_pages_processed += 1
        data = body.get("data", {}) if isinstance(body, dict) else {}
        products = data.get("products", []) if isinstance(data, dict) else []

        # Guard 1: Empty page guard
        if not products:
            self.logger.info("Không còn sản phẩm ở page=%s (products=[]). Kết thúc listing.", page)
            if self.stop_reason == "in_progress":
                self.stop_reason = "no_more_products"
            return

        # Guard 2: Repeated-page / signature guard
        current_page_pids = []
        for p in products:
            if isinstance(p, dict) and p.get("general"):
                pid = str(p["general"].get("product_id"))
                if pid:
                    current_page_pids.append(pid)

        page_sig = tuple(current_page_pids)
        if page_sig in self.seen_page_signatures:
            self.logger.warning(
                "Phát hiện page signature bị lặp lại tại page=%s. Dừng pagination để bảo vệ an toàn crawler.",
                page,
            )
            self.stop_reason = "repeated_page_detected"
            return
        self.seen_page_signatures.add(page_sig)

        # Xử lý các parent products trong page
        for p in products:
            if not isinstance(p, dict):
                continue

            gen = p.get("general") or {}
            filt = p.get("filterable") or {}
            pid = str(gen.get("product_id", "")).strip()
            if not pid:
                continue

            # Guard 3: Max products guard cho pilot
            if self.max_products is not None and self.scheduled_products >= self.max_products:
                self.logger.info(
                    "Đã đạt giới hạn max_products=%s. Dừng lên lịch sản phẩm mới.",
                    self.max_products,
                )
                if self.stop_reason == "in_progress":
                    self.stop_reason = "max_products_reached"
                return

            self.scheduled_products += 1

            if pid not in self.seen_parent_ids:
                self.seen_parent_ids.add(pid)
                self.unique_parents_collected += 1

            # Dispatch xử lý parent & child variants
            for req in self.dispatch_parent_product(p):
                yield req

        # Pagination: tiếp tục sang page tiếp theo nếu chưa đạt limit
        if self.max_products is None or self.scheduled_products < self.max_products:
            if len(products) >= self.page_size:
                next_page = page + 1
                yield self.make_listing_request(page=next_page)
            else:
                self.logger.info(
                    "Số sản phẩm trả về (%s) ít hơn page_size (%s) tại page=%s. Kết thúc catalog.",
                    len(products),
                    self.page_size,
                    page,
                )
                if self.stop_reason == "in_progress":
                    self.stop_reason = "catalog_exhausted"

    # ---------------------------------------------------------
    # 4. DISPATCH PARENT & CHILD VARIANTS
    # ---------------------------------------------------------

    def dispatch_parent_product(self, parent_data: Dict[str, Any]):
        """
        Xử lý 1 parent product:
        - Nếu có child_product IDs: gửi GraphQL child query (is_parent="false")
        - Nếu không có child_product: gửi detail request trực tiếp cho parent
        """
        gen = parent_data.get("general") or {}
        filt = parent_data.get("filterable") or {}

        parent_id = str(gen.get("product_id", "")).strip()
        parent_name = gen.get("name")
        parent_sku = gen.get("sku")
        manufacturer = gen.get("manufacturer")
        url_path = (gen.get("url_path") or "").lstrip("/")
        parent_url = f"{BASE_WEB_URL}/{url_path}" if url_path else self.canonical_url

        rev_info = gen.get("review") or {}
        rating = rev_info.get("average_rating")
        review_count = rev_info.get("total_count")

        parent_meta = {
            "parent_id": parent_id,
            "parent_name": parent_name,
            "parent_sku": parent_sku,
            "brand": manufacturer,
            "parent_url": parent_url,
            "rating": rating,
            "review_count": review_count,
            "general_attrs": gen.get("attributes") or {},
            "parent_filt": filt,
            "raw_payload": parent_data,
        }

        child_ids = gen.get("child_product") or []
        # Chuyển child_ids sang danh sách string
        clean_child_ids = [str(cid).strip() for cid in child_ids if cid]

        if clean_child_ids:
            self.child_variant_requests += 1
            yield self.make_child_variants_request(clean_child_ids, parent_meta)
        else:
            # Single product không có child variants
            yield self.make_detail_request(parent_url, parent_meta=parent_meta, child_variants=None)

    # ---------------------------------------------------------
    # 5. CHILD VARIANTS GRAPHQL REQUEST & PARSER
    # ---------------------------------------------------------

    def make_child_variants_request(self, child_ids: List[str], parent_meta: Dict[str, Any]):
        """
        Tạo GraphQL request getDataProductChild.
        Bắt buộc static.is_parent = "false" để CellphoneS trả về dữ liệu biến thể con.
        """
        child_ids_json = json.dumps([str(cid) for cid in child_ids])
        query = f"""
        query getDataProductChild {{
            products(
                filter: {{
                    static: {{
                        is_parent: "false",
                        product_id: {child_ids_json},
                        province_id: {self.province_id}
                    }}
                }},
                size: {len(child_ids)}
            ) {{
                general {{
                    product_id
                    name
                    attributes
                    sku
                    url_path
                }}
                filterable {{
                    price
                    special_price
                    stock
                    thumbnail
                    display_price
                    display_root_price
                    prices
                }}
            }}
        }}
        """
        payload = {
            "query": query,
            "variables": {},
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": BASE_WEB_URL,
            "Referer": parent_meta["parent_url"],
        }

        return scrapy.Request(
            url=CATALOG_GRAPHQL_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_child_variants,
            errback=self.errback_child_variants,
            meta={"parent_meta": parent_meta, "child_ids": child_ids},
        )

    def errback_child_variants(self, failure):
        req = failure.request
        parent_meta = req.meta.get("parent_meta") if req.meta else {}
        parent_id = parent_meta.get("parent_id", "unknown") if parent_meta else "unknown"
        self.logger.error("Child variants request thất bại cho parent %s: %s", parent_id, failure.value)
        # Fallback sang detail page với single parent
        if parent_meta:
            yield self.make_detail_request(
                parent_meta["parent_url"],
                parent_meta=parent_meta,
                child_variants=None,
            )

    def parse_child_variants(self, response):
        parent_meta = response.meta.get("parent_meta") or {}
        parent_url = parent_meta.get("parent_url", self.canonical_url)

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error(
                "Không decode được JSON ở child variants cho parent %s: %s",
                parent_meta.get("parent_id"),
                exc,
            )
            body = {}

        data = body.get("data", {}) if isinstance(body, dict) else {}
        child_products = data.get("products", []) if isinstance(data, dict) else []

        if not child_products:
            self.logger.info(
                "Child products query trả về rỗng cho parent %s. Sẽ dùng single-parent fallback.",
                parent_meta.get("parent_id"),
            )
            child_products = None

        yield self.make_detail_request(parent_url, parent_meta=parent_meta, child_variants=child_products)

    # ---------------------------------------------------------
    # 6. DETAIL REQUEST & ATTRIBUTE EXTRACTION
    # ---------------------------------------------------------

    def make_detail_request(self, detail_url: str, parent_meta: Dict[str, Any], child_variants: Optional[List[Dict[str, Any]]]):
        """
        Request HTML trang chi tiết sản phẩm để trích xuất technical attributes (Schema.org JSON-LD / DOM).
        """
        return scrapy.Request(
            url=detail_url,
            callback=self.parse_detail_attributes,
            errback=self.errback_detail,
            meta={
                "parent_meta": parent_meta,
                "child_variants": child_variants,
                "detail_url": detail_url,
            },
        )

    def errback_detail(self, failure):
        req = failure.request
        parent_meta = req.meta.get("parent_meta") or {}
        child_variants = req.meta.get("child_variants")
        detail_url = req.meta.get("detail_url", "unknown")

        self.detail_failures += 1
        self.attribute_extraction_failures += 1
        self.logger.error("Detail request thất bại tại url=%s: %s", detail_url, failure.value)

        # Khi detail request fail, fallback sang trích xuất attributes từ GraphQL general.attributes
        fallback_attrs = self.extract_graphql_attributes(parent_meta.get("general_attrs"))
        if fallback_attrs:
            self.attribute_fallback_used += 1

        for item in self.yield_product_items(parent_meta, child_variants, fallback_attrs or {}):
            yield item

        # Vẫn schedule review nếu được bật
        if self.crawl_reviews and parent_meta.get("parent_id"):
            self.review_requests_scheduled += 1
            yield self.make_review_request(
                parent_id=parent_meta["parent_id"],
                parent_url=parent_meta["parent_url"],
                page=1,
            )

    def parse_detail_attributes(self, response):
        """
        Trích xuất attributes theo thứ tự ưu tiên đã xác minh:
        1. Schema.org JSON-LD (additionalProperty)
        2. GraphQL general.attributes (fallback)
        3. DOM technical specification (fallback)
        """
        self.detail_pages_processed += 1
        self.detail_successes += 1

        parent_meta = response.meta.get("parent_meta") or {}
        child_variants = response.meta.get("child_variants")

        html_text = response.text

        # 1. Schema.org JSON-LD additionalProperty
        attributes = self.extract_jsonld_attributes(html_text)
        attr_source = "jsonld"

        # 2. GraphQL fallback
        if not attributes:
            attributes = self.extract_graphql_attributes(parent_meta.get("general_attrs"))
            if attributes:
                attr_source = "graphql"
                self.attribute_fallback_used += 1

        # 3. DOM fallback
        if not attributes:
            attributes = self.extract_dom_attributes(html_text)
            if attributes:
                attr_source = "dom"
                self.attribute_fallback_used += 1

        if attributes:
            self.attribute_extraction_successes += 1
            self.logger.debug(
                "Trích xuất thành công %s attributes (nguồn: %s) cho parent %s",
                len(attributes),
                attr_source,
                parent_meta.get("parent_id"),
            )
        else:
            self.attributes_missing += 1
            self.logger.info("Không tìm thấy technical attributes nào cho parent %s", parent_meta.get("parent_id"))

        # Yield canonical product items
        for item in self.yield_product_items(parent_meta, child_variants, attributes or {}):
            yield item

        # Schedule reviews cho parent product
        if self.crawl_reviews and parent_meta.get("parent_id"):
            self.review_requests_scheduled += 1
            yield self.make_review_request(
                parent_id=parent_meta["parent_id"],
                parent_url=parent_meta["parent_url"],
                page=1,
            )

    def extract_jsonld_attributes(self, html_text: str) -> Dict[str, Any]:
        """Trích xuất additionalProperty từ script Schema.org JSON-LD."""
        if not html_text:
            return {}

        soup = BeautifulSoup(html_text, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            if not s.string:
                continue
            try:
                data = json.loads(s.string)
            except Exception:
                continue

            candidates = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for c in candidates:
                if isinstance(c, dict) and "additionalProperty" in c:
                    props = c["additionalProperty"]
                    if isinstance(props, list):
                        attrs = {}
                        for p in props:
                            if isinstance(p, dict) and "name" in p and "value" in p:
                                k = str(p["name"]).strip()
                                v = str(p["value"]).strip()
                                if k:
                                    attrs[k] = v
                        if attrs:
                            return attrs
        return {}

    def extract_graphql_attributes(self, general_attrs: Any) -> Dict[str, Any]:
        """Trích xuất specifications từ general.attributes của GraphQL."""
        if not isinstance(general_attrs, dict):
            return {}

        attrs = {}
        for k, v in general_attrs.items():
            if v is not None and v != "":
                # Bỏ qua các flag boolean hoặc ID không mang ý nghĩa thông số
                if isinstance(v, (str, int, float, list)):
                    attrs[str(k).strip()] = v
        return attrs

    def extract_dom_attributes(self, html_text: str) -> Dict[str, Any]:
        """Trích xuất specifications từ DOM (các khối technical-content, box-spec, table)."""
        if not html_text:
            return {}

        soup = BeautifulSoup(html_text, "html.parser")
        attrs = {}

        # 1. Tìm trong các container thông số kỹ thuật phổ biến
        spec_container = soup.find(class_=lambda x: x and any(c in str(x).lower() for c in ("technical-content", "box-spec", "box-technical-info", "thong-so")))
        if spec_container:
            rows = spec_container.find_all(["li", "tr", "div"], class_=lambda x: x and any(c in str(x).lower() for c in ("item", "row", "spec")))
            for r in rows:
                text = r.get_text(":", strip=True)
                if ":" in text:
                    k, _, v = text.partition(":")
                    k = k.strip()
                    v = v.strip()
                    if k and v:
                        attrs[k] = v

        # 2. Tìm trong table
        if not attrs:
            for table in soup.find_all("table"):
                for tr in table.find_all("tr"):
                    tds = tr.find_all(["td", "th"])
                    if len(tds) >= 2:
                        k = tds[0].get_text(strip=True)
                        v = tds[1].get_text(strip=True)
                        if k and v:
                            attrs[k] = v

        return attrs

    # ---------------------------------------------------------
    # 7. YIELD PRODUCT ITEMS (CANONICAL SCHEMA = 25 FIELDS)
    # ---------------------------------------------------------

    def yield_product_items(
        self,
        parent_meta: Dict[str, Any],
        child_variants: Optional[List[Dict[str, Any]]],
        attributes: Dict[str, Any],
    ):
        """
        Khởi tạo TechProductRawItem tuân thủ đúng 25 fields của Canonical Contract:
        - Nếu có child variants: tạo 1 item cho mỗi variant con, lấy giá thực tế từ child variant filterable.
        - Nếu không có child variants: tạo 1 item fallback cho parent product.
        """
        crawl_time = datetime.now().astimezone().isoformat(timespec="seconds")

        if child_variants and isinstance(child_variants, list):
            for cv in child_variants:
                if not isinstance(cv, dict):
                    continue

                c_gen = cv.get("general") or {}
                c_filt = cv.get("filterable") or {}
                c_attrs = c_gen.get("attributes") or {}

                # Variant price mapping
                special_price = c_filt.get("special_price")
                list_price = c_filt.get("price")

                if special_price is not None and isinstance(special_price, (int, float)) and special_price > 0:
                    current_price = special_price
                    original_price = list_price
                else:
                    current_price = list_price
                    original_price = list_price

                # Variant URL
                c_url_path = (c_gen.get("url_path") or "").lstrip("/")
                variant_url = f"{BASE_WEB_URL}/{c_url_path}" if c_url_path else parent_meta["parent_url"]

                # Variant color
                variant_color = c_attrs.get("color") or c_attrs.get("color_text")
                if variant_color and isinstance(variant_color, str):
                    variant_color = variant_color.strip()

                # Variant SKU
                variant_sku = str(c_gen.get("sku")).strip() if c_gen.get("sku") else None

                item = TechProductRawItem()
                item["source"] = "cellphones"
                item["category"] = self.category
                item["crawl_batch"] = self.batch_id
                item["crawl_time"] = crawl_time

                # Parent identifiers
                item["product_id_raw"] = parent_meta["parent_id"]
                item["product_name_raw"] = parent_meta["parent_name"]
                item["product_url_raw"] = parent_meta["parent_url"]
                item["parent_product_id_raw"] = parent_meta["parent_id"]
                item["parent_product_name_raw"] = parent_meta["parent_name"]
                item["parent_url_raw"] = parent_meta["parent_url"]
                item["sku_raw"] = parent_meta["parent_sku"]

                # Variant specifics
                item["variant_sku_raw"] = variant_sku
                item["variant_name_raw"] = c_gen.get("name")
                item["variant_color_raw"] = variant_color
                item["variant_url_raw"] = variant_url
                item["availability_raw"] = c_filt.get("stock")

                # Pricing
                item["price_raw"] = current_price
                item["original_price_raw"] = original_price

                # Seller & Reputation
                item["brand_raw"] = parent_meta["brand"]
                item["seller_raw"] = "CellphoneS"
                item["rating_raw"] = parent_meta["rating"]
                item["review_count_raw"] = parent_meta["review_count"]
                item["total_sold_raw"] = None

                # Specifications & Raw Payload
                item["attributes_raw"] = attributes
                item["raw_payload"] = {
                    "parent": parent_meta["raw_payload"],
                    "child": cv,
                }

                self.scraped_items_count += 1
                self.variant_items_yielded += 1
                yield item
        else:
            # Single-child / fallback parent item
            p_filt = parent_meta.get("parent_filt") or {}
            special_price = p_filt.get("special_price")
            list_price = p_filt.get("price")

            if special_price is not None and isinstance(special_price, (int, float)) and special_price > 0:
                current_price = special_price
                original_price = list_price
            else:
                current_price = list_price
                original_price = list_price

            item = TechProductRawItem()
            item["source"] = "cellphones"
            item["category"] = self.category
            item["crawl_batch"] = self.batch_id
            item["crawl_time"] = crawl_time

            item["product_id_raw"] = parent_meta["parent_id"]
            item["product_name_raw"] = parent_meta["parent_name"]
            item["product_url_raw"] = parent_meta["parent_url"]
            item["parent_product_id_raw"] = parent_meta["parent_id"]
            item["parent_product_name_raw"] = parent_meta["parent_name"]
            item["parent_url_raw"] = parent_meta["parent_url"]
            item["sku_raw"] = parent_meta["parent_sku"]

            item["variant_sku_raw"] = None
            item["variant_name_raw"] = None
            item["variant_color_raw"] = None
            item["variant_url_raw"] = None
            item["availability_raw"] = p_filt.get("stock")

            item["price_raw"] = current_price
            item["original_price_raw"] = original_price

            item["brand_raw"] = parent_meta["brand"]
            item["seller_raw"] = "CellphoneS"
            item["rating_raw"] = parent_meta["rating"]
            item["review_count_raw"] = parent_meta["review_count"]
            item["total_sold_raw"] = None

            item["attributes_raw"] = attributes
            item["raw_payload"] = parent_meta["raw_payload"]

            self.scraped_items_count += 1
            self.variant_items_yielded += 1
            yield item

    # ---------------------------------------------------------
    # 8. REVIEW REQUESTS & PARSER (CANONICAL SCHEMA = 19 FIELDS)
    # ---------------------------------------------------------

    def make_review_request(self, parent_id: str, parent_url: str, page: int = 1):
        """
        Tạo GraphQL request lấy reviews của parent product.
        Pagination: 1-based, 5 reviews/page.
        Review linkage: hoàn toàn ở cấp parent (product_id).
        """
        try:
            numeric_pid = int(parent_id)
        except (ValueError, TypeError):
            numeric_pid = parent_id

        query = f"""
        query {{
            reviews(filter: {{product_id: {numeric_pid}}}, page: {page}) {{
                matches {{
                    id
                    content
                    status
                    customer {{
                        id
                        fullname
                    }}
                    product_id
                    created_at
                    rating_id
                    sent_from
                    is_pinned
                    children
                    photos
                    is_admin
                    is_purchased
                    attributes {{
                        attribute_name
                        label
                    }}
                }}
                total
            }}
        }}
        """
        payload = {
            "query": query,
            "variables": {},
        }

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": BASE_WEB_URL,
            "Referer": parent_url,
        }

        return scrapy.Request(
            url=REVIEW_GRAPHQL_URL,
            method="POST",
            body=json.dumps(payload),
            headers=headers,
            callback=self.parse_reviews,
            errback=self.errback_reviews,
            meta={
                "parent_id": parent_id,
                "parent_url": parent_url,
                "page": page,
            },
        )

    def errback_reviews(self, failure):
        req = failure.request
        pid = req.meta.get("parent_id", "unknown") if req.meta else "unknown"
        page = req.meta.get("page", 1) if req.meta else 1
        self.review_failures += 1
        self.logger.error("Review request thất bại cho parent %s tại page=%s: %s", pid, page, failure.value)

    def parse_reviews(self, response):
        parent_id = str(response.meta.get("parent_id", "")).strip()
        parent_url = response.meta.get("parent_url", self.canonical_url)
        page = response.meta.get("page", 1)

        self.review_pages_processed += 1

        try:
            body = response.json()
        except Exception as exc:
            self.logger.error(
                "Không decode được JSON ở review response cho parent %s (page=%s): %s",
                parent_id,
                page,
                exc,
            )
            self.review_failures += 1
            return

        data = body.get("data", {}) if isinstance(body, dict) else {}
        reviews_data = data.get("reviews", {}) if isinstance(data, dict) else {}
        matches = reviews_data.get("matches", []) if isinstance(reviews_data, dict) else []
        total = reviews_data.get("total", 0) if isinstance(reviews_data, dict) else 0

        if not matches:
            return

        crawl_time = datetime.now().astimezone().isoformat(timespec="seconds")

        for r in matches:
            if not isinstance(r, dict):
                continue

            rev_id = str(r.get("id", "")).strip()
            if not rev_id:
                continue

            if rev_id in self.seen_review_ids:
                continue
            self.seen_review_ids.add(rev_id)

            customer = r.get("customer") or {}
            author = customer.get("fullname") if isinstance(customer, dict) else None

            review_item = TechReviewRawItem()
            review_item["source"] = "cellphones"
            review_item["category"] = self.category
            review_item["crawl_batch"] = self.batch_id
            review_item["crawl_time"] = crawl_time

            # Linkage strictly at parent level
            review_item["parent_product_id_raw"] = parent_id
            review_item["parent_product_url_raw"] = parent_url

            review_item["review_id_raw"] = rev_id
            review_item["rating_raw"] = r.get("rating_id")
            review_item["review_text_raw"] = r.get("content")
            review_item["author_raw"] = author
            review_item["review_time_raw"] = r.get("created_at")
            review_item["like_count_raw"] = None  # CellphoneS không cung cấp like_count trực tiếp

            # Invariant bắt buộc: CellphoneS review không có reliable variant SKU
            review_item["review_product_code_raw"] = None
            review_item["variant_code_raw"] = None
            review_item["variant_sku_raw"] = None

            review_item["buy_date_raw"] = None
            review_item["reply_raw"] = r.get("children")
            review_item["attached_files_raw"] = r.get("photos")
            review_item["raw_payload"] = r

            self.reviews_yielded += 1
            yield review_item

        # Pagination: 5 reviews/page
        if len(matches) > 0 and (page * self.review_page_size < total) and (page < self.max_review_pages):
            next_page = page + 1
            yield self.make_review_request(
                parent_id=parent_id,
                parent_url=parent_url,
                page=next_page,
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
            "  - province_id: %s\n"
            "  - last_listing_page: %s\n"
            "  - listing_pages_processed: %s\n"
            "  - listing_failures: %s\n"
            "  - scheduled_products: %s\n"
            "  - unique_parents_collected: %s\n"
            "  - child_variant_requests: %s\n"
            "  - scraped_items_count: %s\n"
            "  - variant_items_yielded: %s\n"
            "  - detail_pages_processed: %s\n"
            "  - detail_successes: %s\n"
            "  - detail_failures: %s\n"
            "  - attribute_extraction_successes: %s\n"
            "  - attribute_fallback_used: %s\n"
            "  - attribute_extraction_failures: %s\n"
            "  - attributes_missing: %s\n"
            "  - review_requests_scheduled: %s\n"
            "  - review_pages_processed: %s\n"
            "  - review_failures: %s\n"
            "  - reviews_yielded: %s\n"
            "====================================================",
            self.name,
            reason,
            self.stop_reason,
            self.province_id,
            self.last_listing_page,
            self.listing_pages_processed,
            self.listing_failures,
            self.scheduled_products,
            self.unique_parents_collected,
            self.child_variant_requests,
            self.scraped_items_count,
            self.variant_items_yielded,
            self.detail_pages_processed,
            self.detail_successes,
            self.detail_failures,
            self.attribute_extraction_successes,
            self.attribute_fallback_used,
            self.attribute_extraction_failures,
            self.attributes_missing,
            self.review_requests_scheduled,
            self.review_pages_processed,
            self.review_failures,
            self.reviews_yielded,
        )
