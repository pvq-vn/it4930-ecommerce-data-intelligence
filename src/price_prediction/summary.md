# Báo cáo Quy trình Xây dựng & So sánh Mô hình Dự đoán Giá Sản phẩm (Laptop & Smartphone)

Tài liệu này tổng hợp toàn bộ quy trình từ khâu kiểm tra chất lượng dữ liệu, tiền xử lý, thiết kế đặc trưng (Feature Engineering), huấn luyện các mô hình học máy, so sánh kết quả đánh giá cho đến đóng gói pipeline dự đoán thực tế (`PricePredictor`).

---

## 1. Đánh giá Dữ liệu Đầu vào & Các Vấn đề Phát hiện

Qua quá trình khảo sát dữ liệu thô định dạng JSONL (`products_cleaned.jsonl` và `products_processed.jsonl`), hệ thống ghi nhận các đặc điểm và bất thường cần xử lý trước khi đưa vào huấn luyện:

1. **Khuyết thiếu và bất thường ở biến mục tiêu (`price_vnd`):**
   * Nhiều bản ghi thuộc trạng thái ngừng kinh doanh (`out_of_stock`) có giá trị `price_vnd = 0.0` hoặc cờ `is_price_missing: true`.
   * Cột `original_price_vnd` và `discount_rate` bị khuyết không đồng đều và mang nguy cơ rò rỉ dữ liệu (data leakage) nếu dùng làm biến đầu vào.
2. **Nhiễu danh mục (Category Noise):**
   * Một số thiết bị máy tính để bàn / All-in-One của Apple (iMac 21.5", iMac 27", Mac Studio, Mac Pro) bị gắn nhầm nhãn `category = "laptop"`.
3. **Lỗi trích xuất thông số phần cứng:**
   * **Nhầm lẫn dung lượng ổ cứng (`storage_gb`):** Một số mẫu laptop bị parse nhầm dung lượng RAM sang ổ cứng (ví dụ: `storage_gb = 16.0` hoặc `< 64GB` trong khi tên sản phẩm ghi rõ `256GB`, `512GB` hoặc `1TB`).
   * **Tỷ lệ thiếu dữ liệu cao:** Các cột như `ram_gb`, `battery_wh` (laptop) hoặc `battery_mah` (smartphone) có tỷ lệ giá trị `null` đáng kể.
   * **Dữ liệu trùng lặp & Biến thể sản phẩm:** Cùng một dòng sản phẩm gốc (`source_parent_id`) có thể xuất hiện nhiều lần với các mã niêm yết (`listing_record_id`) khác nhau.

---

## 2. Quy trình Thực hiện (Pipeline Xử lý & Huấn luyện)

### Bước 1: Tải, Gộp và Làm sạch Dữ liệu (`features.py`)
* **Gộp dữ liệu:** Hợp nhất dữ liệu từ `products_cleaned.jsonl` và các thông số bổ sung từ `products_processed.jsonl` (`battery_wh`, `battery_mah`, `camera_mp`, `display_type_norm`, `network_type_norm`) dựa trên khóa `listing_record_id`.
* **Lọc nhiễu giá và danh mục:**
  * Chỉ giữ lại các bản ghi hợp lệ với ngưỡng giá tối thiểu: **Laptop** $\ge 3,000,000\text{ VNĐ}$ và **Smartphone** $\ge 1,000,000\text{ VNĐ}$.
  * Loại bỏ hoàn toàn các cột gây rò rỉ dữ liệu (`LEAKAGE_COLS`: `discount_rate`, `original_price_vnd`, `listing_record_id`, `crawl_time`, `crawl_batch`, `is_price_missing`, `product_name`, `raw_specs`).
* **Khắc phục lỗi dung lượng lưu trữ:** Với các mẫu laptop có `storage_gb < 64`, hệ thống sử dụng biểu thức chính quy (Regex) trích xuất lại dung lượng thực tế (`128GB` đến `4TB`) từ `product_name`.

### Bước 2: Thiết kế Đặc trưng (Feature Engineering)
Dữ liệu được tách thành hai luồng độc lập tương ứng với đặc thù phần cứng của từng ngành hàng:

