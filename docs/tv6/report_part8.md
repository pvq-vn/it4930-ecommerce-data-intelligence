# PHẦN 8: XỬ LÝ NGÔN NGỮ TỰ NHIÊN & KHAI PHÁ DỮ LIỆU ĐÁNH GIÁ (REVIEW NLP & SENTIMENT ANALYSIS)

**Tác giả phụ trách**: Thành viên 6 (TV6 – Xử lý Ngôn ngữ Tự nhiên & Khai phá Đánh giá Khách hàng)  
**Mã học phần**: IT4930 – Khoa học Dữ liệu & Trí tuệ Kinh doanh  
**Tập dữ liệu nghiên cứu**: Toàn bộ kho dữ liệu đánh giá thương mại điện tử công nghệ gồm **15.805 bản ghi** ($14.869$ review hợp lệ có văn bản, $936$ review cách ly audit)  
**Căn cứ tài liệu quy chuẩn**: [docs/feature_contracts_tv3_tv8.md](../feature_contracts_tv3_tv8.md)  
**Môi trường thực nghiệm**: Python 3.12, PyTorch 2.5.1, Transformers 4.46.3, Underthesea 6.8.4, Scikit-learn 1.6.1 trên GPU NVIDIA GeForce RTX 2060 SUPER (8GB VRAM GDDR6, CUDA 12.2)  

---

## 8.1. Tổng quan Phân hệ TV6 & Kiến trúc View Phân tích Độc lập (Bước 0)

Trong hệ sinh thái dữ liệu đa chiều của đồ án **IT4930 E-Commerce Data Intelligence**, các phân hệ TV3, TV4, TV5 và TV7 chủ yếu khai thác các thuộc tính định lượng và thông số kỹ thuật phần cứng (RAM, CPU, Ổ cứng, Giá niêm yết, Tỷ lệ giảm giá). Tuy nhiên, thông số kỹ thuật thuần túy chỉ đại diện cho cấu hình xuất xưởng lý thuyết, chưa thể hiện được:
1. **Trải nghiệm sử dụng thực tế**: Máy chạy mượt hay giật lag, tản nhiệt tốt hay nóng ran, quạt kêu ồn, màn hình có điểm chết hay hở sáng.
2. **Thiện cảm thương hiệu & Mức độ tín nhiệm (Brand Sentiment & Trust)**: Phản hồi về độ bền bỉ, độ tin cậy của nhà sản xuất.
3. **Chất lượng dịch vụ bán lẻ**: Khâu tư vấn, đóng gói, tốc độ giao vận và chính sách bảo hành hậu mãi của chuỗi cửa hàng.

**Phân hệ TV6** nhận trách nhiệm tiếp nhận dữ liệu review thô từ TV2 (Gold v2), xây dựng pipeline NLP tiếng Việt chuyên sâu, kiểm toán chất lượng nội dung, phân loại cảm xúc đa lớp, khai phá chủ đề và khía cạnh công nghệ (ABSA), và bàn giao bảng đặc trưng tổng hợp theo sản phẩm cho **TV5 (Mô hình hóa Dự đoán Giá)**.

```mermaid
flowchart TD
    G2["data/gold_v2/fact_reviews.jsonl\n(15.805 reviews)"] --> S0["Bước 0: Xây dựng View Phân tích\n& Kiểm toán Dữ liệu Thô"]
    S0 --> ALL["reviews_tv6_all.jsonl (15.805)"]
    S0 --> USA["reviews_tv6_usable.jsonl (14.869)"]
    S0 --> UNUSA["reviews_tv6_unusable.jsonl (936)"]
    
    USA --> S1["Bước 1: Kiểm toán Chất lượng & EDA\n(7 Bảng Thống kê, 5 Biểu đồ)"]
    USA --> S2["Bước 2: Pipeline Tiền xử lý & Tokenization\n(NFC, Emoji, 79 Teencode, Disambiguation, Underthesea)"]
    
    S2 --> S31["Bước 3.1: ML Sentiment Baseline\n(TF-IDF + Logistic, SVM, Naive Bayes)"]
    S2 --> S32["Bước 3.2: Fine-Tuning Transformer SOTA\n(vinai/phobert-base-v2 trên GPU CUDA)"]
    
    S32 --> S4["Bước 4: Topic Modeling & ABSA\n(LDA 5 Chủ đề, ABSA 5 Khía cạnh Kỹ thuật)"]
    
    S4 --> S5["Bước 5: Feature Engineering cho TV5\n(Xử lý Cold-Start 73,1%, Chống Leakage, 35 Features)"]
    S5 --> TV5["data/tv6/tv5_review_features.parquet\n(Bàn giao cho TV5 Price Prediction)"]
```

### Nguyên tắc Bất khả Xâm phạm về Toàn vẹn Dữ liệu:
- **Không xâm lấn vùng lưu trữ chung**: Toàn bộ mã nguồn đặt tại `src/review_nlp/`, tài liệu tại `docs/tv6/`, dữ liệu dẫn xuất tại `data/tv6/`. Tuyệt đối không ghi đè vào `data/gold_v2/` hay `data/raw/`.
- **Bảo toàn 100% dữ liệu gốc (Zero Data Loss)**: Toàn bộ 15.805 review được giữ nguyên vẹn trong [`reviews_tv6_all.jsonl`](../../data/tv6/reviews_tv6_all.jsonl). 
- **Cách ly kiểm toán chuẩn mực**: Phân tách thành hai luồng xử lý:
  * **Tập Usable** ($N = 14.869$, chiếm $94,08\%$): Chứa văn bản thực tế, thỏa mãn tiền điều kiện NLP.
  * **Tập Unusable** ($N = 936$, chiếm $5,92\%$): Bao gồm 489 review từ Viettel Store bị khuyết toàn bộ văn bản và 447 review rỗng/chỉ chứa khoảng trắng từ CellphoneS. Nhóm này được cách ly riêng trong [`reviews_tv6_unusable.jsonl`](../../data/tv6/reviews_tv6_unusable.jsonl) để phục vụ thanh tra chất lượng dữ liệu của TV8.
- **Làm giàu ngữ cảnh**: Nối khóa `source_parent_id` với `dim_source_parents.jsonl` để bổ sung tên sản phẩm cha chuẩn mực (`product_name`), giải quyết triệt để lỗi sinh 45.651 dòng giả nếu nối nhầm với bảng biến thể listing.

### Bảng 8.1: Quy chuẩn Bảng View 23 Trường Canonical Phân hệ TV6

