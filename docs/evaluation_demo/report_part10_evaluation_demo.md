# Phần 10. Đánh giá mô hình, giải thích dự đoán và demo

**Dự án IT4930 — Thành viên 8**

TV8 đánh giá khả năng ước lượng **giá niêm yết tại đợt thu thập** của laptop và điện thoại. Công việc gồm đối chiếu sáu mô hình TV5, tìm các nhóm hay dự đoán sai, đo tác động của dữ liệu TV3–TV7, giải thích dự đoán và đưa kết quả vào một demo có thể chạy cục bộ. Các kết quả dưới đây sử dụng cùng một phép chia dữ liệu, nên chênh lệch giữa các phiên bản có thể đối chiếu theo từng dòng test.

## 10.1. Dữ liệu và cách đánh giá

Dữ liệu đầu vào lấy từ `data/processed/` đã hợp nhất trên `main` (kết hợp bảng ánh xạ `listing_id_crosswalk.csv` để đồng bộ mã `listing_record_id` giữa bản `products_cleaned.jsonl` / TV4 và bản `products_processed.jsonl` / TV7). Ghép bảng đã làm sạch với bảng processed khớp đủ **8.374/8.374 dòng**. Sau các ngưỡng giá và bộ lọc bản ghi hỏng `_is_corrupted_record()` của TV5 (laptop từ 3 triệu đồng, điện thoại từ 1 triệu đồng), còn **8.132 dòng** đủ điều kiện. Dùng `GroupShuffleSplit` với seed 42 và nhóm `source_parent_id`. Các biến thể cùng sản phẩm cha trong một nguồn vào cùng một tập. Cùng một dòng máy ở hai cửa hàng có thể mang hai mã cha khác nhau, vì vậy đây là đánh giá theo nhóm sản phẩm cha trong nguồn.

| Loại thiết bị | Train | Test |
|---|---:|---:|
| Laptop | 3.227 | 819 |
| Điện thoại | 3.276 | 810 |

Mã định danh được giữ riêng để ghép và kiểm toán. Mô hình hồi quy học trên `log1p(giá)`, sau đó đổi kết quả về VNĐ trước khi tính sai số. Giá gốc, tỷ lệ giảm giá, cụm đồ thị có dùng giá và cờ bất thường cũng nằm ngoài đầu vào. TV8 tái tạo đúng phép chia của TV5 với **1.629 dòng test** không trùng `source_parent_id`. [Mã chia dữ liệu](../../src/evaluation_demo/prepare_test_data.py)

Đề cương nêu chiến lược kết hợp 10-fold cross-validation với tập kiểm thử độc lập. Mã TV5 dùng `GroupKFold(n_splits=10)` để tìm tham số Random Forest và LightGBM trong train. Phần 10.2–10.3 đánh giá 6 mô hình TV5 đã tích hợp đầy đủ đặc trưng liên nhóm trên `main`, còn Phần 10.4–10.6 giữ nguyên chuỗi thử nghiệm ablation có kiểm soát `S1–S5` trên snapshot cơ sở `24cd858`. [Mã huấn luyện Random Forest](../../src/price_prediction/models/training_rf.py) · [Mã huấn luyện LightGBM](../../src/price_prediction/models/training_lgbm.py)

## 10.2. So sánh sáu mô hình TV5

MAE là trung bình độ lệch tuyệt đối và RMSE phạt mạnh các dự đoán sai lớn. MdAE, MAPE, MdAPE và R² bổ sung cách nhìn về trung vị, sai số theo tỷ lệ và mức độ khớp. Thời gian là trung bình của 30 lần dự đoán từng dòng sau lượt làm nóng, tính trên máy chạy thử và bỏ thời gian nạp mô hình. Độ nhạy được đo bằng mức tăng MAE sau khi che ngẫu nhiên 20% giá trị đang có của RAM và 20% giá trị đang có của bộ nhớ, dùng cùng mặt nạ giữa ba mô hình của mỗi loại thiết bị.

