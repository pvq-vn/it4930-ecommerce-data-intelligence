import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import scrapy
from bs4 import BeautifulSoup

try:
    from crawler.hoanghamobile.items import TechProductRawItem, TechReviewRawItem
except ImportError:
    try:
        from items import TechProductRawItem, TechReviewRawItem
    except ImportError:
        from crawler.tgdd.items import TechProductRawItem, TechReviewRawItem

_UNSET = object()
BASE_WEB_URL = "https://hoanghamobile.com"


def _parse_numeric_price(val: Any) -> Optional[float]:
    """Trích xuất giá trị số từ chuỗi giá (ví dụ: '37.990.000 ₫' -> 37990000.0)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    cleaned = re.sub(r"[^\d]", "", str(val))
    if not cleaned:
        return None
    try:
        f = float(cleaned)
        return f if f > 0 else None
    except (ValueError, TypeError):
        return None



class HoanghamobileBaseSpider(scrapy.Spider):
    """
    Base spider cho sàn Hoàng Hà Mobile (hoanghamobile.com).
    Thu thập dữ liệu theo chuẩn TV1 (Web Crawling & Data Acquisition).
    Tuân thủ tuyệt đối Canonical Product (25 fields) & Review (19 fields) Raw Data Contract.

    Kiến trúc thu thập:
    LISTING (GET /{slug}?p={page}, lưu listing_data với 4 tầng giá, badges, stock)
      ↓
    PAGINATION GUARD (Empty page, repeated page signature, max_products limit, page-pager check)
      ↓
    DEDUPLICATION GATE (Chuẩn hóa /lap-top/ -> /laptop/ và dedup theo canonical slug / product ID)
      ↓
    DETAIL (SSR HTML + Schema.org JSON-LD + bảng thông số kỹ thuật 20+ dòng)
      ↓
    PRICE SEMANTICS (Tách giá bán, giá gốc; loại bỏ giá Member, giá trả góp, giá phụ kiện; fallback listing nếu detail ẩn giá)
      ↓
    PRODUCT ITEM (Yield 1 TechProductRawItem cho mỗi sản phẩm/cấu hình, KHÔNG tự nhân bản variant)
      ↓
    REVIEWS (Hoàng Hà Mobile chỉ có Q&A / comment threads, KHÔNG map vào TechReviewRawItem theo quy tắc Rule 6 & 14)
    """

    name = "hoanghamobile_base"
    allowed_domains = ["hoanghamobile.com", "cdn.hoanghamobile.vn"]

    # Category configuration (sẽ được override ở subclass)
    category: str = "general"
    slug: str = "laptop"
    canonical_url: str = "https://hoanghamobile.com/laptop"

    # Default limits & configurations
    max_products: Optional[int] = 50
    crawl_reviews: bool = True
    page_size: int = 18

    # Cố định khu vực Hà Nội (location_id: 1) để đảm bảo tính tái lập (reproducibility)
    default_cookies = {
        "location_id": "1",
        "current_location": "1",
    }

    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 2.0,
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
            "crawler.hoanghamobile.pipelines.HoanghamobileReviewExportPipeline": 300,
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
        self.seen_slugs: Set[str] = set()
        self.seen_page_signatures: Set[tuple] = set()
        self.stop_reason = "in_progress"
        self.last_listing_page = 0

    # ---------------------------------------------------------
    # URL NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_url(raw_url: str) -> str:
        """
        Chuẩn hóa URL của Hoàng Hà Mobile:
        - Xử lý đồng nhất tiền tố danh mục: /lap-top/ -> /laptop/
        - Đảm bảo absolute URL bắt đầu bằng https://hoanghamobile.com
        - Bỏ trailing slashes và query params không cần thiết
        """
        if not raw_url:
            return ""
        url = raw_url.strip()
        if url.startswith("/"):
            url = urljoin(BASE_WEB_URL, url)

        parsed = urlparse(url)
        path = parsed.path
        # Thay thế /lap-top/ thành /laptop/
        if path.startswith("/lap-top/"):
            path = "/laptop/" + path[len("/lap-top/") :]
        elif path == "/lap-top":
            path = "/laptop"

        # Bỏ trailing slash nếu không phải root
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        return f"{parsed.scheme}://{parsed.netloc}{path}"

    @staticmethod
    def extract_canonical_slug(url: str) -> str:
        """Trích xuất slug định danh từ URL đã chuẩn hóa."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        slug = path.split("/")[-1]
        return slug

    # ---------------------------------------------------------
    # 1. START REQUESTS & LISTING PAGINATION
    # ---------------------------------------------------------

    async def start(self):
        self.logger.info(
            "Khởi động spider %s [category=%s, slug=%s, max_products=%s, batch=%s]",
            self.name,
            self.category,
            self.slug,
            self.max_products,
            self.batch_id,
        )
        yield self.make_listing_request(page=1)

    def start_requests(self):
        """Tương thích ngược đồng bộ (Scrapy cũ / test suite)."""
        yield self.make_listing_request(page=1)

    def make_listing_request(self, page: int = 1):
        """Tạo GET request phân trang tới /{slug}?p={page}."""
        if page == 1:
            url = f"{BASE_WEB_URL}/{self.slug}"
        else:
            url = f"{BASE_WEB_URL}/{self.slug}?p={page}"

        return scrapy.Request(
            url=url,
            cookies=self.default_cookies,
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
        self.logger.info("Parsing Hoàng Hà Mobile listing page=%s (status=%s)", page, response.status)

        soup = BeautifulSoup(response.text, "html.parser")
        product_items = soup.find_all(class_=lambda c: c and "pj16-item-info" in c.split())

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
                page_urls.append(self.normalize_url(link["href"]))
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

            link_el = it.find("a", href=True)
            if not link_el:
                continue

            raw_href = link_el["href"].strip()
            detail_url = self.normalize_url(raw_href)
            slug = self.extract_canonical_slug(detail_url)

            if not slug:
                continue

            # Deduplication gate: loại bỏ sản phẩm trùng lặp giữa các trang/danh mục
            if slug in self.seen_slugs:
                continue
            self.seen_slugs.add(slug)
            self.scheduled_products += 1
            scheduled_this_page += 1

            # Thu thập thông tin từ Listing card (SSR phong phú làm fallback & làm giàu dữ liệu)
            title_el = it.find("h3") or link_el
            listing_title = title_el.text.strip() if title_el else None

            # Bốn tầng giá trên listing:
            # Tầng 1: Giá bán hiện tại
            price_el = it.find("div", class_=lambda c: c and "price" in c.split() and "price-last" not in c.split())
            listing_price = price_el.find("strong").text.strip() if price_el and price_el.find("strong") else None

            # Tầng 2: Giá gốc gạch ngang
            old_price_el = it.find(class_=lambda c: c and "price-last" in c.split())
            listing_old_price = (
                old_price_el.find("strike").text.strip() if old_price_el and old_price_el.find("strike") else None
            )

            # Tầng 3: Giá Hoàng Hà Member (chỉ từ...)
            member_price_el = it.find(class_=lambda c: c and "price-tags-member" in c.split())
            listing_member_price = (
                member_price_el.find("strong").text.strip()
                if member_price_el and member_price_el.find("strong")
                else None
            )

            # Trạng thái tồn kho: chỉ nhận diện khi thực sự có keyword tồn kho hợp lệ
            HOANGHA_VALID_STOCK_KEYWORDS = {
                "sẵn hàng", "liên hệ", "sắp diễn ra", "tạm hết hàng", "hết hàng",
                "còn hàng", "đặt trước", "ngừng kinh doanh"
            }
            listing_stock = None
            for badge_el in it.find_all(class_=lambda c: c and any(k in c.lower() for k in ["stock", "status", "sticker"])):
                b_text = badge_el.text.strip()
                if b_text.lower() in HOANGHA_VALID_STOCK_KEYWORDS:
                    listing_stock = b_text
                    break

            listing_data = {
                "slug": slug,
                "title": listing_title,
                "price": listing_price,
                "original_price": listing_old_price,
                "member_price": listing_member_price,
                "stock": listing_stock,
                "url": detail_url,
            }

            yield scrapy.Request(
                url=detail_url,
                cookies=self.default_cookies,
                callback=self.parse_detail,
                errback=self.errback_detail,
                meta={
                    "slug": slug,
                    "listing_data": listing_data,
                    "page": page,
                    "handle_httpstatus_list": [403, 404, 500, 502],
                },
            )

        # Kiểm tra nút phân trang "Xem thêm {N} sản phẩm" (#page-pager a)
        pager = soup.find(id="page-pager")
        has_next_page = False
        if pager:
            pager_link = pager.find("a", href=True)
            if pager_link and "?p=" in pager_link["href"]:
                has_next_page = True

        if has_next_page:
            if self.max_products is None or self.scheduled_products < self.max_products:
                yield self.make_listing_request(page=page + 1)
        else:
            if self.stop_reason == "in_progress":
                self.stop_reason = "no_more_products"

    def errback_detail(self, failure):
        self.detail_failures += 1
        req = failure.request
        slug = req.meta.get("slug") if req.meta else None
        self.logger.error("Detail request thất bại cho slug=%s [url=%s]: %s", slug, req.url, failure.value)

    # ---------------------------------------------------------
    # 3. PARSE DETAIL RESPONSE
    # ---------------------------------------------------------

    def parse_detail(self, response):
        meta = response.meta or {}
        slug = meta.get("slug")
        listing_data = meta.get("listing_data", {})
        now_iso = datetime.now().astimezone().isoformat()

        HOANGHA_VALID_STOCK_KEYWORDS = {
            "sẵn hàng", "liên hệ", "sắp diễn ra", "tạm hết hàng", "hết hàng",
            "còn hàng", "đặt trước", "ngừng kinh doanh"
        }

        def _is_excluded_price_el(el):
            if not el:
                return True
            elements_to_check = [el] + list(el.parents)
            for item in elements_to_check:
                classes = item.get("class", [])
                class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                id_str = str(item.get("id", ""))
                combined = f"{class_str} {id_str}".lower()
                if any(k in combined for k in [
                    "accessory", "accessories", "phu-kien", "phukien", "bundle",
                    "related", "similar", "tuong-tu", "goi-y", "suggest",
                    "price-tags-member", "member", "installment", "tra-gop",
                    "thu-cu", "thucu", "trade-in", "tradein", "old-for-new",
                    "promotion", "khuyen-mai", "deal", "sp-lien-quan", "box-installment"
                ]):
                    return True
            return False

        # Xử lý trường hợp URL detail bị lỗi hoặc inaccessible (403, 404) -> fallback an toàn từ Listing data
        if response.status in (403, 404, 500, 502):
            self.logger.warning("Detail page %s trả về HTTP %s. Sử dụng fallback từ Listing.", response.url, response.status)
            yield self._build_item_from_listing(listing_data, response.url, now_iso, response_status=response.status)
            return

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Trích xuất Schema.org JSON-LD
        json_ld_data = {}
        for s in soup.find_all("script", type="application/ld+json"):
            if s.string and "Product" in s.string:
                try:
                    data = json.loads(s.string.strip())
                    if isinstance(data, dict) and data.get("@type") == "Product":
                        json_ld_data = data
                        break
                except Exception:
                    pass

        # 2. Product ID (Primary ID)
        # Hierarchy:
        # 1. Hidden inputs: quickOrder_productId, ModelID, ProductId (must be digits)
        # 2. URL suffix -p(\d+)$ (typical for used/refurbished products)
        # 3. None (Never use slug or arbitrary text as product_id_raw)
        product_id_raw = None
        for id_name in ["quickOrder_productId", "ModelID", "ProductId"]:
            inp = soup.find("input", id=id_name) or soup.find("input", attrs={"name": id_name})
            if inp and inp.get("value") and inp["value"].strip().isdigit():
                product_id_raw = inp["value"].strip()
                break

        if not product_id_raw:
            pid_url_match = re.search(r"-p(\d+)$", response.url)
            if pid_url_match:
                product_id_raw = pid_url_match.group(1)

        # 3. Product Name
        product_name = None
        h1_el = soup.find("h1")
        if h1_el and h1_el.text.strip():
            product_name = h1_el.text.strip()
        elif json_ld_data.get("name"):
            product_name = str(json_ld_data["name"]).strip()
        else:
            product_name = listing_data.get("title")

        # 4. Product URL
        product_url_raw = self.normalize_url(response.url)

        # 5. Pricing (Precedence: DOM main price -> JSON-LD offer price -> listing_data fallback)
        price_raw = None
        original_price_raw = None
        price_source = "detail"

        # Lấy giá bán chính từ DOM detail (tránh lấy nhầm giá phụ kiện, related products, hoặc giá Member)
        detail_price_el = None
        for p_el in soup.find_all("div", class_=lambda c: c and "price" in c.split() and "price-last" not in c.split()):
            if not _is_excluded_price_el(p_el):
                detail_price_el = p_el
                break

        if detail_price_el and detail_price_el.find("strong"):
            p_str = detail_price_el.find("strong").text.strip()
            if any(c.isdigit() for c in p_str):
                price_raw = p_str
        elif json_ld_data.get("offers", {}).get("price"):
            json_p = str(json_ld_data["offers"]["price"]).strip()
            if json_p and json_p not in ("0", "None", ""):
                price_raw = json_p
                price_source = "json_ld"

        # Fallback từ Listing nếu Detail ẩn giá (do khu vực hết hàng hoặc tạm ngưng bán online)
        if not price_raw or price_raw.lower() in ("none", "0", ""):
            if listing_data.get("price"):
                price_raw = listing_data["price"]
                price_source = "listing_fallback"
                self.logger.info("Detail ẩn giá cho %s, kích hoạt fallback sang listing_data price: %s", slug, price_raw)

        # Giá gốc niêm yết cũ (original_price_raw)
        # 1. Giữ original_price_raw là giá niêm yết cũ của chính sản phẩm, không lấy giá member,
        #    installment, promotion, accessory, related product hay block khác.
        # 2. Nếu listing_data["original_price"] tồn tại và hợp lệ thì ưu tiên nó.
        # 3. Candidate từ detail chỉ được nhận nếu thực sự thuộc main product price block và hợp lệ về mặt semantic.
        # 4. Nếu candidate original_price_raw nhỏ hơn price_raw thì không dùng candidate đó; trả None nếu không có giá gốc hợp lệ khác.
        original_price_raw = None
        price_num = _parse_numeric_price(price_raw)

        # Bước 1: Ưu tiên listing_data["original_price"] nếu tồn tại và hợp lệ (>= price_raw)
        listing_orig = listing_data.get("original_price")
        if listing_orig and any(c.isdigit() for c in str(listing_orig)):
            l_num = _parse_numeric_price(listing_orig)
            if l_num is not None:
                if price_num is None or l_num >= price_num:
                    original_price_raw = str(listing_orig).strip()

        # Bước 2: Nếu listing_data không có hoặc không hợp lệ, tìm candidate từ Detail page
        if not original_price_raw:
            detail_candidates = []

            # 2a. Tìm trong phạm vi main product price block / container của detail_price_el trước
            search_containers = []
            if detail_price_el:
                search_containers.append(detail_price_el)
                if detail_price_el.parent:
                    search_containers.append(detail_price_el.parent)
                main_box = detail_price_el.find_parent(
                    class_=lambda c: c and any(k in c.lower() for k in [
                        "product-info", "product-details", "product-detail",
                        "top-product", "product-shop", "detail-info"
                    ])
                )
                if main_box and main_box not in search_containers:
                    search_containers.append(main_box)

            for container in search_containers:
                for el in container.find_all(class_=lambda c: c and "price-last" in c.split()):
                    if not _is_excluded_price_el(el):
                        st = el.find("strike")
                        cand_text = st.text.strip() if st else el.text.strip()
                        if cand_text and cand_text not in detail_candidates:
                            detail_candidates.append(cand_text)
                for st in container.find_all("strike"):
                    if not _is_excluded_price_el(st):
                        cand_text = st.text.strip()
                        if cand_text and cand_text not in detail_candidates:
                            detail_candidates.append(cand_text)

            # 2b. Nếu chưa thấy trong search_containers, mở rộng tìm kiếm toàn soup nhưng loại trừ chặt chẽ
            if not detail_candidates:
                for el in soup.find_all(class_=lambda c: c and "price-last" in c.split()):
                    if not _is_excluded_price_el(el):
                        st = el.find("strike")
                        cand_text = st.text.strip() if st else el.text.strip()
                        if cand_text and cand_text not in detail_candidates:
                            detail_candidates.append(cand_text)
                for st in soup.find_all("strike"):
                    if not _is_excluded_price_el(st):
                        cand_text = st.text.strip()
                        if cand_text and cand_text not in detail_candidates:
                            detail_candidates.append(cand_text)

            # 2c. Kiểm tra tính hợp lệ semantic: candidate >= price_raw
            for cand in detail_candidates:
                cand_clean = cand.strip()
                if not any(c.isdigit() for c in cand_clean):
                    continue
                cand_num = _parse_numeric_price(cand_clean)
                if cand_num is None or cand_num <= 0:
                    continue
                # Quy tắc cứng: giá gốc không được nhỏ hơn giá bán
                if price_num is not None and cand_num < price_num:
                    continue
                # Candidate hợp lệ
                original_price_raw = cand_clean
                break

        # Giá Member và giá trả góp (được tách riêng và lưu vào attributes_raw, KHÔNG map vào price_raw)
        member_price_raw = listing_data.get("member_price")
        detail_member_el = None
        for p_el in soup.find_all(class_=lambda c: c and "price-tags-member" in c.split()):
            detail_member_el = p_el
            break

        if detail_member_el and detail_member_el.find("strong"):
            member_price_raw = detail_member_el.find("strong").text.strip()

        installment_monthly_raw = None
        inst_match = re.search(r"Hoặc\s*([\d\.,]+\s*₫)\s*x\s*6T", response.text, re.I)
        if inst_match:
            installment_monthly_raw = inst_match.group(1).strip()

        # 6. SKU / MPN trích xuất
        sku_raw = None
        variant_sku_raw = None
        if self.category == "laptop":
            # Laptop Windows thường có SKU/MPN trong JSON-LD hoặc tiêu đề
            if json_ld_data.get("sku"):
                sku_raw = str(json_ld_data["sku"]).strip()
                variant_sku_raw = sku_raw
            elif product_name:
                # Tìm mã model/MPN dạng alphanumeric có chữ và số
                sku_candidates = re.findall(r"\b([A-Z0-9]{5,}-[A-Z0-9]+|[0-9]{2}[A-Z0-9]{6,}|P\d{3}F\d{3})\b", product_name)
                if sku_candidates:
                    sku_raw = sku_candidates[-1]
                    variant_sku_raw = sku_raw
        else:
            sku_raw = None
            variant_sku_raw = None

        # 7. Brand
        brand_raw = None
        if json_ld_data.get("brand"):
            brand_val = json_ld_data["brand"]
            brand_raw = brand_val.get("name") if isinstance(brand_val, dict) else str(brand_val)

        # 8. Availability (Evidence-based only: absence of evidence = None, KHÔNG default thành "Sẵn hàng")
        availability_raw = None

        # Evidence 1: Check DOM status / out-of-stock notices in detail area
        out_of_stock_el = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["out-of-stock", "out_of_stock", "hethang"]))
        if out_of_stock_el:
            availability_raw = "Tạm hết hàng"
        else:
            status_el = soup.find(class_=lambda c: c and any(k in c.lower() for k in ["status", "stock", "availability"]))
            if status_el and not _is_excluded_price_el(status_el):
                st_text = status_el.text.strip().lower()
                if "tạm dừng đặt hàng" in st_text or "tạm hết hàng" in st_text or "hết hàng" in st_text:
                    availability_raw = "Tạm hết hàng"
                elif "sẵn hàng" in st_text or "còn hàng" in st_text:
                    availability_raw = "Sẵn hàng"
                elif "liên hệ" in st_text:
                    availability_raw = "Liên hệ"
                elif "sắp diễn ra" in st_text:
                    availability_raw = "Sắp diễn ra"

        # Evidence 2: Check JSON-LD offers.availability
        if not availability_raw:
            avail_schema = json_ld_data.get("offers", {}).get("availability", "")
            if "InStock" in avail_schema:
                availability_raw = "Sẵn hàng"
            elif "OutOfStock" in avail_schema:
                availability_raw = "Tạm hết hàng"

        # Evidence 3: Fallback to valid listing stock if present
        if not availability_raw and listing_data.get("stock"):
            if listing_data["stock"].lower() in HOANGHA_VALID_STOCK_KEYWORDS:
                availability_raw = listing_data["stock"]

        # Nếu không có bất kỳ bằng chứng tồn kho nào, availability_raw giữ nguyên None!

        # 9. Technical Attributes (trích xuất từ bảng specs 20+ dòng)
        attributes_raw: Dict[str, Any] = {}
        for tbl in soup.find_all("table"):
            for tr in tbl.find_all("tr"):
                tds = tr.find_all(["td", "th"])
                if len(tds) >= 2:
                    k = tds[0].text.strip()
                    v = tds[1].text.strip()
                    if k and v and k not in attributes_raw and len(k) < 80:
                        attributes_raw[k] = v

        if member_price_raw:
            attributes_raw["member_price_raw"] = member_price_raw
        if installment_monthly_raw:
            attributes_raw["installment_monthly_raw"] = installment_monthly_raw

        # 10. Raw Payload (Extracted debug provenance dictionary capturing source properties, listing snapshot, and JSON-LD data; NOT a full HTML dump)
        raw_payload = {
            "source": "hoanghamobile",
            "category": self.category,
            "slug": slug,
            "product_id_raw": product_id_raw,
            "price_source": price_source,
            "region": "Hà Nội",
            "listing_data": listing_data,
            "json_ld": json_ld_data,
            "detail_url": product_url_raw,
        }

        # 11. Yield TechProductRawItem (25 CANONICAL FIELDS)
        item = TechProductRawItem()
        item["source"] = "hoanghamobile"
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
        item["seller_raw"] = "Hoàng Hà Mobile"
        item["rating_raw"] = None
        item["review_count_raw"] = None
        item["total_sold_raw"] = None

        item["attributes_raw"] = attributes_raw
        item["raw_payload"] = raw_payload

        self.scraped_items_count += 1
        yield item

        # Hoàng Hà Mobile chỉ có comment/hỏi đáp (Q&A), KHÔNG có customer review theo rating.
        # Customer review extraction hiện chưa được hỗ trợ cho Hoàng Hà Mobile và KHÔNG yield TechReviewRawItem.

    def _build_item_from_listing(self, listing_data: dict, url: str, now_iso: str, response_status: int):
        """Xây dựng TechProductRawItem dự phòng hoàn toàn từ Listing khi Detail bị lỗi kết nối/HTTP 404/403."""
        norm_url = self.normalize_url(url)
        slug = listing_data.get("slug") or self.extract_canonical_slug(norm_url)
        title = listing_data.get("title")

        item = TechProductRawItem()
        item["source"] = "hoanghamobile"
        item["category"] = self.category
        item["crawl_batch"] = self.batch_id
        item["crawl_time"] = now_iso

        item["product_id_raw"] = None
        item["product_name_raw"] = title
        item["product_url_raw"] = norm_url

        item["parent_product_id_raw"] = None
        item["parent_product_name_raw"] = title
        item["parent_url_raw"] = norm_url

        item["sku_raw"] = None
        item["variant_sku_raw"] = None
        item["variant_name_raw"] = None
        item["variant_color_raw"] = None
        item["variant_url_raw"] = norm_url

        HOANGHA_VALID_STOCK_KEYWORDS = {
            "sẵn hàng", "liên hệ", "sắp diễn ra", "tạm hết hàng", "hết hàng",
            "còn hàng", "đặt trước", "ngừng kinh doanh"
        }
        listing_st = listing_data.get("stock")
        if listing_st and listing_st.lower() in HOANGHA_VALID_STOCK_KEYWORDS:
            item["availability_raw"] = listing_st
        else:
            item["availability_raw"] = None

        item["price_raw"] = listing_data.get("price")
        listing_orig = listing_data.get("original_price")
        p_num = _parse_numeric_price(item["price_raw"])
        l_num = _parse_numeric_price(listing_orig)
        if listing_orig and (p_num is None or l_num is None or l_num >= p_num):
            item["original_price_raw"] = listing_orig
        else:
            item["original_price_raw"] = None

        item["brand_raw"] = None
        item["seller_raw"] = "Hoàng Hà Mobile"
        item["rating_raw"] = None
        item["review_count_raw"] = None
        item["total_sold_raw"] = None

        attrs = {}
        if listing_data.get("member_price"):
            attrs["member_price_raw"] = listing_data["member_price"]
        item["attributes_raw"] = attrs

        item["raw_payload"] = {
            "source": "hoanghamobile",
            "category": self.category,
            "slug": slug,
            "listing_data": listing_data,
            "detail_url": norm_url,
            "detail_http_status": response_status,
            "price_source": "listing_only",
        }

        self.scraped_items_count += 1
        return item
