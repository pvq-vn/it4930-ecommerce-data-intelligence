# Feature contract cho TV3–TV8

Gold v2 chứa raw fields, provenance, quality flags và fields dẫn xuất. Các nhóm sử dụng **không nên lấy toàn bộ cột làm feature**. Tài liệu này quy định tập trường canonical theo từng bài toán.

## 1. Quy ước tên canonical

| Mục đích | Trường canonical | Trường cũ/alias cần tránh dùng mới |
|---|---|---|
| Giá hiện tại | `price_vnd` | `price_value`, `price_normalized` |
| Giá gốc | `original_price_vnd` | `original_price_value`, `original_price_normalized` |
| Rating | `rating_norm` | `rating_value`, `rating_normalized` |
| Trạng thái availability | `availability_status` | Không dùng `availability_raw` làm feature trực tiếp |
| Text review | `review_text_normalized` | `review_text_raw` cho NLP trực tiếp |
| ID listing | `listing_record_id` | `product_id_raw` nếu cần khóa quan sát ổn định |
| ID parent theo source | `source_parent_id` | Không coi là canonical product toàn thị trường |

Các alias hiện vẫn được giữ để tương thích và truy nguyên; pipeline mới nên dùng cột canonical.

## 2. Nhóm trường dùng chung

### Được dùng để phân nhóm/kiểm tra

`source`, `category`, `seller_raw`, `brand_raw`, `crawl_batch`, `crawl_time`.

### Được dùng làm feature số khi hợp lệ

`price_vnd`, `original_price_vnd`, `discount_rate`, `rating_norm`, `review_count_normalized`, `total_sold_raw` sau khi xử lý trạng thái riêng.

### Chỉ dùng để lọc/đánh giá chất lượng

`price_parse_status`, `original_price_parse_status`, `rating_normalized_status`, `has_rating`, `discount_status`, `is_price_zero`, `is_price_missing`, `is_price_relation_issue`, `is_review_count_missing`, `hardware_extraction_confidence`, `review_usable`.

### Chỉ dùng để truy nguyên

`raw_file`, `raw_line_number`, `raw_record_id`, `raw_payload`, `product_id_raw`, `parent_product_id_raw`, `variant_sku_raw`, `listing_record_id`, `source_parent_id`.

## 3. Contract theo nhóm

### TV3 – EDA

Tập tối thiểu: `source`, `category`, `brand_norm`, `seller_raw`, `price_vnd`, `original_price_vnd`, `discount_rate`, `rating_norm`, `review_count_normalized`, `availability_status`, `crawl_batch`.

Phải báo cáo missing/flag theo source. Không tính trung bình rating bằng cách coi `has_rating = false` là rating 0.

### TV4 – Graph

Node/edge tối thiểu: `source_parent_id`, `listing_record_id`, `seller_raw`, `category`, `source`.

Graph hiện phản ánh quan hệ trong source/category. Chưa được tạo một node canonical xuyên cửa hàng nếu chưa có entity resolution.

### TV5 – Price prediction

Candidate features: `category`, `brand_norm`, `seller_raw`, `rating_norm`, `review_count_normalized`, `discount_rate`, `availability_status`, `installed_ram_gb`, `max_ram_gb`, `battery_mah`, `battery_wh`, `charger_watt`, `cpu_norm`, `gpu_norm`, `storage_gb`, `color_norm`, `screen_size_inch`, `operating_system_norm`, `camera_mp`, `display_type_norm`, `network_type_norm`.

Target mặc định: `price_vnd` tại snapshot. Đây là ước lượng giá quan sát, không phải dự báo giá tương lai. Không dùng `raw_payload`, `raw_file`, ID hoặc `crawl_time` làm feature nếu chưa có thiết kế chống leakage.

### TV6 – Review NLP

Dùng `fact_reviews`: `review_text_normalized`, `rating_raw`, `review_time_raw`, `source_parent_id`, `source`, `category`, `review_usable`.

`review_usable = false` phải được loại hoặc phân tích riêng theo policy NLP. Không coi review có text trùng là review giả.

### TV7 – Anomaly detection

Candidate features: `price_vnd`, `original_price_vnd`, `discount_rate`, `rating_norm`, `review_count_normalized`, `availability_status`, `source`, `category`.

Các cờ chất lượng được dùng làm evidence/segment, không phải nhãn fraud đã xác minh. `price_parse_status != OK` không được đưa thẳng vào mô hình số.

### TV8 – Evaluation/Explainability

Mọi prediction/anomaly/review output phải giữ `listing_record_id` hoặc `review_record_id`, `source`, `category`, `crawl_batch` và phiên bản pipeline để truy nguyên mẫu.

## 4. Nguyên tắc tạo view phân tích

Mỗi nhóm nên tạo một view/table dẫn xuất riêng từ Gold v2, chỉ chọn trường trong contract của nhóm. Không xóa hoặc ghi đè Gold v2. View phải lưu lại:

- phiên bản pipeline;
- số dòng đầu vào/đầu ra;
- tiêu chí lọc `review_usable` hoặc parse status;
- tỷ lệ missing sau khi chọn feature;
- khóa truy nguyên.

## 5. Những điều chưa được tự động quyết định

- Không coi mọi `price_vnd = 0` là lỗi nếu chưa có policy của source.
- Không gộp `brand_raw` thành brand chuẩn nếu chưa có mapping dictionary được duyệt.
- Không dùng `variant_sku_raw` làm khóa toàn cục.
- Không dùng `rating_raw > 5` như nhãn gian lận.