* **Tạo cờ báo thiếu dữ liệu (Missing Indicators):** Thêm các biến nhị phân `is_ram_missing`, `is_battery_missing` trước khi điền khuyết để mô hình nhận biết trạng thái khuyết thông số của sản phẩm.
* **Điền khuyết theo phân nhóm (Group Median Imputation):** Điền giá trị thiếu của các biến số bằng trung vị theo từng hãng (`brand`), sau đó điền trung vị toàn cục nếu vẫn còn thiếu.
* **Đặc trưng chuyên biệt cho Laptop (`engineer_laptop`):**
  * `ram_x_storage`: Biến tương tác giữa dung lượng RAM và ổ cứng ($\text{RAM} \times \text{Storage}$).
  * `is_dedicated_gpu`: Cờ nhận diện card đồ họa rời dựa trên từ khóa (`rtx`, `gtx`, `radeon`, `rx`, `arc`).
  * `cpu_tier_score`: Phân cấp sức mạnh vi xử lý theo thang điểm từ `0` đến `5` (ví dụ: Core i3/Ryzen 3 = `1`, Core i5/Ryzen 5 = `2`, Core i7/Ryzen 7 = `3`, Apple Silicon M1–M4 = `4`, Core i9/Ryzen 9 = `5`).
* **Đặc trưng chuyên biệt cho Smartphone (`engineer_smartphone`):**
  * `is_rom_high`: Cờ đánh dấu bộ nhớ trong lớn ($\ge 256\text{GB}$).
  * `is_oled`: Cờ nhận diện công nghệ màn hình cao cấp (`oled`, `amoled`, `retina`).

### Bước 3: Chiến lược Chia tập & Chống Rò rỉ Dữ liệu (`utils.py`)
* **Group-based Splitting:** Sử dụng `GroupShuffleSplit` (tỷ lệ 80% Train / 20% Test, `random_state = 42`) gom nhóm theo `source_parent_id`. Cách chia này đảm bảo các biến thể của cùng một sản phẩm không đồng thời xuất hiện ở cả tập huấn luyện và tập kiểm thử.
* **Biến đổi mục tiêu (Target Transformation):** Áp dụng `TransformedTargetRegressor` với hàm biến đổi $\log(1 + y)$ (`np.log1p`) khi huấn luyện và hàm ngược $e^{\hat{y}} - 1$ (`np.expm1`) khi dự đoán nhằm giảm độ lệch phải của phân phối giá thiết bị điện tử.

### Bước 4: Huấn luyện & Tối ưu Siêu tham số
Ba kiến trúc mô hình được triển khai và đánh giá trên cùng một bộ chỉ số (**MAE**, **RMSE**, $R^2$):
1. **Ridge Regression (Baseline - `trainning_baseline.py`):** Tiền xử lý biến số bằng `RobustScaler` và biến phân loại bằng `OneHotEncoder(handle_unknown='ignore')`, huấn luyện mô hình tuyến tính chuẩn hóa $L_2$ ($\alpha = 1.0$).
2. **Random Forest Regressor (`trainning_rf.py`):** Mã hóa biến phân loại bằng `OrdinalEncoder`, tối ưu 5 siêu tham số qua `RandomizedSearchCV` (25 tổ hợp) kết hợp kiểm định chéo 10-fold theo nhóm (`GroupKFold(n_splits=10)`).
3. **LightGBM Regressor (`trainning_lgbm.py`):** Tận dụng khả năng xử lý trực tiếp kiểu dữ liệu `category`, tinh chỉnh 9 siêu tham số bằng `RandomizedSearchCV` (25 tổ hợp) với `GroupKFold(n_splits=10)`.

---

## 3. So sánh Kết quả Đánh giá Các Mô hình

### 3.1. Bảng Tổng hợp Chỉ số trên Tập Kiểm thử (Test Set)

#### A. Danh mục Laptop
| Mô hình | MAE (VNĐ) | RMSE (VNĐ) | $R^2$ Score | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Ridge Regression (Baseline)** | 4,944,289 | 8,707,331 | 0.8205 | Mức cơ sở, hạn chế với quan hệ phi tuyến |
| **Random Forest** | 4,050,629 | 7,463,192 | 0.8681 | Giảm ~893.7k MAE so với Baseline |
| **LightGBM** | **3,772,465** | **6,803,738** | **0.8904** | **Tốt nhất trên cả 3 chỉ số** |

