# Báo cáo cập nhật xử lý dữ liệu và đánh giá hiệu năng mô hình

## 1. Tổng hợp các thay đổi về dữ liệu và đặc trưng

### 1.1. Loại bỏ bản ghi hỏng cấu trúc (DOM Mismatch)

* **Hiện tượng phát hiện:** Kiểm tra chéo giữa nhãn thương hiệu (`brand`), tên sản phẩm (`product_name`) và kích thước màn hình (`screen_size_inch`) phát hiện **11 bản ghi lỗi liên tiếp** từ nguồn `viettelstore` (chỉ số `8238` đến `8248`). Bộ cào dữ liệu bị kẹt trạng thái từ bản ghi `8237` (`OPPO Reno14 5G`), dẫn đến việc ghép nhầm tên và giá bán của các mẫu máy tầm trung/cận cao cấp (9 bản ghi `OPPO Reno14 5G` giá $12.990.000$ VNĐ, `iPhone 16e` giá $15.990.000$ VNĐ, `HONOR X9d 5G` giá $11.990.000$ VNĐ) với thông số kỹ thuật của các mẫu điện thoại phổ thông/hãng khác (`brand` gán nhầm thành `Nokia`, `Masstel`, `Apple`, `Honor`, `ZTE`, `Xiaomi`; `model_clean = "Unknown"`; kích thước màn hình $1.77$–$2.40$ inch và khuyết RAM/ROM).
* **Thay đổi áp dụng:** Bổ sung hàm `_is_corrupted_record()` trong `load_and_split_data()` để tự động loại bỏ các bản ghi vi phạm một trong ba điều kiện:
  1. `model_clean` mang giá trị `'unknown'` hoặc khuyết.
  2. Mâu thuẫn thương hiệu chéo: `product_name` chứa từ khóa nhận diện của một hãng khác với giá trị trong cột `brand`.
  3. Mâu thuẫn vật lý: sản phẩm thuộc nhóm `smartphone` có `screen_size_inch < 3.5` nhưng giá bán $> 3.000.000$ VNĐ.
* **Tác động quy mô dữ liệu:** Tập dữ liệu giảm từ $8.374$ xuống còn $8.363$ bản ghi (nhóm `smartphone` giảm từ $4.323$ xuống $4.312$ bản ghi; số lượng bản ghi `model_clean == "Unknown"` giảm từ $10$ về $0$).

### 1.2. Chặn ngưỡng vật lý và khôi phục `screen_size_inch` & `storage_gb`

* **Hiện tượng phát hiện:**
  * Ở nhóm `laptop`, phát hiện 2 bản ghi `Lenovo ThinkPad E14 Gen 5` có `screen_size_inch = 300.0` (do bộ trích xuất bắt nhầm thông số độ sáng $300\text{ nits}$ thành kích thước inch) và 2 bản ghi bị khuyết thông số (`ASUS ROG Strix SCAR 18`, `HP 15 fd2183TU`).
  * Một số bản ghi `laptop` bị khuyết `storage_gb` (`NaN`) dù dung lượng ổ cứng có ghi rõ trong tên sản phẩm.
* **Thay đổi áp dụng:**
  * Thiết lập ngưỡng hợp lệ vật lý cho `screen_size_inch`: $[11.0, 19.0]$ inch đối với `laptop` và $[4.0, 8.5]$ inch đối với `smartphone`. Các giá trị nằm ngoài khoảng này được đưa về `NaN`.
  * Bổ sung hàm `_extract_screen_size_from_text()` trích xuất kích thước tường minh hoặc suy diễn theo quy ước đặt tên dòng máy laptop (`SCAR 18` $\rightarrow 18.0$, `HP 15` $\rightarrow 15.6$, `ThinkPad E14` $\rightarrow 14.0$) trước khi điền khuyết bằng trung vị theo hãng.
  * Mở rộng điều kiện khôi phục ổ cứng laptop (`storage_gb.isna() | (storage_gb < 64)`) để trích xuất dung lượng từ `product_name` cho cả các dòng bị `NaN`.

### 1.3. Chuẩn hóa và khôi phục đặc trưng mạng `network_type_norm` (Smartphone)