| Nhóm Trường | Tên Cột Canonical | Kiểu Dữ liệu | Ý nghĩa & Mục đích Sử dụng |
|:---|:---|:---|:---|
| **Khóa định danh** | `review_record_id` | string (hex hash) | Khóa chính duy nhất truy nguyên từng bản ghi đánh giá |
| | `source_parent_id` | string (hex hash) | Khóa ngoại nối với bảng sản phẩm cha `dim_source_parents` |
| | `product_name` | string | Tên sản phẩm đại diện được làm giàu từ bảng cha |
| | `source` | string | Sàn TMĐT (`cellphones`, `fptshop`, `tgdd`) |
| | `category` | string | Ngành hàng thiết bị (`laptop`, `smartphone`) |
| **Nội dung đánh giá** | `rating_raw` | int8 ($1 \rightarrow 5$) | Điểm số sao đánh giá gốc của người dùng |
| | `rating_norm` | float32 ($1.0 \rightarrow 5.0$) | Điểm số sao đã chuẩn hóa kiểu dữ liệu |
| | `review_text_normalized` | string (UTF-8) | Văn bản đánh giá sau tầng làm sạch sơ bộ của TV2 |
| | `review_time_raw` | string (ISO-8601) | Mốc thời gian gửi đánh giá của người mua hàng |
| | `author_raw` | string | Tên hoặc biệt danh người đánh giá |
| **Cờ kiểm toán** | `review_usable` | boolean | Cờ xác định review có văn bản hợp lệ cho NLP (True/False) |
| | `review_text_status` | string | Trạng thái văn bản (`VALID`, `EMPTY_TEXT`, `WHITESPACE_ONLY`) |
| | `review_time_status` | string | Trạng thái thời gian (`VALID_TIMESTAMP`, `MISSING_TIMESTAMP`) |
| | `is_reply_present` | boolean | Đánh giá có phản hồi từ nhân viên cửa hàng hay không |
| | `is_attachment_present` | boolean | Đánh giá có đính kèm ảnh/video mở hộp thực tế hay không |
| | `review_metadata_suspect_candidate`| boolean | Cờ nghi ngờ bất thường metadata |
| **Truy nguyên gốc** | `crawl_batch` | string | Mã đợt cào dữ liệu |
| | `crawl_time` | string (ISO-8601) | Thời điểm thu thập dữ liệu snapshot của sàn |
| | `raw_record_id` | string | Mã bản ghi tại tầng thô raw |
| | `raw_file` | string | Đường dẫn tệp dữ liệu thô ban đầu |
| | `raw_line_number` | int32 | Vị trí dòng bản ghi trong tệp thô |
| | `gold_version` | string | Phiên bản schema Gold (`gold_v2`) |
| | `tv6_pipeline_version` | string | Phiên bản pipeline TV6 (`tv6-v1.0.0`) |

---

## 8.2. Kiểm toán Chất lượng & Đặc trưng Dữ liệu Đánh giá (EDA - Bước 1)

![Fig 1.1: Phân bố Điểm Đánh giá Sao theo Sàn Thu thập](../../data/tv6/figures/fig_1_1_rating_distribution_by_source.png)
![Fig 1.2: Cơ cấu Tập Đánh giá Hợp lệ vs Cách ly Audit](../../data/tv6/figures/fig_1_2_usable_vs_unusable_breakdown.png)
![Fig 1.3: Phân bố Độ dài Ký tự Văn bản Đánh giá](../../data/tv6/figures/fig_1_3_text_length_distribution.png)
![Fig 1.4: Xu hướng Khối lượng Đánh giá theo Thời gian (2019-2026)](../../data/tv6/figures/fig_1_4_temporal_trend_reviews.png)
![Fig 1.5: Kiểm toán Bao phủ Đánh giá & Thách thức Cold-Start](../../data/tv6/figures/fig_1_5_product_review_coverage.png)

### 8.2.1. Hiện tượng "Lạm phát Sao 5★" (Rating Inflation)
*Căn cứ [table_1_1_rating_source_distribution.md](../../data/tv6/tables/table_1_1_rating_source_distribution.md):*
- Khảo sát trên 14.869 đánh giá hợp lệ ghi nhận sự mất cân bằng cực đoan về số sao:
  * **5 sao**: $12.607$ review (**$84,79\%$**).
  * **4 sao**: $512$ review (**$3,44\%$**).
  * **3 sao**: $444$ review (**$2,99\%$**).
  * **2 sao**: $213$ review (**$1,43\%$**).
  * **1 sao**: $1.093$ review (**$7,35\%$**).
- Điểm đánh giá trung bình toàn thị trường đạt mức rất cao: **$4,56 \pm 1,12★$**.
- Hiện tượng phân cực hình chữ U (U-shaped distribution): Người dùng TMĐT Việt Nam có xu hướng chỉ để lại đánh giá khi cực kỳ hài lòng (chấm 5 sao nhận xu/điểm thưởng) hoặc khi gặp sự cố nghiêm trọng (chấm 1 sao để khiếu nại). Vùng trung tính (2–3 sao) chiếm tỷ lệ rất mỏng ($4,42\%$).

### Bảng 8.2: Phân bố Đánh giá Sao theo Từng Sàn Thương Mại Điện Tử

| Sàn TMĐT | 1★ | 2★ | 3★ | 4★ | 5★ | Tổng Hợp Lệ | Rating TB | Tỷ lệ 5★ |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|
| `cellphones` | 468 | 134 | 269 | 358 | 9.817 | **11.046** | 4,62★ | 88,87% |
| `fptshop` | 47 | 10 | 25 | 40 | 1.566 | **1.688** | 4,82★ | 92,77% |
| `tgdd` | 578 | 69 | 150 | 114 | 1.224 | **2.135** | 4,12★ | 57,33% |
| **Toàn thị trường** | **1.093** | **213** | **444** | **512** | **12.607** | **14.869** | **4,56★** | **84,79%** |

### 8.2.2. Đặc tính Ngắn gọn & Hiện tượng Review Trùng lặp Khách quan
*Căn cứ [table_1_3_text_length_percentiles.md](../../data/tv6/tables/table_1_3_text_length_percentiles.md) và [table_1_4_top_duplicate_texts.md](../../data/tv6/tables/table_1_4_top_duplicate_texts.md):*
- Độ dài văn bản đánh giá rất cô đọng: Trung vị đạt **44,0 ký tự** (tương đương **10 từ**), $75\%$ review dưới 91 ký tự (21 từ).
- Kiểm toán phát hiện **$2.422$ review trùng lặp văn bản** ($16,29\%$ tổng số review hợp lệ, tương ứng $12.447$ văn bản độc nhất theo `quality_report.json`), tập trung vào các câu cửa miệng mẫu:
  * *"Tốt"* (210 lần).
  * *"Ok"* (128 lần).
  * *"5 sao"* (104 lần).
  * *"tốt"* (91 lần) / *"Hài lòng"* (52 lần) / *"Sản phẩm rất tốt"* (50 lần)...
- **Khẳng định phương pháp luận khoa học**: Đây **không phải là dữ liệu giả (fake reviews)** hay lỗi cào dữ liệu lặp lại. Đây là các giao dịch mua hàng độc lập từ những khách hàng khác nhau (`author_raw` và mã giao dịch khác biệt) sử dụng các gợi ý có sẵn trên ứng dụng di động để nhanh chóng hoàn thành đánh giá. Việc TV6 giữ lại nguyên vẹn các review này đảm bảo đo lường chính xác khối lượng giao dịch và sự tín nhiệm của từng model máy.

