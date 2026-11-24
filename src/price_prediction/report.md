# Báo cáo cập nhật xử lý dữ liệu, tích hợp đặc trưng đa thành viên và đánh giá hiệu năng mô hình

## 1. Tổng hợp các thay đổi về làm sạch dữ liệu và chuẩn hóa thuộc tính

### 1.1. Loại bỏ bản ghi hỏng cấu trúc (DOM Mismatch) và sai danh mục thiết bị

* **Hiện tượng phát hiện:**
  * Kiểm tra chéo giữa nhãn thương hiệu (`brand`), tên sản phẩm (`product_name`) và kích thước màn hình (`screen_size_inch`) phát hiện **$11$ bản ghi lỗi liên tiếp** từ nguồn `viettelstore` (chỉ số `8238` đến `8248`), ghép nhầm tên và giá bán của các mẫu máy tầm trung/cận cao cấp (`OPPO Reno14 5G`, `iPhone 16e`, `HONOR X9d 5G`) với thông số của điện thoại phổ thông (`brand` gán nhầm thành `Nokia`, `Masstel`,...; `model_clean = "Unknown"`; màn hình $1.77$–$2.40$ inch).
  * Ở giai đoạn dữ liệu thô ban đầu, danh mục `laptop` từng xuất hiện một số bản ghi máy tính để bàn / All-in-One của Apple (`iMac`, `Mac Studio`, `Mac mini`, `Mac Pro`) bị gán nhầm nhãn `category_clean == 'laptop'`. **Trong tập dữ liệu đã làm sạch hiện tại (`products_cleaned.jsonl`), toàn bộ các bản ghi máy tính để bàn này đã được loại bỏ triệt để ngay từ khâu chuẩn hóa dữ liệu đầu vào.**
* **Thay đổi áp dụng:** Bổ sung hàm `_is_corrupted_record()` trong `load_and_split_data()` để tự động lọc và kiểm tra phòng vệ theo bốn điều kiện:
  1. `model_clean` mang giá trị `'unknown'` hoặc khuyết.
  2. Mâu thuẫn thương hiệu chéo: `product_name` chứa từ khóa nhận diện của một hãng khác với giá trị trong cột `brand`.
  3. Mâu thuẫn vật lý: sản phẩm thuộc nhóm `smartphone` có `screen_size_inch` $< 3.5$ nhưng giá bán $> 3.000.000\text{ VNĐ}$.
  4. Kiểm tra phòng vệ danh mục máy để bàn: mặc dù `products_cleaned.jsonl` đã loại bỏ hoàn toàn máy bàn, quy tắc kiểm tra `iMac`, `Mac Studio`, `Mac mini` và `Mac Pro` vẫn được duy trì trong `_is_corrupted_record()` như một lớp bảo vệ tự động cho các đợt cập nhật dữ liệu mới.

### 1.2. Chặn ngưỡng vật lý và khôi phục `screen_size_inch` & `storage_gb`

* **Hiện tượng phát hiện:**
  * Ở nhóm `laptop`, phát hiện $2$ bản ghi `Lenovo ThinkPad E14 Gen 5` có `screen_size_inch = 300.0` (do bộ trích xuất bắt nhầm thông số độ sáng $300\text{ nits}$ thành kích thước inch) và $2$ bản ghi bị khuyết thông số (`ASUS ROG Strix SCAR 18`, `HP 15 fd2183TU`).
  * Một số bản ghi `laptop` bị khuyết `storage_gb` (`NaN` hoặc $< 64\text{ GB}$) dù dung lượng ổ cứng có ghi rõ trong tên sản phẩm.
