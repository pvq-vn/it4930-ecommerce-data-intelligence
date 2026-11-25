# ĐẠI HỌC BÁCH KHOA HÀ NỘI
## BÁO CÁO BÀI TẬP LỚN
### MÔN: NHẬP MÔN KHOA HỌC DỮ LIỆU (IT4930)

---

**Đề tài:**  
# XÂY DỰNG HỆ THỐNG TRÍ TUỆ DỮ LIỆU THỊ TRƯỜNG VÀ THẨM ĐỊNH GIÁ HỢP LÝ SẢN PHẨM CÔNG NGHỆ ĐA SÀN THƯƠNG MẠI ĐIỆN TỬ

**Nhóm thực hiện: Nhóm 12**
1. Phạm Văn Quyết — `202416331` *(TV1: Thu thập dữ liệu đa nguồn bất biến)*
2. Hà Đức Anh — `20235001` *(TV2: Quản trị chất lượng, tích hợp & chuẩn hóa dữ liệu đa tầng)*
3. Hoàng Phúc Hưng — `202416216` *(TV3: Phân tích khám phá dữ liệu EDA & kiểm định thống kê)*
4. Nguyễn Chính Minh — `202416293` *(TV4: Phân tích đồ thị cạnh tranh đa sàn, phân khúc Louvain & khoảng trống thị trường)*
5. Đào Duy Anh — `20235000` *(TV5: Mô hình định giá hưởng lạc Hedonic Fair-Value tích hợp đa nguồn)*
6. Nguyễn Trịnh Minh Hiếu — `20235078` *(TV6: Xử lý ngôn ngữ tự nhiên tiếng Việt, PhoBERT Sentiment, LDA & ABSA)*
7. Nguyễn Tùng Dương — `20230024` *(TV7: Kiểm toán bất thường danh mục & giá bán đa phương pháp)*
8. Lê Trần Anh — `202416112` *(TV8: Thẩm định 3 chiều, giải thích nhân tố giá XAI & Hệ thống hỗ trợ quyết định 5 Tab)*

**Giảng viên hướng dẫn:** Nguyễn Văn Sơn  
**Hà Nội, 2026**

---

## 1. PHÂN TÍCH NGHIỆP VỤ VÀ ĐỊNH HÌNH BÀI TOÁN KHOA HỌC DỮ LIỆU

### 1.1. Bối cảnh thực tế và Động lực triển khai

Thị trường bán lẻ thiết bị công nghệ thông tin (đặc biệt là **Laptop** và **Điện thoại thông minh**) tại Việt Nam có tốc độ tăng trưởng cao nhưng tồn tại sự **bất cân xứng thông tin nghiêm trọng** giữa nhà bán lẻ và người tiêu dùng, cũng như sự phân mảnh dữ liệu lớn giữa các chuỗi phân phối hàng đầu (**CellphoneS, Thế Giới Di Động, FPT Shop, Hoàng Hà Mobile, Viettel Store**):

1. **Ma trận biến thể cấu hình và chiến thuật neo giá khuyến mãi**: Cùng một dòng máy thương mại nhưng mỗi sàn lại tách nhỏ thành hàng chục mã SKU theo dung lượng RAM, bộ nhớ lưu trữ, đời vi xử lý hoặc màu sắc. Qua khảo sát thực tế `10.316` dòng niêm yết của dự án, có tới **`75,0%` (`7.737` bản ghi)** gắn nhãn giảm giá so với "giá gốc gạch ngang" với biên độ chiết khấu khác biệt lớn giữa các sàn (trung bình từ `7,95%` tại FPT Shop đến `20,81%` tại Hoàng Hà Mobile). Người mua phổ thông rất khó phân biệt đâu là mức giảm giá thực chất và đâu chỉ là chiến thuật neo giá gốc cao rồi hạ xuống.
2. **Nhiễu thông tin đánh giá sau mua (*Rating Inflation*)**: Hệ thống đánh giá sao trên các website thương mại điện tử bị lệch cực đoan — tới **`84,79%` trong tổng số `14.869` đánh giá có nội dung là 5 sao** (trung bình `4,56/5,0`), đồng thời tồn tại các đánh giá mâu thuẫn giữa điểm sao và văn bản nhận xét hoặc chấm điểm dịch vụ giao nhận thay vì chất lượng thiết bị.
3. **Bẫy chất lượng dữ liệu danh mục thực tế**: Kho dữ liệu niêm yết trực tuyến pha trộn cả sản phẩm đang mở bán với hàng ngừng kinh doanh lưu giữ giá cũ (*lifecycle price drift*), thông số kỹ thuật khuyết thiếu có hệ thống theo từng sàn, và phụ kiện/máy tính để bàn gán nhầm vào danh mục thiết bị di động.
4. **Bài toán mù thông tin cạnh tranh của nhà quản trị ngành hàng (B2B)**: Do không có mã định danh sản phẩm thống nhất (GTIN/EAN) công khai giữa các sàn tại Việt Nam, bộ phận quản trị danh mục (*Category Management*) khó xác định chính xác sàn mình đang bỏ trống phân khúc cấu hình nào (*blind spots*) hoặc những mẫu máy nào đang niêm yết cao/thấp bất thường so với mặt bằng cấu hình toàn thị trường.

Xuất phát từ các vấn đề nghiệp vụ đó, Nhóm 12 triển khai dự án theo đúng tinh thần của học phần **IT4930 — Nhập môn Khoa học Dữ liệu**: đi xuyên suốt từ thu thập dữ liệu thô ngoài thực tế, quản trị chất lượng dữ liệu đa tầng, khám phá tri thức thống kê, phân tích mạng lưới cạnh tranh, khai phá ngôn ngữ tự nhiên tiếng Việt, kiểm toán dị biệt danh mục cho tới thẩm định giá trị hợp lý và xây dựng hệ thống hỗ trợ ra quyết định trực quan.

### 1.2. Phát biểu Hệ bài toán theo Chu trình Khoa học Dữ liệu

Khác với cách tiếp cận hẹp của một bài toán Học máy thuần túy (chỉ tối ưu sai số dự đoán trên một tập dữ liệu cho sẵn), dự án định hình **4 trụ cột phân tích liên hoàn** trong chu trình Khoa học Dữ liệu (*Business Understanding → Data Acquisition & Governance → Exploratory/Graph/Text/Anomaly Discovery → Fair-Value Valuation & Decision Support*):

1. **Trụ cột 1 — Phân tích Mô tả & Chẩn đoán Quy luật Thị trường (*Descriptive & Diagnostic Analytics — TV1, TV2, TV3*)**:
   - Xây dựng kho dữ liệu chuẩn hóa theo mô hình hình sao (*Star Schema*) bảo toàn vết dữ liệu gốc từ 5 nhà bán lẻ.
   - Lượng hóa phân phối giá, chiến lược chiết khấu, cơ chế khuyết dữ liệu (`MCAR/MAR/MNAR`), kiểm định thống kê các yếu tố phần cứng thực sự dẫn dắt giá bán so với các thông số tiếp thị gây ngộ nhận, và đo lường hiện tượng trôi giá theo trạng thái tồn kho.
2. **Trụ cột 2 — Khai phá Cấu trúc Mạng lưới Cạnh tranh & Khoảng trống Danh mục (*Market Graph Analytics — TV4*)**:
   - Giải quyết bài toán đồng nhất thực thể sản phẩm liên sàn (*Cross-Retailer Entity Resolution*), dựng đồ thị hai phía *Nhà bán lẻ – Sản phẩm chuẩn* và đồ thị tương đồng hiệu năng phần cứng.
   - Định lượng mức độ độc quyền danh mục, ma trận trùng lặp Jaccard, tỷ lệ dẫn đầu giá rẻ (*Price-Leader Win Rate*), phân khúc thị trường tự nhiên bằng thuật toán cộng đồng Louvain và phát hiện các khoảng trống thị trường (*Structural Holes*).
3. **Trụ cột 3 — Khai phá Tiếng nói Khách hàng & Kiểm toán Chất lượng Danh mục (*Voice-of-Customer NLP & Catalog Anomaly Audit — TV6, TV7*)**:
   - Xử lý văn bản tiếng Việt đặc thù thương mại điện tử (teencode, từ viết tắt phần cứng), bóc tách sắc thái cảm xúc thực tế bằng mô hình ngôn ngữ tiền huấn luyện (`PhoBERT`), khai phá chủ đề tiềm ẩn (`LDA`) và cảm xúc theo khía cạnh kỹ thuật (`ABSA`).
   - Kết hợp quy tắc nghiệp vụ, thống kê khoảng tứ phân vị trên thang log (`Log-IQR`) và mô hình cô lập đa biến (`Isolation Forest`) để phân loại rõ **lỗi dữ liệu/sai danh mục** với **siêu phẩm cấu hình cao hợp lệ**, tránh việc làm sạch dữ liệu mù quáng gây méo mó phân phối thị trường.
4. **Trụ cột 4 — Thẩm định Giá trị Hợp lý theo Cấu hình & Giải thích Nhân tố Giá (*Hedonic Fair-Value Valuation & Explainable Decision Support — TV5, TV8*)**:
   - Dựa trên **Lý thuyết Định giá Hưởng lạc (Hedonic Pricing Theory — Rosen, 1974)**, giá trị nội tại hợp lý $\hat{P}(x)$ của một thiết bị công nghệ được ước lượng từ tổ hợp độ thỏa dụng của các thuộc tính cấu thành (năng lực xử lý CPU/GPU, bộ nhớ RAM/ROM, công nghệ hiển thị, độ phủ thị trường và uy tín cảm xúc thương hiệu).
   - Thay vì yêu cầu người tiêu dùng tự nhập thông số cho những sản phẩm vốn đã có giá niêm yết công khai, hệ thống sử dụng $\hat{P}(x)$ làm **thước đo chuẩn đối chiếu (*Fair-Value Benchmark*)** để tính độ lệch định giá trên từng SKU thực tế đang bán:
     $$\Delta P_i = P_{\text{niêm yết}, i} - \hat{P}_{\text{hợp lý}}(x_i)$$
     kèm theo phân rã đóng góp bằng tiền VNĐ của từng nhóm thuộc tính thông qua giá trị **SHAP**, giúp người mua và nhà quản trị hiểu rõ **vì sao** một sản phẩm đang rẻ hời hay đắt hơn mặt bằng cấu hình.

### 1.3. Đối tượng thụ hưởng, Đầu vào – Đầu ra và Kịch bản ra quyết định

Hệ thống đầu cuối (`src/evaluation_demo/app.py`) được thiết kế thành **5 tab nghiệp vụ** phục vụ trực tiếp hai nhóm đối tượng:

