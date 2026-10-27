"""
Script thực thi Nhiệm vụ 1.2 (TV3):
Phân tích biến Giá bán (price_vnd, original_price_vnd, discount_rate) và Thử nghiệm biến đổi Log.
"""

import sys
from pathlib import Path

# Thiết lập encoding UTF-8 cho Windows console
sys.stdout.reconfigure(encoding="utf-8")

from eda_stats import (
    load_processed_products,
    compute_price_descriptive_stats,
    compute_price_log_comparison,
    compute_discount_stats_by_source,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import (
    plot_price_distribution_and_log_transform,
    plot_discount_rate_by_source
)


def main():
    print("=== BẮT ĐẦU THỰC HIỆN NHIỆM VỤ 1.2 (EDA - TV3) ===")

    # 1. Đọc dữ liệu
    data_path = "data/processed/products_processed.jsonl"
    print(f"[*] Đọc dữ liệu từ: {data_path}")
    df = load_processed_products(data_path)
    total_records = len(df)
    print(f"[+] Tổng số bản ghi quan sát: {total_records:,}")

    tables_dir = "src/eda/outputs/tables"
    figures_dir = "src/eda/outputs/figures"

    # 2. Thống kê mô tả toàn diện biến Giá
    print("\n--- 1. Thống kê mô tả Giá bán (price_vnd) theo Ngành hàng (Đơn vị: Triệu VNĐ) ---")
    price_stats_df = compute_price_descriptive_stats(df)
    print(price_stats_df)

    export_dataframe_to_markdown_and_csv(
        price_stats_df,
        tables_dir,
        "table_1_2_price_summary_stats",
        "Bảng 1.7: Thống kê mô tả phân phối Giá bán (Triệu VNĐ) và Mức độ lệch chuẩn"
    )

    # 3. So sánh Skewness & Kurtosis trước và sau Log-Transform
    print("\n--- 2. So sánh Phân phối Thang đo Gốc vs Thang đo Log10 ---")
    log_comp_df = compute_price_log_comparison(df)
    print(log_comp_df)

    export_dataframe_to_markdown_and_csv(
        log_comp_df,
        tables_dir,
        "table_1_2_price_log_transform_comparison",
        "Bảng 1.8: So sánh Độ lệch (Skewness) và Độ nhọn (Kurtosis) giữa Thang đo Gốc và Thang đo Log"
    )

    # 4. Thống kê tỷ lệ giảm giá (discount_rate) theo nguồn bán
    print("\n--- 3. Thống kê Tỷ lệ Giảm giá (discount_rate) theo Nguồn bán ---")
    discount_df = compute_discount_stats_by_source(df)
    print(discount_df)

    export_dataframe_to_markdown_and_csv(
        discount_df,
        tables_dir,
        "table_1_2_discount_rate_by_source",
        "Bảng 1.9: Phân phối Tỷ lệ Giảm giá (%) theo từng Sàn giao dịch"
    )

    # 5. Vẽ biểu đồ trực quan hóa
    print("\n--- 4. Vẽ biểu đồ phân phối giá và lưu artifacts ---")

    fig1 = f"{figures_dir}/fig_1_2_price_distribution_and_log_transform.png"
    plot_price_distribution_and_log_transform(df, fig1)
    print(f"[+] Đã lưu biểu đồ: {fig1}")

    fig2 = f"{figures_dir}/fig_1_2_discount_rate_by_source.png"
    plot_discount_rate_by_source(df, fig2)
    print(f"[+] Đã lưu biểu đồ: {fig2}")

    print("\n=== HOÀN THÀNH NHIỆM VỤ 1.2 XUẤT SẮC! ===")


if __name__ == "__main__":
    main()