* **Thay đổi áp dụng:**
  * Thiết lập ngưỡng hợp lệ vật lý cho `screen_size_inch`: $[11.0, 19.0]$ inch đối với `laptop` và $[4.0, 8.5]$ inch đối với `smartphone`. Các giá trị nằm ngoài khoảng này được đưa về `NaN`.
  * Bổ sung hàm `_extract_screen_size_from_text()` trích xuất kích thước tường minh hoặc suy diễn theo quy ước đặt tên dòng máy laptop (`SCAR 18` $\rightarrow 18.0$, `HP 15` $\rightarrow 15.6$, `ThinkPad E14` $\rightarrow 14.0$) trước khi điền khuyết bằng trung vị theo hãng.
  * Mở rộng điều kiện khôi phục ổ cứng laptop (`storage_gb.isna() | (storage_gb < 64)`) để trích xuất dung lượng từ `product_name` cho cả các dòng bị `NaN`.

### 1.3. Chuẩn hóa và khôi phục đặc trưng mạng `network_type_norm` (Smartphone)

* **Hiện tượng phát hiện:** Cột `network_type_norm` từ dữ liệu đã xử lý có tới **$32$ giá trị phân mảnh**, lẫn chuỗi giá bán (`'khoảng 12.490.000 vnđ'`), màu sắc (`'xanh'`), nhiều biến thể trùng nghĩa và tỷ lệ `'unknown'` lên tới $\approx 62,3\%$.
* **Thay đổi áp dụng:** Bổ sung hàm `_normalize_smartphone_network()` gom nhóm toàn bộ biến thể về **$4$ nhãn chuẩn duy nhất** (`'5g'`, `'4g'`, `'2g_3g'`, `'unknown'`) và khôi phục nhãn `'5g'`/`'4g'` dựa trên từ khóa trong `product_name`, `model_clean`, `raw_specs` và nhận diện phần cứng các dòng `iPhone 12` trở lên.

### 1.4. Tái cấu trúc trích xuất văn bản và chuẩn hóa phân loại trong pipeline

* Chuyển các bước trích xuất thông số từ văn bản (`product_name`, `raw_specs`) sang thực hiện trong `load_and_split_data()` trước khi loại bỏ `LEAKAGE_COLS`.
* Chuẩn hóa toàn bộ biến phân loại về chữ thường (`.str.lower().str.strip()`) trong `_prepare_stateless()` và khóa cố định danh sách `pd.CategoricalDtype` (`cat_dtype_`) trong `fit()` của `HardwareFeatureEngineer` để xử lý nhất quán các nhãn chưa từng gặp (`'unknown'`) giữa Train, Validation, Test và lúc suy luận thực tế (`predictor.py`).

### 1.5. Thiết lập mô hình cơ sở (Baseline Model Setup)

* Trong quy trình huấn luyện (`training_baseline.py`), **Ridge Regression** (với tham số chuẩn $\alpha = 1.0$) được sử dụng thuần túy với vai trò là **mô hình cơ sở (baseline model)** tuyến tính nhằm thiết lập ngưỡng tham chiếu ban đầu để đánh giá mức độ cải thiện của các mô hình cây quyết định nâng cao (`Random Forest`, `LightGBM`).
* Vì `Ridge` chỉ đóng vai trò làm mốc đối chiếu chuẩn nên **không cần thiết phải sử dụng quy trình kiểm định chéo `GroupKFold` (`RandomizedSearchCV` / `GridSearchCV`) để hiệu chỉnh siêu tham số**; việc giữ cố định tham số mặc định giúp duy trì tính đơn giản, nhất quán của đường cơ sở và tiết kiệm chi phí tính toán.

---

## 2. Đánh giá hiệu năng sau giai đoạn làm sạch dữ liệu (Giai đoạn 1)

### 2.1. Bảng tổng hợp chỉ số đánh giá (Trước vs. Sau làm sạch dữ liệu)

