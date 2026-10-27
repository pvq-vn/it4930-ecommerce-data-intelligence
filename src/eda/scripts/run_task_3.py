"""
Script Thực thi Phân tích Nhiệm vụ 3: Đánh giá chất lượng dữ liệu cho bài toán Hồi quy (Regression Readiness Audit).

Nội dung:
- 3.1. Nhận diện Outliers & Dữ liệu biên (16 bản ghi thiếu giá, < 500k, > 100M, phân vị biên P0.1 - P99.9)
- 3.2. Đo lường Đa cộng tuyến (Multicollinearity) & Tính toán VIF
- 3.3. Phòng chống Rò rỉ dữ liệu (Data Leakage Risks Audit)
- 3.4. Đánh giá Tác động của Trạng thái tồn kho (availability_status) & Hiện tượng Price Drift

Đầu ra:
- Tables: src/eda/outputs/tables/
  * table_3_1_price_invalid_records.md & .csv
  * table_3_1_price_percentiles_boundaries.md & .csv
  * table_3_1_price_extreme_outliers.md & .csv
  * table_3_2_multicollinearity_vif.md & .csv
  * table_3_2_cross_correlation_laptop.md & .csv
  * table_3_2_cross_correlation_smartphone.md & .csv
  * table_3_3_data_leakage_audit.md & .csv
  * table_3_4_availability_status_stats.md & .csv
  * table_3_4_availability_hypothesis_test.md & .csv
- Figures: src/eda/outputs/figures/ (300 DPI)
  * fig_3_1_price_outliers_and_boundaries.png
  * fig_3_2_multicollinearity_and_vif.png
  * fig_3_3_availability_price_comparison.png
"""

import sys
from pathlib import Path
import pandas as pd

# Đảm bảo console Windows không bị lỗi Unicode
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm đường dẫn gốc để import module EDA nội bộ
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src" / "eda" / "scripts"))

