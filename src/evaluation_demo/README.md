# Hệ thống Hỗ trợ Quyết định Thị trường & Thẩm định Giá Hợp lý Đa sàn (TV8 — IT4930)

Ứng dụng Streamlit tại `src/evaluation_demo/app.py` là giao diện tích hợp cuối cùng của dự án **IT4930 — Nhập môn Khoa học Dữ liệu (Nhóm 12)**, kết nối trọn vẹn đầu ra phân tích của cả **8 thành viên (TV1–TV8)** thành một nền tảng **Trí tuệ Dữ liệu Thị trường & Thẩm định Giá Hợp lý (E-Commerce Tech Market Intelligence & Fair-Value Analytics)** cho hai ngành hàng **Laptop** và **Smartphone** trên 5 hệ thống bán lẻ lớn tại Việt Nam (`CellphoneS`, `Thế Giới Di Động`, `FPT Shop`, `Hoàng Hà Mobile`, `Viettel Store`).

---

## 1. Khởi chạy nhanh trên máy cục bộ

Mở terminal tại thư mục gốc của kho Git, kích hoạt môi trường ảo Python rồi chạy:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run src/evaluation_demo/app.py --server.address 127.0.0.1
```

Mở địa chỉ `http://127.0.0.1:8501` trên trình duyệt nếu chưa tự động bật. Dừng ứng dụng bằng `Ctrl+C` trong terminal.

---

## 2. Kiến trúc 5 Tab Nghiệp vụ Khoa học Dữ liệu

1. **Tab 1 — `Tổng quan & Quy luật giá (TV1–TV3)`**
   - Hiển thị 6 KPI toàn cảnh thị trường đọc trực tiếp từ dữ liệu đã kiểm toán (`10.316` dòng niêm yết, `15.805` đánh giá với `14.869` văn bản hợp lệ, `4.414` sản phẩm chuẩn hóa liên sàn, `8.132` bản ghi sạch đủ điều kiện định giá).
   - Trình bày đầy đủ **15 biểu đồ EDA chuẩn 300 DPI** chia theo 4 chủ đề lớn. Mỗi biểu đồ đi kèm khung diễn giải 3 bước bắt buộc: **Câu hỏi nghiệp vụ → Phát hiện định lượng → Ý nghĩa kinh doanh & Quyết định phân tích**, cùng bảng CSV gốc thu gọn bên dưới.

2. **Tab 2 — `Cạnh tranh đa sàn & Review (TV4 & TV6)`**
   - **Cạnh tranh đa sàn (TV4)**: Bảng vị thế cạnh tranh của 5 nhà bán lẻ (độ rộng danh mục, tỷ lệ độc quyền, tỷ lệ dẫn đầu giá rẻ, mức chênh giá trung bình), ma trận trùng lặp danh mục **Jaccard**, bảng phân khúc thị trường tự nhiên **Louvain** (`63` phân khúc), bộ lọc tương tác **90 khoảng trống thị trường (`structural_holes.csv`)** gồm `68` điểm mù danh mục nhà bán lẻ (`retailer_blind_spot`) và `22` phân khúc cầu cao – ít sàn bán (`underserved_high_demand`), cùng đồ thị hai phía tương tác **PyVis HTML**.
   - **Tiếng nói khách hàng (TV6)**: Đối sánh mô hình phân loại cảm xúc tiếng Việt **PhoBERT** (`Macro F1 = 0,6491`, `Accuracy = 92,23%`) với Baseline ML, bảng **5 chủ đề tiềm ẩn LDA**, ma trận **5 khía cạnh kỹ thuật ABSA** (chỉ rõ điểm nghẽn số 1 là *Hiệu năng & Tản nhiệt* với `21,34%–21,70%` phàn nàn tiêu cực), và hiện tượng *lạm phát 5 sao* (`84,79%` đánh giá 5★).

3. **Tab 3 — `Thẩm định giá hợp lý (TV5–TV8)`** *(Trọng tâm ứng dụng B2C & B2B)*
   - **Chế độ 1 (Mặc định — B2C & B2B): Thẩm định SKU đang niêm yết thực tế trên 5 sàn**
     - Người dùng lọc theo Ngành hàng, Nhà bán lẻ, Thương hiệu, Mức cờ kiểm toán TV7 hoặc từ khóa để chọn trực tiếp một trong `8.132` SKU đang bán thực tế (không cần tự gõ tay cấu hình).
     - Hệ thống đối chiếu **Giá niêm yết thực tế** với **Giá hợp lý theo cấu hình (Hedonic Fair Value)** từ mô hình TV5 (`LightGBM`, `Random Forest`, `Ridge`), tính độ lệch VNĐ & `%` so với ngưỡng `±MdAPE`, kết luận *Giá hời / Hợp lý / Cao hơn mặt bằng cấu hình*, giải thích nhân tố đóng góp giá bằng **SHAP VNĐ**, hiển thị hồ sơ kiểm toán `anomaly_type` & `recommended_action` (TV7), tóm tắt đánh giá khách hàng (TV6) và bảng 5 SKU tương đương trên các sàn.
   - **Chế độ 2 (B2B Category Manager): Mô phỏng định giá SKU mới (Ràng buộc phần cứng tương thích)**
     - Hỗ trợ bộ phận thu mua / quản trị ngành hàng ước lượng giá hợp lý cho cấu hình dự kiến nhập mới.
     - Hàm `build_compatibility_options()` tự động lọc phân tầng **Thương hiệu → Dòng máy → CPU tương thích → GPU / RAM / Bộ nhớ / Màn hình / Chuẩn mạng tương thích**, chặn hoàn toàn các tổ hợp phi vật lý (như chọn hãng `Apple` với chip `Snapdragon` hay card rời `RTX`). Tùy chọn mở rộng RAM/ROM ngoài cấu hình đã thấy luôn đi kèm cảnh báo ngoại suy ngoài phân phối dữ liệu huấn luyện.