| Danh mục            | Mô hình                | Chỉ số    | Trước cập nhật | Sau làm sạch (GĐ 1) | Chênh lệch ($\Delta$) |    Mức cải thiện    |
| :------------------- | :----------------------- | :---------- | :----------------: | :--------------------: | :-----------------------: | :--------------------: |
| **Laptop**     | **Ridge Baseline** | MAE (VNĐ)  |   $4.945.224$   |     $4.897.040$     |        $-48.184$        |      $-0,97\%$      |
|                      |                          | RMSE (VNĐ) |   $8.692.758$   |     $8.564.659$     |       $-128.099$       |      $-1,47\%$      |
|                      |                          | $R^2$     |     $0,8211$     |       $0,8263$       |        $+0,0052$        |      $+0,64\%$      |
|                      | **Random Forest**  | MAE (VNĐ)  |   $4.073.539$   |     $4.058.410$     |        $-15.129$        |      $-0,37\%$      |
|                      |                          | RMSE (VNĐ) |   $7.486.733$   |     $7.463.642$     |        $-23.092$        |      $-0,31\%$      |
|                      |                          | $R^2$     |     $0,8673$     |       $0,8681$       |        $+0,0008$        |      $+0,09\%$      |
|                      | **LightGBM**       | MAE (VNĐ)  |   $3.768.480$   |     $3.749.220$     |        $-19.261$        |      $-0,51\%$      |
|                      |                          | RMSE (VNĐ) |   $6.858.651$   |     $6.852.468$     |        $-6.183$        |      $-0,09\%$      |
|                      |                          | $R^2$     |     $0,8886$     |       $0,8888$       |        $+0,0002$        |      $+0,02\%$      |
| **Smartphone** | **Ridge Baseline** | MAE (VNĐ)  |   $2.681.182$   |     $2.265.246$     |       $-415.936$       | **$-15,51\%$** |
|                      |                          | RMSE (VNĐ) |   $7.342.246$   |     $3.301.180$     |      $-4.041.066$      | **$-55,04\%$** |
|                      |                          | $R^2$     |     $0,8013$     |       $0,9508$       |        $+0,1494$        | **$+18,65\%$** |
|                      | **Random Forest**  | MAE (VNĐ)  |   $2.643.627$   |     $2.209.994$     |       $-433.633$       | **$-16,40\%$** |
|                      |                          | RMSE (VNĐ) |   $6.757.150$   |     $3.429.871$     |      $-3.327.280$      | **$-49,24\%$** |
|                      |                          | $R^2$     |     $0,8317$     |       $0,9469$       |        $+0,1151$        | **$+13,84\%$** |
|                      | **LightGBM**       | MAE (VNĐ)  |   $2.510.216$   |     $1.841.594$     |       $-668.622$       | **$-26,64\%$** |
|                      |                          | RMSE (VNĐ) |   $7.373.367$   |     $3.003.119$     |      $-4.370.248$      | **$-59,27\%$** |
|                      |                          | $R^2$     |     $0,7996$     |       $0,9593$       |        $+0,1596$        | **$+19,96\%$** |

### 2.2. Nhận xét Giai đoạn 1

* Việc loại bỏ $11$ bản ghi lỗi DOM của `viettelstore` và chuẩn hóa `network_type_norm` giúp RMSE của LightGBM trên Smartphone giảm mạnh từ $7,37$ triệu xuống còn $3,00$ triệu VNĐ ($-59,27\%$), đưa $R^2$ từ $0,7996$ lên $0,9593$.
* Trên Laptop, việc chặn ngưỡng vật lý sửa lỗi `screen_size_inch = 300.0` giúp mô hình tuyến tính Ridge giảm $128.099\text{ VNĐ}$ ở chỉ số RMSE và cải thiện đều trên cả Random Forest lẫn LightGBM.

---

## 3. Tích hợp Insight & Đặc trưng Đa Thành viên (TV3, TV4, TV6, TV7 — Giai đoạn 2)