* **Hiện tượng phát hiện:** Cột `network_type_norm` từ dữ liệu đã xử lý có tới **32 giá trị phân mảnh**, bao gồm:
  * **Nhiễu và rò rỉ dữ liệu:** Lẫn chuỗi giá bán (ví dụ `'khoảng 12.490.000 vnđ'`, `'48,590,000 vnđ'`) và màu sắc (`'xanh'`, `'xanh (galaxy blue)'`).
  * **Trùng lặp ngữ nghĩa:** Cùng chuẩn 5G/4G nhưng tách thành nhiều biến thể (`'5g'`, `'hỗ trợ 5g'`, `'5g (sub-6 ghz)...'`, `'4g'`, `'hỗ trợ 4g'`, `'4g lte'`, `'hỗ trợ 4g volte'`).
  * **Tỷ lệ khuyết cao:** $2.694 / 4.323$ bản ghi smartphone ($\approx 62,3\%$) bị gán `'unknown'`, trong đó có $739$ bản ghi có chữ `'5G'` ngay trong `product_name` và $178+$ bản ghi thuộc các dòng `iPhone 12` trở lên (mặc định hỗ trợ 5G).
* **Thay đổi áp dụng:** Bổ sung hàm chuẩn hóa `network_type_norm` cho `smartphone`:
  * Gom nhóm toàn bộ biến thể về **4 nhãn chuẩn duy nhất**: `'5g'`, `'4g'`, `'2g_3g'`, `'unknown'`, đồng thời loại bỏ hoàn toàn các chuỗi giá tiền và màu sắc.
  * Khôi phục nhãn `'5g'` và `'4g'` cho các bản ghi `'unknown'` dựa trên từ khóa trong `product_name`, `model_clean`, `raw_specs` và nhận diện phần cứng các dòng `iPhone 12` trở lên (`iPhone 12`–`19`, `iPhone Air`, `iPhone SE 2022/3`).

### 1.4. Tái cấu trúc vị trí trích xuất văn bản trong pipeline

* **Thay đổi áp dụng:** Chuyển các bước trích xuất thông số từ văn bản (`product_name`, `raw_specs`) sang thực hiện trong `load_and_split_data()` trước khi loại bỏ `LEAKAGE_COLS`. Vì đây là các biến đổi độc lập trên từng dòng (stateless), việc đặt tại bước nạp dữ liệu vừa đảm bảo không gây rò rỉ dữ liệu giữa các fold đánh giá chéo, vừa tránh lỗi thiếu cột (`KeyError: 'product_name'`) khi truyền ma trận đặc trưng phần cứng vào `HardwareFeatureEngineer`.

---

## 2. Đánh giá và so sánh kết quả mô hình

### 2.1. Bảng tổng hợp chỉ số đánh giá (Trước vs. Sau cập nhật)

| Danh mục            | Mô hình                | Chỉ số    | Trước cập nhật | Sau cập nhật | Chênh lệch ($\Delta$) |    Mức cải thiện    |
| :------------------- | :----------------------- | :---------- | :----------------: | :------------: | :-----------------------: | :--------------------: |
| **Laptop**     | **Ridge Baseline** | MAE (VNĐ)  |   $4.945.224$   | $4.897.040$ |        $-48.184$        |      $-0,97\%$      |
|                      |                          | RMSE (VNĐ) |   $8.692.758$   | $8.564.659$ |       $-128.099$       |      $-1,47\%$      |
|                      |                          | $R^2$     |     $0,8211$     |   $0,8263$   |        $+0,0052$        |      $+0,64\%$      |
|                      | **Random Forest**  | MAE (VNĐ)  |   $4.073.539$   | $4.058.410$ |        $-15.129$        |      $-0,37\%$      |
|                      |                          | RMSE (VNĐ) |   $7.486.733$   | $7.463.642$ |        $-23.092$        |      $-0,31\%$      |
|                      |                          | $R^2$     |     $0,8673$     |   $0,8681$   |        $+0,0008$        |      $+0,09\%$      |
|                      | **LightGBM**       | MAE (VNĐ)  |   $3.768.480$   | $3.749.220$ |        $-19.261$        |      $-0,51\%$      |
|                      |                          | RMSE (VNĐ) |   $6.858.651$   | $6.852.468$ |        $-6.183$        |      $-0,09\%$      |
|                      |                          | $R^2$     |     $0,8886$     |   $0,8888$   |        $+0,0002$        |      $+0,02\%$      |
| **Smartphone** | **Ridge Baseline** | MAE (VNĐ)  |   $2.681.182$   | $2.265.246$ |       $-415.936$       | **$-15,51\%$** |
|                      |                          | RMSE (VNĐ) |   $7.342.246$   | $3.301.180$ |      $-4.041.066$      | **$-55,04\%$** |
|                      |                          | $R^2$     |     $0,8013$     |   $0,9508$   |        $+0,1494$        | **$+18,65\%$** |
|                      | **Random Forest**  | MAE (VNĐ)  |   $2.643.627$   | $2.209.994$ |       $-433.633$       | **$-16,40\%$** |
|                      |                          | RMSE (VNĐ) |   $6.757.150$   | $3.429.871$ |      $-3.327.280$      | **$-49,24\%$** |
|                      |                          | $R^2$     |     $0,8317$     |   $0,9469$   |        $+0,1151$        | **$+13,84\%$** |
|                      | **LightGBM**       | MAE (VNĐ)  |   $2.510.216$   | $1.841.594$ |       $-668.622$       | **$-26,64\%$** |
|                      |                          | RMSE (VNĐ) |   $7.373.367$   | $3.003.119$ |      $-4.370.248$      | **$-59,27\%$** |
|                      |                          | $R^2$     |     $0,7996$     |   $0,9593$   |        $+0,1596$        | **$+19,96\%$** |