#### B. Danh mục Smartphone
| Mô hình | MAE (VNĐ) | RMSE (VNĐ) | $R^2$ Score | Đánh giá |
| :--- | :---: | :---: | :---: | :--- |
| **Ridge Regression (Baseline)** | 2,680,533 | 7,343,676 | 0.8013 | Ổn định nhưng sai số trung bình cao |
| **Random Forest** | 2,622,213 | **7,117,629** | **0.8133** | **Tốt nhất về RMSE và $R^2$ (ít sai số lớn)** |
| **LightGBM** | **2,445,580** | 7,720,708 | 0.7803 | Tốt nhất về MAE nhưng có một vài dự đoán lệch lớn |

### 3.2. Biểu đồ Trực quan So sánh Sai số (Đơn vị: Triệu VNĐ)

Biểu đồ dưới đây minh họa trực quan mức độ giảm sai số giữa các thuật toán:

```text
[LAPTOP - MAE (Triệu VNĐ)]
Ridge (Baseline) | █████████████████████████████████████████████████░ 4.94M
Random Forest    | █████████████████████████████████████████░░░░░░░░░ 4.05M
LightGBM (Best)  | ██████████████████████████████████████░░░░░░░░░░░░ 3.77M (-23.7%)

[LAPTOP - RMSE (Triệu VNĐ)]
Ridge (Baseline) | █████████████████████████████████████████████████░ 8.71M
Random Forest    | ██████████████████████████████████████████░░░░░░░░ 7.46M
LightGBM (Best)  | ██████████████████████████████████████░░░░░░░░░░░░ 6.80M (-21.9%)

---------------------------------------------------------------------------

[SMARTPHONE - MAE (Triệu VNĐ)]
Ridge (Baseline) | █████████████████████████████████████████████████░ 2.68M
Random Forest    | ████████████████████████████████████████████████░░ 2.62M
LightGBM         | █████████████████████████████████████████████░░░░░ 2.45M

[SMARTPHONE - RMSE (Triệu VNĐ)]
Ridge (Baseline) | ███████████████████████████████████████████████░░░ 7.34M
Random Forest    | █████████████████████████████████████████████░░░░░ 7.12M (Best)
LightGBM         | █████████████████████████████████████████████████░ 7.72M (Overfit outliers)
```

### 3.3. Phân tích & Lựa chọn Mô hình Triển khai
1. **Đối với Laptop — Chọn `LightGBM` (`lgbm_laptop.pkl`):**
   * Giải thích được **89.04%** phương sai của giá bán ($R^2 = 0.8904$), giảm sai số trung bình xuống còn **~3.77 triệu VNĐ**.
   * Khả năng chia nhánh dựa trên histogram và xử lý trực tiếp biến phân loại giúp LightGBM nắm bắt chính xác mức chênh lệch giá giữa các dòng chip, card đồ họa và phân khúc máy.
2. **Đối với Smartphone — Chọn `Random Forest` (`rf_smartphone.pkl`):**
   * Mặc dù LightGBM có MAE thấp hơn (~2.45 triệu VNĐ), nhưng **RMSE tăng vọt lên 7.72 triệu VNĐ** (kém hơn cả Baseline) và $R^2$ giảm xuống `0.7803`. Điều này phản ánh việc các cây tăng cường (boosting) bị quá khớp cục bộ hoặc ngoại suy lệch mạnh ở nhóm smartphone flagship dung lượng lớn / màn hình gập.
   * **Random Forest** nhờ cơ chế lấy trung bình nhiều cây độc lập (bagging) giúp triệt tiêu phương sai, đạt **RMSE thấp nhất (7.12 triệu VNĐ)** và $R^2$ cao nhất (`0.8133`), đảm bảo độ an toàn khi dự đoán thực tế.

---

## 4. Phân tích Tầm quan trọng của Đặc trưng (Feature Importance)

Dựa trên cấu trúc bộ đặc trưng (`LAPTOP_NUM_FEATURES + LAPTOP_CAT_FEATURES` và `SMARTPHONE_NUM_FEATURES + SMARTPHONE_CAT_FEATURES`) cùng cơ chế phân chia của mô hình cây quyết định, mức độ đóng góp của các nhóm biến được phân tầng như sau:

