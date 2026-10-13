# IT4930 - E-commerce Data Intelligence

## TV1: Web Crawling & Data Acquisition (Thế Giới Di Động - Laptop & Smartphone)

Hệ thống crawler thực tế cho sàn thương mại điện tử Thế Giới Di Động (TGDĐ), phục vụ giai đoạn thu thập dữ liệu gốc (Raw Data) cho bài toán dự đoán giá sản phẩm công nghệ trong đúng 2 danh mục mục tiêu của project: **Laptop** và **Smartphone**.

> **Phạm vi (Scope)**: Chỉ crawl dữ liệu cho 2 danh mục Laptop (`/laptop`) và Smartphone (`/dtdd`). Không thu thập các danh mục khác của TGDĐ. Không thực hiện chuẩn hóa, làm sạch (cleaning) hay khử trùng ngữ nghĩa (semantic deduplication) tại raw layer (các tác vụ này thuộc TV2).

---

### 1. Cấu trúc thư mục
- `crawler/tgdd/items.py`: Schema dữ liệu thô `TechProductRawItem` theo chuẩn TV1.
- `crawler/tgdd/base_spider.py`: Spider cơ sở (`TgddBaseSpider`) tích hợp cơ chế request API, phân trang (hỗ trợ cả Pilot mode và Full crawl mode), chốt an toàn chống lặp trang (pagination guard), trích xuất Schema.org JSON-LD và fallback DOM, kiểm soát duplicate request và theo dõi observability.
- `crawler/tgdd/tgdd_laptop_spider.py`: Spider danh mục Laptop (`/laptop`).
- `crawler/tgdd/tgdd_smartphone_spider.py`: Spider danh mục Smartphone (`/dtdd`).
- `crawler/run_crawler.py`: CLI script điều phối chạy crawler, hỗ trợ Pilot mode, Full crawl mode và cơ chế snapshot bất biến (immutable snapshots).
- `data/raw/tgdd/laptop/`: Thư mục raw snapshots Laptop (`pilot.jsonl`, `<batch_id>.jsonl`).
- `data/raw/tgdd/smartphone/`: Thư mục raw snapshots Smartphone (`pilot.jsonl`, `<batch_id>.jsonl`).
- `tests/test_tgdd_crawler.py`: Bộ kiểm thử tự động (Unit tests: schema, raw integrity, duplicate control, observability, immutability, pilot validation, full crawl pagination).

---

### 2. Nguyên tắc & Chính sách Thu thập (Politeness)
- **Robots.txt Domain chính**: `www.thegioididong.com/robots.txt` quy định `User-agent: *`, `Crawl-delay: 5`. Hai danh mục `/laptop` và `/dtdd` không nằm trong danh sách `Disallow`.
- **API Domain**: `api.thegioididong.com/robots.txt` trả về HTTP 404 (Not Found), không suy diễn policy riêng cho API. Hệ thống crawler áp dụng cấu hình conservative tuân thủ nghiêm ngặt chính sách của trang www:
  - `ROBOTSTXT_OBEY = True`
  - `DOWNLOAD_DELAY = 5.0` (giây, tuân thủ Crawl-delay 5s)
  - `CONCURRENT_REQUESTS = 1` (tuần tự hóa hoàn toàn, 1 request tại 1 thời điểm)
  - `CONCURRENT_REQUESTS_PER_DOMAIN = 1`
  - `AUTOTHROTTLE_ENABLED = True` (start delay 5.0s, max delay 60.0s, target concurrency 1.0)
  - `RETRY_TIMES = 3` (xử lý retry cho các mã lỗi tạm thời 500, 502, 503, 504, 408, 429)
  - **Tuyệt đối không tăng tốc**: Không dùng đa luồng, không giảm delay, không bypass anti-bot, không dùng token ẩn.
- **Kiểm soát trùng lặp HTTP**: Không dùng `dont_filter=True`, Scrapy `RFPDupeFilter` tự động tính fingerprint dựa trên POST body (chứa `pageIndex`) ở listing và URL ở detail, ngăn gửi lặp HTTP request không cần thiết.
- **Immutable Raw Snapshots**: Mỗi đợt crawl tạo một file snapshot riêng theo timestamp/batch_id (ví dụ: `20261013_081500.jsonl`). Runner từ chối chạy nếu file output đã tồn tại (không overwrite, không append).
- **Điều kiện dừng phân trang an toàn (Pagination Guard)**:
  - Khi API trả về mảng sản phẩm rỗng (`products=[]`), crawler dừng với stop_reason `no_more_products`.
  - Nếu API trả lại cùng một danh sách sản phẩm lặp lại (trùng `page_signature`), crawler phát hiện và dừng với stop_reason `repeated_page_signature` để chống infinite loop.

---

### 3. Cài đặt môi trường
```bash
pip install -r requirements.txt
```

---

### 4. Thực thi Crawler

#### A. Chế độ Pilot (Mặc định `limit=50` để test nhanh):
```bash
# Chạy cả 2 danh mục (mỗi danh mục 50 sản phẩm):
python crawler/run_crawler.py --category all --limit 50

# Chạy riêng từng danh mục:
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50

# Lệnh rút gọn (không truyền tham số gì mặc định chạy pilot 50):
python crawler/run_crawler.py --category laptop
```

#### B. Chế độ Full Crawl (`--full`, thu thập toàn bộ sản phẩm danh mục):
```bash
# Thu thập toàn bộ Laptop và Smartphone:
python crawler/run_crawler.py --category all --full

# Thu thập toàn bộ Laptop:
python crawler/run_crawler.py --category laptop --full

# Thu thập toàn bộ Smartphone:
python crawler/run_crawler.py --category smartphone --full
```
> **Lưu ý**: Tùy chọn `--full` và `--limit` là loại trừ lẫn nhau (mutually exclusive). Nếu truyền đồng thời cả hai, chương trình sẽ báo lỗi và dừng lại.

#### C. Chạy tùy chỉnh file đầu ra hoặc Batch ID (chỉ áp dụng khi chọn 1 danh mục):
```bash
python crawler/run_crawler.py --category laptop --limit 50 --output data/raw/tgdd/laptop/test_run.jsonl
python crawler/run_crawler.py --category laptop --full --batch-id 20261013_081500
```

#### D. Quy định Entry Point và bảo vệ Snapshot Bất Biến (Immutable Protection):
> **LƯU Ý BẮT BUỘC**: Luôn sử dụng `python crawler/run_crawler.py` làm entry point duy nhất để chạy crawler trong dự án.
>
> **Tuyệt đối không chạy trực tiếp `scrapy runspider ... -o ...` từ terminal.** Lệnh gọi trực tiếp Scrapy với tùy chọn `-o` sẽ bỏ qua cơ chế kiểm tra collision (`ensure_output_path_available()`) của runner, có nguy cơ ghi đè hoặc append vào các raw snapshot đã tồn tại (như `pilot.jsonl`), vi phạm nguyên tắc raw data immutability và provenance của TV1.

---

### 5. Kiểm thử
```bash
python -m unittest discover tests
```
