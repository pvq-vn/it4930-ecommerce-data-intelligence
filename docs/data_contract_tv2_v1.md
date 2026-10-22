# Data contract TV2 – bản phát hành v1

## Phạm vi

Bản phát hành này cung cấp dữ liệu dẫn xuất từ 18 file JSONL raw cho các nhóm TV3–TV8. Raw là bất biến. Staging giữ trường raw, thêm kiểu dữ liệu và cờ chất lượng. Gold là các bảng theo đúng grain đã kiểm tra; chưa có hợp nhất sản phẩm giữa cửa hàng.

## Các bảng Gold

| Bảng | Grain | Khóa sử dụng |
|---|---|---|
| `dim_source_parents` | Một sản phẩm cha quan sát trong một `source/category` | `source_parent_id` |
| `fact_listings` | Một dòng listing/biến thể quan sát được | `listing_record_id` = `raw_record_id` |
| `fact_reviews` | Một review cấp cao nhất | `review_record_id` = `raw_record_id` |
| `fact_review_replies` | Một phản hồi trực tiếp của một review | `reply_record_id` |

## Quy tắc khóa

`source_parent_id` chỉ có nghĩa trong nguồn và danh mục tương ứng. Không dùng tên, SKU hoặc ID của một cửa hàng để khẳng định cùng sản phẩm ở cửa hàng khác. `variant_sku_raw`, `review_product_code_raw` và `variant_code_raw` là mã gốc/candidate; ý nghĩa phải được diễn giải theo source.

## Truy nguyên bắt buộc

`fact_listings` và `fact_reviews` phải giữ `raw_file`, `raw_line_number`, `raw_record_id`, `source`, `category`, `crawl_batch` và `pipeline_version`. Review reply giữ `parent_review_record_id` và `reply_index`.

## Cờ chất lượng

Cờ như `is_price_zero`, `is_price_relation_issue`, `is_rating_out_of_declared_range`, `is_review_text_unusable`, `review_metadata_suspect_candidate` chỉ mô tả quan sát. Người dùng Gold không được tự hiểu chúng là nhãn lỗi, fraud hoặc lý do xóa dòng.

## Trường chuẩn hóa trong Silver v2

- Product: `price_vnd`, `price_parse_status`, `original_price_vnd`, `original_price_parse_status`, `availability_status` (`in_stock`, `out_of_stock`, `unknown`), `rating_norm`, `has_rating` (`rating_raw = 0` ???c xem l? ch?a c? rating), `review_count_normalized`, `discount_rate`, `discount_status`, `is_price_missing`, `total_sold_normalized`.
- Hardware candidates: `installed_ram_gb`, `max_ram_gb`, `battery_mah`, `battery_wh`, `charger_watt`, `hardware_extraction_confidence`.
- Review: `review_text_normalized`, `review_text_status`, `review_usable`, `review_time_status`.

Các trường trên là giá trị dẫn xuất; trường raw tương ứng vẫn được giữ. `review_usable = false` cho review Viettel Store và review không có text hữu ích. `review_count_normalized` không được điền cho FPT Shop và Hoàng Hà Mobile.

## Kiểm tra nghiệm thu

- 18/18 file raw đọc được, không có JSON error.
- Raw không bị sửa; SHA256 và số dòng nằm trong `reports/release_manifest_tv2_v1.json`.
- Gold có 7.051 source-scoped parents, 10.316 listings, 15.805 reviews và 108 replies.
- Khóa Gold duy nhất; mọi review hiện có parent trong cùng `source/category`.
- Nối review với toàn bộ listing của parent là one-to-many và không được dùng cho join cấp biến thể.

## Giới hạn

Bản v1 chưa phải dữ liệu đã làm sạch hoàn toàn, chưa có canonical product giữa các cửa hàng, chưa có nhãn sentiment/fraud và chưa dự báo giá tương lai. Mọi biến đổi riêng cho mô hình phải tạo bảng dẫn xuất mới, giữ khóa truy nguyên và không ghi đè Gold v1.
