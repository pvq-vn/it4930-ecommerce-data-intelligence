# Báo cáo Phân tích Đồ thị Sản phẩm & Khoảng trống Thị trường (IT4930)

## 1. Thống kê Độc quyền vs Cạnh tranh theo Nhà bán lẻ

### Mảng Laptop

| retailer   |   total_canonical_products |   exclusive_count |   competitive_count |   exclusive_pct |   price_leader_win_rate_pct |   avg_price_premium_pct |
|:-----------|---------------------------:|------------------:|--------------------:|----------------:|----------------------------:|------------------------:|
| CellphoneS |                       2350 |              2190 |                 160 |           93.19 |                       69.38 |                   10.59 |
| FPT        |                        298 |               181 |                 117 |           60.74 |                       64.1  |                    2.64 |
| Hoàng Hà   |                         91 |                62 |                  29 |           68.13 |                       75.86 |                    0.55 |
| TGDĐ       |                        397 |               265 |                 132 |           66.75 |                       51.52 |                    2.85 |
| Viettel    |                         21 |                 9 |                  12 |           42.86 |                       66.67 |                    5.2  |

### Mảng Smartphone

| retailer   |   total_canonical_products |   exclusive_count |   competitive_count |   exclusive_pct |   price_leader_win_rate_pct |   avg_price_premium_pct |
|:-----------|---------------------------:|------------------:|--------------------:|----------------:|----------------------------:|------------------------:|
| CellphoneS |                       1090 |               951 |                 139 |           87.25 |                       47.48 |                  240.06 |
| FPT        |                        180 |                55 |                 125 |           30.56 |                       37.6  |                  219.98 |
| Hoàng Hà   |                        181 |                90 |                  91 |           49.72 |                       64.84 |                    2.22 |
| TGDĐ       |                        278 |               195 |                  83 |           70.14 |                       39.76 |                   20.21 |
| Viettel    |                        134 |                35 |                  99 |           26.12 |                       55.56 |                  278.73 |

## 2. Ma trận Jaccard Trùng lặp Danh mục

### Mảng Laptop

|            |   CellphoneS |    FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-----------|-------------:|-------:|-----------:|-------:|----------:|
| CellphoneS |       100    |   3.4  |       0.83 |   3.74 |      0.21 |
| FPT        |         3.4  | 100    |       4.01 |   9.62 |      0.95 |
| Hoàng Hà   |         0.83 |   4.01 |     100    |   3.39 |      0.9  |
| TGDĐ       |         3.74 |   9.62 |       3.39 | 100    |      1.7  |
| Viettel    |         0.21 |   0.95 |       0.9  |   1.7  |    100    |

### Mảng Smartphone

|            |   CellphoneS |    FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-----------|-------------:|-------:|-----------:|-------:|----------:|
| CellphoneS |       100    |   8.18 |       6.36 |   4.11 |      6.81 |
| FPT        |         8.18 | 100    |      19.54 |  18.04 |     26.1  |
| Hoàng Hà   |         6.36 |  19.54 |     100    |  10.34 |     18.42 |
| TGDĐ       |         4.11 |  18.04 |      10.34 | 100    |     14.13 |
| Viettel    |         6.81 |  26.1  |      18.42 |  14.13 |    100    |

## 3. Khoảng trống Thị trường (Structural Holes)

- **Điểm mù theo nhà bán lẻ (Retailer Blind Spots):** 71 phân khúc bỏ ngỏ.
- **Phân khúc nhu cầu cao ít cạnh tranh (Underserved):** 20 phân khúc.

### 3.1 Điểm mù của từng sàn (Retailer Blind Spots)