- **Kịch bản 1 — Người tiêu dùng cá nhân & Đơn vị thu mua thiết bị cũ (B2C)**:
  - *Đầu vào*: Người dùng chọn trực tiếp một sản phẩm Laptop hoặc Smartphone đang niêm yết thực tế tại bất kỳ sàn nào trong 5 sàn (hoặc lọc theo tầm giá, hãng, nhà bán lẻ) mà không cần gõ tay thông số kỹ thuật.
  - *Đầu ra hỗ trợ quyết định*: Đối chiếu song song **Giá niêm yết thực tế** với **Giá hợp lý theo cấu hình**, kết luận mức hời/đắt theo dải sai số điển hình `±MdAPE`, biểu đồ thanh phân rã từng triệu đồng tăng/giảm theo linh kiện (SHAP VNĐ), cảnh báo nếu bản ghi có dấu hiệu sai thông số/hết hàng lưu giá cũ (TV7), hồ sơ khen/chê thực tế của người mua trước về pin, màn hình, tản nhiệt (TV6) và danh sách 5 SKU cấu hình tương đương trên các sàn đối thủ để so giá tức thì.
- **Kịch bản 2 — Quản trị ngành hàng & Bộ phận định giá bán lẻ (B2B Category Manager)**:
  - *Đầu vào*: Bộ lọc ngành hàng, nhà bán lẻ mục tiêu hoặc cấu hình SKU dự kiến nhập kho mới.
  - *Đầu ra hỗ trợ quyết định*:
    1. Bảng chẩn đoán vị thế giá của sàn so với 4 đối thủ (tỷ lệ thắng giá đáy, mức chênh giá trung bình).
    2. Danh mục **90 khoảng trống thị trường** chỉ rõ từng phân khúc đang bỏ ngỏ kèm khuyến nghị dải điểm chuẩn CPU/GPU cần nhập hàng (`perf_recommendation`).
    3. Danh sách bản ghi nghi vấn lỗi nhập liệu thông số hoặc sai danh mục trên website để đội vận hành chỉnh sửa.
    4. Công cụ mô phỏng định giá cho SKU sắp mở bán với **cơ chế khóa tương thích phần cứng vật lý** (chỉ cho phép tổ hợp Hãng – Dòng máy – CPU – GPU – RAM – ROM tồn tại thực tế).

### 1.4. Phạm vi, Đạo đức dữ liệu và Sự phối hợp 8 Thành viên

- **Phạm vi dữ liệu**: Hai ngành hàng công nghệ có cấu trúc thông số kỹ thuật chuẩn hóa cao nhất là **Laptop** (`4.874` dòng niêm yết) và **Smartphone** (`5.442` dòng niêm yết), thu thập từ **5 hệ thống bán lẻ chính hãng** tại Việt Nam: *CellphoneS, Thế Giới Di Động (TGDĐ), FPT Shop, Hoàng Hà Mobile và Viettel Store* (tổng cộng `10.316` bản ghi sản phẩm và `15.805` bản ghi đánh giá).
- **Nguyên tắc đạo đức & kỹ thuật thu thập**: Tuân thủ quy tắc `robots.txt`, giới hạn tuần tự `CONCURRENT_REQUESTS = 1` kết hợp `AutoThrottle`, tuyệt đối không thu thập thông tin định danh nhạy cảm của cá nhân và bảo toàn nguyên vẹn dữ liệu thô bất biến (`immutable raw snapshots`).
- **Luồng phối hợp xuyên suốt 8 thành viên**: Các phân hệ không làm việc rời rạc mà liên kết chặt chẽ qua các **Hợp đồng dữ liệu (*Data & Feature Contracts*)**: TV1 thu thập raw → TV2 chuẩn hóa thành kho dữ liệu hình sao Gold v2 & bảng ánh xạ khóa `listing_id_crosswalk.csv` → TV3 khám phá quy luật thống kê và định hướng xử lý dữ liệu cho TV4, TV5, TV7 → TV4 chuẩn hóa thực thể liên sàn & cung cấp điểm chuẩn phần cứng không rò rỉ giá → TV6 khai phá đánh giá khách hàng & cung cấp đặc trưng cảm xúc cấp sản phẩm cha → TV7 kiểm toán bất thường & phân loại hành động xử lý mẫu → TV5 tích hợp đặc trưng đa nguồn xây dựng mô hình định giá hợp lý → TV8 kiểm định độc lập 3 chiều, giải thích nhân tố giá và hợp nhất toàn bộ kết quả TV1–TV8 lên nền tảng 5 tab.

---

## 2. KHẢO SÁT CÔNG TRÌNH KHOA HỌC, BỘ DỮ LIỆU VÀ GIẢI PHÁP THEO QUY TRÌNH DATA SCIENCE

### 2.1. Cơ sở lý thuyết và Các công trình khoa học liên quan

1. **Lý thuyết Định giá Hưởng lạc (*Hedonic Price Theory* — Rosen, 1974)**: Đặt nền móng kinh tế lượng cho việc phân rã giá bán của hàng hóa dị biệt (*differentiated goods* như máy tính, điện thoại, bất động sản) thành hàm giá ẩn của tập thuộc tính cấu thành. Đây là cơ sở học thuật để dự án sử dụng mô hình hồi quy phi tuyến như một **công cụ thẩm định giá trị cấu hình hợp lý** thay vì dự báo chuỗi thời gian.
2. **Quản trị Chất lượng Dữ liệu Đa chiều (*Data Quality Dimensions* — Wang & Strong, 1996; Giáo trình IT4930)**: Đánh giá dữ liệu trên 6 chiều cốt lõi gồm *Tính đầy đủ (Completeness), Tính chính xác (Accuracy), Tính nhất quán (Consistency), Tính hợp lệ (Validity), Tính duy nhất (Uniqueness)* và *Tính kịp thời/truy nguyên (Timeliness & Lineage)* — trực tiếp định hình kiến trúc 5 tầng *flag-don't-drop* của TV2 và bộ quy tắc kiểm toán của TV7.
3. **Phân tích Mạng lưới Hai phía & Phát hiện Cộng đồng (*Bipartite Networks & Louvain Modularity* — Blondel et al., 2008; Burt, 1992)**: Biểu diễn mối quan hệ *Nhà bán lẻ – Sản phẩm* và *Sản phẩm – Sản phẩm tương đồng* dưới dạng đồ thị cho phép phát hiện các phân khúc cạnh tranh tự nhiên bằng tối ưu hóa Modularity (Louvain) và nhận diện các *Lỗ hổng cấu trúc (Structural Holes)* nơi nhu cầu thị trường chưa được đáp ứng đầy đủ.
4. **Mô hình Ngôn ngữ Tiếng Việt Tiền huấn luyện (*PhoBERT* — Nguyen & Nguyen, 2020) & Khai phá Chủ đề (Blei et al., 2003)**: Kết hợp mô hình Transformer đơn ngữ tiếng Việt `vinai/phobert-base-v2` với mô hình chủ đề ẩn `Latent Dirichlet Allocation (LDA)` và phân tích cảm xúc theo khía cạnh (`ABSA`) giúp vượt qua hạn chế của từ điển cảm xúc tĩnh trước ngôn ngữ bình luận đa nghĩa, viết tắt trên sàn thương mại điện tử Việt Nam.
5. **Phát hiện Ngoại lai Cô lập (*Isolation Forest* — Liu et al., 2008) & Giải thích Cộng tính (*SHAP* — Lundberg & Lee, 2017)**: Isolation Forest tách biệt các tổ hợp cấu hình–giá hiếm mà không đòi hỏi giả định phân phối chuẩn đa biến; trong khi TreeSHAP phân bổ công bằng chênh lệch dự đoán về từng thuộc tính theo lý thuyết trò chơi hợp tác.

### 2.2. Khảo sát bộ dữ liệu công khai và Động lực tự xây dựng bộ dữ liệu Việt Nam

Qua đối chiếu các bộ dữ liệu quốc tế phổ biến như *Kaggle Laptop Price Dataset* (~1.300 mẫu) hay *Amazon Electronics Reviews*, nhóm nhận thấy hai rào cản khiến chúng không thể giải quyết bài toán nghiệp vụ tại Việt Nam:
1. **Lạc hậu thế hệ công nghệ**: Các bộ dữ liệu công khai chủ yếu chứa cấu hình giai đoạn 2018–2021 (Intel Gen 8–10, ổ HDD, RAM 4GB), thiếu vắng hoàn toàn các thế hệ chip mới đang chi phối thị trường hiện tại như *Apple Silicon M1–M4/M5, Intel Core Ultra, Snapdragon 8 Gen 3 / Elite, Apple A17/A18 Pro*.
2. **Lệch miền thị trường (*Market Domain Shift*)**: Cấu trúc thuế nhập khẩu, VAT, chính sách bảo hành chính hãng VN/A, thói quen chiết khấu giá gạch và ngôn ngữ đánh giá tiếng Việt của 5 chuỗi bán lẻ nội địa khác biệt hoàn toàn với thị trường Mỹ/Châu Âu. Do đó, việc tự thu thập và chuẩn hóa bộ dữ liệu đa sàn thực tế tại Việt Nam là yêu cầu bắt buộc để mang lại tri thức có giá trị ứng dụng thật.

### 2.3. Tổng quan lựa chọn giải pháp theo từng khâu trong Vòng đời Khoa học Dữ liệu

