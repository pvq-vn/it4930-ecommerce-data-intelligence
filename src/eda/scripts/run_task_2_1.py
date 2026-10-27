"""
Script thực thi Nhiệm vụ 2.1: Phân tích tương quan & Mối liên hệ Cấu hình - Giá bán
(Bivariate Correlations, Hardware Segments & Hypothesis Testing: ANOVA & Kruskal-Wallis)

Thực hiện theo tiêu chuẩn TV3 (docs/tv3/tv3.md) và feature contracts (docs/feature_contracts_tv3_tv8.md).
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Thiết lập UTF-8 cho Windows console
sys.stdout.reconfigure(encoding="utf-8")

from eda_stats import (
    load_processed_products,
    compute_bivariate_correlations,
    classify_laptop_hardware,
    classify_smartphone_hardware,
    compute_group_price_stats,
    perform_hypothesis_tests,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import (
    plot_hardware_correlation_heatmaps,
    plot_hardware_price_relationships_laptop,
    plot_hardware_price_relationships_smartphone
)


def run_task_2_1():
    print("=== BẮT ĐẦU THỰC HIỆN NHIỆM VỤ 2.1 (EDA - TV3) ===")
    
    # 1. Tải dữ liệu
    data_path = "data/processed/products_processed.jsonl"
    print(f"[*] Đọc dữ liệu từ: {data_path}")
    df = load_processed_products(data_path)
    print(f"[+] Tổng số bản ghi quan sát: {len(df):,}")

    tables_dir = "src/eda/outputs/tables"
    figures_dir = "src/eda/outputs/figures"

    # 2. Phân tầng phần cứng Laptop & Smartphone
    print("\n--- 1. Phân tầng Phần cứng (Hardware Classification) ---")
    laptop_df = classify_laptop_hardware(df)
    phone_df = classify_smartphone_hardware(df)
    print(f"[+] Laptop đã gắn nhãn cấu hình: {len(laptop_df):,} bản ghi")
    print(f"[+] Smartphone đã gắn nhãn cấu hình: {len(phone_df):,} bản ghi")

    # 3. Tính ma trận tương quan Bivariate (Pearson & Spearman)
    print("\n--- 2. Tính Tương quan Cấu hình Số với Giá bán (price_vnd & log10(price)) ---")
    laptop_num_cols = ["installed_ram_gb", "storage_gb", "battery_wh", "screen_size_inch", "charger_watt"]
    phone_num_cols = ["installed_ram_gb", "storage_gb", "battery_mah", "screen_size_inch", "charger_watt", "camera_mp"]

    corr_laptop = compute_bivariate_correlations(df, "laptop", laptop_num_cols)
    corr_phone = compute_bivariate_correlations(df, "smartphone", phone_num_cols)

    export_dataframe_to_markdown_and_csv(
        corr_laptop, tables_dir, "table_2_1_laptop_correlations",
        "Bảng 2.1: Hệ số Tương quan Tuyến tính (Pearson) & Phi tuyến (Spearman) - Ngành hàng Laptop"
    )
    export_dataframe_to_markdown_and_csv(
        corr_phone, tables_dir, "table_2_1_smartphone_correlations",
        "Bảng 2.2: Hệ số Tương quan Tuyến tính (Pearson) & Phi tuyến (Spearman) - Ngành hàng Smartphone"
    )
    print("[+] Đã xuất bảng tương quan Laptop & Smartphone.")

    # 4. Thống kê biến thiên Giá theo các phân nhóm phần cứng
    print("\n--- 3. Thống kê Phân phối Giá theo Phân tầng Phần cứng & Thương hiệu ---")
    # Laptop
    stats_laptop_ram = compute_group_price_stats(laptop_df, "ram_group")
    stats_laptop_storage = compute_group_price_stats(laptop_df, "storage_group")
    stats_laptop_cpu = compute_group_price_stats(laptop_df, "cpu_tier")
    stats_laptop_gpu = compute_group_price_stats(laptop_df, "gpu_type")

    export_dataframe_to_markdown_and_csv(
        stats_laptop_ram, tables_dir, "table_2_1_laptop_ram_price",
        "Bảng 2.3: Phân phối Giá bán (Triệu VNĐ) theo Dung lượng RAM - Laptop"
    )
    export_dataframe_to_markdown_and_csv(
        stats_laptop_storage, tables_dir, "table_2_1_laptop_storage_price",
        "Bảng 2.4: Phân phối Giá bán (Triệu VNĐ) theo Dung lượng Ổ cứng - Laptop"
    )
    export_dataframe_to_markdown_and_csv(
        stats_laptop_cpu, tables_dir, "table_2_1_laptop_cpu_tier_price",
        "Bảng 2.5: Phân phối Giá bán (Triệu VNĐ) theo Phân tầng Vi xử lý CPU - Laptop"
    )
    export_dataframe_to_markdown_and_csv(
        stats_laptop_gpu, tables_dir, "table_2_1_laptop_gpu_type_price",
        "Bảng 2.6: Phân phối Giá bán (Triệu VNĐ) theo Phân loại GPU Đồ họa - Laptop"
    )

    # Smartphone
    stats_phone_storage = compute_group_price_stats(phone_df, "storage_group")
    stats_phone_ram = compute_group_price_stats(phone_df, "ram_group")
    stats_phone_brand = compute_group_price_stats(phone_df[phone_df["brand_norm"].isin(["Apple", "Samsung", "Xiaomi", "OPPO", "Vivo", "Realme", "Honor", "Nokia"])], "brand_norm")
    stats_phone_display = compute_group_price_stats(phone_df[phone_df["display_group"].isin(["OLED / AMOLED", "IPS / LCD"])], "display_group")

    export_dataframe_to_markdown_and_csv(
        stats_phone_storage, tables_dir, "table_2_1_phone_storage_price",
        "Bảng 2.7: Phân phối Giá bán (Triệu VNĐ) theo Bộ nhớ ROM - Smartphone"
    )
    export_dataframe_to_markdown_and_csv(
        stats_phone_ram, tables_dir, "table_2_1_phone_ram_price",
        "Bảng 2.8: Phân phối Giá bán (Triệu VNĐ) theo Dung lượng RAM - Smartphone"
    )
    export_dataframe_to_markdown_and_csv(
        stats_phone_brand, tables_dir, "table_2_1_phone_brand_price",
        "Bảng 2.9: Phân phối Giá bán (Triệu VNĐ) theo Top Thương hiệu - Smartphone"
    )
    export_dataframe_to_markdown_and_csv(
        stats_phone_display, tables_dir, "table_2_1_phone_display_price",
        "Bảng 2.10: Phân phối Giá bán (Triệu VNĐ) theo Công nghệ Màn hình - Smartphone"
    )
    print("[+] Đã xuất toàn bộ 8 bảng phân phối giá theo phân tầng cấu hình.")

    # 5. Kiểm định Giả thuyết Thống kê (ANOVA & Kruskal-Wallis)
    print("\n--- 4. Kiểm định Giả thuyết Thống kê (ANOVA F-test & Kruskal-Wallis H-test) ---")
    # Hợp nhất df phân loại để chạy kiểm định
    df_classified = pd.concat([laptop_df, phone_df], axis=0, ignore_index=True)

    test_factors = [
        ("laptop", "Phân tầng CPU (cpu_tier)", "cpu_tier"),
        ("laptop", "Phân loại GPU (gpu_type)", "gpu_type"),
        ("laptop", "Dung lượng RAM (ram_group)", "ram_group"),
        ("laptop", "Dung lượng Ổ cứng (storage_group)", "storage_group"),
        ("laptop", "Thương hiệu Laptop (brand_norm)", "brand_norm"),
        ("smartphone", "Bộ nhớ trong ROM (storage_group)", "storage_group"),
        ("smartphone", "Dung lượng RAM (ram_group)", "ram_group"),
        ("smartphone", "Thương hiệu Smartphone (brand_norm)", "brand_norm"),
        ("smartphone", "Công nghệ Màn hình (display_group)", "display_group"),
    ]

    tests_summary = perform_hypothesis_tests(df_classified, test_factors)
    export_dataframe_to_markdown_and_csv(
        tests_summary, tables_dir, "table_2_1_hypothesis_tests",
        "Bảng 2.11: Bảng Tổng hợp Kết quả Kiểm định Thống kê ANOVA & Kruskal-Wallis về Biến thiên Giá"
    )
    print("[+] Đã xuất bảng kiểm định giả thuyết thống kê.")
    print(tests_summary[["Ngành hàng", "Yếu tố phân loại", "ANOVA F-statistic", "ANOVA p-value", "Kruskal-Wallis H", "Khác biệt có ý nghĩa thống kê?"]])

    # 6. Trực quan hóa dữ liệu và xuất figures
    print("\n--- 5. Vẽ biểu đồ Phân tích và lưu artifacts (300 DPI) ---")
    fig_corr_path = f"{figures_dir}/fig_2_1_hardware_correlation_heatmaps.png"
    plot_hardware_correlation_heatmaps(df, fig_corr_path)
    print(f"[+] Đã lưu biểu đồ: {fig_corr_path}")

    fig_laptop_path = f"{figures_dir}/fig_2_1_hardware_price_relationships_laptop.png"
    plot_hardware_price_relationships_laptop(laptop_df, fig_laptop_path)
    print(f"[+] Đã lưu biểu đồ: {fig_laptop_path}")

    fig_phone_path = f"{figures_dir}/fig_2_1_hardware_price_relationships_smartphone.png"
    plot_hardware_price_relationships_smartphone(phone_df, fig_phone_path)
    print(f"[+] Đã lưu biểu đồ: {fig_phone_path}")

    print("\n=== HOÀN THÀNH NHIỆM VỤ 2.1 XUẤT SẮC! ===")


if __name__ == "__main__":
    run_task_2_1()