| retailer   | segment_label                  | category   | price_range_m   | top_brands    |   cpu_perf_median |   gpu_perf_median | perf_recommendation                                                   |
|:-----------|:-------------------------------|:-----------|:----------------|:--------------|------------------:|------------------:|:----------------------------------------------------------------------|
| Viettel    | Laptop 17-146M (ASUS, Lenovo)  | laptop     | 17.49-145.99M   | ASUS, Lenovo  |             45.5  |             29.1  | Cần nhập laptop có CPU quanh mức 45.5 (23.6-63.0), GPU quanh mức 29.1 |
| Viettel    | Laptop 28-46M (Lenovo, ASUS)   | laptop     | 27.89-46.29M    | Lenovo, ASUS  |             42.8  |              5.6  | Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6  |
| Hoàng Hà   | Laptop 14-43M (ASUS, Lenovo)   | laptop     | 14.19-42.99M    | ASUS, Lenovo  |             29.3  |             11.3  | Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3 |
| Viettel    | Laptop 14-43M (ASUS, Lenovo)   | laptop     | 14.19-42.99M    | ASUS, Lenovo  |             29.3  |             11.3  | Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3 |
| Viettel    | Laptop 15-45M (ASUS, MSI)      | laptop     | 14.99-44.99M    | ASUS, MSI     |             39.7  |             14.4  | Cần nhập laptop có CPU quanh mức 39.7 (31.7-50.5), GPU quanh mức 14.4 |
| Viettel    | Laptop 14-21M (ASUS, HP)       | laptop     | 14.19-21.44M    | ASUS, HP      |             31    |              4.4  | Cần nhập laptop có CPU quanh mức 31.0 (26.5-36.2), GPU quanh mức 4.4  |
| Viettel    | Laptop 7-33M (ASUS, HP)        | laptop     | 7.49-32.53M     | ASUS, HP      |             19.6  |              4.3  | Cần nhập laptop có CPU quanh mức 19.6 (14.4-26.5), GPU quanh mức 4.3  |
| Viettel    | Laptop 8-16M (ASUS, Lenovo)    | laptop     | 8.29-16.49M     | ASUS, Lenovo  |             36.2  |              4.4  | Cần nhập laptop có CPU quanh mức 36.2 (30.3-44.4), GPU quanh mức 4.4  |
| Viettel    | Laptop 23-198M (Apple, MSI)    | laptop     | 23.0-198.14M    | Apple, MSI    |             64.1  |            nan    | Cần nhập laptop có CPU quanh mức 64.1 (50.6-74.8)                     |
| Hoàng Hà   | Laptop 46-110M (Apple, Lenovo) | laptop     | 46.49-109.99M   | Apple, Lenovo |             45.75 |             10.95 | Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9 |
| Viettel    | Laptop 46-110M (Apple, Lenovo) | laptop     | 46.49-109.99M   | Apple, Lenovo |             45.75 |             10.95 | Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9 |
| FPT        | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0  |
| Hoàng Hà   | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0  |
| TGDĐ       | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0  |
| Viettel    | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0  |

### 3.2 Phân khúc thiếu cung toàn thị trường (Underserved High Demand)

