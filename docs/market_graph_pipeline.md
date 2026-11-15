# Tài liệu Kỹ thuật Pipeline Đồ thị Thị trường & Phân tích Khoảng trống (Market Graph)

Tài liệu này mô tả chi tiết kiến trúc, quy trình 4 bước (Step 1 đến Step 4) và ý nghĩa của các file dữ liệu đầu ra trong module `src/market_graph/`.

---

## 1. Tổng quan Kiến trúc Pipeline

Pipeline được thiết kế nhằm chuẩn hóa dữ liệu thương mại điện tử đa sàn (TGDĐ, FPT Shop, CellphoneS, Viettel Store, Hoàng Hà Mobile), giải quyết bài toán đồng nhất thực thể (Entity Resolution), mô hình hóa thị trường dưới dạng Đồ thị Hai phía (Bipartite Graph), phân khúc thị trường tự động bằng thuật toán Louvain và phát hiện khoảng trống cạnh tranh (Structural Holes).

### 1.1 Sơ đồ Luồng dữ liệu

```
[Raw Crawled Data] (data/TV2_Data_Handoff/processed/products_processed.jsonl)
       │
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 1: Pre-filtering & LLM Spec Cleaning (llm_clean.py)               │
│ - Lọc bỏ giá <= 0 / missing                                            │
│ - DeepSeek JSON extraction: brand, model_clean, cpu_model, specs       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ products_llm_cleaned.jsonl
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 1.5: Benchmark Enrichment (benchmark_extract.py,                   │
│           laptop_benchmark_match.py, smartphone_benchmark_match.py)     │
│ - Parse Notebookcheck HTML → CPU/GPU benchmark CSVs                     │
│ - Match listing × benchmark: exact → alias → variant → prefix          │
│ - Outputs: laptop_benchmarks.jsonl, smartphone_benchmarks.jsonl        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 2: Entity Resolution & Bipartite Market Graph (bipartite_graph.py)│
│ - Base hash (7 phần cứng: brand, model, cpu, ram, storage, gpu, screen)│
│ - Bipartite Graph: Retailers <──> Canonical Products                   │
│ - Phân loại Exclusivity vs Competitive & Ma trận Jaccard Similarity    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ canonical_products.csv
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 3: Product Similarity Graph & Louvain Segmentation                 │
│         (louvain_segments.py + perf_scores.py)                          │
│ - enrich_perf_scores(): gắn CPU/GPU benchmark score, impute, normalize │
│ - Graph P-P cross-brand, CPU/GPU score chênh <= 15%, giá chênh <= 20%  │
│ - Phân cụm cộng đồng Louvain (Community Detection theo Modularity)     │
│ - Auto-tuning resolution parameter                                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ canonical_products_segmented.csv
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 4: Structural Holes & Visual Reporting (gaps_and_reports.py)       │
│ - Ma trận Retailer × Community & Phát hiện Retailer Blind Spots         │
│ - Báo cáo Underserved Segments (Cầu cao - Cung hẹp)                    │
│ - Xuất PyVis HTML, Seaborn Heatmaps & Báo cáo Markdown tổng hợp       │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Module Map

| Module | Vai trò | File chính |
|---|---|---|
| `llm_clean.py` | Step 1 — Chuẩn hóa thông số bằng LLM | DeepSeek API + Pydantic schema |
| `benchmark_extract.py` | Step 1.5 — Parse HTML benchmark | Notebookcheck CPU/GPU/Phone tables |
| `laptop_benchmark_match.py` | Step 1.5 — Match laptop listings | Tiered CPU/GPU matching |
| `smartphone_benchmark_match.py` | Step 1.5 — Match smartphone listings | Phone CPU matching |
| `bipartite_graph.py` | Step 2 — Entity Resolution + Bipartite Graph | SHA256 hashing, price clustering |
| `perf_scores.py` | Step 3 helper — Performance score enrichment | Score aggregation, imputation, normalization |
| `louvain_segments.py` | Step 3 — Product similarity graph + Louvain | Edge building, community detection |
| `gaps_and_reports.py` | Step 4 — Structural holes + visualization | Heatmaps, PyVis, Markdown report |
| `cli.py` | CLI entry point | `python -m src.market_graph.cli` |
| `__init__.py` | Package marker | — |

---

## 2. Chi tiết Từng Bước Thực Thi (Step-by-Step)

### Step 1: Chuẩn hóa Thông số Kỹ thuật bằng LLM (`llm_clean.py`)

- **Mục tiêu**: Khắc phục tình trạng tiêu đề sản phẩm bị phân mảnh, chứa rác quảng cáo ("Chính hãng", "VN/A", "Thu cũ đổi mới") và thiếu thông số phần cứng thống nhất.
- **Cơ chế xử lý**:
  1. **Lọc sạch dữ liệu giá**: Sử dụng hàm `load_valid_price_rows()` loại bỏ các listing có `price_vnd` bị thiếu, `None`, hoặc `<= 0`.
  2. **Deduplicate tối ưu chi phí LLM**: Gom cụm các sản phẩm có cùng `(product_name, raw_specs, brand_norm, category)` thành các key duy nhất bằng SHA256 hash.
  3. **Trích xuất thông minh (DeepSeek API)**: Áp dụng Pydantic Schema `CleanedSpecBatch` để trích xuất có cấu trúc:
     - `brand`: Tên hãng chuẩn hóa (qua `BRAND_CANON_MAP` với 50+ entries).
     - `model_clean`: Tên dòng máy sạch để gom nhóm (vd: *"MacBook Air M3 13 inch"*, *"Galaxy S24 Ultra"*).
     - `cpu_model`: Định danh vi xử lý (vd: *"Apple M3"*, *"Core i5-13420H"*, *"Snapdragon 8 Gen 3"*).
     - `ram_gb`, `storage_gb`, `gpu_model`, `screen_size_inch`.
     - `category_clean`: Phân nhóm nghiêm ngặt thành `laptop`, `smartphone`, và loại bỏ `other` (phụ kiện, iPad, tablet, PC AIO).
  4. **Cơ chế Cache**: Ghi tuần tự vào file `llm_spec_cache.jsonl` giúp chạy lặp lại tức thì không tốn API key.
  5. **Retry logic**: Exponential backoff (2s × 2^attempt), tối đa 4 lần thử cho mỗi batch.

---

### Step 1.5: Notebookcheck Benchmark Enrichment

#### 1.5a. Trích xuất Benchmark (`benchmark_extract.py`)

- **Mục tiêu**: Parse các snapshot HTML từ Notebookcheck thành bảng benchmark CSV có cấu trúc.
- **Dữ liệu nguồn**: snapshot HTML trong `data/market_graph/benchmarks/`:
  - `notebookcheck_cpu.html` — CPU laptop (Perf. Rating + 16 benchmark scores)
  - `notebookcheck_gpu.html` — GPU laptop (Perf. Rating + 4 × 3DMark scores)
  - `notebookcheck_cpu_phone.html` — CPU smartphone (Geekbench 2/3/4/5, PassMark, SunSpider)
- **Xử lý parser**:
  - `clean_text()` chuẩn hóa Unicode NFKC, thay thế Unicode dashes, loại bỏ ®/™.
  - `parse_perf_rating()`: Parse format `~39.5 94%` → `(rating=39.5, is_approx=True, coverage=94.0)`.
  - `parse_score()`: Parse format `3430.5 n2` → `(score=3430.5, samples=2, is_approx=False)`.
  - Tự động sinh `match_key` chuẩn hóa cho mỗi row (dùng `cpu_match_key()`, `gpu_match_key()`, `phone_cpu_match_keys()`).

**Chạy**: `python -m src.market_graph.benchmark_extract`

#### 1.5b. Match Laptop Listings (`laptop_benchmark_match.py`)

- **Chiến lược match CPU** (theo thứ tự ưu tiên):
  1. **Exact match** (confidence: high): Tên CPU chuẩn hóa khớp chính xác.
  2. **Apple GPU-core match** (confidence: high): Phân biệt Apple M-series variants bằng số GPU core (vd: M4 + 10-core GPU → M4 10-core).
  3. **Apple family single** (confidence: medium): Family chỉ có 1 variant → dùng luôn.
  4. **Apple family best coverage** (confidence: low): Chọn variant có `perf_rating_coverage_pct` cao nhất.
  5. Các tên CPU generic (`Core i5`, `Ryzen AI`, `Intel AI Boost NPU`...) bị **bỏ qua** để tránh false match.

- **Chiến lược match GPU** (theo thứ tự ưu tiên):
  1. **Exact match** (confidence: high).
  2. **Alias mapping**: `Intel Arc 130v` → `Intel Arc Graphics 130V`, `RTX 3050` → `RTX 3050 6GB`.
  3. **Integrated GPU resolution** (`_choose_integrated_gpu()`): Tra bảng theo CPU generation:
     - `Intel Iris Xe` + CPU i7/i9 → 96EUs; + CPU i5 → 80EUs.
     - `Intel Arc Graphics` + CPU Ultra V-series → 130V/140V.
     - `Intel UHD Graphics` + CPU gen khác nhau → ánh xạ theo bảng.
  4. **Unique prefix match** (confidence: medium): Nếu key là prefix duy nhất trong index.
  5. Apple GPU: **Bỏ qua** (Notebookcheck không có Perf. Rating cho Apple GPU).

**Chạy**: `python -m src.market_graph.laptop_benchmark_match`

#### 1.5c. Match Smartphone Listings (`smartphone_benchmark_match.py`)

- **Chiến lược match**:
  1. **Exact match** trên main key.
  2. **Parenthetical alias**: Thử tên trong ngoặc của benchmark entry.
  3. **Product alias**: Thử aliases sinh ra từ tên sản phẩm.
  4. **Variant base** (confidence: low): Bỏ hậu tố `Ultimate`, `Ultra`, `Energy`, `AIE`, `+` để khớp model gốc.
  5. **Unique prefix match** (confidence: medium).

- **Cơ chế Chuẩn hóa & Quy đổi Điểm hiệu năng**: Snapshot `notebookcheck_cpu_phone.html` không có cột `Perf. Rating`. Bộ trích xuất ưu tiên dùng **Geekbench 5.5 Multi-Core** (249 models); khi khuyết Geekbench 5, tự động fallback sang **Geekbench 4.4 Multi-Core** quy đổi về thang Geekbench 5 theo hệ số chuẩn hóa tuyến tính $0.2475$ (đạt tương quan $r = 0.966$ với Geekbench 5, thêm 76 models). Điểm PassMark thô (thang đo lệch từ 800 tới 750.000) được loại bỏ khỏi `benchmark_score` để tránh phá vỡ phép đo khoảng cách tương đối trong đồ thị. Tổng cộng bao phủ **325 / 549** vi xử lý điện thoại trên một trục điểm đồng nhất (~500 - 6.000 điểm).

**Chạy**: `python -m src.market_graph.cli step1_5` (hoặc chạy từng script riêng: `python -m src.market_graph.smartphone_benchmark_match`).

---

### Step 2: Entity Resolution & Đồ thị Hai phía Bipartite (`bipartite_graph.py`)

- **Mục tiêu**: Định danh một mẫu máy bán trên nhiều sàn thành một thực thể duy nhất (**Canonical Product**) và dựng cấu trúc cạnh tranh đa kênh.
- **Cơ chế xử lý**:
  1. **Impute Unknown Specs** (`_impute_unknown_specs()`): Điền khuyết `cpu_model`, RAM (`ram_gb`), bộ nhớ trong/ổ cứng (`storage_gb`), GPU (`gpu_model`), và kích thước màn hình (`screen_size_inch`) cho các listing bị thiếu thông tin nếu cùng dòng máy và có mức giá tương đồng ($\le 10\%$) với một cấu hình đã biết duy nhất. **Ràng buộc tương thích nghiêm ngặt**: Chỉ xét các bản ghi ứng viên không xung đột với các trường phần cứng đã có sẵn của listing (ví dụ: máy đã biết RAM 16GB sẽ không bị điền nhầm CPU của bản ghi RAM 8GB; máy có GPU rời không bị điền thông số của bản dùng iGPU).
  2. **Base Hash Identification**: Đưa đầy đủ 7 trường phần cứng vào chuỗi hash:
     $$\text{BaseHash} = \text{SHA256}(\text{brand} \parallel \text{model\_clean} \parallel \text{cpu\_model} \parallel \text{ram\_gb} \parallel \text{storage\_gb} \parallel \text{gpu\_model} \parallel \text{screen\_size\_inch})[:16]$$
     Nhờ đó, các biến thể GPU rời (như *RTX 2050* vs *RTX 4050*) hoặc kích thước màn hình (như MacBook Air *13.6 inch* vs *15.3 inch*) được phân tách chính xác thành các thực thể độc lập.
  3. **Phân tách cụm giá linh hoạt**:
     - **Khi có thông số phần cứng (RAM, Storage, GPU, hoặc Screen Size)**: Không cắt theo giá; các listing cùng cấu hình dù giảm giá sâu ($> 20\%$) vẫn được gom trọn vẹn vào cùng một sản phẩm chuẩn duy nhất.
     - **Khi thiếu toàn bộ thông số phần cứng cụ thể**: Thuật toán sắp xếp giá tăng dần và ngắt thành các cluster con độc lập nếu $\frac{\text{Price}_{\max} - \text{Price}_{\min}}{\text{Price}_{\min}} > 20\%$ (`max_spread`).
  4. **Xây dựng NetworkX Bipartite Graph**:
     - Tập đỉnh $U$ (bipartite=0): 5 Nhà bán lẻ (`retailer`).
     - Tập đỉnh $V$ (bipartite=1): Các sản phẩm chuẩn (`canonical_product`).
     - Cạnh nối $(u, v)$: Tồn tại nếu nhà bán lẻ $u$ kinh doanh sản phẩm $v$. Trọng số cạnh lưu `price_min`, `price_median`, và `listing_count`.
  5. **Chỉ số Độc quyền vs Cạnh tranh**:
     - Đỉnh sản phẩm có $\text{Degree}(v) = 1$: **Exclusive** (Chỉ duy nhất 1 sàn phân phối).
     - Đỉnh sản phẩm có $\text{Degree}(v) > 1$: **Competitive** (Chiến trường giá giữa $\ge 2$ nhà bán lẻ).
  6. **Chỉ số Dẫn dắt Giá & Mức độ Đắt hơn (`retailer_degree_stats_laptop.csv`, `retailer_degree_stats_smartphone.csv`)**:
     - **Tỷ lệ thắng giá đáy (`price_leader_win_rate_pct`)**: Tỷ lệ phần trăm các sản phẩm cạnh tranh mà nhà bán lẻ niêm yết mức giá thấp nhất thị trường:
       $$\text{WinRate}(R) = \frac{\sum_{p \in \text{Comp}(R)} \mathbb{I}[P(R, p) \le P_{\min}(p)]}{|\text{Comp}(R)|} \times 100\%$$
     - **Mức độ đắt hơn trung bình (`avg_price_premium_pct`)**: Mức độ chênh lệch phần trăm trung bình giữa giá của sàn so với giá sàn thị trường trên các sản phẩm cạnh tranh:
       $$\text{PricePremium}(R) = \frac{1}{|\text{Comp}(R)|} \sum_{p \in \text{Comp}(R)} \frac{P(R, p) - P_{\min}(p)}{P_{\min}(p)} \times 100\%$$
     - Các chỉ số được tính độc lập cho từng ngành hàng; mỗi bảng vẫn giữ đủ 5 nhà bán lẻ (retailer không bán ngành hàng đó sẽ có giá trị 0).
  7. **Độ tương đồng danh mục Jaccard (`jaccard_matrix_laptop.csv`, `jaccard_matrix_smartphone.csv`)**:
     $$J(R_1, R_2) = \frac{|P(R_1) \cap P(R_2)|}{|P(R_1) \cup P(R_2)|}$$
     Với $P(R)$ là tập canonical products thuộc ngành hàng tương ứng mà retailer $R$ kinh doanh.

---

### Step 3: Đồ thị Tương đồng Sản phẩm & Phân khúc Louvain (`louvain_segments.py` + `perf_scores.py`)

- **Mục tiêu**: Phân đoạn thị trường tự động dựa trên cấu trúc tương đồng sản phẩm (Micro-segmentation) bằng benchmark hiệu năng thực tế thay vì chỉ dựa trên tên CPU/dải giá cơ học.

#### 3.1 Bổ sung điểm hiệu năng — `perf_scores.py`

Module `perf_scores.py` thực hiện 4 bước enrichment:

1. **Score aggregation** (`_scores_from_listings()`):
   - Join `canonical_listings.jsonl` với `laptop_benchmarks.jsonl` / `smartphone_benchmarks.jsonl` qua `listing_record_id`.
   - Laptop CPU/GPU dùng `perf_rating` từ Notebookcheck; smartphone dùng `benchmark_score` (Geekbench 5 Multi-Core).
   - Khi cùng một canonical product có nhiều listings, aggregate bằng **median** — robust hơn mean với outliers.
   - Fallback path (`_scores_from_products()`): Nếu chưa có benchmark files, match trực tiếp `cpu_model`/`gpu_model` từ canonical products.

2. **GPU type classification** (`is_discrete_gpu()`):
   - Classify GPU thành 3 loại: `discrete` (RTX, GTX, MX, Quadro, Radeon RX...), `integrated` (Intel UHD/HD/Iris, AMD Radeon Graphics, Apple GPU...), `unknown`.
   - Kết quả được lưu vào cột `gpu_type` để Step 3 sử dụng khi xây dựng cạnh.

3. **CPU score imputation**:
   - Với canonical products thiếu CPU score, impute bằng **median** của cùng nhóm `(category, cpu_tier)`.
   - Chỉ impute khi tier có $\ge 3$ mẫu có score (`valid_tiers`), tránh suy diễn từ sample quá nhỏ.
   - Tier `unknown` không được impute.
   - Cột `cpu_score_source` ghi `"tier_median"` để phân biệt với `"listing_median"` (score thật).

4. **Min-Max Normalization**:
   - Normalize CPU/GPU scores về $[0, 1]$ **riêng biệt theo từng category** (laptop vs smartphone).
   - Edge case: nếu tất cả scores giống nhau hoặc all-NaN, trả về 0.0.

#### 3.2 Xây dựng Product-Product Similarity Graph ($G_{pp}$) — `louvain_segments.py`

Xây dựng đồ thị tương đồng riêng biệt cho từng ngành hàng (`laptop`, `smartphone`).

**Hai strategy xây dựng cạnh:**

##### a) Performance-based edges (`_perf_edges()`) — Chế độ mặc định

Thuật toán tối ưu sử dụng sorted-array + binary search:

```
Sort products by price_median
For each product i:
    Binary search (np.searchsorted) to find price window [i+1, hi)
      where price_j <= price_i × (1 + price_tol)
    
    Vectorized: compute CPU relative diff and GPU relative diff
    
    Edge conditions:
      (1) |cpu_score_i - cpu_score_j| / max(cpu_score_i, cpu_score_j) <= perf_tol (15%)
      (2) For laptops: GPU isolation (discrete ↔ integrated/unknown blocked)
          If both have GPU scores: |gpu_score_i - gpu_score_j| / max(...) <= perf_tol
      
    Edge weight:
      W = 0.5 × PriceSim + 0.5 × SpecSim
      
      PriceSim = 1 - (price_j - price_i) / price_j  (= price_i / price_j)
      
      SpecSim (laptop with GPU) = 0.7 × CPUSim + 0.3 × GPUSim
      SpecSim (smartphone / laptop w/o GPU) = CPUSim
      
      CPUSim = 1 - |cpu_norm_i - cpu_norm_j|
      GPUSim = 1 - |gpu_norm_i - gpu_norm_j|