| Thiết bị | Mô hình | MAE (triệu đ) | RMSE (triệu đ) | R² | ms/mẫu | MB | MAE tăng khi thiếu thông số |
|---|---|---:|---:|---:|---:|---:|---:|
| Laptop | Ridge | 4,279 | 7,035 | 0,883 | 87,54 | 0,125 | +13,50% |
| Laptop | Random Forest | 3,828 | 6,992 | 0,884 | 130,49 | 49,476 | +24,61% |
| Laptop | LightGBM | 3,489 | 6,080 | 0,912 | 144,05 | 2,546 | +29,60% |
| Điện thoại | Ridge | 2,185 | 3,265 | 0,952 | 66,73 | 0,062 | +17,47% |
| Điện thoại | Random Forest | 2,115 | 3,407 | 0,948 | 113,37 | 32,187 | +19,29% |
| Điện thoại | LightGBM | 1,865 | 3,023 | 0,959 | 116,10 | 1,986 | +18,81% |

LightGBM có MAE thấp nhất, RMSE thấp nhất và R² cao nhất trên cả hai loại thiết bị (`0,912` cho Laptop và `0,959` cho Điện thoại). Ridge có tệp nhỏ nhất (`0,062`–`0,125` MB) và dự đoán nhanh nhất. [Bảng 10.1 — Kết quả đầy đủ](../../src/evaluation_demo/outputs/tables/table_10_1_model_benchmark_3d.csv)

## 10.3. Mô hình sai ở đâu?

Sai số có dấu bằng giá dự đoán trừ giá ghi nhận. Một điểm âm trên Hình 10.1 cho biết mô hình định giá thấp hơn dữ liệu. Hình 10.2 dùng MAE và số dòng của các nhóm giá và cửa hàng để đọc sai số cùng với cỡ mẫu.

- **Theo khoảng giá.** LightGBM điện thoại có MAE **0,934 triệu đồng** trên 443 dòng dưới 10 triệu, so với **3,543 triệu đồng** trên 79 dòng trên 35 triệu (định giá thấp hơn trung bình **0,481 triệu đồng**, và **1,796 triệu đồng** ở nhóm 20–35 triệu trên 121 dòng). [Bảng 10.3](../../src/evaluation_demo/outputs/tables/table_10_3_error_by_price_tier.csv)
- **Theo hãng và nhà bán lẻ.** Các nhóm có số dòng rất khác nhau. Khi trình bày chênh lệch MAE, đọc `n_test` cùng với giá trị sai số, nhất là ở hãng hoặc cửa hàng ít mẫu. [Bảng 10.4](../../src/evaluation_demo/outputs/tables/table_10_4_error_by_brand_and_seller.csv)
- **Theo tồn kho và mức đầy đủ thông số.** LightGBM điện thoại có MAE **2,407 triệu** ở 108 dòng thiếu RAM và **1,781 triệu** ở 702 dòng có RAM. Theo tồn kho, hai nhóm còn hàng và hết hàng có MAE lần lượt **1,650** và **1,950 triệu đồng**. Đây là chênh lệch quan sát trên những nhóm khác nhau. [Bảng 10.5](../../src/evaluation_demo/outputs/tables/table_10_5_error_by_stock_and_missingness.csv)
- **Theo cấu hình đã thấy ở cửa hàng khác.** Dùng khóa hãng, model, RAM và bộ nhớ để tìm trong train. LightGBM điện thoại có MAE **1,298 triệu** trên 167 dòng tìm được ở cửa hàng khác và **1,858 triệu** trên 527 dòng có đủ cấu hình nhưng chưa gặp khóa trong train. Cùng khóa này vẫn có thể khác CPU hoặc các chi tiết khác. [Bảng 10.6](../../src/evaluation_demo/outputs/tables/table_10_6_cross_store_generalization.csv)
- **Hai mươi dòng sai nhiều nhất.** Mỗi dòng xuất hiện một lần, gắn mô hình sai nhiều nhất trong ba thuật toán, khớp 20/20 với bảng cờ TV7 mới nhất: có **1 dòng `extreme`**, **6 dòng `review`** và **13 dòng `none`**. Đứng đầu là `Laptop ASUS ROG Zephyrus DUO 16 GX651AX-SR050WS-Xám` ghi nhận **199,99 triệu đồng**, Random Forest dự đoán **125,17 triệu đồng** (cờ TV7 `review`). Đây là đầu mối để đối chiếu lại sản phẩm, gói bán và giá trên nguồn. [Bảng 10.7](../../src/evaluation_demo/outputs/tables/table_10_7_top20_worst_predictions_audit.csv)

