# DANH MỤC CẦN CHỈNH SỬA (TV4 – TV7) & CHỈ DẪN THỰC CHIẾN CHO TV8

- **Dự án**: Hệ thống Phân tích Dữ liệu & Dự đoán Giá Sản phẩm Công nghệ E-Commerce (`it4930-ecommerce-data-intelligence`)
- **Phạm vi tài liệu**: Chỉ giữ lại **các phần TV4 – TV7 cần chỉnh sửa** (kèm bằng chứng thực nghiệm tích hợp đặc trưng đa thành viên cho TV5) và **chỉ dẫn công việc chi tiết cho TV8** (các phần của TV1–TV3 đã được xử lý và đồng bộ trên nhánh `main` tại commit `fd3b991`).
- **Tài liệu gốc kiểm toán đầy đủ**: [`scratch/BAO_CAO_KIEM_TOAN_TOAN_DIEN_TV1_TV6_VA_CHI_DAN_TV8.md`](file:///d:/IT4930/scratch/BAO_CAO_KIEM_TOAN_TOAN_DIEN_TV1_TV6_VA_CHI_DAN_TV8.md)

---

## MỤC LỤC

1. [Phần I — Tóm tắt & Chi tiết Các Phần Cần Chỉnh Sửa cho TV4 – TV7](#phần-i--tóm-tắt--chi-tiết-các-phần-cần-chỉnh-sửa-cho-tv4--tv7)
   - [Bảng Tóm tắt Đầu việc Cần Sửa (TV4 – TV7)](#bảng-tóm-tắt-đầu-việc-cần-sửa-tv4--tv7)
   - [TV4 — Nguyễn Chính Minh (`src/market_graph/`, `data/market_graph/`)](#tv4--nguyễn-chính-minh-graph-analytics-entity-resolution--benchmarks)
   - [TV5 — Đào Duy Anh (`src/price_prediction/`)](#tv5--đào-duy-anh-price-prediction-modeling--khai-thác-insight-đa-thành-viên)
   - [TV6 — Nguyễn Trịnh Minh Hiếu (`src/review_nlp/`, `data/tv6/`)](#tv6--nguyễn-trịnh-minh-hiếu-review-nlp--sentimenttopic-mining)
   - [TV7 — Nguyễn Tùng Dương (`src/anomaly_detection/`)](#tv7--nguyễn-tùng-dương-market-anomaly-detection)
2. [Phần II — Chỉ dẫn Công việc Toàn diện & Thực chiến cho TV8 (`src/evaluation_demo/`)](#phần-ii--chỉ-dẫn-công-việc-toàn-diện--thực-chiến-cho-tv8-lê-trần-anh--srcevaluation_demo)
   - [2.1. Vị trí làm việc, Cấu trúc Thư mục & Danh sách Đầu vào từ TV2 – TV7](#21-vị-trí-làm-việc-cấu-trúc-thư-mục--danh-sách-đầu-vào-từ-tv2--tv7)
   - [2.2. 4 Quy tắc Kỹ thuật & Chống Rò rỉ Bắt buộc cho TV8](#22-4-quy-tắc-kỹ-thuật--chống-rò-rỉ-bắt-buộc-cho-tv8)
   - [2.3. Chi tiết 5 Hạng mục Công việc TV8 Cần Thực hiện & Làm Thế Nào (Kèm Code Mẫu)](#23-chi-tiết-5-hạng-mục-công-việc-tv8-cần-thực-hiện--làm-thế-nào-kèm-code-mẫu)
   - [2.4. Danh mục Hiện vật Bàn giao (Deliverables Checklist) của TV8](#24-danh-mục-hiện-vật-bàn-giao-deliverables-checklist-của-tv8)

---

## PHẦN I — TÓM TẮT & CHI TIẾT CÁC PHẦN CẦN CHỈNH SỬA CHO TV4 – TV7

### Bảng Tóm tắt Đầu việc Cần Sửa (TV4 – TV7)

| Thành viên | Thư mục làm việc | Các vấn đề trọng tâm cần khắc phục |
| :--- | :--- | :--- |
| **TV4**<br>Nguyễn Chính Minh | [`src/market_graph/`](file:///d:/IT4930/src/market_graph), [`data/market_graph/`](file:///d:/IT4930/data/market_graph) | • **[P1 - Target Leakage]** [louvain_segments.py](file:///d:/IT4930/src/market_graph/louvain_segments.py#L46-L78) và Bước 2 [entity_resolution.py](file:///d:/IT4930/src/market_graph/entity_resolution.py#L142-L195) dùng `price_median`/`price_vnd` để nối cạnh và tách cụm $\rightarrow$ **Cấm dùng `community_id`, `segment_label`, `price_band` cho dự đoán giá**.<br>• **[P2]** Cột `cpu_perf_rating` trong `smartphone_benchmarks.csv` bị rỗng 100% (dữ liệu thật nằm ở `cpu_benchmark_score`, `cpu_geekbench_5_multi`).<br>• **[P2]** 116 máy `< 1 triệu` VNĐ làm méo `avg_price_premium_pct` (`220%–279%`); commit ~8,6 MB file `.html`/`.js` thô vào Git và số liệu cũ trong `docs/market_graph_pipeline.md`. |
| **TV5**<br>Đào Duy Anh | [`src/price_prediction/`](file:///d:/IT4930/src/price_prediction) | • **[P1 - Lỗi Casing khi Demo]** Không chuẩn hóa chữ hoa/thường trong [features.py](file:///d:/IT4930/src/price_prediction/models/features.py#L99-L100) làm giá dự đoán iPhone 15 Pro Max viết thường tụt từ `24,89M` xuống `14,31M VNĐ` (`-42,5%`).<br>• **[P1]** [predictor.py](file:///d:/IT4930/src/price_prediction/predictor.py#L21-L26) khai báo `'catboost'` không tồn tại, thiếu `'ridge'`; `requirements.txt` thiếu `lightgbm`, `joblib`.<br>• **[P1 - Bỏ sót Insight từ TV3, TV4, TV6, TV7]** Chưa đưa `is_out_of_stock` & `charger_watt` (TV3), `cpu_perf_rating`/`gpu_perf_rating`/`cpu_benchmark_score`/`hw_seller_count` (TV4), `tv5_review_features.csv` (TV6) và kiểm định độ nhạy `anomaly_flags.csv` (TV7) vào mô hình (thực nghiệm giúp $R^2$ Smartphone tăng vọt từ `0,7886` lên `0,8588`).<br>• **[P2]** Chưa lọc 101 iMac trong `laptop`, 3 `screen_size_inch = 300.0` và 19 `network_type_norm` chứa tiền VNĐ trong `features.py`. |
| **TV6**<br>Nguyễn Trịnh Minh Hiếu | [`src/review_nlp/`](file:///d:/IT4930/src/review_nlp), [`data/tv6/`](file:///d:/IT4930/data/tv6) | • **[P2]** Gán nhầm nhãn cố định `topic_id = 1` (Màn hình/Camera $\rightarrow$ gán nhầm thành Dịch vụ/Giao hàng) và `topic_id = 3` (Nhân viên/Shop $\rightarrow$ gán nhầm thành Pin/Sạc) trong [feature_engineering_tv5.py](file:///d:/IT4930/src/review_nlp/feature_engineering_tv5.py#L67-L73).<br>• **[P2]** Lệch số liệu giữa [report_part8.md](file:///d:/IT4930/docs/tv6/report_part8.md) và `data/tv6/*.json`; còn link `file:///c:/HUST/...`.<br>• **[P2]** [test_tv6_sentiment_baseline.py](file:///d:/IT4930/tests/test_tv6_sentiment_baseline.py#L43-L45) thiếu `skipTest` khi chạy trên máy sạch không có `data/tv6/*.jsonl`. |
| **TV7**<br>Nguyễn Tùng Dương | [`src/anomaly_detection/`](file:///d:/IT4930/src/anomaly_detection) | • **[P1 - Chưa tách Lỗi dữ liệu vs. Flagship hợp lệ]** Gộp chung 234 ca giá thấp/lỗi giá (`< 3M` laptop, `< 1M` phone) với 73 siêu phẩm chính hãng `>= 80M VNĐ` vào cùng `combined_flag`, khiến việc lọc toàn bộ `combined_flag` làm tụt $R^2$ của TV5 từ `0,8805` xuống `0,8364` (Laptop) và `0,8588` xuống `0,7044` (Phone).<br>• **[P2 - Bỏ sót lỗi phần cứng phi giá]** Không bắt được 3 laptop `screen_size_inch = 300.0` (`0/3` flagged), 101 máy bàn Apple iMac lọt vào `laptop` (`0/101` flagged) và 21/23 giá tiền lọt vào `network_type_norm`.<br>• **[P2]** Chưa xuất bảng Sensitivity Analysis cho TV5; báo cáo [anomaly_report.md](file:///d:/IT4930/src/anomaly_detection/outputs/anomaly_report.md) mới 41 dòng sơ lược, chưa có biểu đồ. |

---

### TV4 — Nguyễn Chính Minh: Graph Analytics, Entity Resolution & Benchmarks
- **Vị trí làm việc**: [`src/market_graph/`](file:///d:/IT4930/src/market_graph), [`data/market_graph/`](file:///d:/IT4930/data/market_graph), [`docs/market_graph_pipeline.md`](file:///d:/IT4930/docs/market_graph_pipeline.md)

#### Các điểm cần chỉnh sửa & Cách khắc phục cụ thể
1. **[P1 - NGHIÊM TRỌNG: Rò rỉ nhãn mục tiêu (Target Leakage) trong Phân cụm Louvain và Entity Resolution Bước 2]**:
   - *Hiện trạng*:
     - Trong [src/market_graph/entity_resolution.py](file:///d:/IT4930/src/market_graph/entity_resolution.py#L142-L195) (Bước 2), các sản phẩm cùng cấu hình được chia tách cụm dựa trực tiếp trên độ lệch giá bán `price_vnd` (`max_spread = 0.20`).
     - Trong [src/market_graph/louvain_segments.py](file:///d:/IT4930/src/market_graph/louvain_segments.py#L46-L78), cạnh tương đồng giữa 2 sản phẩm chỉ được nối khi chênh lệch `price_median <= 20%`, và `price_band` / `segment_label` ghi trực tiếp khoảng giá (`"Laptop 16-22M"`).
   - *Cách khắc phục*:
     - Giữ kết quả Louvain cho mục đích phân tích cấu trúc thị trường ở Phần 6, nhưng phải bổ sung mục **"Cảnh báo Chống Rò rỉ khi Bàn giao cho TV5/TV8"** vào [`docs/market_graph_pipeline.md`](file:///d:/IT4930/docs/market_graph_pipeline.md): **Cấm tuyệt đối đưa `community_id`, `segment_label`, `price_band`, `price_median`, `price_min`, `price_max` vào mô hình dự đoán giá**.
     - Chỉ bàn giao cho TV5/TV8 các đặc trưng **hoàn toàn không dùng giá (Price-Free)**: điểm chuẩn phần cứng (`cpu_perf_rating`, `gpu_perf_rating`, `cpu_benchmark_score`, `cpu_geekbench_5_multi`) và số lượng sàn cùng bán một cấu hình phần cứng thuần túy (`hw_seller_count` tính từ khóa Bước 1 `(category_clean, brand, model_clean, ram_gb, storage_gb)`).
2. **[P2] Cột `cpu_perf_rating` trong [`data/market_graph/smartphone_benchmarks.csv`](file:///d:/IT4930/data/market_graph/smartphone_benchmarks.csv) bị rỗng `100%` (`NaN`)**:
   - *Hiện trạng*: Khi kiểm thử ghép nối `smartphone_benchmarks.csv` vào mô hình dự đoán giá, cột `cpu_perf_rating` trên Smartphone có **0/4.323 giá trị khác rỗng** (gây cảnh báo `Skipping features without any observed values: ['cpu_perf_rating']` trong `SimpleImputer`), trong khi điểm chuẩn thực tế của Smartphone lại được lưu ở các cột **`cpu_benchmark_score`**, **`cpu_geekbench_5_single`**, **`cpu_geekbench_5_multi`** và **`cpu_passmark`**!
   - *Cách khắc phục*: Điền `cpu_perf_rating` cho Smartphone từ phân vị chuẩn hóa của `cpu_benchmark_score` / `cpu_geekbench_5_multi`, hoặc ghi rõ trong tài liệu bàn giao rằng Laptop dùng `(`cpu_perf_rating`, `gpu_perf_rating`)` còn Smartphone dùng `(`cpu_benchmark_score`, `cpu_geekbench_5_multi`)`.
3. **[P2] 116 điện thoại `< 1.000.000` VNĐ làm méo chỉ số `avg_price_premium_pct` lên `220%–279%`**:
   - *Hiện trạng*: Trong [`data/market_graph/reports/market_gaps_report.md`](file:///d:/IT4930/data/market_graph/reports/market_gaps_report.md#L17-L23), `avg_price_premium_pct` của Smartphone vọt lên `240.06%` (CellphoneS), `219.98%` (FPT Shop), `278.73%` (Viettel Store) và xuất hiện phân khúc `"Smartphone 0-0M (Samsung) (0.39-0.39M)"` do gộp 116 máy cục gạch 2G/4G giá `110k–990k VNĐ`.
   - *Cách khắc phục*: Áp dụng ngưỡng lọc `price_median >= 1_000_000` cho `smartphone` và `>= 3_000_000` cho `laptop` (khớp với ngưỡng của TV3, TV5 và TV7) trước khi chạy `louvain_segments.py` và `structural_holes.py`.
4. **[P2] Dọn 6 tệp `.html`/`.js` thô (~8,6 MB) trong `data/market_graph/benchmarks/` khỏi Git & sửa số liệu cũ ở Mục 6 [`docs/market_graph_pipeline.md`](file:///d:/IT4930/docs/market_graph_pipeline.md#L453-L470)** (`3.112` $\rightarrow$ `1.899` mẫu CellphoneS; `125` $\rightarrow$ `71` blind spots; `24` $\rightarrow$ `20` underserved).

---

### TV5 — Đào Duy Anh: Price Prediction Modeling & Khai thác Insight Đa Thành viên
- **Vị trí làm việc**: [`src/price_prediction/`](file:///d:/IT4930/src/price_prediction), [`data/processed/products_cleaned.jsonl`](file:///d:/IT4930/data/processed/products_cleaned.jsonl)

#### Các lỗi kỹ thuật trong `src/price_prediction/` cần khắc phục ngay
1. **[P1 - NGHIÊM TRỌNG KHI DEMO] Không chuẩn hóa chữ hoa/thường (`casing`) và tên nhà bán lẻ trong `HardwareFeatureEngineer._prepare_stateless()`**:
   - *Hiện trạng*: Tại [src/price_prediction/models/features.py](file:///d:/IT4930/src/price_prediction/models/features.py#L99-L100), các cột phân loại (`brand`, `model_clean`, `seller_name`, `cpu_model`, `gpu_model`, `display_type_norm`, `network_type_norm`) chỉ được ép `.astype(str)` mà không chuẩn hóa chữ thường hay ánh xạ tên sàn. Khi chạy thử mẫu test viết thường ngay trong [src/price_prediction/predictor.py](file:///d:/IT4930/src/price_prediction/predictor.py#L58-L67) (`"brand": "apple"`, `"model_clean": "iphone 15 pro max"`, `"seller_name": "fpt shop"`, `"cpu_model": "apple a17 pro"`), mô hình `rf_smartphone.pkl` không khớp được với nhãn huấn luyện (`"Apple"`, `"iPhone 15 Pro Max"`, `"FPT"`, `"Apple A17 Pro"`), khiến giá dự đoán tụt từ **`24.892.000 VNĐ`** xuống chỉ còn **`14.306.000 VNĐ`** (sai lệch **`-10.586.000 VNĐ` = `-42,5%`**!).
   - *Cách khắc phục*: Trong `_prepare_stateless()` của `features.py`, chuẩn hóa `.astype(str).str.strip().str.lower()` cho mọi cột trong `cat_cols` và ánh xạ `seller_name` về một chuẩn duy nhất trước khi `fit`/`transform` (hoặc bọc hàm `canonicalize_product_dict()` trong `predictor.py` và ở tầng `model_loader.py` của TV8).
2. **[P1] Lệch cấu hình `predictor.py`, `summary.md` và `requirements.txt`**:
   - *Hiện trạng*: [src/price_prediction/predictor.py](file:///d:/IT4930/src/price_prediction/predictor.py#L21-L26) khai báo `'catboost'` (`results/catboost/cb_*.pkl`) nhưng không có tệp trên đĩa, trong khi bỏ sót `'ridge'` (`results/ridge/ridge_*.pkl` đang có sẵn). Ngoài ra [`requirements.txt`](file:///d:/IT4930/requirements.txt) chưa khai báo `lightgbm` và `joblib`, khiến máy chưa cài `lightgbm` không thể `joblib.load()` được `lgbm_laptop.pkl` và `lgbm_smartphone.pkl`.
   - *Cách khắc phục*: Thay key `'catboost'` bằng `'ridge'` trong `predictor.py` và thêm `lightgbm>=4.0.0`, `joblib>=1.3.0` vào `requirements.txt`.
3. **[P2] Nhận diện được lỗi Apple iMac nằm trong `laptop` ở `summary.md` nhưng quên lọc trong `features.py`**:
   - *Hiện trạng*: Tại [src/price_prediction/summary.md](file:///d:/IT4930/src/price_prediction/summary.md#L14-L15), TV5 ghi rõ: *"Một số thiết bị máy tính để bàn / All-in-One của Apple (iMac 21.5", iMac 27", Mac Studio, Mac Pro) bị gắn nhầm nhãn `category = 'laptop'`"*. Tuy nhiên trong hàm `load_and_split_data()` ([`features.py` dòng 33–45](file:///d:/IT4930/src/price_prediction/models/features.py#L33-L45)), TV5 lại **không hề lọc bỏ 101 bản ghi iMac này**, cũng như chưa lọc 3 bản ghi `screen_size_inch = 300.0` và 19 bản ghi `network_type_norm` chứa giá tiền VNĐ!

---

#### Đánh giá & Hướng dẫn khắc phục việc TV5 sử dụng Insight & Đặc trưng từ Các Thành viên Khác (TV2, TV3, TV4, TV6, TV7)

Theo đúng yêu cầu đặc tả Phần 7 (*"Đầu vào: file sản phẩm processed, kết quả bàn giao của TV3 và các đặc trưng đã được TV4/TV6/TV7 xác nhận là phù hợp"*), dưới đây là kiểm toán chi tiết những gì TV5 **đã dùng**, những gì TV5 **đang bỏ sót**, và **kết quả thực nghiệm định lượng** khi tích hợp đầy đủ:

##### A. Bảng Kiểm toán Mức độ Tiếp nhận Insight từ TV2, TV3, TV4, TV6, TV7 vào TV5

| Nguồn bàn giao | Insight / Đặc trưng bàn giao cho TV5 | Trạng thái sử dụng hiện tại trong `src/price_prediction/` | Đánh giá & Cách tích hợp vào `features.py` của TV5 |
| :--- | :--- | :---: | :--- |
| **TV2**<br>*(Data Quality)* | • Bảng [`products_processed.jsonl`](file:///d:/IT4930/data/processed/products_processed.jsonl) (`source_parent_id`, `battery_wh`, `battery_mah`, `camera_mp`, `display_type_norm`, `network_type_norm`).<br>• Cờ `availability_status` (`in_stock`, `out_of_stock`). | ⚠️ **Mới dùng một phần** | TV5 đã nối `source_parent_id`, pin, camera, màn hình, mạng từ `products_processed.jsonl`, nhưng **bỏ quên `availability_status` và `charger_watt`**, đồng thời chưa lọc 19 giá trị tiền tệ VNĐ bị lọt vào `network_type_norm` và 3 mẫu `screen_size_inch = 300.0`. |
| **TV3**<br>*(EDA — [`tv3_to_tv5_handoff.md`](file:///d:/IT4930/docs/tv3/tv3_to_tv5_handoff.md))* | 1. Tách 2 mô hình Laptop & Smartphone.<br>2. Biến đổi $\ln(1 + \text{price\_vnd})$.<br>3. Lọc sàn giá `>= 3M` (Laptop) & `>= 1M` (Phone).<br>4. Điền trung vị theo `brand` + cờ `is_ram_missing`, `is_battery_missing`.<br>5. Tạo biến `ram_x_storage`, `is_dedicated_gpu`, `cpu_tier_score` (Laptop) và `is_rom_high`, `is_oled` (Phone).<br>6. **Bổ sung `is_out_of_stock` (bù Price Drift `-28%..-34%` hàng EOL) và `charger_watt` ($\rho = +0.722$ trên Laptop)**.<br>7. **Kiểm soát đa cộng tuyến & tinh chỉnh `alpha` cho `Ridge`**. | ✅ **Đã dùng 5/7**<br>❌ **Bỏ sót mục 6 & 7** | TV5 đã thực thi rất tốt 5 khuyến nghị đầu của TV3, nhưng **bỏ sót hoàn toàn biến `is_out_of_stock` (`availability_status == 'out_of_stock'`) và `charger_watt`** dù TV3 đã chứng minh bằng kiểm định Mann-Whitney ($p < 10^{-16}$) rằng hàng hết tồn kho rẻ hơn tới 28%–34%. Ngoài ra `training_baseline.py` đang gắn cứng `Ridge(alpha=1.0)` thay vì tìm `alpha` tối ưu qua CV. |
| **TV4**<br>*(Market Graph & Benchmarks)* | 1. Bảng làm sạch LLM [`products_cleaned.jsonl`](file:///d:/IT4930/data/processed/products_cleaned.jsonl) (`8.374` dòng).<br>2. **Điểm chuẩn hiệu năng phần cứng**: `cpu_perf_rating`, `gpu_perf_rating` từ [`laptop_benchmarks.csv`](file:///d:/IT4930/data/market_graph/laptop_benchmarks.csv) (`4.051` dòng, khớp 100%) và `cpu_benchmark_score`, `cpu_geekbench_5_multi`, `cpu_passmark` từ [`smartphone_benchmarks.csv`](file:///d:/IT4930/data/market_graph/smartphone_benchmarks.csv) (`4.323` dòng, khớp 100%).<br>3. **Đặc trưng đồ thị không rò rỉ giá**: Số sàn cùng bán một cấu hình phần cứng (`hw_seller_count`).<br>4. *(Cấm dùng `louvain_segments.csv` / `community_id` vì rò rỉ giá)*. | ⚠️ **Chỉ mới dùng mục 1**<br>❌ **Bỏ sót toàn bộ mục 2 & 3** | Hiện tại TV5 mới chỉ dùng `cpu_tier_score` bậc thô `0..5` và cờ nhị phân `is_dedicated_gpu` (`0/1`), nên không phân biệt được hiệu năng thực tế giữa RTX 2050 và RTX 4090 hay giữa Snapdragon 680 và Snapdragon 8 Gen 3! Việc ghép thêm `cpu_perf_rating`, `gpu_perf_rating` (Laptop) và `cpu_benchmark_score`, `cpu_geekbench_5_multi` (Smartphone) cùng `hw_seller_count` theo `listing_record_id` là hoàn toàn **Price-Free (0% rò rỉ)** và cải thiện mạnh sai số phần trăm `MAPE`! |
| **TV6**<br>*(Review NLP — [`tv5_review_features.csv`](file:///d:/IT4930/data/tv6/tv5_review_features.csv))* | • Bảng `7.051` sản phẩm cha × `35` đặc trưng NLP đã kiểm duyệt mốc thời gian (`has_review_data`, `review_count_usable`, `avg_sentiment_score`, `sentiment_positive_ratio`, `sentiment_net_score`, 5 điểm cảm xúc khía cạnh `aspect_sentiment_score_*`).<br>• Chỉ số cảm xúc thương hiệu **`brand_sentiment_prior`** (tính trung bình trên tập Train theo hãng để dùng được cả cho sản phẩm mới chưa có review). | ❌ **Chưa sử dụng (`0/35` cột)** | TV5 chưa nối bảng `data/tv6/tv5_review_features.csv` (hoặc `.parquet`) qua khóa `source_parent_id`. Thực nghiệm bên dưới chứng minh việc bổ sung nhóm đặc trưng NLP của TV6 giúp **RMSE trên Smartphone giảm sâu tới `-1,385 triệu VNĐ` và $R^2$ tăng vọt từ `0,7886` lên `0,8588`**! |
| **TV7**<br>*(Anomaly Detection — [`anomaly_flags.csv`](file:///d:/IT4930/src/anomaly_detection/outputs/anomaly_flags.csv))* | • Bảng `10.316` dòng cờ (`rule_flag`, `iqr_flag`, `iqr_extreme_flag`, `isolation_forest_flag`, `anomaly_severity` = `none` / `review` / `extreme`).<br>• Đánh giá độ nhạy (Sensitivity Analysis) khi giữ lại vs. lọc bỏ các bản ghi bất thường trên tập Huấn luyện. | ⚠️ **Mới dùng ngưỡng sàn (`>=3M` / `>=1M`), chưa chạy Sensitivity Analysis** | TV5 đã lọc `price_vnd >= 3M` (Laptop) và `>= 1M` (Phone) — tương đương với việc loại bỏ 100% các bản ghi `rule_flag == True` của TV7. Tuy nhiên TV5 chưa thực hiện bảng so sánh độ nhạy khi loại bỏ thêm nhóm `anomaly_severity == 'extreme'` vs. loại bỏ toàn bộ `combined_flag == True` trên tập Train. |

##### B. Bằng chứng Thực nghiệm Định lượng: Mô hình TV5 Mạnh Lên Như Thế Nào Khi Kết Hợp Insight Của TV3 + TV4 + TV6 + TV7?

Chúng tôi đã chạy thực nghiệm trực tiếp trên đúng phép chia `GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)` theo `source_parent_id` của TV5 (`Laptop: 3.227 Train / 819 Test`; `Smartphone: 3.300 Train / 797 Test` với cùng cấu hình `RandomForestRegressor(n_estimators=200, random_state=42)` bọc trong `TransformedTargetRegressor(func=np.log1p, inverse_func=np.expm1)`):

###### Bảng 1 — Kết quả Tích hợp Đa Thành viên & Phân tích Độ nhạy trên LAPTOP (`n_test = 819`)

| Cấp độ Tích hợp (Ablation & Sensitivity Stage) | Thành viên đóng góp | MAE (VNĐ) | RMSE (VNĐ) | MAPE (%) | $R^2$ Score | Nhận xét Thực nghiệm |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **S1: TV5 Baseline Features** *(Hiện tại)* | TV2 + TV5 | `4.144.179` | `7.427.045` | `12,69%` | `0,8694` | Mức cơ sở với 11 biến phần cứng & hãng của TV5. |
| **S2: + TV3 Insights** *(`is_out_of_stock`, `charger_watt`, sửa `screen=300`)* | + **TV3** | `4.036.030` | `7.393.589` | **`12,22%`** | `0,8706` | Giảm ngay **`-108.149 VNĐ` MAE** và **`-0,47%` MAPE** nhờ bù trừ Price Drift hàng hết tồn kho và công suất sạc! |
| **S3: + TV4 Price-Free Features** *(`cpu_perf_rating`, `gpu_perf_rating`, `hw_seller_count`)* | + **TV4** | `4.077.202` | `7.327.864` | `12,69%` | `0,8729` | Điểm chuẩn CPU/GPU liên tục từ NotebookCheck giúp giảm thêm **`-65.725 VNĐ` RMSE** ở các dòng máy cấu hình cao. |
| **S4: + TV6 Review NLP** *(`review_count_usable`, `avg_sentiment_score`, `brand_sentiment_prior`)* | + **TV6** | `3.985.608` | **`7.104.989`** | `12,43%` | **`0,8805`** | Giảm mạnh **`-322.056 VNĐ` RMSE** và tăng **`+0,0111` $R^2$** so với S1! |
| **S5a: S4 + TV7 Lọc `extreme` Anomalies trên tập Train** | + **TV7** *(Đúng chuẩn)* | **`3.975.005`** | `7.143.663` | `12,42%` | `0,8792` | **Đạt MAE thấp nhất (`3.975.005 VNĐ`, giảm `-169.174 VNĐ` so với S1)** khi chỉ lọc các điểm dị biệt cực đoan (`extreme`) khỏi tập Train. |
| **S5b: S4 + TV7 Lọc TOÀN BỘ `combined_flag` trên tập Train** | + **TV7** *(Cảnh báo)* | `4.329.085` | `8.314.281` | `12,88%` | `0,8364` | **Suy giảm mạnh (`R2` tụt từ `0,8805` xuống `0,8364`)** vì `combined_flag` xóa nhầm cả các laptop flagship `> 80 triệu VNĐ` hợp lệ khỏi tập Train! |

###### Bảng 2 — Kết quả Tích hợp Đa Thành viên & Phân tích Độ nhạy trên SMARTPHONE (`n_test = 797`)

| Cấp độ Tích hợp (Ablation & Sensitivity Stage) | Thành viên đóng góp | MAE (VNĐ) | RMSE (VNĐ) | MAPE (%) | $R^2$ Score | Nhận xét Thực nghiệm |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **S1: TV5 Baseline Features** *(Hiện tại)* | TV2 + TV5 | `2.649.586` | `7.574.441` | `22,06%` | `0,7886` | Mức cơ sở hiện tại trên Smartphone. |
| **S2: + TV3 Insights** *(`is_out_of_stock`, `charger_watt`, lọc nhiễu)* | + **TV3** | `2.618.141` | `7.566.727` | `21,76%` | `0,7890` | Giảm `-31.445 VNĐ` MAE và `-0,30%` MAPE. |
| **S3: + TV4 Price-Free Features** *(`cpu_benchmark_score`, `cpu_geekbench_5_multi`, `hw_seller_count`)* | + **TV4** | `2.578.740` | `7.616.905` | **`19,61%`** | `0,7862` | Điểm chuẩn Geekbench 5 / Benchmark SoC và độ phủ sàn giúp **MAPE giảm sâu `-2,45%`** (từ `22,06%` xuống `19,61%`)! |
| **S4: + TV6 Review NLP** *(`review_count_usable`, `avg_sentiment_score`, `brand_sentiment_prior`)* | + **TV6** | **`2.522.719`** | **`6.189.160`** | `19,98%` | **`0,8588`** | **Bứt phá ngoạn mục**: Nhờ độ phủ review trên Smartphone đạt `67,8%`, việc ghép đặc trưng NLP của TV6 giúp **RMSE giảm kỷ lục `-1.385.281 VNĐ` và $R^2$ tăng vọt từ `0,7886` lên `0,8588` (`+7,02%`!)**. |
| **S5a: S4 + TV7 Lọc `extreme` Anomalies trên tập Train** | + **TV7** | `2.705.635` | `7.455.352` | `20,25%` | `0,7952` | Do nhiều mẫu điện thoại gập/flagship 1TB nằm trong nhóm `extreme` IQR của Smartphone, việc xóa chúng khỏi Train làm tăng sai số trên các flagship ở tập Test. |
| **S5b: S4 + TV7 Lọc TOÀN BỘ `combined_flag` trên tập Train** | + **TV7** *(Cảnh báo)* | `2.908.920` | `8.956.429` | `20,88%` | `0,7044` | Chứng minh sắc bén nguyên tắc của Phần 7 & Phần 9: **Tuyệt đối không tự động xóa mọi điểm bất thường (`combined_flag`)** vì sẽ làm mất vùng dữ liệu flagship, kéo $R^2$ tụt xuống `0,7044`! |

---

### TV6 — Nguyễn Trịnh Minh Hiếu: Review NLP & Sentiment/Topic Mining
- **Vị trí làm việc**: [`src/review_nlp/`](file:///d:/IT4930/src/review_nlp), [`data/tv6/`](file:///d:/IT4930/data/tv6), [`docs/tv6/`](file:///d:/IT4930/docs/tv6), [`tests/test_tv6_*.py`](file:///d:/IT4930/tests)

#### Các điểm cần chỉnh sửa & Cách khắc phục cụ thể
1. **[P2] Gán nhầm nhãn tên chủ đề cố định cho `topic_id = 1` và `topic_id = 3`**:
   - *Hiện trạng*: Trong [src/review_nlp/feature_engineering_tv5.py](file:///d:/IT4930/src/review_nlp/feature_engineering_tv5.py#L67-L73) và [data/tv6/topic_aspect_report.json](file:///d:/IT4930/data/tv6/topic_aspect_report.json#L6-L41), `topic_id = 1` có bộ từ khóa thực tế là `màn_hình, chụp, đẹp, rất, hình, có, mượt, nét, camera, hình_ảnh` nhưng bị gán cứng nhãn là `"Dịch vụ shop & Giao hàng"` (`topic_share_service_delivery`); ngược lại `topic_id = 3` có từ khóa `nhân_viên, nhiệt_tình, tư_vấn, tốt, mua, hàng, máy, shop, giao, nhanh` nhưng lại bị gán nhãn là `"Thời lượng pin & Phụ kiện sạc"` (`topic_share_battery_charging`).
   - *Cách khắc phục*: Hoán đổi lại ánh xạ `topic_id = 1` (`"Màn hình & Camera"` $\rightarrow$ `topic_share_screen_camera`), `topic_id = 2` (`"Thời lượng pin & Phụ kiện sạc"` $\rightarrow$ `topic_share_battery_charging`), `topic_id = 3` (`"Dịch vụ shop & Giao hàng"` $\rightarrow$ `topic_share_service_delivery`) trong `topic_aspect.py` và `feature_engineering_tv5.py`.
2. **[P2] Đồng bộ các con số trong [`docs/tv6/report_part8.md`](file:///d:/IT4930/docs/tv6/report_part8.md) với `data/tv6/*.json` và gỡ link cục bộ `file:///c:/HUST/...`**:
   - *Cách khắc phục*: Cập nhật độ dài trung vị từ `50` thành `44.0` ký tự, số bản ghi trùng dư thừa từ `6.202` thành `2.422` (`12.447` văn bản duy nhất / `14.869` review hợp lệ theo `quality_report.json`), Accuracy của Logistic Regression từ `89,17%` thành `89,81%` (`sentiment_baseline_report.json`), và PhoBERT Validation Macro F1 từ `0,5789` thành `0,6315` (`sentiment_phobert_report.json`).
3. **[P2] Thêm `skipTest` vào [`tests/test_tv6_sentiment_baseline.py`](file:///d:/IT4930/tests/test_tv6_sentiment_baseline.py#L43-L45)**:
   - *Hiện trạng*: Do `data/tv6/*.jsonl` đã được đưa vào `.gitignore`, khi chạy `pytest` trên một bản clone sạch không có tệp `.jsonl` trung gian, `test_tv6_sentiment_baseline.py` sẽ bị FAIL (khác với `test_tv6_phobert_sentiment.py` và `test_tv6_topic_aspect.py` đã có `if not jsonl_path.exists(): self.skipTest(...)`).
   - *Cách khắc phục*: Thêm kiểm tra `if not out_jsonl.exists(): self.skipTest("Intermediate JSONL is gitignored on clean checkout")` vào `test_tv6_sentiment_baseline.py`.

---

### TV7 — Nguyễn Tùng Dương: Market Anomaly Detection
- **Vị trí làm việc**: [`src/anomaly_detection/`](file:///d:/IT4930/src/anomaly_detection), [`src/anomaly_detection/outputs/`](file:///d:/IT4930/src/anomaly_detection/outputs)

#### Các điểm cần chỉnh sửa & Cách khắc phục cụ thể cho TV7
1. **[P1 - Chưa phân loại tường minh giữa "Lỗi dữ liệu / Sai danh mục" và "Sản phẩm Flagship hiếm nhưng hợp lệ"]**:
   - *Hiện trạng*: Đặc tả nhiệm vụ Phần 9 yêu cầu rõ: *"Phân biệt lỗi dữ liệu tiềm năng với các trường hợp hiếm nhưng hợp lệ"*. Hiện tại trong `anomaly_flags.csv`, cột `combined_flag` (`468` bản ghi) và `anomaly_severity` (`extreme`: `95` bản ghi; `review`: `373` bản ghi) đang **trộn lẫn 2 bản chất hoàn toàn trái ngược nhau**:
     - **Nhóm Lỗi giá / Lạc danh mục thực sự**: 5 laptop Core i5/i7 giá `1,69 triệu` VNĐ và 229 điện thoại bàn phím 2G `< 1 triệu` VNĐ (cần loại bỏ khỏi tập huấn luyện smartphone/laptop).
     - **Nhóm Siêu phẩm (Flagship / Workstation) chính hãng hợp lệ**: Có tới **73 / 188 sản phẩm giá `>= 80.000.000 VNĐ`** (MacBook Pro M3 Max, MSI Titan 18 HX, ASUS ROG Strix SCAR, Samsung Galaxy Z Fold) bị `iqr_flag` (do giá cao hơn `Q3 + 1.5 IQR` của hãng) hoặc `isolation_forest_flag` gắn cờ!
     - Như thực nghiệm ở Mục B phần TV5 bên trên (Bảng 1 & Bảng 2) đã chứng minh: Nếu TV5 lọc bỏ toàn bộ `combined_flag == True` khỏi tập Train (kịch bản `S5b`), mô hình sẽ mất sạch dữ liệu học ở phân khúc cao cấp, làm **$R^2$ trên tập Test sụt giảm nghiêm trọng từ `0,8805` xuống `0,8364` (Laptop) và từ `0,8588` xuống `0,7044` (Smartphone)**!
   - *Cách khắc phục trong [`src/anomaly_detection/detect_price_anomalies.py`](file:///d:/IT4930/src/anomaly_detection/detect_price_anomalies.py)*:
     - Bổ sung cột `anomaly_type` và `recommended_action` vào `anomaly_flags.csv`:
       - `"low_price_or_category_noise"` (`recommended_action = "filter_before_modeling"`): Các bản ghi có `rule_flag == True` (`laptop < 3M`, `smartphone < 1M`) hoặc máy bàn iMac lọt vào `laptop`.
       - `"rare_valid_flagship"` (`recommended_action = "keep_with_log_transform"`): Các bản ghi có giá cao (`_log_price > high` theo IQR) nhưng sở hữu cấu hình cao cấp tương xứng (`installed_ram_gb >= 32` hoặc `storage_gb >= 1024` hoặc `gpu_norm` chứa `RTX 4080/4090`).
       - `"spec_price_mismatch_review"` (`recommended_action = "sensitivity_check"`): Các bản ghi bị Isolation Forest gắn cờ hoặc giá thấp hơn ngưỡng dưới IQR (`_log_price < low`) dù trên mức sàn.
2. **[P2 - Bỏ sót các bất thường thông số phần cứng & sai danh mục phi giá (Hardware & Category Rules)]**:
   - *Hiện trạng*: Kiểm chứng thực nghiệm trên `src/anomaly_detection/outputs/anomaly_flags.csv` cho thấy:
     - **3 laptop Lenovo bị lỗi regex `screen_size_inch = 300.0`** (`"300 nits"`) đều có **`combined_flag = False` (`0/3` được gắn cờ)**!
     - **101 máy tính để bàn Apple iMac (`21.5"`, `24"`, `27"`) có giá hợp lệ nằm nhầm trong `category = "laptop"`** đều có **`combined_flag = False` (`0/101` được gắn cờ)**!
     - **21/23 bản ghi Hoàng Hà Mobile có giá tiền VNĐ lọt vào `network_type_norm`** cũng có **`combined_flag = False`**!
   - *Cách khắc phục*: Tại dòng 156–162 của [`src/anomaly_detection/detect_price_anomalies.py`](file:///d:/IT4930/src/anomaly_detection/detect_price_anomalies.py#L156-L162), bổ sung thêm các quy tắc kiểm tra miền vật lý phần cứng vào `rule_flag`:
     ```python
     # 1. Phát hiện kích thước màn hình phi vật lý (ví dụ 300.0 inch do lỗi parse "300 nits" hoặc iMac 21.5"-27" trong laptop)
     bad_lap_screen = (df["category_group"] == "laptop") & (
         df["screen_size_inch"].gt(20.0) | df["screen_size_inch"].lt(10.0)
     )
     bad_sma_screen = (df["category_group"] == "smartphone") & (
         df["screen_size_inch"].gt(11.0) | df["screen_size_inch"].lt(3.0)
     )
     # 2. Phát hiện máy bàn Apple iMac / Mac Studio / Mac mini lọt vào danh mục laptop
     is_desktop_in_laptop = (df["category_group"] == "laptop") & df["product_name"].astype(str).str.contains(
         r"\bimac\b|\bmac\s*studio\b|\bmac\s*mini\b|\bmac\s*pro\b", case=False, regex=True
     )
     # 3. Phát hiện ổ cứng laptop < 32GB (lỗi parse nhầm RAM sang ổ cứng) hoặc giá tiền lọt vào network_type_norm
     bad_lap_storage = (df["category_group"] == "laptop") & df["storage_gb"].lt(32.0)
     bad_network_val = df["network_type_norm"].astype(str).str.contains(r"₫|vnđ|\d+\.\d{3}\.\d{3}", case=False, regex=True)
     ```
3. **[P2 - Bổ sung Bảng Phân tích Độ nhạy (Sensitivity Analysis), Biểu đồ trực quan và Báo cáo Phần 9 chi tiết]**:
   - *Hiện trạng*: Tệp [`src/anomaly_detection/outputs/anomaly_report.md`](file:///d:/IT4930/src/anomaly_detection/outputs/anomaly_report.md) hiện mới dài 41 dòng, chưa có biểu đồ trực quan (như Scatter Plot `log(price)` vs `installed_ram_gb` tô màu theo `anomaly_severity`, hoặc Boxplot theo nhóm hãng) và chưa đính kèm bảng kết quả Sensitivity Analysis trên mô hình của TV5 (TV7 có thể đưa ngay số liệu thực nghiệm `S4 vs S5a vs S5b` ở phần TV5 bên trên vào báo cáo Phần 9!).
4. **[P1 - Cảnh báo Chống Rò rỉ Nhãn Mục tiêu (`_log_price`) khi Bàn giao sang TV5 & TV8]**:
   - *Nguyên tắc bắt buộc*: Do cả 3 cờ (`rule_flag`, `iqr_flag`, `isolation_forest_flag`) và `isolation_score` đều được tính từ biến mục tiêu `price_vnd` (`_log_price`), **TV5 và TV8 tuyệt đối không được đưa `isolation_score` hay `anomaly_flag` làm cột đặc trưng đầu vào $X$ của mô hình dự đoán giá** (vì tại thời điểm dự đoán cho một sản phẩm mới, hệ thống chưa biết `price_vnd`). Các cờ của TV7 chỉ được dùng để: **(1)** Lọc làm sạch hoặc phân tích độ nhạy trên tập Huấn luyện (Training Set Sensitivity Analysis), và **(2)** Đối chiếu chéo để giải thích các ca dự đoán có sai số lớn (Worst-Case Residuals) trên tập Kiểm thử ở TV8.

---

## PHẦN II — CHỈ DẪN CÔNG VIỆC TOÀN DIỆN & THỰC CHIẾN CHO TV8 (LÊ TRẦN ANH — `src/evaluation_demo/`)

- **Thành viên phụ trách**: **TV8 — Lê Trần Anh** (Phần 10: Đánh giá Mô hình Độc lập, Phân tích Lỗi Đa chiều, Giải thích Mô hình XAI & Xây dựng Ứng dụng Demo Streamlit)
- **Vai trò cốt lõi trước Hội đồng chấm**: TV8 là người tổng kết toàn bộ thành quả của cả nhóm (TV1 $\rightarrow$ TV7), trả lời bằng số liệu thực nghiệm và giao diện trực quan 3 câu hỏi lớn:
  1. *Mô hình nào tốt nhất trên Laptop và Smartphone khi xét toàn diện cả Độ chính xác (Accuracy), Tốc độ/Dung lượng (Efficiency) và Độ bền vững (Robustness)?*
  2. *Các nhánh công việc của TV2 (Làm sạch), TV3 (EDA), TV4 (Điểm chuẩn CPU/GPU & Đồ thị), TV6 (Cảm xúc đánh giá PhoBERT) và TV7 (Phát hiện bất thường) đã đóng góp định lượng bao nhiêu vào việc giảm sai số dự đoán giá (Ablation & Sensitivity Study)?*
  3. *Mô hình dự đoán dựa trên quy luật kỹ thuật nào (SHAP Global/Local & Monotonicity Check), sai nhiều nhất ở đâu, vì sao, và người dùng cuối tương tác với hệ thống trên Streamlit Demo như thế nào?*

---

### 2.1. Vị trí làm việc, Cấu trúc Thư mục & Danh sách Đầu vào từ TV2 – TV7

#### A. Vị trí làm việc bắt buộc của TV8
- **Thư mục mã nguồn & ứng dụng Demo**: `d:\IT4930\src\evaluation_demo\`
- **Thư mục báo cáo Phần 10**: `d:\IT4930\docs\tv8\report_part10_evaluation_demo.md`
- **Thư mục kiểm thử tự động**: `d:\IT4930\tests\test_tv8_evaluation_demo.py`

```text
src/evaluation_demo/
├── __init__.py
├── README.md                    # Hướng dẫn cài đặt và lệnh chạy đánh giá + chạy Streamlit demo
├── model_loader.py              # Nạp an toàn 6 mô hình .pkl của TV5 + sửa lỗi chuẩn hóa chữ hoa/thường
├── evaluate_models.py           # Đánh giá độc lập 6 mô hình (Accuracy, Efficiency, Robustness) + 4 lát cắt lỗi
├── ablation_sensitivity.py      # Thực nghiệm Ablation Study (TV2->TV3->TV4->TV6) & Sensitivity Analysis (TV7)
├── explainability.py            # Tính SHAP Global (Beeswarm, Bar), SHAP Local (Waterfall) & Monotonicity Test
├── app.py                       # Ứng dụng Streamlit Demo 4 Tab tương tác trực quan
└── outputs/
    ├── tables/
    │   ├── table_10_1_model_benchmark_3d.csv
    │   ├── table_10_2_ablation_and_tv7_sensitivity.csv
    │   ├── table_10_3_error_by_price_tier.csv
    │   ├── table_10_4_error_by_brand_and_seller.csv
    │   ├── table_10_5_error_by_stock_and_missingness.csv
    │   ├── table_10_6_cross_store_generalization.csv
    │   └── table_10_7_top20_worst_predictions_audit.csv
    └── figures/
        ├── fig_10_1_residual_and_actual_vs_pred.png
        ├── fig_10_2_error_by_price_tier_and_seller.png
        ├── fig_10_3_ablation_and_sensitivity_chart.png
        ├── fig_10_4_shap_summary_laptop.png
        ├── fig_10_5_shap_summary_smartphone.png
        ├── fig_10_6_shap_waterfall_examples.png
        └── fig_10_7_monotonicity_sanity_check.png
```

#### B. Danh sách các Tệp Đầu vào (Có sẵn 100% trên Git `main`) mà TV8 cần đọc
1. **Từ TV5 (`src/price_prediction/`)**:
   - 6 mô hình đã huấn luyện:
     - `src/price_prediction/models/results/lightgbm/lgbm_laptop.pkl` & `lgbm_smartphone.pkl`
     - `src/price_prediction/models/results/random_forest/rf_laptop.pkl` & `rf_smartphone.pkl`
     - `src/price_prediction/models/results/ridge/ridge_laptop.pkl` & `ridge_smartphone.pkl`
   - Các module tiền xử lý & chia tập: [`src/price_prediction/models/config.py`](file:///d:/IT4930/src/price_prediction/models/config.py), [`features.py`](file:///d:/IT4930/src/price_prediction/models/features.py), [`utils.py`](file:///d:/IT4930/src/price_prediction/models/utils.py).
   - Bảng dữ liệu làm sạch: [`data/processed/products_cleaned.jsonl`](file:///d:/IT4930/data/processed/products_cleaned.jsonl) (`8.374` dòng).
2. **Từ TV2 & TV3 (`data/processed/`)**:
   - [`data/processed/products_processed.jsonl`](file:///d:/IT4930/data/processed/products_processed.jsonl) (`10.316` dòng × `32` cột — lấy thêm `availability_status`, `charger_watt`, `source_parent_id`).
3. **Từ TV4 (`data/market_graph/`)**:
   - [`data/market_graph/laptop_benchmarks.csv`](file:///d:/IT4930/data/market_graph/laptop_benchmarks.csv) (`4.051` dòng — lấy cột **`cpu_perf_rating`**, **`gpu_perf_rating`** theo `listing_record_id`).
   - [`data/market_graph/smartphone_benchmarks.csv`](file:///d:/IT4930/data/market_graph/smartphone_benchmarks.csv) (`4.323` dòng — lấy cột **`cpu_benchmark_score`**, **`cpu_geekbench_5_multi`**, **`cpu_passmark`** theo `listing_record_id`).
4. **Từ TV6 (`data/tv6/`)**:
   - [`data/tv6/tv5_review_features.csv`](file:///d:/IT4930/data/tv6/tv5_review_features.csv) (hoặc `.parquet`, `7.051` dòng — lấy cột `has_review_data`, `review_count_usable`, `avg_sentiment_score`, `sentiment_positive_ratio`, `sentiment_net_score`, `aspect_sentiment_score_*` theo `source_parent_id`).
5. **Từ TV7 (`src/anomaly_detection/outputs/`)**:
   - [`src/anomaly_detection/outputs/anomaly_flags.csv`](file:///d:/IT4930/src/anomaly_detection/outputs/anomaly_flags.csv) (`10.316` dòng — lấy cột `rule_flag`, `iqr_flag`, `iqr_extreme_flag`, `isolation_forest_flag`, `isolation_score`, `methods_agree`, `combined_flag`, `anomaly_severity`, `anomaly_reasons` theo `listing_record_id`).

---

### 2.2. 4 Quy tắc Kỹ thuật & Chống Rò rỉ Bắt buộc cho TV8

1. **Quy tắc 1 — Khắc phục lỗi `sys.path` và thiếu thư viện khi nạp `.pkl` của TV5**:
   - Các tệp `.pkl` của TV5 được lưu khi thư mục làm việc là `src/price_prediction/models/` và import trực tiếp `from features import HardwareFeatureEngineer`. Do đó, mọi script của TV8 bắt buộc phải chạy `sys.path.insert(0, str(ROOT / "src" / "price_prediction" / "models"))` trước khi gọi `joblib.load()`.
   - Bổ sung vào [`requirements.txt`](file:///d:/IT4930/requirements.txt) các gói bắt buộc cho TV5 & TV8:
     ```text
     lightgbm>=4.0.0
     joblib>=1.3.0
     shap>=0.44.0
     streamlit>=1.32.0
     pyarrow>=15.0.0
     ```
2. **Quy tắc 2 — Khắc phục lỗi nhạy cảm chữ hoa/thường (`casing`) của TV5 khi chạy Streamlit Demo**:
   - Tuyệt đối không truyền chuỗi viết thường tự do (như `"apple"`, `"fpt shop"`) trực tiếp vào `model.predict()`. Bắt buộc bọc qua hàm `canonicalize_product_dict()` (xem code ở Mục 2.3 — Hạng mục 1) và dùng `st.selectbox` nạp danh sách các giá trị chuẩn từ tập huấn luyện của TV5.
3. **Quy tắc 3 — Chống Rò rỉ Nhãn Mục tiêu (Anti-Leakage) từ TV4 và TV7**:
   - **Đối với TV4**: Không bao giờ đưa `community_id`, `segment_label`, `price_band`, `price_median` từ `canonical_products_segmented.csv` / `louvain_segments.csv` vào làm đặc trưng dự đoán giá.
   - **Đối với TV7**: Không bao giờ đưa `isolation_score`, `anomaly_flag`, `combined_flag` làm cột đầu vào $X$ khi dự đoán giá (vì các cột này được tính từ `_log_price`). Chỉ dùng cờ của TV7 để: (a) lọc tập Train trong bài toán Sensitivity Analysis, và (b) đối chiếu giải thích nguyên nhân cho Top-20 ca dự đoán sai lệch lớn nhất trên tập Test!
4. **Quy tắc 4 — Tái tạo chính xác 100% Tập Kiểm thử Độc lập (Held-out Test Set) của TV5**:
   - Phải gọi đúng hàm `load_and_split_data()` và `split_by_group()` từ `src/price_prediction/models/features.py` và `utils.py` (`GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)` theo `source_parent_id`) để thu được chính xác **`819` mẫu Test Laptop** và **`797` mẫu Test Smartphone** hoàn toàn độc lập với tập Train.

---

### 2.3. Chi tiết 5 Hạng mục Công việc TV8 Cần Thực hiện & Làm Thế Nào (Kèm Code Mẫu)

#### Hạng mục 1: Xây dựng `src/evaluation_demo/model_loader.py` (Nạp Mô hình & Chuẩn hóa Đầu vào)

Tạo tệp `src/evaluation_demo/model_loader.py` để làm cổng giao tiếp duy nhất với các mô hình `.pkl` của TV5:

```python
# src/evaluation_demo/model_loader.py
from __future__ import annotations

import sys
from pathlib import Path
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TV5_MODELS_DIR = ROOT / "src" / "price_prediction" / "models"
if str(TV5_MODELS_DIR) not in sys.path:
    sys.path.insert(0, str(TV5_MODELS_DIR))

from config import (  # noqa: E402
    CLEANED_DATA_PATH,
    PROCESSED_DATA_PATH,
    LAPTOP_CAT_FEATURES,
    SMARTPHONE_CAT_FEATURES,
)
from features import load_and_split_data  # noqa: E402
from utils import prepare_raw_data, split_by_group  # noqa: E402

MODEL_REGISTRY = {
    "laptop": {
        "lgbm": TV5_MODELS_DIR / "results" / "lightgbm" / "lgbm_laptop.pkl",
        "rf": TV5_MODELS_DIR / "results" / "random_forest" / "rf_laptop.pkl",
        "ridge": TV5_MODELS_DIR / "results" / "ridge" / "ridge_laptop.pkl",
    },
    "smartphone": {
        "lgbm": TV5_MODELS_DIR / "results" / "lightgbm" / "lgbm_smartphone.pkl",
        "rf": TV5_MODELS_DIR / "results" / "random_forest" / "rf_smartphone.pkl",
        "ridge": TV5_MODELS_DIR / "results" / "ridge" / "ridge_smartphone.pkl",
    },
}

SELLER_ALIASES = {
    "fpt shop": "FPT",
    "fptshop": "FPT",
    "fpt": "FPT",
    "tgdd": "TGDĐ",
    "the gioi di dong": "TGDĐ",
    "thế giới di động": "TGDĐ",
    "cellphones": "CellphoneS",
    "cellphone s": "CellphoneS",
    "hoangha": "HoangHa",
    "hoanghamobile": "HoangHa",
    "hoàng hà mobile": "HoangHa",
    "viettel": "Viettel",
    "viettelstore": "Viettel",
    "viettel store": "Viettel",
}


def get_tv5_datasets():
    """Trả về (df_laptop, df_smartphone) đúng chuẩn pipeline TV5."""
    return load_and_split_data(CLEANED_DATA_PATH, PROCESSED_DATA_PATH)


def build_canonical_lookup(df_cat: pd.DataFrame, category: str) -> dict[str, dict[str, str]]:
    """Tạo bảng tra cứu không phân biệt hoa/thường cho toàn bộ biến phân loại của TV5."""
    cat_cols = LAPTOP_CAT_FEATURES if category == "laptop" else SMARTPHONE_CAT_FEATURES
    lookup: dict[str, dict[str, str]] = {}
    for col in cat_cols:
        if col in df_cat.columns:
            unique_vals = df_cat[col].dropna().astype(str).unique()
            lookup[col] = {v.strip().lower(): v for v in unique_vals}
    return lookup


def canonicalize_input(
    product_info: dict, lookup: dict[str, dict[str, str]]
) -> dict:
    """Chuẩn hóa chữ hoa/thường và tên sàn bán lẻ khớp 100% với tập huấn luyện của TV5."""
    cleaned = dict(product_info)
    if "seller_name" in cleaned and cleaned["seller_name"] is not None:
        s_key = str(cleaned["seller_name"]).strip().lower()
        if s_key in SELLER_ALIASES:
            cleaned["seller_name"] = SELLER_ALIASES[s_key]

    for col, mapping in lookup.items():
        if col in cleaned and cleaned[col] is not None:
            val_key = str(cleaned[col]).strip().lower()
            if val_key in mapping:
                cleaned[col] = mapping[val_key]
    return cleaned


def load_trained_model(category: str, model_key: str = "lgbm"):
    path = MODEL_REGISTRY[category.lower()][model_key.lower()]
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file model: {path}")
    return joblib.load(path)
```

---

#### Hạng mục 2: Đánh giá Độc lập 6 Mô hình trên 3 Chiều & Phân tích Lỗi 4 Lát cắt (`src/evaluation_demo/evaluate_models.py`)

TV8 viết kịch bản `src/evaluation_demo/evaluate_models.py` thực hiện:

1. **Bảng 10.1 — Đánh giá 3 Chiều (Accuracy – Efficiency – Robustness) cho cả 6 Mô hình (`.pkl`)**:
   - **Accuracy Metrics** trên tập Test (`819` Laptop, `797` Smartphone):
     - `MAE` (VNĐ), `MdAE` (Median Absolute Error — VNĐ), `RMSE` (VNĐ), `MAPE` (%), `MdAPE` (%), `R2`.
     - *(Ghi chú kết quả thực nghiệm đã xác minh để TV8 đối chiếu)*:
       - **Laptop (`n = 819`)**:
         - `LightGBM`: `MAE = 3.768.480`, `RMSE = 6.858.651`, `R2 = 0,8886` (File size: `2,37 MB`).
         - `Random Forest`: `MAE = 4.073.539`, `MdAE = 2.327.207`, `RMSE = 7.486.733`, `MAPE = 12,55%`, `MdAPE = 9,73%`, `R2 = 0,8673` (File size: `47,91 MB`).
         - `Ridge`: `MAE = 4.945.224`, `MdAE = 2.966.610`, `RMSE = 8.692.758`, `MAPE = 15,76%`, `MdAPE = 11,50%`, `R2 = 0,8211` (File size: `0,06 MB`).
       - **Smartphone (`n = 797`)**:
         - `Random Forest`: `MAE = 2.643.627`, `MdAE = 1.254.699`, `RMSE = 6.757.150`, `MAPE = 19,32%`, `MdAPE = 14,85%`, `R2 = 0,8317` (File size: `31,76 MB`).
         - `LightGBM`: `MAE = 2.510.216`, `RMSE = 7.373.367`, `R2 = 0,7996` (File size: `0,63 MB`).
         - `Ridge`: `MAE = 2.681.182`, `MdAE = 1.326.593`, `RMSE = 7.342.246`, `MAPE = 21,56%`, `MdAPE = 14,63%`, `R2 = 0,8013` (File size: `0,03 MB`).
   - **Efficiency Metrics**: Thời gian suy luận trung bình 1 mẫu (`latency_ms_per_sample` dùng `time.perf_counter()`) và dung lượng tệp `.pkl` (`model_size_mb`).
   - **Robustness Stress Test**: Khi ẩn ngẫu nhiên `20%` giá trị `ram_gb` và `storage_gb` trên tập Test thành `np.nan`, đo mức tăng $\Delta \text{MAE}$ (%) để chứng minh cơ chế `by_brand_medians_` trong `HardwareFeatureEngineer` giúp mô hình không bị sụp đổ khi người dùng nhập thiếu cấu hình.
2. **Phân tích Sai số Cắt lát Đa chiều (Sliced Error Analysis — Bảng 10.3 đến 10.6)**:
   - **Lát cắt 1 — Theo 4 Phân khúc Giá (`price_tier`)**: Giá rẻ (`< 10M`), Tầm trung (`10–20M`), Cận cao cấp (`20–35M`), Cao cấp/Flagship (`> 35M`).
   - **Lát cắt 2 — Theo Thương hiệu (`brand`) & Sàn bán lẻ (`seller_name`)**: Tính cả sai số tuyệt đối (`MAE`, `MAPE`) lẫn **Sai số có dấu trung bình ($\text{Mean Signed Error} = \frac{1}{N}\sum (\hat{y}_i - y_i)$)** để chỉ ra thương hiệu nào bị dự đoán thấp hơn thực tế (*Under-predicted*) hoặc cao hơn thực tế (*Over-predicted*).
   - **Lát cắt 3 — Theo Trạng thái Tồn kho (`availability_status`: `in_stock` vs `out_of_stock`) và Tình trạng Khuyết Thông số (`is_ram_missing == 0` vs `1`)**.
   - **Lát cắt 4 — Kiểm định Khả năng Tổng quát hóa Liên sàn (`table_10_6_cross_store_generalization.csv`)**: So sánh sai số trên các mẫu Test có cấu hình `(brand, model_clean, ram_gb, storage_gb)` **chưa từng xuất hiện ở bất kỳ sàn nào trong tập Train** vs. các mẫu **đã xuất hiện ở một sàn khác trong tập Train**.
3. **Bảng 10.7 — Kiểm toán Top-20 Ca Dự đoán Sai lệch Lớn nhất (`|y_true - y_pred|` Worst-Case Audit) Kết hợp Cờ Bất thường của TV7**:
   - Ghép kết quả dự đoán trên tập Test với [`src/anomaly_detection/outputs/anomaly_flags.csv`](file:///d:/IT4930/src/anomaly_detection/outputs/anomaly_flags.csv) theo `listing_record_id`.
   - Với 20 sản phẩm có $|y_i - \hat{y}_i|$ lớn nhất, hiển thị rõ cột `anomaly_severity`, `anomaly_reasons` của TV7 và phân loại nguyên nhân gốc rễ:
     - *(a) Lỗi danh mục / thông số*: Ví dụ máy bàn Apple iMac lọt vào `laptop`.
     - *(b) Siêu phẩm Flagship / Workstation hiếm gặp*: Ví dụ laptop gaming `> 120 triệu` VNĐ hoặc điện thoại gập/1TB mà TV7 đã gắn cờ `iqr_flag` / `isolation_forest_flag`.
     - *(c) Chênh lệch giá niêm yết giữa các nhà bán lẻ*.

---

#### Hạng mục 3: Thực nghiệm Ablation Study & Phân tích Độ nhạy Bất thường (`src/evaluation_demo/ablation_sensitivity.py`)

TV8 đóng gói đoạn mã thực nghiệm tích hợp đa thành viên ở phần TV5 của tài liệu này thành tệp `src/evaluation_demo/ablation_sensitivity.py` để xuất tự động bảng `table_10_2_ablation_and_tv7_sensitivity.csv` và biểu đồ `fig_10_3_ablation_and_sensitivity_chart.png` qua 6 cấp độ:
- **Stage 1**: Baseline TV5 (`products_cleaned.jsonl` + `HardwareFeatureEngineer`).
- **Stage 2 (+ TV3 EDA Insights)**: Thêm `is_out_of_stock`, `charger_watt`, lọc `screen_size_inch = 300.0`.
- **Stage 3 (+ TV4 Hardware Benchmarks & Price-Free Graph)**: Thêm `cpu_perf_rating`, `gpu_perf_rating` (Laptop) / `cpu_benchmark_score`, `cpu_geekbench_5_multi` (Smartphone) + `hw_seller_count` *(tuyệt đối không dùng `louvain_segment`)*.
- **Stage 4 (+ TV6 Review NLP & Brand Sentiment Prior)**: Thêm `review_count_usable`, `avg_sentiment_score`, `sentiment_positive_ratio`, `aspect_sentiment_score_*` và `brand_sentiment_prior` (tính trên tập Train).
- **Stage 5a (+ TV7 Sensitivity — Lọc `extreme` Anomalies trên tập Train)**: Chứng minh lọc đúng dị biệt cực đoan giúp giữ vững/cải thiện MAE trên Laptop (`3.975.005 VNĐ`).
- **Stage 5b (+ TV7 Sensitivity — Lọc toàn bộ `combined_flag` trên tập Train)**: Chứng minh thực nghiệm vì sao xóa toàn bộ `combined_flag` (gồm cả 73 flagship `>= 80M VNĐ`) làm tụt $R^2$, khẳng định tính đúng đắn của quy tắc *"không tự động xóa mọi điểm bất thường"* trong đề bài!

---

#### Hạng mục 4: Giải thích Mô hình bằng SHAP (Global & Local) và Kiểm thử Tính Đơn điệu (`src/evaluation_demo/explainability.py`)

TV8 tạo tệp `src/evaluation_demo/explainability.py` thực hiện 3 chức năng:
1. **Giải thích Toàn cục (Global SHAP)**:
   - Bóc tách `pipeline = model_ttr.regressor_`, lấy `fe = pipeline.named_steps['fe']`, `estimator = pipeline.named_steps['model']` (và `preprocessor = pipeline.named_steps['preprocessor']` đối với Random Forest) để tính `shap.TreeExplainer(estimator)`.
   - Xuất biểu đồ **SHAP Summary Beeswarm Plot** và **SHAP Mean `|SHAP|` Bar Plot** cho `Laptop` và `Smartphone` (`fig_10_4_shap_summary_laptop.png`, `fig_10_5_shap_summary_smartphone.png`).
2. **Giải thích Cục bộ (Local SHAP Waterfall) & Quy đổi sang Tiền VNĐ**:
   - Với một sản phẩm cụ thể, quy đổi đóng góp SHAP $\phi_j$ từ thang log-giá $z = \ln(1 + y)$ sang số tiền VNĐ dễ hiểu cho người dùng cuối theo công thức:
     $$\Delta \text{VND}_j = (\hat{y} - y_{\text{base}}) \times \frac{\phi_j}{\sum_{k} \phi_k}, \quad \text{với } y_{\text{base}} = \exp(\mathbb{E}[z]) - 1$$
   - Xuất `fig_10_6_shap_waterfall_examples.png` cho 3 mẫu máy đại diện (1 máy giá rẻ `< 10M`, 1 máy tầm trung `~20M`, 1 máy cao cấp `> 40M`).
3. **Kiểm thử Tính Hợp lý Nghiệp vụ & Tính Đơn điệu (Monotonicity Sanity Check — `fig_10_7_monotonicity_sanity_check.png`)**:
   - Cố định một cấu hình Laptop chuẩn (ví dụ: `ASUS VivoBook 15, Core i5-13500H, 15.6 inch`) và một Smartphone chuẩn (`Apple iPhone 15, Apple A16 Bionic, 6.1 inch`), thay đổi tuần tự:
     - `ram_gb`: `8` $\rightarrow$ `16` $\rightarrow$ `32` $\rightarrow$ `64` GB
     - `storage_gb`: `128` $\rightarrow$ `256` $\rightarrow$ `512` $\rightarrow$ `1024` GB
   - Vẽ đường biểu diễn giá dự đoán của `Ridge`, `Random Forest`, `LightGBM` để kiểm tra tính đơn điệu tăng theo dung lượng phần cứng.

---

#### Hạng mục 5: Xây dựng Ứng dụng Streamlit Demo 4 Tab (`src/evaluation_demo/app.py`)

Ứng dụng khởi chạy bằng lệnh `streamlit run src/evaluation_demo/app.py` cần được thiết kế trực quan, xử lý an toàn mọi đầu vào thiếu hoặc không hợp lệ, gồm **4 Tab**:

1. **Tab 1 — Dự đoán Giá Thông minh & Giải thích SHAP Trực tiếp (Interactive Price Predictor)**:
   - Người dùng chọn **Loại thiết bị** (`Laptop` / `Smartphone`) và **Mô hình** (`LightGBM`, `Random Forest`, `Ridge`).
   - Các trường phân loại (`Thương hiệu`, `Dòng máy`, `CPU`, `GPU`, `Công nghệ màn hình`, `Nhà bán lẻ`) dùng `st.selectbox` nạp từ danh sách giá trị chuẩn trong tập huấn luyện của TV5 (kết hợp `canonicalize_input()` để triệt tiêu lỗi chữ hoa/thường); các trường số (`RAM GB`, `SSD/ROM GB`, `Kích thước màn hình inch`, `Pin`, `Camera MP`) dùng `st.number_input` / `st.slider` có kiểm tra miền hợp lệ (`RAM: 2–128 GB`, `ROM: 32–4096 GB`, `Màn hình Laptop: 10–18.5 inch`, `Smartphone: 4.0–8.5 inch`) và cho phép để trống (pipeline tự điền trung vị theo hãng).
   - **Kết quả hiển thị**:
     - **Giá dự đoán (VNĐ)** + **Khoảng tham chiếu tin cậy** ($\hat{y} \times [1 - \text{MdAPE}, 1 + \text{MdAPE}]$).
     - **Biểu đồ đóng góp SHAP (VNĐ)** chỉ rõ linh kiện nào làm tăng/giảm giá bao nhiêu triệu đồng so với mức giá cơ sở.
     - **Bảng đối chiếu 5 sản phẩm thực tế gần nhất trên thị trường** (lọc từ `products_cleaned.jsonl` + `anomaly_flags.csv`) kèm giá bán thực tế tại từng sàn và cảnh báo nếu có cờ bất thường của TV7.
2. **Tab 2 — Bảng Xếp hạng Mô hình 3 Chiều & Đóng góp Toàn Nhóm (Model Benchmark & Ablation Study)**:
   - Hiển thị bảng và biểu đồ so sánh `Ridge`, `Random Forest`, `LightGBM` trên 3 chiều (Accuracy, Efficiency, Robustness).
   - Hiển thị biểu đồ **Ablation Study (`S1` $\rightarrow$ `S4`)** và **TV7 Sensitivity Analysis (`S5a`, `S5b`)** chứng minh giá trị kết tinh từ TV2, TV3, TV4, TV5, TV6, TV7.
3. **Tab 3 — Phân tích Sai số Cắt lát & Kiểm toán Ca Dị biệt (Error Diagnostics & Anomaly Explorer)**:
   - Hiển thị biểu đồ Residual Plot, sai số theo Phân khúc giá / Thương hiệu / Sàn bán lẻ / Tồn kho, và bảng tương tác Top-20 ca sai số lớn nhất có gắn kèm cờ `anomaly_severity` và `anomaly_reasons` của TV7.
4. **Tab 4 — Giải thích Toàn cục & Kiểm thử Tính Đơn điệu (Global Explainability & Monotonicity)**:
   - Hiển thị biểu đồ SHAP Summary Beeswarm của Laptop & Smartphone và biểu đồ đường cong kiểm thử tính đơn điệu khi nâng cấp RAM / ROM.

---

### 2.4. Danh mục Hiện vật Bàn giao (Deliverables Checklist) của TV8

- [ ] **Cập nhật [`requirements.txt`](file:///d:/IT4930/requirements.txt)**: Đảm bảo có đủ `lightgbm`, `joblib`, `shap`, `streamlit`, `pyarrow`.
- [ ] **Mã nguồn trong `src/evaluation_demo/`**:
  - [ ] `model_loader.py` (nạp đủ 6 mô hình `.pkl`, tích hợp `canonicalize_input` sửa lỗi chữ hoa/thường).
  - [ ] `evaluate_models.py` (tính đủ `MAE`, `MdAE`, `RMSE`, `MAPE`, `MdAPE`, `R2`, `Latency`, `Model Size`, `Robustness` và 4 lát cắt lỗi).
  - [ ] `ablation_sensitivity.py` (chứng minh đóng góp của TV2, TV3, TV4, TV6, TV7 không rò rỉ giá).
  - [ ] `explainability.py` (SHAP Global, SHAP Local quy đổi VNĐ, Monotonicity Sanity Check).
  - [ ] `app.py` + `README.md` (ứng dụng Streamlit 4 Tab kèm hướng dẫn cài đặt và chạy demo).
- [ ] **Hiện vật Bảng (`src/evaluation_demo/outputs/tables/*.csv`, 7 bảng)** và **Biểu đồ (`src/evaluation_demo/outputs/figures/*.png`, 7 hình 300 DPI)**.
- [ ] **Báo cáo Phần 10 (`docs/tv8/report_part10_evaluation_demo.md`)** kèm ảnh chụp màn hình giao diện Streamlit Demo.
- [ ] **Kiểm thử tự động (`tests/test_tv8_evaluation_demo.py`)**: Kiểm tra nạp mô hình, kiểm tra `canonicalize_input("apple", "fpt shop")` trả về đúng giá `~24,89M VNĐ` (không bị tụt xuống `14,31M VNĐ`), và kiểm tra sự tồn tại của các bảng/biểu đồ đầu ra.