```

**Cross-brand**: Cạnh được phép kết nối sản phẩm khác brand (điểm khác biệt quan trọng so với legacy mode).

**Fallback within perf-mode**: Khi cả hai bên đều thiếu CPU score, rơi về logic `same_brand + (tier_match ∨ ram_match)` với trọng số thấp hơn (`baseline_spec = 0.5` cho tier match, `0.4` cho ram-only).

**Edge metadata**:
- `perf_match = "benchmark"`: Cả hai sản phẩm có score thật từ benchmark.
- `perf_match = "imputed"`: Ít nhất một bên dùng score imputed (tier_median).
- `perf_match = "fallback"`: Không có score, dùng heuristic tier/RAM.

##### b) Legacy edges (`_legacy_edges()`) — Chế độ `--no-benchmarks`

Logic cũ: chỉ kết nối sản phẩm **cùng brand**, same `cpu_tier` hoặc same `ram_gb` (khi tier unknown). Trọng số:

$$W = 0.5 \times \text{PriceSim} + 0.5 \times (0.7 \times \text{CPUTierMatch} + 0.3 \times \text{RAMMatch})$$

#### 3.3 Phát hiện Cộng đồng Louvain (Modularity Maximization)

- **Auto-tuning resolution** (`_select_resolution()`):
  - Thử 4 giá trị resolution: `1.0, 1.5, 2.0, 2.5`.
  - Đánh giá theo metrics: số communities ý nghĩa ($\ge 5$ products), tỷ lệ singleton, tỷ lệ community lớn nhất.
  - Tiêu chí chọn: **Nhiều community ý nghĩa nhất** → **Community lớn nhất ≤ 25% total** → **Ít singleton nhất**.
  - Có thể override bằng `--resolution 2.0`.

- **Gán nhãn community**:
  - Cụm $\ge 3$ sản phẩm: nhận label `{cat}_c{idx}` và segment label `{Category} {PriceMin}-{PriceMax}M ({TopBrands})`.
  - Cụm $< 3$ sản phẩm: gom vào nhóm niche theo price band → `{cat}_niche_{band}`.

- **Segment profiling**: Mỗi segment được profile với:
  - `price_min_m`, `price_median_m`, `price_max_m` (triệu VNĐ)
  - `top_brands`: 2 brands phổ biến nhất
  - `avg_retailer_degree`: mức độ cạnh tranh trung bình
  - `total_reviews`: tổng lượt review
  - `cpu_perf_median/min/max`, `gpu_perf_median`: profile hiệu năng
  - `resolution_used`: giá trị resolution đã dùng

---

### Step 4: Phát hiện Khoảng trống Thị trường & Báo cáo Trực quan (`gaps_and_reports.py`)

- **Mục tiêu**: Nhận diện lỗ hổng cạnh tranh (Structural Holes) của từng nhà bán lẻ và phát hiện các phân khúc tiềm năng trên thị trường dựa trên cả mức giá và hồ sơ hiệu năng phần cứng.
- **Cơ chế xử lý**:
  1. **Lập bảng chéo Retailer × Louvain Community**: Thống kê số lượng mã hàng mỗi nhà bán lẻ sở hữu trong từng phân khúc.
  2. **Phát hiện 2 loại khoảng trống thị trường (Structural Holes)**:
     - **Retailer Blind Spot (Điểm mù danh mục)**: Phân khúc có quy mô thị trường sôi động ($\ge 5$ mẫu máy) nhưng nhà bán lẻ có đúng $0$ sản phẩm.
     - **Underserved High-Demand Segment (Phân khúc thiếu hụt cung)**: Phân khúc có nhu cầu người dùng lớn (tổng lượt review / mẫu máy vượt trung vị ngành hàng tính riêng cho Laptop và Smartphone, kèm điều kiện review > 0) nhưng số lượng mẫu máy ít hoặc mức độ cạnh tranh giữa các sàn rất thấp ($\text{AvgDegree} \le 1.25$). Việc tính ngưỡng trung vị riêng biệt theo từng `category` giúp ngăn chặn hiện tượng lượng review cực lớn của điện thoại lấn át và triệt tiêu các phân khúc laptop tiềm năng.
  3. **Đồng bộ Thông số Hiệu năng & Khuyến nghị Cấu hình Nhập hàng (`perf_recommendation`)**:
     - Kéo các chỉ số `cpu_perf_median`, `cpu_perf_min`, `cpu_perf_max`, và `gpu_perf_median` từ Step 3 vào từng bản ghi khoảng trống.
     - Tự động sinh chỉ dẫn kỹ thuật phần cứng cụ thể: ví dụ *"Cần nhập laptop có CPU quanh mức 39.5 (34.0-45.2), GPU quanh mức 42.0 để lấp phân khúc này"*.
  4. **Xuất báo cáo trực quan & Báo cáo Kinh doanh**:
     - `jaccard_similarity_heatmap.png`: Biểu đồ 2 subplot, mỗi ngành hàng một ma trận Jaccard 5×5 với thang màu dùng chung để so sánh trực diện.
     - `segment_price_heatmap.png`: Retailer × Price Band heatmap (tách Laptop/Smartphone).
     - `bipartite_market_graph_laptop.html` / `bipartite_market_graph_smartphone.html`: 2 đồ thị tương tác PyVis riêng biệt (top 180 competitive products + sample exclusive cho từng ngành hàng).
     - `market_gaps_report.md`: Báo cáo Markdown tổng hợp, gồm 2 bảng thống kê nhà bán lẻ và 2 bảng Jaccard theo ngành hàng, cùng Mục 3.3 liệt kê chi tiết mục tiêu cấu hình phần cứng cho từng nhà bán lẻ để lấp điểm mù danh mục.

---

## 3. Module `perf_scores.py` — Tài liệu Kỹ thuật Chi tiết

### 3.1 Mục đích

Module này đóng vai trò **bridge** giữa benchmark data (Step 1.5) và similarity graph (Step 3). Nó giải quyết 3 bài toán:

1. **Aggregation**: Benchmark scores được match ở mức listing. Canonical products gom nhiều listings → cần aggregate score.
2. **Imputation**: Không phải listing nào cũng match được benchmark → cần impute missing scores.
3. **Normalization**: CPU laptop dùng Notebookcheck perf_rating (scale ~10-100), smartphone dùng Geekbench 5 (scale ~1000-6000) → cần normalize về scale chung.

### 3.2 API chính

```python
def enrich_perf_scores(
    products_df: pd.DataFrame,     # canonical_products.csv
    work_dir: Path,                # data/market_graph/
    use_benchmarks: bool = True,   # False → skip, trả về DataFrame với cột rỗng
) -> pd.DataFrame:
```

**Output columns được thêm vào DataFrame:**

| Cột | Kiểu | Mô tả |
|---|---|---|
| `cpu_perf_score` | float | Điểm CPU thô (perf_rating hoặc geekbench_5_multi) |
| `gpu_perf_score` | float | Điểm GPU thô (perf_rating, chỉ laptop) |
| `cpu_perf_metric` | str | Metric gốc (`notebookcheck_perf_rating` / `geekbench_5_multi_core`) |
| `gpu_perf_metric` | str | Metric gốc GPU |
| `cpu_score_source` | str | `listing_median` / `tier_median` / `missing` |
| `gpu_score_source` | str | `listing_median` / `missing` |
| `cpu_perf_norm` | float | CPU score normalized [0,1] per category |
| `gpu_perf_norm` | float | GPU score normalized [0,1] per category |
| `gpu_type` | str | `discrete` / `integrated` / `unknown` |

### 3.3 Utility Functions

```python
def relative_perf_diff(score_a, score_b) -> float | None:
    """Relative performance difference: |a-b| / max(a,b). None if either input is NaN."""

