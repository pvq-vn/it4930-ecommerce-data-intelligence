# Tài Liệu Bàn Giao Dữ Liệu Thô (Raw Data Handoff Document)
## IT4930 - Nhập môn Khoa học Dữ liệu | it4930-ecommerce-data-intelligence

---

## 1. Mục đích

Tài liệu này đóng vai trò là biên bản bàn giao dữ liệu kỹ thuật từ giai đoạn **Web Crawling & Data Acquisition** sang giai đoạn **Data Quality & Integration**:
- Toàn bộ dữ liệu trong thư mục này là dữ liệu thô (Raw Data) được thu thập từ 5 sàn thương mại điện tử lớn tại Việt Nam cho 2 danh mục: **Laptop** và **Smartphone**.
- Dữ liệu được bảo toàn nguyên vẹn ở trạng thái raw, giữ nguyên kiểu dữ liệu gốc, cấu trúc HTML/JSON-LD, thông số kỹ thuật và provenance metadata.
- **TV2** chịu trách nhiệm tiếp nhận và thực hiện các công đoạn: làm sạch (cleaning), chuẩn hóa (normalization), khử trùng lặp (deduplication), so khớp thực thể (entity matching) và tích hợp đa nguồn (cross-source integration).

### Nguyên tắc bất biến (Core Principles)
- **Raw data là IMMUTABLE (Bất biến)**: Tuyệt đối không thay đổi, chỉnh sửa hay xóa bất kỳ file hoặc dòng dữ liệu nào trong `data/raw/`.
- **Không overwrite trực tiếp**: TV2 không được phép ghi đè (overwrite) hoặc ghi nối (append) vào các file snapshot thô trong `data/raw/`.
- **Phân định ranh giới đầu ra**: Mọi kết quả, dataset sau xử lý làm sạch, chuẩn hóa và tích hợp của TV2 bắt buộc phải được lưu trữ trong thư mục `data/processed/`.

---

## 2. Cấu trúc thư mục

Cấu trúc lưu trữ dữ liệu của dự án được tổ chức như sau:

```text
data/
├── raw/
│   ├── README.md
│   ├── tgdd/
│   │   ├── laptop.jsonl
│   │   ├── laptop_reviews.jsonl
│   │   ├── smartphone.jsonl
│   │   └── smartphone_reviews.jsonl
│   ├── fptshop/
│   │   ├── laptop.jsonl
│   │   ├── laptop_reviews.jsonl
│   │   ├── smartphone.jsonl
│   │   └── smartphone_reviews.jsonl
│   ├── cellphoneS/
│   │   ├── laptop.jsonl
│   │   ├── laptop_reviews.jsonl
│   │   ├── smartphone.jsonl
│   │   └── smartphone_reviews.jsonl
│   ├── viettelStore/
│   │   ├── laptop.jsonl
│   │   ├── laptop_reviews.jsonl
│   │   ├── smartphone.jsonl
│   │   └── smartphone_reviews.jsonl
│   └── hoanghamobile/
│       ├── laptop.jsonl
│       ├── laptop_reviews.jsonl
│       ├── smartphone.jsonl
│       └── smartphone_reviews.jsonl
│
└── processed/
    └── .gitkeep
```

### Ý nghĩa các thư mục:
- **`data/raw/`**: Thư mục lưu trữ các tập tin dữ liệu thô (raw data snapshots) định dạng JSON Lines (`.jsonl`), được trích xuất trực tiếp từ các website sàn TMĐT bởi TV1. Toàn bộ nội dung trong thư mục này là bất biến (immutable) và tuân thủ Canonical Raw Schema.
- **`data/processed/`**: Thư mục làm việc và lưu trữ đầu ra độc quyền của TV2. Chứa các tập dữ liệu đã qua tiền xử lý, làm sạch định dạng giá, trích xuất cấu hình RAM/SSD, chuẩn hóa thương hiệu, khử trùng lặp và bảng dữ liệu tích hợp hoàn chỉnh.

---

## 3. Các nguồn dữ liệu

Dự án thu thập dữ liệu từ đúng 5 sàn thương mại điện tử phân phối thiết bị công nghệ chính hãng tại Việt Nam:

| Source | Tên | Category |
|---|---|---|
| tgdd | TGDĐ | laptop, smartphone |
| fptshop | FPT Shop | laptop, smartphone |
| cellphoneS | CellphoneS | laptop, smartphone |
| viettelStore | Viettel Store | laptop, smartphone |
| hoanghamobile | Hoàng Hà Mobile | laptop, smartphone |