### 8.2.3. Phát hiện Nghịch lý Bất nhất Điểm số – Văn bản (Rating–Text Mismatch)
*Căn cứ [table_1_5_rating_text_mismatch_audit.md](../../data/tv6/tables/table_1_5_rating_text_mismatch_audit.md):*
- Phát hiện **$118$ trường hợp mâu thuẫn trực diện** giữa điểm sao chấm và nội dung văn bản viết:
  * **Chấm 4–5★ nhưng nội dung chê bai thậm tệ**: Người dùng lớn tuổi hoặc thao tác vội chọn nhầm 5 sao mặc định của giao diện, nhưng trong phần bình luận viết: *"Tệ. Thất vọng. Tiền mất tật mang..."* (Record `16ce1d94b759...` tại CellphoneS) hoặc *"Mua về 1 tháng máy lỗi màn hình rung giật, tắt ngúm..."* (Record `03763b355c10...`).
  * **Chấm 1–2★ nhưng nội dung khen ngợi sản phẩm**: Khách hàng hài lòng với máy nhưng tức giận vì shop hết màu, giao hàng trễ hoặc nhân viên tổng đài tư vấn chậm trễ: *"Chọn được mẫu ưng ý mà không có sẵn hàng..."* (Record `4e976257ae8d...` tại FPT Shop).
- **Ý nghĩa Kỹ thuật**: Kết quả này khẳng định giá trị cốt lõi của bài toán NLP: **Không thể tin cậy mù quáng vào số sao nguyên bản**. Mô hình phân loại cảm xúc văn bản đóng vai trò hiệu chỉnh (calibrate) tín hiệu cảm xúc thực sự của sản phẩm.

### 8.2.4. Độ Bao phủ Sản phẩm & Bài toán Cold-Start ($73,10\%$)
*Căn cứ [table_1_6_product_coverage_audit.md](../../data/tv6/tables/table_1_6_product_coverage_audit.md):*
- Trong toàn bộ **7.051 sản phẩm cha** đại diện cho thị trường:
  * Chỉ có **1.897 sản phẩm** ($26,90\%$) có ít nhất 1 review hợp lệ.
  * Có tới **5.154 sản phẩm** ($73,10\%$) **hoàn toàn không có review**.
  * Hoàng Hà Mobile ($285$ sản phẩm) và Viettel Store ($167$ sản phẩm) hoàn toàn khuyết review text.
- Đây là insight mang tính sống còn để TV6 thiết kế cờ nhị phân `has_review_data` trong bảng bàn giao cho TV5.

---

## 8.3. Pipeline Tiền xử lý Ngôn ngữ Tự nhiên & Khử Nhập nhằng Ngữ cảnh (Bước 2)

![Fig 2.1: Phân bố Tần suất Top 30 Từ tố Tiếng Việt Sau Tiền Xử Lý](../../data/tv6/figures/fig_2_1_top_tokens_frequency.png)

Ngôn ngữ review thương mại điện tử công nghệ tại Việt Nam mang tính phi hình thức cao, pha trộn dày đặc từ lóng, teencode, viết tắt thuật ngữ phần cứng và tiếng lóng chuyển dịch nghĩa. Phân hệ TV6 đã thiết kế một pipeline tiền xử lý 7 tầng chuyên sâu tại [`src/review_nlp/vietnamese_nlp_utils.py`](../../src/review_nlp/vietnamese_nlp_utils.py):

### 8.3.1. Các Tầng Chuyển đổi Dữ liệu Cốt lõi
*Căn cứ [table_2_1_preprocessing_pipeline_stages.md](../../data/tv6/tables/table_2_1_preprocessing_pipeline_stages.md):*
1. **Chuẩn hóa Bảng mã Unicode & Sửa Lỗi Hiển thị**: Chuyển đổi triệt để về định dạng Unicode dựng sẵn (**NFC**), xử lý lỗi font UTF-8/CP1252 thường gặp trong dữ liệu cào thô (ví dụ: `Æ¡i` $\rightarrow$ `ơi`).
2. **Ánh xạ Biểu tượng Cảm xúc (Emoji Semantic Tokenization)**: Thay vì xóa bỏ làm mất sắc thái, hệ thống dịch chuyển emoji thành các token mang ý nghĩa cảm xúc chuẩn hóa: `😍`, `❤️`, `👍` $\rightarrow$ `emoji_positive`; `😡`, `👎`, `😭` $\rightarrow$ `emoji_negative`; `🤔`, `😐` $\rightarrow$ `emoji_neutral`.
3. **Từ điển Chuẩn hóa 79 Quy tắc Teencode & Viết tắt**: Quy đổi toàn bộ ngôn ngữ chat về từ phổ thông: `dc/đc` $\rightarrow$ `được`, `k/ko/khg` $\rightarrow$ `không`, `ok/oke/oki` $\rightarrow$ `tốt`, `dt` $\rightarrow$ `điện thoại`, `sp` $\rightarrow$ `sản phẩm`, `pin trau` $\rightarrow$ `pin trâu`.

### 8.3.2. Đột phá Kỹ thuật: 3 Nhóm Luật Khử Nhập nhằng Ngữ cảnh (Contextual Disambiguation)
Nhiều từ viết tắt trong đánh giá công nghệ mang tính đa nghĩa trầm trọng. Nếu chỉ dùng bảng tra cứu thô (lookup table), câu văn sẽ bị bóp méo hoàn toàn:
- **Nhóm 1: 'bh' (Bảo hành vs Bao giờ)**:
  * Đi kèm động từ thời gian hoặc trạng thái (`hàng về`, `có hàng`, `mới về`) $\rightarrow$ Khử thành **"bao giờ"** (*"Shop ơi bh có hàng"* $\rightarrow$ *"Shop ơi bao giờ có hàng"*).
  * Đi kèm thuật ngữ kỹ thuật, thời hạn (`12 tháng`, `chính hãng`, `lỗi`, `đổi trả`) $\rightarrow$ Khử thành **"bảo hành"** (*"máy bh 12 tháng chính hãng"*).
- **Nhóm 2: 'cam' (Camera vs Màu sắc)**:
  * Đi kèm từ ngữ chụp ảnh, quang học (`chụp`, `nét`, `sau`, `trước`, `góc rộng`, `quay video`) $\rightarrow$ Khử thành **"camera"** (*"cam chụp đêm rất nét"*).
  * Đi kèm danh từ trang phục, phụ kiện hoặc màu sắc (`màu`, `bản`, `màu cam`, `vỏ`) $\rightarrow$ Giữ nguyên tính từ chỉ **"màu cam"**.
- **Nhóm 3: Các từ đa nghĩa công nghệ ('kg', 'kh', 'cn', 'mh', 'sd', 'bt', 'kb')**:
  * `'kg'` trước tính từ/động từ $\rightarrow$ **"không"**; sau chữ số thập phân (`2kg`, `1.5 kg`) $\rightarrow$ **"kilogram"** (trọng lượng laptop).
  * `'mh'` đi cùng hiển thị, cảm ứng $\rightarrow$ **"màn hình"**; đi cùng xưng hô $\rightarrow$ **"mình"**.
  * `'sd'` đi cùng thao tác $\rightarrow$ **"sử dụng"**; đi cùng thẻ nhớ $\rightarrow$ **"thẻ nhớ SD"**.

