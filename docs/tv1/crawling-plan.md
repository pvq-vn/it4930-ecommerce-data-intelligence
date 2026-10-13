# Kế hoạch & Kiến trúc Crawler Thế Giới Di Động (TV1)

Tài liệu này mô tả chi tiết kiến trúc, chính sách thu thập (politeness), cơ chế quản lý snapshot bất biến (immutable snapshots), kiểm soát trùng lặp HTTP request và khả năng quan sát (observability) cho crawler Thế Giới Di Động (TGDĐ) thuộc giai đoạn TV1 (Web Crawling & Data Acquisition).

---

## 1. Nguồn Dữ Liệu
- **Laptop**: `https://www.thegioididong.com/laptop`
- **Smartphone**: `https://www.thegioididong.com/dtdd` *(lưu ý: endpoint cũ `/dien-thoai` trả về HTTP 404)*

---

## 2. Chính Sách Tuân Thủ (Robots.txt & Politeness)
1. **Robots.txt trên domain chính (`www.thegioididong.com`)**:
   - `User-agent: *`
   - `Crawl-delay: 5`
   - Các danh mục `/laptop` và `/dtdd` không nằm trong danh sách `Disallow`.
2. **Robots.txt trên API subdomain (`api.thegioididong.com`)**:
   - Truy vấn `https://api.thegioididong.com/robots.txt` trả về mã HTTP `404 Not Found`.
   - **Quy tắc**: Không suy diễn hoặc tự đặt ra policy riêng cho API. Để đảm bảo an toàn và tôn trọng máy chủ nguồn, crawler chủ động áp dụng cấu hình conservative tuân theo policy Crawl-delay của domain chính.
3. **Cấu hình Politeness (Conservative Crawler Settings)**:
   - `ROBOTSTXT_OBEY = True`
   - `DOWNLOAD_DELAY = 5.0` (giây, tuân thủ Crawl-delay 5s)
   - `CONCURRENT_REQUESTS = 1` (tuần tự hóa mọi request)
   - `CONCURRENT_REQUESTS_PER_DOMAIN = 1`
   - `AUTOTHROTTLE_ENABLED = True`
   - `AUTOTHROTTLE_START_DELAY = 5.0`
   - `AUTOTHROTTLE_MAX_DELAY = 60.0`
   - `AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0`
   - `RETRY_TIMES = 3` (xử lý retry cho 500, 502, 503, 504, 408, 429)

---

## 3. Cơ Chế Thu Thập (Evidence-Based Acquisition)

### A. Danh sách sản phẩm (Listing)
- **Endpoint**: `POST https://api.thegioididong.com/gw/bus-tgdd-tmdt/api/Cate/GetproductCateV2`
- **Headers**:
  - `Content-Type`: `application/json`
  - `Accept`: `application/json, text/plain, */*`
  - `Referer`: `https://www.thegioididong.com/laptop` hoặc `/dtdd`
  - `User-Agent`: Chrome Windows User-Agent chuẩn
  - `Os`: `WebTGDD`
  - `Platform`: `1`
  - `Provinceid`: `1000`
  - `Siteid`: `1`
  - `Isverify`: `0`
- **Payload**:
  - Laptop: `{"pageIndex": <page>, "pageSize": 20, "provinceId": 1000, "urlCate": "laptop", "cateId": "17", "filters": [{"filterId": 1, "filterTypeId": 6, "sortName": "FEATURED_PRODUCTS", "url": ""}]}`
  - Smartphone: `{"pageIndex": <page>, "pageSize": 20, "provinceId": 1000, "urlCate": "dtdd", "cateId": "42", "filters": [{"filterId": 1, "filterTypeId": 6, "sortName": "FEATURED_PRODUCTS", "url": ""}]}`
- **Cấu trúc Response**: JSON `data.products[]`. Không phụ thuộc vào HTML fragment.
- **Trường lấy từ Listing**: `product_id_raw`, `product_name_raw`, `product_url_raw`, `price_raw`, `original_price_raw`, `seller_raw`, `rating_raw`, `review_count_raw`, `brand_raw`, `total_sold_raw`, `sku_raw`.

### B. Chi tiết sản phẩm (Detail)
- **Phương thức**: `GET https://www.thegioididong.com/<url>`
- **Trích xuất thông số kỹ thuật (`attributes_raw`)**:
  - Ưu tiên: Schema.org JSON-LD (`@type` là `Product` hoặc `ProductGroup`) -> lấy mảng `additionalProperty` gồm các cặp `{name, value}` chuẩn.
  - Fallback: HTML DOM `<section>` chứa "Thông số kỹ thuật".
  - Bảo toàn tên thuộc tính và giá trị gốc, không normalize.
- **Xử lý khi detail thất bại**: Nếu request detail gặp lỗi kết nối/HTTP error, crawler kích hoạt `errback_detail` để ghi log chi tiết (URL, product_id, tên sản phẩm), cập nhật metric lỗi và yield record fallback từ listing (với `attributes_raw = {}`) nhằm bảo toàn dữ liệu đã phát hiện thay vì drop âm thầm.

---