*(Hệ thống không thu thập bất kỳ nguồn nào nằm ngoài 5 sàn trên).*

---

## 4. Google Drive

(https://drive.google.com/drive/folders/1wQbWDOmYZFz2Ut3AShMu2o1wkMTJESuJ?usp=sharing)

| Source | Laptop | Smartphone | Reviews |
|---|---|---|---|
| TGDĐ | TODO | TODO | TODO |
| FPT Shop | TODO | TODO | TODO |
| CellphoneS | TODO | TODO | TODO |
| Viettel Store | TODO | TODO | TODO |
| Hoàng Hà Mobile | TODO | TODO | TODO |

---

## 5. Product Raw Schema

Dữ liệu sản phẩm tuân thủ nghiêm ngặt **Canonical Product Raw Contract** gồm đúng **25 trường** theo thứ tự:

```text
source
category
crawl_batch
crawl_time
product_id_raw
product_name_raw
product_url_raw
parent_product_id_raw
parent_product_name_raw
parent_url_raw
sku_raw
variant_sku_raw
variant_name_raw
variant_color_raw
variant_url_raw
availability_raw
price_raw
original_price_raw
brand_raw
seller_raw
rating_raw
review_count_raw
total_sold_raw
attributes_raw
raw_payload
```

### Bảng đặc tả chi tiết 25 trường Product Raw:

| STT | Field | Ý nghĩa | Ghi chú về dữ liệu raw |
|---|---|---|---|
| 1 | `source` | Mã định danh sàn TMĐT | Chuỗi viết thường: `tgdd`, `fptshop`, `cellphoneS`, `viettelStore`, `hoanghamobile`. |
| 2 | `category` | Danh mục sản phẩm | Một trong hai danh mục chuẩn: `laptop` hoặc `smartphone`. |
| 3 | `crawl_batch` | Mã định danh mẻ crawl | Chuỗi batch định danh phiên thu thập (ví dụ: `20261017_132828`). |
| 4 | `crawl_time` | Dấu thời gian thu thập | Định dạng thời gian chuẩn ISO-8601 (`YYYY-MM-DDTHH:MM:SS.mmmmmm`). |
| 5 | `product_id_raw` | ID gốc của sản phẩm | Chuỗi ID số hoặc mã định danh của sản phẩm lấy từ URL/HTML/API của sàn. |
| 6 | `product_name_raw` | Tên gốc của sản phẩm | Tiêu đề sản phẩm nguyên bản từ thẻ `h1` hoặc metadata JSON-LD của trang chi tiết. |
| 7 | `product_url_raw` | URL gốc của sản phẩm | Địa chỉ URL đầy đủ, chuẩn hóa giao thức `https://` dẫn đến sản phẩm. |
| 8 | `parent_product_id_raw` | ID nhóm/sản phẩm cha | Định danh nhóm sản phẩm cha; nếu không có phân cấp thì bằng `product_id_raw`. |
| 9 | `parent_product_name_raw` | Tên nhóm/sản phẩm cha | Tên dòng/nhóm sản phẩm cha; nếu không có thì bằng `product_name_raw`. |
| 10 | `parent_url_raw` | URL nhóm/sản phẩm cha | URL dẫn đến trang nhóm sản phẩm cha; mặc định là `product_url_raw`. |
| 11 | `sku_raw` | Mã SKU sản phẩm gốc | Mã quản lý kho hàng của sản phẩm được bóc tách từ thông số/DOM (có thể `null`). |
| 12 | `variant_sku_raw` | Mã SKU biến thể | Mã SKU riêng biệt của từng biến thể (RAM/SSD/màu) nếu sàn có quản lý riêng. |
| 13 | `variant_name_raw` | Tên phiên bản / cấu hình | Tên biến thể cấu hình (ví dụ: `16GB - 512GB`, `8GB/256GB`); `null` nếu là sản phẩm đơn. |
| 14 | `variant_color_raw` | Tên màu sắc biến thể | Tên màu sắc hiển thị trên giao diện sàn (ví dụ: `Titan Sa Mạc`, `Bạc`); có thể `null`. |
| 15 | `variant_url_raw` | URL biến thể cụ thể | URL gắn liền với tùy chọn cấu hình/màu sắc đang xem. |
| 16 | `availability_raw` | Tình trạng tồn kho raw | Chuỗi trạng thái tồn kho gốc (`InStock`, `Sẵn hàng`, `Tạm hết hàng`, `Liên hệ`, hoặc `null`). |
| 17 | `price_raw` | Giá bán hiện tại gốc | Giá bán thực tế nguyên bản (`string` kèm đơn vị như `23.990.000 ₫`, `number`, hoặc `Liên hệ`). |
| 18 | `original_price_raw` | Giá niêm yết cũ gốc | Giá trước khi giảm (gạch ngang) của chính sản phẩm; `null` nếu không có chiết khấu. |
| 19 | `brand_raw` | Tên thương hiệu gốc | Tên nhãn hàng lấy từ metadata, breadcrumb hoặc specs (chưa chuẩn hóa case). |
| 20 | `seller_raw` | Tên đơn vị bán lẻ | Tên sàn bán hàng chính thức (ví dụ: `Thế Giới Di Động`, `FPT Shop`, `CellphoneS`,...). |
| 21 | `rating_raw` | Điểm đánh giá trung bình | Số sao hoặc điểm đánh giá gốc (thang 5); `null` nếu chưa có đánh giá. |
| 22 | `review_count_raw` | Tổng số lượt đánh giá | Số lượng đánh giá hiển thị trên trang; kiểu `int`, `string` hoặc `null`. |
| 23 | `total_sold_raw` | Số lượng đã bán | Số sản phẩm đã bán ra nếu sàn hiển thị công khai (thường là `null` trên các sàn này). |
| 24 | `attributes_raw` | Bảng thông số kỹ thuật | Dictionary (`key-value`) chứa toàn bộ bảng cấu hình chi tiết trích xuất nguyên bản. |
| 25 | `raw_payload` | Payload provenance gốc | Dict chứa metadata JSON-LD, listing snapshot phục vụ audit/debug; **TV2 không sửa**. |

### Các ghi chú kỹ thuật quan trọng cho TV2:
- **Ý nghĩa hậu tố `_raw`**: Toàn bộ các trường có hậu tố `_raw` đều là dữ liệu trích xuất nguyên bản từ HTML DOM hoặc API của website nguồn, hoàn toàn chưa qua các bước normalize, clean, chuyển đổi đơn vị hay ép kiểu.
- **Đặc thù trường giá (`price_raw`, `original_price_raw`)**: Tùy theo từng nguồn, giá có thể là chuỗi ký tự định dạng kiểu Việt Nam (`23.990.000 ₫`), chuỗi số (`23990000`), chuỗi ký tự thông báo (`Liên hệ`, `Tạm hết hàng`), hoặc `null`. Giá gốc `original_price_raw` đã được TV1 lọc bỏ các giá phụ kiện/trả góp/member, nhưng TV2 cần parse số và xử lý logic so sánh.
- **Đặc thù thông số kỹ thuật (`attributes_raw`)**: Là một dictionary thuần túy lưu trữ các cặp thông số (như `{"Màn hình": "14 inch OLED", "CPU": "Intel Core Ultra 5"}`). Các khóa và giá trị phụ thuộc vào cấu trúc bảng của từng sàn, có thể chứa dấu xuống dòng, khoảng trắng thừa hoặc tên gọi khác nhau giữa các sàn.
- **Trường `raw_payload`**: Là đối tượng provenance lưu vết dữ liệu gốc nhằm mục đích kiểm tra chéo (audit trail). TV2 tuyệt đối không can thiệp, chỉnh sửa hay xóa bỏ trường này.
- **Không tự suy diễn giá trị thiếu (Missing values)**: Nếu một trường raw có giá trị `null` hoặc chuỗi rỗng `""`, TV2 phải tôn trọng bản chất thiếu dữ liệu của nguồn, không được tự ý điền các giá trị mặc định giả tạo làm sai lệch bản chất dữ liệu thô.

---

## 6. Review Raw Schema

Dữ liệu đánh giá của người dùng tuân thủ nghiêm ngặt **Canonical Review Raw Contract** gồm đúng **19 trường** theo thứ tự:

```text
source
category
crawl_batch
crawl_time
parent_product_id_raw
parent_product_url_raw
review_id_raw
rating_raw
review_text_raw
author_raw
review_time_raw
like_count_raw
review_product_code_raw
variant_code_raw
variant_sku_raw
buy_date_raw
reply_raw
attached_files_raw
raw_payload
```

### Bảng đặc tả chi tiết 19 trường Review Raw:

| STT | Field | Ý nghĩa | Ghi chú về dữ liệu raw |
|---|---|---|---|
| 1 | `source` | Mã định danh sàn TMĐT | Chuỗi định danh nguồn: `tgdd`, `fptshop`, `cellphoneS`, `viettelStore`, `hoanghamobile`. |
| 2 | `category` | Danh mục sản phẩm | `laptop` hoặc `smartphone`. |
| 3 | `crawl_batch` | Mã định danh mẻ crawl | Đồng bộ với batch ID của sản phẩm tương ứng. |
| 4 | `crawl_time` | Dấu thời gian thu thập | Thời gian ghi nhận review (định dạng ISO-8601). |
| 5 | `parent_product_id_raw` | ID sản phẩm cha liên kết | Khóa ngoại dùng để ánh xạ bài đánh giá này về bản ghi trong `product.jsonl`. |
| 6 | `parent_product_url_raw` | URL sản phẩm cha liên kết | URL trang sản phẩm chứa review này. |
| 7 | `review_id_raw` | Mã định danh review | ID duy nhất của review từ hệ thống đánh giá của sàn. |
| 8 | `rating_raw` | Số sao đánh giá gốc | Thường từ 1 đến 5 (dạng số hoặc chuỗi, ví dụ: `5`, `4.0`, có thể `null`). |
| 9 | `review_text_raw` | Nội dung nhận xét gốc | Văn bản bình luận đầy đủ của người dùng, giữ nguyên chính tả, dấu câu, icon. |
| 10 | `author_raw` | Tên người đánh giá | Tên hiển thị của khách hàng viết đánh giá (có thể ẩn danh, ví dụ: `Anh Nam`, `Khách`). |
| 11 | `review_time_raw` | Thời gian đăng đánh giá | Chuỗi thời gian raw từ giao diện (ví dụ: `2 ngày trước`, `14/10/2026`, timestamp). |
| 12 | `like_count_raw` | Lượt thích / hữu ích | Số lượt người dùng khác bấm 'Hữu ích' / Thích cho review này. |
| 13 | `review_product_code_raw` | Mã sản phẩm nội bộ sàn | Mã quản lý sản phẩm nội bộ của hệ thống review (nếu có). |
| 14 | `variant_code_raw` | Mã biến thể đã mua | Mã cấu hình phiên bản mà khách hàng đã thực tế mua khi đánh giá. |
| 15 | `variant_sku_raw` | SKU biến thể đã mua | Mã SKU cụ thể của sản phẩm đã mua gắn với review. |
| 16 | `buy_date_raw` | Ngày mua hàng đã xác thực | Thời điểm khách hàng mua hàng (verified purchase badge nếu có). |
| 17 | `reply_raw` | Phản hồi của quản trị viên | Nội dung phản hồi từ đại diện sàn bán hàng / CSKH (nếu có). |
| 18 | `attached_files_raw` | Danh sách tệp đính kèm | Mảng chứa URL các hình ảnh/video thực tế người dùng chụp đính kèm review. |
| 19 | `raw_payload` | Payload provenance gốc | Dict chứa bản ghi response thô từ API review của sàn; **TV2 không sửa**. |

---

## 7. Validation Status

Hệ thống dữ liệu thô đã trải qua quy trình kiểm thử và thẩm định schema toàn diện (automated schema validation test suite):
- **Product Schema**: Đạt **25/25 fields** hợp lệ 100% trên cả 5 nguồn dữ liệu.
- **Review Schema**: Đạt **19/19 fields** hợp lệ 100% trên tất cả các file review có dữ liệu.
- **Lưu ý về Hoàng Hà Mobile**: Sàn Hoàng Hà Mobile không sử dụng hệ thống star-rating/review truyền thống mà chỉ có luồng bình luận/hỏi đáp Q&A (theo quy tắc contract không được map nhầm vào review). Do đó, 2 file review của Hoàng Hà Mobile hiện có **0 records** (kích thước 0 bytes) và trạng thái schema được ghi nhận là **EMPTY / NOT OBSERVABLE**, hoàn toàn không phải lỗi schema failure.

### Thống kê số lượng bản ghi (Dataset Counts Snapshot):

#### Dữ liệu Sản phẩm (Product Records):
- **TGDĐ**: 490 laptop + 707 smartphone = 1,197 records
- **FPTShop**: 356 laptop + 464 smartphone = 820 records
- **CellphoneS**: 3,912 laptop + 3,935 smartphone = 7,847 records
- **ViettelStore**: 23 laptop + 144 smartphone = 167 records
- **Hoàng Hà Mobile**: 93 laptop + 192 smartphone = 285 records

#### Dữ liệu Đánh giá (Review Records):
- **TGDĐ**: 99 laptop + 2,329 smartphone = 2,428 records
- **FPTShop**: 602 laptop + 1,092 smartphone = 1,694 records
- **CellphoneS**: 1,898 laptop + 9,296 smartphone = 11,194 records
- **ViettelStore**: 63 laptop + 426 smartphone = 489 records
- **Hoàng Hà Mobile**: 0 laptop + 0 smartphone = 0 records

#### Tổng cộng hiện tại:
- **10,316** product/variant records
- **15,805** review records

> *Lưu ý: Đây là số liệu snapshot hiện tại đã được validation của đợt crawl. Đây là số liệu cố định của dataset bàn giao, không phải là con số động.*

---

## 8. Quy định cho TV2

Nhằm đảm bảo tính toàn vẹn dữ liệu, quy trình khoa học dữ liệu chuẩn mực và phân định trách nhiệm rõ ràng giữa các giai đoạn của dự án, các quy định sau được áp dụng bắt buộc cho thành viên phụ trách **TV2 (Data Quality & Integration)**:

### TV2 ĐƯỢC PHÉP:
1. **Làm sạch và chuẩn hóa giá (Price parsing & normalization)**: Phân tích cú pháp chuỗi `price_raw`, `original_price_raw` thành kiểu số nguyên/thực (`int`/`float`), quy đổi về đơn vị chuẩn (VND), tính toán tỷ lệ chiết khấu, xử lý các trường hợp "Liên hệ" hoặc ngoại lai.
2. **Xử lý dữ liệu khuyết thiếu (Missing value handling)**: Phân loại cơ chế missing (MCAR, MAR, MNAR), áp dụng kỹ thuật loại bỏ hoặc điền khuyết (imputation) phù hợp trong tập dữ liệu mới dưới `data/processed/`.
3. **Chuẩn hóa thông số kỹ thuật (Specification normalization)**: Bóc tách, trích xuất và chuẩn hóa các trường thông số kỹ thuật quan trọng từ `attributes_raw` và tên sản phẩm thành các cột có cấu trúc riêng (RAM theo GB, SSD theo GB/TB, CPU family/generation, độ phân giải màn hình, kích thước màn hình theo inch, dung lượng pin theo mAh/Wh).
4. **Chuẩn hóa thương hiệu & danh mục (Brand & category normalization)**: Đưa tên thương hiệu về dạng chuẩn đồng nhất (ví dụ: `APPLE` / `apple` → `Apple`, `ASUS` / `asus` → `Asus`).
5. **Khử trùng lặp (Deduplication)**: Nhận diện và xử lý các bản ghi trùng lặp nội bộ sàn hoặc giữa các phiên crawl.
6. **So khớp thực thể (Entity matching & resolution)**: Ghép nối các bản ghi cùng một dòng sản phẩm/model trên các sàn khác nhau thông qua tên gọi, SKU, model number và cấu hình.
7. **Tích hợp đa nguồn (Cross-source integration)**: Xây dựng bảng dữ liệu thống nhất phục vụ phân tích so sánh giá, thị phần và mô hình hóa machine learning.
8. **Tạo dataset mới trong `data/processed/`**: Tự do kiến trúc các bảng dữ liệu mới, định dạng tập tin lưu trữ (ví dụ `.csv`, `.parquet`, `.jsonl`) bên trong thư mục `data/processed/`.

### TV2 KHÔNG ĐƯỢC PHÉP:
1. **Không sửa raw**: Tuyệt đối không chỉnh sửa nội dung bất kỳ tập tin nào trong `data/raw/`.
2. **Không overwrite raw**: Không lưu đè kết quả đã làm sạch vào các file thô ban đầu.
3. **Không xóa raw**: Không xóa bất kỳ tập tin snapshot nào trong `data/raw/` (kể cả các file rỗng như `hoanghamobile/*_reviews.jsonl`).
4. **Không suy diễn rồi ghi ngược vào raw**: Không suy diễn các giá trị thiếu hoặc giá trị đã chuẩn hóa rồi cập nhật ngược lại vào thư mục raw.
5. **Không thay đổi schema raw**: Không thay đổi schema raw mà không có quyết định chung của toàn thể project.

---

## 9. Handoff Note

> TV1 đã hoàn tất crawling và validation schema cho 5 nguồn. TV2 bắt đầu từ các file trong `data/raw/` và tạo toàn bộ output xử lý dưới `data/processed/`.
