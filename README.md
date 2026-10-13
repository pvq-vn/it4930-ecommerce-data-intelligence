# IT4930 - E-commerce Data Intelligence

## TV1: Web Crawling & Data Acquisition (Thế Giới Di Động Pilot)

Hệ thống crawler thực tế cho sàn thương mại điện tử Thế Giới Di Động (TGDĐ), phục vụ giai đoạn thu thập dữ liệu gốc (Raw Data) cho bài toán dự đoán giá sản phẩm công nghệ (Laptop & Smartphone).

### 1. Cấu trúc thư mục
- `crawler/tgdd/items.py`: Schema dữ liệu thô `TechProductRawItem` theo chuẩn TV1.
- `crawler/tgdd/base_spider.py`: Spider cơ sở (`TgddBaseSpider`) tích hợp cơ chế request API, phân trang, trích xuất Schema.org JSON-LD và fallback DOM, kiểm soát duplicate request và theo dõi observability.
- `crawler/tgdd/tgdd_laptop_spider.py`: Spider danh mục Laptop (`/laptop`).
- `crawler/tgdd/tgdd_smartphone_spider.py`: Spider danh mục Smartphone (`/dtdd`).
- `crawler/run_crawler.py`: CLI script điều phối chạy crawler, hỗ trợ tạo raw snapshot bất biến (immutable snapshots).
- `data/raw/tgdd/laptop/`: Thư mục chứa các raw snapshots Laptop (`pilot.jsonl`, `<batch_id>.jsonl`).
- `data/raw/tgdd/smartphone/`: Thư mục chứa các raw snapshots Smartphone (`pilot.jsonl`, `<batch_id>.jsonl`).
- `tests/test_tgdd_crawler.py`: Bộ kiểm thử tự động (Unit tests, duplicate control, observability, runner và validation pilot data).

### 2. Nguyên tắc & Chính sách Thu thập (Politeness)
- **Robots.txt**: `www.thegioididong.com/robots.txt` quy định `User-agent: *`, `Crawl-delay: 5`. Hai danh mục `/laptop` và `/dtdd` không nằm trong danh sách `Disallow`.
- **API Domain**: `api.thegioididong.com/robots.txt` trả về HTTP 404 (Not Found), không suy diễn policy riêng cho API. Hệ thống crawler áp dụng cấu hình conservative tuân thủ nghiêm ngặt chính sách của trang www:
  - `ROBOTSTXT_OBEY = True`
  - `DOWNLOAD_DELAY = 5.0` (giây)
  - `CONCURRENT_REQUESTS = 1` (tuần tự hóa hoàn toàn)
  - `CONCURRENT_REQUESTS_PER_DOMAIN = 1`
  - `AUTOTHROTTLE_ENABLED = True` (start delay 5.0s, target concurrency 1.0)
- **Kiểm soát trùng lặp HTTP**: Bỏ `dont_filter=True`, tận dụng `RFPDupeFilter` của Scrapy để tránh tạo duplicate HTTP requests (phân biệt qua POST body ở listing và URL ở detail). Không thực hiện semantic deduplication tại TV1 (thuộc phạm vi TV2).
- **Immutable Raw Snapshots**: Mỗi đợt crawl tạo một file snapshot riêng theo timestamp/batch_id (ví dụ: `20261013_081500.jsonl`). Tuyệt đối không xóa hay ghi đè snapshot cũ.
- **Bảo toàn dữ liệu gốc**: Raw layer giữ nguyên dữ liệu gốc (số nguyên, chuỗi raw, cấu trúc thuộc tính), không thực hiện normalize/cleaning ngữ nghĩa.

### 3. Cài đặt môi trường
```bash
pip install -r requirements.txt
```

### 4. Thực thi Crawler
#### Chạy crawl tạo snapshot bất biến (mặc định):
```bash
# Chạy cả 2 danh mục (mỗi danh mục tạo 1 snapshot riêng theo timestamp):
python crawler/run_crawler.py --category all --limit 50

# Chạy riêng từng danh mục:
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50
```

#### Chỉ định file đầu ra hoặc batch_id thủ công (chỉ áp dụng khi chọn 1 danh mục):
```bash
python crawler/run_crawler.py --category laptop --limit 50 --output data/raw/tgdd/laptop/custom_snapshot.jsonl
python crawler/run_crawler.py --category laptop --limit 50 --batch-id 20261013_081500
```

#### Hoặc chạy trực tiếp qua Scrapy CLI:
```bash
scrapy runspider crawler/tgdd/tgdd_laptop_spider.py -a max_products=50 -a batch_id=20261013_081500 -o data/raw/tgdd/laptop/20261013_081500.jsonl
scrapy runspider crawler/tgdd/tgdd_smartphone_spider.py -a max_products=50 -a batch_id=20261013_081900 -o data/raw/tgdd/smartphone/20261013_081900.jsonl
```

### 5. Kiểm thử
```bash
python -m unittest discover tests
```
