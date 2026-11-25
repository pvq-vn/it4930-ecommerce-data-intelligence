# IT4930 — Hệ thống Trí tuệ Dữ liệu Thị trường & Thẩm định Giá Hợp lý Sản phẩm Công nghệ Đa sàn
*(E-Commerce Tech Market Intelligence & Fair-Value Analytics Platform)*

> **Học phần**: IT4930 — Nhập môn Khoa học Dữ liệu (Đại học Bách Khoa Hà Nội)  
> **Giảng viên hướng dẫn**: Nguyễn Văn Sơn  
> **Nhóm thực hiện**: Nhóm 12 (8 thành viên — TV1 đến TV8)

---

## 1. Định vị Dự án Khoa học Dữ liệu (Data Science vs. Pure Machine Learning)

Thị trường bán lẻ thiết bị công nghệ tại Việt Nam (**Laptop** và **Smartphone**) có mức độ phân mảnh rất cao giữa các chuỗi lớn (**CellphoneS, Thế Giới Di Động, FPT Shop, Hoàng Hà Mobile, Viettel Store**): cùng một dòng sản phẩm nhưng tồn tại hàng chục biến thể cấu hình, chính sách giá gạch/khuyến mãi khác nhau, hàng ngừng kinh doanh lưu giá cũ (*price drift*), thông số kỹ thuật khuyết thiếu không đồng nhất và hiện tượng *lạm phát đánh giá 5 sao* (`84,79%`).

Khác với một đồ án Học máy thuần túy (chỉ tập trung huấn luyện hàm dự đoán giá từ thông số nhập tay), dự án này triển khai **trọn vẹn chu trình Khoa học Dữ liệu (Data Science Lifecycle)** nhằm giải quyết **5 câu hỏi nghiệp vụ cốt lõi** cho cả **Người tiêu dùng / Đơn vị thu mua (B2C)** và **Quản trị ngành hàng bán lẻ (B2B)**:

1. **Quy luật cấu thành giá & Vệ sinh dữ liệu (TV1–TV3)**: Cấu trúc thị phần, chiến lược chiết khấu niêm yết của 5 sàn ra sao? Thông số nào thực sự chi phối giá bán và thông số nào là "con số quảng cáo hào nhoáng" (*Pin 5.000 mAh, Camera 108 MP, Màn hình 15,6 inch*)?
2. **Cấu trúc cạnh tranh & Khoảng trống danh mục liên sàn (TV4)**: Khi đối sánh thực thể sản phẩm chuẩn hóa liên sàn (`4.414` sản phẩm chuẩn), sàn nào dẫn đầu về độ phủ và giá rẻ? Đâu là **90 khoảng trống thị trường** (*điểm mù danh mục* và *phân khúc cầu cao nhưng ít sàn bán*)?
3. **Tiếng nói thực chất của khách hàng sau mua (TV6)**: Sau lớp vỏ bọc `84,79%` đánh giá 5 sao trên web, khách hàng Việt Nam thực sự hài lòng và phàn nàn về khía cạnh kỹ thuật nào (*tản nhiệt, pin, màn hình, camera hay dịch vụ giao nhận*)?
4. **Kiểm toán chất lượng danh mục & Dị biệt giá (TV7)**: Làm sao phân biệt tự động giữa **lỗi dữ liệu/sai danh mục** (`401` mẫu giá dưới sàn/phụ kiện, `93` lỗi thông số phần cứng) với **siêu phẩm cấu hình cao hợp lệ** (`65` workstation/flagship) và **nghi vấn lệch giá–cấu hình** (`156` mẫu) mà không xóa nhầm dữ liệu quý?
5. **Thẩm định Giá Hợp lý (Hedonic Fair-Value Audit) & Hỗ trợ Quyết định (TV5 & TV8)**: Với một SKU đang niêm yết sẵn giá trên sàn, mức giá đó đang **hời (undervalued)**, **hợp lý (fair)** hay **đắt hơn mặt bằng cấu hình (overvalued)** bao nhiêu tiền, và linh kiện/yếu tố thương hiệu nào tạo ra khoản chênh lệch đó (giải thích bằng **SHAP quy đổi ra VNĐ**)?

---

## 2. Kiến trúc Quy trình Khoa học Dữ liệu 8 Thành viên (TV1 → TV8)

