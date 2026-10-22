# Data Quality Report – TV2 release v1

## 1. Phạm vi và kết quả phát hành

TV2 nhận 18 file JSONL snapshot: 10 file product và 8 file review từ 5 nguồn `cellphones`, `fptshop`, `hoanghamobile`, `tgdd`, `viettelstore`.

| Loại dữ liệu | Số dòng raw | Số dòng sau pipeline |
|---|---:|---:|
| Product/listing | 10.316 | 10.316 |
| Review cấp cao nhất | 15.805 | 15.805 |
| Reply | 108 | 108 |

Pipeline không xóa dòng, không điền missing và không sửa `data/raw/`. Bản phát hành đạt quality gates:

```text
status = PASSED
stages_completed = 11
final_release_ready = true
```

## 2. Các vấn đề phát hiện trong raw

### Missing và sentinel

- `total_sold_raw` thiếu: 8.412/10.316 product.
- Giá bằng 0: 1.752 product.
- Rating ngoài thang khai báo ở FPT: 104 product.
- Review thiếu hoặc không dùng được text: 936/15.805 review.
- Review thiếu thời gian: 489, toàn bộ thuộc Viettel Store.
- Attributes rỗng: 45 product.
- Mã nhận diện variant thiếu: 2.022 product.

Các giá trị `0`, `NULL`, chuỗi rỗng và “Liên hệ” được giữ riêng vì không có cùng ý nghĩa. Không có giá trị nào được tự động thay bằng trung vị, 0 hoặc giá trị suy đoán.

### Kiểu và định dạng

Giá được biểu diễn khác nhau giữa nguồn: số ở CellphoneS/TGDĐ/FPT Shop và chuỗi tiền tệ ở Viettel Store/Hoàng Hà Mobile. Availability cũng khác nhau: mã số, text tiếng Việt hoặc URL schema.org.

### Grain và liên kết

10.316 dòng product là listing/variant quan sát, không phải 10.316 model độc lập. Có 7.051 khóa parent theo `(source, category, parent_product_id_raw)`. Tất cả 15.805 review tìm thấy parent trong cùng source/category, nhưng nhiều review chỉ nối được ở parent level.

Nếu nối mỗi review với mọi listing của parent, số dòng giả định tăng lên 45.651. Vì vậy pipeline không dùng parent-only join cho phân tích cấp variant.

### Review metadata

Viettel Store có 489 review: tất cả thiếu text và ngày, đều rating 5 và có metadata payload. Đây là `metadata_suspect_candidate`, không phải nhãn review giả; các dòng vẫn được giữ.

## 3. Pipeline đã xử lý như thế nào

### Raw và Staging

Raw được khóa bằng SHA256, số dòng và `raw_record_id`. Staging giữ toàn bộ raw fields, thêm provenance, parse status và quality flags. Không có record bị drop.

### Silver v2

Silver v2 tạo các trường dẫn xuất:

- `price_vnd`, `original_price_vnd` và `OK/FAILED` parse status.
- `rating_norm`, `has_rating`, `review_count_normalized`.
- `availability_status`: `in_stock`, `out_of_stock`, `unknown`.
- `discount_rate` chỉ tính khi giá hiện tại và giá gốc hợp lệ.
- `review_text_normalized`, `review_usable`.
- Hardware candidates: RAM hiện tại/tối đa, pin mAh/Wh, công suất sạc và confidence.

Raw fields vẫn được giữ song song với fields dẫn xuất. Review Viettel và review thiếu text có `review_usable = false`, không bị xóa.

### Gold v2

Gold v2 tách theo grain:

- `dim_source_parents`: 7.051 parent theo source/category.
- `fact_listings`: 10.316 listing, gồm raw, provenance, flags và derived fields.
- `fact_reviews`: 15.805 review.
- `fact_review_replies`: 108 reply.

`source_parent_id` chỉ là khóa trong source/category; chưa có canonical product xuyên cửa hàng.

### Feature view

Để các nhóm không phải dùng toàn bộ bảng audit rộng, TV2 tạo:

`data/gold_v2/fact_listings_features.jsonl`

File này có 10.316 dòng và 31 tr??ng canonical cho phân tích listing. `fact_listings.jsonl` giữ bảng rộng để audit/truy nguyên.

## 4. Trước và sau chuẩn hóa

| Khía cạnh | Trước | Sau |
|---|---|---|
| Giá | nhiều kiểu số/chuỗi | `price_vnd` + parse status |
| Availability | mã số, text, URL khác nhau | 3 trạng thái chuẩn |
| Rating | raw theo source | `rating_norm` + `has_rating` |
| Review text | null/rỗng/trạng thái khác nhau | normalized text + `review_usable` |
| Attributes | object lồng nhau, tên key khác nhau | candidates có confidence, raw giữ nguyên |
| Định danh | mã nguồn theo từng website | source-scoped keys + raw record IDs |
| Duplicate | cần phân biệt text trùng và bản ghi trùng | kiểm tra khóa/exact duplicate; không tự gộp dòng |

## 5. Những gì không làm

- Không sửa hoặc ghi đè Raw.
- Không xóa/gộp bản ghi chỉ vì text hoặc tên giống nhau.
- Không điền missing.
- Không gán sentiment, fraud hoặc verified purchase.
- Không hợp nhất sản phẩm cùng tên giữa các cửa hàng.
- Không coi giá khác thường chắc chắn là lỗi.

## 6. Giới hạn và cách sử dụng

Giá trị parse thất bại, rating ngoài thang, availability `unknown` và hardware `AMBIGUOUS/FAILED` cần được nhóm sử dụng lọc hoặc phân tích riêng. `price_vnd` là giá quan sát tại snapshot, không phải dự báo giá tương lai. Review linkage ở variant level chưa hoàn chỉnh.

Nhóm sử dụng nên đọc thêm:

- `docs/data_contract_tv2_v1.md`
- `docs/feature_contracts_tv3_tv8.md`
- `docs/gold_handoff.md`
- `reports/quality_gate_report.json`
- `reports/release_manifest_tv2_v1.json`

## 7. Kết luận

TV2 đã chuyển 18 file raw thành pipeline có thể tái chạy, có Silver v2, Gold v2, feature view 31 trường, provenance và quality gates. Bản phát hành giữ nguyên số dòng và dữ liệu gốc, đồng thời làm rõ kiểu dữ liệu, missing, trạng thái bất thường và grain để các nhóm sau sử dụng đúng mục đích.
