# Phát hiện bất thường

Bản thảo nội dung Phần 9 của báo cáo đồ án nằm tại [`report_section_9.md`](report_section_9.md).

Chạy từ thư mục gốc dự án:

```powershell
python src/anomaly_detection/detect_price_anomalies.py
```

Chương trình đọc `data/processed/products_processed.jsonl` và tạo:

- `outputs/anomaly_flags.csv`: cờ theo từng listing, nhóm đối chiếu và lý do.
- `outputs/anomaly_summary.csv`: số lượng theo danh mục, trạng thái giá và mức cờ.
- `outputs/anomaly_method_summary.csv`: số lượng cờ của từng phương pháp và phần giao nhau.
- `outputs/anomaly_report.md`: phương pháp, thống kê theo loại bất thường, biểu đồ và kết quả độ nhạy TV5.
- `outputs/anomaly_price_vs_ram.png`: log giá theo RAM, tô màu theo mức độ bất thường.

`outputs/tv5_sensitivity.csv` lưu số liệu S4/S5a/S5b trích từ mục TV5.B của báo cáo kiểm toán. Chương trình đọc bảng này để đưa vào báo cáo, không huấn luyện lại mô hình TV5. Các thư viện cần thiết gồm NumPy, pandas, scikit-learn, Matplotlib và tabulate.

Giá thiếu hoặc không dương được ghi trạng thái riêng. IQR và Isolation Forest chỉ xét giá dương, tách laptop và smartphone. IQR dùng log giá và nhóm danh mục + thương hiệu khi thương hiệu có ít nhất 20 bản ghi giá dương trong danh mục. Các thương hiệu ít mẫu được gộp theo danh mục. Vi phạm biên 3 IQR hoặc có ít nhất hai phương pháp đồng thuận được xếp mức `extreme`; các bản ghi có cờ còn lại là `review`.

`rule_flag` bao gồm giá dưới sàn EDA (3 triệu cho laptop, 1 triệu cho smartphone), máy bàn Apple lọt vào laptop, màn hình ngoài khoảng 10–20 inch với laptop hoặc 3–11 inch với smartphone, ổ laptop dưới 32 GB và giá tiền trong `network_type_norm`. Quy tắc phi giá áp dụng cả khi thiếu giá.

Sau baseline, Isolation Forest chạy riêng cho laptop và smartphone. Mô hình dùng log giá, thông số phần cứng, cờ thiếu dữ liệu và tần suất xuất hiện của các đặc trưng phân loại. Cấu hình mặc định gồm 300 cây, `contamination=0.02` và `random_state=42`. Tần suất được dùng thay cho mã số thứ tự để không tạo quan hệ giả như Apple < Dell < Lenovo.

File chi tiết tách riêng `rule_flag`, `iqr_flag`, `isolation_forest_flag`, `isolation_score`, `methods_agree` và `combined_flag`. Điểm `isolation_score` càng lớn thì record càng khác thường theo mô hình. `combined_flag` là hợp của ba phương pháp; các record được ít nhất hai phương pháp đồng thời gắn cờ được ưu tiên rà soát.

| `anomaly_type` | `recommended_action` |
|---|---|
| `low_price_or_category_noise` | `filter_before_modeling` |
| `hardware_spec_error` | `verify_or_correct_specs` |
| `rare_valid_flagship` | `keep_with_log_transform` |
| `spec_price_mismatch_review` | `sensitivity_check` |
| `none` | `none` |

Nếu nhiều loại cùng khớp, ưu tiên lỗi giá thấp/sai danh mục rồi tới lỗi thông số. Flagship cần giá trên biên IQR, không vi phạm quy tắc và có RAM ≥ 32 GB, storage ≥ 1.024 GB hoặc RTX 4080/4090. Xác minh nguồn trước khi xử lý. Pipeline giữ đầy đủ listing.

**Bàn giao TV5 và TV8.** Ghép theo `listing_record_id`. Loại cờ và điểm bất thường, gồm `isolation_score`, `combined_flag`, `anomaly_type` và `recommended_action`, khỏi đặc trưng đầu vào của mô hình giá vì chúng có thể phụ thuộc vào giá mục tiêu. TV5 dùng chúng để lọc hoặc đo độ nhạy trên tập train. TV8 đối chiếu với sai số lớn sau khi dự đoán trên tập test.
