# S2: Kiểm tra gói đặc trưng TV3

Dữ liệu vẫn ở commit `24cd858`. Giữ nguyên toàn bộ dòng train/test và tham số mô hình của S1.
S2 bổ sung `is_out_of_stock`, `charger_watt`, `is_charger_missing` cho cả ba thuật toán.
`is_out_of_stock=1` khi trạng thái là out_of_stock; 0 nghĩa là không được đánh dấu hết hàng (có thể unknown).
Sạc thiếu/không dương được điền bằng trung vị cùng hãng trên train, sau đó trung vị toàn train nếu hãng không có dữ liệu.
Nếu toàn train không có công suất sạc hợp lệ thì dùng 0 và giữ cờ thiếu bằng 1.
Giá trị màn hình đúng bằng 300 inch được đổi thành thiếu ở cả train/test, rồi điền theo cách của TV5, chỉ fit trên train.
Không xóa dòng test. Không tối ưu lại alpha hoặc tham số cây trong thí nghiệm này.

| Loại máy | Mô hình | MAE S1 (VNĐ) | MAE S2 (VNĐ) | Thay đổi MAE | RMSE S2 (VNĐ) | R² S2 |
|---|---|---:|---:|---:|---:|---:|
| laptop | ridge | 4,945,224 | 4,824,836 | -2.43% | 8,526,467 | 0.8279 |
| laptop | rf | 4,202,439 | 4,139,911 | -1.49% | 7,544,327 | 0.8653 |
| laptop | lgbm | 4,064,379 | 3,946,469 | -2.90% | 7,231,663 | 0.8762 |
| smartphone | ridge | 2,681,182 | 2,747,587 | +2.48% | 7,430,668 | 0.7965 |
| smartphone | rf | 2,550,440 | 2,431,305 | -4.67% | 5,780,397 | 0.8769 |
| smartphone | lgbm | 2,468,931 | 2,518,896 | +2.02% | 7,236,573 | 0.8070 |

Số âm ở cột thay đổi MAE nghĩa là sai số giảm so với S1.
Đây là tác động của cả gói S2; chưa tách riêng tác động của tồn kho, sạc và sửa màn hình.
Kết quả trên một phép chia dữ liệu chưa phải bằng chứng về độ cải thiện ổn định hay quan hệ nhân quả.

| Loại máy | Tập | Số dòng | Có sạc | Thiếu sạc | Hết hàng | Còn hàng | Tồn kho unknown | Screen=300 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| laptop | train | 3227 | 88 | 97.27% | 2154 | 434 | 639 | 1 |
| laptop | test | 819 | 26 | 96.83% | 541 | 99 | 179 | 1 |
| smartphone | train | 3300 | 669 | 79.73% | 1946 | 999 | 355 | 0 |
| smartphone | test | 797 | 155 | 80.55% | 476 | 238 | 83 | 0 |

Chạy bằng `python src/evaluation_demo/ablation_sensitivity.py --stage S2`.
Sáu mô hình và thông tin truy nguyên nằm trong `models/s2_tv3/`.
Dự đoán từng dòng được lưu ở `s2_test_predictions.csv`; độ phủ trường mới ở `tables/s2_input_coverage.csv`.
Các bước TV4, TV6 và TV7 chưa được chạy trong S2.