| Phân hệ | Thành viên phụ trách | Vai trò trong vòng đời Khoa học Dữ liệu | Đầu ra định lượng & Hiện vật cốt lõi |
|---|---|---|---|
| **TV1** | Phạm Văn Quyết (`202416331`) | Thu thập dữ liệu đa nguồn bất biến (*Multi-Source Acquisition*) | `10.316` listings (`25` trường raw) & `15.805` reviews (`19` trường raw) từ 5 sàn trong `data/raw/` |
| **TV2** | Hà Đức Anh (`20235001`) | Quản trị chất lượng dữ liệu & Tích hợp 5 tầng (*Data Governance & Star Schema*) | Pipeline 11 bước `raw → staging → silver_v2 → gold_v2 → processed`, nguyên lý *flag-don't-drop*, `listing_id_crosswalk.csv` |
| **TV3** | Hoàng Phúc Hưng (`202416216`) | Phân tích khám phá & Kiểm định thống kê (*EDA & Hypothesis Testing*) | `15` biểu đồ 300 DPI, `36+` bảng kiểm định Spearman / Kruskal-Wallis / Mann-Whitney / VIF (`src/eda/outputs/`) |
| **TV4** | Nguyễn Chính Minh (`202416293`) | Phân tích liên kết đồ thị thị trường & Khoảng trống danh mục (*Market Graph*) | `4.414` sản phẩm chuẩn, ma trận Jaccard, `63` cụm Louvain, `90` khoảng trống thị trường, điểm chuẩn CPU/GPU price-free (`data/market_graph/`) |
| **TV5** | Đào Duy Anh (`20235000`) | Mô hình định giá hưởng lạc không rò rỉ (*Hedonic Fair-Value Modeling*) | 6 pipeline tự đóng gói (`Ridge`, `RF`, `LightGBM`) trên `8.132` mẫu sạch; LightGBM đạt `R² = 0,9125` (Laptop) & `R² = 0,9587` (Smartphone) |
| **TV6** | Nguyễn Trịnh Minh Hiếu (`20235078`) | Khai phá văn bản đánh giá tiếng Việt (*PhoBERT Sentiment, LDA & ABSA*) | `14.869` review hợp lệ, PhoBERT `Macro F1 = 0,6491`, 5 chủ đề LDA, 5 khía cạnh ABSA, 35 đặc trưng cấp `source_parent_id` (`data/tv6/`) |
| **TV7** | Nguyễn Tùng Dương (`20230024`) | Kiểm toán bất thường đa phương pháp (*Catalog & Price Anomaly Audit*) | Tổ hợp Rule + Log-IQR + Isolation Forest phát hiện `715` bản ghi (`6,93%`), tách 4 `anomaly_type` & `recommended_action` (`src/anomaly_detection/`) |
| **TV8** | Lê Trần Anh (`202416112`) | Thẩm định 3 chiều, Ablation/Sensitivity, XAI SHAP & Nền tảng 5 Tab (*Decision App*) | Chuỗi thực nghiệm `S1–S5`, 7 bảng + 7 hình 300 DPI, giải thích SHAP VNĐ & ứng dụng 5 tab `src/evaluation_demo/app.py` |

---

## 3. Tài liệu Báo cáo & Cẩm nang Bảo vệ Đồ án