### 8.3.3. Tách Từ ghép Tiếng Việt & Bộ lọc Stopword An toàn (Safe Stopwords)
- **Tách từ phức**: Sử dụng engine `underthesea` kết hợp từ điển chuyên ngành công nghệ để gắn kết từ ghép bằng dấu gạch dưới: `màn_hình`, `pin_trâu`, `nhiệt_độ`, `bảo_hành`, `giao_hàng`, `xuất_sắc`.
- **Bảo toàn từ phủ định**: Loại bỏ các hư từ không mang tải trọng thông tin (`thì`, `là`, `mà`, `ở`, `tại`), nhưng **tuyệt đối giữ lại các từ phủ định cốt tử** (`không`, `chẳng`, `chưa`, `kém`, `tệ`, `hỏng`) để tránh hiện tượng đảo ngược phân cực câu văn (*"máy không nóng"* nếu bỏ *không* sẽ thành *"máy nóng"*).
- **Quy mô kho ngữ liệu Bước 2**: Sản sinh **196.819 tokens** với **11.627 từ vựng duy nhất**, lưu trữ tại [`reviews_tv6_preprocessed.jsonl`](../../data/tv6/reviews_tv6_preprocessed.jsonl).

---

## 8.4. Phân loại Cảm xúc Đa lớp: Đối sánh Baseline ML vs PhoBERT Transformer SOTA (Bước 3)

![Fig 3.1: So sánh Toàn diện Metric giữa 4 Mô hình Baseline](../../data/tv6/figures/fig_3_1_model_comparison_metrics.png)
![Fig 3.2: Heatmap Ma trận Nhầm lẫn 4 Mô hình Machine Learning Baseline](../../data/tv6/figures/fig_3_2_confusion_matrices.png)
![Fig 3.3: Top 20 Từ tố Phân cực Tích cực & Tiêu cực Mạnh nhất](../../data/tv6/figures/fig_3_3_top_polar_words.png)
![Fig 3.4: Đường cong Huấn luyện PhoBERT (Train/Val Loss & Macro F1 qua 3 Epoch)](../../data/tv6/figures/fig_3_4_phobert_training_curves.png)
![Fig 3.5: Đối đầu Trực quan PhoBERT Transformer SOTA vs Logistic Regression Baseline](../../data/tv6/figures/fig_3_5_phobert_vs_baseline_comparison.png)

### 8.4.1. Thiết lập Bài toán & Khung Đánh giá Khoa học
- **Định nghĩa nhãn**: Bài toán phân loại 3 lớp cảm xúc văn bản:
  * **Positive ($88,23\%$)**: Gồm các đánh giá 4–5 sao hoặc văn bản khen ngợi sâu sắc.
  * **Negative ($8,78\%$)**: Gồm các đánh giá 1–2 sao hoặc văn bản phàn nàn sự cố.
  * **Neutral ($2,99\%$)**: Gồm các đánh giá 3 sao hoặc nhận xét pha trộn khen chê vừa phải.
- **Phân chia dữ liệu chuẩn**: Phân tầng (Stratified Split) tỷ lệ **$80\%$ Train ($11.895$ review)** và **$20\%$ Test ($2.974$ review)**, cố định `random_state=42`.
- **Thước đo quyết định**: Trong điều kiện mất cân bằng lớp trầm trọng, độ chính xác tổng thể (Accuracy) là chỉ số vô nghĩa (mô hình ngây thơ luôn dự đoán Positive cũng đạt $88\%$ accuracy). TV6 lựa chọn **Macro F1-Score** (trung bình cộng F1 không trọng số của 3 lớp) làm **chỉ số thẩm định tối cao**.

### 8.4.2. Huấn luyện Mô hình Baseline Machine Learning (Bước 3.1)
*Căn cứ [table_3_1_model_comparison.md](../../data/tv6/tables/table_3_1_model_comparison.md):*
- Trích xuất đặc trưng: TF-IDF Vectorizer (Unigram + Bigram, `max_features=5000`, `min_df=2`, `sublinear_tf=True`).
- Thử nghiệm 4 thuật toán học máy cổ điển với 5-fold Stratified Cross-Validation:
  1. **Multinomial Naive Bayes**: Macro F1 $0,3415$ (Thất bại hoàn toàn ở lớp Neutral $F_1 = 0,00$ và Negative $F_1 = 0,0671$ do giả định độc lập từ ngây thơ).
  2. **Complement Naive Bayes**: Macro F1 $0,5226$ (Cải thiện tốt cho tập mất cân bằng).
  3. **Linear Support Vector Machine (LinearSVC)**: Macro F1 $0,5778$, Accuracy $92,57\%$.
  4. **Logistic Regression (Class-Balanced)**: Đạt đỉnh Baseline với **Macro F1 $0,5901$**, Weighted F1 $0,9116$, Accuracy **$89,81\%$**.
- Trọng số từ tố phân cực phân giải từ Logistic Regression:
  * Phân cực Dương: `tốt`, `đẹp`, `nhanh`, `ổn_định`, `tuyệt_vời`, `chính_hãng`, `hài_lòng`.
  * Phân cực Âm: `kém`, `tệ`, `hỏng`, `thất_vọng`, `đơ`, `nóng`, `lag`, `chậm`, `lỗi`.

### 8.4.3. Huấn luyện Mô hình Transformer Tiếng Việt SOTA: PhoBERT (Bước 3.2)
*Căn cứ [table_3_4_phobert_vs_baseline.md](../../data/tv6/tables/table_3_4_phobert_vs_baseline.md):*
- **Kiến trúc**: Sử dụng pretrained model chuẩn mực của VinAI: `vinai/phobert-base-v2` (135 triệu tham số, cơ chế tự chú ý Self-Attention 12 tầng, độ dài ngữ cảnh `max_length=128`).
- **Chiến lược Huấn luyện Tối ưu trên GPU**:
  * Tận dụng nhân Tensor Core trên **RTX 2060 SUPER 8GB VRAM** với công nghệ Tự động Ép kiểu Hỗn hợp (**Automatic Mixed Precision - FP16 AMP**), giảm $50\%$ tiêu hao bộ nhớ và tăng tốc xử lý lên gấp $2,5$ lần.
  * Bộ giải tối ưu **AdamW** (`lr = 2e-5`, `weight_decay = 0.01`), lịch điều chỉnh tốc độ học Cosine Annealing kèm $10\%$ warmup steps.
  * **Class-Weighted Cross-Entropy Loss**: Trọng số nghịch đảo tần suất lớp ($w_{\text{neg}} = 3,80$, $w_{\text{neu}} = 11,18$, $w_{\text{pos}} = 0,38$) để cưỡng chế mô hình tập trung vào việc học các mẫu biên giới của lớp Neutral và Negative.

### Bảng 8.3: Đối sánh Chi tiết Năng lực Phân loại Cảm xúc trên Tập Kiểm thử Độc lập ($N = 2.974$)

| Mô hình Phân loại | Accuracy | Macro F1 | Weighted F1 | $F_1$ Negative | $F_1$ Neutral (Lớp khó nhất) | $F_1$ Positive | Mức Tăng trưởng Macro F1 |
|:---|---:|---:|---:|---:|---:|---:|:---|
| MultinomialNB | 91,80% | 0,3415 | 0,8804 | 0,0671 | 0,0000 | 0,9573 | Mốc cơ sở thô |
| ComplementNB | 86,38% | 0,5226 | 0,8856 | 0,4453 | 0,1867 | 0,9359 | $+53,0\%$ |
| LinearSVC | 92,57% | 0,5778 | 0,9227 | 0,5606 | 0,2032 | 0,9697 | $+69,2\%$ |
| Logistic Regression (Baseline tốt nhất) | 89,81% | 0,5901 | 0,9116 | 0,5623 | 0,2526 | 0,9556 | $+72,8\%$ |
| **PhoBERT Transformer (SOTA TV6)** | **92,23%** | **0,6491** | **0,9302** | **0,6316** | **0,3472** | **0,9686** | **$+90,1\%$ (vs MNB) / $+10,0\%$ (vs LR)** |

