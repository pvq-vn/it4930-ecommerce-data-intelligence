# Báo cáo Phân tích Đồ thị Sản phẩm & Khoảng trống Thị trường (IT4930)

## 1. Thống kê Độc quyền vs Cạnh tranh theo Nhà bán lẻ

### Mảng Laptop

| retailer   |   total_canonical_products |   exclusive_count |   competitive_count |   exclusive_pct |   price_leader_win_rate_pct |   avg_price_premium_pct |   median_price_premium_pct |   price_premium_pairs_used |   price_premium_pairs_excluded |
|:-----------|---------------------------:|------------------:|--------------------:|----------------:|----------------------------:|------------------------:|---------------------------:|---------------------------:|-------------------------------:|
| CellphoneS |                       2350 |              2190 |                 160 |           93.19 |                       69.38 |                    1.8  |                          0 |                        159 |                              1 |
| FPT        |                        298 |               181 |                 117 |           60.74 |                       64.1  |                    2.64 |                          0 |                        117 |                              0 |
| Hoàng Hà   |                         87 |                58 |                  29 |           66.67 |                       75.86 |                    0.55 |                          0 |                         29 |                              0 |
| TGDĐ       |                        397 |               265 |                 132 |           66.75 |                       51.52 |                    2.85 |                          0 |                        132 |                              0 |
| Viettel    |                         21 |                 9 |                  12 |           42.86 |                       66.67 |                    5.2  |                          0 |                         12 |                              0 |

### Mảng Smartphone

| retailer   |   total_canonical_products |   exclusive_count |   competitive_count |   exclusive_pct |   price_leader_win_rate_pct |   avg_price_premium_pct |   median_price_premium_pct |   price_premium_pairs_used |   price_premium_pairs_excluded |
|:-----------|---------------------------:|------------------:|--------------------:|----------------:|----------------------------:|------------------------:|---------------------------:|---------------------------:|-------------------------------:|
| CellphoneS |                       1039 |               905 |                 134 |           87.1  |                       45.52 |                    2.23 |                       0.51 |                        128 |                              6 |
| FPT        |                        167 |                46 |                 121 |           27.54 |                       38.02 |                    4.56 |                       1.56 |                        118 |                              3 |
| Hoàng Hà   |                        146 |                56 |                  90 |           38.36 |                       64.44 |                    2.25 |                       0    |                         90 |                              0 |
| TGDĐ       |                        260 |               177 |                  83 |           68.08 |                       39.76 |                    2.76 |                       1.16 |                         82 |                              1 |
| Viettel    |                        128 |                31 |                  97 |           24.22 |                       55.67 |                    2.37 |                       0    |                         94 |                              3 |

## 2. Ma trận Jaccard Trùng lặp Danh mục

### Mảng Laptop

|            |   CellphoneS |    FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-----------|-------------:|-------:|-----------:|-------:|----------:|
| CellphoneS |       100    |   3.4  |       0.83 |   3.74 |      0.21 |
| FPT        |         3.4  | 100    |       4.05 |   9.62 |      0.95 |
| Hoàng Hà   |         0.83 |   4.05 |     100    |   3.42 |      0.93 |
| TGDĐ       |         3.74 |   9.62 |       3.42 | 100    |      1.7  |
| Viettel    |         0.21 |   0.95 |       0.93 |   1.7  |    100    |

### Mảng Smartphone

|            |   CellphoneS |    FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-----------|-------------:|-------:|-----------:|-------:|----------:|
| CellphoneS |       100    |   8.26 |       6.76 |   4.34 |      6.97 |
| FPT        |         8.26 | 100    |      23.23 |  19.61 |     27.16 |
| Hoàng Hà   |         6.76 |  23.23 |     100    |  11.85 |     21.78 |
| TGDĐ       |         4.34 |  19.61 |      11.85 | 100    |     15.13 |
| Viettel    |         6.97 |  27.16 |      21.78 |  15.13 |    100    |

## 3. Khoảng trống Thị trường (Structural Holes)

- **Điểm mù theo nhà bán lẻ (Retailer Blind Spots):** 68 phân khúc bỏ ngỏ.
- **Phân khúc nhu cầu cao ít cạnh tranh (Underserved):** 22 phân khúc.

### 3.1 Điểm mù của từng sàn (Retailer Blind Spots)

