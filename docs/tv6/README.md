# TV6 – Review NLP Sentiment Analysis (Documentation Hub)

Chào mừng bạn đến với trung tâm tài liệu của **Thành viên 6 (TV6)** trong dự án **IT4930 E-Commerce Data Intelligence**.

TV6 chịu trách nhiệm tiếp nhận dữ liệu review thương mại điện tử từ TV2 (Gold v2), xây dựng pipeline tiền xử lý ngôn ngữ tự nhiên (NLP tiếng Việt), kiểm toán chất lượng nội dung đánh giá (EDA), huấn luyện mô hình phân loại cảm xúc (Sentiment Analysis), khai phá từ khóa & khía cạnh đánh giá (Aspect Mining), bàn giao bảng đặc trưng tổng hợp theo sản phẩm cho **TV5 (Price Prediction)**, và hoàn thiện **Phần 8** của báo cáo dự án.

---

## 1. Báo Cáo Tổng Thể Chính Thức (Tệp Duy Nhất)

Toàn bộ báo cáo học thuật, phương pháp luận, bảng số liệu, biểu đồ trực quan hóa và code mẫu tích hợp của phân hệ TV6 từ Bước 0 đến Bước 6 đã được hợp nhất toàn diện trong một tệp duy nhất:

👉 [**report_part8.md**](report_part8.md) – **PHẦN 8: XỬ LÝ NGÔN NGỮ TỰ NHIÊN & KHAI PHÁ DỮ LIỆU ĐÁNH GIÁ (REVIEW NLP & SENTIMENT ANALYSIS)**

### Tóm tắt các Mục trong Báo cáo `report_part8.md`:
- **Mục 8.1**: Tổng quan phân hệ TV6, kiến trúc View phân tích độc lập & cam kết bảo toàn dữ liệu 100% ($15.805 = 14.869 \text{ usable} + 936 \text{ unusable}$).
- **Mục 8.2**: Kiểm toán chất lượng & khám phá dữ liệu (EDA), hiện tượng "Lạm phát sao 5★", $118$ trường hợp rating–text mismatch, phân tích độ dài và kiểm toán Cold-Start ($73,1\%$).
- **Mục 8.3**: Pipeline tiền xử lý văn bản tiếng Việt 7 tầng, 79 quy tắc teencode & giải pháp khử nhập nhằng ngữ cảnh 26 cụm đa nghĩa (`bh`, `cam`, `kg`, `mh`, `sd`...).
- **Mục 8.4**: Phân loại cảm xúc đa lớp, đối sánh Baseline ML vs PhoBERT Transformer SOTA (`vinai/phobert-base-v2`, Macro F1 $0,6491$, Accuracy $92,23\%$), luận giải khoa học về 3 epochs.
- **Mục 8.5**: Khai phá chủ đề tiềm ẩn (LDA Perplexity $1.186,9$) và phân tích cảm xúc 5 khía cạnh công nghệ (ABSA), so sánh hành vi giữa Laptop vs Smartphone, WordCloud đối sánh.
- **Mục 8.6**: Hợp đồng bàn giao 35 đặc trưng cấp `source_parent_id` cho TV5, kiểm toán chống rò rỉ dữ liệu ($100\%$ PASS), xử lý Cold-Start và code mẫu tích hợp LightGBM.
- **Mục 8.7 & 8.8**: Đóng góp khoa học, hướng mở rộng và danh mục câu lệnh tái hiện.

---

## 2. Cấu trúc Mã nguồn (`src/review_nlp/`)

```text
src/review_nlp/
├── __init__.py                 # Khởi tạo package TV6
├── config.py                   # Cấu hình đường dẫn, danh sách trường canonical, phiên bản pipeline
├── build_view.py               # Module xử lý cốt lõi Bước 0 (ingest, transform, filter, export, manifest)
├── run_step0.py                # Entry point thực thi Bước 0 từ CLI
├── eda_quality.py              # Module xử lý cốt lõi Bước 1 (EDA, thống kê, kiểm toán, sinh biểu đồ)
├── run_step1.py                # Entry point thực thi Bước 1 từ CLI
├── vietnamese_nlp_utils.py     # Thư viện hàm NLP tiếng Việt (Unicode, teencode, emojis, underthesea, safe stopwords)
├── preprocess.py               # Module xử lý cốt lõi Bước 2 (chạy pipeline tiền xử lý trên toàn bộ tập dữ liệu)
├── run_step2.py                # Entry point thực thi Bước 2 từ CLI
├── sentiment_baseline.py       # Module xử lý cốt lõi Bước 3.1 (huấn luyện, cross-validation, trích xuất feature)
├── run_step3_1.py              # Entry point thực thi Bước 3.1 từ CLI
├── phobert_sentiment.py        # Module xử lý cốt lõi Bước 3.2 (Fine-tuning PhoBERT Transformer, AMP FP16, Weighted Loss)
├── run_step3_2.py              # Entry point thực thi Bước 3.2 từ CLI
├── topic_aspect_mining.py      # Module xử lý cốt lõi Bước 4 (Topic Modeling LDA/NMF, ABSA 5 khía cạnh, WordCloud)
├── run_step4.py                # Entry point thực thi Bước 4 từ CLI
├── feature_engineering_tv5.py  # Module xử lý cốt lõi Bước 5 (Tổng hợp đặc trưng cấp parent, xử lý Cold-Start, chống leakage)
└── run_step5.py                # Entry point thực thi Bước 5 từ CLI
```