---

### 2.2. Phân tích chi tiết kết quả

#### A. Nhóm Smartphone: Cải thiện đột phá về độ chính xác và độ ổn định

* **Giảm gần $50\%$–$60\%$ sai số bình phương trung bình (RMSE):** Trước khi làm sạch, RMSE của cả ba mô hình đều ở mức rất cao ($6,76$–$7,37$ triệu VNĐ), kéo $R^2$ xuống quanh ngưỡng $0,80$–$0,83$ (thậm chí LightGBM có RMSE cao hơn cả Ridge Baseline). Nguyên nhân chính đến từ **11 bản ghi lỗi DOM của `viettelstore`**: các mẫu máy giá $12$–$16$ triệu VNĐ lại mang thông số của điện thoại phổ thông ($1.77$–$2.40$ inch, `brand = Nokia/Masstel`, `model_clean = Unknown`). Khi rơi vào tập kiểm thử theo nhóm (`GroupKFold`), mô hình dự đoán mức giá dưới $1$ triệu VNĐ cho nhóm này, tạo ra sai số bình phương cực lớn. Sau khi loại bỏ cụm lỗi này, RMSE của LightGBM giảm mạnh từ $7,37$ triệu xuống còn **$3,00$ triệu VNĐ** ($-59,27\%$), đưa $R^2$ tăng vọt từ **$0,7996$ lên $0,9593$**.
* **Tác động rõ rệt lên sai số tuyệt đối trung bình (MAE):** Việc chuẩn hóa `network_type_norm` từ $32$ nhãn nhiễu về $4$ nhãn chuẩn và khôi phục thông tin `5g`/`4g` cho hơn $900$ bản ghi giúp mô hình phân tách chính xác chênh lệch giá giữa các phiên bản 4G và 5G của cùng một dòng máy. Nhờ đó, MAE giảm đồng loạt từ $15,51\%$ (Ridge) đến **$26,64\%$** (LightGBM, xuống còn **$1,84$ triệu VNĐ**).

#### B. Nhóm Laptop: Cải thiện ổn định và loại bỏ điểm ngoại lai tuyến tính

* **Hiệu quả rõ nhất trên mô hình tuyến tính (Ridge Baseline):** Việc chặn ngưỡng vật lý để sửa giá trị `screen_size_inch = 300.0` (từ lỗi bắt nhầm $300\text{ nits}$) về $14.0$ inch giúp Ridge giảm $128.099$ VNĐ ở chỉ số RMSE ($-1,47\%$) và tăng $R^2$ từ $0,8211$ lên $0,8263$, do các mô hình tuyến tính rất nhạy cảm với các điểm ngoại lai lớn gấp hơn $20$ lần giá trị thực.
* **Duy trì đà cải thiện trên mô hình cây (Random Forest & LightGBM):** Các thuật toán dựa trên cây quyết định vốn ít bị ảnh hưởng bởi ngoại lai đơn biến nên mức thay đổi nhỏ hơn, nhưng việc khôi phục kích thước màn hình và dung lượng ổ cứng bị khuyết vẫn giúp cả Random Forest và LightGBM cải thiện đồng đều trên cả ba thước đo MAE, RMSE và $R^2$ (LightGBM đạt $R^2 = 0,8888$, MAE $= 3,75$ triệu VNĐ).