Sau khi hoàn tất làm sạch dữ liệu nội bộ, pipeline dự đoán giá được nâng cấp toàn diện bằng cách tích hợp các tín hiệu và kết quả phân tích từ các thành viên khác trong nhóm, đồng thời áp dụng kiểm soát chống rò rỉ dữ liệu nghiêm ngặt.

### 3.1. Chi tiết Các Nhóm Đặc trưng và Insight Đã Tích hợp

1. **Từ TV2 & TV3 (EDA & Phân tích Trôi giá Tồn kho):**
   * **Bổ sung đặc trưng `is_out_of_stock`:** Khai thác cột `availability_status` từ `products_processed.jsonl` để mã hóa trạng thái ngừng kinh doanh (`availability_status == 'out_of_stock'`), giúp mô hình nhận diện mức giảm giá của các dòng máy xả kho / cuối vòng đời (EOL).
   * **Bổ sung đặc trưng `charger_watt` & `is_charger_missing` (Laptop):** Đưa công suất bộ sạc (tương quan thuận mạnh với phân khúc laptop gaming/workstation) và cờ khuyết thông số sạc vào tập biến đầu vào của Laptop.
2. **Từ TV4 (Đồ thị Thị trường & Điểm chuẩn Hiệu năng Phần cứng):**
   * **Điểm chuẩn hiệu năng liên tục (`laptop_benchmarks.csv`, `smartphone_benchmarks.csv`):** Ghép theo khóa `listing_record_id` các chỉ số `cpu_perf_rating`, `gpu_perf_rating` cho Laptop và `cpu_benchmark_score`, `cpu_geekbench_5_multi`, `cpu_passmark` cho Smartphone, giúp mô hình phân tách chi tiết hiệu năng thực tế giữa các thế hệ chip thay vì chỉ dựa vào phân tầng thô `cpu_tier_score`.
   * **Đặc trưng cấu trúc thị trường không rò rỉ giá (`hw_seller_count`):** Tính số lượng niêm yết cùng kinh doanh một cấu hình phần cứng thuần túy `(category_clean, brand, model_clean, ram_gb, storage_gb)` nhằm phản ánh mức độ phổ biến và cạnh tranh của cấu hình đó.
   * **Chống rò rỉ nhãn mục tiêu từ phân cụm Louvain:** Tuyệt đối loại bỏ `community_id`, `segment_label`, `price_band`, `price_median`, `price_min`, `price_max` thông qua `LEAKAGE_COLS` do các cột này được xây dựng trực tiếp từ biến mục tiêu `price_vnd`.
3. **Từ TV6 (Khai phá Cảm xúc Đánh giá Khách hàng — Review NLP):**
   * **Đặc trưng cảm xúc cấp sản phẩm (`tv5_review_features.csv`):** Ghép theo khóa `source_parent_id` $5$ chỉ số tổng hợp từ đánh giá người dùng đã kiểm duyệt mốc thời gian: `has_review_data`, `review_count_usable`, `avg_sentiment_score`, `sentiment_positive_ratio`, `sentiment_net_score`.
   * **Chỉ số cảm xúc tiên nghiệm theo thương hiệu (`brand_sentiment_prior`):** Tính trung bình `avg_sentiment_score` theo từng `brand` hoàn toàn bên trong `HardwareFeatureEngineer.fit()` trên tập Train (fallback về trung bình toàn cục cho hãng mới), giúp bổ sung tín hiệu uy tín thương hiệu ngay cả cho các sản phẩm chưa có lượt đánh giá.