---

## 3. Dữ liệu Đầu ra (`data/tv6/`)

```text
data/tv6/
├── reviews_tv6_all.jsonl          # 15.805 bản ghi (Toàn bộ reviews kèm cờ chất lượng & truy nguyên raw)
├── reviews_tv6_usable.jsonl       # 14.869 bản ghi (Tập review sạch, có text, sẵn sàng cho NLP)
├── reviews_tv6_unusable.jsonl     # 936 bản ghi (Tập review rỗng/thiếu text, được cách ly phục vụ audit)
├── reviews_tv6_preprocessed.jsonl # 14.869 bản ghi (Tập review ĐÃ TIỀN XỬ LÝ & TOKENIZED)
├── reviews_tv6_sentiment_baseline.jsonl # 14.869 bản ghi (Tập review ĐÃ GÁN ĐIỂM SENTIMENT BASELINE)
├── reviews_tv6_sentiment_phobert.jsonl  # 14.869 bản ghi (Tập review ĐÃ GÁN ĐIỂM SENTIMENT PHOBERT)
├── reviews_tv6_aspects.jsonl      # 14.869 bản ghi (Tập review ĐÃ GÁN CHỦ ĐỀ LDA & 5 KHÍA CẠNH ABSA)
├── tv5_review_features.parquet    # 7.051 dòng x 35 cột (BẢNG ĐẶC TRƯNG TOÀN THỊ TRƯỜNG BÀN GIAO CHO TV5)
├── tv5_review_features.csv        # 7.051 dòng x 35 cột (Bản CSV tương đương phục vụ kiểm toán)
├── tv5_review_features_active_only.parquet # 1.897 dòng x 35 cột (Tập con các sản phẩm có review)
├── tv5_review_features_active_only.csv     # 1.897 dòng x 35 cột (Bản CSV tập con có review)
├── quality_report.json            # Báo cáo JSON toàn diện Bước 1
├── preprocessing_report.json      # Báo cáo JSON tiền xử lý Bước 2
├── sentiment_baseline_report.json # Báo cáo JSON baseline cảm xúc Bước 3.1
├── sentiment_phobert_report.json  # Báo cáo JSON PhoBERT cảm xúc Bước 3.2
├── topic_aspect_report.json       # Báo cáo JSON khai phá chủ đề & khía cạnh Bước 4
├── tv5_feature_report.json        # Báo cáo JSON kiểm toán chống rò rỉ & tổng hợp đặc trưng Bước 5
├── view_manifest_step0.json       # Manifest xác thực số liệu Bước 0
├── tables/                        # 20 bảng thống kê song song CSV và Markdown (table_1_1 -> table_5_3)
└── figures/                       # 14 biểu đồ chất lượng cao định dạng PNG DPI >= 300 (fig_1_1 -> fig_5_3)
```

---

## 4. Hướng dẫn Lệnh Chạy Tái Hiện Nhanh

```bash
# 1. Chạy sinh View phân tích Bước 0:
python src/review_nlp/run_step0.py

# 2. Chạy sinh toàn bộ Bảng và Biểu đồ EDA Bước 1:
python src/review_nlp/run_step1.py

# 3. Chạy pipeline Tiền xử lý & Tokenization Bước 2:
python src/review_nlp/run_step2.py

# 4. Chạy pipeline Sentiment Classification ML Baseline Bước 3.1:
python src/review_nlp/run_step3_1.py

# 5. Chạy fine-tuning PhoBERT Transformer SOTA Bước 3.2 (trên GPU CUDA):
python src/review_nlp/run_step3_2.py

# 6. Chạy pipeline Topic Modeling & Aspect-Based Sentiment Analysis Bước 4:
python src/review_nlp/run_step4.py

# 7. Chạy pipeline Tổng hợp Đặc trưng Bàn giao cho TV5 Bước 5:
python src/review_nlp/run_step5.py

# 8. Chạy toàn bộ 38 bài kiểm thử tự động của phân hệ TV6 (100% PASS):
python -m unittest discover -s tests -p "test_tv6_*.py" -v
```
