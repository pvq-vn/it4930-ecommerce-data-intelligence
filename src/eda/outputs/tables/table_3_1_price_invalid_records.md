### Bảng 3.1A: Kiểm toán các Bản ghi Giá Thiếu và Không Hợp lệ (Invalid & Missing Prices)

|    | Tiêu chí kiểm tra                |   Số lượng bản ghi |   Tỷ lệ trên tổng (%) | Ghi chú / Hành động TV5                                       |
|---:|:---------------------------------|-------------------:|----------------------:|:--------------------------------------------------------------|
|  0 | is_price_missing == True         |               1752 |                 16.98 | Bắt buộc loại bỏ khỏi tập huấn luyện hồi quy (target missing) |
|  1 | price_vnd <= 0                   |               1752 |                 16.98 | Giá bằng 0 hoặc âm; trùng khớp với is_price_missing == True   |
|  2 | price_vnd là NaN / Null          |                 16 |                  0.16 | 16 bản ghi thiếu giá hoàn toàn từ file thô                    |
|  3 | Tổng số bản ghi giá KHÔNG HỢP LỆ |               1768 |                 17.14 | Loại bỏ triệt để 1.768 bản ghi này (còn 8.548 bản ghi hợp lệ) |