### 4.1. Nhóm đặc trưng chi phối giá Laptop (LightGBM)
1. **Nhóm Vi xử lý & Đồ họa (`cpu_tier_score`, `cpu_model`, `gpu_model`, `is_dedicated_gpu`):**
   * Đây là nhóm quyết định phân khúc giá cốt lõi. Việc bổ sung biến tổng hợp `cpu_tier_score` (thang 0–5) và cờ `is_dedicated_gpu` giúp mô hình tách biệt rõ ràng nhóm laptop phổ thông (dưới 15 triệu) với nhóm Gaming/Workstation có GPU rời RTX/GTX (20–60+ triệu).
2. **Nhóm Bộ nhớ & Tương tác cấu hình (`ram_x_storage`, `ram_gb`, `storage_gb`):**
   * Đặc trưng tương tác `ram_x_storage` đóng vai trò lớn trong việc định giá các phiên bản nâng cấp (ví dụ: bản 16GB/1TB đắt hơn đáng kể so với bản tiêu chuẩn 8GB/256GB cùng dòng).
3. **Nhóm Thương hiệu & Dòng máy (`brand`, `model_clean`):**
   * Giúp định vị biên độ giá theo thương hiệu (ví dụ: Apple MacBook, Dell XPS, Lenovo ThinkPad có mặt bằng giá cao hơn các dòng phổ thông cùng thông số phần cứng).
4. **Nhóm Cờ khuyết dữ liệu (`is_ram_missing`, `is_battery_missing`):**
   * Đóng vai trò phụ trợ quan trọng, giúp mô hình phân biệt các sản phẩm đời cũ/thiếu thông số niêm yết với các sản phẩm mới có thông số đầy đủ sau khi đã điền trung vị.

### 4.2. Nhóm đặc trưng chi phối giá Smartphone (Random Forest)
1. **Dòng sản phẩm & Thương hiệu (`model_clean`, `brand`):**
   * Khác với laptop (nơi cấu hình phần cứng quyết định phần lớn giá), giá smartphone phụ thuộc rất mạnh vào tên dòng sản phẩm cụ thể (`model_clean` như dòng Pro Max, Ultra, Galaxy Z Fold so với dòng tiêu chuẩn).
2. **Dung lượng lưu trữ (`storage_gb`, `is_rom_high`):**
   * Với cùng một mẫu điện thoại, dung lượng ROM (128GB, 256GB, 512GB, 1TB) là yếu tố tạo ra các nấc thang giá cố định (thường chênh lệch 3–5 triệu đồng mỗi bậc). Cờ `is_rom_high` ($\ge 256\text{GB}$) giúp Random Forest tách nhanh nhóm phiên bản dung lượng cao.
3. **Vi xử lý & Công nghệ màn hình (`cpu_model`, `is_oled`, `display_type_norm`):**
   * Cờ `is_oled` và loại chip giúp phân tách nhóm smartphone tầm trung/flagship sử dụng màn hình OLED/AMOLED với nhóm giá rẻ sử dụng màn hình LCD.
4. **Thông số phần cứng bổ sung (`ram_gb`, `screen_size_inch`, `battery_mah`, `camera_mp`, `network_type_norm`):**
   * Đóng góp vào việc tinh chỉnh mức giá trong cùng phân khúc (ví dụ: hỗ trợ mạng 5G hay kích thước màn hình lớn).

## 4. Đóng gói & Tích hợp Hệ thống Dự đoán (`predictor.py`)

Hệ thống suy luận (Inference) được đóng gói trong lớp `PricePredictor` với cấu hình mặc định tối ưu dựa trên kết quả thực nghiệm (`laptop_model='lgbm'`, `smartphone_model='rf'`):

* **Xử lý đầu vào linh hoạt:** Tự động bổ sung các cột thiếu bằng `np.nan` nếu người dùng trên giao diện Demo chỉ nhập một vài thông số cơ bản (ví dụ: chỉ nhập `brand`, `ram_gb`, `storage_gb`).
* **Đồng bộ hóa Feature Engineering:** Gọi trực tiếp `engineer_laptop` và `engineer_smartphone` từ `features.py` để đảm bảo logic biến đổi đặc trưng lúc suy luận khớp hoàn toàn với lúc huấn luyện.
* **Kiểm soát đầu ra & Bắt lỗi:** Kiểm tra tính hợp lệ của `category` (chỉ chấp nhận `'laptop'` hoặc `'smartphone'`), chuyển đổi kiểu dữ liệu `category` khi chạy mô hình LightGBM, và làm tròn giá dự đoán đến hàng nghìn đồng (`round(pred_price, -3)`).
