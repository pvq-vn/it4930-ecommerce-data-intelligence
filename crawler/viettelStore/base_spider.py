import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.viettelStore.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    try:
        from items import TechProductRawItem, TechReviewRawItem
    except ImportError:
        from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem

_UNSET = object()

GET_USER_CONTROL_ASYNC_URL = "https://viettelstore.vn/Site/_Sys/GetUserControlAsync.aspx"


class ViettelstoreBaseSpider(scrapy.Spider):
    """
    Base spider cho sàn Viettel Store (viettelstore.vn).
    Thu thập dữ liệu theo chuẩn TV1 (Web Crawling & Data Acquisition).
    Tuân thủ tuyệt đối Canonical Product (25 fields) & Review (19 fields) Raw Data Contract.

    Kiến trúc thu thập:
    LISTING (POST GetUserControlAsync.aspx, CatID='010001' cho smartphone, '010002' cho laptop)
      ↓
    PAGINATION GUARD (Empty page, repeated page signature, max_products limit)
      ↓
    DEDUPLICATION GATE (Mã pid từ URL: -pid(\\d+)\\.html)
      ↓
    DETAIL (SSR HTML + Schema.org JSON-LD additionalProperty + rating chart)
      ↓
    PRICE & ATTRIBUTES (Selling price, original price, excluding installment base price)
      ↓
    PRODUCT ITEM (Yield 1 TechProductRawItem cho mỗi sản phẩm/cấu hình, KHÔNG tự nhân bản variant)
      ↓
    REVIEWS (Nếu crawl_reviews=True và có customer reviews từ JSON-LD, linkage strictly at parent level)
    """

    name = "viettelstore_base"
    allowed_domains = ["viettelstore.vn", "cdn.viettelstore.vn"]

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    cat_id: str = "010001"
    start_url: str = "https://viettelstore.vn"

    # Default limits & configurations
    max_products: Optional[int] = 50
    crawl_reviews: bool = True
    page_size: int = 25

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
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429, 403],
        "LOG_LEVEL": "INFO",
        "FEED_EXPORT_ENCODING": "utf-8",
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        },
        "ITEM_PIPELINES": {
            "crawler.viettelStore.pipelines.ViettelstoreReviewExportPipeline": 300,
        },
    }

    def __init__(
        self,
        max_products: Any = _UNSET,
        batch_id: Optional[str] = None,
        crawl_reviews: Any = _UNSET,
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

        if crawl_reviews is not _UNSET:
            if isinstance(crawl_reviews, str):
                self.crawl_reviews = crawl_reviews.strip().lower() in ("true", "1", "yes")
            else:
                self.crawl_reviews = bool(crawl_reviews)
        else:
            self.crawl_reviews = getattr(self, "crawl_reviews", True)

        now = datetime.now().astimezone()
        self.batch_id = batch_id or now.strftime("%Y%m%d_%H%M%S")
        self.review_output = kwargs.get("review_output")

        # Observability & guards
        self.scheduled_products = 0
        self.scraped_items_count = 0
        self.listing_pages_processed = 0
        self.listing_failures = 0
        self.detail_failures = 0
        self.seen_pids: Set[str] = set()
        self.seen_page_signatures: Set[tuple] = set()
        self.stop_reason = "in_progress"
        self.last_listing_page = 0

    # ---------------------------------------------------------
    # 1. START REQUESTS & LISTING PAGINATION
    # ---------------------------------------------------------

    async def start(self):
        self.logger.info(
            "Khởi động spider %s [category=%s, cat_id=%s, max_products=%s, batch=%s]",
            self.name,
            self.category,
            self.cat_id,
            self.max_products,
            self.batch_id,
        )
        yield self.make_listing_request(page=1)

    def start_requests(self):
        """Tương thích ngược đồng bộ (Scrapy cũ / test suite)."""
        yield self.make_listing_request(page=1)

    def make_listing_request(self, page: int = 1):
        """Tạo POST request phân trang tới GetUserControlAsync.aspx."""
        formdata = {
            "path": "ProductList5Col2026",
            "PaginationVisiable": "0",
            "CatID": str(self.cat_id),
            "ManID": "",
            "Tags": "",
            "PageSize": str(self.page_size),
            "CurrentPage": str(page),
            "SpecOrder": "MoiNhat",
            "SpecFilter": "",
            "FeatureFilter": "",
            "PriceFrom": "-1",
            "PriceTo": "-1",
            "isHot": "",
        }
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        return scrapy.FormRequest(
            url=GET_USER_CONTROL_ASYNC_URL,
            formdata=formdata,
            headers=headers,
            callback=self.parse_listing,
            errback=self.errback_listing,
            meta={"page": page},
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
    # 2. PARSE LISTING RESPONSE
    # ---------------------------------------------------------

    def parse_listing(self, response):
        page = response.meta.get("page", 1)
        self.last_listing_page = page
        self.listing_pages_processed += 1
        self.logger.info("Parsing Viettel Store listing page=%s (status=%s)", page, response.status)

        soup = BeautifulSoup(response.text, "html.parser")
        product_items = soup.find_all(class_=lambda c: c and "product-item" in c.split())

        if not product_items:
            self.logger.info("Không còn sản phẩm ở page=%s. Dừng pagination.", page)
            if self.stop_reason == "in_progress":
                self.stop_reason = "no_more_products"
            return

        # Pagination guard: kiểm tra page signature chống lặp vô hạn
        page_urls = []
        for it in product_items:
            link = it.find("a", href=True)
            if link:
                page_urls.append(link["href"])
        page_signature = tuple(page_urls)

        if page_signature in self.seen_page_signatures:
            self.logger.warning(
                "Phát hiện page signature bị lặp lại tại page=%s. Dừng pagination.",
                page,
            )
            self.stop_reason = "repeated_page_signature"
            return
        self.seen_page_signatures.add(page_signature)

        scheduled_this_page = 0
        for it in product_items:
            if self.max_products is not None and self.scheduled_products >= self.max_products:
                self.logger.info(
                    "Đạt giới hạn scheduled_products=%s. Dừng lên lịch sản phẩm mới.",
                    self.max_products,
                )
                self.stop_reason = "max_products_reached"
                break

            link_el = it.find("a", href=re.compile(r"-pid\d+\.html"))
            if not link_el:
                link_el = it.find("a", href=True)
            if not link_el:
                continue

            raw_href = link_el["href"].strip()
            detail_url = urljoin("https://viettelstore.vn", raw_href)

            # Trích xuất numeric product ID từ -pid{id}.html
            pid_match = re.search(r"-pid(\d+)\.html", detail_url)
            pid = pid_match.group(1) if pid_match else None

            if not pid:
                # Nếu không khớp pid, bỏ qua hoặc không coi là product hợp lệ
                continue

            # Deduplication gate: loại bỏ sản phẩm trùng lặp trong phiên chạy
            if pid in self.seen_pids:
                continue
            self.seen_pids.add(pid)
            self.scheduled_products += 1
            scheduled_this_page += 1

            # Thu thập thông tin từ listing card để làm đối chiếu/dự phòng
            name_el = it.find(class_=lambda c: c and any(k in c for k in ["name", "title"])) or link_el
            listing_name = name_el.text.strip() if name_el else None
            price_el = it.find(class_="price")
            listing_price = price_el.text.strip() if price_el else None
            old_price_el = it.find(class_="price-old")
            listing_old_price = old_price_el.text.strip() if old_price_el else None

            VIETTEL_VALID_STOCK_KEYWORDS = {
                "còn hàng", "tạm hết hàng", "hết hàng", "số lượng có hạn",
                "ngừng kinh doanh", "liên hệ", "đặt trước"
            }
            listing_stock = None
            status_badge = it.find(class_=lambda c: c and any(k in c.lower() for k in ["status", "stock", "availability"]))
            if status_badge and status_badge.text.strip().lower() in VIETTEL_VALID_STOCK_KEYWORDS:
                listing_stock = status_badge.text.strip()

            listing_data = {
                "pid": pid,
                "name": listing_name,
                "price": listing_price,
                "old_price": listing_old_price,
                "stock": listing_stock,
                "url": detail_url,
            }

            yield scrapy.Request(
                url=detail_url,
                callback=self.parse_detail,
                errback=self.errback_detail,
                meta={
                    "pid": pid,
                    "listing_data": listing_data,
                    "page": page,
                },
            )

        # Lên lịch trang kế tiếp nếu chưa đạt giới hạn
        if self.max_products is None or self.scheduled_products < self.max_products:
            yield self.make_listing_request(page=page + 1)

    def errback_detail(self, failure):
        self.detail_failures += 1
        req = failure.request
        pid = req.meta.get("pid") if req.meta else None
        self.logger.error("Detail request thất bại cho pid=%s [url=%s]: %s", pid, req.url, failure.value)

    # ---------------------------------------------------------
    # 3. PARSE DETAIL RESPONSE
    # ---------------------------------------------------------

    def parse_detail(self, response):
        meta = response.meta or {}
        pid = meta.get("pid")
        listing_data = meta.get("listing_data", {})
        now_iso = datetime.now().astimezone().isoformat()

        def _is_excluded_price_el(el):
            if not el:
                return True
            for parent in el.parents:
                classes = parent.get("class", [])
                class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                id_str = str(parent.get("id", ""))
                combined = f"{class_str} {id_str}".lower()
                if any(k in combined for k in [
                    "accessory", "accessories", "phukien", "phu-kien", "bundle",
                    "related", "tuong-tu", "goi-y", "suggest",
                    "installment", "tra-gop", "khuyen-mai", "promotion"
                ]):
                    return True
            return False

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Trích xuất Schema.org JSON-LD
        json_ld_data = {}
        for s in soup.find_all("script", type="application/ld+json"):
            if s.string:
                try:
                    data = json.loads(s.string.strip())
                    if isinstance(data, dict) and data.get("@type") == "Product":
                        json_ld_data = data
                        break
                except Exception:
                    pass

        # 2. Product Name
        product_name = None
        name_el = soup.find(class_="product-name") or soup.find(class_="title-product") or soup.find("h1")
        if name_el and name_el.text.strip():
            product_name = name_el.text.strip()
        elif json_ld_data.get("name"):
            product_name = str(json_ld_data["name"]).strip()
        else:
            product_name = listing_data.get("name")

        # 3. Product ID (Primary ID: actual source product ID từ -pid{id})
        # Hierarchy:
        # 1. pid từ URL -pid(\d+).html (được xác minh là internal ID của Viettel Store)
        # 2. json_ld sku nếu là chuỗi số nguyên (đối chiếu trùng khớp với pid)
        # 3. None (không dùng slug hay trường ngẫu nhiên)
        product_id_raw = None
        if pid and str(pid).strip().isdigit():
            product_id_raw = str(pid).strip()
        elif json_ld_data.get("sku") and str(json_ld_data["sku"]).strip().isdigit():
            product_id_raw = str(json_ld_data["sku"]).strip()

        # 4. Product URL
        product_url_raw = response.url

        # 5. Pricing (Phân biệt rõ ràng: current price vs original price vs installment base price vs accessories)
        price_raw = None
        original_price_raw = None
        availability_raw = None

        # Tìm phần tử giá bán chính thức trong DOM (loại trừ accessories, related, promotion, installment)
        detail_price_el = None
        for p_el in soup.find_all(class_=lambda c: c and any(k in c.split() for k in ["price", "price-current", "pro-price"])):
            classes = p_el.get("class", [])
            class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
            if any(k in class_str.lower() for k in ["price-old", "price-last", "strike"]):
                continue
            if not _is_excluded_price_el(p_el):
                detail_price_el = p_el
                break

        price_text = detail_price_el.text.strip() if detail_price_el else ""

        # Kiểm tra cụ thể trạng thái "Liên hệ" trong khối giá bán hoặc nút mua hàng
        is_contact_price = False
        if "liên hệ" in price_text.lower():
            is_contact_price = True
        else:
            status_btn = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["btn-buy", "btn-order", "product-status"]))
            if status_btn and "liên hệ" in status_btn.text.strip().lower() and not _is_excluded_price_el(status_btn):
                is_contact_price = True

        if is_contact_price:
            availability_raw = "Liên hệ"
            price_raw = None
            original_price_raw = None
        else:
            # Giá bán chính thức
            if price_text and any(c.isdigit() for c in price_text):
                price_raw = price_text
            elif json_ld_data.get("offers", {}).get("price"):
                p_val = json_ld_data["offers"]["price"]
                if p_val and str(p_val).strip() not in ("0", "None", ""):
                    price_raw = str(p_val).strip()
            elif listing_data.get("price"):
                price_raw = listing_data["price"]

            # Giá gốc niêm yết (chỉ lấy khi có giá gạch ngang rõ ràng)
            old_price_el = None
            for p_el in soup.find_all(class_=lambda c: c and any(k in c.split() for k in ["price-old", "price-last"])):
                if not _is_excluded_price_el(p_el):
                    old_price_el = p_el
                    break

            if old_price_el and old_price_el.text.strip() and any(c.isdigit() for c in old_price_el.text):
                original_price_raw = old_price_el.text.strip()
            elif listing_data.get("old_price"):
                original_price_raw = listing_data.get("old_price")

            # Availability (Evidence-based: absence of evidence = None, KHÔNG default thành "Còn hàng")
            avail_schema = json_ld_data.get("offers", {}).get("availability", "")
            if "InStock" in avail_schema:
                availability_raw = "Còn hàng"
            elif "OutOfStock" in avail_schema:
                availability_raw = "Tạm hết hàng"

            # Check DOM evidence in main product info (#hanghoa or status blocks)
            if not availability_raw:
                hanghoa_el = soup.find(id="hanghoa") or soup.find(class_=lambda c: c and "product-info" in c)
                if hanghoa_el:
                    txt_lower = hanghoa_el.text.lower()
                    if "tạm hết hàng" in txt_lower or "hết hàng" in txt_lower:
                        availability_raw = "Tạm hết hàng"
                    elif "số lượng có hạn" in txt_lower:
                        availability_raw = "Số lượng có hạn"
                    elif "còn hàng" in txt_lower:
                        availability_raw = "Còn hàng"

            # Fallback to valid listing stock if present
            if not availability_raw and listing_data.get("stock"):
                availability_raw = listing_data["stock"]

            # Nếu không có bất kỳ bằng chứng tồn kho nào, availability_raw giữ nguyên None

        # 6. SKU / MPN trích xuất cho Laptop
        sku_raw = None
        variant_sku_raw = None
        if self.category == "laptop" and product_name:
            # Laptop thường nhúng mã MPN/SKU ở cuối tên trong ngoặc đơn, ví dụ: (CPH995), (X1404MA-EB027W)
            mpn_match = re.search(r"\(([A-Za-z0-9_\-]+)\)\s*$", product_name)
            if mpn_match:
                sku_raw = mpn_match.group(1).strip()
                variant_sku_raw = sku_raw
            elif json_ld_data.get("sku"):
                sku_raw = str(json_ld_data["sku"]).strip()
                variant_sku_raw = sku_raw
        else:
            # Smartphone không phơi bày SKU riêng -> để None (không forge SKU)
            sku_raw = None
            variant_sku_raw = None

        # 7. Brand
        brand_raw = None
        if json_ld_data.get("brand"):
            brand_val = json_ld_data["brand"]
            brand_raw = brand_val.get("name") if isinstance(brand_val, dict) else str(brand_val)
        if not brand_raw:
            # Fallback lấy brand từ tiêu đề hoặc breadcrumbs
            brand_el = soup.find("input", id="HiddenBrand")
            if brand_el and brand_el.get("value"):
                brand_raw = brand_el["value"].strip()

        # 8. Rating & Review Count
        rating_raw = None
        review_count_raw = None

        # Thống kê từ detail-rating-chart nếu có
        chart_el = soup.find(class_="detail-rating-chart")
        if chart_el:
            counts = [0, 0, 0, 0, 0]  # [1-star, 2-star, 3-star, 4-star, 5-star]
            star_items = chart_el.find_all(class_="rating-item")
            for sit in star_items:
                lvl = sit.find(class_="rating-level")
                cnt = sit.find(class_="rating-counter")
                if lvl and cnt and cnt.text.strip().isdigit():
                    num = int(cnt.text.strip())
                    lvl_t = lvl.text.strip().lower()
                    if "tuyệt vời" in lvl_t or "5" in lvl_t:
                        counts[4] = num
                    elif "rất tốt" in lvl_t or "4" in lvl_t:
                        counts[3] = num
                    elif "bình thường" in lvl_t or "3" in lvl_t:
                        counts[2] = num
                    elif "tạm được" in lvl_t or "2" in lvl_t:
                        counts[1] = num
                    elif "không thích" in lvl_t or "1" in lvl_t:
                        counts[0] = num

            total_revs = sum(counts)
            if total_revs > 0:
                review_count_raw = total_revs
                avg_score = (counts[4] * 5 + counts[3] * 4 + counts[2] * 3 + counts[1] * 2 + counts[0] * 1) / total_revs
                rating_raw = round(avg_score, 2)

        if rating_raw is None and json_ld_data.get("aggregateRating"):
            agg = json_ld_data["aggregateRating"]
            rating_raw = agg.get("ratingValue")
            review_count_raw = agg.get("reviewCount") or agg.get("ratingCount")

        # 9. Technical Attributes
        attributes_raw: Dict[str, Any] = {}
        for prop in json_ld_data.get("additionalProperty", []):
            if isinstance(prop, dict) and prop.get("name") and prop.get("value"):
                attributes_raw[str(prop["name"]).strip()] = str(prop["value"]).strip()

        # Bổ sung các thông tin chi tiết từ bảng HTML hoặc các block
        for tbl in soup.find_all("table"):
            for tr in tbl.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                if len(tds) >= 2:
                    k = tds[0].text.strip()
                    v = tds[1].text.strip()
                    if k and v and k not in attributes_raw and len(k) < 80:
                        attributes_raw[k] = v

        # Bảo toàn giá cơ sở trả góp 0% (installment base price) nếu có trong mô tả khuyến mãi
        inst_match = re.search(r"trả góp\s*0%[\s\S]*?(?:tính trên|giá cơ sở|mức giá)[^\d]*([\d\.,]+\s*₫)", response.text, re.I)
        if inst_match:
            attributes_raw["installment_base_price_raw"] = inst_match.group(1).strip()

        # 10. Raw Payload (Extracted debug provenance dictionary capturing source properties, listing snapshot, and JSON-LD data; NOT a full HTML dump)
        raw_payload = {
            "source": "viettelstore",
            "category": self.category,
            "pid": pid,
            "listing_data": listing_data,
            "json_ld": json_ld_data,
            "detail_url": product_url_raw,
        }

        # 11. Yield TechProductRawItem (25 CANONICAL FIELDS)
        item = TechProductRawItem()
        item["source"] = "viettelstore"
        item["category"] = self.category
        item["crawl_batch"] = self.batch_id
        item["crawl_time"] = now_iso

        item["product_id_raw"] = product_id_raw
        item["product_name_raw"] = product_name
        item["product_url_raw"] = product_url_raw

        item["parent_product_id_raw"] = product_id_raw
        item["parent_product_name_raw"] = product_name
        item["parent_url_raw"] = product_url_raw

        item["sku_raw"] = sku_raw
        item["variant_sku_raw"] = variant_sku_raw
        item["variant_name_raw"] = None
        item["variant_color_raw"] = None
        item["variant_url_raw"] = product_url_raw

        item["availability_raw"] = availability_raw
        item["price_raw"] = price_raw
        item["original_price_raw"] = original_price_raw

        item["brand_raw"] = brand_raw
        item["seller_raw"] = "Viettel Store"
        item["rating_raw"] = rating_raw
        item["review_count_raw"] = review_count_raw
        item["total_sold_raw"] = None

        item["attributes_raw"] = attributes_raw
        item["raw_payload"] = raw_payload

        self.scraped_items_count += 1
        yield item

        # 12. Yield TechReviewRawItem (19 CANONICAL FIELDS) nếu có reviews hợp lệ
        if self.crawl_reviews and json_ld_data.get("review"):
            reviews_list = json_ld_data["review"]
            if isinstance(reviews_list, list):
                for idx, rev in enumerate(reviews_list):
                    if not isinstance(rev, dict):
                        continue
                    author_obj = rev.get("author", {})
                    author_name = author_obj.get("name") if isinstance(author_obj, dict) else str(author_obj)
                    review_rating = rev.get("reviewRating", {}).get("ratingValue")

                    rev_item = TechReviewRawItem()
                    rev_item["source"] = "viettelstore"
                    rev_item["category"] = self.category
                    rev_item["crawl_batch"] = self.batch_id
                    rev_item["crawl_time"] = now_iso

                    rev_item["parent_product_id_raw"] = str(product_id_raw) if product_id_raw else None
                    rev_item["parent_product_url_raw"] = product_url_raw

                    rev_item["review_id_raw"] = f"{product_id_raw}_{idx}"
                    rev_item["rating_raw"] = review_rating
                    rev_item["review_text_raw"] = rev.get("reviewBody") or rev.get("description")
                    rev_item["author_raw"] = author_name
                    rev_item["review_time_raw"] = rev.get("datePublished")
                    rev_item["like_count_raw"] = None

                    rev_item["review_product_code_raw"] = str(product_id_raw) if product_id_raw else None
                    rev_item["variant_code_raw"] = None
                    rev_item["variant_sku_raw"] = None

                    rev_item["buy_date_raw"] = None
                    rev_item["reply_raw"] = None
                    rev_item["attached_files_raw"] = None
                    rev_item["raw_payload"] = rev

                    yield rev_item