from eda_stats import (
    load_processed_products,
    audit_price_outliers_and_boundaries,
    compute_multicollinearity_and_vif,
    audit_data_leakage_risks,
    analyze_availability_status_impact,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import (
    plot_price_outliers_and_boundaries,
    plot_multicollinearity_and_vif,
    plot_availability_price_comparison
)


def run_task_3():
    print("=" * 80)
    print("THỰC THI NHIỆM VỤ 3: ĐÁNH GIÁ CHẤT LƯỢNG DỮ LIỆU BÀI TOÁN HỒI QUY (TV3 - EDA)")
    print("=" * 80)

    data_path = ROOT_DIR / "data" / "processed" / "products_processed.jsonl"
    tables_dir = str(ROOT_DIR / "src" / "eda" / "outputs" / "tables")
    figures_dir = ROOT_DIR / "src" / "eda" / "outputs" / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tải dữ liệu
    print(f"\n[Bước 1/5] Đang đọc dữ liệu sạch từ {data_path.name}...")
    df = load_processed_products(str(data_path))
    print(f"  -> Tổng số bản ghi quan sát: {len(df):,}")

    # 2. Tiểu mục 3.1: Nhận diện Outliers & Dữ liệu biên
    print("\n[Bước 2/5] Đang kiểm toán Outliers và Dữ liệu biên (Task 3.1)...")
    invalid_summary, boundary_df, outlier_summary = audit_price_outliers_and_boundaries(df)
    export_dataframe_to_markdown_and_csv(
        invalid_summary, tables_dir, "table_3_1_price_invalid_records",
        "Bảng 3.1A: Kiểm toán các Bản ghi Giá Thiếu và Không Hợp lệ (Invalid & Missing Prices)"
    )
    export_dataframe_to_markdown_and_csv(
        boundary_df, tables_dir, "table_3_1_price_percentiles_boundaries",
        "Bảng 3.1B: Phân vị Cực biên (P0.1 - P99.9) và Ranh giới Tukey Fences của Giá bán"
    )
    export_dataframe_to_markdown_and_csv(
        outlier_summary, tables_dir, "table_3_1_price_extreme_outliers",
        "Bảng 3.1C: Nhận diện và Đánh giá Nhóm Giá Ngoại lai Cực biên (< 500k và > 100M)"
    )
    fig_3_1_path = figures_dir / "fig_3_1_price_outliers_and_boundaries.png"
    plot_price_outliers_and_boundaries(df, str(fig_3_1_path))
    print(f"  -> Đã lưu biểu đồ: {fig_3_1_path.name}")

    # 3. Tiểu mục 3.2: Đo lường Đa cộng tuyến & Tính toán VIF
    print("\n[Bước 3/5] Đang đo lường Đa cộng tuyến và Tính toán VIF (Task 3.2)...")
    lap_corr, ph_corr, vif_df = compute_multicollinearity_and_vif(df)
    export_dataframe_to_markdown_and_csv(
        lap_corr.reset_index().rename(columns={"index": "Feature"}),
        tables_dir, "table_3_2_cross_correlation_laptop",
        "Bảng 3.2A: Ma trận Tương quan Chéo giữa các Biến Cấu hình Độc lập (Laptop)"
    )
    export_dataframe_to_markdown_and_csv(
        ph_corr.reset_index().rename(columns={"index": "Feature"}),
        tables_dir, "table_3_2_cross_correlation_smartphone",
        "Bảng 3.2B: Ma trận Tương quan Chéo giữa các Biến Cấu hình Độc lập (Smartphone)"
    )
    export_dataframe_to_markdown_and_csv(
        vif_df, tables_dir, "table_3_2_multicollinearity_vif",
        "Bảng 3.2C: Bảng Chỉ số Phóng đại Phương sai (Variance Inflation Factor - VIF)"
    )
    fig_3_2_path = figures_dir / "fig_3_2_multicollinearity_and_vif.png"
    plot_multicollinearity_and_vif(df, str(fig_3_2_path))
    print(f"  -> Đã lưu biểu đồ: {fig_3_2_path.name}")

    # 4. Tiểu mục 3.3: Phòng chống Rò rỉ dữ liệu (Data Leakage Audit)
    print("\n[Bước 4/5] Đang rà soát và kiểm toán Rủi ro Rò rỉ Dữ liệu (Task 3.3)...")
    leakage_df = audit_data_leakage_risks()
    export_dataframe_to_markdown_and_csv(
        leakage_df, tables_dir, "table_3_3_data_leakage_audit",
        "Bảng 3.3: Ma trận Kiểm toán Rủi ro Rò rỉ Dữ liệu (Data Leakage Audit Matrix for TV5)"
    )

    # 5. Tiểu mục 3.4: Tác động của Trạng thái Tồn kho (availability_status)
    print("\n[Bước 5/5] Đang đánh giá tác động của Trạng thái Tồn kho & Price Drift (Task 3.4)...")
    status_stats, status_test = analyze_availability_status_impact(df)
    export_dataframe_to_markdown_and_csv(
        status_stats, tables_dir, "table_3_4_availability_status_stats",
        "Bảng 3.4A: Thống kê Phân phối Giá theo Trạng thái Tồn kho (in_stock vs. out_of_stock)"
    )
    export_dataframe_to_markdown_and_csv(
        status_test, tables_dir, "table_3_4_availability_hypothesis_test",
        "Bảng 3.4B: Kiểm định Mann-Whitney U test về Hiện tượng Lệch Giá (Price Drift) của Hàng Hết Tồn kho"
    )
    fig_3_3_path = figures_dir / "fig_3_3_availability_price_comparison.png"
    plot_availability_price_comparison(df, str(fig_3_3_path))
    print(f"  -> Đã lưu biểu đồ: {fig_3_3_path.name}")

    print("\n" + "=" * 80)
    print("HOÀN THÀNH TOÀN DIỆN NHIỆM VỤ 3!")
    print("=" * 80)


if __name__ == "__main__":
    run_task_3()
