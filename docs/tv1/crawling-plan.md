# Kế hoạch & Kiến trúc Crawler Thế Giới Di Động (TV1)

Tài liệu này mô tả chi tiết kiến trúc, chính sách thu thập (politeness), cơ chế quản lý snapshot bất biến (immutable snapshots), kiểm soát trùng lặp HTTP request, khả năng quan sát (observability), cùng hai chế độ thu thập **Pilot Mode** và **Full Crawl Mode** cho sàn Thế Giới Di Động (TGDĐ) thuộc giai đoạn TV1 (Web Crawling & Data Acquisition).

---

## 1. Nguồn Dữ Liệu & Phạm Vi (Scope)
- **Laptop**: `https://www.thegioididong.com/laptop` (Listing API `urlCate="laptop"`, `cateId="17"`)
- **Smartphone**: `https://www.thegioididong.com/dtdd` (Listing API `urlCate="dtdd"`, `cateId="42"`)

> **Quy định phạm vi**: Chỉ thu thập đúng 2 danh mục Laptop và Smartphone phục vụ bài toán dự đoán giá sản phẩm công nghệ của đề tài. Tuyệt đối không crawl các danh mục ngoài phạm vi (như tablet, smartwatch, phụ kiện). Không thực hiện chuẩn hóa ngữ nghĩa, làm sạch hoặc khử trùng thực thể dữ liệu tại TV1 (thuộc TV2).

---

## 2. Chính Sách Tuân Thủ (Robots.txt & Politeness)
1. **Robots.txt trên domain chính (`www.thegioididong.com`)**:
   - `User-agent: *`
   - `Crawl-delay: 5`
   - Các danh mục `/laptop` và `/dtdd` không nằm trong danh sách `Disallow`.
2. **Robots.txt trên API subdomain (`api.thegioididong.com`)**:
   - Truy vấn `https://api.thegioididong.com/robots.txt` trả về HTTP `404 Not Found`.
   - **Quy tắc**: Không suy diễn hoặc tự đặt ra policy riêng cho API. Để đảm bảo an toàn tối đa cho máy chủ nguồn và tuân thủ đạo đức thu thập, crawler áp dụng cấu hình conservative tuân theo policy Crawl-delay của domain chính.
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
   - **Không áp dụng kỹ thuật lách**: Không tăng tốc, không dùng đa luồng, không giảm delay, không bypass anti-bot hay dùng access token ẩn.

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
- **Xử lý khi detail thất bại**: Kích hoạt `errback_detail` để ghi log chi tiết (URL, product_id, tên sản phẩm), cập nhật metric lỗi và yield record fallback từ listing (với `attributes_raw = {}`) nhằm bảo toàn dữ liệu đã phát hiện thay vì drop âm thầm.

---

## 4. Chế Độ Thu Thập & Điều Kiện Dừng Phân Trang

Hệ thống hỗ trợ 2 chế độ thu thập thông qua tham số `max_products`:

### A. Pilot Mode (`max_products = 50`)
- Mục đích: Thu thập mẫu nhỏ (50 sản phẩm mỗi danh mục) để kiểm thử luồng dữ liệu nhanh, kiểm thử schema và unit tests.
- Điều kiện dừng: Khi `scheduled_products >= 50`, crawler ngắt vòng lặp phân trang với `stop_reason = "max_products_reached"`.
- Snapshot ban đầu: Đã lưu tại `data/raw/tgdd/laptop/pilot.jsonl` và `data/raw/tgdd/smartphone/pilot.jsonl`.

### B. Full Crawl Mode (`max_products = None` / `--full`)
- Mục đích: Thu thập toàn bộ sản phẩm thực tế trong danh mục mà không bị giới hạn số lượng (`unlimited`).
- Cơ chế phân trang: Tiếp tục qua các trang `pageIndex = 1, 2, 3, ...` tuần tự cho đến khi thỏa mãn một trong các điều kiện dừng an toàn.

### C. Các Điều Kiện Dừng Phân Trang (Termination & Guard Conditions)
1. **Hết sản phẩm (`no_more_products`)**:
   - Khi API trả về response có `products = []` hoặc không còn phần tử mới.
   - Đây là điểm kết thúc tự nhiên của danh mục.
2. **Chốt an toàn chống lặp trang (`repeated_page_signature`)**:
   - Để ngăn ngừa vòng lặp vô tận (infinite loop) trong trường hợp API máy chủ trả về lặp lại cùng một trang sản phẩm (lỗi phân trang thường gặp ở một số e-commerce API khi vượt quá trang cuối), crawler tính toán `page_signature` (bộ nhận diện danh sách product ID / URL trên trang).
   - Nếu một page signature bị trùng lặp với trang trước đó, crawler sẽ cảnh báo, dừng phân trang ngay lập tức và ghi nhận `stop_reason = "repeated_page_signature"`.