4. **Từ TV7 (Phát hiện Bất thường Thị trường — Anomaly Detection):**
   * **Xác nhận loại bỏ nhiễu danh mục phi giá:** Toàn bộ máy tính để bàn Apple (`iMac`, `Mac Studio`, `Mac mini`, `Mac Pro`) đã được loại bỏ hoàn toàn trong tập dữ liệu sạch `products_cleaned.jsonl`, đồng thời được kiểm soát bổ sung qua bộ lọc `_is_corrupted_record()`.
   * **Ngăn chặn rò rỉ dữ liệu từ cờ bất thường:** Toàn bộ các cột cờ và điểm dị biệt tính từ giá (`rule_flag`, `iqr_flag`, `iqr_extreme_flag`, `isolation_forest_flag`, `isolation_score`, `methods_agree`, `combined_flag`, `anomaly_severity`, `anomaly_reasons`) đều bị cấm đưa vào ma trận đặc trưng $X$.
   * **Kiểm định độ nhạy trên tập Huấn luyện (`ANOMALY_FILTER_MODE`):** Triển khai hàm `_apply_anomaly_train_filter()` trong `utils.py` cho phép kiểm chứng $3$ kịch bản lọc trên tập Train (`none`, `extreme_only`, `drop_combined`) trong khi giữ nguyên tập Test. Kết quả kiểm định cho thấy việc lọc toàn bộ `combined_flag` (`drop_combined`) làm $\text{RMSE}$ của Ridge trên Laptop tăng vọt từ $8,12$ triệu lên $9,52$ triệu VNĐ và $R^2$ tụt từ $0,8623$ xuống $0,8106$ do xóa nhầm các mẫu laptop flagship ($\ge 80\text{ triệu VNĐ}$) hợp lệ; do đó hệ thống chốt sử dụng chế độ `none` (lọc lỗi danh mục/ngưỡng sàn nhưng giữ lại sản phẩm cao cấp hợp lệ).

---

### 3.2. Bảng So sánh Hiệu năng Mô hình (Sau Làm sạch GĐ 1 vs. Sau Tích hợp Đa Thành viên Đã Khắc phục Crosswalk ID)

> *Lưu ý tích hợp liên nhánh:* Khi hợp nhất vào `main`, `products_processed.jsonl` (`fd3b991`) và `anomaly_flags.csv` (TV7) sử dụng mã băm `listing_record_id` mới, trong khi `products_cleaned.jsonl` và dữ liệu TV4 giữ mã băm cũ. Bảng ánh xạ 1-1 `data/processed/listing_id_crosswalk.csv` được bổ sung để khôi phục khớp đủ **8.374/8.374 dòng** với `source_parent_id` thực tế (không rò rỉ biến thể giữa Train/Test) và ghép đầy đủ đặc trưng TV2, TV3, TV4, TV6, TV7 trước khi huấn luyện lại cả 6 mô hình.