### Luận chứng Khoa học vì sao 3 Epochs là "Điểm Rơi Vàng" (Golden Epoch):
Phân tích diễn tiến Loss và Macro F1 qua 3 chu kỳ huấn luyện:
- **Epoch 1**: Train Loss $= 0,807$, Val Loss $= 0,635$, Val Macro F1 $= 0,6315$.
- **Epoch 2**: Train Loss $= 0,569$, Val Loss $= 0,705$, Val Macro F1 $= 0,6473$.
- **Epoch 3**: Train Loss $= 0,448$, Val Loss $= 0,877$, Val Macro F1 đạt đỉnh **$0,6491$**.
- **Kết luận**: Mặc dù Train Loss giảm liên tục nhưng Val Loss bắt đầu đảo chiều tăng từ cuối Epoch 2 do hàm mất mát bị phạt nặng bởi trọng số của lớp Neutral. Val Macro F1 đạt điểm cực đại tại Epoch 3. Nếu tiếp tục huấn luyện 4–5 epochs, mạng nơ-ron sâu sẽ rơi vào hiện tượng **Quá khớp sớm (Early Overfitting)**, khiến khả năng tổng quát hóa trên tập dữ liệu kiểm thử suy giảm mạnh. Quyết định dừng lại ở 3 Epochs là chuẩn mực khoa học dữ liệu.

---

## 8.5. Khai phá Chủ đề Tiềm ẩn & Phân tích Cảm xúc theo Khía cạnh ABSA (Bước 4)

![Fig 4.1: WordCloud Đối sánh Từ tố Phân cực: Tích cực vs Tiêu cực](../../data/tv6/figures/fig_4_1_wordclouds_by_sentiment.png)
![Fig 4.2: Tỷ trọng Phân bổ 5 Chủ đề Tiềm ẩn Khám phá từ LDA](../../data/tv6/figures/fig_4_2_topic_distribution.png)
![Fig 4.3: Ma trận Xếp chồng Sắc thái Cảm xúc theo 5 Khía cạnh Kỹ thuật ABSA](../../data/tv6/figures/fig_4_3_aspect_sentiment_matrix.png)
![Fig 4.4: So sánh Mức độ Quan tâm Khía cạnh giữa Laptop và Smartphone](../../data/tv6/figures/fig_4_4_aspect_by_category.png)

### 8.5.1. Khai phá Chủ đề Tiềm ẩn Không Giám sát (LDA Topic Modeling)
*Căn cứ [table_4_1_lda_topics.md](../../data/tv6/tables/table_4_1_lda_topics.md):*
Áp dụng thuật toán Latent Dirichlet Allocation (LDA) với độ rối Perplexity tối ưu $1.186,9$, phát hiện 5 cụm chủ đề tiềm ẩn chi phối hành vi đánh giá của người tiêu dùng:

### Bảng 8.4: Danh mục 5 Chủ đề Tiềm ẩn Khám phá từ Mô hình LDA

| Mã Chủ đề | Tên Chủ đề Gợi mở | Tỷ trọng Corpus | Top Từ Khóa Đặc trưng (Top Keywords) |
|:---|:---|---:|:---|
| **Chủ đề 0** | Cấu hình, Hiệu năng & Thiết lập Máy | **29,61%** | `không`, `được`, `máy`, `có`, `mua`, `mới`, `pin`, `bị`, `dùng`, `nhưng` |
| **Chủ đề 1** | Màn hình Hiển thị & Quay chụp Camera | **16,46%** | `rất`, `trong`, `đẹp`, `màn_hình`, `chụp`, `máy`, `tầm`, `camera`, `sử_dụng`, `dùng` |
| **Chủ đề 2** | Thời lượng Pin & Phụ kiện Sạc | **16,11%** | `mình`, `mua`, `nên`, `không`, `có`, `điện_thoại`, `máy`, `con`, `em`, `còn` |
| **Chủ đề 3** | Dịch vụ Bán lẻ, Giao vận & Đóng gói | **19,09%** | `nhân_viên`, `hàng`, `nhiệt_tình`, `tư_vấn`, `shop`, `rất`, `sản_phẩm`, `nhân_viên tư_vấn`, `có`, `giao` |
| **Chủ đề 4** | Trải nghiệm Thực tế & Sự cố Phát sinh | **18,74%** | `tốt`, `ok`, `sản_phẩm`, `máy`, `đẹp`, `rất_tốt`, `dùng`, `giá`, `quá`, `chất_lượng` |

### 8.5.2. Phân tích Cảm xúc theo 5 Khía cạnh Công nghệ Chuyên sâu (ABSA)
*Căn cứ [table_4_3_aspect_sentiment_distribution.md](../../data/tv6/tables/table_4_3_aspect_sentiment_distribution.md):*
Áp dụng bộ quy tắc ngữ cảnh kết hợp trọng số sắc thái câu, TV6 bóc tách cảm xúc theo 5 khía cạnh kỹ thuật trên $8.312$ review có đề cập khía cạnh (Độ phủ khía cạnh đạt **$55,90\%$**):

### Bảng 8.5: Phân bố Sắc thái Cảm xúc theo Từng Khía cạnh Kỹ thuật & Dịch vụ

| Khía cạnh Kỹ thuật (`Aspect`) | Số lượt Đề cập | Tỷ lệ Tích cực | Tỷ lệ Trung tính | Tỷ lệ Tiêu cực | Điểm Cực tính Khía cạnh (Polarity) |
|:---|---:|---:|---:|---:|---:|
| **Dịch vụ & Giao vận (`service_logistics`)** | $3.806$ | **90,96%** | 2,78% | 6,25% | **+0,8471** |
| **Màn hình & Thiết kế (`display_design`)** | $2.811$ | **88,08%** | 3,13% | 8,79% | **+0,7930** |
| **Hiệu năng & Tản nhiệt (`performance_thermal`)** | $3.051$ | 74,47% | 3,83% | **21,70%** | **+0,5277** |
| **Pin & Nguồn điện (`battery_power`)** | $1.987$ | 77,55% | 4,18% | **18,27%** | **+0,5929** |
| **Camera & Âm thanh (`camera_audio`)** | $1.067$ | 76,01% | 5,53% | **18,46%** | **+0,5754** |

> [!WARNING]
> **Điểm nóng Phàn nàn của Thị trường**:
> Khía cạnh **Hiệu năng & Tản nhiệt (`performance_thermal`)** có tỷ lệ tiêu cực cao nhất thị trường (**$21,70\%$**), tập trung vào các phàn nàn: máy nóng ran khi chơi game hoặc render video, tụt xung nhịp CPU (thermal throttling), quạt tản nhiệt hú to, giật lag khung hình (FPS drop). Đây là tín hiệu nhạy cảm nhất liên quan đến định giá và khấu hao máy cũ.

