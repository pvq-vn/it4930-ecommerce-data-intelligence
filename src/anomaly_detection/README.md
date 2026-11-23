# Phát hiện bất thường

Chạy từ thư mục gốc dự án:

```powershell
python src/anomaly_detection/detect_price_anomalies.py
```

Chương trình đọc `data/processed/products_processed.jsonl` và tạo:

- `outputs/anomaly_flags.csv`: cờ theo từng listing, nhóm đối chiếu và lý do.
- `outputs/anomaly_summary.csv`: số lượng theo danh mục, trạng thái giá và mức cờ.
- `outputs/anomaly_method_summary.csv`: số lượng cờ của từng phương pháp và phần giao nhau.
- `outputs/anomaly_report.md`: mô tả phương pháp, tổng hợp và giới hạn.

Giá thiếu hoặc không dương được ghi trạng thái riêng để nhóm mô hình xử lý như dữ liệu không có target. Với giá dương, chương trình tính ngưỡng IQR trên log giá; laptop và smartphone luôn được xét riêng. Nếu thương hiệu có từ 20 bản ghi hợp lệ trở lên, dùng nhóm danh mục + thương hiệu; nhóm nhỏ hơn dùng toàn bộ danh mục. Cờ `review` là ngoại lệ theo ngưỡng 1.5 IQR hoặc dưới ngưỡng giá tham chiếu EDA (3 triệu cho laptop, 1 triệu cho smartphone); `extreme` vượt quá 3 IQR. Không có bước tự động xóa dữ liệu.

Sau baseline, Isolation Forest chạy riêng cho laptop và smartphone. Mô hình dùng log giá, thông số phần cứng, cờ thiếu dữ liệu và tần suất xuất hiện của các đặc trưng phân loại. Cấu hình mặc định gồm 300 cây, `contamination=0.02` và `random_state=42`. Tần suất được dùng thay cho mã số thứ tự để không tạo quan hệ giả như Apple < Dell < Lenovo.

File chi tiết tách riêng `rule_flag`, `iqr_flag`, `isolation_forest_flag`, `isolation_score`, `methods_agree` và `combined_flag`. Điểm `isolation_score` càng lớn thì record càng khác thường theo mô hình. `combined_flag` là hợp của ba phương pháp; các record được ít nhất hai phương pháp đồng thời gắn cờ được ưu tiên rà soát.

Các ngưỡng giá tối thiểu chỉ nhằm yêu cầu xác minh vì EDA từng ghi nhận phụ kiện và sản phẩm sai danh mục. `contamination=0.02` cũng chỉ là ngân sách rà soát, không phải tỷ lệ lỗi thật. Trước khi lọc cho mô hình, cần kiểm tra tên sản phẩm, cấu hình, nguồn và giá niêm yết.