3. **Lỗi hệ thống hoặc kết nối (`error/failure`)**:
   - Khi request listing thất bại sau toàn bộ số lần retry (3 lần) hoặc gặp lỗi giải mã JSON nghiêm trọng.

---

## 5. Kiểm Soát Trùng Lặp HTTP Request (Duplicate Request Control)
- **Bỏ `dont_filter=True`**: Cả listing request và detail request đều sử dụng cơ chế lọc trùng mặc định `RFPDupeFilter` của Scrapy.
- **Cơ chế phân biệt**:
  - Listing POST request: Scrapy tính fingerprint dựa trên URL và request body. Vì body chứa `pageIndex` khác nhau, các trang tiếp theo không bị chặn, nhưng request trùng cùng một trang sẽ bị chặn.
  - Detail GET request: Fingerprint dựa trên URL chi tiết, ngăn việc gửi lặp HTTP request tới cùng 1 sản phẩm.
- **Phân định trách nhiệm**: TV1 chỉ quản lý deduplication ở tầng HTTP request. Khâu khử trùng thực thể dữ liệu (semantic data deduplication) thuộc phạm vi TV2.

---

## 6. Khả Năng Quan Sát (Observability & Error Metrics)
Crawl summary in tự động khi spider đóng (`closed`):
- `finish_reason`: Trạng thái kết thúc của Scrapy (ví dụ: `finished`).
- `stop_reason`: Lý do dừng phân trang (`max_products_reached`, `no_more_products`, `repeated_page_signature`, `error/failure`).
- `last_listing_page`: Trang listing cuối cùng đã xử lý.
- `listing_pages_processed`: Tổng số trang listing đã parse thành công.
- `listing_failures`: Số trang listing gặp lỗi request/JSON decode.
- `scheduled_products`: Số lượng sản phẩm đã được lên lịch cào.
- `scraped_items_count`: Số lượng records thực tế đã thu thập và yield.
- `detail_successes`: Số lượng trang chi tiết cào thành công.
- `detail_failures`: Số lượng trang chi tiết gặp lỗi.
- `attribute_extraction_successes`: Số lượng sản phẩm trích xuất được thuộc tính kỹ thuật.
- `attribute_extraction_failures`: Số lượng sản phẩm không trích xuất được thuộc tính.

---

## 7. Snapshot Bất Biến & Chống Ghi Đè (Immutable Raw Snapshots)
- **Định dạng file**: JSON Lines (`.jsonl`).
- **Đường dẫn**:
  - `data/raw/tgdd/laptop/<batch_id>.jsonl`
  - `data/raw/tgdd/smartphone/<batch_id>.jsonl`
- **Định dạng Batch ID**: Timestamp `YYYYMMDD_HHMMSS` (ví dụ: `20261013_081500`).
- **Tính đồng nhất**: Giá trị trường `crawl_batch` trong từng record luôn đồng nhất với `batch_id` của tên file snapshot.
- **Quy tắc bất biến (Immutability)**:
  - Nếu đường dẫn file snapshot đã tồn tại trên ổ đĩa, runner raise `FileExistsError` và dừng lại ngay trước khi khởi động Scrapy.
  - Tuyệt đối không append vào file cũ, không overwrite và không xóa file cũ.
  - File `pilot.jsonl` ban đầu được bảo toàn nguyên vẹn làm baseline pilot.

---

## 8. Hướng Dẫn Thực Thi

### A. Chế độ Pilot (Mặc định `limit=50`):
```bash
# Chạy cả 2 danh mục:
python crawler/run_crawler.py --category all --limit 50

# Chạy riêng từng danh mục:
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50
```

### B. Chế độ Full Crawl (`--full`):
```bash
# Thu thập toàn bộ Laptop và Smartphone:
python crawler/run_crawler.py --category all --full

# Thu thập toàn bộ Laptop:
python crawler/run_crawler.py --category laptop --full

# Thu thập toàn bộ Smartphone:
python crawler/run_crawler.py --category smartphone --full
```

### C. Quy định Entry Point & Bảo Vệ Snapshot Bất Biến:
> **LƯU Ý BẮT BUỘC**: `crawler/run_crawler.py` là entry point duy nhất được phép sử dụng để vận hành crawler trong toàn bộ dự án.
>
> **Tuyệt đối không chạy trực tiếp `scrapy runspider ... -o ...` từ terminal.** Việc gọi trực tiếp Scrapy Feed Exporter (`-o`) sẽ bỏ qua hàm kiểm tra collision `ensure_output_path_available()` của runner, dẫn đến rủi ro ghi đè hoặc append dữ liệu vào các snapshot đã có (như `pilot.jsonl`), phá vỡ tính bất biến (immutability) của raw layer.

### D. Kiểm thử tự động:
```bash
python -m unittest discover tests
```
