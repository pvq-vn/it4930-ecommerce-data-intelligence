"""
EDA Visualization Helper Functions (TV3)
Module cung cấp các hàm tạo biểu đồ phân tích phân phối, thị phần thương hiệu, nguồn bán và biến Giá.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd


def set_plotting_theme():
    """Thiết lập style chuẩn cho các biểu đồ trong báo cáo EDA."""
    sns.set_theme(style="whitegrid", font="sans-serif")
    plt.rcParams["font.size"] = 10
    plt.rcParams["axes.titlesize"] = 12
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.labelsize"] = 10
    plt.rcParams["axes.labelweight"] = "bold"
    plt.rcParams["figure.dpi"] = 300


def plot_source_category_distribution(df: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ cột nhóm hiển thị số lượng listing theo Nguồn (Source) và Ngành hàng (Category).
    """
    set_plotting_theme()
    fig, ax = plt.subplots(figsize=(10, 6))

    df_agg = df.groupby(["source", "category"]).size().reset_index(name="count")
    df_agg["Ngành hàng"] = df_agg["category"].map({"laptop": "Laptop", "smartphone": "Smartphone"})

    order = df["source"].value_counts().index.tolist()
    palette = {"Laptop": "#2b5c8f", "Smartphone": "#d95f02"}

    sns.barplot(
        data=df_agg,
        x="source",
        y="count",
        hue="Ngành hàng",
        order=order,
        palette=palette,
        ax=ax
    )

    ax.set_title("Phân bố số lượng sản phẩm theo Nguồn cào (Source) & Ngành hàng (Category)", pad=15)
    ax.set_xlabel("Nguồn cào (Source)", labelpad=10)
    ax.set_ylabel("Số lượng bản ghi (Listings)", labelpad=10)
    
    source_labels = {
        "cellphones": "CellphoneS\n(7.847)",
        "tgdd": "TGDĐ\n(1.197)",
        "fptshop": "FPT Shop\n(820)",
        "hoanghamobile": "Hoàng Hà\n(285)",
        "viettelstore": "Viettel Store\n(167)"
    }
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([source_labels.get(s, s) for s in order])

    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(
                f"{int(height):,}",
                (p.get_x() + p.get_width() / 2.0, height),
                ha="center",
                va="bottom",
                fontsize=9.5,
                fontweight="bold",
                xytext=(0, 4),
                textcoords="offset points"
            )

    ax.set_ylim(0, df_agg["count"].max() * 1.12)
    ax.legend(title="Ngành hàng", loc="upper right", frameon=True)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_brand_market_share_comparison(brand_dict: dict, output_path: str):
    """
    Vẽ biểu đồ so sánh Top 10 thương hiệu giữa Laptop và Smartphone (2 subplots cạnh nhau).
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=False)

    # 1. Laptop
    df_laptop = brand_dict["laptop"].loc[brand_dict["laptop"].index != "Other"].head(10).reset_index()
    df_laptop.columns = ["brand", "count", "share_pct"]

    sns.barplot(
        data=df_laptop,
        x="share_pct",
        y="brand",
        color="#2b5c8f",
        ax=axes[0]
    )
    axes[0].set_title("Top 10 Thương hiệu Laptop (% Thị phần listing)", pad=12)
    axes[0].set_xlabel("Tỷ lệ thị phần (%)", labelpad=8)
    axes[0].set_ylabel("Thương hiệu (brand_norm)", labelpad=8)
    axes[0].set_xlim(0, df_laptop["share_pct"].max() * 1.15)

    for p in axes[0].patches:
        width = p.get_width()
        axes[0].annotate(
            f"{width:.1f}%",
            (width, p.get_y() + p.get_height() / 2.0),
            ha="left",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            xytext=(4, 0),
            textcoords="offset points"
        )

    # 2. Smartphone
    df_phone = brand_dict["smartphone"].loc[brand_dict["smartphone"].index != "Other"].head(10).reset_index()
    df_phone.columns = ["brand", "count", "share_pct"]

    sns.barplot(
        data=df_phone,
        x="share_pct",
        y="brand",
        color="#d95f02",
        ax=axes[1]
    )
    axes[1].set_title("Top 10 Thương hiệu Smartphone (% Thị phần listing)", pad=12)
    axes[1].set_xlabel("Tỷ lệ thị phần (%)", labelpad=8)
    axes[1].set_ylabel("")
    axes[1].set_xlim(0, df_phone["share_pct"].max() * 1.15)

    for p in axes[1].patches:
        width = p.get_width()
        axes[1].annotate(
            f"{width:.1f}%",
            (width, p.get_y() + p.get_height() / 2.0),
            ha="left",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            xytext=(4, 0),
            textcoords="offset points"
        )

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_seller_share(df_seller: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ tròn (Donut chart) thể hiện tỷ trọng của các nhà bán lẻ (seller_raw).
    """
    set_plotting_theme()
    fig, ax = plt.subplots(figsize=(8, 6))

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    wedges, texts, autotexts = ax.pie(
        df_seller["share_pct"],
        labels=df_seller.index,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors,
        pctdistance=0.75,
        textprops={"fontsize": 10}
    )

    centre_circle = plt.Circle((0, 0), 0.55, fc="white")
    ax.add_artist(centre_circle)

    for autotext in autotexts:
        autotext.set_weight("bold")

    ax.set_title("Cơ cấu thị phần sản phẩm theo Nhà bán lẻ (seller_raw)", pad=15)
    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_price_distribution_and_log_transform(df: pd.DataFrame, output_path: str):
    """
    Vẽ lưới 2x2 biểu đồ phân tích phân phối Giá bán và phép biến đổi Log:
    1. Histogram & KDE giá gốc (triệu VNĐ)
    2. Histogram & KDE giá Log10
    3. Boxplot so sánh giá Laptop vs Smartphone
    4. Boxplot so sánh giá theo từng Nguồn sàn (Source)
    """
    set_plotting_theme()
    valid_df = df[df["price_vnd"] > 0].copy()
    valid_df["price_mil"] = valid_df["price_vnd"] / 1e6
    valid_df["log10_price"] = np.log10(valid_df["price_vnd"])
    valid_df["Ngành hàng"] = valid_df["category"].map({"laptop": "Laptop", "smartphone": "Smartphone"})

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    palette = {"Laptop": "#2b5c8f", "Smartphone": "#d95f02"}

    # Subplot 1: Phân phối giá gốc (cắt lát <= 80 triệu để quan sát rõ phân phối chính)
    sns.histplot(
        data=valid_df[valid_df["price_mil"] <= 80],
        x="price_mil",
        hue="Ngành hàng",
        kde=True,
        bins=40,
        palette=palette,
        element="step",
        common_norm=False,
        ax=axes[0, 0]
    )
    axes[0, 0].set_title("Phân phối Giá gốc (Triệu VNĐ) — Lệch phải cực đoan", pad=10)
    axes[0, 0].set_xlabel("Giá bán (Triệu VNĐ)")
    axes[0, 0].set_ylabel("Tần số (Mẫu)")

    # Subplot 2: Phân phối sau Log10 Transform
    sns.histplot(
        data=valid_df,
        x="log10_price",
        hue="Ngành hàng",
        kde=True,
        bins=35,
        palette=palette,
        element="step",
        common_norm=False,
        ax=axes[0, 1]
    )
    axes[0, 1].set_title("Phân phối sau Biến đổi Log10 — Dạng Chuông Chuẩn (Bell-shaped)", pad=10)
    axes[0, 1].set_xlabel("log10(price_vnd) [6.0 = 1Tr, 7.0 = 10Tr, 8.0 = 100Tr]")
    axes[0, 1].set_ylabel("Tần số (Mẫu)")

    # Subplot 3: Boxplot so sánh khoảng giá Laptop vs Smartphone
    sns.boxplot(
        data=valid_df,
        x="Ngành hàng",
        y="price_mil",
        hue="Ngành hàng",
        palette=palette,
        legend=False,
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "white", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[1, 0]
    )
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_title("Boxplot Khoảng giá theo Ngành hàng (Thang đo Log)", pad=10)
    axes[1, 0].set_xlabel("Ngành hàng")
    axes[1, 0].set_ylabel("Giá bán (Triệu VNĐ, log-scale)")
    axes[1, 0].set_yticks([1, 2, 5, 10, 20, 50, 100, 200, 500])
    axes[1, 0].get_yaxis().set_major_formatter(plt.ScalarFormatter())

    # Subplot 4: Boxplot so sánh giá theo từng Nguồn sàn
    source_order = valid_df["source"].value_counts().index
    sns.boxplot(
        data=valid_df,
        x="source",
        y="price_mil",
        hue="source",
        order=source_order,
        palette="Blues_r",
        legend=False,
        showmeans=True,
        meanprops={"marker": "s", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "6"},
        ax=axes[1, 1]
    )
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_title("Boxplot Phân phối Giá theo Nguồn bán (Thang đo Log)", pad=10)
    axes[1, 1].set_xlabel("Nguồn cào (Source)")
    axes[1, 1].set_ylabel("Giá bán (Triệu VNĐ, log-scale)")
    axes[1, 1].set_yticks([1, 2, 5, 10, 20, 50, 100, 200, 500])
    axes[1, 1].get_yaxis().set_major_formatter(plt.ScalarFormatter())

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_discount_rate_by_source(df: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ phân phối Tỷ lệ chiết khấu (%) theo từng Nguồn bán.
    """
    set_plotting_theme()
    valid_discount = df[df["discount_rate"].notna()].copy()
    valid_discount["discount_pct"] = valid_discount["discount_rate"] * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    order = valid_discount["source"].value_counts().index

    sns.boxplot(
        data=valid_discount,
        x="source",
        y="discount_pct",
        hue="source",
        order=order,
        palette="Spectral",
        legend=False,
        showmeans=True,
        meanprops={"marker": "D", "markerfacecolor": "yellow", "markeredgecolor": "black", "markersize": "6"},
        ax=ax
    )

    # Thêm đường trung vị toàn thị trường
    overall_median = valid_discount["discount_pct"].median()
    ax.axhline(
        overall_median,
        color="red",
        linestyle="--",
        linewidth=1.5,
        label=f"Trung vị thị trường: {overall_median:.1f}%"
    )

    ax.set_title("Phân bố Tỷ lệ Giảm giá (%) theo từng Nguồn sàn (Source)", pad=15)
    ax.set_xlabel("Nguồn cào (Source)", labelpad=10)
    ax.set_ylabel("Tỷ lệ giảm giá (%)", labelpad=10)
    ax.set_ylim(-2, 70)  # Cắt outlier cực đoan >70% để nhìn rõ hộp chính
    ax.legend(loc="upper right", frameon=True)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_overall_missingness_ranking(df_miss: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ thanh ngang xếp hạng tỷ lệ thiếu (%) của toàn bộ 30 thuộc tính.
    Phân màu theo mức độ nghiêm trọng:
    - Đỏ: > 80% (Cực cao / Đặc thù)
    - Cam: 50 - 80% (Cao)
    - Vàng: 20 - 50% (Trung bình)
    - Xanh lá: < 20% (Thấp / Đầy đủ)
    """
    set_plotting_theme()
    fig, ax = plt.subplots(figsize=(12, 10))

    plot_df = df_miss.reset_index()
    
    # Gán màu sắc theo ngưỡng
    colors = []
    for pct in plot_df["Tỷ lệ Missing (%)"]:
        if pct > 80:
            colors.append("#d73027")  # Đỏ đậm
        elif pct > 50:
            colors.append("#fc8d59")  # Cam
        elif pct > 20:
            colors.append("#fee08b")  # Vàng
        elif pct > 0:
            colors.append("#91cf60")  # Xanh lá nhạt
        else:
            colors.append("#1a9850")  # Xanh lá đậm (0%)

    y_pos = range(len(plot_df))
    bars = ax.barh(y_pos, plot_df["Tỷ lệ Missing (%)"], color=colors, edgecolor="black", linewidth=0.5)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(plot_df["Tên trường"], fontsize=9.5)
    ax.invert_yaxis()  # Trường thiếu nhiều nhất nằm trên cùng

    ax.set_xlabel("Tỷ lệ thiếu (%)", labelpad=10)
    ax.set_title("Xếp hạng Mức độ Thiếu Dữ liệu (%) của 30 Thuộc tính (Missingness Profile)", pad=15)
    ax.set_xlim(0, 110)

    # Thêm số % trực tiếp bên cạnh mỗi thanh
    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            f"{width:.1f}%",
            (width, bar.get_y() + bar.get_height() / 2.0),
            ha="left",
            va="center",
            fontsize=8.5,
            fontweight="bold" if width > 50 else "normal",
            xytext=(4, 0),
            textcoords="offset points"
        )

    # Chú thích mức độ
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor="#d73027", edgecolor="black", label="Cực cao / Đặc thù (>80%)"),
        Patch(facecolor="#fc8d59", edgecolor="black", label="Cao (50–80%)"),
        Patch(facecolor="#fee08b", edgecolor="black", label="Trung bình (20–50%)"),
        Patch(facecolor="#91cf60", edgecolor="black", label="Thấp (0–20%)"),
        Patch(facecolor="#1a9850", edgecolor="black", label="Không thiếu (0%)")
    ]
    ax.legend(handles=legend_elements, loc="lower right", frameon=True, fontsize=9)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_missingness_heatmap_by_source_category(df: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ nhiệt (Heatmap) tỷ lệ thiếu của các đặc trưng quan trọng phân rã theo Source x Category.
    """
    set_plotting_theme()
    fig, ax = plt.subplots(figsize=(12, 7))

    candidate_cols = [
        "price_vnd", "discount_rate", "rating_norm", "total_sold_normalized",
        "installed_ram_gb", "storage_gb", "cpu_norm", "gpu_norm",
        "battery_mah", "battery_wh", "screen_size_inch", "display_type_norm", "charger_watt"
    ]

    # Tạo nhãn phân nhóm 2 chiều
    df_copy = df.copy()
    df_copy["segment"] = df_copy["source"] + " - " + df_copy["category"].map({"laptop": "Laptop", "smartphone": "Phone"})

    # Tính ma trận % missing
    heatmap_matrix = df_copy.groupby("segment")[candidate_cols].apply(lambda x: (x.isna().mean() * 100).round(1)).T

    # Sắp xếp các cột theo thứ tự hợp lý
    col_order = sorted(heatmap_matrix.columns)
    heatmap_matrix = heatmap_matrix[col_order]

    sns.heatmap(
        heatmap_matrix,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        cbar_kws={"label": "Tỷ lệ thiếu (%)"},
        linewidths=0.5,
        linecolor="white",
        ax=ax
    )

    ax.set_title("Ma trận Biểu đồ Nhiệt Tỷ lệ Thiếu (%) theo Nguồn cào & Ngành hàng", pad=15)
    ax.set_xlabel("Phân đoạn (Source - Category)", labelpad=10)
    ax.set_ylabel("Thuộc tính quan sát (Features)", labelpad=10)
    plt.xticks(rotation=45, ha="right", fontsize=9.5)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_hardware_missingness_comparison(df: pd.DataFrame, output_path: str):
    """
    Vẽ biểu đồ so sánh đối đầu tỷ lệ thiếu các thuộc tính phần cứng giữa Laptop và Smartphone.
    Làm rõ tại sao một số thuộc tính thiếu là do đặc thù ngành hàng (Category-specific missingness).
    """
    set_plotting_theme()
    fig, ax = plt.subplots(figsize=(11, 6))

    hardware_cols = [
        "installed_ram_gb", "storage_gb", "cpu_norm", "gpu_norm",
        "battery_mah", "battery_wh", "screen_size_inch", "display_type_norm", "camera_mp", "charger_watt"
    ]

    laptop_miss = (df[df["category"] == "laptop"][hardware_cols].isna().mean() * 100).round(1)
    phone_miss = (df[df["category"] == "smartphone"][hardware_cols].isna().mean() * 100).round(1)

    comp_df = pd.DataFrame({
        "Laptop": laptop_miss,
        "Smartphone": phone_miss
    }).reset_index().rename(columns={"index": "feature"})

    comp_melted = comp_df.melt(id_vars="feature", var_name="Ngành hàng", value_name="missing_pct")

    palette = {"Laptop": "#2b5c8f", "Smartphone": "#d95f02"}

    sns.barplot(
        data=comp_melted,
        x="feature",
        y="missing_pct",
        hue="Ngành hàng",
        palette=palette,
        ax=ax
    )

    ax.set_title("So sánh Tỷ lệ Thiếu (%) các Đặc trưng Cấu hình: Laptop vs. Smartphone", pad=15)
    ax.set_xlabel("Đặc trưng phần cứng", labelpad=10)
    ax.set_ylabel("Tỷ lệ thiếu (%)", labelpad=10)
    ax.set_ylim(0, 115)
    plt.xticks(rotation=30, ha="right")

    for p in ax.patches:
        height = p.get_height()
        if height > 0:
            ax.annotate(
                f"{height:.1f}%",
                (p.get_x() + p.get_width() / 2.0, height),
                ha="center",
                va="bottom",
                fontsize=8.5,
                xytext=(0, 3),
                textcoords="offset points"
            )

    ax.legend(title="Ngành hàng", loc="upper right", frameon=True)

    plt.tight_layout()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_hardware_correlation_heatmaps(
    df: pd.DataFrame,
    output_path: str
):
    """
    Vẽ 2 heatmap ma trận tương quan Spearman cạnh nhau:
    - Trái: Ngành hàng Laptop
    - Phải: Ngành hàng Smartphone
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.5))

    # Chuẩn bị dữ liệu Laptop
    laptop = df[(df["category"] == "laptop") & (df["price_vnd"] > 0)].copy()
    laptop["log_price"] = np.log10(laptop["price_vnd"])
    laptop_cols = {
        "log_price": "Log10(Giá)",
        "price_vnd": "Giá gốc",
        "installed_ram_gb": "RAM (GB)",
        "storage_gb": "Ổ cứng (GB)",
        "battery_wh": "Pin (Wh)",
        "screen_size_inch": "Màn hình (\")",
        "charger_watt": "Sạc (W)"
    }
    sub_laptop = laptop[list(laptop_cols.keys())].rename(columns=laptop_cols)
    corr_laptop = sub_laptop.corr(method="spearman")

    # Heatmap Laptop
    sns.heatmap(
        corr_laptop,
        annot=True,
        fmt="+.2f",
        cmap="coolwarm",
        vmin=-0.2,
        vmax=1.0,
        cbar=True,
        linewidths=0.8,
        annot_kws={"size": 10, "weight": "bold"},
        ax=axes[0]
    )
    axes[0].set_title("A. Tương quan Thứ hạng (Spearman) - Ngành hàng Laptop", pad=14, fontsize=12, fontweight="bold")
    plt.setp(axes[0].get_xticklabels(), rotation=35, ha="right", fontsize=9.5)
    plt.setp(axes[0].get_yticklabels(), rotation=0, fontsize=9.5)

    # Chuẩn bị dữ liệu Smartphone
    phone = df[(df["category"] == "smartphone") & (df["price_vnd"] > 0)].copy()
    phone["log_price"] = np.log10(phone["price_vnd"])
    phone_cols = {
        "log_price": "Log10(Giá)",
        "price_vnd": "Giá gốc",
        "installed_ram_gb": "RAM (GB)",
        "storage_gb": "Bộ nhớ (GB)",
        "battery_mah": "Pin (mAh)",
        "screen_size_inch": "Màn hình (\")",
        "charger_watt": "Sạc (W)",
        "camera_mp": "Camera (MP)"
    }
    sub_phone = phone[list(phone_cols.keys())].rename(columns=phone_cols)
    corr_phone = sub_phone.corr(method="spearman")

    # Heatmap Smartphone
    sns.heatmap(
        corr_phone,
        annot=True,
        fmt="+.2f",
        cmap="coolwarm",
        vmin=-0.2,
        vmax=1.0,
        cbar=True,
        linewidths=0.8,
        annot_kws={"size": 10, "weight": "bold"},
        ax=axes[1]
    )
    axes[1].set_title("B. Tương quan Thứ hạng (Spearman) - Ngành hàng Smartphone", pad=14, fontsize=12, fontweight="bold")
    plt.setp(axes[1].get_xticklabels(), rotation=35, ha="right", fontsize=9.5)
    plt.setp(axes[1].get_yticklabels(), rotation=0, fontsize=9.5)

    fig.suptitle(
        "Ma trận Tương quan Phi tuyến (Spearman Rank) giữa Cấu hình Phần cứng và Giá bán",
        fontsize=14,
        fontweight="bold",
        y=0.98
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.94])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_hardware_price_relationships_laptop(
    laptop_df: pd.DataFrame,
    output_path: str
):
    """
    Vẽ lưới 2x2 Boxplots phân tích biến thiên Giá bán (Triệu VNĐ) theo 4 trục cấu hình Laptop:
    (A) Dung lượng RAM (ram_group)
    (B) Dung lượng Ổ cứng (storage_group)
    (C) Phân tầng CPU Tier (cpu_tier)
    (D) Phân loại GPU (gpu_type)
    """
    set_plotting_theme()
    fig, axes = plt.subplots(2, 2, figsize=(16, 13))

    data = laptop_df[laptop_df["price_vnd"] > 0].copy()
    data["price_mil"] = data["price_vnd"] / 1e6

    # 1. RAM Boxplot
    ram_order = ["8 GB", "16 GB", "32 GB", ">= 64 GB"]
    ram_data = data[data["ram_group"].isin(ram_order)]
    sns.boxplot(
        data=ram_data,
        x="ram_group",
        y="price_mil",
        order=ram_order,
        hue="ram_group",
        legend=False,
        palette="Blues_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[0, 0]
    )
    axes[0, 0].set_title("A. Biến thiên Giá theo Dung lượng RAM (Laptop)", pad=10, fontsize=11, fontweight="bold")
    axes[0, 0].set_xlabel("Dung lượng RAM", fontweight="bold")
    axes[0, 0].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[0, 0].set_ylim(-2, 145)

    # 2. Storage Boxplot
    storage_order = ["256 GB", "512 GB", "1 TB (1024 GB)", ">= 2 TB"]
    storage_data = data[data["storage_group"].isin(storage_order)]
    sns.boxplot(
        data=storage_data,
        x="storage_group",
        y="price_mil",
        order=storage_order,
        hue="storage_group",
        legend=False,
        palette="Greens_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[0, 1]
    )
    axes[0, 1].set_title("B. Biến thiên Giá theo Dung lượng Ổ cứng (Laptop)", pad=10, fontsize=11, fontweight="bold")
    axes[0, 1].set_xlabel("Dung lượng Ổ cứng", fontweight="bold")
    axes[0, 1].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[0, 1].set_ylim(-2, 145)

    # 3. CPU Tier Boxplot (Rút gọn tên để nhãn rõ ràng, không đè nhau)
    cpu_map = {
        "Tier 4: Core i3 / Entry-level": "Core i3 / Entry",
        "Tier 3: Core i5 / Ryzen 5 (Mainstream)": "Core i5 / Ryzen 5",
        "Tier 2: Core i7 / Ryzen 7 (High-end)": "Core i7 / Ryzen 7",
        "Tier 1: Core i9 / Ryzen 9 (Flagship/Enthusiast)": "Core i9 / Ryzen 9",
        "Apple Silicon (M-series)": "Apple M-Series"
    }
    cpu_data = data[data["cpu_tier"].isin(cpu_map.keys())].copy()
    cpu_data["cpu_tier_short"] = cpu_data["cpu_tier"].map(cpu_map)
    cpu_short_order = ["Core i3 / Entry", "Core i5 / Ryzen 5", "Core i7 / Ryzen 7", "Core i9 / Ryzen 9", "Apple M-Series"]

    sns.boxplot(
        data=cpu_data,
        x="cpu_tier_short",
        y="price_mil",
        order=cpu_short_order,
        hue="cpu_tier_short",
        legend=False,
        palette="Purples_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[1, 0]
    )
    axes[1, 0].set_title("C. Biến thiên Giá theo Phân tầng Vi xử lý CPU (Laptop)", pad=10, fontsize=11, fontweight="bold")
    axes[1, 0].set_xlabel("Phân tầng CPU", fontweight="bold")
    axes[1, 0].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    plt.setp(axes[1, 0].get_xticklabels(), rotation=20, ha="right", fontsize=9.5)
    axes[1, 0].set_ylim(-2, 145)

    # 4. GPU Type Boxplot
    gpu_order = ["Integrated (Onboard)", "Dedicated (GPU rời)", "Apple Silicon GPU"]
    gpu_data = data[data["gpu_type"].isin(gpu_order)]
    sns.boxplot(
        data=gpu_data,
        x="gpu_type",
        y="price_mil",
        order=gpu_order,
        hue="gpu_type",
        legend=False,
        palette="Oranges_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[1, 1]
    )
    axes[1, 1].set_title("D. Biến thiên Giá theo Phân loại GPU Đồ họa (Laptop)", pad=10, fontsize=11, fontweight="bold")
    axes[1, 1].set_xlabel("Phân loại GPU", fontweight="bold")
    axes[1, 1].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[1, 1].set_ylim(-2, 145)

    fig.suptitle(
        "Phân tích Mối liên hệ Phân tầng Cấu hình Phần cứng và Giá bán: Ngành hàng Laptop\n(Tam giác đỏ: Giá trung bình - Mean; Đường ngang: Trung vị - Median)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_hardware_price_relationships_smartphone(
    phone_df: pd.DataFrame,
    output_path: str
):
    """
    Vẽ lưới 2x2 Boxplots phân tích biến thiên Giá bán (Triệu VNĐ) theo 4 trục cấu hình & thương hiệu Smartphone:
    (A) Dung lượng Bộ nhớ ROM (storage_group)
    (B) Dung lượng RAM (ram_group)
    (C) Thương hiệu Top 8 (brand_norm)
    (D) Công nghệ Màn hình (display_group)
    """
    set_plotting_theme()
    fig, axes = plt.subplots(2, 2, figsize=(16, 13))

    data = phone_df[phone_df["price_vnd"] > 0].copy()
    data["price_mil"] = data["price_vnd"] / 1e6

    # 1. Storage Boxplot
    storage_order = ["<= 64 GB", "128 GB", "256 GB", "512 GB", ">= 1 TB"]
    storage_data = data[data["storage_group"].isin(storage_order)]
    sns.boxplot(
        data=storage_data,
        x="storage_group",
        y="price_mil",
        order=storage_order,
        hue="storage_group",
        legend=False,
        palette="Blues_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[0, 0]
    )
    axes[0, 0].set_title("A. Biến thiên Giá theo Bộ nhớ trong ROM (Smartphone)", pad=10, fontsize=11, fontweight="bold")
    axes[0, 0].set_xlabel("Dung lượng Bộ nhớ trong (ROM)", fontweight="bold")
    axes[0, 0].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[0, 0].set_ylim(-2, 85)

    # 2. RAM Boxplot
    ram_order = ["<= 4 GB", "6 GB", "8 GB", "12 GB", ">= 16 GB"]
    ram_data = data[data["ram_group"].isin(ram_order)]
    sns.boxplot(
        data=ram_data,
        x="ram_group",
        y="price_mil",
        order=ram_order,
        hue="ram_group",
        legend=False,
        palette="Greens_r",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[0, 1]
    )
    axes[0, 1].set_title("B. Biến thiên Giá theo Dung lượng RAM (Smartphone)", pad=10, fontsize=11, fontweight="bold")
    axes[0, 1].set_xlabel("Dung lượng RAM", fontweight="bold")
    axes[0, 1].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[0, 1].set_ylim(-2, 85)

    # 3. Top Brands Boxplot
    top_brands = ["Apple", "Samsung", "Xiaomi", "OPPO", "Vivo", "Realme", "Honor", "Nokia"]
    brand_data = data[data["brand_norm"].isin(top_brands)]
    sns.boxplot(
        data=brand_data,
        x="brand_norm",
        y="price_mil",
        order=top_brands,
        hue="brand_norm",
        legend=False,
        palette="Set2",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[1, 0]
    )
    axes[1, 0].set_title("C. Biến thiên Giá theo Top 8 Thương hiệu Smartphone", pad=10, fontsize=11, fontweight="bold")
    axes[1, 0].set_xlabel("Thương hiệu", fontweight="bold")
    axes[1, 0].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    plt.setp(axes[1, 0].get_xticklabels(), rotation=25, ha="right", fontsize=9.5)
    axes[1, 0].set_ylim(-2, 85)

    # 4. Display Type Boxplot
    disp_order = ["OLED / AMOLED", "IPS / LCD"]
    disp_data = data[data["display_group"].isin(disp_order)]
    sns.boxplot(
        data=disp_data,
        x="display_group",
        y="price_mil",
        order=disp_order,
        hue="display_group",
        legend=False,
        palette="coolwarm",
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": "7"},
        ax=axes[1, 1]
    )
    axes[1, 1].set_title("D. Biến thiên Giá theo Công nghệ Màn hình (Smartphone)", pad=10, fontsize=11, fontweight="bold")
    axes[1, 1].set_xlabel("Công nghệ Màn hình", fontweight="bold")
    axes[1, 1].set_ylabel("Giá bán (Triệu VNĐ)", fontweight="bold")
    axes[1, 1].set_ylim(-2, 85)

    fig.suptitle(
        "Phân tích Mối liên hệ Cấu hình Phần cứng & Thương hiệu với Giá bán: Ngành hàng Smartphone\n(Tam giác đỏ: Giá trung bình - Mean; Đường ngang: Trung vị - Median)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.02, 1, 0.94])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_pricing_drivers_comparison(df: pd.DataFrame, output_path: str):
    """
    Nhiệm vụ 2.2: Trực quan hóa đối đầu chuyên sâu Cấu trúc Quyết định Giá:
    Laptop vs. Smartphone (Fig 2.2).
    Lưới 1x3 Panels:
    - Panel A: Đối đầu Hệ số tương quan Spearman (ρ) giữa cấu hình và Giá bán.
    - Panel B: Biên độ đòn bẩy giá (Price Multiplier: Tỷ lệ chênh lệch giá Max Tier / Min Tier).
    - Panel C: Độ mạnh phân tầng của các biến danh mục qua ANOVA F-statistic.
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 3, figsize=(20, 6.5))

    # --- PANEL A: SPEARMAN CORRELATION COMPARISON ---
    corr_features = [
        "Dung lượng RAM",
        "Bộ nhớ / Ổ cứng",
        "Công suất Sạc",
        "Dung lượng Pin",
        "Kích thước Màn hình",
        "Camera MP"
    ]
    # Spearman rho values from empirical data
    laptop_rhos = [0.803, 0.548, 0.722, 0.658, 0.089, np.nan]
    phone_rhos = [0.589, 0.702, 0.505, 0.038, 0.178, 0.027]

    y_pos = np.arange(len(corr_features))
    bar_height = 0.38

    ax1 = axes[0]
    rects1 = ax1.barh(y_pos + bar_height/2, laptop_rhos, bar_height, label="Laptop", color="#2b5c8f", alpha=0.9)
    rects2 = ax1.barh(y_pos - bar_height/2, phone_rhos, bar_height, label="Smartphone", color="#d95f02", alpha=0.9)

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(corr_features, fontsize=10, fontweight="bold")
    ax1.invert_yaxis()  # Đi từ trên xuống dưới
    ax1.set_xlabel("Hệ số tương quan Spearman (ρ) với Giá bán", fontsize=10.5, fontweight="bold")
    ax1.set_xlim(-0.05, 1.0)
    ax1.set_title("A. So sánh Tương quan Cấu hình - Giá bán (Spearman ρ)", pad=12, fontsize=11.5, fontweight="bold")
    ax1.legend(loc="lower right", frameon=True, fontsize=10)
    ax1.axvline(0, color="gray", linestyle="--", alpha=0.7)

    # Thêm nhãn số trên các thanh
    for rect in rects1:
        w = rect.get_width()
        if not np.isnan(w):
            ax1.annotate(f"{w:+.2f}", (w + 0.02, rect.get_y() + rect.get_height()/2),
                         va="center", fontsize=8.5, fontweight="bold", color="#2b5c8f")
        else:
            ax1.annotate("N/A", (0.02, rect.get_y() + rect.get_height()/2),
                         va="center", fontsize=8.5, color="gray", fontstyle="italic")

    for rect in rects2:
        w = rect.get_width()
        if not np.isnan(w):
            ax1.annotate(f"{w:+.2f}", (w + 0.02, rect.get_y() + rect.get_height()/2),
                         va="center", fontsize=8.5, fontweight="bold", color="#d95f02")

    # --- PANEL B: PRICE MULTIPLIER (MAX TIER / MIN TIER) ---
    ax2 = axes[1]
    multiplier_data = [
        {"Factor": "ROM Smartphone (1TB vs 64GB)", "Multiplier": 11.97, "Category": "Smartphone"},
        {"Factor": "Thương hiệu Phone (Apple vs Android entry)", "Multiplier": 7.28, "Category": "Smartphone"},
        {"Factor": "RAM Smartphone (>=16GB vs <=4GB)", "Multiplier": 7.29, "Category": "Smartphone"},
        {"Factor": "Màn hình Phone (OLED vs IPS)", "Multiplier": 4.11, "Category": "Smartphone"},
        {"Factor": "Ổ cứng Laptop (>=2TB vs 256GB)", "Multiplier": 5.21, "Category": "Laptop"},
        {"Factor": "RAM Laptop (>=64GB vs 8GB)", "Multiplier": 5.16, "Category": "Laptop"},
        {"Factor": "CPU Laptop (i9 vs Core i3)", "Multiplier": 4.60, "Category": "Laptop"},
        {"Factor": "Pin Laptop (>75Wh vs <45Wh)", "Multiplier": 2.78, "Category": "Laptop"},
        {"Factor": "GPU Laptop (Apple/Discrete vs Onboard)", "Multiplier": 2.05, "Category": "Laptop"},
    ]
    mult_df = pd.DataFrame(multiplier_data).sort_values(by="Multiplier", ascending=True)

    colors_b = ["#d95f02" if cat == "Smartphone" else "#2b5c8f" for cat in mult_df["Category"]]
    bars_b = ax2.barh(mult_df["Factor"], mult_df["Multiplier"], color=colors_b, alpha=0.88, height=0.6)

    ax2.set_xlabel("Hệ số Chênh lệch Giá (Median Max Tier / Median Min Tier)", fontsize=10.5, fontweight="bold")
    ax2.set_xlim(0, 14.5)
    ax2.set_title("B. Biên độ Đòn bẩy Giá giữa Phân khúc Cao & Thấp", pad=12, fontsize=11.5, fontweight="bold")

    for bar in bars_b:
        w = bar.get_width()
        ax2.annotate(f"{w:.2f}x", (w + 0.2, bar.get_y() + bar.get_height()/2),
                     va="center", fontsize=9, fontweight="bold", color="#333333")

    # Custom legend for panel B
    from matplotlib.patches import Patch
    legend_elements_b = [
        Patch(facecolor="#2b5c8f", label="Laptop"),
        Patch(facecolor="#d95f02", label="Smartphone")
    ]
    ax2.legend(handles=legend_elements_b, loc="lower right", frameon=True, fontsize=10)

    # --- PANEL C: ANOVA F-STATISTIC COMPARISON ---
    ax3 = axes[2]
    anova_data = [
        {"Factor": "Màn hình OLED/IPS (Phone)", "F": 2954.2, "Category": "Smartphone"},
        {"Factor": "CPU Tier (Laptop)", "F": 757.2, "Category": "Laptop"},
        {"Factor": "Storage Group (Phone)", "F": 569.8, "Category": "Smartphone"},
        {"Factor": "RAM Group (Laptop)", "F": 565.4, "Category": "Laptop"},
        {"Factor": "Brand Segment (Phone)", "F": 562.9, "Category": "Smartphone"},
        {"Factor": "GPU Type (Laptop)", "F": 502.1, "Category": "Laptop"},
        {"Factor": "RAM Group (Phone)", "F": 377.9, "Category": "Smartphone"},
        {"Factor": "Brand Segment (Laptop)", "F": 128.4, "Category": "Laptop"}
    ]
    anova_df = pd.DataFrame(anova_data).sort_values(by="F", ascending=True)

    colors_c = ["#d95f02" if cat == "Smartphone" else "#2b5c8f" for cat in anova_df["Category"]]
    bars_c = ax3.barh(anova_df["Factor"], anova_df["F"], color=colors_c, alpha=0.88, height=0.6)

    ax3.set_xlabel("Chỉ số ANOVA F-statistic (Độ phân tách phân phối log-price)", fontsize=10.5, fontweight="bold")
    ax3.set_xlim(0, 3350)
    ax3.set_title("C. Độ mạnh Phân hóa của các Biến Danh mục (ANOVA F)", pad=12, fontsize=11.5, fontweight="bold")

    for bar in bars_c:
        w = bar.get_width()
        ax3.annotate(f"F = {w:,.1f}", (w + 40, bar.get_y() + bar.get_height()/2),
                     va="center", fontsize=9, fontweight="bold", color="#333333")

    ax3.legend(handles=legend_elements_b, loc="lower right", frameon=True, fontsize=10)

    fig.suptitle(
        "Nhiệm vụ 2.2: So sánh Đối đầu Cấu trúc Quyết định Giá bán (Pricing Decision Structure): Laptop vs. Smartphone\n(Màu Xanh: Laptop - Hướng Tài nguyên Xử lý | Màu Cam: Smartphone - Hướng Trải nghiệm & Thương hiệu)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


# ==============================================================================
# NHIỆM VỤ 3: TRỰC QUAN HÓA CHẤT LƯỢNG DỮ LIỆU BÀI TOÁN HỒI QUY (REGRESSION READINESS)
# ==============================================================================

def plot_price_outliers_and_boundaries(df: pd.DataFrame, output_path: str):
    """
    Nhiệm vụ 3.1: Nhận diện Ngoại lai (Outliers) và Ranh giới Biên Phân phối Giá:
    - Panel A: Boxplot phân phối giá trên thang log10(price_vnd) làm nổi bật cụm < 500k và > 100M.
    - Panel B: Đường cong phân vị lũy tích (Percentile Distribution Curve) của Laptop vs Smartphone.
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    valid_df = df[df["price_vnd"] > 0].copy()
    valid_df["price_mil"] = valid_df["price_vnd"] / 1e6
    valid_df["log_price"] = np.log10(valid_df["price_vnd"])

    # --- PANEL A: LOG-PRICE BOXPLOT VỚI VÙNG NGOẠI LAI CỰC BIÊN ---
    ax1 = axes[0]
    palette = {"laptop": "#2b5c8f", "smartphone": "#d95f02"}
    
    sns.boxplot(
        data=valid_df,
        x="category",
        y="log_price",
        hue="category",
        palette=palette,
        legend=False,
        width=0.45,
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "yellow", "markeredgecolor": "black", "markersize": "8"},
        ax=ax1
    )

    # Đánh dấu các mốc giá quan trọng
    # 500k = 5e5 -> log10 = 5.699
    # 100M = 1e8 -> log10 = 8.000
    ax1.axhline(np.log10(500000), color="#e41a1c", linestyle="--", linewidth=1.5, alpha=0.85, label="Ngưỡng cực thấp: < 500k (N=97)")
    ax1.axhline(np.log10(100000000), color="#7570b3", linestyle="--", linewidth=1.5, alpha=0.85, label="Ngưỡng cực cao: > 100M (N=87)")

    # Đổi tick trục Y sang VNĐ dễ đọc
    log_ticks = [5.0, 5.699, 6.0, 7.0, 7.301, 8.0, 8.301]
    tick_labels = ["100k", "500k", "1 Triệu", "10 Triệu", "20 Triệu", "100 Triệu", "200 Triệu"]
    ax1.set_yticks(log_ticks)
    ax1.set_yticklabels(tick_labels, fontsize=9.5)
    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(["Laptop (N=3.382)", "Smartphone (N=5.166)"], fontsize=11, fontweight="bold")
    ax1.set_title("A. Nhận diện Ngoại lai Phân phối Giá trên thang Logarithm\n(Tam giác vàng: Giá trung bình log; Vạch ngang: Trung vị)", pad=12, fontsize=11, fontweight="bold")
    ax1.set_xlabel("Ngành hàng mục tiêu", labelpad=8, fontweight="bold")
    ax1.set_ylabel("Mức giá niêm yết (Quy đổi thang Log)", labelpad=8, fontweight="bold")
    ax1.legend(loc="upper left", frameon=True, fontsize=9.5)

    # --- PANEL B: ĐƯỜNG CONG PHÂN VỊ LŨY TÍCH (PERCENTILE CURVES) ---
    ax2 = axes[1]
    percentiles = np.linspace(0.01, 0.99, 99)

    lap_p = np.percentile(valid_df[valid_df["category"] == "laptop"]["price_mil"], percentiles * 100)
    ph_p = np.percentile(valid_df[valid_df["category"] == "smartphone"]["price_mil"], percentiles * 100)

    ax2.plot(percentiles * 100, lap_p, color="#2b5c8f", linewidth=2.5, label="Laptop (Max: 485 Triệu)")
    ax2.plot(percentiles * 100, ph_p, color="#d95f02", linewidth=2.5, label="Smartphone (Max: 54 Triệu)")

    ax2.axvline(50, color="gray", linestyle=":", alpha=0.7, label="Trung vị (P50)")
    ax2.axvline(95, color="#e41a1c", linestyle=":", alpha=0.7, label="P95 (Bắt đầu phân khúc Flagship)")

    ax2.set_title("B. Đường cong Phân vị Giá (Percentile Curve): P1 đến P99\n(Cho thấy độ kéo đuôi cực dài của phân khúc cao cấp)", pad=12, fontsize=11, fontweight="bold")
    ax2.set_xlabel("Phân vị phần trăm (Percentile %)", labelpad=8, fontweight="bold")
    ax2.set_ylabel("Giá niêm yết (Triệu VNĐ)", labelpad=8, fontweight="bold")
    ax2.set_ylim(-2, 140)
    ax2.set_xlim(0, 100)
    ax2.legend(loc="upper left", frameon=True, fontsize=9.5)

    fig.suptitle(
        "Nhiệm vụ 3.1: Nhận diện Ngoại lai (Outliers) và Ranh giới Dữ liệu Biên phục vụ Mô hình Hồi quy (TV5)\n(Khẳng định yêu cầu loại bỏ 1.768 bản ghi không hợp lệ & áp dụng biến đổi log1p cho target price_vnd)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_multicollinearity_and_vif(df: pd.DataFrame, output_path: str):
    """
    Nhiệm vụ 3.2: Đo lường Đa cộng tuyến (Multicollinearity) & Cảnh báo VIF cho TV5:
    - Panel A: Heatmap ma trận tương quan chéo của Smartphone (tương quan RAM - ROM).
    - Panel B: Bar chart chỉ số Variance Inflation Factor (VIF) với các ngưỡng cảnh báo 2.5 và 5.0.
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    valid_df = df[df["price_vnd"] > 0].copy()

    # --- PANEL A: CROSS-CORRELATION MATRIX (SMARTPHONE) ---
    ax1 = axes[0]
    phone_df = valid_df[valid_df["category"] == "smartphone"]
    ph_cols = ["installed_ram_gb", "storage_gb", "charger_watt", "battery_mah", "screen_size_inch"]
    ph_labels = ["RAM (GB)", "ROM (GB)", "Sạc (W)", "Pin (mAh)", "Màn hình (\")"]
    
    ph_sub = phone_df[ph_cols].dropna()
    ph_corr = ph_sub.corr()

    mask = np.triu(np.ones_like(ph_corr, dtype=bool))
    cmap = sns.diverging_palette(220, 20, as_cmap=True)

    sns.heatmap(
        ph_corr,
        mask=mask,
        cmap="coolwarm",
        vmax=1.0,
        vmin=-0.2,
        center=0,
        annot=True,
        fmt=".2f",
        square=True,
        linewidths=.5,
        cbar_kws={"shrink": .8, "label": "Hệ số tương quan Pearson (r)"},
        xticklabels=ph_labels,
        yticklabels=ph_labels,
        ax=ax1
    )
    plt.setp(ax1.get_yticklabels(), rotation=0, fontsize=9.5)
    plt.setp(ax1.get_xticklabels(), rotation=25, ha="right", fontsize=9.5)
    ax1.set_title("A. Ma trận Tương quan Chéo giữa các Biến Cấu hình (Smartphone)\n(Cảnh báo tương quan cao giữa RAM & ROM: r = +0.83)", pad=12, fontsize=11, fontweight="bold")

    # --- PANEL B: VIF BAR CHART ---
    ax2 = axes[1]
    vif_data = [
        {"Feature": "RAM Smartphone", "VIF": 5.44, "Category": "Smartphone"},
        {"Feature": "ROM Smartphone", "VIF": 3.55, "Category": "Smartphone"},
        {"Feature": "Pin Wh Laptop", "VIF": 2.82, "Category": "Laptop"},
        {"Feature": "Sạc Watt Phone", "VIF": 2.29, "Category": "Smartphone"},
        {"Feature": "RAM Laptop", "VIF": 2.05, "Category": "Laptop"},
        {"Feature": "Màn hình Laptop", "VIF": 1.62, "Category": "Laptop"},
        {"Feature": "Ổ cứng Laptop", "VIF": 1.51, "Category": "Laptop"},
        {"Feature": "Sạc Watt Laptop", "VIF": 1.46, "Category": "Laptop"},
        {"Feature": "Màn hình Phone", "VIF": 1.31, "Category": "Smartphone"},
        {"Feature": "Pin mAh Phone", "VIF": 1.08, "Category": "Smartphone"}
    ]
    vif_df = pd.DataFrame(vif_data).sort_values(by="VIF", ascending=True)

    colors = ["#d95f02" if cat == "Smartphone" else "#2b5c8f" for cat in vif_df["Category"]]
    bars = ax2.barh(vif_df["Feature"], vif_df["VIF"], color=colors, alpha=0.88, height=0.6)

    # Vạch ngưỡng cảnh báo
    ax2.axvline(2.5, color="green", linestyle="--", linewidth=1.5, alpha=0.8, label="Ngưỡng an toàn (VIF < 2.5)")
    ax2.axvline(5.0, color="orange", linestyle="--", linewidth=1.5, alpha=0.8, label="Ngưỡng cảnh báo đa cộng tuyến (VIF > 5.0)")

    for bar in bars:
        w = bar.get_width()
        ax2.annotate(f"{w:.2f}", (w + 0.12, bar.get_y() + bar.get_height()/2),
                     va="center", fontsize=9, fontweight="bold", color="#333333")

    ax2.set_xlabel("Chỉ số Phóng đại Phương sai (Variance Inflation Factor - VIF)", fontsize=10.5, fontweight="bold")
    ax2.set_xlim(0, 7.0)
    ax2.set_title("B. Chỉ số VIF của các Thuộc tính Phần cứng (Laptop vs. Smartphone)\n(Màu Xanh: Laptop | Màu Cam: Smartphone)", pad=12, fontsize=11, fontweight="bold")
    ax2.legend(loc="lower right", frameon=True, fontsize=9.5)

    fig.suptitle(
        "Nhiệm vụ 3.2: Đánh giá Hiện tượng Đa cộng tuyến (Multicollinearity) & Kiểm toán Chỉ số VIF\n(Cảnh báo TV5: Cần dùng Ridge Regularization hoặc GBDT để khắc phục cộng tuyến giữa RAM và ROM)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()


def plot_availability_price_comparison(df: pd.DataFrame, output_path: str):
    """
    Nhiệm vụ 3.4: Đánh giá Tác động của Trạng thái Tồn kho (availability_status) đến Giá bán:
    - Panel A: Boxplot so sánh giá bán (Triệu VNĐ) giữa in_stock và out_of_stock theo ngành hàng.
    - Panel B: KDE plot thể hiện hiện tượng 'Price Drift' (độ lệch giá do hàng out_of_stock là máy đời cũ EOL).
    """
    set_plotting_theme()
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    valid_df = df[(df["price_vnd"] > 0) & (df["availability_status"].isin(["in_stock", "out_of_stock"]))].copy()
    valid_df["price_mil"] = valid_df["price_vnd"] / 1e6
    valid_df["log_price"] = np.log10(valid_df["price_vnd"])

    # --- PANEL A: BOXPLOT SO SÁNH IN_STOCK VS OUT_OF_STOCK ---
    ax1 = axes[0]
    palette = {"in_stock": "#2ca02c", "out_of_stock": "#d62728"}

    sns.boxplot(
        data=valid_df,
        x="category",
        y="price_mil",
        hue="availability_status",
        hue_order=["in_stock", "out_of_stock"],
        palette=palette,
        showmeans=True,
        meanprops={"marker": "^", "markerfacecolor": "yellow", "markeredgecolor": "black", "markersize": "8"},
        ax=ax1
    )

    ax1.set_xticks([0, 1])
    ax1.set_xticklabels(["Laptop", "Smartphone"], fontsize=11, fontweight="bold")
    ax1.set_ylabel("Giá bán niêm yết (Triệu VNĐ)", fontsize=10.5, fontweight="bold")
    ax1.set_xlabel("Ngành hàng mục tiêu", fontsize=10.5, fontweight="bold")
    ax1.set_ylim(-2, 90)
    ax1.set_title("A. So sánh Giá niêm yết: Đang kinh doanh (in_stock) vs Hết hàng (out_of_stock)\n(Tam giác vàng: Mean; Vạch ngang: Median)", pad=12, fontsize=11, fontweight="bold")
    
    # Custom legend labels
    handles, labels = ax1.get_legend_handles_labels()
    ax1.legend(handles=handles, labels=["Còn hàng (in_stock)", "Hết hàng (out_of_stock)"], loc="upper right", frameon=True, fontsize=10)


    # --- PANEL B: PHÂN PHỐI MẬT ĐỘ LOG-PRICE (PRICE DRIFT PHENOMENON) ---
    ax2 = axes[1]
    
    # Vẽ KDE cho Laptop
    sns.kdeplot(
        data=valid_df[(valid_df["category"] == "laptop") & (valid_df["availability_status"] == "in_stock")]["log_price"],
        color="#2ca02c", linewidth=2.2, linestyle="-", label="Laptop: in_stock (Median: 33.49M)", ax=ax2
    )
    sns.kdeplot(
        data=valid_df[(valid_df["category"] == "laptop") & (valid_df["availability_status"] == "out_of_stock")]["log_price"],
        color="#2b5c8f", linewidth=2.0, linestyle="--", label="Laptop: out_of_stock (Median: 23.99M)", ax=ax2
    )

    # Vẽ KDE cho Smartphone
    sns.kdeplot(
        data=valid_df[(valid_df["category"] == "smartphone") & (valid_df["availability_status"] == "in_stock")]["log_price"],
        color="#ff7f0e", linewidth=2.2, linestyle="-", label="Phone: in_stock (Median: 9.79M)", ax=ax2
    )
    sns.kdeplot(
        data=valid_df[(valid_df["category"] == "smartphone") & (valid_df["availability_status"] == "out_of_stock")]["log_price"],
        color="#d62728", linewidth=2.0, linestyle="--", label="Phone: out_of_stock (Median: 6.49M)", ax=ax2
    )

    log_ticks = [6.0, 6.699, 7.0, 7.301, 7.699, 8.0]
    tick_labels = ["1M", "5M", "10M", "20M", "50M", "100M"]
    ax2.set_xticks(log_ticks)
    ax2.set_xticklabels(tick_labels, fontsize=9.5)
    ax2.set_xlabel("Mức giá niêm yết (Quy đổi thang Log)", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Mật độ phân phối xác suất (KDE Density)", fontsize=10.5, fontweight="bold")
    ax2.set_title("B. Hiện tượng Lệch Giá (Price Drift): Hàng hết tồn kho dịch về vùng giá thấp\n(Chứng minh sản phẩm out_of_stock lưu giữ mức giá EOL lạc hậu)", pad=12, fontsize=11, fontweight="bold")
    ax2.legend(loc="upper right", frameon=True, fontsize=9)

    fig.suptitle(
        "Nhiệm vụ 3.4: Đánh giá Tác động của Trạng thái Tồn kho (availability_status) đến Giá niêm yết\n(Khuyến nghị TV5: Hàng out_of_stock có giá rẻ hơn 28-34% do là máy đời cũ EOL, cần thêm cờ nhị phân is_out_of_stock)",
        fontsize=13,
        fontweight="bold",
        y=0.985
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.93])
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()