[Hình 10.1 — Giá ghi nhận, dự đoán và sai số](../../src/evaluation_demo/outputs/figures/fig_10_1_residual_and_actual_vs_pred.png) · [Hình 10.2 — Sai số theo giá và cửa hàng](../../src/evaluation_demo/outputs/figures/fig_10_2_error_by_price_tier_and_seller.png)

## 10.4. Thử từng nhóm đặc trưng

**S1** huấn luyện lại bằng bộ đặc trưng của TV5, với Ridge `alpha=1`, Random Forest 200 cây và LightGBM 200 cây. S1 là mốc tham số cố định của TV8. Các mô hình đã tối ưu do TV5 bàn giao được dùng cho Bảng 10.1 và demo dự đoán. S2–S5 giữ tham số của S1 và cùng tập test, để so sánh khi đổi đầu vào hoặc lọc train.

**S2** thử cờ hết hàng, sửa màn hình `300 inch`, thêm công suất sạc và cờ thiếu sạc. Thông tin sạc laptop chỉ có ở **88/3.227 dòng train**. Khi so sánh trực tiếp với bản **S2A** gồm cờ hết hàng và sửa màn hình, hai cột về sạc giảm MAE ở LightGBM laptop và Random Forest điện thoại, các mô hình còn lại có mức tăng từ nhẹ đến gần 2,51%. Chọn S2A làm mốc chung cho S3. [Đối chiếu thông tin sạc](../../src/evaluation_demo/outputs/tables/s2_charger_comparison.csv)

**S3** thêm điểm CPU/GPU của TV4 và số cửa hàng có cùng nhóm hãng, model, RAM, bộ nhớ. Điểm phần cứng được ghép theo mã listing từ commit `a4874b0`. Test có điểm ở **729/819 CPU laptop**, **412/819 GPU laptop** và **497/797 CPU điện thoại**. Điểm thiếu được điền bằng trung vị train. Điện thoại dùng điểm CPU tổng hợp vì cột Geekbench 5 trùng điểm khi cả hai cùng có. Đếm các cửa hàng khác từ những cấu hình có trong train, rồi cộng cửa hàng của dòng đang xét nếu khóa đủ thông tin. So với S2A, MAE giảm ở cả ba mô hình laptop. LightGBM laptop giảm **8,76%**. Ở điện thoại, Ridge giảm nhẹ, còn Random Forest và LightGBM tăng nhẹ.

**S4** nối review TV6 từ commit `1d53f97` theo sản phẩm cha. Bản đếm thêm cờ có review và số review dùng được. Bản đầy đủ còn thêm cảm xúc chung, tỷ lệ tích cực, cảm xúc theo khía cạnh và trung bình cảm xúc theo hãng. Khi tính trung bình, mỗi sản phẩm cha có review trong train đóng góp một lần và giá trị của chính sản phẩm đó được loại khỏi phép tính nếu truy vấn một dòng train. Chỉ **234/819 laptop** và **551/797 điện thoại** trong test thực sự có review. TV6 chấm cảm xúc trên tập review của đợt thu thập với phép chia riêng ở cấp review, nên đây là đánh giá dùng kết quả bàn giao có sẵn trên snapshot.

| Thiết bị | Mô hình | S1 | S2A | S3 | S3 + bản đếm | S4 đầy đủ |
|---|---|---:|---:|---:|---:|---:|
| Laptop | Ridge | 4,945 | 4,813 | 4,552 | 4,406 | 4,573 |
| Laptop | Random Forest | 4,202 | 4,139 | 4,045 | 4,052 | 4,039 |
| Laptop | LightGBM | 4,064 | 4,074 | 3,717 | 3,672 | 3,726 |
| Điện thoại | Ridge | 2,681 | 2,695 | 2,675 | 2,676 | 2,664 |
| Điện thoại | Random Forest | 2,550 | 2,589 | 2,626 | 2,563 | 2,576 |
| Điện thoại | LightGBM | 2,469 | 2,457 | 2,469 | 2,441 | 2,398 |

*MAE tính bằng triệu đồng. Đường S1 → S2A → S3 → S4 là chuỗi thí nghiệm chính. Bản đếm là phép so riêng để xem giá trị bổ sung của cảm xúc.*