def perf_close(score_a, score_b, tol=0.15) -> bool:
    """True if relative_perf_diff <= tol (default 15%)."""

def is_discrete_gpu(gpu_model) -> str:
    """Classify GPU string → 'discrete' | 'integrated' | 'unknown'."""
```

### 3.4 Luồng xử lý bên trong `enrich_perf_scores()`

```
1. _scores_from_listings(work_dir)
   ├── Đọc canonical_listings.jsonl
   ├── Join với laptop_benchmarks.jsonl (cpu_perf_rating, gpu_perf_rating)
   ├── Join với smartphone_benchmarks.jsonl (cpu_benchmark_score)
   ├── Merge CPU scores: laptop perf_rating || phone benchmark_score
   └── Aggregate by canonical_product_id → median
   
2. Nếu step 1 return None → fallback:
   _scores_from_products(df, work_dir)
   ├── Load benchmark CSVs trực tiếp
   └── Match canonical product cpu_model/gpu_model → score

3. Merge scores vào products_df

4. CPU imputation:
   ├── Group by (category, cpu_tier)
   ├── Chỉ impute nếu tier có >= 3 samples
   └── Ghi cpu_score_source = "tier_median"

5. GPU type classification: is_discrete_gpu() trên cột gpu_model

6. Normalize per-category: _normalize() → min-max [0, 1]

