# IT4930 - E-commerce Data Intelligence

## TV1: Web Crawling & Data Acquisition (Thế Giới Di Động Pilot)

Hệ thống crawler thực tế cho sàn thương mại điện tử Thế Giới Di Động (TGDĐ), phục vụ giai đoạn thu thập dữ liệu gốc (Raw Data) cho bài toán dự đoán giá sản phẩm công nghệ (Laptop & Smartphone).

### 1. Cấu trúc thư mục
- `crawler/tgdd/items.py`: Schema dữ liệu thô `TechProductRawItem` theo chuẩn TV1.
- `crawler/tgdd/base_spider.py`: Spider cơ sở (`TgddBaseSpider`) tích hợp cơ chế request API, phân trang, trích xuất Schema.org JSON-LD và fallback DOM.
- `crawler/tgdd/tgdd_laptop_spider.py`: Spider danh mục Laptop (`/laptop`).
- `crawler/tgdd/tgdd_smartphone_spider.py`: Spider danh mục Smartphone (`/dtdd`).
- `crawler/run_crawler.py`: CLI script điều phối chạy crawler.
- `data/raw/tgdd/laptop/pilot.jsonl`: Dữ liệu pilot 50 Laptop dạng JSONL.
- `data/raw/tgdd/smartphone/pilot.jsonl`: Dữ liệu pilot 50 Smartphone dạng JSONL.
- `tests/test_tgdd_crawler.py`: Bộ kiểm thử tự động (Unit tests & file validation).

### 2. Cài đặt môi trường
```bash
pip install -r requirements.txt
```

### 3. Thực thi Crawler
#### Chạy toàn bộ Pilot (50 Laptop + 50 Smartphone):
```bash
python crawler/run_crawler.py --category all --limit 50
```

#### Chạy riêng từng danh mục:
```bash
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50
```

#### Hoặc chạy trực tiếp qua Scrapy CLI:
```bash
scrapy runspider crawler/tgdd/tgdd_laptop_spider.py -a max_products=50 -o data/raw/tgdd/laptop/pilot.jsonl
scrapy runspider crawler/tgdd/tgdd_smartphone_spider.py -a max_products=50 -o data/raw/tgdd/smartphone/pilot.jsonl
```

### 4. Kiểm thử
```bash
python -m unittest discover tests
```
