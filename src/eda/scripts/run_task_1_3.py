"""
Script thực thi Nhiệm vụ 1.3 (TV3):
Phân tích mức độ thiếu dữ liệu (Missingness Profile) và Bóc tách Ma trận 2 chiều (Source x Category).
"""

import sys
from pathlib import Path

# Thiết lập encoding UTF-8 cho Windows console
sys.stdout.reconfigure(encoding="utf-8")

from eda_stats import (
    load_processed_products,
    compute_overall_missingness,
    compute_missingness_by_category,
    compute_missingness_by_source,
    compute_missingness_matrix_source_category,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import (
    plot_overall_missingness_ranking,
    plot_missingness_heatmap_by_source_category,
    plot_hardware_missingness_comparison
)


def main():
    print("=== BẮT ĐẦU THỰC HIỆN NHIỆM VỤ 1.3 (EDA - TV3) ===")

    # 1. Đọc dữ liệu
    data_path = "data/processed/products_processed.jsonl"
    print(f"[*] Đọc dữ liệu từ: {data_path}")
    df = load_processed_products(data_path)
    total_records = len(df)
    print(f"[+] Tổng số bản ghi quan sát: {total_records:,}")

    tables_dir = "src/eda/outputs/tables"
    figures_dir = "src/eda/outputs/figures"

    # 2. Bảng tổng hợp mức độ thiếu của 30 thuộc tính
    print("\n--- 1. Bảng Tổng hợp Tỷ lệ Thiếu của 30 Thuộc tính (Missingness Profile) ---")
    overall_miss_df = compute_overall_missingness(df)
    print(overall_miss_df.head(15))

    export_dataframe_to_markdown_and_csv(
        overall_miss_df,
        tables_dir,
        "table_1_3_overall_missingness",
        "Bảng 1.10: Tổng hợp Mức độ Thiếu Dữ liệu của 30 Thuộc tính và Phân loại Nghiêm trọng"
    )

    # 3. So sánh tỷ lệ thiếu giữa Laptop và Smartphone
    print("\n--- 2. So sánh Tỷ lệ Thiếu giữa Laptop và Smartphone ---")
    cat_miss_df = compute_missingness_by_category(df)
    print(cat_miss_df.head(15))

    export_dataframe_to_markdown_and_csv(
        cat_miss_df,
        tables_dir,
        "table_1_3_missingness_by_category",
        "Bảng 1.11: So sánh Tỷ lệ Thiếu (%) giữa Laptop và Smartphone kèm Giải thích Bản chất Khác biệt"
    )

    # 4. Phân tích tỷ lệ thiếu theo Nguồn bán (Source)
    print("\n--- 3. Tỷ lệ Thiếu (%) theo từng Nguồn sàn (Source) ---")
    source_miss_df = compute_missingness_by_source(df)
    print(source_miss_df)

    export_dataframe_to_markdown_and_csv(
        source_miss_df,
        tables_dir,
        "table_1_3_missingness_by_source",
        "Bảng 1.12: Tỷ lệ Thiếu (%) của các Đặc trưng Ứng viên theo từng Nguồn cào (Source)"
    )

    # 5. Ma trận 2 chiều (Source x Category)
    print("\n--- 4. Ma trận Phân rã 2 chiều: Nguồn bán x Ngành hàng (Source x Category) ---")
    matrix_2d_df = compute_missingness_matrix_source_category(df)
    print(matrix_2d_df)

    export_dataframe_to_markdown_and_csv(
        matrix_2d_df,
        tables_dir,
        "table_1_3_candidate_features_missingness",
        "Bảng 1.13: Ma trận Tỷ lệ Thiếu (%) của Candidate Features theo Source x Category"
    )

    # 6. Vẽ biểu đồ trực quan hóa
    print("\n--- 5. Vẽ biểu đồ Missingness và lưu artifacts ---")

    fig1 = f"{figures_dir}/fig_1_3_overall_missingness_ranking.png"
    plot_overall_missingness_ranking(overall_miss_df, fig1)
    print(f"[+] Đã lưu biểu đồ: {fig1}")

    fig2 = f"{figures_dir}/fig_1_3_missingness_heatmap_by_source_category.png"
    plot_missingness_heatmap_by_source_category(df, fig2)
    print(f"[+] Đã lưu biểu đồ: {fig2}")

    fig3 = f"{figures_dir}/fig_1_3_hardware_missingness_laptop_vs_phone.png"
    plot_hardware_missingness_comparison(df, fig3)
    print(f"[+] Đã lưu biểu đồ: {fig3}")

    print("\n=== HOÀN THÀNH NHIỆM VỤ 1.3 XUẤT SẮC! ===")


if __name__ == "__main__":
    main()