4. **Tab 4 — `Kiểm toán bất thường (TV7)`**
   - Bảng đối chiếu 3 phương pháp phát hiện bất thường (`Rule-based`: `494`, `Log-price IQR`: `156`, `Isolation Forest`: `172`, hợp nhất `715` bản ghi = `6,93%`).
   - Phân rã thành 4 bản chất nghiệp vụ (`low_price_or_category_noise`: `401`, `spec_price_mismatch_review`: `156`, `hardware_spec_error`: `93`, `rare_valid_flagship`: `65`) với khuyến nghị xử lý riêng (`recommended_action`), biểu đồ phân bố `log(giá)` theo `RAM`, và bộ lọc tra cứu chi tiết toàn bộ `10.316` bản ghi.

5. **Tab 5 — `Đánh giá mô hình & XAI (TV8)`**
   - **Benchmark 3 chiều & Ablation (S1–S5)**: Độ chính xác (`MAE`, `RMSE`, `MdAPE`, `R²`), tốc độ suy luận, dung lượng mô hình, độ bền vững khi khuyết 20% RAM/ROM ([Bảng 10.1](outputs/tables/table_10_1_model_benchmark_3d.csv)), chuỗi thực nghiệm đóng góp dữ liệu liên thành viên `S1 → S2A → S3 → S4` và phân tích độ nhạy lọc cờ TV7 `S5a/S5b` ([Bảng 10.2](outputs/tables/table_10_2_ablation_and_tv7_sensitivity.csv)).
   - **Phân tích sai số đa chiều**: Đồ thị phần dư, lát cắt sai số theo khoảng giá, hãng, sàn bán, tồn kho, độ phủ liên sàn và kiểm toán 20 ca lệch lớn nhất ([Bảng 10.7](outputs/tables/table_10_7_top20_worst_predictions_audit.csv)).
   - **Giải thích mô hình toàn cục & Kiểm định đơn điệu**: Biểu đồ TreeSHAP tổng quan cho Laptop & Smartphone, 3 ca giải thích waterfall điển hình và phép thử tính đơn điệu khi nâng bậc thang RAM/Bộ nhớ.

---

## 3. Cấu trúc mã nguồn phân hệ `src/evaluation_demo/`

| Tệp | Chức năng |
|---|---|
| `app.py` | Ứng dụng Streamlit 5 tab tích hợp toàn diện TV1–TV8 |
| `market_data.py` | Tầng nạp dữ liệu an toàn và từ điển diễn giải nghiệp vụ 3 bước cho TV3, TV4, TV6, TV7 |
| `demo_data.py` | Tầng phục vụ mô hình TV5, làm giàu catalog 8.132 dòng, kiểm toán `audit_listing_fair_value()`, ràng buộc phần cứng `build_compatibility_options()` và giải thích SHAP VNĐ cục bộ |
| `model_loader.py` | Nạp an toàn 6 pipeline `.pkl` của TV5 và chuẩn hóa bí danh nhãn đầu vào (`canonicalize_input`) |
| `prepare_test_data.py` | Tái tạo phép chia `GroupShuffleSplit` theo `source_parent_id` đồng bộ `listing_id_crosswalk.csv` |
| `evaluate_models.py` | Tính toán Bảng 10.1 và các bảng phân tích sai số lát cắt 10.3–10.7 |
| `ablation_sensitivity.py` | Chuỗi thực nghiệm có kiểm soát `S1–S5` đánh giá giá trị gia tăng của TV3, TV4, TV6, TV7 |
| `explainability.py` | Trích xuất TreeSHAP toàn cục, quy đổi đóng góp sang VNĐ và kiểm định tính đơn điệu |

---

## 4. Kiểm thử tự động & Tái lập hiện vật

Chạy bộ kiểm thử hồi quy và giao diện từ thư mục gốc của dự án:

```powershell
python -m pytest tests/test_tv8_evaluation_demo.py -q
```

Nếu cần tái tạo lại các bảng thống kê và biểu đồ đánh giá trong `src/evaluation_demo/outputs/`:

```powershell
python src/evaluation_demo/evaluate_models.py
python src/evaluation_demo/ablation_sensitivity.py --stage all
python src/evaluation_demo/explainability.py
& .\src\evaluation_demo\plot_error_diagnostics.ps1
& .\src\evaluation_demo\plot_explainability.ps1
```

Xem chi tiết luận giải số liệu tại [Báo cáo Phần 10](../../docs/evaluation_demo/report_part10_evaluation_demo.md) và báo cáo tổng hợp toàn dự án tại [BAO_CAO_KHOA_HOC_DU_LIEU_IT4930_NHOM12.md](../../docs/BAO_CAO_KHOA_HOC_DU_LIEU_IT4930_NHOM12.md).