S4 giảm MAE ở cả ba mô hình điện thoại so với S3. Bản đếm vẫn tốt hơn S4 đầy đủ cho Random Forest điện thoại, Ridge laptop và LightGBM laptop. Trên nhóm có review, S4 giảm MAE ở cả sáu mô hình. Trên nhóm thiếu review, chỉ LightGBM điện thoại giảm. Điều này cho thấy lợi ích của review phụ thuộc vào độ phủ và thuật toán. [Kết quả theo nhóm có/thiếu review](../../src/evaluation_demo/outputs/tables/s4_review_comparison.csv)

## 10.5. Thử lọc dữ liệu theo cờ TV7

**S5a** lọc dòng train có `anomaly_severity=extreme`. **S5b** lọc mọi dòng train có `combined_flag`. Dùng cờ bàn giao ở commit `66f089b` cho so sánh hồi cứu. Do TV7 ban đầu dùng toàn bộ giá trong snapshot để tính cờ, TV8 chạy lần thứ hai bằng cách tính lại cờ chỉ từ tập train. Hai nguồn cờ được ghi riêng trong kết quả. Khi huấn luyện lại, các thống kê điền thiếu, số nhà bán lẻ và trung bình cảm xúc theo hãng được tính từ phần train còn lại.

| Thiết bị | Mô hình | S5a, cờ bàn giao | S5b, cờ bàn giao | S5a, cờ chỉ từ train | S5b, cờ chỉ từ train |
|---|---|---:|---:|---:|---:|
| Laptop | Ridge | −0,01% | −0,24% | −0,01% | −3,55% |
| Laptop | Random Forest | −0,36% | +7,67% | −0,36% | +8,10% |
| Laptop | LightGBM | +0,48% | +0,05% | +0,48% | +1,48% |
| Điện thoại | Ridge | +2,41% | +2,86% | +2,35% | +3,87% |
| Điện thoại | Random Forest | +5,57% | +2,90% | −1,04% | −0,73% |
| Điện thoại | LightGBM | +3,54% | +11,90% | −1,57% | +13,61% |

*Phần trăm thay đổi MAE so với S4. Giá trị âm là sai số giảm.*

Với cờ bàn giao, S5a bỏ 5 laptop và 10 điện thoại. S5b bỏ 121 laptop, 63 điện thoại, trong đó có **10/13 dòng train điện thoại giá từ 80 triệu đồng**. Trên 11 điện thoại test thuộc nhóm giá này, LightGBM có MAE **20,0 triệu** ở S4 và **40,4 triệu** ở S5b. Với cờ tính lại từ train, MAE nhóm giá cao ở S5b vẫn khoảng **40,3 triệu đồng**. Cờ TV7 là tín hiệu rà soát, nên giữ S4 làm mốc và xem các trường hợp gắn cờ trước khi quyết định loại dòng. [Bảng 10.2](../../src/evaluation_demo/outputs/tables/table_10_2_ablation_and_tv7_sensitivity.csv) · [Chi tiết S5](../../src/evaluation_demo/outputs/tables/s5_tv7_sensitivity_details.csv) · [Hình 10.3](../../src/evaluation_demo/outputs/figures/fig_10_3_ablation_and_sensitivity_chart.png)

## 10.6. Giải thích mô hình và kiểm tra RAM/bộ nhớ

TreeSHAP của LightGBM S4 được tính trên toàn bộ **819 laptop và 797 điện thoại test**. Trong biểu đồ tổng quan, mỗi điểm là một listing và giá trị dương đẩy dự đoán lên so với mức nền. Độ dài thanh bên phải là trung bình độ lớn đóng góp. Mẫu CPU đứng đầu ở cả hai loại thiết bị. Laptop tiếp theo là RAM × bộ nhớ và mẫu GPU. Điện thoại tiếp theo là bộ nhớ và thương hiệu. [Hình 10.4 — Laptop](../../src/evaluation_demo/outputs/figures/fig_10_4_shap_summary_laptop.png) · [Hình 10.5 — Điện thoại](../../src/evaluation_demo/outputs/figures/fig_10_5_shap_summary_smartphone.png)

