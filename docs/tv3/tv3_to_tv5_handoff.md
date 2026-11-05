# Tài liệu Bàn giao Kỹ thuật: Phân tích Khám phá Dữ liệu (TV3) sang Mô hình Hồi quy Dự đoán Giá (TV5)

**Dự án**: `it4930-ecommerce-data-intelligence`  
**Bên bàn giao**: Thành viên 3 (TV3 - Exploratory Data Analysis)  
**Bên tiếp nhận**: Thành viên 5 (TV5 - Price Prediction Modeling)  
**Tập dữ liệu đầu vào**: `data/processed/products_processed.jsonl` ($N = 10.316$ listings, 30 trường canonical)  
**Phụ thuộc môi trường**: [requirements-eda.txt](../../requirements-eda.txt) (`pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`)  
**Tài liệu quy chuẩn đối chiếu**:
- [tv3.md](tv3.md)
- [docs/feature_contracts_tv3_tv8.md](../feature_contracts_tv3_tv8.md#L51-L56)
- [docs/data_contract_tv2_v1.md](../data_contract_tv2_v1.md)
- [docs/data_quality_report_tv2_v1.md](../data_quality_report_tv2_v1.md)

---

## 1. Tóm tắt Khuyến nghị Kiến trúc Cốt lõi (Executive Summary for TV5)

1. **Phân tách Mô hình (Model Separation)**:  
   Khuyến nghị TV5 **huấn luyện 2 mô hình hồi quy độc lập**: 1 mô hình riêng cho ngành hàng **Laptop** ($N = 4.222$ bản ghi hợp lệ) và 1 mô hình riêng cho **Smartphone** ($N = 4.326$ bản ghi hợp lệ).  
   *Cơ sở thực nghiệm (Task 2.2 & Bảng 2.11)*: Triết lý định giá của 2 ngành hàng hoàn toàn khác nhau. Laptop định giá theo *Tài nguyên Xử lý Phần cứng* (RAM $\rho = +0.80$, CPU Tier $F = 757.19$, GPU Type $F = 399.81$), trong khi Smartphone định giá theo *Trải nghiệm & Thương hiệu* (ROM $\rho = +0.70$, Công nghệ Màn hình OLED $F = 2954.16$, Thương hiệu $H = 2335.59$). Việc gộp chung vào 1 mô hình sẽ gây nhiễu trọng số và suy giảm độ chính xác $R^2$.

2. **Lọc Mẫu Mục tiêu (Target Filtering)**:  
   Loại bỏ triệt để **1.768 bản ghi không hợp lệ** (1.752 bản ghi có `is_price_missing == True` / `price_vnd <= 0` và 16 bản ghi thiếu giá hoàn toàn), giữ lại đúng **8.548 bản ghi sạch** có giá hợp lệ $> 0$ để huấn luyện và đánh giá mô hình (Laptop: 4.222 máy, Smartphone: 4.326 máy).

3. **Biến đổi Target bắt buộc ($\log_{10}$ hoặc $\log(1 + y)$)**:  
   Do phân phối giá trên thang đo gốc có độ lệch phải rất nặng (Laptop Skewness $= \mathbf{+2.89}$, Kurtosis $= \mathbf{+13.54}$; Smartphone Skewness $= \mathbf{+7.38}$, Kurtosis $= \mathbf{+170.71}$) và tồn tại 87 mẫu flagship cực cao ($> 100$ triệu VNĐ), TV5 bắt buộc phải huấn luyện mô hình dự đoán trên thang $\log(1 + y)$ sử dụng `TransformedTargetRegressor(regressor=..., func=np.log1p, inverse_func=np.expm1)`. Biến đổi log giúp giảm mạnh độ lệch Skewness về xấp xỉ phân phối chuẩn đối xứng (Laptop: $\mathbf{+0.29}$, Smartphone: $\mathbf{-0.58}$).

4. **Ưu tiên Mô hình Cây Quyết định Tăng cường (GBDT)**:  
   Ưu tiên triển khai **LightGBM**, **XGBoost**, hoặc **CatBoost**. Các mô hình GBDT xử lý giá trị thiếu (Missing values) tự nhiên, miễn nhiễm với phân phối lệch và không bị tổn thương bởi hiện tượng đa cộng tuyến giữa RAM và ROM ở Smartphone ($r = +0.83$, $VIF = 5.44$).

---

## 2. Ma trận Đặc trưng Ứng viên (Candidate Feature Matrix)

*Căn cứ bảng tổng hợp thực nghiệm tại [table_1_3_candidate_features_missingness.md](../../src/eda/outputs/tables/table_1_3_candidate_features_missingness.md):*

| Tên đặc trưng (`feature`) | Kiểu dữ liệu | Tỷ lệ thiếu tổng | Thiếu Laptop | Thiếu Phone | Mức ưu tiên TV5 | Đề xuất Chiến lược Tiền xử lý cho TV5 |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `category` | Categorical | 0.0% | 0.0% | 0.0% | **Bắt buộc** | Phân tách tập dữ liệu để huấn luyện 2 mô hình độc lập. |
| `brand_norm` | Categorical | 0.3% | 0.1% | 0.4% | **Bắt buộc** | Target Encoding (Out-of-fold có smoothing) hoặc One-Hot cho Top 10 brand lớn, còn lại gom vào `'Other'`. |
| `installed_ram_gb` | Numeric | 33.6% | 45.6% | 22.9% | **Rất cao** | Biến số liên tục. Điền Median có phân tầng theo `(category, brand_norm)`. Bổ sung cờ `is_ram_missing`. |
| `storage_gb` | Numeric | 25.7% | 32.3% | 19.7% | **Rất cao** | Biến số liên tục. Điền Median có phân tầng theo `(category, brand_norm)`. Tạo biến phân đoạn bậc thang `storage_group`. |
| `cpu_norm` | Categorical | 53.7% | 21.7% | 82.5% | **Rất cao (Laptop)** | Rút trích phân tầng CPU Tier: Tier 1 (i9/R9), Tier 2 (i7/R7), Tier 3 (i5/R5), Tier 4 (i3/Entry), Apple M-series, gán `'Unknown'`. |
| `gpu_norm` | Categorical | 44.2% | 15.3% | 70.0% | **Cao (Laptop)** | Chỉ dùng cho Laptop. Tạo cờ nhị phân `is_dedicated_gpu` (Có/Không có GPU rời RTX/GTX/Radeon) và `is_apple_gpu`. |
| `display_type_norm` | Categorical | 44.8% | 70.0% | 22.3% | **Rất cao (Phone)** | Chỉ dùng mạnh cho Phone. Phân nhóm 3 bậc: OLED/AMOLED (1), IPS/LCD (0), Unknown (-1). Phân hóa giá $F = 2954.2$. |
| `battery_wh` | Numeric | 80.7% | 59.2% | 99.9% | **Cao (Laptop)** | Chỉ dùng cho Laptop. Tương quan $\rho = +0.66$ với giá. Điền median theo phân khúc GPU/CPU. |
| `battery_mah` | Numeric | 59.7% | 99.5% | 24.1% | **Trung bình (Phone)**| Chỉ dùng cho Phone. Tương quan $\rho = +0.036$ (bão hòa quanh 5.000 mAh). Tuyệt đối không ép trọng số tuyến tính dương lớn. |
| `charger_watt` | Numeric | 91.5% | 97.9% | 85.7% | **Xem xét** | Tỷ lệ thiếu cao (>85%). Nếu dùng, bắt buộc tạo cờ `is_charger_missing` và điền median. Tương quan đồng biến $\rho = +0.72$ ở Laptop. |
| `screen_size_inch` | Numeric | 84.8% | 79.8% | 89.2% | **Xem xét** | Tỷ lệ thiếu rất cao. Tương quan yếu với giá ($\rho = +0.09$). Điền median hoặc cân nhắc loại bỏ để giảm chiều dữ liệu. |
| `seller_raw` | Categorical | 0.0% | 0.0% | 0.0% | **Trung bình** | Frequency Encoding hoặc Target Encoding. Đại diện cho chính sách định giá của từng hệ thống bán lẻ. |
| `availability_status`| Categorical | 0.0% | 0.0% | 0.0% | **Cao** | Tạo cờ nhị phân `is_out_of_stock` để bù trừ độ lệch giá Price Drift (-28% đến -34% ở hàng hết tồn kho). |

---

## 3. Quy chuẩn Phòng chống Rò rỉ Dữ liệu (Data Leakage Prevention)

*Tuân thủ nghiêm ngặt [docs/feature_contracts_tv3_tv8.md#L55](../feature_contracts_tv3_tv8.md#L55) và bảng kiểm toán [table_3_3_data_leakage_audit.md](../../src/eda/outputs/tables/table_3_3_data_leakage_audit.md):*

### 3.1. Danh sách ĐEN - Tuyệt đối CẤM đưa vào Huấn luyện (Blacklist)

| Tên trường canonical | Lý do kỹ thuật / Cơ chế rò rỉ | Mức độ nguy hiểm |
| :--- | :--- | :---: |
| `discount_rate` | **RÒ RỈ TRỰC TIẾP TỪ TARGET**: $\text{discount\_rate} = 1 - \frac{\text{price\_vnd}}{\text{original\_price\_vnd}}$. Mô hình sẽ giải phương trình đại số tính ngược ra nhãn $y$ đạt $R^2 = 1.0$ giả tạo! | **TỐI NGUY HIỂM** |
| `original_price_vnd` | Tương quan $r = 0.96$ với target; mô hình chỉ học phép trừ chiết khấu thay vì học giá trị cấu hình sản phẩm. | **TỐI NGUY HIỂM** |
| `listing_record_id` | ID định danh nhân tạo do crawler tự sinh; gây ghi nhớ ID và overfitting cực nặng. | Nghiêm trọng |
| `source_parent_id` | ID nhóm sản phẩm của sàn TMĐT nguồn; không mang ý nghĩa vật lý phần cứng. | Nghiêm trọng |
| `crawl_time`, `crawl_batch` | Dấu ấn thời gian cào; mô hình hóa snapshot tĩnh không được học time-bias. | Trung bình |
| `is_price_missing` | Cờ chỉ báo thiếu target; chỉ dùng làm bộ lọc loại bỏ mẫu trước khi train. | Nghiêm trọng |

---

## 4. Chiến lược Tiền xử lý & Kỹ thuật Đặc trưng (Feature Engineering Guidelines)

### 4.1. Xử lý Giá trị Thiếu (Imputation Strategy)
1. **Biến số phần cứng liên tục (`installed_ram_gb`, `storage_gb`)**:
   - Không điền Mean (vì phân phối lệch).
   - Áp dụng **Stratified Median Imputation**: Điền giá trị trung vị có điều kiện theo nhóm `(category, brand_norm)`. Nếu nhóm `(category, brand_norm)` có $< 5$ mẫu thì lùi về trung vị của toàn bộ `category`.
2. **Missing Indicators**:
   - Đối với các biến số có tỷ lệ thiếu $> 30\%$ (`installed_ram_gb`, `display_type_norm`, `screen_size_inch`, `battery_mah`, `battery_wh`), bắt buộc tạo thêm cột cờ nhị phân `_is_missing` (ví dụ: `is_ram_missing`, `is_battery_missing`). Cờ này giúp mô hình nhận diện được pattern thiếu theo sàn cào (ví dụ CellphoneS cào thiếu RAM nhiều hơn TGDD).
3. **Biến phân loại danh mục (`cpu_norm`, `gpu_norm`, `display_type_norm`)**:
   - Gán giá trị thiếu thành nhãn tường minh `'Unknown'` hoặc `'Missing'`, không bỏ dòng.

### 4.2. Mã hóa Biến phân loại (Categorical Encoding)
1. **Low-cardinality features**:
   - `display_type_norm` (OLED/AMOLED vs IPS/LCD vs Unknown): One-Hot Encoding hoặc Ordinal Encoding (OLED=2, IPS=1, Unknown=0).
   - `category` (Laptop vs Smartphone): Tách mô hình riêng.
2. **High-cardinality features**:
   - `brand_norm` (Top 10 brands chiếm 80% thị phần): Áp dụng One-Hot Encoding cho Top 10, các hãng còn lại gom vào `'Other'`. Hoặc sử dụng Target Encoding (Out-of-Fold 5-fold cross-validation có Gaussian noise smoothing để chống rò rỉ target trong tập train).
   - `seller_raw`: Áp dụng Frequency Encoding (tỷ lệ xuất hiện của sàn) hoặc Target Encoding.

### 4.3. Biến tương tác & Đòn bẩy giá (Interaction Features)
*Căn cứ phát hiện từ Nhiệm vụ 2.1 & 2.2:*
- **Laptop**:
  * Tạo biến tương tác tài nguyên: `ram_x_storage = installed_ram_gb * storage_gb` (phân hóa cực mạnh ở phân khúc máy trạm render/AI).
  * Biến nhị phân đồ họa: `is_dedicated_gpu = 1` nếu card rời (RTX/GTX/Radeon), `= 0` nếu Onboard.
  * Biến phân tầng CPU: `cpu_tier_score` (Core i3 = 1, i5 = 2, i7 = 3, Apple M = 4, i9/R9 = 5).
- **Smartphone**:
  * Biến phân đoạn bậc thang ROM: `is_rom_high = 1` nếu $\ge 256$GB (bắt đầu vùng biên độ giá tăng vọt theo cấp số nhân).
  * Cờ màn hình cao cấp: `is_oled = 1` nếu OLED/AMOLED/Retina, `= 0` nếu IPS/LCD.

### 4.4. Kiểm soát Đa cộng tuyến (Multicollinearity Control)
*Căn cứ Bảng 3.2C VIF:*
- `installed_ram_gb` và `storage_gb` ở Smartphone có $r = +0.83$ và $VIF = 5.44$.
- Nếu TV5 huấn luyện các mô hình tuyến tính (OLS, Ridge, Lasso, ElasticNet, SVR, MLP):
  * **Bắt buộc sử dụng Ridge Regression ($L_2$ regularization)** với siêu tham số $\alpha$ được tinh chỉnh qua Cross-Validation để co nhỏ hệ số hồi quy.
  * Hoặc áp dụng PCA (Principal Component Analysis) kết hợp RAM và ROM thành 1 nhân tố "Memory Capacity".
  * Áp dụng `RobustScaler` thay vì `StandardScaler` để kháng cự ngoại lai.
- Nếu TV5 dùng GBDT (LightGBM/XGBoost/CatBoost): Không cần xử lý đa cộng tuyến vì cây quyết định tự động chọn thuộc tính tối ưu tại mỗi điểm phân nhánh.

### 4.5. Xử lý Trạng thái Tồn kho (`availability_status`)
*Căn cứ Bảng 3.4B Kiểm định Mann-Whitney U ($p < 10^{-16}$):*
- Hàng `in_stock` đắt hơn `out_of_stock` tới **+39.6% ở Laptop** và **+50.9% ở Smartphone** do hàng hết lưu giữ mức giá EOL cũ.
- **Khuyến nghị TV5**:
  * Đưa cờ nhị phân `is_out_of_stock = (availability_status == 'out_of_stock').astype(int)` làm feature đầu vào.
  * Khi đánh giá mô hình (Evaluation Benchmark), nên đánh giá riêng biệt Metric ($R^2$, MAE, MAPE, RMSE) trên 2 phân nhóm: Tập đang kinh doanh (`in_stock`) và Toàn bộ tập dữ liệu.

---

## 5. Tuyên bố Bằng chứng Khám phá (Exploratory vs. Causal Caveat)

> [!IMPORTANT]
> **Tuyên bố khoa học bắt buộc ghi vào phần phương pháp luận và kết quả mô hình TV5**:
> *"Các phân tích tương quan ($\rho, r$), mức độ quan trọng đặc trưng (Feature Importance), và các trọng số hồi quy (Regression Coefficients) được trình bày trong nghiên cứu này phản ánh mối liên hệ thống kê (statistical associations) được khám phá từ snapshot dữ liệu thị trường TMĐT Việt Nam. Đây là bằng chứng khám phá thực nghiệm phục vụ việc tối ưu hóa năng lực dự đoán giá (Predictive Performance), **tuyệt đối không được diễn giải là kết luận về quan hệ nhân quả (Causal Inference)** (ví dụ: việc nâng cấp 8GB RAM trên thị trường không đồng nghĩa với việc trực tiếp làm tăng chi phí sản xuất một lượng tiền cố định tương ứng)."*