| retailer   | segment_label                      | category   | price_range_m   | top_brands      |   cpu_perf_median |   gpu_perf_median | perf_recommendation                                                   |
|:-----------|:-----------------------------------|:-----------|:----------------|:----------------|------------------:|------------------:|:----------------------------------------------------------------------|
| ALL_MARKET | Laptop 28-46M (Lenovo, ASUS)       | laptop     | 27.89-46.29M    | Lenovo, ASUS    |             42.8  |               5.6 | Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6  |
| ALL_MARKET | Laptop 15-45M (ASUS, MSI)          | laptop     | 14.99-44.99M    | ASUS, MSI       |             39.7  |              14.4 | Cần nhập laptop có CPU quanh mức 39.7 (31.7-50.5), GPU quanh mức 14.4 |
| ALL_MARKET | Laptop 25-32M (ASUS, HP)           | laptop     | 25.24-31.99M    | ASUS, HP        |             42.9  |               5.7 | Cần nhập laptop có CPU quanh mức 42.9 (39.7-49.7), GPU quanh mức 5.7  |
| ALL_MARKET | Laptop 16-22M (ASUS, Lenovo)       | laptop     | 15.79-21.99M    | ASUS, Lenovo    |             39.05 |               4.4 | Cần nhập laptop có CPU quanh mức 39.0 (34.9-49.7), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 14-21M (ASUS, HP)           | laptop     | 14.19-21.44M    | ASUS, HP        |             31    |               4.4 | Cần nhập laptop có CPU quanh mức 31.0 (26.5-36.2), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 7-33M (ASUS, HP)            | laptop     | 7.49-32.53M     | ASUS, HP        |             19.6  |               4.3 | Cần nhập laptop có CPU quanh mức 19.6 (14.4-26.5), GPU quanh mức 4.3  |
| ALL_MARKET | Laptop 19-29M (ASUS, Lenovo)       | laptop     | 19.19-28.99M    | ASUS, Lenovo    |             40.95 |               4.4 | Cần nhập laptop có CPU quanh mức 41.0 (37.2-49.7), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 23-198M (Apple, MSI)        | laptop     | 23.0-198.14M    | Apple, MSI      |             64.1  |             nan   | Cần nhập laptop có CPU quanh mức 64.1 (50.6-74.8)                     |
| ALL_MARKET | Laptop 19-26M (HP, Lenovo)         | laptop     | 18.99-25.99M    | HP, Lenovo      |             37.2  |               5.6 | Cần nhập laptop có CPU quanh mức 37.2 (31.7-42.1), GPU quanh mức 5.6  |
| ALL_MARKET | Laptop 25-34M (Lenovo, HP)         | laptop     | 24.99-34.49M    | Lenovo, HP      |             36.2  |               5.6 | Cần nhập laptop có CPU quanh mức 36.2 (31.0-39.8), GPU quanh mức 5.6  |
| ALL_MARKET | Laptop 19-27M (Dell, HP)           | laptop     | 19.49-26.99M    | Dell, HP        |             31    |               4.4 | Cần nhập laptop có CPU quanh mức 31.0 (26.2-36.2), GPU quanh mức 4.4  |
| ALL_MARKET | Smartphone 8-22M (Xiaomi, OPPO)    | smartphone | 8.49-21.99M     | Xiaomi, OPPO    |           3581    |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 3581 (2814-5284)  |
| ALL_MARKET | Smartphone 3-5M (Xiaomi, Samsung)  | smartphone | 2.99-5.49M      | Xiaomi, Samsung |           1817    |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 1817 (1625-2155)  |
| ALL_MARKET | Smartphone 6-12M (Xiaomi, Samsung) | smartphone | 5.5-11.99M      | Xiaomi, Samsung |           2915.5  |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 2916 (2500-4234)  |
| ALL_MARKET | Smartphone 4-8M (OPPO, Vivo)       | smartphone | 4.49-7.59M      | OPPO, Vivo      |           1337.5  |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 1338 (1155-1541)  |


### 3.3 Khuyến nghị Cấu hình Nhập hàng để Lấp Điểm Mù (Hardware Procurement Targets)

#### Nhà bán lẻ: CellphoneS
- **Smartphone 9-14M (Realme)** (8.79-14.49M): Chưa có dữ liệu benchmark cho phân khúc này
- **Smartphone 0-0M (Samsung)** (0.39-0.39M): Cần nhập smartphone có điểm CPU benchmark quanh mức 8657 (8657-8657)
- **Smartphone 4-5M (Motorola)** (3.59-4.69M): Chưa có dữ liệu benchmark cho phân khúc này

#### Nhà bán lẻ: FPT
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5
- **Laptop 39-62M (Microsoft, HP)** (39.49-61.99M): Cần nhập laptop có CPU quanh mức 22.4 (20.7-22.9)
- **Laptop 14-19M (HP, Dell)** (13.99-19.39M): Cần nhập laptop có CPU quanh mức 36.2 (36.2-38.4), GPU quanh mức 7.9