| Khâu trong quy trình KHDL | Phân hệ | Phương pháp & Giải pháp kỹ thuật lựa chọn | Lý do lựa chọn phù hợp với đặc thù dữ liệu thực tế |
|---|---|---|---|
| **1. Thu thập dữ liệu** | TV1 | Python `Scrapy` + khai thác linh hoạt GraphQL / REST API / JSON-LD / SSR HTML + lưu trữ `JSON Lines (.jsonl)` bất biến + `RunnerLock` | Thích ứng 5 kiến trúc web khác nhau mà vẫn đảm bảo một hợp đồng dữ liệu thô thống nhất, an toàn và không gây quá tải máy chủ nguồn. |
| **2. Quản trị & Tích hợp** | TV2 | Kiến trúc kho dữ liệu 5 tầng (`raw → staging → silver_v2 → gold_v2 → processed`), 11 cổng kiểm định chất lượng, thiết kế **Star Schema** | Tách biệt rõ dữ liệu gốc bất biến và dữ liệu phân tích; giữ nguyên giá trị thiếu kèm cờ kiểm toán (*flag-don't-drop*) thay vì xóa dòng làm lệch mẫu. |
| **3. Khám phá & Kiểm định** | TV3 | Thống kê trung vị/IQR, biến đổi $\log$, tương quan thứ hạng Spearman $\rho$, kiểm định phi tham số Kruskal-Wallis & Mann-Whitney U, hệ số VIF | Phân phối giá lệch phải rất mạnh (`Skewness` tới `+7,38`) làm các kiểm định tham số trung bình thông thường bị chệch. |
| **4. Đồ thị & Cạnh tranh** | TV4 | Chuẩn hóa thông số LLM có cache + ghép điểm chuẩn Notebookcheck + Băm thực thể 7 trường + Đồ thị `NetworkX` + Phân cụm `Louvain` + `PyVis` | Giải quyết triệt để việc thiếu mã SKU chung liên sàn, cho phép đo lường trùng lặp Jaccard và phát hiện khoảng trống nhập hàng theo hiệu năng thật. |
| **5. Khai phá Văn bản** | TV6 | Chuẩn hóa tiếng Việt 7 bước (79 quy tắc teencode + 26 cụm đa nghĩa ngữ cảnh) + `TF-IDF/LogReg` đối sánh `PhoBERT` + `LDA` 5 chủ đề + `ABSA` 5 khía cạnh | Khắc phục hiện tượng lạm phát 5 sao (`84,79%`) và xử lý an toàn bài toán `73,10%` sản phẩm chưa có bình luận (*Cold-Start*). |
| **6. Kiểm toán Dị biệt** | TV7 | Tổ hợp 3 tầng: Quy tắc miền vật lý/danh mục + `IQR` trên $\ln(\text{price})$ phân tầng theo hãng + `Isolation Forest` đa biến + Phân loại 4 `anomaly_type` | Ngăn chặn sai lầm xóa nhầm các siêu phẩm workstation/flagship hợp lệ nhưng vẫn bắt chính xác lỗi thông số và phụ kiện lạc danh mục. |
| **7. Định giá Hợp lý** | TV5 | Pipeline `HardwareFeatureEngineer` không rò rỉ + `TransformedTargetRegressor(log1p/expm1)` + `GroupShuffleSplit` & `GroupKFold(10)` trên `Ridge`, `RF`, `LightGBM` | Ước lượng khách quan giá trị cấu hình hợp lý trên thang VNĐ với 4 chốt chặn chống rò rỉ nhãn giá và biến thể cùng sản phẩm cha. |
| **8. Thẩm định & Ra quyết định** | TV8 | Đánh giá 3 chiều (Độ chính xác – Tốc độ/Dung lượng – Độ bền khuyết thông số), thực nghiệm Ablation `S1–S5`, `TreeSHAP` VNĐ & Ứng dụng `Streamlit` 5 Tab | Chuyển hóa toàn bộ kết quả TV1–TV7 thành công cụ tra cứu giá hợp lý SKU thực tế (B2C) và quản trị danh mục tương thích phần cứng (B2B). |

---

## 3. THU THẬP DỮ LIỆU ĐA NGUỒN BẤT BIẾN *(Phạm Văn Quyết — 202416331 — TV1)*

### 3.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Trong chu trình Khoa học Dữ liệu, mọi suy diễn thống kê hay mô hình định giá ở hạ nguồn đều vô nghĩa nếu dữ liệu đầu vào bị sai lệch ngữ nghĩa giá (nhầm giá trả góp/giá thu cũ đổi mới với giá bán thẳng) hoặc mất liên kết giữa sản phẩm cha và biến thể cấu hình. Nhiệm vụ của TV1 là thiết kế hệ thống thu thập dữ liệu thực địa từ **5 chuỗi bán lẻ công nghệ lớn nhất Việt Nam** cho hai ngành hàng **Laptop** và **Smartphone**, đảm bảo tính nguyên bản (*immutability*) và khả năng truy vết 100% về nguồn gốc.

### 3.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
1. **Kiến trúc Multi-Source Crawler có điều phối tập trung**: Xây dựng bằng Python và `Scrapy` xoay quanh bộ điều phối `crawler/run_crawler.py` (`SOURCE_REGISTRY`), kết hợp cơ chế khóa tiến trình nguyên tử `RunnerLock` (`O_EXCL` gắn PID) ngăn chặn tuyệt đối việc hai tiến trình ghi đè đồng thời vào tầng dữ liệu thô.
2. **Chiến lược bóc tách thích ứng đặc thù từng nguồn (*Source-Specific Extraction*)**:
   - **CellphoneS**: Truy vấn API `GraphQL` cho danh mục và đánh giá, duyệt đầy đủ cây quan hệ *sản phẩm cha – biến thể màu sắc/cấu hình con* trước khi lấy thông số chi tiết.
   - **Thế Giới Di Động (TGDĐ)**: Kết hợp API phân trang danh mục, bóc tách bảng thông số kỹ thuật trang chi tiết và gọi endpoint API đánh giá riêng.
   - **FPT Shop**: Tích hợp API tìm kiếm/danh mục với dữ liệu có cấu trúc `JSON-LD` trên trang chi tiết.
   - **Viettel Store**: Truy vấn các endpoint `AJAX` danh mục và phân tích DOM HTML cho thông số chi tiết cùng bình luận.
   - **Hoàng Hà Mobile**: Phân tích HTML `SSR` kết hợp `JSON-LD`, thiết kế bộ lọc ngữ nghĩa giá chuyên biệt để tách đúng giá bán niêm yết khỏi *giá hội viên (Member), giá trả góp 0%* hoặc *giá phụ kiện mua kèm*.
3. **Chuẩn hóa Hợp đồng Dữ liệu Thô (*Canonical Raw Data Contracts*)**: Mọi bản ghi từ cả 5 nguồn đều được đóng gói về định dạng `JSON Lines (.jsonl)` kèm toàn bộ `raw_payload` gốc, tuân thủ nghiêm ngặt **Product Raw Contract (25 trường)** và **Review Raw Contract (19 trường)** mà không ép kiểu hay sửa đổi giá trị gốc.

### 3.3. Kết quả định lượng & Phát hiện rút ra trong quy trình Khoa học Dữ liệu

Hệ thống đạt **100% PASS** kiểm định hợp đồng schema (`25/25` trường sản phẩm và `19/19` trường đánh giá) với quy mô thu thập thực tế:

| Nguồn bán lẻ | Laptop (Listings) | Smartphone (Listings) | Tổng Listings | Tỷ trọng Listings | Laptop (Reviews) | Smartphone (Reviews) | Tổng Reviews |
|---|---:|---:|---:|---:|---:|---:|---:|
| **CellphoneS** | 3.912 | 3.935 | **7.847** | 76,07% | 1.898 | 9.296 | **11.194** |
| **Thế Giới Di Động** | 490 | 707 | **1.197** | 11,60% | 99 | 2.329 | **2.428** |
| **FPT Shop** | 356 | 464 | **820** | 7,95% | 602 | 1.092 | **1.694** |
| **Hoàng Hà Mobile** | 93 | 192 | **285** | 2,76% | 0 | 0 | **0** |
| **Viettel Store** | 23 | 144 | **167** | 1,62% | 63 | 426 | **489** |
| **Toàn thị trường** | **4.874** | **5.442** | **10.316** | **100,00%** | **2.662** | **13.143** | **15.805** |

**Những phát hiện quan trọng rút ra ngay từ khâu thu thập**:
- **Bản chất sự chênh lệch số lượng bản ghi giữa các sàn**: CellphoneS chiếm `76,07%` tổng số dòng niêm yết không phải vì quy mô cửa hàng lớn gấp 7 lần TGDĐ, mà do **kiến trúc quản lý danh mục trên web**: CellphoneS tạo URL riêng cho từng tổ hợp màu sắc – bộ nhớ và giữ nguyên các trang sản phẩm đã hết hàng/ngừng kinh doanh để duy trì lưu lượng tìm kiếm SEO; trong khi TGDĐ và FPT Shop gộp biến thể và ẩn nhanh các mẫu cuối vòng đời. Phát hiện này là chìa khóa giúp TV3, TV4 và TV5 không diễn giải sai thị phần thực tế.
- **Sự bất đối xứng của dữ liệu đánh giá**: Smartphone thu hút lượng bình luận gấp gần **5 lần** Laptop (`13.143` so với `2.662` reviews), trong khi Hoàng Hà Mobile không mở công khai API bình luận văn bản chuẩn như các sàn còn lại (`0` review) và Viettel Store có nhiều bản ghi chỉ lưu số sao mà trống nội dung chữ (`489` bản ghi). Điều này báo trước bài toán *khuyết thiếu văn bản và Cold-Start* mà TV6 phải giải quyết.

---

## 4. QUẢN TRỊ CHẤT LƯỢNG, TÍCH HỢP VÀ CHUẨN HÓA DỮ LIỆU ĐA TẦNG *(Hà Đức Anh — 20235001 — TV2)*

### 4.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Dữ liệu thô từ 5 nhà bán lẻ có định dạng hoàn toàn không đồng nhất: giá bán lúc là số nguyên, lúc là chuỗi `"24.990.000 ₫"`, lúc bằng `0` ("Liên hệ"); thông số kỹ thuật nằm rải rác trong từ điển khóa–giá trị tiếng Việt tự do (`"Dung lượng RAM"`, `"Bộ nhớ đệm"`, `"Công nghệ màn hình"`); điểm đánh giá sản phẩm dùng `0` làm giá trị báo thiếu (*sentinel value*). Nhiệm vụ của TV2 là xây dựng **hệ thống quản trị chất lượng và tích hợp dữ liệu chuẩn kho dữ liệu (*Data Warehousing*)**, biến dữ liệu thô thành nguồn dữ liệu sạch, nhất quán, có kiểm toán chất lượng cho toàn bộ TV3–TV8.

### 4.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
1. **Kiến trúc Pipeline 5 tầng tuần tự (`11 stages` tự động hóa qua `src/preprocessing/run_tv2_pipeline.py`)**:
   $$\texttt{data/raw/} \longrightarrow \texttt{staging/} \longrightarrow \texttt{silver\_v2/} \longrightarrow \texttt{gold\_v2/} \longrightarrow \texttt{processed/}$$
   Áp dụng xuyên suốt triết lý quản trị dữ liệu hiện đại **"Không xóa dòng — Chỉ gắn cờ kiểm toán" (*Flag-Don't-Drop*)**: mọi bản ghi thiếu giá hoặc khuyết thông số đều được giữ lại ở kho trung tâm kèm các cờ trạng thái (`is_price_missing`, `price_parse_status`, `has_rating`, `review_usable`) để các nhóm phân tích hạ nguồn chủ động lọc theo đúng mục đích nghiên cứu mà không làm mất dấu vết mẫu gốc.
2. **Chuẩn hóa ngữ nghĩa tại tầng Silver (`silver_v2`)**:
   - Chuẩn hóa tiền tệ về số thực VNĐ (`price_vnd`, `original_price_vnd`), tách bạch trường hợp `rating_raw = 0` thành `rating_norm = null` và `has_rating = False` để không kéo tụt giả tạo điểm sao trung bình của sản phẩm mới.
   - Bóc tách có kiểm soát **14 thuộc tính phần cứng chuẩn hóa** từ `attributes_raw` và tên biến thể bằng hệ thống biểu thức chính quy (`Regex`) kết hợp từ điển ánh xạ chuẩn (`installed_ram_gb`, `max_ram_gb`, `storage_gb`, `battery_mah`, `battery_wh`, `charger_watt`, `cpu_norm`, `gpu_norm`, `screen_size_inch`, `display_type_norm`, `operating_system_norm`, `camera_mp`, `color_norm`, `network_type_norm`), đồng thời chuẩn hóa `brand_norm` và trạng thái kho `availability_status`.
3. **Thiết kế Kho dữ liệu Hình sao (*Star Schema*) tại tầng Gold (`gold_v2`) & Đồng bộ khóa liên phiên bản**:
   - Tổ chức dữ liệu thành **5 bảng quan hệ chuẩn mực**: `fact_listings` (`10.316 × 81`), `fact_listings_features` (`10.316 × 31`), `fact_reviews` (`15.805 × 40`), `dim_source_parents` (`7.051 × 11` sản phẩm cha theo nguồn) và `fact_review_replies` (`108 × 23`).
   - Xây dựng khóa tích hợp `source_parent_id` để nối chính xác bảng đánh giá với bảng sản phẩm cha (tránh lỗi nhân bản tích Đề-các lên tới 45.651 dòng nếu nối nhầm ở cấp biến thể màu sắc), đồng thời thiết lập bảng đối chiếu `data/processed/listing_id_crosswalk.csv` (`10.316` dòng) đảm bảo đồng bộ tuyệt đối mã `listing_record_id` giữa mọi nhánh làm việc của dự án.

### 4.3. Kết quả kiểm toán chất lượng & Bài học Khoa học Dữ liệu rút ra
- **11/11 cổng kiểm soát chất lượng (*Quality Gates*) đạt PASS**: `0` bản ghi trùng khóa `listing_record_id`, `0` bản ghi trùng `review_record_id`, `0` mâu thuẫn logic giữa `rating_norm` và `has_rating`, `100%` liên kết khóa ngoại `source_parent_id` hợp lệ.
- **Tri thức rút ra về Quản trị Dữ liệu**:
  1. *Không điền khuyết mù quáng ở tầng dữ liệu nền*: Việc TV2 kiên quyết giữ `null` thay vì tự điền trung bình cho các trường không bóc tách được đã giúp TV3 phát hiện ra quy luật khuyết thiếu có cấu trúc giữa Laptop và Smartphone, đồng thời ngăn ngừa hiện tượng rò rỉ thống kê giữa tập huấn luyện và tập kiểm thử ở TV5.
  2. *Phân biệt hạt độ dữ liệu (Data Granularity)*: Tách biệt rõ hạt độ **Biến thể niêm yết (`10.316` listings)** và hạt độ **Sản phẩm cha trên từng sàn (`7.051` source parents)** là điều kiện tiên quyết để tích hợp dữ liệu đánh giá khách hàng (TV6) và chia tập kiểm định không rò rỉ (TV5, TV8).

---

## 5. PHÂN TÍCH KHÁM PHÁ DỮ LIỆU (EDA) VÀ KIỂM ĐỊNH QUY LUẬT GIÁ THỊ TRƯỜNG *(Hoàng Phúc Hưng — 202416216 — TV3)*

### 5.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Trước khi áp dụng bất kỳ thuật toán đồ thị, phát hiện bất thường hay mô hình định giá nào, nhà khoa học dữ liệu phải trả lời bằng bằng chứng thống kê: **Mặt bằng giá thực tế phân bố ra sao? Các nhà bán lẻ chiết khấu thế nào? Thông số kỹ thuật nào thực sự quyết định giá bán, và thông số nào chỉ là chiêu trò tiếp thị? Dữ liệu ẩn chứa những cạm bẫy chất lượng nào?** Phân hệ TV3 thực hiện kiểm toán thống kê toàn diện trên `10.316` bản ghi × `32` thuộc tính, xuất bản **5 Jupyter Notebooks, hơn 36 bảng thống kê và 15 biểu đồ chuẩn 300 DPI**.

### 5.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
- Kết hợp thống kê mô tả bền vững với ngoại lai (**Trung vị, Khoảng tứ phân vị IQR, Skewness, Kurtosis**) và phép biến đổi $\log_{10}(\text{price})$ / $\ln(1 + \text{price})$.
- Áp dụng hệ thống **kiểm định giả thuyết phi tham số và tham số**: tương quan thứ hạng đơn điệu **Spearman ($\rho$)** cho biến định lượng lệch chuẩn, kiểm định **Kruskal-Wallis ($H$)** và **ANOVA ($F$)** trên thang log cho biến phân loại đa nhóm (hãng, phân khúc CPU, loại màn hình), kiểm định **Mann-Whitney U** cho sự dịch chuyển phân phối giá theo tồn kho, và **Hệ số phóng đại phương sai (VIF)** cho đa cộng tuyến.

### 5.3. Các phát hiện định lượng cốt lõi & Ý nghĩa nghiệp vụ rút ra

1. **Cấu trúc thị phần tập trung ở Laptop nhưng phân mảnh ở Smartphone**:
   - Ở Laptop, **7 thương hiệu đầu** (`ASUS 23,88%`, `Apple 19,72%`, `Lenovo 15,18%`, `HP 10,73%`, `Dell 10,16%`, `MSI 8,00%`, `Acer 7,28%`) chiếm tới **`95,66%`** toàn bộ danh mục niêm yết. Ngược lại ở Smartphone, Top 3 hãng (`Samsung 17,92%`, `Xiaomi 17,42%`, `Apple 13,27%`) chỉ chiếm **`48,61%`**, phần còn lại cạnh tranh gay gắt giữa OPPO, Vivo, Realme, Honor, Tecno.
2. **Phân phối giá lệch phải cực đoan & Bẫy "Trung bình cộng"**:
   - Trong `10.316` bản ghi có **`8.548` bản ghi có giá dương hợp lệ** (`4.222` Laptop, `4.326` Smartphone) và **`1.768` bản ghi thiếu hoặc giá $\le 0$** (`1.752` không dương + `16` trống).
   - Trên thang VNĐ gốc, Laptop có trung vị **`26,84 triệu`** nhưng trung bình bị kéo lên **`32,99 triệu`** (`Skewness = +2,89`, `Kurtosis = +13,54`, đỉnh `269,99 triệu`); Smartphone có trung vị **`7,99 triệu`** nhưng trung bình vọt lên **`13,99 triệu`** (`Skewness = +7,38`, `Kurtosis = +170,71`). Sau phép biến đổi $\log_{10}$, độ lệch giảm mạnh về **`+0,29`** (Laptop) và **`-0,58`** (Smartphone). *Hệ quả*: mọi báo cáo giá thị trường phải dùng Trung vị, và mọi mô hình IQR/Hồi quy ở TV7, TV5 bắt buộc làm việc trên không gian Logarithm.
3. **Chiến lược chiết khấu giá gạch khác biệt rõ giữa 5 nhà bán lẻ**:
   - Có tới **`75,0%`** sản phẩm niêm yết kèm tỷ lệ giảm giá (trung bình toàn thị trường `11,50%`, trung vị `8,34%`). Nhóm chuỗi bán lẻ thiên về cạnh tranh giá như **Hoàng Hà Mobile (`20,81%`)** và **Viettel Store (`14,53%`)** hiển thị biên độ chiết khấu sâu hơn hẳn nhóm chuỗi lớn **CellphoneS (`11,70%`), TGDĐ (`9,05%`) và FPT Shop (`7,95%`)**.
4. **Cơ chế khuyết dữ liệu mang tính cấu trúc ngành hàng (*Category-Specific MAR*)**:
   - `battery_wh` khuyết `99,94%` ở Smartphone nhưng hiện diện ở `40,95%` Laptop; ngược lại `battery_mah` có ở `75,93%` Smartphone nhưng khuyết `99,45%` Laptop; `gpu_norm` chỉ khuyết `4,80%` ở Laptop nhưng khuyết `69,96%` ở Smartphone. Đây là căn cứ định lượng buộc dự án **tách đôi hoàn toàn pipeline phân tích cho Laptop và Smartphone**.
5. **Đối lập cấu trúc định giá Laptop vs. Smartphone & "Ba Nghịch lý Phần cứng"**:
   - **Laptop được định giá như công cụ hiệu suất làm việc**: `installed_ram_gb` có tương quan đơn điệu mạnh nhất ($\rho = +0,744$; trung vị giá tăng **5,12 lần** từ `18,99M` ở 8GB lên `97,14M` ở $\ge 64\text{GB}$), đi cùng phân khúc CPU ($H = 2099,48$, Core i9/Ryzen 9 đạt trung vị `54,99M` gấp `4,60` lần Core i3 `11,95M`), dung lượng pin Wh ($\rho = +0,665$) và công suất sạc W ($\rho = +0,623$).
   - **Smartphone được định giá theo bậc thang bộ nhớ, công nghệ màn hình và định vị thương hiệu**: `storage_gb` dẫn đầu ($\rho = +0,703$; trung vị giá tăng **11,97 lần** từ `3,49M` ở $\le 64\text{GB}$ lên `41,79M` ở $\ge 1\text{TB}$); màn hình **OLED/AMOLED có trung vị `15,99M` — đắt gấp `4,21` lần màn IPS/LCD (`3,80M`, $F = 2902,99$)**; thương hiệu Apple có trung vị `25,49M` so với `15,84M` của Samsung ($H = 2335,59$).
   - **Ba Nghịch lý Phần cứng cảnh báo người tiêu dùng**: (i) *Pin Smartphone bão hòa quanh 5.000 mAh* ở mọi tầm giá ($\rho = +0,036$); (ii) *Số "chấm" Camera MP không phản ánh đẳng cấp flagship* ($\rho = +0,179$ do điện thoại giá rẻ chạy đua 50–108MP trong khi máy cao cấp tối ưu kích thước cảm biến và quang học); (iii) *Laptop màn hình nhỏ 13–14 inch (Ultrabook doanh nhân/MacBook) đắt ngang hoặc hơn laptop 15,6 inch phổ thông* ($\rho = +0,143$).
   - *Lưu ý phương pháp luận*: Các hệ số tương quan này phản ánh sự kết hợp cấu hình trên thị trường (*bundling association*), không đồng nhất với chi phí sản xuất nhân quả của từng linh kiện rời.
6. **Phát hiện hiện tượng "Trôi giá theo vòng đời tồn kho" (*Lifecycle Price Drift*) & Kiểm định VIF**:
   - Kiểm định Mann-Whitney U chứng minh các sản phẩm đang còn hàng (`in_stock`) có mức giá cao hơn nhóm hết hàng (`out_of_stock`) tới **`+9,50 triệu VNĐ` (`+39,6%`, $p = 3,98 \times 10^{-37}$)** ở Laptop và **`+3,30 triệu VNĐ` (`+50,9%`, $p = 1,02 \times 10^{-17}$)** ở Smartphone — do các mẫu hết hàng lưu lại mức giá xả kho cuối vòng đời của thế hệ phần cứng cũ.
   - Toàn bộ biến số đều có **VIF $\le 1,58$ ở Laptop** và **tối đa `2,98` ở Smartphone** (`< 5,0`), khẳng định không xảy ra đa cộng tuyến phá hủy mô hình.

---

## 6. PHÂN TÍCH ĐỒ THỊ CẠNH TRANH ĐA SÀN, PHÂN KHÚC LOUVAIN VÀ KHOẢNG TRỐNG THỊ TRƯỜNG *(Nguyễn Chính Minh — 202416293 — TV4)*

### 6.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Cùng một chiếc *iPhone 15 Pro Max 256GB* hay *ASUS Vivobook 15*, mỗi chuỗi bán lẻ đặt một tiêu đề thương mại khác nhau. Nếu không gom được chúng về cùng một thực thể chuẩn, doanh nghiệp không thể trả lời ba câu hỏi chiến lược: **(1) Mức độ trùng lặp danh mục và sức ép cạnh tranh giá trực diện giữa 5 sàn lớn đến đâu? (2) Thị trường tự hình thành những phân khúc vi mô nào theo hiệu năng thực tế? (3) Từng nhà bán lẻ đang bỏ lỡ những cơ hội nhập hàng nào (*Structural Holes*)?**

### 6.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
1. **Chuẩn hóa thông số thông minh & Ghép điểm chuẩn hiệu năng thực tế (`Step 1 & 1.5`)**:
   - Sử dụng mô hình ngôn ngữ lớn có cơ chế lưu đệm (`llm_spec_cache.jsonl`) và lược đồ kiểm tra kiểu nghiêm ngặt để chuẩn hóa tên hãng, dòng máy sạch (`model_clean`) và cấu hình cho các bản ghi có giá hợp lệ, đồng thời loại bỏ phụ kiện/máy tính bảng lạc danh mục.
   - Trích xuất các bảng điểm chuẩn phần cứng độc lập từ **Notebookcheck** (`cpu_benchmarks.csv`, `gpu_benchmarks.csv`, `cpu_phone_benchmarks.csv`), ghép phân tầng điểm `cpu_perf_rating`, `gpu_perf_rating` cho Laptop và `cpu_benchmark_score` (thang Geekbench 5 Multi-Core đồng nhất cho `325/549` dòng SoC di động) cho Smartphone.
2. **Đồng nhất thực thể (*Entity Resolution*) & Đồ thị Hai phía Bipartite (`Step 2`)**:
   - Ánh xạ các dòng niêm yết trên 5 sàn về **`4.414` sản phẩm chuẩn (`canonical_products.csv`)** dựa trên mã băm SHA-256 của 7 thuộc tính phần cứng cốt lõi (`brand`, `model_clean`, `cpu_model`, `ram_gb`, `storage_gb`, `gpu_model`, `screen_size_inch`).
   - Dựng đồ thị hai phía $G = (U, V, E)$ giữa $5$ Nhà bán lẻ và tập Sản phẩm chuẩn (áp ngưỡng sàn phân tích `Laptop >= 3M`, `Smartphone >= 1M` để khử nhiễu phụ kiện/điện thoại cơ bản), tính toán độ trùng lặp **Jaccard**, tỷ lệ độc quyền, **Tỷ lệ dẫn đầu giá đáy (*Price-Leader Win Rate*)** và **Mức độ đắt hơn trung bình có lọc nhiễu (*Guarded Price Premium*)**.
3. **Đồ thị Tương đồng Sản phẩm, Phân cụm Cộng đồng Louvain & Phát hiện Khoảng trống (`Step 3 & 4`)**:
   - Dựng đồ thị tương đồng $G_{pp}$ nối các sản phẩm xuyên thương hiệu có hiệu năng CPU/GPU chênh lệch $\le 15\%$ và mức giá trung vị chênh lệch $\le 20\%$ (cách ly chặt laptop GPU rời với GPU tích hợp), sau đó tối ưu hóa tham số phân giải để chia thị trường thành **`63` phân khúc tự nhiên Louvain (`louvain_segments.csv`)**.
   - Đối chiếu ma trận chéo *Nhà bán lẻ × Phân khúc Louvain* kết hợp tổng lượng đánh giá để phát hiện **Điểm mù danh mục (`retailer_blind_spot`)** và **Phân khúc cầu cao – ít sàn bán (`underserved_high_demand`)**, tự động sinh khuyến nghị cấu hình nhập hàng (`perf_recommendation`).
   - Xuất riêng gói đặc trưng hoàn toàn không chứa giá (`data/market_graph/handoff/tv5_tv8_price_free_features.csv`) gồm điểm chuẩn CPU/GPU và mật độ sàn bán cùng cấu hình `hw_seller_count` cho TV5/TV8.

### 6.3. Các phát hiện định lượng cốt lõi & Khuyến nghị chiến lược B2B

#### Bảng 6.1. Vị thế danh mục và năng lực cạnh tranh giá của 5 nhà bán lẻ (trên các sản phẩm chuẩn hợp lệ)

| Nhà bán lẻ | Laptop: Số SP chuẩn | Laptop: Tỷ lệ độc quyền | Laptop: Tỷ lệ rẻ nhất (*Win Rate*) | Laptop: Chênh giá TB so với đáy | Smartphone: Số SP chuẩn | Smartphone: Tỷ lệ độc quyền | Smartphone: Tỷ lệ rẻ nhất (*Win Rate*) | Smartphone: Chênh giá TB so với đáy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **CellphoneS** | 2.350 | 93,19% | 69,38% | +1,80% | 1.039 | 87,10% | 45,52% | +2,23% |
| **Thế Giới Di Động** | 397 | 66,75% | 51,52% | +2,85% | 260 | 68,08% | 39,76% | +2,76% |
| **FPT Shop** | 298 | 60,74% | 64,10% | +2,64% | 167 | 27,54% | 38,02% | +4,56% |
| **Hoàng Hà Mobile** | 87 | 66,67% | **75,86%** | **+0,55%** | 146 | 38,36% | **64,44%** | +2,25% |
| **Viettel Store** | 21 | 42,86% | 66,67% | +5,20% | 128 | 24,22% | 55,67% | +2,37% |

**Những phát hiện kinh doanh giá trị cao từ đồ thị thị trường**:
1. **Hai cấu trúc cạnh tranh trái ngược giữa Laptop và Smartphone**:
   - Trên mảng **Laptop**, ma trận tương đồng Jaccard giữa các sàn cực thấp (cặp trùng lặp cao nhất là **FPT – TGDĐ cũng chỉ đạt `9,62%`**; các cặp khác từ `0,21%` đến `4,05%`). Nguyên nhân là các hãng Laptop phân phối mã cấu hình phụ (khác mã đuôi CPU, tấm nền, dung lượng SSD) riêng cho từng đại lý (*exclusive SKU differentiation*) nhằm giảm so sánh giá trực diện.
   - Ngược lại trên mảng **Smartphone**, các mã máy chuẩn hóa cao nên cạnh tranh trực diện rất khốc liệt: độ trùng lặp Jaccard giữa **FPT – Viettel đạt `27,16%`**, **FPT – Hoàng Hà đạt `23,23%`**, **Hoàng Hà – Viettel đạt `21,78%`**, và **FPT – TGDĐ đạt `19,61%`**.
2. **Định vị chiến lược giá thực chất của từng chuỗi**:
   - **Hoàng Hà Mobile** là "nhà dẫn dắt giá rẻ" rõ nét nhất trên các mẫu máy đối đầu trực tiếp khi giành chiến thắng giá thấp nhất tới **`75,86%` ở Laptop** (chỉ đắt hơn đáy trung bình `+0,55%`) và **`64,44%` ở Smartphone**.
   - **CellphoneS** thống trị tuyệt đối về chiều rộng danh mục dài hạn (`2.350` mẫu Laptop chuẩn và `1.039` mẫu Smartphone chuẩn), đồng thời vẫn duy trì giá bán rất cạnh tranh (`69,38%` win rate Laptop, chênh đáy `+1,80%` đến `+2,23%`).
   - **TGDĐ và FPT Shop** chấp nhận mức chênh giá cao hơn đáy khoảng `+2,64%` đến `+4,56%` để đổi lấy lợi thế độ phủ cửa hàng vật lý toàn quốc và dịch vụ hậu mãi.
3. **Phát hiện `90` Khoảng trống Thị trường cụ thể để mở rộng danh mục**:
   - Hệ thống chỉ ra chính xác **`68` điểm mù danh mục (`retailer_blind_spot`)** nơi đối thủ có từ $\ge 5$ mẫu máy sôi động nhưng sàn đang có `0` mã (ví dụ: FPT Shop và TGDĐ đang bỏ trống phân khúc *Laptop 6–17M ASUS/HP* hiệu năng CPU quanh `27,2` và *Laptop 14–19M HP/Dell* CPU quanh `36,2`; Hoàng Hà và Viettel Store bỏ trống phân khúc *Laptop đồ họa/doanh nhân cao cấp 46–110M Apple/Lenovo*), cùng **`22` phân khúc cầu cao – cung mỏng (`underserved_high_demand`)** toàn thị trường có mật độ đánh giá người dùng vượt trung vị nhưng độ cạnh tranh trung bình $\le 1,25$ sàn.

---

## 7. XÂY DỰNG MÔ HÌNH ĐỊNH GIÁ HƯỞNG LẠC (HEDONIC FAIR-VALUE) TÍCH HỢP ĐA NGUỒN *(Đào Duy Anh — 20235000 — TV5)*

### 7.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Trong hệ thống Khoa học Dữ liệu của Nhóm 12, phân hệ TV5 đóng vai trò xây dựng **Thước đo Giá trị Hợp lý Khách quan (*Hedonic Fair-Value Benchmark*)**: tổng hợp toàn bộ tri thức cấu hình phần cứng (TV2, TV3), điểm chuẩn hiệu năng và mật độ phân phối phần cứng (TV4) cùng chỉ số uy tín cảm xúc khách hàng (TV6) để ước lượng mức giá thị trường hợp lý cho từng cấu hình thiết bị, phục vụ kiểm toán đắt/rẻ trên SKU thực tế và mô phỏng định giá nhập hàng.

### 7.2. Cách thức triển khai kỹ thuật & 4 Chốt chặn Chống rò rỉ dữ liệu (Làm thế nào?)
1. **Lọc vệ sinh bản ghi hợp lệ & Đồng bộ khóa liên thành viên**:
   - Sử dụng bảng đối chiếu `listing_id_crosswalk.csv` để kết nối chính xác `8.374/8.374` bản ghi đã làm sạch với kho dữ liệu `products_processed.jsonl`.
   - Áp dụng bộ lọc `_is_corrupted_record()` loại bỏ các bản ghi hỏng cấu trúc (như các máy tính để bàn `iMac`, `Mac Studio`, `Mac mini`, `Mac Pro` bị sàn gắn nhầm vào danh mục `laptop`, bản ghi mâu thuẫn tên hãng, điện thoại màn hình `< 3,5 inch` nhưng giá `> 3 triệu`) và áp ngưỡng sàn nghiệp vụ thống nhất (`Laptop >= 3.000.000 VNĐ`, `Smartphone >= 1.000.000 VNĐ`), thu được **`8.132` bản ghi sạch chất lượng cao** (`4.046` Laptop và `4.086` Smartphone).
2. **Thiết kế 4 chốt chặn chống rò rỉ dữ liệu (*Zero-Leakage Architecture*)**:
   - *Chốt chặn 1 — Chia tập theo cụm sản phẩm cha (`GroupShuffleSplit` theo `source_parent_id`)*: Đảm bảo mọi biến thể màu sắc/dung lượng con của cùng một sản phẩm cha tại một sàn nằm trọn vẹn trong tập Huấn luyện (`3.227` Laptop; `3.276` Smartphone) hoặc trọn vẹn trong tập Kiểm thử (`819` Laptop; `810` Smartphone).
   - *Chốt chặn 2 — Cấm tuyệt đối biến hậu kiểm chứa thông tin giá (`LEAKAGE_COLS`)*: Loại bỏ `original_price_vnd`, `discount_rate`, các nhãn phân khúc Louvain có dùng giá của TV4 và toàn bộ cờ bất thường của TV7 khỏi ma trận đặc trưng $X$.
   - *Chốt chặn 3 — Biến đổi đặc trưng đóng gói trong `HardwareFeatureEngineer`*: Đặt đầu tiên trong `sklearn.pipeline.Pipeline` (26 đặc trưng cho Laptop và 26 đặc trưng cho Smartphone). Mọi giá trị điền khuyết trung vị theo hãng (`by_brand_medians_`), chuẩn hóa danh mục chữ thường (`cat_dtype_`) và điểm cảm xúc thương hiệu tiên nghiệm (`brand_sentiment_prior`) chỉ được ước lượng trên tập Train của từng fold trong `GroupKFold(n_splits=10)`.
   - *Chốt chặn 4 — Ổn định phương sai mục tiêu*: Bọc toàn bộ pipeline trong `TransformedTargetRegressor(func=np.log1p, inverse_func=np.expm1)`, huấn luyện và đối sánh ba họ mô hình từ tuyến tính điều chuẩn (`Ridge Regression`) tới tổ hợp cây (`Random Forest` và `LightGBM`).

### 7.3. Kết quả định lượng & Tri thức rút ra về cấu trúc định giá thị trường

| Ngành hàng | Quy mô (Train / Test) | Mô hình | MAE (VNĐ) | RMSE (VNĐ) | $R^2$ | Ý nghĩa trong bài toán Thẩm định Giá Hợp lý |
|---|---|---|---:|---:|---:|---|
| **Laptop** | `3.227 / 819` | Ridge Regression | 4.279.435 | 7.035.497 | 0,8828 | Mốc tham chiếu tuyến tính trên thang log ổn định nhờ VIF thấp |
| **Laptop** | `3.227 / 819` | Random Forest | 3.828.453 | 6.992.113 | 0,8843 | Nắm bắt ngưỡng nhảy bậc RAM/CPU tốt hơn tuyến tính |
| **Laptop** | `3.227 / 819` | **LightGBM** | **3.488.936** | **6.079.915** | **0,9125** | **Mô hình chuẩn Fair-Value (giảm 18,5% MAE so với Ridge)** |
| **Smartphone** | `3.276 / 810` | Ridge Regression | 2.184.928 | 3.264.949 | 0,9518 | Nền tảng tuyến tính mạnh khi có chuẩn mạng, OLED và SoC score |
| **Smartphone** | `3.276 / 810` | Random Forest | 2.114.765 | 3.406.507 | 0,9476 | Cải thiện sai số tuyệt đối trung bình ở tầm giá phổ thông |
| **Smartphone** | `3.276 / 810` | **LightGBM** | **1.864.679** | **3.022.967** | **0,9587** | **Mô hình chuẩn Fair-Value (giải thích gần 95,9% phương sai giá)** |

**Những đúc kết cốt lõi rút ra từ quá trình xây dựng mô hình định giá**:
- Việc `LightGBM` giải thích được **`91,25%` phương sai giá Laptop** và **`95,87%` phương sai giá Smartphone** trên tập kiểm thử độc lập theo nhóm sản phẩm cha chứng minh rằng: bất chấp sự hỗn loạn của giá gạch khuyến mãi bề nổi, **mặt bằng giá thực bán trên thị trường công nghệ Việt Nam bám rất sát giá trị cấu thành của phần cứng, hiệu năng vi xử lý, trạng thái vòng đời tồn kho và định vị thương hiệu**.
- Khoảng sai số tuyệt đối vượt ra ngoài dải điển hình (`MdAPE = 7,92%` ở Laptop và `10,99%` ở Smartphone) chính là tín hiệu định lượng quý giá để phát hiện các SKU đang được khuyến mãi hời thực sự hoặc đang bị định giá cao bất thường tại từng chuỗi bán lẻ.

---

## 8. KHAI PHÁ TIẾNG NÓI KHÁCH HÀNG TIẾNG VIỆT BẰNG NLP, PHOBERT, LDA VÀ ABSA *(Nguyễn Trịnh Minh Hiếu — 20235078 — TV6)*

### 8.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Cấu hình phần cứng trên giấy không cho biết máy dùng thực tế có bị quá nhiệt, sụt pin nhanh hay giao hàng trễ hẹn hay không; trong khi điểm trung bình sao trên web lại bị méo mó bởi hiện tượng chấm 5 sao mặc định. Nhiệm vụ của TV6 là khai phá **`15.805` đánh giá khách hàng** để giải mã **tiếng nói thực chất của người tiêu dùng Việt Nam (*Voice of Customer*)**, chỉ ra điểm mạnh/điểm nghẽn hậu mãi theo từng khía cạnh sản phẩm và đóng gói bộ đặc trưng cảm xúc không rò rỉ cho hệ thống định giá và thẩm định SKU.

### 8.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
1. **Kiểm toán chất lượng văn bản & Bảo toàn dữ liệu (`Zero Data Loss`)**:
   - Tách bạch `15.805` bản ghi thành **`14.869` đánh giá hợp lệ có nội dung chữ (`94,08%`)** và cách ly kiểm toán **`936` bản ghi rỗng (`5,92%`** gồm `489` bản ghi Viettel Store khuyết văn bản và `447` bản ghi CellphoneS chỉ chứa khoảng trắng).
   - Nối khóa ở cấp `source_parent_id` (`7.051` sản phẩm cha), phát hiện tỷ lệ **Cold-Start `73,10%`** (`5.154` sản phẩm cha chưa có bình luận; `1.897` sản phẩm cha có bình luận tích cực).
2. **Pipeline tiền xử lý tiếng Việt chuyên biệt cho miền phần cứng công nghệ (7 bước)**:
   - Chuẩn hóa Unicode dựng sẵn NFC, xử lý biểu tượng cảm xúc, chuẩn hóa **79 quy tắc teencode** thương mại điện tử và giải quyết nhập nhằng ngữ cảnh cho **26 từ viết tắt đa nghĩa** (ví dụ phân biệt `"cam"` là *camera* hay *màu cam*, `"bh"` là *bảo hành* hay *bao giờ*, `"mh"` là *màn hình*), tách từ bằng `underthesea` và lọc hư từ an toàn bảo toàn từ phủ định (`không`, `chẳng`, `chưa`, `kém`).
3. **Phân loại cảm xúc đa lớp (`PhoBERT` vs. Baseline), Mô hình Chủ đề (`LDA`) & Cảm xúc theo Khía cạnh (`ABSA`)**:
   - Đối sánh các mô hình học máy truyền thống (`TF-IDF` + Logistic Regression / Linear SVM / Complement Naive Bayes) với mô hình ngôn ngữ Transformer tiếng Việt **`vinai/phobert-base-v2`** tinh chỉnh có trọng số lớp (*class-weighted cross-entropy*) trên tập kiểm thử độc lập `2.974` đánh giá.
   - Huấn luyện mô hình chủ đề ẩn **LDA (5 chủ đề)** và hệ thống **ABSA 5 khía cạnh kỹ thuật** (`service_logistics`, `display_design`, `performance_thermal`, `battery_power`, `camera_audio`).

### 8.3. Các phát hiện định lượng cốt lõi & Tri thức nghiệp vụ rút ra

1. **Bằng chứng định lượng về "Lạm phát 5 sao" và sự vượt trội của PhoBERT**:
   - Trong `14.869` bình luận có chữ, **`84,79%` (`12.607` mẫu) chấm 5 sao**, `7,35%` (`1.093` mẫu) chấm 1 sao, kéo điểm sao trung bình lên **`4,56★`**, đồng thời phát hiện **`118` trường hợp mâu thuẫn trực diện** giữa điểm sao và nội dung lời bình.
   - Trên tập kiểm thử cực kỳ mất cân bằng lớp, **`PhoBERT` đạt `Macro F1 = 0,6491` và `Accuracy = 92,23%` (`Weighted F1 = 0,9302`)**, vượt xa mô hình cơ sở Logistic Regression (`Macro F1 = 0,5901`, tăng tương đối **`+10,0%`** khả năng nhận diện đúng các bình luận trung tính và tiêu cực hiếm).
2. **Cấu trúc 5 chủ đề thảo luận thực tế của người mua hàng công nghệ (LDA)**:
   - *Hiệu năng & Tốc độ xử lý* chiếm tỷ trọng thảo luận lớn nhất (**`29,61%`**), tiếp theo là *Dịch vụ cửa hàng & Giao nhận* (**`19,09%`**), *Trải nghiệm sử dụng dài ngày & Sự cố* (**`18,74%`**), *Màn hình & Camera* (**`16,46%`**) và *Thời lượng pin & Phụ kiện sạc* (**`16,11%`**). Phát hiện gần **1/5 lượng bình luận nói về dịch vụ bán hàng/vận chuyển** giải thích vì sao một mẫu máy tốt vẫn có thể bị chấm 1 sao do giao hàng trễ.
3. **Bản đồ Điểm đau Khách hàng qua 5 Khía cạnh Kỹ thuật (ABSA)**:

| Khía cạnh đánh giá (Aspect) | Tỷ lệ Tích cực | Tỷ lệ Trung tính | Tỷ lệ Tiêu cực | Hàm ý quản trị chất lượng & Tư vấn bán hàng |
|---|---:|---:|---:|---|
| **Dịch vụ & Giao vận (`service_logistics`)** | **90,96%** | 2,84% | 6,20% | Thế mạnh vận hành của các chuỗi bán lẻ chính hãng tại Việt Nam |
| **Màn hình & Thiết kế (`display_design`)** | **87,26%** | 4,02% | 8,72% | Mức độ hài lòng cao nhờ xu hướng phổ cập tấm nền OLED/viền mỏng |
| **Camera & Âm thanh (`camera_audio`)** | 76,65% | 5,45% | **17,90%** | Kỳ vọng chụp đêm/quay video thực tế khắt khe hơn số MP quảng cáo |
| **Pin & Nguồn sạc (`battery_power`)** | 77,37% | 4,51% | **18,12%** | Phàn nàn sụt pin sau cập nhật phần mềm và cắt giảm củ sạc đi kèm |
| **Hiệu năng & Tản nhiệt (`performance_thermal`)** | 73,63% | 5,03% | **21,34%** | **Điểm nghẽn số 1 thị trường (nóng máy, tụt xung, giật lag, tiếng ồn quạt)** |

- Đối sánh theo ngành hàng còn chỉ ra hành vi tiêu dùng rất rõ: người mua **Laptop** quan tâm tới *Hiệu năng & Tản nhiệt* (`29,42%` đề cập) và *Màn hình & Thiết kế* (`27,68%`) cao hơn hẳn người mua Smartphone (`18,65%` và `17,06%`); ngược lại khách hàng **Smartphone** nhạy cảm hơn với *Pin & Sạc* (`13,88%` vs `10,92%`) và *Camera* (`7,65%` vs `4,92%`).

---

## 9. KIỂM TOÁN BẤT THƯỜNG DANH MỤC VÀ GIÁ BÁN ĐA PHƯƠNG PHÁP *(Nguyễn Tùng Dương — 20230024 — TV7)*

### 9.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Trên sàn thương mại điện tử, một bản ghi có mức giá khác biệt lớn so với mặt bằng chung có thể mang hai bản chất hoàn toàn trái ngược: hoặc là **lỗi dữ liệu bẩn** (phụ kiện ốp lưng/cáp sạc gắn nhầm vào điện thoại, máy bàn Mac Studio gắn nhầm vào laptop, parse nhầm độ sáng `300 nits` thành màn hình `300 inch`), hoặc là **sản phẩm siêu cao cấp hợp lệ hiếm gặp** (máy trạm di động `MSI Titan 18 HX` gần 200 triệu đồng, điện thoại gập/Vertu chính hãng). Do không có nhãn gian lận xác thực, TV7 định hình bài toán chuẩn xác là **Kiểm toán Bất thường Thị trường & Danh mục (*Market & Catalog Anomaly Audit*)**: kết hợp đa phương pháp để phân loại đúng bản chất và đề xuất hành động xử lý phù hợp thay vì xóa dữ liệu tùy tiện.

### 9.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
Triển khai độc lập cho Laptop và Smartphone trên toàn bộ `10.316` bản ghi thông qua tổ hợp **3 phương pháp bổ trợ lẫn nhau** (`src/anomaly_detection/detect_price_anomalies.py`):
1. **Tầng 1 — Quy tắc miền vật lý & nghiệp vụ (`Rule-based`)**: Bắt các bản ghi dưới ngưỡng giá sàn (`Laptop < 3M`, `Smartphone < 1M`) và các vi phạm phi giá ngay cả khi thiếu giá (`screen_size_inch` ngoài `[10, 20]` inch ở Laptop hoặc `[3, 11]` inch ở Smartphone; máy bàn Apple `iMac / Mac mini / Mac Studio / Mac Pro` nằm trong danh mục `laptop`; ổ cứng laptop `< 32 GB`; trường `network_type_norm` chứa chuỗi tiền tệ VNĐ).
2. **Tầng 2 — Khoảng tứ phân vị trên thang Logarithm (`Log-Price IQR`)**: Tính $z_i = \ln(\text{price}_i)$ phân tầng theo từng cặp `(category, brand)` đối với các hãng có $\ge 20$ mẫu hợp lệ, gắn cờ ngoại lai vừa ($1,5 \times \text{IQR}$) và cực đoan ($3,0 \times \text{IQR}$).
3. **Tầng 3 — Rừng cô lập đa biến (`Isolation Forest`)**: Huấn luyện `300` cây cô lập (`contamination = 0,02`, `random_state = 42`) trên tổ hợp không gian giá log và các thuộc tính cấu hình để phát hiện các mẫu **lệch tương quan cấu hình – giá** mà quy tắc đơn biến không nhìn thấy.
4. **Phân rã bản chất nghiệp vụ (`anomaly_type`) & Khuyến nghị hành động (`recommended_action`)**: Hợp nhất tín hiệu của 3 phương pháp thành 4 nhóm hành động tường minh cho quản trị viên danh mục và mô hình hóa.

### 9.3. Kết quả kiểm toán định lượng & Bài học Khoa học Dữ liệu rút ra

- Trên `10.316` bản ghi kiểm toán (`8.548` có giá dương hợp lệ + `1.768` thiếu/không có giá dương), từng phương pháp gắn cờ lần lượt: **Rule-based: `494` (`4,79%`)**, **Log-IQR: `156` (`1,51%`)**, **Isolation Forest: `172` (`1,67%`)**. Hợp nhất cả 3 phương pháp phát hiện **`715` bản ghi bất thường (`6,93%`**, gồm `350` Laptop và `365` Smartphone; `106` mức `extreme` và `609` mức `review`; `102` bản ghi có từ $\ge 2$ phương pháp đồng thuận).

#### Bảng 9.1. Phân loại 4 nhóm bản chất bất thường và hành động quản trị tương ứng

| Nhóm bản chất (`anomaly_type`) | Số lượng bản ghi | Tỷ trọng trong 715 cờ | Khuyến nghị hành động (`recommended_action`) | Ví dụ thực tế điển hình trong dữ liệu |
|---|---:|---:|---|---|
| **`low_price_or_category_noise`** | **401** | 56,08% | `filter_before_modeling` *(Loại khỏi định giá / Chuyển đúng danh mục)* | Điện thoại cơ bản 2G/4G dưới 1 triệu, phụ kiện hoặc `Mac mini / iMac` lẫn vào Laptop |
| **`spec_price_mismatch_review`** | **156** | 21,82% | `sensitivity_check` *(Rà soát thủ công giá khuyến mãi / biến thể đặc biệt)* | Máy cấu hình phổ thông nhưng lưu giá niêm yết đợt mở bán cao bất thường hoặc giảm sâu xả kho |
| **`hardware_spec_error`** | **93** | 13,01% | `verify_or_correct_specs` *(Chuẩn hóa / Bóc tách lại thông số từ tiêu đề)* | Laptop parse nhầm độ sáng `300 nits` thành `300 inch`, hoặc `network_type_norm` dính chuỗi giá tiền |
| **`rare_valid_flagship`** | **65** | 9,09% | `keep_with_log_transform` *(Giữ lại nguyên vẹn kèm biến đổi log-price)* | Siêu phẩm thật RAM $\ge 32\text{GB}$, SSD $\ge 1\text{TB}$, GPU `RTX 4080/4090` như `ROG Zephyrus Duo 16` |
| **Bình thường (`none`)** | **9.601** | — | `none` *(Không cần can thiệp)* | Các dòng sản phẩm nằm trong miền giá – cấu hình chuẩn của thị trường |

**Bài học cốt lõi về Vệ sinh Dữ liệu**: Nếu một dự án thiếu bước phân loại ngữ nghĩa của TV7 mà xóa cơ học toàn bộ `715` dòng ngoại lai, hệ thống sẽ xóa nhầm **`65` siêu phẩm đầu bảng hợp lệ** — làm mất hoàn toàn tri thức định giá ở phân khúc cao cấp (điều được TV8 chứng minh định lượng ở thí nghiệm `S5b`).

---

## 10. THẨM ĐỊNH ĐỘC LẬP, GIẢI THÍCH NHÂN TỐ GIÁ (XAI) VÀ HỆ THỐNG HỖ TRỢ QUYẾT ĐỊNH 5 TAB *(Lê Trần Anh — 202416112 — TV8)*

### 10.1. Bài toán nghiệp vụ & Vai trò trong quy trình Khoa học Dữ liệu
Ở chặng cuối của chu trình Khoa học Dữ liệu, TV8 chịu trách nhiệm trả lời ba câu hỏi quyết định trước khi đưa hệ thống vào sử dụng thực tế: **(1) Các nhóm dữ liệu của TV3, TV4, TV6, TV7 thực sự đóng góp bao nhiêu phần trăm cải thiện cho bài toán định giá, và mô hình có bền vững khi thông số sàn bị khuyết không? (2) Mô hình định giá dựa trên quy luật kinh tế hợp lý hay đang học vẹt tương quan giả, sai số tập trung ở phân khúc nào? (3) Làm sao tích hợp toàn bộ kết quả của cả 8 thành viên thành một ứng dụng hỗ trợ ra quyết định dễ hiểu, trung thực và không cho phép nhập cấu hình phi vật lý?**

### 10.2. Cách thức triển khai kỹ thuật (Làm thế nào?)
1. **Đánh giá mô hình đa chiều (*3D Benchmark — Bảng 10.1*)**: Không chỉ đo sai số định lượng (`MAE`, `MdAE`, `RMSE`, `MAPE`, `MdAPE`, $R^2$) trên `1.629` mẫu kiểm thử độc lập (`819` Laptop + `810` Smartphone), TV8 còn đo **chi phí vận hành** (độ trễ suy luận trung bình `ms/mẫu`, dung lượng tệp `.pkl`) và **độ bền vững khi khuyết thông số thực tế** (mức tăng MAE khi che ngẫu nhiên `20%` RAM và `20%` Bộ nhớ).
2. **Thực nghiệm cắt lớp có kiểm soát (*Controlled Ablation S1–S4*) & Phân tích độ nhạy lọc bất thường (*TV7 Sensitivity S5a/S5b — Bảng 10.2*)**: Giữ cố định tập kiểm thử và cấu hình siêu tham số chuẩn để đo lường minh bạch tác động biên khi lần lượt bổ sung: xử lý tồn kho & sửa lỗi màn hình của TV3 (`S2A`), điểm chuẩn hiệu năng CPU/GPU & độ phủ nhà bán lẻ của TV4 (`S3`), đặc trưng độ phủ và cảm xúc đánh giá của TV6 (`S4`), và đối chứng hai chính sách lọc cờ bất thường TV7 trên tập huấn luyện (`S5a: lọc extreme` vs. `S5b: lọc toàn bộ combined_flag`).
3. **Phân tích sai số theo lát cắt nghiệp vụ (`Bảng 10.3–10.7`), Giải thích `TreeSHAP` quy đổi VNĐ & Kiểm định tính đơn điệu (`Hình 10.4–10.7`)**:
   - Mổ xẻ sai số theo khoảng giá, thương hiệu, nhà bán lẻ, trạng thái tồn kho, tình trạng khuyết RAM và độ phủ liên sàn; kiểm toán thủ công 20 bản ghi có sai số tuyệt đối lớn nhất đối chiếu trực tiếp với cờ TV7.
   - Quy đổi các giá trị đóng góp `SHAP` trên thang log về đúng **đơn vị tiền tệ VNĐ** bảo toàn tính chất cộng tính ($\text{Mức nền} + \sum \Delta \text{VNĐ}_j = \hat{P}$), đồng thời thực hiện phép thử bậc thang RAM (`8 → 64 GB`) và Bộ nhớ (`128 → 1.024 GB`) để kiểm tra tính hợp lý vật lý và phát hiện hiện tượng ngoại suy ngoài miền dữ liệu.
4. **Xây dựng Hệ thống Hỗ trợ Quyết định 5 Tab (`src/evaluation_demo/app.py`, `market_data.py`, `demo_data.py`)**:
   - Hợp nhất toàn bộ hiện vật phân tích của TV1–TV8 lên một giao diện trực quan duy nhất gồm 5 tab nghiệp vụ.
   - Thiết kế hàm kiểm toán giá hợp lý cho SKU thực tế `audit_listing_fair_value()` và bộ lọc tương thích phần cứng phân cấp `build_compatibility_options()` ngăn chặn triệt để các tổ hợp linh kiện không tồn tại ngoài đời thực.

### 10.3. Kết quả thẩm định định lượng & Minh chứng giá trị liên kết toàn dự án

1. **Chứng minh định lượng giá trị đóng góp của từng thành viên qua chuỗi Ablation `S1 → S4`**:
   - Trên **Laptop (`LightGBM`)**, việc bổ sung điểm chuẩn hiệu năng CPU/GPU thực tế từ Notebookcheck và số sàn cùng bán một cấu hình của TV4 (`S3`) giúp kéo giảm mạnh sai số MAE từ **`4,074 triệu` (`S2A`) xuống `3,717 triệu VNĐ` (giảm `-8,76%`)**, và khi kết hợp thêm độ phủ đánh giá khách hàng (`S3 + count`) đạt **`3,672 triệu VNĐ`**.
   - Trên **Smartphone (`LightGBM`)**, chuỗi tích hợp cải thiện ổn định qua từng bước từ **`2,469 triệu` (`S1`) → `2,457 triệu` (`S2A` — cờ tồn kho TV3) → `2,441 triệu` (`S3 + count`) → `2,398 triệu VNĐ` (`S4` đầy đủ cảm xúc PhoBERT & khía cạnh ABSA của TV6)**. Đặc biệt trên phân nhóm sản phẩm đã có bình luận khách hàng, `S4` giúp giảm sai số trên **cả 6/6 mô hình** ở cả hai ngành hàng.
2. **Bằng chứng thực nghiệm bác bỏ việc "xóa mù quáng mọi ngoại lai" (`S5b`)**:
   - Khi áp dụng chính sách lọc thô `S5b` (loại bỏ mọi dòng train có `combined_flag = True`), tập huấn luyện Smartphone bị mất **`10/13` mẫu điện thoại siêu cao cấp có giá từ `80 triệu VNĐ` trở lên**. Hệ quả là trên `11` mẫu điện thoại $\ge 80\text{ triệu}$ ở tập kiểm thử, sai số MAE của LightGBM **tăng vọt gấp đôi từ `20,0 triệu` (`S4`) lên `40,4 triệu VNĐ` (`S5b`)**, làm tổng MAE toàn ngành Smartphone xấu đi `+11,90%` (hoặc `+13,61%` khi tính lại cờ độc lập trên tập train). Kết quả này xác nhận hoàn toàn giá trị thực tiễn của việc tách nhãn `rare_valid_flagship` ở TV7.
3. **Chẩn đoán vùng sai số, Tổng quát hóa liên sàn & Giải thích nhân tố dẫn dắt giá (XAI)**:
   - *Theo tầm giá & độ phủ liên sàn*: Ở phân khúc phổ thông dưới 10 triệu (`443` mẫu test Smartphone), LightGBM đạt độ chính xác rất cao với **MAE chỉ `0,934 triệu VNĐ`**; trên các cấu hình xuất hiện ở nhiều chuỗi bán lẻ khác nhau (`167` mẫu), MAE giảm còn **`1,298 triệu VNĐ`** so với `1,858 triệu VNĐ` ở các cấu hình độc quyền chỉ xuất hiện một lần.
   - *Kiểm toán Top-20 ca lệch giá lớn nhất (`Bảng 10.7`)*: Đối chiếu với TV7 cho thấy các sai số lớn nhất không phải lỗi thuật toán ngẫu nhiên mà rơi đúng vào các phiên bản giới hạn/màn hình kép cực hiếm (như `ASUS ROG Zephyrus DUO 16 GX651AX` niêm yết `199,99 triệu`, mô hình định giá cấu hình ở mức `125,17 triệu`, đã được TV7 gắn cờ `review`).
   - *Giải thích TreeSHAP & Ranh giới ngoại suy*: Phân rã TreeSHAP toàn cục xác nhận mô hình tuân thủ đúng quy luật kinh tế học phần cứng: **Vi xử lý (`cpu_model`), Tương tác `RAM × Bộ nhớ` và `GPU` dẫn dắt giá Laptop**; trong khi **Vi xử lý SoC, Dung lượng lưu trữ (`storage_gb`), Thương hiệu (`brand`) và Màn hình OLED dẫn dắt giá Smartphone**. Phép thử bậc thang dung lượng chứng minh các mô hình cây giữ tính đơn điệu hợp lý trên miền dữ liệu thực, đồng thời phát hiện mô hình tuyến tính `Ridge` có thể vọt lên `1,81 tỷ VNĐ` nếu nhập mức RAM giả định `64 GB` cho điện thoại (ngoài miền dữ liệu thực tế tối đa `24 GB`) — từ đó giúp ứng dụng thiết lập giới hạn trần vật lý và cảnh báo ngoại suy an toàn.
4. **Hoàn thiện Hệ thống Hỗ trợ Quyết định 5 Tab & Kiểm thử tự động**:
   - Ứng dụng Streamlit 5 tab (`Tổng quan & Quy luật giá`, `Cạnh tranh đa sàn & Review`, `Thẩm định giá hợp lý`, `Kiểm toán bất thường`, `Đánh giá mô hình & XAI`) vận hành mượt mà trên dữ liệu thật của cả 8 thành viên và vượt qua toàn bộ bộ kiểm thử tự động `pytest` (kiểm tra tính bất biến dữ liệu chia nhóm, tái lập chính xác 6 mô hình, tính cộng tính SHAP VNĐ, ràng buộc tương thích phần cứng và kết xuất không lỗi trên cả 5 tab).

---

## KẾT LUẬN TỔNG HỢP VÀ HƯỚNG PHÁT TRIỂN

1. **Tổng kết giá trị Khoa học Dữ liệu đạt được**:
   Dự án của Nhóm 12 đã hoàn thành trọn vẹn một chu trình Khoa học Dữ liệu đầu–cuối trên dữ liệu thương mại điện tử thực tế tại Việt Nam (`10.316` dòng niêm yết sản phẩm và `15.805` đánh giá từ 5 chuỗi bán lẻ lớn). Thay vì dừng lại ở việc huấn luyện mô hình dự đoán giá đơn thuần, dự án đã trích xuất thành công hệ tri thức định lượng đa chiều có giá trị hành động trực tiếp: (i) làm sáng tỏ cấu trúc định giá trái ngược giữa Laptop và Smartphone cùng 3 nghịch lý thông số quảng cáo và hiện tượng trôi giá tồn kho; (ii) lập bản đồ cạnh tranh liên sàn trên `4.414` sản phẩm chuẩn và chỉ ra `90` khoảng trống danh mục kèm cấu hình khuyến nghị nhập hàng; (iii) bóc tách điểm nghẽn tản nhiệt/hiệu năng ẩn sau lớp vỏ `84,79%` đánh giá 5 sao bằng PhoBERT & ABSA; (iv) thiết lập quy trình kiểm toán 4 loại bất thường bảo vệ dữ liệu flagship hợp lệ; và (v) cung cấp công cụ **Thẩm định Giá Hợp lý (Hedonic Fair-Value)** có giải thích bằng tiền VNĐ cho từng SKU thực tế trên thị trường.
2. **Hướng mở rộng trong tương lai**:
   - Chuyển đổi từ thu thập ảnh chụp tĩnh (*cross-sectional snapshot*) sang thu thập định kỳ theo tuần (*longitudinal snapshots*) để theo dõi lịch sử biến động giá thực tế trước và sau các dịp khuyến mãi lớn, kiểm chứng trực tiếp mức độ "nâng giá gốc rồi giảm" tại từng sàn.
   - Mở rộng mô hình đồng nhất thực thể liên sàn sang các sàn thương mại điện tử mô hình chợ (*Marketplace* như Shopee Mall, Lazada Mall) nơi độ phân mảnh nhà bán hàng và rủi ro giá ảo còn phức tạp hơn nhiều lần so với 5 chuỗi bán lẻ chính hãng hiện tại.
