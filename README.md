# IT4930 - E-commerce Data Intelligence

## TV1: Web Crawling & Data Acquisition (Multi-Source Architecture)

Hệ thống crawler thực tế thu thập dữ liệu gốc (Raw Data) cho bài toán phân tích và dự đoán giá sản phẩm công nghệ trong đúng 2 danh mục mục tiêu của project: **Laptop** và **Smartphone**.

> **Phạm vi (Scope)**:
>
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
      _(Khi gọi CLI tới các nguồn chưa triển khai, runner sẽ báo lỗi rõ ràng và từ chối chạy, tuyệt đối không âm thầm fallback sang nguồn khác)._

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

## TV2 — Data Quality & Integration

TV2 chuyển dữ liệu raw từ crawler thành dữ liệu đã chuẩn hóa, có kiểm tra chất lượng và giữ khả năng truy nguyên.

### Pipeline

```text
data/raw/
    ↓
data/staging/
    ↓
data/silver_v2/
    ↓
data/gold_v2/
    ↓
data/processed/
```

Chạy pipeline:

```bash
py src/run_tv2_pipeline.py
```

Kết quả thành công:

```json
{
    "status": "PASSED",
    "stages_completed": 11,
    "final_release_ready": true
}
```

### Dữ liệu bàn giao

Các thành viên TV3–TV8 sử dụng:

```text
data/processed/products_processed.jsonl
data/processed/reviews_processed.jsonl
```

`products_processed.jsonl` có 10.316 listing và 30 trường, gồm tên sản phẩm, `brand_norm`, giá, rating, availability, `total_sold_normalized` và các thuộc tính phần cứng.

`reviews_processed.jsonl` có 15.805 review và 14 trường, gồm tên sản phẩm, `rating_raw`, `rating_norm`, nội dung review và `review_usable`.

Trong dữ liệu sản phẩm:

```text
rating_raw = 0
rating_norm = null
has_rating = false
```

### Google Drive

Bộ dữ liệu Gold v2 và hai file processed được lưu tại:

[TV2 Data Handoff trên Google Drive](https://drive.google.com/drive/folders/1NtfrhPY44LnNFrI5_mLcyw2r-tcK0dlc?usp=drive_link)

Bộ bàn giao gồm:

- `processed/products_processed.jsonl`
- `processed/reviews_processed.jsonl`
- `gold_v2/` với 5 file Gold và README hướng dẫn.

### Các bước xử lý chính

- Giữ nguyên dữ liệu raw, không sửa hoặc ghi đè.
- Gắn mã truy nguyên cho từng bản ghi.
- Chuẩn hóa giá, rating, availability và thương hiệu.
- Chuẩn hóa tên sản phẩm và loại bỏ một số hậu tố marketing chắc chắn.
- Bóc tách CPU, GPU, RAM, storage, pin, màn hình và camera.
- Chuẩn hóa `total_sold_raw` thành `total_sold_normalized`.
- Giữ nguyên giá trị thiếu, không tự động điền dữ liệu.
- Kiểm tra khóa, số dòng, schema và liên kết sản phẩm–review.

### Tài liệu TV2

- `docs/data_contract_tv2_v1.md`
- `docs/data_field_decision_matrix.md`
- `docs/feature_contracts_tv3_tv8.md`
- `docs/data_quality_report_tv2_v1.md`
- `docs/gold_handoff.md`
- `docs/pipeline_execution_v1.md`
