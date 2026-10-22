# Pipeline thực thi TV2 – giải quyết từng nhóm vấn đề

Bản phát hành cuối chỉ được tạo sau khi tất cả stage dưới đây chạy thành công. Không stage nào ghi đè Raw; mỗi stage tạo output phiên bản mới và báo cáo kiểm tra.

## Luồng tổng thể

```text
Raw v0
  -> S0: manifest/provenance
  -> S1: schema + kiểu dữ liệu
  -> S2: missing semantics theo source
  -> S3: price/rating/availability normalization
  -> S4: identity, duplicate và grain
  -> S5: nested attributes parser
  -> S6: review/reply linkage và metadata
  -> S7: Gold views theo bài toán
  -> S8: release quality gates
  -> TV2 release v1 (final)
```

## Stage và tiêu chí hoàn thành

### S0 – Khóa đầu vào

Input là 18 file Raw. Tính SHA256, số dòng và `raw_record_id`. Nếu file đổi, pipeline dừng và tạo release mới.

### S1 – Schema và kiểu dữ liệu

Kiểm tra JSONL, trường tầng ngoài, kiểu giá trị và payload lồng nhau. Mọi parse lỗi có trạng thái riêng; không đổi raw.

### S2 – Missing semantics

Phân biệt `NULL`, chuỗi rỗng, container rỗng, `0`, chuỗi “Liên hệ” và giá trị không parse được. Quy tắc được ghi theo `source/category/field`; chưa điền giá trị ở stage này.

### S3 – Chuẩn hóa nghiệp vụ

Tạo cột dẫn xuất cho giá, giá gốc, discount, rating và availability. Chỉ tính discount khi điều kiện hợp lệ. Rating ngoài thang giữ raw và gắn trạng thái. Availability phải có mapping theo source.

### S4 – Grain, định danh và duplicate

Giữ một dòng quan sát theo `raw_record_id`. Không deduplicate theo text/tên. Kiểm tra SKU trong parent, mã review và các candidate key; trường hợp mơ hồ được gắn cờ.

### S5 – Thuộc tính lồng nhau

Parser có ngữ cảnh cho RAM hiện tại/tối đa, pin và sạc. Mỗi giá trị có `extraction_status`, `confidence` và đường dẫn bằng chứng. Parser thất bại không được tự đoán.

### S6 – Review và liên kết

Tách review cấp cao nhất và reply. Nối trong cùng `source/category`; giữ `PARENT_ONLY`, `VARIANT_MATCHED`, `VARIANT_UNRESOLVED`. Viettel metadata được báo cáo như candidate, không gán nhãn review giả.

### S7 – Gold views

Tạo dimension parent theo source, fact listing, fact review và fact reply. Các view phục vụ TV3–TV8 có thể chọn cột, nhưng phải giữ khóa truy nguyên.

### S8 – Release gates

- Không mất dòng ngoài các dòng JSON không hợp lệ đã được báo cáo.
- Raw SHA256 không đổi.
- Khóa duy nhất theo grain.
- Không còn parse lỗi không có trạng thái.
- Mọi missing và anomaly có lý do.
- Nối review không tạo nhân dòng ngoài quy tắc đã công bố.
- Báo cáo trước/sau và manifest được tạo tự động.

## Trạng thái hiện tại

- S0–S1: đã có kiểm tra và báo cáo.
- S2: đã lập missing profile; policy theo source đang được chốt.
- S3: có Silver v2 bảo thủ; cần hoàn thiện mapping availability và parser số theo source.
- S4: đã audit grain và khóa.
- S5: chưa hoàn thành parser attributes có validation set.
- S6: đã có liên kết parent/variant và tách reply; cần hoàn thiện policy review metadata.
- S7: đã có Gold v1, chưa phải release cuối.
- S8: mới có manifest/validation cơ bản; chưa đủ điều kiện gọi là final.

## Khi nào có bản chuẩn cuối?

Chỉ khi S2–S6 đã có policy được kiểm chứng, S7 được dựng lại từ output các stage đó và S8 đạt toàn bộ quality gates. Từ thời điểm đó, `tv2-release-v1` mới là bản bàn giao chính thức; các bản trước được giữ để so sánh và truy nguyên.