Biểu đồ giải thích từng máy phân bổ chênh lệch giá từ mức nền sang VNĐ theo tỷ lệ các giá trị SHAP trên thang log. Kiểm tra cộng tính xác nhận mức nền và tổng đóng góp khớp dự đoán. Chẳng hạn, OPPO Reno7 Z 5G có mức nền **9,66 triệu đồng**, mẫu CPU đóng góp khoảng **−2,34 triệu** và bộ nhớ khoảng **−1,36 triệu**. Sau khi cộng tất cả, dự đoán **7,08 triệu đồng** so với giá ghi nhận **7,00 triệu đồng**. Các phần đóng góp giải thích cách mô hình tạo dự đoán trong trường hợp cụ thể. [Hình 10.6 — Ba ví dụ](../../src/evaluation_demo/outputs/figures/fig_10_6_shap_waterfall_examples.png)

Thử tăng RAM 8, 16, 32, 64 GB và bộ nhớ 128, 256, 512, 1.024 GB, mỗi lần thay một thông số của ASUS Vivobook 15 OLED hoặc OPPO Find N3. Các đầu vào còn lại lấy từ dòng tham chiếu. Các đặc trưng dẫn xuất của thông số đang thay tiếp tục được tính theo pipeline. Trong 12 đường thử, dự đoán giữ nguyên hoặc tăng giữa các mốc. Tuy nhiên, tập train điện thoại thiếu mức RAM 32 và 64 GB. Ridge lên tới **1,81 tỷ đồng** ở 64 GB trên cấu hình điện thoại giả lập. Đây là ví dụ về ngoại suy ngoài dữ liệu và là lý do demo giới hạn RAM điện thoại ở 24 GB, đồng thời cảnh báo mức cấu hình chưa thấy trong train. [Hình 10.7 — Phép thử dung lượng](../../src/evaluation_demo/outputs/figures/fig_10_7_monotonicity_sanity_check.png) · [Bảng dự đoán RAM/bộ nhớ](../../src/evaluation_demo/outputs/tables/monotonicity_sweeps.csv)

## 10.7. Hệ thống Hỗ trợ Quyết định Đa tầng (5-Tab Data Science Platform) và Bàn giao

Ứng dụng Streamlit tại `src/evaluation_demo/app.py` (kết hợp tầng dữ liệu `demo_data.py` và `market_data.py`) được nâng cấp thành **Hệ thống Trí tuệ Dữ liệu Thị trường & Thẩm định Giá Hợp lý Đa sàn** gồm **5 tab nghiệp vụ**, tích hợp xuyên suốt kết quả của toàn bộ 8 thành viên (TV1–TV8):

1. **Tab 1 — Tổng quan & Quy luật giá (TV1–TV3)**: Hiển thị các chỉ số toàn cảnh thị trường (`10.316` niêm yết, `15.805` đánh giá, `4.414` sản phẩm chuẩn, `8.132` mẫu sạch) và toàn bộ **15 biểu đồ EDA** kèm hộp phân tích 3 bước (*Câu hỏi nghiệp vụ → Phát hiện định lượng → Ý nghĩa kinh doanh & Quyết định hạ nguồn*).
2. **Tab 2 — Cạnh tranh đa sàn & Review (TV4 & TV6)**: Trình bày thống kê cạnh tranh của 5 chuỗi bán lẻ, ma trận trùng lặp danh mục Jaccard, phân khúc thị trường Louvain, bộ lọc tương tác **90 khoảng trống danh mục** (`68` điểm mù theo sàn + `22` phân khúc cầu cao ít sàn bán), đồ thị hai phía tương tác PyVis và phân tích tiếng nói khách hàng tiếng Việt (PhoBERT Sentiment, 5 chủ đề LDA, 5 khía cạnh ABSA).
3. **Tab 3 — Thẩm định giá hợp lý (TV5–TV8)**: Gồm 2 chế độ phục vụ đúng nhu cầu thực tế:
   - **Chế độ 1 (Mặc định — B2C & B2B): Thẩm định SKU đang niêm yết thực tế** trên 5 sàn (không bắt người dùng tự gõ tay cấu hình), đối chiếu *Giá niêm yết thực tế* với *Giá hợp lý theo cấu hình (Hedonic Fair Value)*, kết luận mức hời/đắt theo ngưỡng `±MdAPE`, giải thích đóng góp SHAP bằng VNĐ, hiển thị hồ sơ cờ kiểm toán TV7 (`anomaly_type`, `recommended_action`), tóm tắt review TV6 và bảng 5 cấu hình tương đương liên sàn.
   - **Chế độ 2 (Dành cho Quản trị ngành hàng B2B): Mô phỏng định giá SKU mới trong miền phần cứng tương thích** (`build_compatibility_options()`), khóa chặt tổ hợp linh kiện theo Hãng → Dòng máy → CPU → GPU/RAM/ROM, ngăn chặn triệt để các cấu hình phi vật lý (như chọn Apple kèm GPU RTX hoặc chip Snapdragon). Luồng tham chiếu cơ bản với iPhone 15 Pro Max 8 GB/256 GB tại FPT dự đoán **22.642.018 đồng** bằng LightGBM (và **25.862.396 đồng** bằng Random Forest với ca kiểm thử chuẩn hóa nhãn `apple` / `fpt shop`).