#### Nhà bán lẻ: Hoàng Hà
- **Laptop 14-43M (ASUS, Lenovo)** (14.19-42.99M): Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3
- **Laptop 46-110M (Apple, Lenovo)** (46.49-109.99M): Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5

#### Nhà bán lẻ: TGDĐ
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-31.0), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5
- **Laptop 39-62M (Microsoft, HP)** (39.49-61.99M): Cần nhập laptop có CPU quanh mức 22.4 (20.7-22.9)
- **Laptop 14-19M (HP, Dell)** (13.99-19.39M): Cần nhập laptop có CPU quanh mức 36.2 (36.2-38.4), GPU quanh mức 7.9

#### Nhà bán lẻ: Viettel
- **Laptop 17-146M (ASUS, Lenovo)** (17.49-145.99M): Cần nhập laptop có CPU quanh mức 45.5 (23.6-63.0), GPU quanh mức 29.1
- **Laptop 28-46M (Lenovo, ASUS)** (27.89-46.29M): Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6
- **Laptop 14-43M (ASUS, Lenovo)** (14.19-42.99M): Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3
- **Laptop 15-45M (ASUS, MSI)** (14.99-44.99M): Cần nhập laptop có CPU quanh mức 39.7 (31.7-50.5), GPU quanh mức 14.4
- **Laptop 14-21M (ASUS, HP)** (14.19-21.44M): Cần nhập laptop có CPU quanh mức 31.0 (26.5-36.2), GPU quanh mức 4.4


## 4. Phân bố Cộng đồng Louvain theo Nhà bán lẻ

| segment_label                  |   CellphoneS |   FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-------------------------------|-------------:|------:|-----------:|-------:|----------:|
| Laptop 14-19M (HP, Dell)       |            9 |     0 |          0 |      0 |         0 |
| Laptop 14-21M (ASUS, HP)       |          166 |     8 |          4 |      6 |         0 |
| Laptop 14-43M (ASUS, Lenovo)   |          212 |     2 |          0 |      3 |         0 |
| Laptop 15-29M (Dell, ASUS)     |           22 |     0 |          0 |      0 |         0 |
| Laptop 15-45M (ASUS, MSI)      |          186 |    13 |          7 |      9 |         0 |
| Laptop 16-22M (ASUS, Lenovo)   |          145 |    23 |         10 |     21 |         5 |
| Laptop 17-146M (ASUS, Lenovo)  |          408 |    69 |          6 |     30 |         0 |
| Laptop 17-19M (ASUS, Acer)     |            5 |     0 |          0 |      0 |         0 |
| Laptop 172-177M (MSI)          |            3 |     0 |          0 |      0 |         0 |
| Laptop 19-26M (HP, Lenovo)     |           80 |    11 |          2 |     30 |         5 |
| Laptop 19-27M (Dell, HP)       |           55 |     9 |          1 |      8 |         1 |
| Laptop 19-29M (ASUS, Lenovo)   |          108 |    26 |         12 |     36 |         2 |
| Laptop 2-2M (HP, Dell)         |            0 |     0 |          3 |      0 |         0 |
| Laptop 23-198M (Apple, MSI)    |           78 |    31 |         32 |     19 |         0 |
| Laptop 25-32M (ASUS, HP)       |          100 |    46 |          4 |     67 |         7 |
| Laptop 25-34M (Lenovo, HP)     |           53 |    10 |          2 |     33 |         1 |
| Laptop 28-46M (Lenovo, ASUS)   |          119 |    31 |          1 |     86 |         0 |
| Laptop 38-42M (Dell, ASUS)     |            5 |     0 |          0 |      0 |         0 |
| Laptop 39-62M (Microsoft, HP)  |            9 |     0 |          0 |      0 |         0 |
| Laptop 46-110M (Apple, Lenovo) |           94 |    12 |          0 |     42 |         0 |