## 4. Kiểm Soát Trùng Lặp HTTP Request (Duplicate Request Control)
- **Bỏ `dont_filter=True`**: Cả listing request và detail request đều không sử dụng `dont_filter=True`, cho phép bộ lọc trùng `RFPDupeFilter` của Scrapy hoạt động theo thiết kế chuẩn.
- **Cơ chế phân biệt**:
  - Đối với Listing POST request: Scrapy tính request fingerprint dựa trên URL và request body. Vì request body chứa `pageIndex` khác nhau giữa các trang phân trang, `RFPDupeFilter` cho phép các trang kế tiếp đi qua bình thường nhưng sẽ ngăn chặn các request trùng trang.
  - Đối với Detail GET request: Fingerprint dựa trên URL chi tiết, ngăn việc crawler gửi nhiều request tải lặp lại cùng một trang chi tiết sản phẩm.
- **Phân định trách nhiệm**: TV1 chỉ quản lý deduplication ở tầng HTTP request. Khâu khử trùng thực thể dữ liệu (semantic data deduplication) được thực hiện độc lập tại TV2.

---

## 5. Khả Năng Quan Sát (Observability & Error Metrics)
Crawler cung cấp khả năng quan sát và phân loại lỗi rõ ràng:
- **Listing errors**: `errback_listing` ghi nhận lỗi kết nối/HTTP ở listing; bắt lỗi `JSONDecodeError` khi decode payload response listing; tăng biến đếm `listing_failures`.
- **Detail errors**: `errback_detail` ghi nhận chi tiết URL bị lỗi, `product_id_raw` và mã lỗi; tăng biến đếm `detail_failures` và `attribute_extraction_failures`.
- **Attribute extraction**: Phân biệt trường hợp trích xuất thành công (`attribute_extraction_successes`) và trường hợp không tìm thấy thuộc tính (`attribute_extraction_failures`). Không nuốt lỗi silently bằng `except Exception: pass`.
- **Crawl summary log**: Khi spider đóng (`closed`), spider tự động in bảng tổng kết:
  - `finish_reason`
  - `listing_pages_processed`
  - `listing_failures`
  - `scheduled_products`
  - `scraped_items_count`
  - `detail_successes`
  - `detail_failures`
  - `attribute_extraction_successes`
  - `attribute_extraction_failures`

---

## 6. Snapshot Bất Biến (Immutable Raw Snapshots)
- **Cấu trúc lưu trữ**: Dữ liệu raw được ghi dưới định dạng JSON Lines (.jsonl). Mỗi lần thực thi crawler sẽ tạo một snapshot riêng biệt:
  - `data/raw/tgdd/laptop/<batch_id>.jsonl`
  - `data/raw/tgdd/smartphone/<batch_id>.jsonl`
- **Định dạng Batch ID**: Timestamp `YYYYMMDD_HHMMSS` (ví dụ: `20261013_081500`).
- **Tính nhất quán**: `batch_id` của tên file đồng nhất hoàn toàn với trường metadata `crawl_batch` trong từng record JSONL.
- **Tính bất biến (Immutability)**: Crawler không xóa (`unlink`), ghi đè hay thay thế các snapshot cũ. File `pilot.jsonl` hiện có trong mỗi danh mục được giữ nguyên vẹn làm snapshot pilot cơ sở ban đầu.
- **Phạm vi dữ liệu**: TV1 bảo toàn nguyên trạng dữ liệu raw (số nguyên, chuỗi, dictionary thô). Tuyệt đối không ghi dữ liệu đã chuẩn hóa/cleaning vào raw layer.

---

## 7. Cấu Trúc Mã Nguồn
```text
crawler/
    run_crawler.py              # CLI runner script (quản lý batch_id, immutable snapshots)
    tgdd/
        __init__.py
        items.py                # TechProductRawItem schema
        base_spider.py          # TgddBaseSpider (logic chung, politeness, dupe control, observability)
        tgdd_laptop_spider.py   # TgddLaptopSpider (/laptop)
        tgdd_smartphone_spider.py # TgddSmartphoneSpider (/dtdd)
data/
    raw/
        tgdd/
            laptop/
                pilot.jsonl     # Snapshot pilot ban đầu (50 records laptop)
                <batch_id>.jsonl # Các snapshot crawl sau đó
            smartphone/
                pilot.jsonl     # Snapshot pilot ban đầu (50 records smartphone)
                <batch_id>.jsonl # Các snapshot crawl sau đó
tests/
    test_tgdd_crawler.py        # Unit tests & validation suite
```

---

## 8. Hướng Dẫn Chạy & Kiểm Thử

### Chạy Crawler (Tạo Immutable Snapshot tự động):
```bash
# Chạy cả 2 danh mục (mỗi danh mục tạo 1 snapshot riêng biệt theo timestamp):
python crawler/run_crawler.py --category all --limit 50

# Chạy riêng từng danh mục:
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50
```

### Chạy với tùy chọn thủ công:
```bash
# Chỉ định file đầu ra cụ thể (chỉ dùng khi chọn 1 category):
python crawler/run_crawler.py --category laptop --limit 50 --output data/raw/tgdd/laptop/test_run.jsonl

# Chỉ định batch_id cụ thể:
python crawler/run_crawler.py --category laptop --limit 50 --batch-id 20261013_081500
```

### Chạy qua Scrapy CLI:
```bash
scrapy runspider crawler/tgdd/tgdd_laptop_spider.py -a max_products=50 -a batch_id=20261013_081500 -o data/raw/tgdd/laptop/20261013_081500.jsonl
scrapy runspider crawler/tgdd/tgdd_smartphone_spider.py -a max_products=50 -a batch_id=20261013_081900 -o data/raw/tgdd/smartphone/20261013_081900.jsonl
```

### Chạy Bộ Kiểm Thử Tự Động:
```bash
python -m unittest discover tests
```