| retailer   | segment_label                  | category   | price_range_m   | top_brands    |   cpu_perf_median |   gpu_perf_median | perf_recommendation                                                   |
|:-----------|:-------------------------------|:-----------|:----------------|:--------------|------------------:|------------------:|:----------------------------------------------------------------------|
| Viettel    | Laptop 17-146M (ASUS, Lenovo)  | laptop     | 17.49-145.99M   | ASUS, Lenovo  |             45.5  |             29.1  | Cần nhập laptop có CPU quanh mức 45.5 (25.5-63.0), GPU quanh mức 29.1 |
| Viettel    | Laptop 8-17M (Lenovo, ASUS)    | laptop     | 8.29-16.52M     | Lenovo, ASUS  |             35    |              4.4  | Cần nhập laptop có CPU quanh mức 35.0 (27.0-42.6), GPU quanh mức 4.4  |
| Viettel    | Laptop 28-46M (Lenovo, ASUS)   | laptop     | 27.89-46.29M    | Lenovo, ASUS  |             42.8  |              5.6  | Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6  |
| Hoàng Hà   | Laptop 14-43M (ASUS, Lenovo)   | laptop     | 14.19-42.99M    | ASUS, Lenovo  |             29.3  |             11.3  | Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3 |
| Viettel    | Laptop 14-43M (ASUS, Lenovo)   | laptop     | 14.19-42.99M    | ASUS, Lenovo  |             29.3  |             11.3  | Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3 |
| Viettel    | Laptop 15-45M (ASUS, MSI)      | laptop     | 14.99-44.99M    | ASUS, MSI     |             39.7  |             14.4  | Cần nhập laptop có CPU quanh mức 39.7 (31.0-50.5), GPU quanh mức 14.4 |
| Viettel    | Laptop 7-33M (ASUS, HP)        | laptop     | 7.49-32.53M     | ASUS, HP      |             19.6  |              4.3  | Cần nhập laptop có CPU quanh mức 19.6 (14.4-26.5), GPU quanh mức 4.3  |
| Viettel    | Laptop 23-198M (Apple, MSI)    | laptop     | 23.0-198.14M    | Apple, MSI    |             64.1  |            nan    | Cần nhập laptop có CPU quanh mức 64.1 (50.6-74.8)                     |
| Hoàng Hà   | Laptop 46-110M (Apple, Lenovo) | laptop     | 46.49-109.99M   | Apple, Lenovo |             45.75 |             10.95 | Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9 |
| Viettel    | Laptop 46-110M (Apple, Lenovo) | laptop     | 46.49-109.99M   | Apple, Lenovo |             45.75 |             10.95 | Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9 |
| FPT        | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0  |
| Hoàng Hà   | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0  |
| TGDĐ       | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0  |
| Viettel    | Laptop 6-17M (ASUS, HP)        | laptop     | 5.99-16.9M      | ASUS, HP      |             27.2  |              3    | Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0  |
| FPT        | Laptop 15-29M (Dell, ASUS)     | laptop     | 14.99-29.19M    | Dell, ASUS    |             31    |              4.2  | Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2  |

### 3.2 Phân khúc thiếu cung toàn thị trường (Underserved High Demand)

