# Phát hiện bất thường giá sản phẩm

- Đầu vào: `data/processed/products_processed.jsonl` (10,316 bản ghi).
- Phương pháp: IQR trên log(giá), so sánh laptop/smartphone riêng; dùng nhóm thương hiệu khi có ít nhất 20 bản ghi, nếu không dùng nhóm danh mục.
- Isolation Forest chạy riêng cho laptop/smartphone với 300 cây, `contamination=0.02` và `random_state=42`; mô hình dùng log giá, cấu hình, cờ thiếu và tần suất của đặc trưng phân loại.
- Giá thấp hơn ngưỡng tham chiếu EDA (laptop 3 triệu, smartphone 1 triệu) được gắn cờ xem xét.
- Các cờ chỉ là tín hiệu rà soát; không xóa bản ghi và không khẳng định mọi giá trị bị gắn cờ là lỗi.
- Giá hợp lệ: 8,548; cờ tổng hợp: 468; mức extreme: 95.

## Tổng hợp theo phương pháp

| method             |   flagged |
|:-------------------|----------:|
| EDA rule           |       234 |
| IQR                |       156 |
| Isolation Forest   |       172 |
| Combined union     |       468 |
| At least 2 methods |        91 |

## Tổng hợp theo danh mục

| category_group   | price_status           | anomaly_severity   |   records |
|:-----------------|:-----------------------|:-------------------|----------:|
| laptop           | missing_or_unparseable | none               |         2 |
| laptop           | non_positive           | none               |       650 |
| laptop           | valid                  | extreme            |        11 |
| laptop           | valid                  | none               |      4067 |
| laptop           | valid                  | review             |       144 |
| smartphone       | missing_or_unparseable | none               |        14 |
| smartphone       | non_positive           | none               |      1102 |
| smartphone       | valid                  | extreme            |        84 |
| smartphone       | valid                  | none               |      4013 |
| smartphone       | valid                  | review             |       229 |

## Cách đọc kết quả

`rule_flag`, `iqr_flag` và `isolation_forest_flag` cho biết phương pháp nào đã gắn cờ. `isolation_score` càng lớn thì tổ hợp đặc trưng càng khác thường trong danh mục. `methods_agree >= 2` được ưu tiên kiểm tra và xếp mức `extreme`; cờ IQR vượt 3 IQR cũng là `extreme`. `combined_flag` là hợp của ba phương pháp.

## Hạn chế

Isolation Forest là mô hình không giám sát và `contamination=0.02` buộc mô hình chọn khoảng 2% bản ghi giá hợp lệ trong mỗi danh mục. Cờ này không phải xác suất lỗi hoặc gian lận. IQR và Isolation Forest đều có thể đánh dấu flagship hay sản phẩm hiếm hợp lệ. Cần đối chiếu raw data/trang nguồn và rà soát thủ công trước khi lọc. Nhóm dự đoán có thể dùng các cờ để so sánh độ nhạy giữa giữ nguyên dữ liệu, chỉ bỏ lỗi đã xác minh và bỏ toàn bộ anomaly.
