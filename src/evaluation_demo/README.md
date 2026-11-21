# Demo đánh giá mô hình dự đoán giá của TV8

Ứng dụng trình bày giá niêm yết ước tính của laptop và điện thoại trong đợt thu thập dữ liệu. Tab dự đoán dùng các mô hình Ridge, Random Forest và LightGBM gốc do TV5 bàn giao. Các tab phân tích hiển thị riêng kết quả thử nghiệm S1–S5 và SHAP của S4.

## Chạy trên máy

Mở terminal tại thư mục gốc của kho Git, chọn môi trường Python sẽ dùng rồi chạy:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run src/evaluation_demo/app.py --server.address 127.0.0.1
```

Mở [demo cục bộ](http://127.0.0.1:8501) nếu trình duyệt chưa tự mở. Dừng ứng dụng bằng `Ctrl+C` trong terminal. Máy cần có Git, commit dữ liệu `24cd858` và các mô hình `.pkl` của TV5 trong kho dự án. App đọc bảng và hình trong `src/evaluation_demo/outputs`.

## Cách xem kết quả

1. **Dự đoán giá.** Chọn loại thiết bị, thuật toán và cấu hình. Có thể để trống một thông số chưa biết. Bấm **Dự đoán giá** để xem mức ước lượng, các yếu tố kéo giá lên hoặc xuống và các dòng có cấu hình tương tự. Dải tham chiếu dựa trên MdAPE của tập test và không mang mức độ bao phủ xác suất.
2. **So sánh mô hình.** Xem độ chính xác, thời gian dự đoán, dung lượng mô hình và mức tăng sai số khi che RAM/bộ nhớ. Đồ thị S1–S4 thể hiện kết quả khi thêm từng nhóm đặc trưng. Bảng S5 so sánh hai cách lọc cờ TV7.
3. **Phân tích sai số.** Đổi loại thiết bị, thuật toán và cách nhóm để xem mô hình lệch nhiều ở đâu. Bảng 20 dòng sai nhất cho biết cờ của TV7 để hỗ trợ đối chiếu.
4. **Giải thích mô hình.** Xem mức đóng góp SHAP trên toàn tập test S4, ba máy minh họa và phép thử khi tăng RAM/bộ nhớ. Hai mức RAM 32 và 64 GB của điện thoại là phép thử nằm ngoài phạm vi dữ liệu train.

LightGBM dùng TreeSHAP có sẵn trong mô hình. Ridge dùng đóng góp tuyến tính so với dữ liệu train. Random Forest dùng TreeSHAP khi có thư viện `shap` và dùng xấp xỉ theo 128 thứ tự đặc trưng khi chạy trong môi trường thiếu thư viện đó.

## Đầu vào và đầu ra dùng chung với TV5

Tab dự đoán chọn mô hình theo loại thiết bị (`laptop` hoặc `smartphone`). Hàm `prediction_frame()` chuẩn hóa nhãn theo tập train và tạo một dòng đầu vào cho pipeline TV5 đã lưu. Các ô để trống được chuyển thành giá trị thiếu để pipeline xử lý.

| Trường | Ý nghĩa và đơn vị |
|---|---|
| `brand`, `model_clean`, `seller_name`, `cpu_model` | Hãng, dòng máy, nhà bán lẻ, mẫu CPU |
| `ram_gb`, `storage_gb`, `screen_size_inch` | RAM và bộ nhớ theo GB, kích thước màn hình theo inch |
| `gpu_model`, `battery_wh` | Mẫu GPU và dung lượng pin theo Wh cho laptop |
| `battery_mah`, `camera_mp`, `display_type_norm`, `network_type_norm` | Pin theo mAh, camera theo MP, loại màn hình và mạng cho điện thoại |

`model.predict()` trả về giá niêm yết ước tính bằng **VNĐ** cho mỗi dòng. Dải tham chiếu trong demo tính từ giá dự đoán và MdAPE của đúng mô hình, đúng loại thiết bị. [Bảng 10.1](outputs/tables/table_10_1_model_benchmark_3d.csv) lưu các chỉ số hiển thị.

## Đối chiếu nhanh khi trình bày

Chọn **Điện thoại → Random Forest → Apple → iPhone 15 Pro Max**. Đặt **FPT**, **Apple A17 Pro**, **8 GB RAM**, **256 GB bộ nhớ** và **6,7 inch**, để trống pin, camera và các trường màn hình/mạng còn lại. Với nhãn gốc của dữ liệu TV5, trường hợp tham chiếu dự đoán khoảng **24,89 triệu đồng**. Mỗi trường có thể được kiểm tra riêng từ danh sách lựa chọn đã chuẩn hóa.

## Kiểm tra trước khi bàn giao

Chạy từ thư mục gốc của kho Git:

```powershell
python -m pytest tests/test_tv8_evaluation_demo.py -q
```

Bộ kiểm thử đối chiếu tập dữ liệu đã chia, sáu mô hình TV5, chuẩn hóa tên hãng và nhà bán lẻ, cùng các hiện vật bàn giao. [Báo cáo Phần 10](../../docs/tv8/report_part10_evaluation_demo.md) giải thích số liệu và liên kết tới ảnh của bốn tab demo.

## Tạo lại các bảng và biểu đồ

Chạy các lệnh sau theo thứ tự nếu cần tạo lại hiện vật từ dữ liệu đã chốt. Các tệp mô hình TV5 cần có sẵn trong kho Git. Các bước S2–S5 đọc kết quả và mô hình đã lưu từ bước trước. Nên dùng cùng phiên bản thư viện giữa các lượt huấn luyện. Phiên bản đã dùng cho S1–S4 được ghi trong các tệp `manifest.json` dưới `outputs/models/`.

```powershell
python src/evaluation_demo/evaluate_models.py
python src/evaluation_demo/ablation_sensitivity.py --stage all
python src/evaluation_demo/explainability.py
```

`--stage all` chạy lần lượt **S1, S2, S2A, S3, S4, S5a/S5b** và xuất Hình 10.3 trên Windows. Có thể chọn từng giai đoạn bằng `--stage S1`, `S2`, `S2A`, `S3`, `S4` hoặc `S5`. Dùng `--stage plot` để vẽ lại riêng Hình 10.3 từ bảng có sẵn.

Sau khi có bảng và dữ liệu SHAP, dùng PowerShell trên Windows để xuất sáu hình còn lại:

```powershell
& .\src\evaluation_demo\plot_error_diagnostics.ps1
& .\src\evaluation_demo\plot_explainability.ps1
```