### 8.5.3. Khác biệt Hành vi Đánh giá: Laptop vs Smartphone
*Căn cứ [table_4_4_category_aspect_comparison.md](../../data/tv6/tables/table_4_4_category_aspect_comparison.md):*
- **Người mua Laptop**: Quan tâm vượt trội đến **Hiệu năng & Tản nhiệt** ($29,42\%$ vs $18,65\%$ ở Smartphone) và **Màn hình & Thiết kế** ($27,68\%$ vs $17,06\%$). Khách hàng kiểm tra rất kỹ cấu hình chip, dung lượng RAM và khả năng tản nhiệt khi làm việc nặng.
- **Người mua Smartphone**: Quan tâm áp đảo đến **Thời lượng Pin & Sạc nhanh** ($13,88\%$ vs $10,92\%$ ở Laptop) và **Camera chụp ảnh / Loa âm thanh** ($7,65\%$ vs $4,92\%$).

---

## 8.6. Tổng hợp Bảng Đặc trưng Bàn giao cho TV5 (Price Prediction - Bước 5)

![Fig 5.1: Ma trận Tương quan Tuyến tính giữa các Đặc trưng Review TV6 Bàn giao](../../data/tv6/figures/fig_5_1_feature_correlation_matrix.png)
![Fig 5.2: Đối chiếu Điểm Sao Gốc (Avg Rating) vs Điểm Cảm xúc PhoBERT (Avg Sentiment)](../../data/tv6/figures/fig_5_2_sentiment_vs_rating_scatter.png)
![Fig 5.3: Phân bố Điểm Cảm xúc 5 Khía cạnh Kỹ thuật trên các Sản phẩm Cha](../../data/tv6/figures/fig_5_3_aspect_scores_distribution.png)

### 8.6.1. Hợp đồng Bàn giao & Giải quyết Thách thức Cold-Start
Để phục vụ bài toán huấn luyện mô hình dự đoán giá của TV5, TV6 đã đóng gói toàn bộ tri thức khai phá được thành bảng dữ liệu đặc trưng chuẩn mực cấp sản phẩm cha (`source_parent_id`), bao phủ toàn bộ **7.051 sản phẩm cha** của thị trường:
1. **Kiểm toán Chống Rò rỉ Dữ liệu (Anti-Leakage Audit)**: Đạt chứng chỉ **100% PASS** trên toàn bộ 15.316 cặp thời gian (`review_time_raw <= crawl_time`), 0 vi phạm rò rỉ thời gian.
2. **Cờ nhị phân `has_review_data`**:
   - $1.897$ sản phẩm Active ($26,90\%$) $\rightarrow$ `has_review_data = 1`.
   - $5.154$ sản phẩm Cold-Start ($73,10\%$) $\rightarrow$ `has_review_data = 0`.
3. **Quy tắc Điền khuyết có Cơ sở Khoa học**:
   - `avg_sentiment_score = 0.0` (trung tính tuyệt đối).
   - Toàn bộ điểm khía cạnh `aspect_sentiment_score_*` và tỷ lệ `*_ratio` gán `= 0.0`.
   - `avg_rating = null` (trong Parquet/CSV, TV5 có thể điền median thị trường $4,50★$ hoặc để GBDT tự phân nhánh).

### Bảng 8.6: Từ điển 35 Đặc trưng Bàn giao Cho Mô hình Dự đoán Giá của TV5

| Tên Đặc trưng (`feature_name`) | Kiểu dữ liệu | Miền giá trị | Xử lý Cold-Start | Ý nghĩa & Hướng dẫn Sử dụng trong Mô hình TV5 |
|:---|:---|:---|:---|:---|
| `source_parent_id` | string | Chuỗi băm Hex 32 ký tự | Khóa chính (Không null) | Khóa định danh sản phẩm cha để join trực tiếp với `dim_source_parents` và `fact_listings_features`. |
| `source` | string | `cellphones`, `fptshop`, `tgdd`... | Giữ nguyên | Sàn thương mại điện tử phân phối sản phẩm, phục vụ phân nhóm hoặc target encoding. |
| `category` | string | `laptop`, `smartphone` | Giữ nguyên | Danh mục phần cứng công nghệ. |
| `product_name_rep` | string | Văn bản UTF-8 | Giữ nguyên | Tên sản phẩm đại diện dùng cho kiểm toán và hiển thị. |
| `has_review_data` | int8 | $0$ hoặc $1$ | $0$ | Cờ nhị phân phân tách sản phẩm có review vs Cold-Start (73.1%). Feature cực kỳ quan trọng cho mô hình cây (LightGBM/XGBoost). |
| `review_count_usable` | int32 | $0 \rightarrow 171$ | $0$ | Khối lượng đánh giá hợp lệ. Phản ánh độ phổ biến và thanh khoản của sản phẩm trên thị trường. |
| `review_count_last_90d` | int32 | $0 \rightarrow 19$ | $0$ | Số lượng review trong 90 ngày gần nhất tính đến snapshot crawl. Thước đo động lượng bán hàng (sales momentum). |
| `avg_rating` | float32 | $[1.0, 5.0]$ | `null` | Điểm đánh giá sao trung bình. TV5 có thể điền median thị trường (4.50) kết hợp với cờ `has_review_data=0`. |
| `rating_std` | float32 | $[0.0, 2.83]$ | $0.0$ | Độ lệch chuẩn điểm rating. Đo lường mức độ đồng thuận hay phân cực của người mua đối với sản phẩm. |
| `rating_min` | int8 | $[1, 5]$ | `null` | Điểm sao thấp nhất từng nhận được. Đo lường rủi ro trải nghiệm xấu. |
| `rating_max` | int8 | $[1, 5]$ | `null` | Điểm sao cao nhất từng nhận được. |
| `avg_sentiment_score` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm cảm xúc thực chất liên tục từ PhoBERT SOTA. Hiệu chỉnh các trường hợp đánh giá bất nhất (rating 5★ nhưng chê sản phẩm). |
| `sentiment_positive_ratio` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ lệ review mang sắc thái khen ngợi, hài lòng. |
| `sentiment_negative_ratio` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ lệ review mang sắc thái phàn nàn, sự cố phần cứng hoặc bảo hành kém. |
| `sentiment_neutral_ratio` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ lệ review trung tính hoặc pha trộn khen chê. |
| `sentiment_net_score` | float32 | $[-1.0, +1.0]$ | $0.0$ | Chỉ số Net Sentiment = pos_ratio - neg_ratio. Đại diện cho thiện cảm thương hiệu tổng hòa. |
| `aspect_mention_rate_battery_power` | float32 | $[0.0, 1.0]$ | $0.0$ | Tần suất người dùng đề cập đến thời lượng pin, tốc độ sạc hoặc củ sạc đi kèm. |
| `aspect_sentiment_score_battery_power` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm hài lòng riêng về pin và củ sạc (-1 tiêu cực, 0 trung tính, +1 tích cực). |
| `aspect_mention_rate_performance_thermal` | float32 | $[0.0, 1.0]$ | $0.0$ | Tần suất đề cập đến hiệu năng CPU/GPU, FPS game, độ mượt, tản nhiệt hoặc tiếng quạt. |
| `aspect_sentiment_score_performance_thermal` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm đánh giá về sức mạnh cấu hình và nhiệt độ (yếu tố ảnh hưởng mạnh đến phân khúc giá cao cấp). |
| `aspect_mention_rate_display_design` | float32 | $[0.0, 1.0]$ | $0.0$ | Tần suất đề cập đến màn hình sắc nét, màu sắc, viền mỏng, độ phân giải, vỏ kim loại/nhựa. |
| `aspect_sentiment_score_display_design` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm đánh giá thẩm mỹ và trải nghiệm thị giác của sản phẩm. |
| `aspect_mention_rate_camera_audio` | float32 | $[0.0, 1.0]$ | $0.0$ | Tần suất đề cập đến camera chụp đêm, góc rộng, âm lượng loa, mic thoại. |
| `aspect_sentiment_score_camera_audio` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm đánh giá khả năng quay chụp và giải trí đa phương tiện. |
| `aspect_mention_rate_service_logistics` | float32 | $[0.0, 1.0]$ | $0.0$ | Tần suất đề cập đến tư vấn, đóng gói, giao hàng, bảo hành của shop. |
| `aspect_sentiment_score_service_logistics` | float32 | $[-1.0, +1.0]$ | $0.0$ | Điểm đánh giá chất lượng phục vụ của kênh bán lẻ. |
| `topic_share_performance_setup` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ trọng đánh giá thuộc chủ đề LDA 0 (Cấu hình, thông số, bảo hành kỹ thuật). |
| `topic_share_screen_camera` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ trọng đánh giá thuộc chủ đề LDA 1 (Màn hình hiển thị, quay chụp camera). |
| `topic_share_battery_charging` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ trọng đánh giá thuộc chủ đề LDA 2 (Pin sạc, phụ kiện đi kèm). |
| `topic_share_service_delivery` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ trọng đánh giá thuộc chủ đề LDA 3 (Giao hàng, đóng gói, chăm sóc khách hàng). |
| `topic_share_usage_experience` | float32 | $[0.0, 1.0]$ | $0.0$ | Tỷ trọng đánh giá thuộc chủ đề LDA 4 (Trải nghiệm thực tế, mượt mà, sự cố phát sinh). |
| `earliest_review_time` | string (ISO) | 2019 $\rightarrow$ 2026 | `null` | Thời điểm nhận review đầu tiên của model sản phẩm. |
| `latest_review_time` | string (ISO) | 2019 $\rightarrow$ 2026 | `null` | Thời điểm nhận review gần nhất trước ngày snapshot cào dữ liệu. |
| `review_span_days` | float32 | $\ge 0.0$ | $0.0$ | Số ngày tồn tại trên thị trường có hoạt động review (ước lượng vòng đời sản phẩm lifecycle). |
| `tv6_pipeline_version` | string | `tv6-v1.0.0` | `tv6-v1.0.0` | Phiên bản mã nguồn pipeline TV6 đảm bảo tính truy nguyên khoa học dữ liệu. |

