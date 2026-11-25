"""Data loaders and structured business annotations for TV1-TV7 artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from prepare_test_data import REPO_ROOT, load_tv7_flags


EDA_FIG_DIR = REPO_ROOT / "src" / "eda" / "outputs" / "figures"
EDA_TABLE_DIR = REPO_ROOT / "src" / "eda" / "outputs" / "tables"
MARKET_GRAPH_DIR = REPO_ROOT / "data" / "market_graph"
TV6_DATA_DIR = REPO_ROOT / "data" / "tv6"
TV6_DOCS_DIR = REPO_ROOT / "docs" / "review_nlp"
TV7_OUT_DIR = REPO_ROOT / "src" / "anomaly_detection" / "outputs"


EDA_THEMES = {
    "market_price_discount": "1. Toàn cảnh thị phần, Phân phối giá & Chiết khấu 5 sàn",
    "missingness_profile": "2. Cấu trúc thiếu dữ liệu theo nguồn & Ngành hàng (MCAR/MAR/MNAR)",
    "pricing_drivers_paradoxes": "3. Quy luật định giá Laptop vs Smartphone & 3 Nghịch lý phần cứng",
    "data_hygiene_drift": "4. Kiểm toán ngoại lai, Đa cộng tuyến VIF & Tác động tồn kho (Price Drift)",
}


EDA_CHART_GUIDE: list[dict[str, str]] = [
    {
        "theme": "market_price_discount",
        "figure": "fig_1_1_source_category_distribution.png",
        "table": "table_1_1_source_category_counts.csv",
        "title": "Hình 1.1A · Phân bố sản phẩm theo nguồn thu thập và ngành hàng",
        "question": "Quy mô danh mục niêm yết giữa 5 chuỗi bán lẻ phân bổ ra sao giữa Laptop và Smartphone?",
        "finding": (
            "Tổng cộng 10.316 bản ghi gồm 4.874 Laptop (47,25%) và 5.442 Smartphone (52,75%). "
            "CellphoneS dẫn đầu về độ rộng danh mục với 7.847 bản ghi (76,07%: 3.912 laptop, 3.935 smartphone), "
            "tiếp theo là TGDĐ (1.197; 11,60%), FPT Shop (820; 7,95%), Hoàng Hà Mobile (285; 2,76%) và Viettel Store (167; 1,62%)."
        ),
        "action": (
            "CellphoneS giữ lưu trữ dài các biến thể màu sắc và hàng ngừng kinh doanh (long-tail catalog), "
            "trong khi các sàn khác tinh gọn danh mục đang bán. Do đó khi so sánh mặt bằng giá liên sàn bắt buộc phải "
            "đối sánh thực thể sản phẩm chuẩn (TV4) và kiểm soát trạng thái tồn kho."
        ),
    },
    {
        "theme": "market_price_discount",
        "figure": "fig_1_1_brand_market_share.png",
        "table": "table_1_1_overall_brand_share.csv",
        "title": "Hình 1.1B · Thị phần Top thương hiệu ở Laptop và Smartphone",
        "question": "Mức độ tập trung thương hiệu giữa thị trường Laptop và Smartphone khác nhau như thế nào?",
        "finding": (
            "Thị trường Laptop tập trung cao khi 7 hãng đầu (ASUS 23,88%, Apple 19,72%, Lenovo 15,18%, HP 10,73%, "
            "Dell 10,16%, MSI 8,00%, Acer 7,28%) chiếm tới 95,66% tổng niêm yết. Ngược lại, Smartphone phân mảnh hơn: "
            "Top 3 hãng lớn nhất (Samsung 17,92%, Xiaomi 17,42%, Apple 13,27%) chiếm 48,61%, phần còn lại trải đều cho OPPO, Vivo, Realme, Honor."
        ),
        "action": (
            "Nhà bán lẻ mở mới danh mục Laptop chỉ cần tập trung 6–7 hãng cốt lõi là bao phủ >95% nhu cầu thị trường; "
            "trong khi mảng Smartphone đòi hỏi chiến lược chọn lọc theo phân khúc giá thay vì dàn trải thương hiệu."
        ),
    },
    {
        "theme": "market_price_discount",
        "figure": "fig_1_1_seller_market_share.png",
        "table": "table_1_1_seller_distribution.csv",
        "title": "Hình 1.1C · Tỷ trọng niêm yết của 5 hệ thống bán lẻ",
        "question": "Sự mất cân bằng kích thước mẫu giữa các nhà bán lẻ tác động gì tới phân tích thống kê và mô hình hóa?",
        "finding": (
            "Ba chuỗi lớn nhất (CellphoneS 76,07%, TGDĐ 11,60%, FPT Shop 7,95%) chiếm 95,62% số dòng niêm yết, "
            "còn Hoàng Hà Mobile và Viettel Store chiếm 4,38%."
        ),
        "action": (
            "Nếu tính trung bình toàn cục không phân tầng, kết quả sẽ bị chi phối bởi cấu trúc danh mục của CellphoneS. "
            "Vì vậy mọi phân tích cạnh tranh (TV4), kiểm toán bất thường (TV7) và đánh giá sai số (TV8) đều phải báo cáo kèm cỡ mẫu theo từng sàn."
        ),
    },
    {
        "theme": "market_price_discount",
        "figure": "fig_1_2_price_distribution_and_log_transform.png",
        "table": "table_1_2_price_log_transform_comparison.csv",
        "title": "Hình 1.2A · Phân phối giá niêm yết lệch phải và hiệu quả biến đổi Logarithm",
        "question": "Phân phối giá thiết bị công nghệ có tuân theo phân phối chuẩn không, và cần biến đổi toán học nào?",
        "finding": (
            "Giá gốc lệch phải rất mạnh: Laptop có Median 26,84M nhưng Mean 32,99M (Skewness +2,89, Kurtosis +13,54, đỉnh tới 269,99M); "
            "Smartphone có Median 7,99M nhưng Mean 13,99M (Skewness +7,38, Kurtosis +170,71). Sau biến đổi log10, độ lệch giảm mạnh về "
            "+0,29 (Laptop) và -0,58 (Smartphone), tiệm cận phân phối đối xứng."
        ),
        "action": (
            "Báo cáo nghiệp vụ phải dùng Trung vị (Median) và IQR thay vì Trung bình cộng để phản ánh đúng mức giá điển hình. "
            "Đồng thời, cả kiểm toán ngoại lai IQR (TV7) lẫn mô hình định giá hợp lý (TV5) bắt buộc hoạt động trên thang log(giá)."
        ),
    },
    {
        "theme": "market_price_discount",
        "figure": "fig_1_2_discount_rate_by_source.png",
        "table": "table_1_2_discount_rate_by_source.csv",
        "title": "Hình 1.2B · Chiến lược chiết khấu niêm yết (Discount Rate) giữa 5 nhà bán lẻ",
        "question": "Các chuỗi bán lẻ tại Việt Nam sử dụng chiến lược giảm giá niêm yết khác nhau ra sao?",
        "finding": (
            "75,0% listing trên thị trường có gắn giá gạch (chiết khấu trung bình 11,50%, trung vị 8,34%). "
            "Hoàng Hà Mobile (TB 20,81%) và Viettel Store (TB 14,53%) niêm yết biên độ giảm sâu nhất; CellphoneS ở mức 11,70%; "
            "TGDĐ (9,05%) và FPT Shop (7,95%) giữ mức chiết khấu niêm yết thận trọng hơn."
        ),
        "action": (
            "Tỷ lệ giảm giá cao chưa hẳn là giá bán thực tế rẻ nhất (do phụ thuộc giá gốc niêm yết ban đầu). "
            "Người mua cần đối chiếu giá thực với Giá trị Hợp lý theo cấu hình (Tab 3), và tuyệt đối cấm đưa discount_rate/original_price_vnd vào mô hình để tránh rò rỉ nhãn mục tiêu."
        ),
    },
    {
        "theme": "missingness_profile",
        "figure": "fig_1_3_overall_missingness_ranking.png",
        "table": "table_1_3_overall_missingness.csv",
        "title": "Hình 1.3A · Xếp hạng tỷ lệ khuyết dữ liệu của 32 thuộc tính",
        "question": "Những thông số kỹ thuật nào bị khuyết nhiều nhất trên dữ liệu thương mại điện tử thực tế?",
        "finding": (
            "Các trường định danh và phân loại cốt lõi (category, seller_raw, product_name) đầy đủ 100%, brand_norm chỉ khuyết 0,27%, "
            "screen_size_inch chỉ khuyết 5,06%. Ngược lại, max_ram_gb (96,58%), charger_watt (90,41%), network_type_norm (83,35%) và "
            "battery_wh (80,62%) có tỷ lệ thiếu toàn cục trên 80%."
        ),
        "action": (
            "Áp dụng nguyên tắc 'gắn cờ thay vì xóa dòng' (flag-don't-drop) ở tầng dữ liệu TV2: giữ nguyên bản ghi và tạo cờ nhị phân "
            "(is_ram_missing, is_battery_missing, is_charger_missing) kết hợp điền trung vị theo từng hãng chỉ trên tập huấn luyện."
        ),
    },
    {
        "theme": "missingness_profile",
        "figure": "fig_1_3_missingness_heatmap_by_source_category.png",
        "table": "table_1_3_missingness_by_source.csv",
        "title": "Hình 1.3B · Bản đồ nhiệt tỷ lệ thiếu dữ liệu theo từng sàn và ngành hàng",
        "question": "Dữ liệu bị thiếu hoàn toàn ngẫu nhiên (MCAR) hay phụ thuộc có hệ thống vào cấu trúc từng website?",
        "finding": (
            "Tỷ lệ khuyết phân bố rất khác nhau giữa các nguồn do khác biệt cấu trúc bảng thông số HTML/JSON-LD giữa TGDĐ, FPT Shop, "
            "CellphoneS, Hoàng Hà và Viettel Store (cơ chế MAR/MNAR theo nguồn thu thập)."
        ),
        "action": (
            "Không được xóa bỏ các bản ghi thiếu thông số phụ vì sẽ làm biến mất hoàn toàn dữ liệu của một số nhà bán lẻ nhỏ. "
            "Thay vào đó cần khôi phục thông số từ tiêu đề sản phẩm (Regex/LLM ở TV4 & TV5) và kiểm tra độ bền vững mô hình khi che 20% RAM/Storage (TV8)."
        ),
    },
    {
        "theme": "missingness_profile",
        "figure": "fig_1_3_hardware_missingness_laptop_vs_phone.png",
        "table": "table_1_3_missingness_by_category.csv",
        "title": "Hình 1.3C · Đối sánh cơ chế khuyết phần cứng đặc thù Laptop vs Smartphone",
        "question": "Vì sao không nên gộp chung Laptop và Smartphone vào một ma trận đặc trưng duy nhất?",
        "finding": (
            "Dữ liệu thiếu mang tính cấu trúc theo ngành hàng (Category-specific MAR): battery_wh khuyết 99,94% ở Smartphone nhưng có ở 40,95% Laptop; "
            "ngược lại battery_mah có ở 75,93% Smartphone nhưng khuyết 99,45% ở Laptop; gpu_norm chỉ khuyết 4,80% ở Laptop nhưng khuyết 69,96% ở Smartphone."
        ),
        "action": (
            "Đây là bằng chứng thống kê trực tiếp buộc toàn bộ hệ thống (TV4 đồ thị, TV7 phát hiện bất thường và TV5 mô hình định giá) "
            "phải tách thành 2 pipeline độc lập cho Laptop và Smartphone."
        ),
    },
    {
        "theme": "pricing_drivers_paradoxes",
        "figure": "fig_2_1_hardware_correlation_heatmaps.png",
        "table": "table_2_1_laptop_correlations.csv",
        "title": "Hình 2.1A · Ma trận tương quan thứ hạng Spearman giữa thông số phần cứng và giá bán",
        "question": "Thông số phần cứng nào có mối liên hệ đơn điệu mạnh nhất với mức giá niêm yết ở từng ngành hàng?",
        "finding": (
            "Ở Laptop, RAM dẫn đầu (Spearman rho = +0,744), kế đến là pin Wh (+0,665), công suất sạc W (+0,623) và SSD (+0,521), "
            "trong khi kích thước màn hình rất yếu (+0,143). Ở Smartphone, bộ nhớ ROM dẫn đầu (rho = +0,703), kế đến là RAM (+0,646), "
            "còn camera MP (+0,179) và pin mAh (+0,036) rất yếu."
        ),
        "action": (
            "Lưu ý học thuật: Tương quan Spearman phản ánh mối liên hệ đồng biến trên thị trường (statistical association), "
            "không phải quan hệ nhân quả về chi phí sản xuất (nhà sản xuất thường đóng gói RAM/ROM lớn kèm chip và màn hình cao cấp)."
        ),
    },
    {
        "theme": "pricing_drivers_paradoxes",
        "figure": "fig_2_1_hardware_price_relationships_laptop.png",
        "table": "table_2_1_laptop_ram_price.csv",
        "title": "Hình 2.1B · Phân tầng giá Laptop theo bậc RAM, phân khúc CPU và loại GPU",
        "question": "Mức giá trung vị của Laptop nhảy bậc như thế nào khi nâng cấp RAM, CPU và card đồ họa rời?",
        "finding": (
            "Giá trung vị Laptop tăng gấp 5,12 lần theo bậc RAM: từ 18,99M (8GB) -> 29,99M (16GB) -> 52,89M (32GB) -> 97,14M (>=64GB). "
            "Theo CPU (Kruskal-Wallis H = 2099,48, p < 1e-300), Core i9/Ryzen 9 có trung vị 54,99M (gấp 4,60 lần Core i3 ở mức 11,95M), "
            "và dòng Apple Silicon đạt trung vị 44,79M."
        ),
        "action": (
            "Laptop được định giá theo năng lực tính toán và làm việc (Productivity Asset). Khi thẩm định giá hợp lý cho Laptop, "
            "tổ hợp CPU benchmark + GPU rời + tương tác RAM × Storage đóng vai trò trục định giá chính."
        ),
    },
    {
        "theme": "pricing_drivers_paradoxes",
        "figure": "fig_2_1_hardware_price_relationships_smartphone.png",
        "table": "table_2_1_phone_storage_price.csv",
        "title": "Hình 2.1C · Phân tầng giá Smartphone theo ROM, công nghệ màn hình và thương hiệu",
        "question": "Yếu tố nào tạo ra sự phân hóa giá mạnh nhất trên thị trường điện thoại thông minh?",
        "finding": (
            "Bộ nhớ trong ROM tạo biên độ giãn giá 11,97 lần: từ trung vị 3,49M (<=64GB) và 6,59M (128GB) vọt lên 16,59M (256GB), "
            "25,59M (512GB) và 41,79M (>=1TB). Màn hình OLED/AMOLED có trung vị 15,99M — đắt gấp 4,21 lần màn IPS/LCD (3,80M; ANOVA F = 2902,99). "
            "Apple có trung vị 25,49M so với 15,84M của Samsung và 4,5–9,0M của nhóm Xiaomi/OPPO/Vivo/Realme."
        ),
        "action": (
            "Các hãng smartphone sử dụng dung lượng ROM và màn hình OLED làm công cụ phân tầng biên lợi nhuận bậc thang (Tiered Upsell). "
            "Người tiêu dùng mua máy 256GB–512GB cần kiểm tra mức chênh giá giữa các sàn vì đây là vùng biên lợi nhuận dao động lớn nhất."
        ),
    },
    {
        "theme": "pricing_drivers_paradoxes",
        "figure": "fig_2_2_pricing_drivers_comparison.png",
        "table": "table_2_2_pricing_structure_matrix.csv",
        "title": "Hình 2.2 · Đối sánh cấu trúc định giá Laptop vs Smartphone & 3 Nghịch lý phần cứng",
        "question": "Vì sao người mua phổ thông dễ bị đánh lừa bởi các con số quảng cáo như Pin 5000mAh, Camera 108MP hay Màn hình 15,6 inch?",
        "finding": (
            "Dữ liệu vạch rõ 3 nghịch lý: (1) Pin Smartphone bão hòa quanh 5.000 mAh ở cả máy 2 triệu lẫn 35 triệu (rho = +0,036); "
            "(2) Camera MP chỉ tương quan yếu với giá (rho = +0,179) do máy giá rẻ chạy đua số chấm 50–108MP còn flagship tối ưu cảm biến & thuật toán; "
            "(3) Laptop 13–14 inch Ultrabook cao cấp đắt ngang hoặc hơn máy 15,6 inch phổ thông (rho = +0,143)."
        ),
        "action": (
            "Giúp người tiêu dùng tránh mua hớ vì 'thông số hào nhoáng nhưng không quyết định giá trị thực', đồng thời giải thích vì sao "
            "cần bổ sung điểm chuẩn hiệu năng SoC/CPU/GPU thực tế từ Notebookcheck (TV4) thay vì chỉ đọc thông số thô."
        ),
    },
    {
        "theme": "data_hygiene_drift",
        "figure": "fig_3_1_price_outliers_and_boundaries.png",
        "table": "table_3_1_price_percentiles_boundaries.csv",
        "title": "Hình 3.1 · Nhận diện ngoại lai và ranh giới phân phối giá",
        "question": "Các điểm giá cực thấp (<1 triệu) và cực cao (>100 triệu) là lỗi dữ liệu hay sản phẩm thật?",
        "finding": (
            "Trong 10.316 bản ghi có 1.768 dòng thiếu/không có giá dương (cần loại khỏi phân tích giá). Nhóm dưới sàn (<500k: 97 mẫu) chủ yếu là "
            "điện thoại cơ bản 2G/4G hoặc phụ kiện lẫn danh mục; ngược lại 87 mẫu >100 triệu đều là Workstation/Gaming flagship thật (MacBook Pro M3/M5 Max, MSI Titan 18 HX)."
        ),
        "action": (
            "Thiết lập ngưỡng sàn nghiệp vụ thống nhất toàn dự án (Laptop >= 3 triệu, Smartphone >= 1 triệu), nhưng tuyệt đối giữ lại các flagship giá cao "
            "với phép biến đổi log(1+y) — tiền đề trực tiếp cho hệ thống phân loại 4 nhóm anomaly_type của TV7."
        ),
    },
    {
        "theme": "data_hygiene_drift",
        "figure": "fig_3_2_multicollinearity_and_vif.png",
        "table": "table_3_2_multicollinearity_vif.csv",
        "title": "Hình 3.2 · Kiểm định đa cộng tuyến và hệ số phóng đại phương sai (VIF)",
        "question": "Các biến phần cứng đưa vào mô hình hồi quy có bị đa cộng tuyến nghiêm trọng làm sai lệch hệ số không?",
        "finding": (
            "Toàn bộ biến số đều nằm dưới ngưỡng cảnh báo VIF = 5,0: ở Laptop mọi biến đạt VIF <= 1,58; ở Smartphone installed_ram_gb có VIF = 2,68 "
            "(do tương quan r = +0,56 với ROM) và charger_watt đạt VIF = 2,98."
        ),
        "action": (
            "Đảm bảo tính ổn định toán học khi sử dụng hồi quy tuyến tính có điều chuẩn L2 (Ridge Regression) làm mốc tham chiếu và "
            "giúp các đóng góp SHAP trên mô hình cây (LightGBM) không bị nhiễu cộng tuyến cực đoan."
        ),
    },
    {
        "theme": "data_hygiene_drift",
        "figure": "fig_3_3_availability_price_comparison.png",
        "table": "table_3_4_availability_hypothesis_test.csv",
        "title": "Hình 3.3 · Tác động của trạng thái tồn kho và hiện tượng trôi giá (Price Drift)",
        "question": "Giá niêm yết lưu trên web của các mẫu 'Hết hàng / Ngừng kinh doanh' có lệch so với hàng đang bán không?",
        "finding": (
            "Kiểm định Mann-Whitney U cho thấy sự chênh lệch rất có ý nghĩa thống kê: hàng đang còn (in_stock) có giá cao hơn hàng hết kho (out_of_stock) "
            "tới +9,50 triệu VNĐ (+39,6%, p = 3,98e-37) ở Laptop và +3,30 triệu VNĐ (+50,9%, p = 1,02e-17) ở Smartphone."
        ),
        "action": (
            "Các mặt hàng hết kho thường là thế hệ cũ cuối vòng đời (EOL) giữ mức giá xả kho cũ. Bắt buộc đưa cờ is_out_of_stock vào mô hình định giá (TV5) "
            "để không kéo tụt mức định giá hợp lý của các sản phẩm đời mới đang mở bán."
        ),
    },
]


TV6_CHART_GUIDE: list[dict[str, str]] = [
    {
        "figure": "fig_4_2_topic_distribution.png",
        "title": "Phân bổ 5 chủ đề tiềm ẩn trong đánh giá khách hàng (LDA Topic Modeling)",
        "question": "Người mua thiết bị công nghệ tại Việt Nam thực sự bàn luận về những chủ đề nào sau khi mua hàng?",
        "finding": (
            "Trên 14.869 đánh giá hợp lệ, mô hình LDA tách được 5 chủ đề rõ rệt: Hiệu năng & Tốc độ máy chiếm tỷ trọng lớn nhất (29,61%), "
            "tiếp theo là Dịch vụ shop & Giao hàng (19,09%), Trải nghiệm sử dụng & Sự cố (18,74%), Màn hình & Camera (16,46%) và Thời lượng pin & Sạc (16,11%)."
        ),
        "action": (
            "Gần 1/5 lượng thảo luận xoay quanh chất lượng phục vụ và giao vận của nhà bán lẻ chứ không riêng phần cứng; "
            "do đó điểm sao trung bình trên web phản ánh hỗn hợp cả dịch vụ cửa hàng lẫn chất lượng máy."
        ),
    },
    {
        "figure": "fig_4_3_aspect_sentiment_matrix.png",
        "title": "Ma trận sắc thái cảm xúc theo 5 khía cạnh kỹ thuật (ABSA)",
        "question": "Khía cạnh kỹ thuật nào khiến khách hàng hài lòng nhất và phàn nàn gay gắt nhất?",
        "finding": (
            "Dịch vụ & Giao vận đạt tỷ lệ tích cực cao nhất (90,96% tích cực, chỉ 6,20% tiêu cực), kế đến là Màn hình & Thiết kế (87,26% tích cực). "
            "Ngược lại, Hiệu năng & Tản nhiệt là 'điểm nóng' phàn nàn số 1 thị trường với 21,34%–21,70% nhận xét tiêu cực (nóng máy, tụt xung, giật lag, quạt ồn), "
            "tiếp theo là Camera & Âm thanh (17,90% tiêu cực) và Pin & Nguồn điện (18,12% tiêu cực)."
        ),
        "action": (
            "Nhà bán lẻ và bộ phận thu mua cần theo dõi sát tỷ lệ phàn nàn nhiệt độ/hiệu năng để cảnh báo sớm rủi ro đổi trả bảo hành; "
            "người mua máy cũ hoặc máy giảm giá sâu nên kiểm tra kỹ khía cạnh tản nhiệt và pin của dòng máy đó."
        ),
    },
    {
        "figure": "fig_4_4_aspect_by_category.png",
        "title": "Khác biệt mối quan tâm hậu mãi giữa người mua Laptop và Smartphone",
        "question": "Hành vi đánh giá sản phẩm của khách hàng Laptop khác khách hàng Smartphone như thế nào?",
        "finding": (
            "Người mua Laptop đặc biệt nhạy cảm với Hiệu năng & Tản nhiệt (29,42% số review đề cập so với 18,65% ở Smartphone) "
            "và Màn hình & Thiết kế (27,68% vs 17,06%). Trong khi đó, người mua Smartphone chú trọng hơn tới Pin & Sạc (13,88% vs 10,92%) và Camera & Âm thanh (7,65% vs 4,92%)."
        ),
        "action": (
            "Tư vấn viên ngành hàng Laptop cần minh bạch thông số tản nhiệt/công suất TGP và độ phủ màu màn hình; "
            "ngành hàng Smartphone cần tập trung truyền thông trải nghiệm pin thực tế và chất lượng camera."
        ),
    },
    {
        "figure": "fig_5_2_sentiment_vs_rating_scatter.png",
        "title": "Đối chiếu Điểm sao gốc (Rating) và Điểm cảm xúc văn bản PhoBERT",
        "question": "Có thể tin tưởng hoàn toàn vào điểm đánh giá trung bình 4,5–5 sao trên website bán lẻ hay không?",
        "finding": (
            "Thị trường có hiện tượng 'lạm phát 5 sao' rất mạnh (84,79% đánh giá là 5 sao, trung bình 4,56 sao) kèm 118 trường hợp mâu thuẫn trực diện "
            "(chấm 4–5 sao mặc định nhưng nội dung than phiền máy lỗi, hoặc chấm 1 sao vì giao hàng chậm dù khen máy tốt). PhoBERT đạt Macro F1 = 0,6491 "
            "(vượt Logistic Regression baseline +10,0%) giúp hiệu chỉnh lại sắc thái thực chất của văn bản."
        ),
        "action": (
            "Thay vì dùng điểm sao thô dễ nhiễu và khuyết 73,10% sản phẩm cha (Cold-Start), hệ thống kết hợp cờ độ phủ has_review_data, "
            "điểm cảm xúc văn bản PhoBERT và chỉ số cảm xúc tiên nghiệm theo hãng (brand_sentiment_prior)."
        ),
    },
]


ANOMALY_TYPE_LABELS = {
    "low_price_or_category_noise": "Giá dưới sàn / Sai danh mục (Phụ kiện, Desktop lẫn vào Laptop)",
    "hardware_spec_error": "Lỗi thông số phần cứng (Màn hình, bộ nhớ hoặc chuẩn mạng phi lý)",
    "rare_valid_flagship": "Siêu phẩm cấu hình cao hợp lệ (Flagship / Workstation hiếm)",
    "spec_price_mismatch_review": "Lệch tương quan Giá – Cấu hình cần rà soát",
    "none": "Bình thường (Không gắn cờ)",
}

RECOMMENDED_ACTION_LABELS = {
    "filter_before_modeling": "Loại khỏi phân tích định giá / Chuyển đúng danh mục",
    "verify_or_correct_specs": "Chuẩn hóa / Bóc tách lại thông số từ tên & nguồn",
    "keep_with_log_transform": "Giữ lại (Sản phẩm thật phân khúc cao cấp, dùng log-price)",
    "sensitivity_check": "Rà soát thủ công & Kiểm định độ nhạy (S5)",
    "none": "Không cần can thiệp",
}


def _safe_read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_platform_kpis(catalog: pd.DataFrame | None = None) -> dict[str, Any]:
    flags = _safe_read_csv(TV7_OUT_DIR / "anomaly_flags.csv", usecols=["listing_record_id", "source", "combined_flag"])
    tv6_quality = _safe_read_json(TV6_DOCS_DIR / "quality_report.json")
    canonical = _safe_read_csv(MARKET_GRAPH_DIR / "canonical_products.csv", usecols=["canonical_product_id"])
    holes = _safe_read_csv(MARKET_GRAPH_DIR / "structural_holes.csv", usecols=["gap_type"])

    total_listings = int(len(flags)) if not flags.empty else 10_316
    retailer_count = int(flags["source"].nunique()) if not flags.empty else 5
    metrics = tv6_quality.get("metrics", {})
    total_reviews = int(metrics.get("total_records_all", 15_805))
    usable_reviews = int(metrics.get("total_usable_reviews", 14_869))
    clean_listings = int(len(catalog)) if catalog is not None else 8_132
    canonical_count = int(len(canonical)) if not canonical.empty else 4_414
    flagged_count = int(flags["combined_flag"].astype(str).str.lower().eq("true").sum()) if not flags.empty else 715
    blind_spots = int(holes["gap_type"].eq("retailer_blind_spot").sum()) if not holes.empty else 68
    underserved = int(holes["gap_type"].eq("underserved_high_demand").sum()) if not holes.empty else 22

    return {
        "total_listings": total_listings,
        "retailer_count": retailer_count,
        "total_reviews": total_reviews,
        "usable_reviews": usable_reviews,
        "clean_listings": clean_listings,
        "canonical_products": canonical_count,
        "flagged_anomalies": flagged_count,
        "blind_spots": blind_spots,
        "underserved_segments": underserved,
    }


def get_eda_items(theme_key: str | None = None) -> list[dict[str, Any]]:
    items = []
    for entry in EDA_CHART_GUIDE:
        if theme_key and entry["theme"] != theme_key:
            continue
        items.append({
            **entry,
            "figure_path": EDA_FIG_DIR / entry["figure"],
            "table_path": EDA_TABLE_DIR / entry["table"],
        })
    return items


def load_eda_table(filename: str) -> pd.DataFrame:
    df = _safe_read_csv(EDA_TABLE_DIR / filename)
    return df.loc[:, ~df.columns.str.startswith("Unnamed")]


def load_retailer_stats(category: str) -> pd.DataFrame:
    return _safe_read_csv(MARKET_GRAPH_DIR / f"retailer_degree_stats_{category}.csv")


def load_jaccard_matrix(category: str) -> pd.DataFrame:
    df = _safe_read_csv(MARKET_GRAPH_DIR / f"jaccard_matrix_{category}.csv")
    if not df.empty and df.columns[0].startswith("Unnamed"):
        df = df.rename(columns={df.columns[0]: "Nhà bán lẻ"})
    return df


def load_louvain_segments(category: str | None = None) -> pd.DataFrame:
    df = _safe_read_csv(MARKET_GRAPH_DIR / "louvain_segments.csv")
    if category and not df.empty and "category" in df.columns:
        df = df.loc[df["category"].eq(category)].reset_index(drop=True)
    return df


def load_structural_holes(
    category: str | None = None,
    retailer: str | None = None,
    gap_type: str | None = None,
) -> pd.DataFrame:
    df = _safe_read_csv(MARKET_GRAPH_DIR / "structural_holes.csv")
    if df.empty:
        return df
    if category and category != "all":
        df = df.loc[df["category"].eq(category)]
    if retailer and retailer != "all":
        df = df.loc[df["retailer"].eq(retailer)]
    if gap_type and gap_type != "all":
        df = df.loc[df["gap_type"].eq(gap_type)]
    return df.reset_index(drop=True)


def load_bipartite_html(category: str) -> str | None:
    path = MARKET_GRAPH_DIR / "reports" / f"bipartite_market_graph_{category}.html"
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def load_tv6_lda_topics() -> pd.DataFrame:
    return _safe_read_csv(TV6_DATA_DIR / "tables" / "table_4_1_lda_topics.csv")


def load_tv6_aspect_summary() -> pd.DataFrame:
    return _safe_read_csv(TV6_DATA_DIR / "tables" / "table_4_3_aspect_sentiment_distribution.csv")


def load_tv6_aspect_by_category() -> pd.DataFrame:
    return _safe_read_csv(TV6_DATA_DIR / "tables" / "table_4_4_category_aspect_comparison.csv")


def load_tv6_model_comparison() -> pd.DataFrame:
    return _safe_read_csv(TV6_DATA_DIR / "tables" / "table_3_4_phobert_vs_baseline.csv")


def get_tv6_charts() -> list[dict[str, Any]]:
    return [
        {**entry, "figure_path": TV6_DATA_DIR / "figures" / entry["figure"]}
        for entry in TV6_CHART_GUIDE
    ]


def load_tv7_method_summary() -> pd.DataFrame:
    return _safe_read_csv(TV7_OUT_DIR / "anomaly_method_summary.csv")


def load_tv7_full_flags() -> pd.DataFrame:
    df = _safe_read_csv(
        TV7_OUT_DIR / "anomaly_flags.csv",
        keep_default_na=False,
        dtype={"listing_record_id": str, "source_parent_id": str},
    )
    if df.empty:
        return df
    df["price_vnd"] = pd.to_numeric(df["price_vnd"], errors="coerce")
    df["isolation_score"] = pd.to_numeric(df["isolation_score"], errors="coerce")
    df["methods_agree"] = pd.to_numeric(df["methods_agree"], errors="coerce").fillna(0).astype(int)
    df["combined_flag_bool"] = df["combined_flag"].astype(str).str.lower().eq("true")
    df["anomaly_type"] = df["anomaly_type"].replace("", "none")
    df["recommended_action"] = df["recommended_action"].replace("", "none")
    df["anomaly_type_vi"] = df["anomaly_type"].map(ANOMALY_TYPE_LABELS).fillna(df["anomaly_type"])
    df["recommended_action_vi"] = df["recommended_action"].map(RECOMMENDED_ACTION_LABELS).fillna(df["recommended_action"])
    return df


def summarize_tv7_types(flags_df: pd.DataFrame) -> pd.DataFrame:
    if flags_df.empty:
        return pd.DataFrame()
    flagged = flags_df.loc[flags_df["anomaly_type"].ne("none")].copy()
    summary = (
        flagged.groupby(["anomaly_type", "recommended_action"], as_index=False)
        .agg(
            listing_count=("listing_record_id", "count"),
            extreme_count=("anomaly_severity", lambda s: int(s.eq("extreme").sum())),
            review_count=("anomaly_severity", lambda s: int(s.eq("review").sum())),
        )
        .sort_values("listing_count", ascending=False)
        .reset_index(drop=True)
    )
    summary["share_of_flagged_pct"] = (100.0 * summary["listing_count"] / max(1, len(flagged))).round(2)
    summary["anomaly_type_vi"] = summary["anomaly_type"].map(ANOMALY_TYPE_LABELS).fillna(summary["anomaly_type"])
    summary["recommended_action_vi"] = summary["recommended_action"].map(RECOMMENDED_ACTION_LABELS).fillna(summary["recommended_action"])
    return summary
