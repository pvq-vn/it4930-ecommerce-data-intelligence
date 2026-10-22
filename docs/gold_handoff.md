# Quy tắc bàn giao Gold cho TV3–TV8

Tài liệu này mô tả cách sử dụng các bảng Gold hiện tại. Gold là lớp dẫn xuất có truy nguyên từ Staging; không phải kết quả hợp nhất sản phẩm toàn thị trường.

## 1. Bảng nào dành cho ai?

| Nhóm | Bảng nên dùng | Cấp dữ liệu | Ghi chú |
|---|---|---|---|
| TV3 – EDA | `dim_source_parents`, `fact_listings` | Cha và listing | So sánh giá theo nguồn cần giữ `source`; không gộp tên giống nhau giữa cửa hàng. |
| TV4 – Graph | `dim_source_parents`, `fact_listings` | Seller–listing–category | Dùng `source_parent_id` làm node sản phẩm theo nguồn; chưa có canonical product giữa cửa hàng. |
| TV5 – Price Prediction | `fact_listings` | Listing/biến thể | Target hiện tại là giá quan sát (`price_value`), không phải giá tương lai. Loại hoặc phân tích riêng cờ giá theo mục tiêu nghiên cứu. |
| TV6 – Review NLP | `fact_reviews`, `dim_source_parents` | Review–sản phẩm cha | Giữ review thiếu text để thống kê chất lượng; chỉ dùng review có text cho NLP sau khi ghi rõ tiêu chí chọn. |
| TV7 – Anomaly Detection | `fact_listings`, cờ chất lượng | Listing/snapshot | Cờ là dấu hiệu cần xem xét, không phải nhãn lỗi hay fraud đã xác minh. |
| TV8 – Evaluation | Kết quả và khóa từ TV3–TV7 | Theo bài toán | Luôn giữ `source`, `category`, `crawl_batch` và ID để truy ngược mẫu đánh giá. |

## 2. Khóa được phép dùng

- `source_parent_id`: khóa sản phẩm cha trong **một source và category**. Không dùng để tuyên bố hai cửa hàng bán cùng một sản phẩm là cùng thực thể.
- `listing_record_id`: ID của đúng dòng listing quan sát được, tương ứng với `raw_record_id`.
- `review_record_id`: ID của đúng review cấp cao nhất.
- `reply_record_id`: ID của phản hồi con, gắn với `parent_review_record_id` và `reply_index`.
- `parent_product_id_raw`, `variant_sku_raw`, `review_product_code_raw`: mã gốc/candidate; phải giữ phạm vi nguồn khi nối.

Không nối `fact_reviews` với `fact_listings` chỉ bằng sản phẩm cha nếu cần một dòng review–listing. Nối như vậy là one-to-many và tạo 45.651 dòng giả định từ 15.805 review. Ở cấp biến thể, chỉ dùng khi `variant_link_status = VARIANT_MATCHED`; các trạng thái khác phải giữ nguyên và báo cáo riêng.

## 3. Quy tắc diễn giải

1. Không gọi số dòng listing là số mẫu máy độc lập.
2. Không coi `is_price_zero`, `is_rating_out_of_declared_range` hoặc `review_metadata_suspect_candidate` là kết luận cuối cùng.
3. Không xóa review vì text ngắn, trùng text hoặc thiếu ngày; dùng cờ để lọc theo mục tiêu và báo cáo tỷ lệ lọc.
4. Không tự động tính discount khi điều kiện giá chưa thỏa mãn.
5. Khi tạo biến đổi mới, phải giữ ID truy nguyên, mã nguồn, danh mục, đợt crawl và phiên bản code.

## 4. Kiểm tra tối thiểu trước khi sử dụng

- Đọc `reports/gold_v2_quality_report.json` và `reports/gold_v2_validation_report.json`.
- Xác nhận số dòng đầu vào và đầu ra không thay đổi ngoài phép chiếu được mô tả.
- Kiểm tra phân bố `variant_link_status` trước khi phân tích cấp biến thể.
- Báo cáo số mẫu theo `source/category`, không chỉ một tổng chung.
- Khi phát hiện bất thường, trích dẫn `raw_file`, `raw_line_number` và `raw_record_id`.

## 5. Giới hạn hiện tại

Gold chưa có `canonical_product_id`, chưa có entity resolution giữa các cửa hàng, chưa có nhãn fraud/sentiment và chưa phải dataset đã làm sạch hoàn toàn. Các quyết định lọc hoặc chuẩn hóa phục vụ từng bài toán phải được ghi ở pipeline của nhóm sử dụng và không được ghi đè các bảng Gold hiện tại.