- 📄 **[Báo cáo Khoa học Dữ liệu Tổng hợp nộp Giảng viên (Nhóm 12)](docs/BAO_CAO_KHOA_HOC_DU_LIEU_IT4930_NHOM12.md)** — Báo cáo đầy đủ 10 phần theo sườn học phần IT4930, tập trung vào bài toán nghiệp vụ, phương pháp thực hiện và tri thức rút ra của từng thành viên TV1–TV8.
- 🎤 **[Cẩm nang Thuyết trình, Diễn giải 15 Biểu đồ EDA & Kịch bản Phản biện](docs/PRESENTATION_AND_DEFENSE_PLAYBOOK.md)** — Tuyên ngôn định vị KHDL B2B/B2C, từ điển 3 bước cho toàn bộ 15 biểu đồ EDA, 8 câu hỏi phản biện chuyên sâu và kịch bản demo 15 phút.
- 📊 **Báo cáo chuyên sâu từng phân hệ**:
  - TV2 (Quản trị & Tích hợp dữ liệu): [Data Contract](docs/data_contract_tv2_v1.md) · [Data Quality Report](docs/data_quality_report_tv2_v1.md) · [Gold Handoff](docs/gold_handoff.md) · [Feature Contracts](docs/feature_contracts_tv3_tv8.md)
  - TV3 (Phân tích khám phá EDA): [Phần 5 — Báo cáo EDA](docs/EDA/report_section_5_eda.md) · [Handoff TV3 → TV5](docs/EDA/tv3_to_tv5_handoff.md)
  - TV5 (Mô hình định giá hợp lý): [Tổng quan kiến trúc & Kết quả TV5](src/price_prediction/summary.md) · [Báo cáo kỹ thuật TV5](src/price_prediction/report.md)
  - TV6 (Xử lý ngôn ngữ tự nhiên đánh giá): [Phần 8 — Review NLP & Sentiment Analysis](docs/review_nlp/report_part8.md)
  - TV7 (Phát hiện bất thường danh mục & giá): [Phần 9 — Anomaly Detection](src/anomaly_detection/report_section_9.md)
  - TV8 (Đánh giá 3 chiều, XAI & Demo): [Phần 10 — Đánh giá, Giải thích & Hệ thống Demo](docs/evaluation_demo/report_part10_evaluation_demo.md) · [Hướng dẫn chạy Demo](src/evaluation_demo/README.md)

---

## 4. Cài đặt Môi trường & Chạy Ứng dụng Demo 5 Tab

### 4.1. Cài đặt phụ thuộc

```bash
# Cài đặt môi trường chuẩn cho toàn bộ pipeline và ứng dụng Streamlit:
python -m pip install -r requirements.txt

# (Tùy chọn) Cài đặt bổ sung cho việc chạy lại 5 Jupyter Notebooks EDA của TV3:
python -m pip install -r requirements-eda.txt
```

### 4.2. Khởi chạy Hệ thống Hỗ trợ Quyết định 5 Tab (`Streamlit`)

```bash
python -m streamlit run src/evaluation_demo/app.py --server.address 127.0.0.1
```

Ứng dụng mở tại `http://127.0.0.1:8501` gồm **5 tab nghiệp vụ**:
1. **Tổng quan & Quy luật giá (TV1–TV3)**: KPI thị trường + 15 biểu đồ EDA kèm hộp diễn giải *Câu hỏi nghiệp vụ → Phát hiện định lượng → Ý nghĩa & Hành động*.
2. **Cạnh tranh đa sàn & Review (TV4 & TV6)**: Vị thế giá 5 sàn, trùng lặp Jaccard, phân khúc Louvain, bộ lọc **90 khoảng trống danh mục**, đồ thị tương tác PyVis và phân tích PhoBERT / LDA / ABSA.
3. **Thẩm định giá hợp lý (TV5–TV8)**:
   - *Chế độ 1 (Mặc định)*: **Thẩm định SKU thực tế đang niêm yết trên 5 sàn** — so sánh *Giá bán thực tế* với *Giá hợp lý theo cấu hình*, giải thích SHAP VNĐ, đối chiếu cờ kiểm toán TV7, review TV6 và các máy tương đương liên sàn.
   - *Chế độ 2 (B2B)*: **Mô phỏng định giá SKU mới trong miền phần cứng tương thích** — khóa chặt tổ hợp linh kiện hợp lệ theo Hãng & Dòng máy.
4. **Kiểm toán bất thường (TV7)**: Phân tích 4 nhóm `anomaly_type`, khuyến nghị xử lý danh mục và tra cứu chi tiết từng bản ghi.
5. **Đánh giá mô hình & XAI (TV8)**: Benchmark 3 chiều, Ablation `S1–S4`, độ nhạy `S5a/S5b`, phân tích sai số lát cắt, Top-20 ca lệch lớn nhất và kiểm định tính đơn điệu TreeSHAP.

### 4.3. Chạy Bộ Kiểm thử Tự động

```bash
# Chạy toàn bộ kiểm thử tích hợp của dự án bằng pytest:
python -m pytest -q

# Hoặc chạy riêng bộ kiểm thử hồi quy mô hình, dữ liệu & giao diện 5 tab:
python -m pytest tests/test_tv8_evaluation_demo.py -q
```