### Bảng 8.7: Thống kê Phân vị Đặc trưng Bàn giao (Toàn thị trường vs Nhóm có Review)

| Tên Đặc trưng | Trung bình Thị trường ($N=7.051$) | Trung vị Thị trường | Trung bình Nhóm có Review ($N=1.897$) | Độ lệch chuẩn Nhóm Review | Giá trị Min | Trung vị Nhóm Review | Giá trị Max |
|:---|---:|---:|---:|---:|---:|---:|---:|
| `review_count_usable` | 2,11 | 0 | **7,84** | 12,09 | 1 | 3 | 171 |
| `review_count_last_90d` | 0,07 | 0 | **0,27** | 1,11 | 0 | 0 | 19 |
| `avg_rating` | 4,72 | 5,00 | **4,72** | 0,61 | 1,00 | 5,00 | 5,00 |
| `rating_std` | 0,06 | 0 | **0,24** | 0,40 | 0 | 0 | 2,83 |
| `avg_sentiment_score` | 0,23 | 0 | **0,85** | 0,32 | -0,95 | 0,97 | 0,97 |
| `sentiment_positive_ratio` | 0,25 | 0 | **0,91** | 0,23 | 0 | 1,00 | 1,00 |
| `sentiment_negative_ratio` | 0,01 | 0 | **0,04** | 0,15 | 0 | 0 | 1,00 |
| `sentiment_net_score` | 0,24 | 0 | **0,88** | 0,35 | -1,00 | 1,00 | 1,00 |
| `aspect_sentiment_score_battery_power` | 0,07 | 0 | **0,28** | 0,50 | -1,00 | 0 | 1,00 |
| `aspect_sentiment_score_performance_thermal` | 0,09 | 0 | **0,32** | 0,58 | -1,00 | 0 | 1,00 |
| `aspect_sentiment_score_display_design` | 0,12 | 0 | **0,45** | 0,52 | -1,00 | 0 | 1,00 |
| `aspect_sentiment_score_camera_audio` | 0,05 | 0 | **0,18** | 0,43 | -1,00 | 0 | 1,00 |
| `aspect_sentiment_score_service_logistics` | 0,13 | 0 | **0,48** | 0,53 | -1,00 | 0,67 | 1,00 |
| `review_span_days` | 59,07 | 0 | **219,57** | 316,86 | 0 | 68,8 | 2.434,9 |

### 8.6.2. Giá trị Thặng dư của Đặc trưng NLP đối với TV5
- **Hiệu chỉnh Hiện tượng Lạm phát Sao**: Phân tích đối chiếu giữa `avg_rating` và `avg_sentiment_score` (Biểu đồ 5.2) chứng minh rằng tại cùng mức điểm $5.0★$, điểm cảm xúc PhoBERT thực tế dao động rất mạnh từ $0,35$ đến $0,98$. Những model máy bị lỗi tản nhiệt hoặc nhanh tụt pin được PhoBERT hạ điểm cảm xúc xuống sâu, cung cấp tín hiệu định giá nhạy bén mà thông số phần cứng tĩnh không thể có.
- **Tương quan và Tính trực giao**: Điểm số các khía cạnh công nghệ có độ tương quan vừa phải ($r \in [0,30; 0,55]$), khẳng định chúng đóng góp các đặc trưng độc lập bổ sung cho các mô hình Gradient Boosted Trees (LightGBM/XGBoost/CatBoost).

