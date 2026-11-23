# Gold v2 — Hướng dẫn sử dụng cho TV3–TV8

Thư mục này chứa các bảng Gold được tạo từ Silver v2. Các file đều ở định dạng JSONL: mỗi dòng là một bản ghi JSON độc lập. Gold v2 giữ số dòng theo dữ liệu đầu vào, không tự động điền missing và không hợp nhất cùng một sản phẩm giữa các cửa hàng.

## Các file trong thư mục

### `dim_source_parents.jsonl`

Đơn vị một dòng là một sản phẩm cha trong một `source/category`.

File này chứa tên sản phẩm đại diện, URL đại diện, số listing thuộc sản phẩm cha và mã `source_parent_id`.

Dùng để:

- Lấy tên sản phẩm khi bảng listing chỉ có ID parent.
- Nhóm listing hoặc review theo sản phẩm cha trong cùng nguồn.
- Kiểm tra xung đột tên và URL của cùng một parent.

Khóa chính: `source_parent_id`.

### `fact_listings.jsonl`

Đơn vị một dòng là một listing/variant được quan sát trong một snapshot của cửa hàng.

Đây là bảng rộng, gồm trường raw, trường chuẩn hóa, cờ chất lượng và thông tin truy nguyên như `raw_file`, `raw_line_number`, `raw_record_id` và `raw_payload`.

Dùng để:

- Audit và truy nguyên về dữ liệu raw.
- Kiểm tra chi tiết chất lượng từng listing.
- Phân tích các trường raw hoặc cờ bất thường khi cần bằng chứng.

Khóa chính: `listing_record_id`.

Không dùng bảng này làm bảng feature mặc định nếu không cần các trường audit và raw payload.

### `fact_listings_features.jsonl`

Đơn vị một dòng vẫn là một listing/variant, nhưng chỉ giữ các trường canonical phục vụ phân tích.

File này có các trường về ID, nguồn, danh mục, brand, giá, rating, availability và thông số phần cứng đã bóc tách như RAM, CPU, GPU, storage, pin, màn hình và camera.

Dùng cho:

- TV3: EDA.
- TV4: graph listing/seller/category.
- TV5: price prediction.
- TV7: anomaly detection.
- TV8: phân tích và giải thích feature.

Khóa chính: `listing_record_id`.

### `fact_reviews.jsonl`

Đơn vị một dòng là một review gốc.

File này giữ thông tin review đầy đủ hơn, gồm text, rating, thời gian, metadata, cờ `review_usable` và mã liên kết sản phẩm cha.

Dùng chủ yếu cho:

- TV6: NLP, sentiment và topic mining.
- Kiểm tra quan hệ review–sản phẩm.
- Phân tích metadata review theo source.

Khóa chính: `review_record_id`.

### `fact_review_replies.jsonl`

Đơn vị một dòng là một phản hồi con của review.

File này dùng khi cần phân tích phản hồi của cửa hàng hoặc quan hệ review–reply. Không gộp phản hồi con vào review gốc.

Dùng chủ yếu cho TV6.

Khóa phản hồi: `reply_record_id`; liên kết tới review gốc qua `parent_review_record_id`.

## Quy tắc liên kết

- Nối listing với parent bằng `source_parent_id`.
- Nối review với parent bằng `source_parent_id`.
- Không nối review với mọi listing cùng parent nếu cần dữ liệu ở cấp variant; phép nối đó là one-to-many và có thể nhân số dòng.
- `source_parent_id` chỉ nhận diện sản phẩm cha trong cùng `source/category`. Nó chưa phải mã nhận diện một sản phẩm hợp nhất giữa các cửa hàng.
- Không mặc định coi `product_id_raw`, SKU hoặc tên sản phẩm giống nhau ở các cửa hàng là cùng một sản phẩm.

## Nên dùng file nào?

| Nhu cầu | File nên dùng |
|---|---|
| Phân tích listing và giá | `fact_listings_features.jsonl` |
| Audit hoặc truy nguyên raw | `fact_listings.jsonl` |
| Lấy tên sản phẩm cha | `dim_source_parents.jsonl` |
| NLP review | `fact_reviews.jsonl` |
| Phân tích phản hồi cửa hàng | `fact_review_replies.jsonl` |

Các giá trị `null` được giữ lại theo dữ liệu và policy của TV2. Không tự động coi `null` là 0 và không tự động xóa bản ghi chỉ vì thiếu một trường.