---

## 5. Hướng dẫn Vận hành Chi tiết Từng Phân hệ Dữ liệu

### 5.1. TV1 — Thu thập Dữ liệu Đa nguồn (`crawler/`)

Hệ thống crawler thu thập dữ liệu gốc bất biến (*Immutable Raw Data*) cho 2 danh mục **Laptop** và **Smartphone** trên đủ **5/5 sàn** (`tgdd`, `fptshop`, `cellphones`, `viettelstore`, `hoanghamobile`), tuân thủ nghiêm ngặt `robots.txt`, `AutoThrottle`, `RunnerLock` chống chạy đồng thời và hợp đồng dữ liệu thô (**Product = 25 trường**, **Review = 19 trường**).

> **Lưu trữ Dữ liệu Thô (Google Drive — TV1)**:  
> [TV1 Raw Data trên Google Drive](https://drive.google.com/drive/folders/1wQbWDOmYZFz2Ut3AShMu2o1wkMTJESuJ?usp=drive_link) (`data/raw/<source>/<category>.jsonl` & `<category>_reviews.jsonl`)

```bash
# Chạy riêng từng nguồn có giới hạn số lượng kiểm thử:
python crawler/run_crawler.py --source cellphones --category laptop --limit 50
python crawler/run_crawler.py --source tgdd --category all --limit 50
python crawler/run_crawler.py --source fptshop --category smartphone --limit 50

# Chạy tuần tự tất cả 5 nguồn đã triển khai:
python crawler/run_crawler.py --source all --category all --limit 50

# Chế độ Full Crawl (--full và --limit loại trừ lẫn nhau):
python crawler/run_crawler.py --source cellphones --category laptop --full
```

### 5.2. TV2 — Quản trị Chất lượng & Tích hợp Dữ liệu 5 Tầng (`src/preprocessing/`)

Biến đổi dữ liệu thô qua 5 tầng tuần tự `data/raw/ → data/staging/ → data/silver_v2/ → data/gold_v2/ → data/processed/` theo nguyên lý **không xóa dòng, chỉ gắn cờ kiểm toán (*flag-don't-drop*)**, thiết kế mô hình kho dữ liệu hình sao (**Star Schema Gold v2** gồm 5 bảng) và xuất bộ dữ liệu chuẩn hóa:
- `data/processed/products_processed.jsonl` (`10.316` dòng × `32` trường) & `data/processed/listing_id_crosswalk.csv`
- `data/processed/reviews_processed.jsonl` (`15.805` dòng × `14` trường)

> **Lưu trữ Dữ liệu Gold v2 & Processed (Google Drive — TV2)**:  
> [TV2 Data Handoff trên Google Drive](https://drive.google.com/drive/folders/1QiIvoEL_Lo2MWF3qoRpHypQvxLDvvELE?usp=drive_link)

```bash
python src/preprocessing/run_tv2_pipeline.py
```

### 5.3. TV3 → TV8 — Tái lập Phân tích, Đồ thị, NLP, Kiểm toán & Thẩm định

```bash
# TV3 — Tái lập 36+ bảng thống kê & 15 biểu đồ EDA 300 DPI:
python src/eda/scripts/reproduce_all.py

# TV4 — Chạy pipeline đối sánh sản phẩm chuẩn, đồ thị thị trường, Louvain & Structural Holes:
python -m src.market_graph.cli run-all

# TV6 — Tái lập pipeline NLP tiếng Việt, Sentiment, LDA & ABSA (Bước 0 -> Bước 5):
python src/review_nlp/run_step0.py
python src/review_nlp/run_step1.py
python src/review_nlp/run_step2.py
python src/review_nlp/run_step3_1.py
python src/review_nlp/run_step4.py
python src/review_nlp/run_step5.py

# TV7 — Chạy kiểm toán bất thường đa phương pháp & xuất anomaly_flags.csv:
python src/anomaly_detection/detect_price_anomalies.py

# TV8 — Đánh giá độc lập 6 mô hình TV5, thực nghiệm Ablation S1–S5 & trích xuất SHAP:
python src/evaluation_demo/evaluate_models.py
python src/evaluation_demo/ablation_sensitivity.py --stage all
python src/evaluation_demo/explainability.py
```