### 8.6.3. Mã Nguồn Mẫu Tích hợp Bảng Đặc trưng Cho TV5
```python
import pandas as pd
import lightgbm as lgb

# 1. Tải bảng đặc trưng review TV6 (định dạng Parquet tốc độ cao)
df_review_features = pd.read_parquet("data/tv6/tv5_review_features.parquet")
print(f"Loaded TV6 review features: {df_review_features.shape}")

# 2. Tải bảng dữ liệu listing của TV5
df_listings = pd.read_json("data/gold_v2/fact_listings_features.jsonl", lines=True)

# 3. Nối bảng đặc trưng theo khóa canonical source_parent_id (Left Join)
df_merged = df_listings.merge(
    df_review_features.drop(columns=["source", "category", "product_name_rep"]),
    on="source_parent_id",
    how="left",
)

# 4. Kiểm tra tỷ lệ Cold-Start và điền giá trị khuyết an toàn
print(f"Merged dataset shape: {df_merged.shape}")
print(f"Cold-start listings ratio: {(df_merged['has_review_data'] == 0).mean():.2%}")

# Điền median thị trường cho avg_rating nếu dùng mô hình Linear
market_median_rating = df_review_features["avg_rating"].median() # 5.0
df_merged["avg_rating_imputed"] = df_merged["avg_rating"].fillna(market_median_rating)

# 5. Huấn luyện mô hình LightGBM với các đặc trưng NLP
features = [
    "installed_ram_gb", "storage_gb", "screen_size_inch", "battery_mah",
    "has_review_data", "review_count_usable", "avg_rating", "avg_sentiment_score",
    "sentiment_positive_ratio", "sentiment_negative_ratio", "sentiment_net_score",
    "aspect_sentiment_score_performance_thermal", "aspect_sentiment_score_battery_power",
    "aspect_sentiment_score_display_design", "aspect_sentiment_score_camera_audio",
    "aspect_sentiment_score_service_logistics",
]
target = "price_vnd"

train_data = df_merged.dropna(subset=[target]).query("is_price_missing == False and price_vnd > 0")
X, y = train_data[features], train_data[target]
print(f"Sẵn sàng huấn luyện mô hình TV5 với {len(features)} đặc trưng!")
```

---

## 8.7. Kết luận, Đóng góp Khoa học & Hướng Mở rộng

### 8.7.1. Tổng kết Đóng góp Khoa học của Phân hệ TV6
1. **Thiết lập Pipeline NLP Tiếng Việt Toàn diện**: Xây dựng thành công chuỗi xử lý khép kín từ dữ liệu cào thô đa nguồn, chuẩn hóa Unicode, khử nhập nhằng ngữ cảnh 26 cụm từ đa nghĩa công nghệ, đến trích xuất đặc trưng phục vụ downstream tasks.
2. **Làm chủ Mô hình Transformer SOTA trên Hạ tầng GPU Cá nhân**: Huấn luyện thành công PhoBERT với kỹ thuật tối ưu hóa bộ nhớ hiện đại (Mixed Precision FP16 AMP, Class-Weighted Loss), đạt đỉnh hiệu năng phân loại cảm xúc **Accuracy $92,23\%$**, **Macro F1 $0,6491$**, vượt trội baseline machine learning $+10,0\%$.
3. **Khai phá Tri thức Đa chiều về Thị trường Công nghệ**: Xác định rõ ràng các chủ đề và khía cạnh nhạy cảm nhất đối với người tiêu dùng (Hiệu năng tản nhiệt là điểm nóng phàn nàn lớn nhất, Dịch vụ là khía cạnh làm hài lòng nhất).
4. **Bàn giao Hoàn hảo cho TV5**: Cung cấp bộ 35 đặc trưng cấp sản phẩm cha đạt chuẩn kiểm toán chống rò rỉ $100\%$, định dạng Parquet tốc độ cao, xử lý triệt để thách thức Cold-Start $73,10\%$.
5. **Đảm bảo Tính Tái hiện & Kiểm thử Toàn diện**: Toàn bộ hệ thống được bảo vệ bởi **38 unit tests tự động**, đạt tỷ lệ **PASS 100%**.

### 8.7.2. Hướng Mở rộng trong Tương lai
- **Trích xuất Khía cạnh Nâng cao bằng Large Language Models (LLMs)**: Tận dụng các mô hình ngôn ngữ lớn (Gemini 2.5 Flash, PhoGPT) với kỹ thuật In-Context Learning / Zero-shot để nhận diện các khía cạnh siêu nhỏ (micro-aspects) như độ nhạy touchpad, hành trình phím, tốc độ vân tay dưới màn hình.
- **Mô hình Đa phương thức (Multimodal Review Intelligence)**: Kết hợp phân tích văn bản với hình ảnh và video unboxing thực tế do người dùng tải lên để phát hiện sớm các lỗi trầy xước, nứt vỡ hoặc hàng giả/hàng nhái trên sàn thương mại điện tử.

---

## 8.8. Bảng Tổng hợp Tệp Đầu ra & Lệnh Tái hiện Toàn bộ Phân hệ TV6

### Danh mục Tệp Artifacts Canonical:
- **Dữ liệu View & NLP**:
  * [`data/tv6/reviews_tv6_all.jsonl`](../../data/tv6/reviews_tv6_all.jsonl) ($15.805$ bản ghi)
  * [`data/tv6/reviews_tv6_usable.jsonl`](../../data/tv6/reviews_tv6_usable.jsonl) ($14.869$ bản ghi)
  * [`data/tv6/reviews_tv6_preprocessed.jsonl`](../../data/tv6/reviews_tv6_preprocessed.jsonl) ($196.819$ tokens)
  * [`data/tv6/reviews_tv6_aspects.jsonl`](../../data/tv6/reviews_tv6_aspects.jsonl) ($14.869$ bản ghi enriched)
- **Dữ liệu Bàn giao TV5**:
  * [`data/tv6/tv5_review_features.parquet`](../../data/tv6/tv5_review_features.parquet) ($7.051$ dòng x $35$ cột)
  * [`data/tv6/tv5_review_features.csv`](../../data/tv6/tv5_review_features.csv) ($7.051$ dòng x $35$ cột)
- **Báo cáo Metadata Máy đọc được**:
  * [`data/tv6/quality_report.json`](../../data/tv6/quality_report.json)
  * [`data/tv6/preprocessing_report.json`](../../data/tv6/preprocessing_report.json)
  * [`data/tv6/sentiment_baseline_report.json`](../../data/tv6/sentiment_baseline_report.json)
  * [`data/tv6/sentiment_phobert_report.json`](../../data/tv6/sentiment_phobert_report.json)
  * [`data/tv6/topic_aspect_report.json`](../../data/tv6/topic_aspect_report.json)
  * [`data/tv6/tv5_feature_report.json`](../../data/tv6/tv5_feature_report.json)
- **Báo cáo Đồ án Hoàn chỉnh (File Duy nhất)**:
  * [`docs/tv6/report_part8.md`](./report_part8.md)

### Lệnh Chạy Tái hiện Toàn bộ Pipeline TV6:
```bash
# 1. Bước 0: Tạo View phân tích độc lập
python src/review_nlp/run_step0.py

# 2. Bước 1: Thống kê & Kiểm toán EDA
python src/review_nlp/run_step1.py

# 3. Bước 2: Tiền xử lý & Tokenization NLP tiếng Việt
python src/review_nlp/run_step2.py

# 4. Bước 3.1: Phân loại Cảm xúc ML Baseline
python src/review_nlp/run_step3_1.py

# 5. Bước 3.2: Fine-Tuning PhoBERT SOTA trên GPU
python src/review_nlp/run_step3_2.py

# 6. Bước 4: Topic Modeling (LDA) & Phân tích Khía cạnh (ABSA)
python src/review_nlp/run_step4.py

# 7. Bước 5: Tổng hợp Đặc trưng Bàn giao cho TV5 (Parquet & CSV)
python src/review_nlp/run_step5.py

# 8. Thực thi toàn bộ bộ kiểm thử tự động của TV6 (38/38 tests PASS 100%):
python -m unittest discover -s tests -p "test_tv6_*.py" -v
```
