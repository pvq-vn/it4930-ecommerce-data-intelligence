# EDA - Exploratory Data Analysis (TV3)

Thư mục làm việc của Thành viên 3 (TV3) phục vụ phân tích khám phá dữ liệu sản phẩm thương mại điện tử (Laptop & Smartphone).

## Cấu trúc thư mục

```text
src/eda/
├── README.md                                  # Tài liệu tổng quan EDA
├── notebooks/                                 # Jupyter Notebooks phân tích
│   ├── 01_overview_and_distributions.ipynb    # Nhiệm vụ 1.1: Phân phối sản phẩm, sàn & thương hiệu
│   ├── 02_price_and_discount_analysis.ipynb   # Nhiệm vụ 1.2: Phân tích biến Giá & Chiết khấu
│   ├── 03_missingness_profile.ipynb           # Nhiệm vụ 1.3: Mức độ thiếu dữ liệu (Missingness Profile)
│   ├── 04_hardware_price_relationships.ipynb  # Nhiệm vụ 2: Tương quan phần cứng & Đối đầu Laptop vs Phone
│   └── 05_regression_readiness_audit.ipynb    # Nhiệm vụ 3: Đánh giá chất lượng dữ liệu cho Hồi quy
├── scripts/                                   # Các module Python dùng chung & script thực thi
│   ├── __init__.py
│   ├── eda_stats.py                           # Thư viện hàm thống kê mô tả, kiểm định giả thuyết & VIF
│   ├── eda_viz.py                             # Thiết lập phong cách đồ họa, bảng màu & trực quan hóa
│   ├── run_task_1_1.py                        # Script tự động chạy Nhiệm vụ 1.1
│   ├── run_task_1_2.py                        # Script tự động chạy Nhiệm vụ 1.2
│   ├── run_task_1_3.py                        # Script tự động chạy Nhiệm vụ 1.3
│   ├── run_task_2_1.py                        # Script tự động chạy Nhiệm vụ 2.1
│   ├── run_task_2_2.py                        # Script tự động chạy Nhiệm vụ 2.2
│   └── run_task_3.py                          # Script tự động chạy Nhiệm vụ 3
└── outputs/                                   # Thư mục lưu kết quả phân tích
    ├── figures/                               # Biểu đồ chất lượng cao định dạng PNG (dpi >= 300)
    └── tables/                                # Bảng thống kê định dạng song song CSV và Markdown
```


## Dữ liệu đầu vào

* [data/processed/products_processed.jsonl](../../data/processed/products_processed.jsonl) (10.316 bản ghi, 30 thuộc tính chuẩn hóa)

## Quy chuẩn & Hướng dẫn chi tiết

Xem toàn văn hướng dẫn nhiệm vụ, data contracts và gói bàn giao TV5 tại:
👉 **[docs/tv3/tv3.md](../../docs/tv3/tv3.md)**
