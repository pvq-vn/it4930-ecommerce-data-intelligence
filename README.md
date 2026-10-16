# IT4930 - E-commerce Data Intelligence

## TV1: Web Crawling & Data Acquisition (Multi-Source Architecture)

Hệ thống crawler thực tế thu thập dữ liệu gốc (Raw Data) cho bài toán phân tích và dự đoán giá sản phẩm công nghệ trong đúng 2 danh mục mục tiêu của project: **Laptop** và **Smartphone**.

> **Phạm vi (Scope)**:
> - Chỉ crawl dữ liệu cho 2 danh mục: **Laptop** và **Smartphone**.
> - Không thực hiện chuẩn hóa, làm sạch (cleaning) hay khử trùng ngữ nghĩa (semantic deduplication) tại raw layer (các tác vụ này thuộc TV2).
> - Raw Contract bất biến: **Product = 25 fields**, **Review = 19 fields**.
> - An toàn dữ liệu thô: Raw snapshots đã crawl là bất biến (immutable), không ghi đè, không append.

---

### 1. Nguồn Dữ Liệu (Source Support)

Hệ thống crawler thiết kế theo mô hình Registry mở rộng (`SOURCE_REGISTRY` trong `crawler/run_crawler.py`), phân định rõ ràng giữa nguồn đã triển khai và nguồn dự kiến tương lai:

- **Nguồn hiện hành (Implemented)**:
  - `tgdd`: Thế Giới Di Động (`crawler/tgdd/`)
  - `fptshop`: FPT Shop (`crawler/fptshop/`)
  - `cellphones`: CellphoneS (`crawler/cellphoneS/`)
- **Nguồn kế hoạch/tương lai (Planned / Future)**:
  - `viettelstore`: Viettel Store (`implemented=False`)
  - `hoanghamobile`: Hoàng Hà Mobile (`implemented=False`)
  *(Khi gọi CLI tới các nguồn chưa triển khai, runner sẽ báo lỗi rõ ràng và từ chối chạy, tuyệt đối không âm thầm fallback sang nguồn khác).*

---

### 2. Cấu trúc thư mục
- `crawler/tgdd/`: Spiders và items cho Thế Giới Di Động.
- `crawler/fptshop/`: Spiders và items cho FPT Shop.
- `crawler/cellphoneS/`: Spiders và items cho CellphoneS (GraphQL + SSR detail/review).
- `crawler/run_crawler.py`: CLI Runner tập trung điều phối các nguồn với `RunnerLock` đảm bảo chống chạy đồng thời và kiểm soát an toàn snapshot bất biến.
- `data/raw/<source>/<category>/`: Thư mục lưu trữ raw snapshots (sản phẩm: `*.jsonl`, đánh giá: `*_reviews.jsonl`).
- `tests/`: Bộ kiểm thử toàn diện (contract, crawler, runner lock, source routing, an toàn raw data).

---

### 3. Nguyên tắc Thu thập (Politeness & Concurrency Safety)
- **Robots.txt & Rate Limiting**:
  - Tuân thủ robots.txt và giới hạn rate limiting theo từng sàn.
  - Chạy tuần tự an toàn (`CONCURRENT_REQUESTS = 1`, AutoThrottle, Conservative download delay).
  - Không bypass anti-bot, không sử dụng luồng ngầm gây quá tải hệ thống nguồn.
- **Tiến trình an toàn (RunnerLock)**:
  - Cơ chế lock đơn tiến trình atomic (`O_EXCL`), gắn liền với start time/PID protection.
  - Giữ lock xuyên suốt chuỗi crawl khi chạy `--category all` hoặc `--source all`.
  - Từ chối khởi động bất kỳ Scrapy subprocess nào nếu lock đang bị giữ bởi tiến trình khác.
- **Chống trùng lặp HTTP & Ngữ nghĩa**:
  - Tận dụng Scrapy RFPDupeFilter cho HTTP requests (không dùng `dont_filter=True` tùy tiện).
  - Kiểm soát trùng lặp ngữ nghĩa ở cấp độ crawler (`seen_parent_ids`, `seen_review_ids`, `seen_page_signatures`).
- **Immutable Raw Snapshots**:
  - Mỗi mẻ crawl tạo snapshot mới định danh theo `batch_id` (hoặc timestamp).
  - Từ chối chạy nếu file snapshot đích đã tồn tại (`ensure_output_path_available`).

---

### 4. Cài đặt môi trường
```bash
pip install -r requirements.txt
```

---

### 5. Thực thi Crawler (`crawler/run_crawler.py`)

Entry point duy nhất để điều phối crawler là `crawler/run_crawler.py`.

#### A. Chạy riêng từng nguồn (Source Isolation):
```bash
# Chỉ chạy CellphoneS:
python crawler/run_crawler.py --source cellphones --category laptop --limit 50
python crawler/run_crawler.py --source cellphones --category smartphone --limit 50
python crawler/run_crawler.py --source cellphones --category all --limit 50

# Chỉ chạy Thế Giới Di Động:
python crawler/run_crawler.py --source tgdd --category laptop --limit 50
python crawler/run_crawler.py --source tgdd --category smartphone --limit 50
python crawler/run_crawler.py --source tgdd --category all --limit 50

# Chỉ chạy FPT Shop:
python crawler/run_crawler.py --source fptshop --category smartphone --limit 50
```

#### B. Chạy toàn bộ các nguồn đã triển khai:
```bash
# Chạy tuần tự tất cả các nguồn đã triển khai (tgdd, fptshop, cellphones):
python crawler/run_crawler.py --source all --category all --limit 50
```

#### C. Chế độ Full Crawl (`--full`):
```bash
# Full crawl CellphoneS Laptop:
python crawler/run_crawler.py --source cellphones --category laptop --full
```
> **Lưu ý**: Tùy chọn `--full` và `--limit` loại trừ lẫn nhau (mutually exclusive).

#### D. Chỉ định Output hoặc Batch ID tùy chỉnh:
Tùy chọn `--output` chỉ hợp lệ khi crawl chính xác 1 nguồn và 1 danh mục:
```bash
python crawler/run_crawler.py --source cellphones --category laptop --limit 50 --output data/raw/cellphones/laptop/custom_run.jsonl
```

---

### 6. Kiểm thử Tự động
Tất cả các unit tests không gọi mạng ngoài, không khởi chạy Scrapy thật, và không ghi dữ liệu giả mạo vào `data/raw`:
```bash
python -m unittest discover tests -v
```

