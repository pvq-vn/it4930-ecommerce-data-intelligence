"""
Script thực thi Nhiệm vụ 1.1 (TV3):
Phân tích phân phối sản phẩm, thị phần thương hiệu và nguồn bán.
"""

import sys
from pathlib import Path

# Thiết lập encoding UTF-8 cho stdout trên Windows
sys.stdout.reconfigure(encoding="utf-8")

from eda_stats import (
    load_processed_products,
    get_source_category_crosstab,
    get_brand_market_share,
    get_seller_distribution,
    export_dataframe_to_markdown_and_csv
)
from eda_viz import (
    plot_source_category_distribution,
    plot_brand_market_share_comparison,
    plot_seller_share
)


def main():
    print("=== BẮT ĐẦU THỰC HIỆN NHIỆM VỤ 1.1 (EDA - TV3) ===")

    # 1. Tải dữ liệu
    data_path = "data/processed/products_processed.jsonl"
    print(f"[*] Đọc dữ liệu từ: {data_path}")
    df = load_processed_products(data_path)
    total_records = len(df)
    print(f"[+] Tổng số bản ghi quan sát: {total_records:,}")

    tables_dir = "src/eda/outputs/tables"
    figures_dir = "src/eda/outputs/figures"

    # 2. Phân tích phân phối Source x Category
    print("\n--- 1. Bảng chéo Nguồn bán (Source) x Ngành hàng (Category) ---")
    ct_counts, ct_pct = get_source_category_crosstab(df)
    print(ct_counts)
    
    export_dataframe_to_markdown_and_csv(
        ct_counts,
        tables_dir,
        "table_1_1_source_category_counts",
        "Bảng 1.1: Phân bố số lượng sản phẩm theo Nguồn bán và Ngành hàng"
    )
    export_dataframe_to_markdown_and_csv(
        ct_pct,
        tables_dir,
        "table_1_1_source_category_percentages",
        "Bảng 1.2: Tỷ lệ phần trăm (%) sản phẩm theo Nguồn bán và Ngành hàng"
    )

    # 3. Phân tích thị phần thương hiệu (Brand Market Share)
    print("\n--- 2. Thị phần thương hiệu (Brand Market Share) ---")
    brand_dict = get_brand_market_share(df, top_n=10)
    
    print("\nTop 10 Hãng Laptop:")
    print(brand_dict["laptop"])
    export_dataframe_to_markdown_and_csv(
        brand_dict["laptop"],
        tables_dir,
        "table_1_1_laptop_brand_share",
        "Bảng 1.3: Thị phần Top 10 Thương hiệu Laptop"
    )

    print("\nTop 10 Hãng Smartphone:")
    print(brand_dict["smartphone"])
    export_dataframe_to_markdown_and_csv(
        brand_dict["smartphone"],
        tables_dir,
        "table_1_1_smartphone_brand_share",
        "Bảng 1.4: Thị phần Top 10 Thương hiệu Smartphone"
    )

    export_dataframe_to_markdown_and_csv(
        brand_dict["overall"],
        tables_dir,
        "table_1_1_overall_brand_share",
        "Bảng 1.5: Thị phần Top 10 Thương hiệu Toàn bộ Listing"
    )

    # 4. Phân tích phân phối nhà bán lẻ (Seller)
    print("\n--- 3. Phân phối nhà bán lẻ (Seller) ---")
    seller_df = get_seller_distribution(df)
    print(seller_df)
    export_dataframe_to_markdown_and_csv(
        seller_df,
        tables_dir,
        "table_1_1_seller_distribution",
        "Bảng 1.6: Phân phối sản phẩm theo Nhà bán lẻ (seller_raw)"
    )

    # 5. Vẽ biểu đồ trực quan hóa
    print("\n--- 4. Vẽ biểu đồ và lưu artifacts ---")
    
    fig1 = f"{figures_dir}/fig_1_1_source_category_distribution.png"
    plot_source_category_distribution(df, fig1)
    print(f"[+] Đã lưu biểu đồ: {fig1}")

    fig2 = f"{figures_dir}/fig_1_1_brand_market_share.png"
    plot_brand_market_share_comparison(brand_dict, fig2)
    print(f"[+] Đã lưu biểu đồ: {fig2}")

    fig3 = f"{figures_dir}/fig_1_1_seller_market_share.png"
    plot_seller_share(seller_df, fig3)
    print(f"[+] Đã lưu biểu đồ: {fig3}")

    print("\n=== HOÀN THÀNH NHIỆM VỤ 1.1 XUẤT SẮC! ===")


if __name__ == "__main__":
    main()
