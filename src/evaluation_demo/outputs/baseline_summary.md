# Mốc cơ sở trước khi thêm đặc trưng

Dữ liệu được đọc từ commit `24cd858` và chia bằng chính mã của TV5.
Laptop có 3.227 dòng train và 819 dòng test. Smartphone có 3.300 dòng train và 797 dòng test.
Toàn bộ bước điền thông số thiếu, mã hóa và huấn luyện chỉ fit trên tập train.

Ridge dùng alpha=1.0. Random Forest dùng 200 cây và random_state=42.
LightGBM dùng 200 cây, learning_rate=0.1, num_leaves=31 và random_state=42.
Các tham số khác giữ mặc định của thư viện. Hai thuật toán cây dùng tối đa 4 luồng.
Bộ tham số này được chọn trước khi xem điểm test và sẽ được giữ cố định khi thêm đặc trưng.

TV5 đã tìm tham số cho Random Forest và LightGBM bằng cross-validation trên tập train.
Ridge của TV5 vốn dùng alpha=1.0, giống bản cơ sở này.
Random Forest TV5 cũng có 200 cây, nhưng max_features=0.5; bản cơ sở dùng max_features=1.0.
LightGBM TV5 có 400 cây và các tham số đã tối ưu khác với bản cơ sở 200 cây.
Cột thay đổi MAE tính theo (MAE cơ sở / MAE TV5 - 1) × 100. Số âm nghĩa là sai số giảm.

| Loại máy | Mô hình | MAE TV5 (VNĐ) | MAE cơ sở (VNĐ) | Thay đổi MAE | RMSE cơ sở (VNĐ) | R² cơ sở |
|---|---|---:|---:|---:|---:|---:|
| laptop | ridge | 4,945,224 | 4,945,224 | +0.00% | 8,692,758 | 0.8211 |
| laptop | rf | 4,073,539 | 4,202,439 | +3.16% | 7,552,169 | 0.8650 |
| laptop | lgbm | 3,768,480 | 4,064,379 | +7.85% | 7,434,339 | 0.8692 |
| smartphone | ridge | 2,681,182 | 2,681,182 | +0.00% | 7,342,246 | 0.8013 |
| smartphone | rf | 2,643,627 | 2,550,440 | -3.52% | 6,478,741 | 0.8453 |
| smartphone | lgbm | 2,510,216 | 2,468,931 | -1.64% | 7,117,832 | 0.8133 |

Điểm TV5 trong bảng được tính lại từ sáu mô hình đã bàn giao trên cùng tập test.
So sánh này phản ánh thay đổi cấu hình huấn luyện. Các thí nghiệm bổ sung đặc trưng sẽ lấy S1 làm mốc.
Báo cáo này mô tả riêng S1 với các đặc trưng TV5. So sánh S2 được lưu riêng ở `tv3_stage_summary.md` khi chạy.

Chạy lại từ môi trường Python có đủ thư viện bằng `python src/evaluation_demo/ablation_sensitivity.py`.
Chi tiết phiên bản thư viện, mã băm dữ liệu và tham số được ghi trong `models/s1_baseline/manifest.json`.
