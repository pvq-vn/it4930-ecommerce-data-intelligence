"""
Script Thực thi Phân tích Nhiệm vụ 2.2: So sánh chuyên sâu cấu trúc quyết định giá (Pricing Decision Structure)
giữa ngành hàng Laptop và Smartphone.

Đầu ra:
- Figures:
  * src/eda/outputs/figures/fig_2_2_pricing_drivers_comparison.png (300 DPI)
- Tables:
  * src/eda/outputs/tables/table_2_2_pricing_drivers_comparison.md & .csv
  * src/eda/outputs/tables/table_2_2_top_hardware_drivers.md & .csv
  * src/eda/outputs/tables/table_2_2_pricing_structure_matrix.md & .csv
"""

import sys
from pathlib import Path
import pandas as pd
from tabulate import tabulate

# Đảm bảo console Windows không bị lỗi Unicode
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Thêm đường dẫn gốc để import module nội bộ
# Đảm bảo thư mục chứa module eda_stats, eda_viz luôn nằm trong sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
REPO_ROOT = SCRIPTS_DIR.parent.parent.parent
ROOT_DIR = REPO_ROOT
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(1, str(REPO_ROOT))
from eda_stats import (
    load_processed_products,
    compute_head_to_head_comparison,
    build_pricing_structure_matrix,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import plot_pricing_drivers_comparison


def main():
    print("=" * 80)
    print("THỰC THI NHIỆM VỤ 2.2: SO SÁNH CHUYÊN SÂU CẤU TRÚC ĐỊNH GIÁ LAPTOP VS SMARTPHONE")
    print("=" * 80)

    data_path = ROOT_DIR / "data" / "processed" / "products_processed.jsonl"
    tables_dir = ROOT_DIR / "src" / "eda" / "outputs" / "tables"
    figures_dir = ROOT_DIR / "src" / "eda" / "outputs" / "figures"

    # 1. Tải dữ liệu
    print(f"\n[Bước 1/4] Đang tải dữ liệu từ {data_path.name}...")
    df = load_processed_products(str(data_path))
    print(f"  -> Tổng số sản phẩm tải thành công: {len(df):,} bản ghi.")

    # 2. Tính toán ma trận đối chiếu tương quan & nhân tố phân hóa
    print("\n[Bước 2/4] Đang tính toán ma trận đối chiếu tương quan & đòn bẩy giá...")
    corr_df, drivers_df = compute_head_to_head_comparison(df)
    matrix_df = build_pricing_structure_matrix()

    # 3. Xuất các bảng thống kê Markdown & CSV
    print("\n[Bước 3/4] Đang lưu các bảng Markdown & CSV vào src/eda/outputs/tables/...")
    export_dataframe_to_markdown_and_csv(
        corr_df,
        str(tables_dir),
        "table_2_2_pricing_drivers_comparison",
        "Bảng 2.2A: Đối chiếu Tương quan Phần cứng với Giá bán (Laptop vs. Smartphone)"
    )
    export_dataframe_to_markdown_and_csv(
        drivers_df,
        str(tables_dir),
        "table_2_2_top_hardware_drivers",
        "Bảng 2.2B: Các Nhân tố Phân hóa Giá mạnh nhất và Hệ số Đòn bẩy (Price Multiplier)"
    )
    export_dataframe_to_markdown_and_csv(
        matrix_df,
        str(tables_dir),
        "table_2_2_pricing_structure_matrix",
        "Bảng 2.2C: Ma trận Đối chiếu Cấu trúc Quyết định Giá toàn diện (Head-to-Head Comparative Decision Matrix)"
    )

    # 4. Vẽ biểu đồ đối đầu
    print("\n[Bước 4/4] Đang xuất biểu đồ 300 DPI vào src/eda/outputs/figures/...")
    fig_path = figures_dir / "fig_2_2_pricing_drivers_comparison.png"
    plot_pricing_drivers_comparison(df, str(fig_path))
    print(f"  -> Đã lưu biểu đồ: {fig_path.name}")

    print("\n" + "=" * 80)
    print("HOÀN THÀNH TOÀN DIỆN NHIỆM VỤ 2.2!")
    print("=" * 80)


if __name__ == "__main__":
    main()