7. Drop temporary columns (listing_cpu_score, listing_gpu_score)
```

---

## 4. Cách Chạy Pipeline

### Chạy từng bước

```bash
# Step 1: Chuẩn hóa specs bằng DeepSeek
python -m src.market_graph.cli step1 --sample-size 100 --batch-size 25

# Step 1.5: Parse benchmarks & match (subcommand mới)
python -m src.market_graph.cli step1_5 --input data/market_graph/sample_100_cleaned.jsonl
# Hoặc alias:
python -m src.market_graph.cli benchmarks --input data/market_graph/sample_100_cleaned.jsonl

# Step 2: Entity Resolution & Bipartite Graph
python -m src.market_graph.cli step2 --input data/market_graph/sample_100_cleaned.jsonl --max-spread 0.20

# Step 3: Product Similarity Graph & Louvain (benchmark mode)
python -m src.market_graph.cli step3 --perf-tol 0.15 --resolution auto

# Step 3 alternative: Legacy mode (cpu_tier/RAM)
python -m src.market_graph.cli step3 --no-benchmarks

# Step 4: Structural Holes & Reports
python -m src.market_graph.cli step4
```

### Chạy end-to-end (Đã liên kết trọn vẹn 1 -> 1.5 -> 2 -> 3 -> 4)

```bash
python -m src.market_graph.cli run-all --sample-size 100 --perf-tol 0.15
```

### Tham số quan trọng

| Tham số | Default | Mô tả |
|---|---|---|
| `--max-spread` | 0.20 | Ngưỡng chênh lệch giá tối đa trong cùng cluster khi thiếu RAM/Storage (Step 2) |
| `--price-tol` | 0.20 | Ngưỡng chênh lệch giá để tạo cạnh P-P (Step 3) |
| `--perf-tol` | 0.15 | Ngưỡng chênh lệch CPU/GPU score để tạo cạnh (Step 3) |
| `--resolution` | auto | Louvain resolution: `auto` hoặc số thực (vd: `2.0`) |
| `--no-benchmarks` | — | Tắt benchmark mode, dùng legacy cpu_tier/RAM logic (Step 3) |
| `--sample-size` | None | Số lượng sample stratified (Step 1) |

---

## 5. Ý nghĩa Chi tiết của Các File Đầu Ra (Outputs)

Toàn bộ kết quả chạy được lưu trữ tại `data/market_graph/`:

| Tên File | Định dạng | Bước sinh ra | Ý nghĩa và Ứng dụng |
| :--- | :---: | :---: | :--- |
| **`raw_products_export.csv`** | CSV | Step 1 | Danh sách tất cả listing gốc sau khi đã lọc bỏ các bản ghi không có giá hợp lệ (giá $\le 0$ hoặc thiếu giá). Dùng để kiểm tra dữ liệu thô đối chiếu. |
| **`llm_spec_cache.jsonl`** | JSONL | Step 1 | Bộ nhớ đệm (cache) lưu trữ các phản hồi trích xuất phần cứng từ LLM theo hash nội dung. Giúp tiết kiệm chi phí và tăng tốc khi chạy lại. |
| **`products_llm_cleaned.jsonl`** / **`.csv`** | JSONL / CSV | Step 1 | Toàn bộ các listing đã được LLM làm sạch hoàn chỉnh: chuẩn hóa hãng (`brand`), tên dòng máy sạch (`model_clean`), vi xử lý (`cpu_model`), thông số RAM/SSD, và loại bỏ các phụ kiện rác. |
| **`benchmarks/cpu_benchmarks.csv`** | CSV | Step 1.5 | Bảng CPU Notebookcheck đã parse: tên model, codename, cache, TDP, MHz, cores/threads, điểm benchmark và `perf_rating` (kèm `perf_rating_is_approx`, `perf_rating_coverage_pct`). |
| **`benchmarks/gpu_benchmarks.csv`** | CSV | Step 1.5 | Bảng GPU Notebookcheck đã parse: kiến trúc, shaders, xung nhịp, bộ nhớ, điểm 3DMark và `perf_rating` (kèm metadata độ tin cậy). |
| **`benchmarks/cpu_phone_benchmarks.csv`** | CSV | Step 1.5 | Bảng CPU smartphone Notebookcheck đã parse: codename, kiến trúc, MHz, cores/threads, Geekbench 2/3/4/5, PassMark, Sunspider và `benchmark_score` (Geekbench 5 Multi-Core, fallback Geekbench 4 Multi quy đổi hệ số về thang Geekbench 5). |
| **`laptop_benchmarks.csv`** / **`.jsonl`** | CSV / JSONL | Step 1.5 | Laptop listing được enrich thêm `cpu_bench_model`, `cpu_perf_rating`, `gpu_bench_model`, `gpu_perf_rating`, phương thức match và độ tin cậy. Không sửa file gốc `products_llm_cleaned`. |
| **`smartphone_benchmarks.csv`** / **`.jsonl`** | CSV / JSONL | Step 1.5 | Smartphone listing được enrich thêm `cpu_bench_model`, `cpu_benchmark_score`, điểm Geekbench/PassMark và metadata match. |
| **`benchmarks/match_report.csv`** | CSV | Step 1.5 | Danh sách các giá trị CPU/GPU chưa match được, kèm số lượng và lý do. |
| **`benchmarks/smartphone_match_report.csv`** | CSV | Step 1.5 | Danh sách CPU smartphone chưa match được, kèm số lượng và lý do. |
| **`canonical_listings.jsonl`** | JSONL | Step 2 | Tập dữ liệu listing ban đầu được bổ sung thêm trường `canonical_product_id`. Cho phép truy vết ngược một listing bất kỳ của một sàn thuộc về mẫu máy chuẩn nào. |
| **`canonical_products.csv`** | CSV | Step 2 | **Bảng danh mục sản phẩm duy nhất của toàn thị trường**. Mỗi dòng là 1 mẫu máy chuẩn kèm theo: `price_min`, `price_median`, `price_max`, `retailer_count` (số sàn bán), danh sách sàn (`retailers`), tổng đánh giá (`total_reviews`), và `avg_rating`. |
| **`bipartite_market_graph_laptop.gexf`** / **`bipartite_market_graph_smartphone.gexf`** | XML/GEXF | Step 2 | Đồ thị hai phía riêng cho từng ngành hàng, dùng để mở trong Gephi hoặc NetworkX. Mỗi đồ thị giữ đủ 5 nhà bán lẻ và chỉ chứa canonical products thuộc ngành hàng tương ứng. |
| **`retailer_degree_stats_laptop.csv`** / **`retailer_degree_stats_smartphone.csv`** | CSV | Step 2 | **Thống kê chiến lược danh mục và giá của 5 nhà bán lẻ theo từng ngành hàng**: Tổng số mẫu máy, số lượng và tỷ lệ hàng độc quyền (`exclusive_pct`), số lượng hàng cạnh tranh, **tỷ lệ thắng giá đáy (`price_leader_win_rate_pct`)** và **mức độ đắt hơn trung bình (`avg_price_premium_pct`)**. |
| **`jaccard_matrix_laptop.csv`** / **`jaccard_matrix_smartphone.csv`** | CSV | Step 2 | **Ma trận độ trùng lặp danh mục (0.0 đến 1.0)** giữa từng cặp nhà bán lẻ, tính riêng theo ngành hàng. Thể hiện mức độ "đối đầu trực diện" hay "phân hóa thị trường" trong từng mảng. |
| **`canonical_products_segmented.csv`** | CSV | Step 3 | Bảng sản phẩm chuẩn được bổ sung nhãn phân khúc Louvain (`community_id`, `segment_label`), dải giá `price_band`, `cpu_tier`, điểm hiệu năng (`cpu_perf_score`, `gpu_perf_score`, `cpu_perf_norm`, `gpu_perf_norm`, `cpu_score_source`, `gpu_score_source`, `gpu_type`). |
| **`louvain_segments.csv`** | CSV | Step 3 | **Hồ sơ chi tiết từng phân khúc thị trường**: Khoảng giá min-max, giá trung vị, các thương hiệu áp đảo (`top_brands`), mức độ cạnh tranh trung bình (`avg_retailer_degree`), tổng lượng review, profile hiệu năng (`cpu_perf_median/min/max`, `gpu_perf_median`) và `resolution_used`. |
| **`retailer_community_matrix.csv`** | CSV | Step 4 | Bảng ma trận chéo (Crosstab) thể hiện: Nhà bán lẻ $X$ đang bán bao nhiêu mẫu máy trong Phân khúc $Y$. |
| **`structural_holes.csv`** | CSV | Step 4 | **Danh sách các khoảng trống thị trường**: Chỉ ra cụ thể sàn nào đang bỏ ngỏ phân khúc nào (`retailer_blind_spot`), hoặc phân khúc nào đang thiếu cung dù nhu cầu cao (`underserved_high_demand`), kèm theo các cột điểm chuẩn hiệu năng (`cpu_perf_median/min/max`, `gpu_perf_median`) và **khuyến nghị cấu hình cụ thể (`perf_recommendation`)**. |
| **`reports/market_gaps_report.md`** | Markdown | Step 4 | Báo cáo kinh doanh tổng hợp được sinh tự động, tóm tắt các phát hiện cốt lõi về cấu trúc thị trường, ma trận Jaccard, bảng thống kê giá, danh sách điểm mù và **khuyến nghị cấu hình nhập hàng theo từng sàn**. |
| **`reports/jaccard_similarity_heatmap.png`** | Hình ảnh PNG | Step 4 | Biểu đồ 2 subplot hiển thị trực quan phần trăm trùng lặp danh mục giữa 5 sàn bán lẻ, tách riêng Laptop và Smartphone với thang màu dùng chung. |
| **`reports/segment_distribution.png`** | Hình ảnh PNG | Step 3 & 4 | Biểu đồ cột thể hiện phân bố mẫu máy theo dải giá và theo các phân khúc Louvain nổi bật. |
| **`reports/segment_price_heatmap.png`** | Hình ảnh PNG | Step 4 | Bản đồ nhiệt phân bổ số lượng sản phẩm của từng nhà bán lẻ theo từng dải giá (tách riêng Laptop và Smartphone). |
| **`reports/bipartite_market_graph_laptop.html`** / **`reports/bipartite_market_graph_smartphone.html`** | Web tương tác | Step 4 | 2 đồ thị mạng PyVis riêng theo ngành hàng, cho phép phóng to, thu nhỏ, kéo thả và click vào từng nhà bán lẻ để xem danh mục kết nối. |

---

## 6. Các Phát Hiện Thị Trường Tiêu Biểu Từ Dữ Liệu Đã Chạy

Dựa trên dữ liệu thực tế thu thập từ 5 nhà bán lẻ (CellphoneS, FPT Shop, Hoàng Hà Mobile, TGDĐ, Viettel Store). *Các số liệu dưới đây lấy từ bản chạy tổng hợp trước khi tách ngành hàng; khi chạy lại, xem chi tiết trong `retailer_degree_stats_laptop.csv` / `retailer_degree_stats_smartphone.csv` và `jaccard_matrix_laptop.csv` / `jaccard_matrix_smartphone.csv`.*

1. **Chiến lược danh mục của các nhà bán lẻ (`retailer_degree_stats_laptop.csv`, `retailer_degree_stats_smartphone.csv`)**:
   - **CellphoneS** có danh mục áp đảo nhất (3.112 mẫu máy) với **90.3% là hàng độc quyền/ngách** (không bị cạnh tranh bởi 4 sàn còn lại).
   - **FPT Shop** (434 mẫu) và **TGDĐ** (596 mẫu) tập trung vào các dòng máy phổ thông có tính cạnh tranh cao (tỷ lệ hàng cạnh tranh lần lượt là 56.68% và 41.61%).
   - **Viettel Store** (142 mẫu) có danh mục hẹp nhất, tập trung phần lớn vào các sản phẩm cạnh tranh (tỷ lệ cạnh tranh 73.24%), gần như chỉ bán các model chủ lực.

2. **Mức độ trùng lặp danh mục (`jaccard_matrix_laptop.csv`, `jaccard_matrix_smartphone.csv`)**:
   - Độ trùng lặp giữa các sàn nhìn chung rất thấp (chỉ dao động từ **2.3% đến 16.4%**).
   - Cặp đôi có sự trùng lặp danh mục cao nhất là **TGDĐ và FPT Shop (16.38%)**, cho thấy đây là hai đối thủ đối đầu trực tiếp mạnh nhất về mặt dòng sản phẩm.

3. **Khoảng trống thị trường (`structural_holes.csv`)**:
   - Thuật toán đã phát hiện **125 điểm mù (Retailer Blind Spots)**. Điển hình như:
     - Viettel Store và Hoàng Hà Mobile bỏ ngỏ hoàn toàn phân khúc *Laptop MSI 9-85M* và *Laptop Lenovo 14-78M*.
     - TGDĐ, FPT Shop và Viettel Store không có sản phẩm trong phân khúc *Laptop HP giá rẻ 6-17M* (nơi CellphoneS đang nắm giữ 53 model độc quyền).
   - Phát hiện **24 phân khúc thiếu hụt nguồn cung (Underserved)**: Có lượt quan tâm và đánh giá cao từ người tiêu dùng nhưng chỉ có 1 hoặc 2 nhà bán lẻ niêm yết.