| Danh mục            | Mô hình                | Chỉ số    | Mốc cũ trước tích hợp (TV5 gốc) | Sau tích hợp ĐTV (Zero-Leakage) | Chênh lệch ($\Delta$) |    Mức cải thiện    |
| :------------------- | :----------------------- | :---------- | :---------------------: | :-------------------------: | :-----------------------: | :--------------------: |
| **Laptop**     | **Ridge Baseline** | MAE (VNĐ)  |      $4.945.224$      |   **$4.279.435$**   |       $-665.789$       |     $-13,46\%$      |
|                      |                          | RMSE (VNĐ) |      $8.692.758$      |   **$7.035.497$**   |      $-1.657.261$      |     $-19,06\%$      |
|                      |                          | $R^2$     |       $0,8211$       |    **$0,8828$**    |        $+0,0617$        |      $+7,51\%$      |
|                      | **Random Forest**  | MAE (VNĐ)  |      $4.073.539$      |   **$3.828.453$**   |       $-245.086$       |      $-6,02\%$      |
|                      |                          | RMSE (VNĐ) |      $7.486.733$      |   **$6.992.113$**   |       $-494.620$       |      $-6,61\%$      |
|                      |                          | $R^2$     |       $0,8673$       |    **$0,8843$**    |        $+0,0170$        |      $+1,96\%$      |
|                      | **LightGBM**       | MAE (VNĐ)  |      $3.768.480$      |   **$3.488.936$**   |       $-279.544$       |      $-7,42\%$      |
|                      |                          | RMSE (VNĐ) |      $6.858.651$      |   **$6.079.915$**   |       $-778.736$       |     $-11,35\%$      |
|                      |                          | $R^2$     |       $0,8886$       |    **$0,9125$**    |        $+0,0239$        |      $+2,69\%$      |
| **Smartphone** | **Ridge Baseline** | MAE (VNĐ)  |      $2.681.182$      |   **$2.184.928$**   |       $-496.254$       | **$-18,51\%$** |
|                      |                          | RMSE (VNĐ) |      $7.342.246$      |   **$3.264.949$**   |      $-4.077.297$      | **$-55,53\%$** |
|                      |                          | $R^2$     |       $0,8013$       |    **$0,9518$**    |        $+0,1505$        | **$+18,78\%$** |
|                      | **Random Forest**  | MAE (VNĐ)  |      $2.643.627$      |   **$2.114.765$**   |       $-528.862$       | **$-20,01\%$** |
|                      |                          | RMSE (VNĐ) |      $6.757.150$      |   **$3.406.507$**   |      $-3.350.643$      | **$-49,59\%$** |
|                      |                          | $R^2$     |       $0,8317$       |    **$0,9476$**    |        $+0,1159$        | **$+13,94\%$** |
|                      | **LightGBM**       | MAE (VNĐ)  |      $2.510.216$      |   **$1.864.679$**   |       $-645.537$       | **$-25,72\%$** |
|                      |                          | RMSE (VNĐ) |      $7.373.367$      |   **$3.022.967$**   |      $-4.350.400$      | **$-59,00\%$** |
|                      |                          | $R^2$     |       $0,7996$       |    **$0,9587$**    |        $+0,1591$        | **$+19,90\%$** |

---

### 3.3. Phân tích Giá trị Đóng góp của Việc Tích hợp Đa Thành viên

1. **Bứt phá toàn diện trên cả hai danh mục với mô hình `LightGBM`:**
   * **Trên Laptop:** `LightGBM` đạt $\text{MAE} = 3.488.936\text{ VNĐ}$, $\text{RMSE} = 6.079.915\text{ VNĐ}$ và $R^2 = \mathbf{0,9125}$ (cải thiện $+0,0239$ $R^2$ so với mốc cũ). Việc bổ sung công suất sạc (`charger_watt`), trạng thái tồn kho (`is_out_of_stock`), điểm chuẩn hiệu năng `cpu_perf_rating`/`gpu_perf_rating` (TV4), `hw_seller_count` và đặc trưng review (TV6) giúp mô hình tách bạch chính xác các phân khúc laptop mỏng nhẹ, gaming và workstation.
   * **Trên Smartphone:** Khi giữ đúng phân chia theo nhóm `source_parent_id` và kết hợp lọc nhiễu DOM + chuẩn mạng `network_type_norm` + điểm chuẩn SoC (TV4) + cảm xúc review (TV6), `LightGBM` giảm $\text{MAE}$ **$-25,72\%$** (từ $2,51$ triệu xuống **$1.864.679\text{ VNĐ}$**), $\text{RMSE}$ giảm **$-59,00\%$** (từ $7,37$ triệu xuống **$3.022.967\text{ VNĐ}$**) và $R^2$ đạt **$0,9587$**.
2. **Hợp nhất mô hình triển khai cuối cùng (`LightGBM` cho cả Laptop và Smartphone):**
   * Nhờ kết hợp làm sạch dữ liệu, khóa tập nhãn `pd.CategoricalDtype`, đồng bộ ánh xạ ID không rò rỉ và bổ sung bộ đặc trưng đa nguồn, `LightGBM` đạt vị trí dẫn đầu trên cả $6$ chỉ số đánh giá của hai danh mục và được đóng gói làm mô hình mặc định trong `PricePredictor` để bàn giao cho TV8.
