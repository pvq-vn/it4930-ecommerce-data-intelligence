# Ma trận quyết định trường TV2 – bản nháp v1

Tài liệu này tách ba quyết định khác nhau: **giữ dữ liệu gốc**, **tạo trường dẫn xuất**, và **không đưa trường vào một bảng phân tích cụ thể**. “Bỏ” ở Gold chỉ là không chiếu vào bảng đó; không xóa khỏi Raw/Staging và không làm mất khả năng truy nguyên.

## 1. Nguyên tắc xử lý missing

Missing được phân biệt theo ý nghĩa quan sát được:

- `NULL/không có trường`: nguồn không cung cấp hoặc bản ghi thiếu trường.
- Chuỗi rỗng/whitespace: có trường nhưng không có nội dung hữu ích.
- `0`: giữ nguyên là giá trị quan sát; chỉ gắn cờ khi trường có ngữ nghĩa khiến 0 đáng nghi.
- `Liên hệ`, `N/A`, chuỗi không parse được: không đổi thành 0; giữ raw và ghi trạng thái parse.
- Không điền trung vị, giá trị mặc định hoặc suy đoán từ tên sản phẩm ở TV2 v1.

## 2. Product fields

| Trường | Raw/Staging | Gold | Quyết định/missing |
|---|---|---|---|
| `source`, `category` | Giữ | Giữ | Khóa phạm vi; không missing trong các file hiện tại. |
| `crawl_batch`, `crawl_time` | Giữ + parse candidate | Giữ | Cần cho snapshot và lineage; không tự gán timezone. |
| `product_id_raw`, `product_url_raw` | Giữ | Giữ trong `fact_listings` | ID/URL nguồn, không canonical hóa. |
| `product_name_raw`, `parent_product_name_raw`, `parent_url_raw` | Giữ | Đại diện ở dimension + giữ listing | Không gộp tên khác nhau nếu chưa entity resolution; ghi conflict. |
| `parent_product_id_raw` | Giữ | Giữ | Tạo `source_parent_id` theo source/category/parent. |
| `variant_name_raw`, `variant_color_raw`, `variant_url_raw` | Giữ | Giữ | Chỉ là bằng chứng/candidate khi thiếu SKU. |
| `variant_sku_raw`, `sku_raw` | Giữ nguyên chuỗi | Giữ | Không bỏ số 0 đầu; không dùng đơn độc ngoài source/category. |
| `availability_raw` | Giữ | Giữ + `availability_status` | Mapping phải theo source; không suy ra chỉ từ giá. |
| `price_raw`, `original_price_raw` | Giữ + parse candidate | Giữ raw + value/status | Không đổi 0 thành missing; chỉ tính discount khi điều kiện hợp lệ. |
| `seller_raw` | Giữ | Giữ | Chưa chuẩn hóa tên seller nếu chưa có từ điển. |
| `rating_raw`, `review_count_raw` | Giữ + parse/status | Giữ raw + value/status | >5 là cờ ngoài thang khai báo; không tự sửa thành 5/NaN. |
| `attributes_raw` | Giữ nguyên payload | Giữ + trường trích xuất có confidence | Chưa regex bắt số; RAM, pin, sạc cần parser có ngữ cảnh. |
| `brand_raw` | Giữ | Giữ raw + mapping candidate | Chỉ mapping khi có từ điển kiểm soát và log bằng chứng. |
| `total_sold_raw` | Giữ | Giữ + missing flag | Không điền; missing hiện được báo cáo riêng. |
| `raw_payload` | Giữ bất biến | Tách payload/provenance | Không dùng làm cột feature trực tiếp; không xóa bằng chứng. |

## 3. Review fields

| Trường | Raw/Staging | Gold | Quyết định/missing |
|---|---|---|---|
| `source`, `category`, `crawl_batch`, `crawl_time` | Giữ | Giữ | Phạm vi và snapshot. |
| `parent_product_id_raw`, `parent_product_url_raw` | Giữ | Giữ + `source_parent_id` | Review có thể chỉ liên kết tới parent. |
| `review_id_raw` | Giữ | Giữ + `review_record_id` | Không gộp chỉ vì text giống nhau. |
| `rating_raw` | Giữ + status | Giữ | Không coi rating giống nhau là review giả. |
| `review_text_raw` | Giữ | Giữ + usability flags | Text thiếu/whitespace được gắn cờ; không xóa ở TV2. |
| `author_raw`, `review_time_raw`, `like_count_raw` | Giữ + parse candidate | Giữ | Missing giữ nguyên; không suy đoán danh tính/thời gian. |
| `review_product_code_raw`, `variant_code_raw`, `variant_sku_raw` | Giữ | Giữ + `variant_link_status` | `variant_code_raw` và FPT `orderCode` chỉ là mã candidate theo source, không đồng nghĩa SKU. |
| `buy_date_raw` | Giữ | Giữ | Chưa xác minh là ngày mua hợp lệ. |
| `reply_raw`, `attached_files_raw` | Giữ | Tách `fact_review_replies`/attachment flags | Không coi reply là review độc lập. |
| `raw_payload` | Giữ bất biến | Tách payload/provenance | Dùng để kiểm chứng metadata, đặc biệt Viettel. |

## 4. Trường không đưa trực tiếp vào mọi bảng Gold

Không có danh sách “drop toàn cục”. Một số trường có thể không chiếu vào bảng dimension hoặc feature table nếu không phù hợp, nhưng vẫn tồn tại trong Raw/Staging và phải có lý do trong log:

- `raw_payload`: phục vụ provenance, không phải feature mặc định.
- Các trường URL/raw ID: dùng liên kết và truy nguyên, không mặc định đưa vào mô hình.
- `reply_raw` hoặc payload review: tách theo grain, không trải phẳng vào một dòng review nếu làm sai đơn vị bản ghi.

## 5. Các quyết định còn phải xác minh trước khi chuẩn hóa

1. Mapping `availability_raw` theo từng source.
2. Parser `attributes_raw` và bộ test có nhãn cho RAM/pin/sạc.
3. Từ điển brand có kiểm soát, không tự gộp thương hiệu/dòng máy.
4. Quy tắc phân biệt sentinel zero với giá 0 có nghĩa.
5. Tiêu chí review metadata candidate của Viettel và cách trình bày trong NLP.

Chỉ sau khi các quy tắc trên được thống nhất mới tạo bản dữ liệu chuẩn hóa tiếp theo; bản Gold v1 hiện tại vẫn là bản chiếu có truy nguyên và cờ chất lượng.