| retailer   | segment_label                      | category   | price_range_m   | top_brands      |   cpu_perf_median |   gpu_perf_median | perf_recommendation                                                   |
|:-----------|:-----------------------------------|:-----------|:----------------|:----------------|------------------:|------------------:|:----------------------------------------------------------------------|
| ALL_MARKET | Laptop 28-46M (Lenovo, ASUS)       | laptop     | 27.89-46.29M    | Lenovo, ASUS    |              42.8 |               5.6 | Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6  |
| ALL_MARKET | Laptop 14-43M (ASUS, Lenovo)       | laptop     | 14.19-42.99M    | ASUS, Lenovo    |              29.3 |              11.3 | Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3 |
| ALL_MARKET | Laptop 15-25M (ASUS, HP)           | laptop     | 15.49-24.99M    | ASUS, HP        |              31   |               4.4 | Cần nhập laptop có CPU quanh mức 31.0 (26.2-36.2), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 15-45M (ASUS, MSI)          | laptop     | 14.99-44.99M    | ASUS, MSI       |              39.7 |              14.4 | Cần nhập laptop có CPU quanh mức 39.7 (31.0-50.5), GPU quanh mức 14.4 |
| ALL_MARKET | Laptop 25-32M (ASUS, HP)           | laptop     | 24.99-31.99M    | ASUS, HP        |              42.9 |               5.7 | Cần nhập laptop có CPU quanh mức 42.9 (39.7-49.7), GPU quanh mức 5.7  |
| ALL_MARKET | Laptop 15-21M (ASUS, Lenovo)       | laptop     | 14.99-20.99M    | ASUS, Lenovo    |              39.3 |               4.4 | Cần nhập laptop có CPU quanh mức 39.3 (35.7-49.7), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 7-33M (ASUS, HP)            | laptop     | 7.49-32.53M     | ASUS, HP        |              19.6 |               4.3 | Cần nhập laptop có CPU quanh mức 19.6 (14.4-26.5), GPU quanh mức 4.3  |
| ALL_MARKET | Laptop 19-29M (Lenovo, ASUS)       | laptop     | 19.19-28.99M    | Lenovo, ASUS    |              40.9 |               4.4 | Cần nhập laptop có CPU quanh mức 40.9 (36.2-49.7), GPU quanh mức 4.4  |
| ALL_MARKET | Laptop 23-198M (Apple, MSI)        | laptop     | 23.0-198.14M    | Apple, MSI      |              64.1 |             nan   | Cần nhập laptop có CPU quanh mức 64.1 (50.6-74.8)                     |
| ALL_MARKET | Laptop 19-26M (HP, Lenovo)         | laptop     | 18.99-25.99M    | HP, Lenovo      |              37.2 |               5.6 | Cần nhập laptop có CPU quanh mức 37.2 (31.7-42.1), GPU quanh mức 5.6  |
| ALL_MARKET | Laptop 24-34M (Lenovo, HP)         | laptop     | 23.99-34.49M    | Lenovo, HP      |              36.2 |               5.6 | Cần nhập laptop có CPU quanh mức 36.2 (31.0-40.1), GPU quanh mức 5.6  |
| ALL_MARKET | Smartphone 8-22M (Xiaomi, OPPO)    | smartphone | 8.49-21.99M     | Xiaomi, OPPO    |            3581   |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 3581 (2558-5284)  |
| ALL_MARKET | Smartphone 3-5M (Samsung, Xiaomi)  | smartphone | 2.99-5.39M      | Samsung, Xiaomi |            1781   |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 1781 (1583-2048)  |
| ALL_MARKET | Smartphone 6-12M (Xiaomi, Samsung) | smartphone | 5.5-11.99M      | Xiaomi, Samsung |            2915.5 |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 2916 (2500-4234)  |
| ALL_MARKET | Smartphone 5-7M (Xiaomi, OPPO)     | smartphone | 5.19-6.69M      | Xiaomi, OPPO    |            1750.5 |             nan   | Cần nhập smartphone có điểm CPU benchmark quanh mức 1750 (1524-2155)  |


### 3.3 Khuyến nghị Cấu hình Nhập hàng để Lấp Điểm Mù (Hardware Procurement Targets)

#### Nhà bán lẻ: CellphoneS
- **Smartphone 9-14M (Realme)** (8.79-14.49M): Chưa có dữ liệu benchmark cho phân khúc này
- **Smartphone 4-5M (Motorola)** (3.59-4.69M): Chưa có dữ liệu benchmark cho phân khúc này

#### Nhà bán lẻ: FPT
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5
- **Laptop 39-62M (Microsoft, HP)** (39.49-61.99M): Cần nhập laptop có CPU quanh mức 22.4 (20.7-22.9)
- **Laptop 14-19M (HP, Dell)** (13.99-19.39M): Cần nhập laptop có CPU quanh mức 36.2 (36.2-38.4), GPU quanh mức 7.9

#### Nhà bán lẻ: Hoàng Hà
- **Laptop 14-43M (ASUS, Lenovo)** (14.19-42.99M): Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3
- **Laptop 46-110M (Apple, Lenovo)** (46.49-109.99M): Cần nhập laptop có CPU quanh mức 45.8 (36.4-54.9), GPU quanh mức 10.9
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5