4. **Tab 4 — Kiểm toán bất thường (TV7)**: Đối chiếu 3 phương pháp phát hiện (Rule-based, Log-price IQR, Isolation Forest), phân rã `715` bản ghi gắn cờ thành 4 nhóm `anomaly_type` với khuyến nghị xử lý riêng biệt, kèm bộ lọc tra cứu từng dòng và minh chứng vì sao xóa mù quáng mọi cờ bất thường sẽ làm suy giảm nghiêm trọng khả năng định giá phân khúc cao cấp.
5. **Tab 5 — Đánh giá mô hình & XAI (TV8)**: Hợp nhất 3 chế độ chuyên sâu gồm *Benchmark 3 chiều & Ablation S1–S5*, *Phân tích sai số đa lát cắt & Top-20 ca lệch lớn nhất*, và *Giải thích mô hình toàn cục TreeSHAP & Kiểm định tính đơn điệu (Monotonicity Check)*.

| Minh họa hiện vật đánh giá cốt lõi | Nội dung | Ảnh chụp tham chiếu |
|---|---|---|
| Giao diện thẩm định & dự đoán giá | Đối chiếu cấu hình, mức giá hợp lý, đóng góp SHAP VNĐ và các máy tương tự | [Ảnh 10.A](../../src/evaluation_demo/outputs/demo_screenshots/01_du_doan_gia.jpg) |
| So sánh mô hình & Ablation | Chỉ số 3 chiều TV5, chuỗi thí nghiệm S1–S4 và độ nhạy cờ TV7 (S5a/S5b) | [Ảnh 10.B](../../src/evaluation_demo/outputs/demo_screenshots/02_so_sanh_mo_hinh.jpg) |
| Phân tích sai số đa chiều | Đồ thị phần dư, sai số theo khoảng giá/hãng/tồn kho và 20 ca lệch lớn nhất | [Ảnh 10.C](../../src/evaluation_demo/outputs/demo_screenshots/03_phan_tich_sai_so.jpg) |
| Giải thích mô hình & Đơn điệu | Biểu đồ TreeSHAP toàn cục, 3 ví dụ waterfall và phép thử bậc thang RAM/ROM | [Ảnh 10.D](../../src/evaluation_demo/outputs/demo_screenshots/04_giai_thich_mo_hinh.jpg) |

![Giao diện dự đoán và giải thích đóng góp giá với iPhone 15 Pro Max](../../src/evaluation_demo/outputs/demo_screenshots/01_du_doan_gia.jpg)

[Hướng dẫn chạy và tái tạo hiện vật](../../src/evaluation_demo/README.md) · [Mã ứng dụng 5 tab](../../src/evaluation_demo/app.py) · [Thư viện](../../requirements.txt) · [Bộ kiểm thử TV8](../../tests/test_tv8_evaluation_demo.py)

```powershell
python -m pytest tests/test_tv8_evaluation_demo.py -q
python -m streamlit run src/evaluation_demo/app.py --server.address 127.0.0.1
```

Bộ kiểm thử tự động kiểm tra tính toàn vẹn của phép chia dữ liệu không rò rỉ, tái lập chính xác 6 mô hình TV5, chuẩn hóa bí danh Apple/FPT, bảo toàn tổng cộng tính SHAP VNĐ, làm giàu danh mục với TV6/TV7, khóa tương thích phần cứng vật lý, chế độ thẩm định giá hợp lý SKU thực tế, 7 bảng CSV, 7 hình 300 DPI, 4 ảnh chụp tham chiếu và khả năng vận hành trọn vẹn 5 tab trên Streamlit `AppTest`.
