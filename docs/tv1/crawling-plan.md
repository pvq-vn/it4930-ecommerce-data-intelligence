# Kế hoạch & Kiến trúc Crawler Thế Giới Di Động (TV1 - Pilot)

## 1. Nguồn Dữ Liệu
- **Laptop**: `https://www.thegioididong.com/laptop`
- **Smartphone**: `https://www.thegioididong.com/dtdd` *(lưu ý: endpoint cũ `/dien-thoai` trả về HTTP 404)*

## 2. Cơ Chế Thu Thập (Evidence-Based)
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
- **Cấu trúc Response**: JSON `data.products[]`. Không trả HTML fragment `listproducts` như giả định cũ.
- **Trường lấy từ Listing**: `product_id_raw`, `product_name_raw`, `product_url_raw`, `price_raw`, `original_price_raw`, `seller_raw`, `rating_raw`, `review_count_raw`, `brand_raw`, `total_sold_raw`, `sku_raw`.

### B. Chi tiết sản phẩm (Detail)
- **Phương thức**: `GET https://www.thegioididong.com/<url>`
- **Trích xuất thông số kỹ thuật (`attributes_raw`)**:
  - Ưu tiên: Schema.org JSON-LD (`@type` là `Product` hoặc `ProductGroup`) -> lấy mảng `additionalProperty` gồm các cặp `{name, value}` chuẩn.
  - Fallback: HTML DOM `<section>` chứa "Thông số kỹ thuật".
  - Giữ nguyên tên thuộc tính và giá trị gốc, không normalize.

## 3. Cấu Trúc Mã Nguồn
```text
crawler/
    run_crawler.py              # CLI runner script
    tgdd/
        __init__.py
        items.py                # TechProductRawItem schema
        base_spider.py          # TgddBaseSpider (logic chung, header, pagination, parsing)
        tgdd_laptop_spider.py   # TgddLaptopSpider
        tgdd_smartphone_spider.py # TgddSmartphoneSpider
data/
    raw/
        tgdd/
            laptop/pilot.jsonl  # 50 records laptop
            smartphone/pilot.jsonl # 50 records smartphone
tests/
    test_tgdd_crawler.py        # Unit tests & validation
```

## 4. Hướng Dẫn Chạy
### Chạy toàn bộ Pilot (50 Laptop + 50 Smartphone):
```bash
python crawler/run_crawler.py --category all --limit 50
```

### Chạy riêng từng danh mục:
```bash
python crawler/run_crawler.py --category laptop --limit 50
python crawler/run_crawler.py --category smartphone --limit 50
```

### Hoặc chạy trực tiếp qua Scrapy CLI:
```bash
scrapy runspider crawler/tgdd/tgdd_laptop_spider.py -a max_products=50 -o data/raw/tgdd/laptop/pilot.jsonl
scrapy runspider crawler/tgdd/tgdd_smartphone_spider.py -a max_products=50 -o data/raw/tgdd/smartphone/pilot.jsonl
```

### Chạy Unit Tests:
```bash
python -m unittest discover tests
```