#### Nhà bán lẻ: TGDĐ
- **Laptop 6-17M (ASUS, HP)** (5.99-16.9M): Cần nhập laptop có CPU quanh mức 27.2 (26.1-30.5), GPU quanh mức 3.0
- **Laptop 15-29M (Dell, ASUS)** (14.99-29.19M): Cần nhập laptop có CPU quanh mức 31.0 (31.0-33.8), GPU quanh mức 4.2
- **Laptop 6-10M (ASUS, HP)** (6.49-9.99M): Cần nhập laptop có CPU quanh mức 8.3 (8.3-10.5), GPU quanh mức 0.5
- **Laptop 39-62M (Microsoft, HP)** (39.49-61.99M): Cần nhập laptop có CPU quanh mức 22.4 (20.7-22.9)
- **Laptop 14-19M (HP, Dell)** (13.99-19.39M): Cần nhập laptop có CPU quanh mức 36.2 (36.2-38.4), GPU quanh mức 7.9

#### Nhà bán lẻ: Viettel
- **Laptop 17-146M (ASUS, Lenovo)** (17.49-145.99M): Cần nhập laptop có CPU quanh mức 45.5 (25.5-63.0), GPU quanh mức 29.1
- **Laptop 8-17M (Lenovo, ASUS)** (8.29-16.52M): Cần nhập laptop có CPU quanh mức 35.0 (27.0-42.6), GPU quanh mức 4.4
- **Laptop 28-46M (Lenovo, ASUS)** (27.89-46.29M): Cần nhập laptop có CPU quanh mức 42.8 (31.0-51.3), GPU quanh mức 5.6
- **Laptop 14-43M (ASUS, Lenovo)** (14.19-42.99M): Cần nhập laptop có CPU quanh mức 29.3 (18.4-46.3), GPU quanh mức 11.3
- **Laptop 15-45M (ASUS, MSI)** (14.99-44.99M): Cần nhập laptop có CPU quanh mức 39.7 (31.0-50.5), GPU quanh mức 14.4


## 4. Phân bố Cộng đồng Louvain theo Nhà bán lẻ

| segment_label                  |   CellphoneS |   FPT |   Hoàng Hà |   TGDĐ |   Viettel |
|:-------------------------------|-------------:|------:|-----------:|-------:|----------:|
| Laptop 14-19M (HP, Dell)       |            9 |     0 |          0 |      0 |         0 |
| Laptop 14-43M (ASUS, Lenovo)   |          208 |     2 |          0 |      3 |         0 |
| Laptop 15-21M (ASUS, Lenovo)   |          145 |    18 |         10 |     19 |         5 |
| Laptop 15-25M (ASUS, HP)       |          177 |    17 |          4 |     15 |         1 |
| Laptop 15-29M (Dell, ASUS)     |           22 |     0 |          0 |      0 |         0 |
| Laptop 15-45M (ASUS, MSI)      |          190 |    13 |          7 |      9 |         0 |
| Laptop 17-146M (ASUS, Lenovo)  |          408 |    69 |          6 |     30 |         0 |
| Laptop 17-19M (ASUS, Acer)     |            5 |     0 |          0 |      0 |         0 |
| Laptop 172-177M (MSI)          |            3 |     0 |          0 |      0 |         0 |
| Laptop 19-26M (HP, Lenovo)     |           85 |    13 |          2 |     30 |         5 |
| Laptop 19-29M (Lenovo, ASUS)   |          113 |    28 |         12 |     33 |         2 |
| Laptop 23-198M (Apple, MSI)    |           78 |    31 |         32 |     19 |         0 |
| Laptop 24-34M (Lenovo, HP)     |           56 |    11 |          2 |     35 |         1 |
| Laptop 25-32M (ASUS, HP)       |          103 |    46 |          4 |     69 |         7 |
| Laptop 28-46M (Lenovo, ASUS)   |          119 |    31 |          1 |     86 |         0 |
| Laptop 38-42M (Dell, ASUS)     |            5 |     0 |          0 |      0 |         0 |
| Laptop 39-62M (Microsoft, HP)  |            9 |     0 |          0 |      0 |         0 |
| Laptop 46-110M (Apple, Lenovo) |           94 |    12 |          0 |     42 |         0 |
| Laptop 6-10M (ASUS, HP)        |           15 |     0 |          0 |      0 |         0 |
| Laptop 6-17M (ASUS, HP)        |           88 |     0 |          0 |      0 |         0 |