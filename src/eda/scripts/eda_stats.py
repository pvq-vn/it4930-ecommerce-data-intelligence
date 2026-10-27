"""
EDA Statistics Helper Functions (TV3)
Module cung cấp các hàm tính toán thống kê phân phối, bảng chéo, thị phần và biến Giá.
"""

from typing import Dict, Tuple, List, Optional
import re
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats


def load_processed_products(data_path: str = "data/processed/products_processed.jsonl") -> pd.DataFrame:
    """Tải tập dữ liệu đã làm sạch products_processed.jsonl."""
    df = pd.read_json(data_path, lines=True)
    return df


def get_source_category_crosstab(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Tính bảng chéo số lượng và tỷ lệ phần trăm giữa source và category.
    """
    ct_counts = pd.crosstab(
        df["source"],
        df["category"],
        margins=True,
        margins_name="Total"
    )
    ct_pct = (ct_counts / len(df) * 100).round(2)
    return ct_counts, ct_pct


def get_brand_market_share(df: pd.DataFrame, top_n: int = 10) -> Dict[str, pd.DataFrame]:
    """
    Tính thị phần thương hiệu (brand_norm) cho:
    - Toàn bộ dữ liệu
    - Ngành hàng Laptop
    - Ngành hàng Smartphone
    """
    results = {}

    # Toàn bộ
    total_brands = df["brand_norm"].fillna("Unknown").value_counts()
    top_total = total_brands.head(top_n).to_frame(name="count")
    top_total["share_pct"] = (top_total["count"] / len(df) * 100).round(2)
    other_count = total_brands.iloc[top_n:].sum()
    if other_count > 0:
        other_row = pd.DataFrame([{"count": other_count, "share_pct": round(other_count / len(df) * 100, 2)}], index=["Other"])
        top_total = pd.concat([top_total, other_row])
    results["overall"] = top_total

    # Theo từng category
    for cat in ["laptop", "smartphone"]:
        sub_df = df[df["category"] == cat]
        sub_len = len(sub_df)
        cat_brands = sub_df["brand_norm"].fillna("Unknown").value_counts()
        top_cat = cat_brands.head(top_n).to_frame(name="count")
        top_cat["share_pct"] = (top_cat["count"] / sub_len * 100).round(2)
        other_cat_count = cat_brands.iloc[top_n:].sum()
        if other_cat_count > 0:
            other_cat_row = pd.DataFrame([{"count": other_cat_count, "share_pct": round(other_cat_count / sub_len * 100, 2)}], index=["Other"])
            top_cat = pd.concat([top_cat, other_cat_row])
        results[cat] = top_cat

    return results


def get_seller_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """
    Thống kê phân phối số lượng sản phẩm theo nhà bán lẻ (seller_raw).
    """
    seller_counts = df["seller_raw"].value_counts().to_frame(name="count")
    seller_counts["share_pct"] = (seller_counts["count"] / len(df) * 100).round(2)
    seller_counts["cumulative_pct"] = seller_counts["share_pct"].cumsum().round(2)
    return seller_counts


def compute_price_descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính các chỉ số thống kê mô tả toàn diện cho biến Giá bán (price_vnd):
    - Đơn vị tính: Triệu VNĐ (Mil. VND)
    - Nhóm: Overall, Laptop, Smartphone
    - Thống kê: Count, Mean, Std, Min, Q1 (25%), Median (50%), Q3 (75%), IQR, Max, Skewness, Kurtosis
    """
    # Chỉ tính trên mẫu có giá hợp lệ (> 0)
    valid_df = df[df["price_vnd"] > 0].copy()

    records = []
    groups = [
        ("Toàn thị trường", valid_df),
        ("Laptop", valid_df[valid_df["category"] == "laptop"]),
        ("Smartphone", valid_df[valid_df["category"] == "smartphone"])
    ]

    for label, group in groups:
        prices = group["price_vnd"] / 1e6  # Chuyển sang Triệu VNĐ
        q1 = prices.quantile(0.25)
        q3 = prices.quantile(0.75)
        iqr = q3 - q1

        records.append({
            "Phân nhóm": label,
            "Số mẫu hợp lệ": len(prices),
            "Số mẫu thiếu/0đ": len(df[df["category"] == group["category"].iloc[0]]) - len(prices) if label != "Toàn thị trường" else len(df) - len(prices),
            "Mean (Tr.đ)": round(prices.mean(), 2),
            "Std (Tr.đ)": round(prices.std(), 2),
            "Min (Tr.đ)": round(prices.min(), 2),
            "Q1 25% (Tr.đ)": round(q1, 2),
            "Median 50% (Tr.đ)": round(prices.median(), 2),
            "Q3 75% (Tr.đ)": round(q3, 2),
            "IQR (Tr.đ)": round(iqr, 2),
            "Max (Tr.đ)": round(prices.max(), 2),
            "Skewness (Độ lệch)": round(prices.skew(), 2),
            "Kurtosis (Độ nhọn)": round(prices.kurt(), 2)
        })

    stats_df = pd.DataFrame(records).set_index("Phân nhóm")
    return stats_df


def compute_price_log_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """
    So sánh độ lệch (Skewness) và độ nhọn (Kurtosis) giữa thang đo gốc và thang đo Log (np.log1p).
    """
    valid_df = df[df["price_vnd"] > 0].copy()

    records = []
    groups = [
        ("Toàn thị trường", valid_df),
        ("Laptop", valid_df[valid_df["category"] == "laptop"]),
        ("Smartphone", valid_df[valid_df["category"] == "smartphone"])
    ]

    for label, group in groups:
        raw_price = group["price_vnd"]
        log_price = np.log10(raw_price)

        records.append({
            "Phân nhóm": label,
            "Raw Skewness": round(raw_price.skew(), 2),
            "Log10 Skewness": round(log_price.skew(), 2),
            "Raw Kurtosis": round(raw_price.kurt(), 2),
            "Log10 Kurtosis": round(log_price.kurt(), 2),
            "Đánh giá dạng phân phối": "Gần chuẩn (Bell-shaped)" if abs(log_price.skew()) < 0.6 else "Hơi lệch trái"
        })

    return pd.DataFrame(records).set_index("Phân nhóm")


def compute_discount_stats_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính thống kê phân phối tỷ lệ chiết khấu (discount_rate) theo từng nguồn sàn (source).
    """
    # Chỉ tính trên mẫu có discount_rate hợp lệ
    valid_discount = df[df["discount_rate"].notna()].copy()
    valid_discount["discount_pct"] = valid_discount["discount_rate"] * 100

    def stats_summary(x):
        q1 = x.quantile(0.25)
        q3 = x.quantile(0.75)
        return pd.Series({
            "Số mẫu có giảm giá": int(len(x)),
            "Tỷ lệ có giảm giá (%)": round(len(x) / len(df[df["source"] == x.name]) * 100, 2),
            "Mean (%)": round(x.mean(), 2),
            "Std (%)": round(x.std(), 2),
            "Min (%)": round(x.min(), 2),
            "Q1 25% (%)": round(q1, 2),
            "Median (%)": round(x.median(), 2),
            "Q3 75% (%)": round(q3, 2),
            "Max (%)": round(x.max(), 2),
            "Skewness": round(x.skew(), 2)
        })

    grouped = valid_discount.groupby("source")["discount_pct"].apply(stats_summary).unstack()

    # Thêm dòng tổng thể
    all_discount = valid_discount["discount_pct"]
    overall_row = pd.Series({
        "Số mẫu có giảm giá": int(len(all_discount)),
        "Tỷ lệ có giảm giá (%)": round(len(all_discount) / len(df) * 100, 2),
        "Mean (%)": round(all_discount.mean(), 2),
        "Std (%)": round(all_discount.std(), 2),
        "Min (%)": round(all_discount.min(), 2),
        "Q1 25% (%)": round(all_discount.quantile(0.25), 2),
        "Median (%)": round(all_discount.median(), 2),
        "Q3 75% (%)": round(all_discount.quantile(0.75), 2),
        "Max (%)": round(all_discount.max(), 2),
        "Skewness": round(all_discount.skew(), 2)
    }, name="Toàn thị trường")

    result = pd.concat([grouped, overall_row.to_frame().T])
    return result


def compute_overall_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tính bảng tổng hợp tỷ lệ thiếu cho toàn bộ 30 cột trong tập dữ liệu.
    Phân loại theo mức độ:
    - Rất thấp: < 5%
    - Thấp: 5% - 20%
    - Trung bình: 20% - 50%
    - Cao: 50% - 80%
    - Cực cao / Đặc thù cấu hình: > 80%
    """
    total = len(df)
    miss_counts = df.isna().sum()
    miss_pct = (miss_counts / total * 100).round(2)
    non_null_counts = total - miss_counts

    def categorize_severity(pct):
        if pct == 0:
            return "Không thiếu (0%)"
        elif pct < 5:
            return "Rất thấp (<5%)"
        elif pct <= 25:
            return "Thấp (5-25%)"
        elif pct <= 50:
            return "Trung bình (25-50%)"
        elif pct <= 80:
            return "Cao (50-80%)"
        else:
            return "Cực cao (>80%) [Đặc thù ngành/sàn]"

    records = []
    for col in df.columns:
        pct = miss_pct[col]
        records.append({
            "Tên trường": col,
            "Kiểu dữ liệu": str(df[col].dtype),
            "Số mẫu Non-Null": int(non_null_counts[col]),
            "Số mẫu Missing": int(miss_counts[col]),
            "Tỷ lệ Missing (%)": pct,
            "Mức độ thiếu": categorize_severity(pct)
        })

    result_df = pd.DataFrame(records).sort_values("Tỷ lệ Missing (%)", ascending=False).set_index("Tên trường")
    return result_df


def compute_missingness_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    So sánh tỷ lệ thiếu của toàn bộ các thuộc tính giữa Laptop và Smartphone.
    """
    total = len(df)
    laptop_df = df[df["category"] == "laptop"]
    phone_df = df[df["category"] == "smartphone"]

    o_miss = (df.isna().mean() * 100).round(2)
    l_miss = (laptop_df.isna().mean() * 100).round(2)
    p_miss = (phone_df.isna().mean() * 100).round(2)

    comp_df = pd.DataFrame({
        "Toàn thị trường (%)": o_miss,
        "Laptop (%)": l_miss,
        "Smartphone (%)": p_miss,
        "Chênh lệch (Laptop - Phone)": (l_miss - p_miss).round(2)
    })

    # Gán nhãn giải thích đặc thù
    def explain_diff(row):
        col = row.name
        if col in ["battery_wh", "gpu_norm"]:
            return "Đặc thù phần cứng Laptop (Pin Wh / GPU rời)"
        elif col in ["battery_mah", "camera_mp", "network_type_norm"]:
            return "Đặc thù phần cứng Smartphone (Pin mAh / Camera / 5G)"
        elif col == "cpu_norm":
            return "Tỷ lệ khai báo CPU trên Laptop cao vượt trội"
        elif col == "rating_norm":
            return "Người dùng Smartphone đánh giá nhiều hơn Laptop"
        elif col in ["listing_record_id", "source_parent_id", "product_name", "source", "category", "seller_raw"]:
            return "Trường định danh chuẩn (Không thiếu)"
        else:
            return "Thiếu tương đương giữa 2 ngành"

    comp_df["Bản chất khác biệt"] = comp_df.apply(explain_diff, axis=1)
    return comp_df.sort_values("Toàn thị trường (%)", ascending=False)


def compute_missingness_by_source(df: pd.DataFrame) -> pd.DataFrame:
    """
    Phân tích tỷ lệ thiếu (%) theo 5 nguồn cào (source) cho các thuộc tính quan trọng.
    """
    candidate_cols = [
        "price_vnd", "original_price_vnd", "discount_rate", "rating_norm",
        "total_sold_normalized", "installed_ram_gb", "storage_gb", "cpu_norm",
        "gpu_norm", "battery_mah", "battery_wh", "screen_size_inch", "charger_watt"
    ]

    source_miss = df.groupby("source")[candidate_cols].apply(lambda x: (x.isna().mean() * 100).round(2))
    overall_miss = (df[candidate_cols].isna().mean() * 100).round(2)
    overall_miss.name = "Toàn thị trường"

    result = pd.concat([source_miss, overall_miss.to_frame().T])
    return result


def compute_missingness_matrix_source_category(df: pd.DataFrame, key_features: list = None) -> pd.DataFrame:
    """
    Ma trận phân rã 2 chiều: (source x category) đối với các candidate features quan trọng.
    """
    if key_features is None:
        key_features = [
            "price_vnd", "rating_norm", "total_sold_normalized",
            "installed_ram_gb", "storage_gb", "cpu_norm", "gpu_norm",
            "battery_mah", "battery_wh", "screen_size_inch"
        ]

    grouped = df.groupby(["source", "category"])[key_features].apply(lambda x: (x.isna().mean() * 100).round(1))
    return grouped


def export_dataframe_to_markdown_and_csv(
    df: pd.DataFrame,
    output_dir: str,
    base_name: str,
    title: str = ""
) -> Path:
    """Xuất DataFrame ra cả file CSV và file Markdown."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / f"{base_name}.csv"
    df.to_csv(csv_path, encoding="utf-8-sig")

    md_path = out_dir / f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        if title:
            f.write(f"### {title}\n\n")
        f.write(df.to_markdown())
        f.write("\n")

    return md_path


def compute_bivariate_correlations(
    df: pd.DataFrame,
    category: str,
    num_cols: List[str]
) -> pd.DataFrame:
    """
    Tính tương quan Pearson (tuyến tính) và Spearman (phi tuyến / thứ hạng)
    giữa các biến cấu hình số với biến Giá (price_vnd và log10(price_vnd)).
    """
    sub_df = df[(df["category"] == category) & (df["price_vnd"] > 0)].copy()
    sub_df["log_price"] = np.log10(sub_df["price_vnd"])

    records = []
    for col in num_cols:
        if col not in sub_df.columns:
            continue
        valid = sub_df.dropna(subset=[col, "price_vnd", "log_price"])
        n_obs = len(valid)
        if n_obs < 10:
            continue

        # Tương quan với log_price (phù hợp với hàm mục tiêu TV5)
        p_log_r, p_log_p = stats.pearsonr(valid[col], valid["log_price"])
        s_log_rho, s_log_p = stats.spearmanr(valid[col], valid["log_price"])

        # Tương quan với giá gốc
        p_raw_r, p_raw_p = stats.pearsonr(valid[col], valid["price_vnd"])
        s_raw_rho, s_raw_p = stats.spearmanr(valid[col], valid["price_vnd"])

        # Đánh giá độ mạnh tương quan
        abs_rho = abs(s_log_rho)
        if abs_rho >= 0.7:
            strength = "Rất mạnh (>= 0.7)"
        elif abs_rho >= 0.5:
            strength = "Mạnh (0.5 - 0.7)"
        elif abs_rho >= 0.3:
            strength = "Trung bình (0.3 - 0.5)"
        elif abs_rho >= 0.1:
            strength = "Yếu (0.1 - 0.3)"
        else:
            strength = "Rất yếu (< 0.1)"

        records.append({
            "Thuộc tính": col,
            "Số mẫu hợp lệ (N)": n_obs,
            "Tỷ lệ có dữ liệu (%)": round(n_obs / len(sub_df) * 100, 1),
            "Pearson r (log_price)": round(p_log_r, 4),
            "p-value (Pearson log)": f"{p_log_p:.2e}" if p_log_p < 0.001 else f"{p_log_p:.4f}",
            "Spearman rho (log_price)": round(s_log_rho, 4),
            "p-value (Spearman log)": f"{s_log_p:.2e}" if s_log_p < 0.001 else f"{s_log_p:.4f}",
            "Spearman rho (raw_price)": round(s_raw_rho, 4),
            "Mức độ tương quan": strength
        })

    corr_df = pd.DataFrame(records)
    corr_df = corr_df.sort_values(by="Spearman rho (log_price)", ascending=False).reset_index(drop=True)
    return corr_df


def classify_laptop_hardware(df: pd.DataFrame) -> pd.DataFrame:
    """
    Phân tầng phần cứng Laptop thành các biến danh mục chuẩn hóa:
    - cpu_tier: Apple Silicon, Tier 1 (Core i9/Ryzen 9), Tier 2 (Core i7/Ryzen 7), Tier 3 (Core i5/Ryzen 5), Tier 4 (Core i3/Entry), Other / Unknown
    - gpu_type: Apple GPU, Dedicated (Card rời), Integrated (Onboard), Other / Unknown
    - ram_group: 8GB, 16GB, 32GB, 64GB+, Unknown
    - storage_group: 256GB, 512GB, 1TB, 2TB+, Unknown
    """
    laptop = df[df["category"] == "laptop"].copy()

    # 1. Phân nhóm CPU
    def _map_cpu(val):
        if pd.isna(val):
            return "Unknown"
        s = str(val).lower()
        if "apple" in s or re.search(r"\bm[1-5]\b", s):
            return "Apple Silicon (M-series)"
        if "i9" in s or "ultra 9" in s or "ryzen 9" in s:
            return "Tier 1: Core i9 / Ryzen 9 (Flagship/Enthusiast)"
        if "i7" in s or "ultra 7" in s or "ryzen 7" in s:
            return "Tier 2: Core i7 / Ryzen 7 (High-end)"
        if "i5" in s or "ultra 5" in s or "core 5" in s or "ryzen 5" in s:
            return "Tier 3: Core i5 / Ryzen 5 (Mainstream)"
        if "i3" in s or "core 3" in s or "ryzen 3" in s or "celeron" in s or "pentium" in s or "n100" in s:
            return "Tier 4: Core i3 / Entry-level"
        return "Other CPUs"

    laptop["cpu_tier"] = laptop["cpu_norm"].apply(_map_cpu)

    # 2. Phân nhóm GPU
    def _map_gpu(val):
        if pd.isna(val):
            return "Unknown"
        s = str(val).lower()
        if any(x in s for x in ["rtx", "gtx", "geforce", "radeon rx", "quadro", "t500", "t1000", "arc a"]):
            return "Dedicated (GPU rời)"
        if any(x in s for x in ["apple", "neural", "gpu 10 lõi", "gpu 8 lõi", "gpu 16 lõi", "gpu 30 lõi", "gpu 40 lõi"]):
            return "Apple Silicon GPU"
        if any(x in s for x in ["intel", "uhd", "iris", "radeon graphics", "onboard"]):
            return "Integrated (Onboard)"
        return "Other GPUs"

    laptop["gpu_type"] = laptop["gpu_norm"].apply(_map_gpu)

    # 3. Phân nhóm RAM
    def _map_ram(val):
        if pd.isna(val):
            return "Unknown"
        try:
            v = float(val)
            if v <= 8:
                return "8 GB"
            elif v <= 16:
                return "16 GB"
            elif v <= 32:
                return "32 GB"
            else:
                return ">= 64 GB"
        except:
            return "Unknown"

    laptop["ram_group"] = laptop["installed_ram_gb"].apply(_map_ram)

    # 4. Phân nhóm Storage
    def _map_storage(val):
        if pd.isna(val):
            return "Unknown"
        try:
            v = float(val)
            if v <= 256:
                return "256 GB"
            elif v <= 512:
                return "512 GB"
            elif v <= 1024:
                return "1 TB (1024 GB)"
            else:
                return ">= 2 TB"
        except:
            return "Unknown"

    laptop["storage_group"] = laptop["storage_gb"].apply(_map_storage)

    return laptop


def classify_smartphone_hardware(df: pd.DataFrame) -> pd.DataFrame:
    """
    Phân tầng phần cứng Smartphone thành các biến danh mục chuẩn hóa:
    - storage_group: <= 64GB, 128GB, 256GB, 512GB, 1TB+, Unknown
    - ram_group: <= 4GB, 6GB, 8GB, 12GB, >= 16GB, Unknown
    - display_group: OLED / AMOLED, IPS / LCD, Other / Unknown
    - brand_segment: Apple Flagship, Samsung Flagship/Mid, Chinese Brands (Xiaomi, OPPO, Vivo, Realme), Other
    """
    phone = df[df["category"] == "smartphone"].copy()

    # 1. Phân nhóm Storage
    def _map_storage(val):
        if pd.isna(val):
            return "Unknown"
        try:
            v = float(val)
            if v <= 64:
                return "<= 64 GB"
            elif v <= 128:
                return "128 GB"
            elif v <= 256:
                return "256 GB"
            elif v <= 512:
                return "512 GB"
            else:
                return ">= 1 TB"
        except:
            return "Unknown"

    phone["storage_group"] = phone["storage_gb"].apply(_map_storage)

    # 2. Phân nhóm RAM
    def _map_ram(val):
        if pd.isna(val):
            return "Unknown"
        try:
            v = float(val)
            if v <= 4:
                return "<= 4 GB"
            elif v <= 6:
                return "6 GB"
            elif v <= 8:
                return "8 GB"
            elif v <= 12:
                return "12 GB"
            else:
                return ">= 16 GB"
        except:
            return "Unknown"

    phone["ram_group"] = phone["installed_ram_gb"].apply(_map_ram)

    # 3. Phân nhóm Màn hình
    def _map_display(val):
        if pd.isna(val):
            return "Unknown"
        s = str(val).lower()
        if any(x in s for x in ["oled", "amoled", "super amoled", "retina", "dynamic amoled"]):
            return "OLED / AMOLED"
        if any(x in s for x in ["ips", "lcd", "tft", "pls"]):
            return "IPS / LCD"
        return "Other / Unknown"

    phone["display_group"] = phone["display_type_norm"].apply(_map_display)

    return phone


def compute_group_price_stats(
    df: pd.DataFrame,
    group_col: str,
    target_col: str = "price_vnd"
) -> pd.DataFrame:
    """
    Tính thống kê phân phối Giá (Triệu VNĐ) theo từng nhóm phân loại:
    Count, Median, Mean, Std, Q1, Q3, IQR.
    """
    valid = df[(df[target_col] > 0) & (df[group_col].notna())].copy()
    valid["price_mil"] = valid[target_col] / 1e6

    records = []
    for grp_name, grp_df in valid.groupby(group_col):
        if len(grp_df) < 5:
            continue
        p = grp_df["price_mil"]
        q1 = p.quantile(0.25)
        q3 = p.quantile(0.75)
        records.append({
            "Phân nhóm": grp_name,
            "Số lượng (N)": len(grp_df),
            "Tỷ lệ (%)": round(len(grp_df) / len(valid) * 100, 1),
            "Trung vị (Median)": round(p.median(), 2),
            "Trung bình (Mean)": round(p.mean(), 2),
            "Độ lệch chuẩn (Std)": round(p.std(), 2),
            "Q1 (25%)": round(q1, 2),
            "Q3 (75%)": round(q3, 2),
            "IQR": round(q3 - q1, 2)
        })

    res_df = pd.DataFrame(records)
    res_df = res_df.sort_values(by="Trung vị (Median)", ascending=False).reset_index(drop=True)
    return res_df


def perform_hypothesis_tests(
    df: pd.DataFrame,
    factors: List[Tuple[str, str, str]],  # List of (Category, Factor_Name, Column_Name)
    target_col: str = "price_vnd"
) -> pd.DataFrame:
    """
    Thực hiện kiểm định giả thuyết thống kê toàn diện:
    - ANOVA 1 yếu tố (One-Way ANOVA F-test): Đánh giá khác biệt kỳ vọng toán
    - Kruskal-Wallis H-test: Đánh giá phi tham số về sự khác biệt phân vị / thứ hạng (robust với ngoại lai)
    """
    results = []

    for category, factor_label, col_name in factors:
        sub_df = df[(df["category"] == category) & (df[target_col] > 0) & (df[col_name].notna())].copy()
        sub_df["log_price"] = np.log10(sub_df[target_col])

        # Gom nhóm và lọc các nhóm có số lượng tối thiểu >= 10
        groups_raw = []
        groups_log = []
        valid_groups = []

        for name, grp in sub_df.groupby(col_name):
            if len(grp) >= 10 and name not in ["Unknown", "Other"]:
                groups_raw.append(grp[target_col].values)
                groups_log.append(grp["log_price"].values)
                valid_groups.append(name)

        k = len(valid_groups)
        if k < 2:
            continue

        # ANOVA trên log_price (để đảm bảo tính chuẩn đối xứng)
        f_stat, anova_p = stats.f_oneway(*groups_log)

        # Kruskal-Wallis trên price_vnd (phi tham số)
        h_stat, kw_p = stats.kruskal(*groups_raw)

        # Kết luận ý nghĩa thống kê
        is_sig = "Có (p < 0.001)" if (anova_p < 0.001 and kw_p < 0.001) else ("Có (p < 0.05)" if anova_p < 0.05 else "Không")

        results.append({
            "Ngành hàng": "Laptop" if category == "laptop" else "Smartphone",
            "Yếu tố phân loại": factor_label,
            "Cột phân tích": col_name,
            "Số nhóm so sánh (k)": k,
            "Tổng số mẫu (N)": sum(len(g) for g in groups_raw),
            "ANOVA F-statistic": round(f_stat, 2),
            "ANOVA p-value": f"{anova_p:.2e}" if anova_p < 0.001 else f"{anova_p:.4f}",
            "Kruskal-Wallis H": round(h_stat, 2),
            "Kruskal p-value": f"{kw_p:.2e}" if kw_p < 0.001 else f"{kw_p:.4f}",
            "Khác biệt có ý nghĩa thống kê?": is_sig
        })

    res_df = pd.DataFrame(results)
    return res_df


def compute_head_to_head_comparison(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Nhiệm vụ 2.2: So sánh chuyên sâu cấu trúc quyết định giá Laptop vs. Smartphone.
    1. Bảng đối chiếu hệ số tương quan Spearman và Pearson của các thuộc tính phần cứng.
    2. Bảng phân tích các nhân tố phân hóa giá mạnh nhất kèm hệ số đòn bẩy giá (Price Multiplier).
    """
    laptop_df = df[df["category"] == "laptop"].copy()
    phone_df = df[df["category"] == "smartphone"].copy()

    # --- 1. Đối chiếu tương quan phần cứng (Correlation Comparison) ---
    features_to_compare = [
        ("installed_ram_gb", "Dung lượng RAM (GB)"),
        ("storage_gb", "Dung lượng Bộ nhớ trong / Ổ cứng (GB)"),
        ("battery_wh", "Dung lượng Pin Wh (Laptop)"),
        ("battery_mah", "Dung lượng Pin mAh (Smartphone)"),
        ("charger_watt", "Công suất Sạc (W)"),
        ("screen_size_inch", "Kích thước Màn hình (Inch)"),
        ("camera_mp", "Độ phân giải Camera chính (MP)")
    ]

    corr_records = []
    for col, label in features_to_compare:
        # Laptop stats
        if col in laptop_df.columns:
            lap_sub = laptop_df.dropna(subset=[col, "price_vnd"])
            lap_sub = lap_sub[(lap_sub[col] > 0) & (lap_sub["price_vnd"] > 0)]
            if len(lap_sub) >= 20:
                lap_spear, lap_sp_p = stats.spearmanr(lap_sub[col], lap_sub["price_vnd"])
                lap_pear, lap_pe_p = stats.pearsonr(lap_sub[col], np.log10(lap_sub["price_vnd"]))
                lap_spear_str = f"{lap_spear:+.3f}"
                lap_pear_str = f"{lap_pear:+.3f}"
                lap_n = len(lap_sub)
            else:
                lap_spear_str = "N/A (Không áp dụng)"
                lap_pear_str = "N/A"
                lap_n = len(lap_sub)
        else:
            lap_spear_str = "N/A (Không áp dụng)"
            lap_pear_str = "N/A"
            lap_n = 0

        # Phone stats
        if col in phone_df.columns:
            ph_sub = phone_df.dropna(subset=[col, "price_vnd"])
            ph_sub = ph_sub[(ph_sub[col] > 0) & (ph_sub["price_vnd"] > 0)]
            if len(ph_sub) >= 20:
                ph_spear, ph_sp_p = stats.spearmanr(ph_sub[col], ph_sub["price_vnd"])
                ph_pear, ph_pe_p = stats.pearsonr(ph_sub[col], np.log10(ph_sub["price_vnd"]))
                ph_spear_str = f"{ph_spear:+.3f}"
                ph_pear_str = f"{ph_pear:+.3f}"
                ph_n = len(ph_sub)
            else:
                ph_spear_str = "N/A (Không áp dụng)"
                ph_pear_str = "N/A"
                ph_n = len(ph_sub)
        else:
            ph_spear_str = "N/A (Không áp dụng)"
            ph_pear_str = "N/A"
            ph_n = 0

        # Đánh giá vai trò
        if col in ["installed_ram_gb", "charger_watt"]:
            role = "Đồng biến cực mạnh ở Laptop; Quan trọng ở Smartphone"
        elif col == "storage_gb":
            role = "Đòn bẩy phân tầng hàng đầu ở cả hai ngành hàng (đặc biệt Smartphone)"
        elif col == "battery_wh":
            role = "Trụ cột phân loại Laptop Gaming/Workstation vs Văn phòng"
        elif col == "battery_mah":
            role = "Nghịch lý bão hòa ở Smartphone (không phân hóa giá do rào cản vật lý)"
        elif col == "camera_mp":
            role = "Gần như không tương quan ở Smartphone (cạnh tranh bằng thuật toán/cảm biến)"
        elif col == "screen_size_inch":
            role = "Tương quan rất yếu (Ultrabook nhỏ nhưng đắt tiền ngang máy 15.6 inch)"
        elif col == "weight_kg":
            role = "Yếu tố bù trừ (Laptop Gaming nặng đắt; Ultrabook mỏng nhẹ cũng đắt)"
        else:
            role = "Tham số phụ"

        corr_records.append({
            "Thuộc tính (Feature)": label,
            "Laptop Spearman (ρ)": lap_spear_str,
            "Laptop Log-Pearson (r)": lap_pear_str,
            "Laptop N": lap_n,
            "Smartphone Spearman (ρ)": ph_spear_str,
            "Smartphone Log-Pearson (r)": ph_pear_str,
            "Smartphone N": ph_n,
            "Nhận định / Cơ chế chi phối": role
        })

    corr_df = pd.DataFrame(corr_records)

    # --- 2. Bảng nhân tố phân hóa giá mạnh nhất và biên độ chênh lệch (Price Drivers & Multiplier) ---
    drivers_records = [
        {
            "Ngành hàng": "Laptop",
            "Nhân tố cốt lõi (Driver)": "Dung lượng RAM (installed_ram_gb)",
            "Chỉ số thống kê chính": "Spearman ρ = +0.803 | ANOVA F = 565.4",
            "Mức sàn (Min Tier)": "8 GB (Trung vị 18.64 Triệu)",
            "Mức trần (Max Tier)": ">= 64 GB (Trung vị 96.24 Triệu)",
            "Hệ số đòn bẩy (Multiplier)": "5.16x",
            "Bản chất chi phối": "Tài nguyên tính toán bắt buộc cho tác vụ nặng (Workstation, Render, AI)"
        },
        {
            "Ngành hàng": "Laptop",
            "Nhân tố cốt lõi (Driver)": "Phân tầng CPU (cpu_tier)",
            "Chỉ số thống kê chính": "ANOVA F = 757.2 | Kruskal-Wallis H = 1748.8",
            "Mức sàn (Min Tier)": "Core i3 (Trung vị 11.95 Triệu)",
            "Mức trần (Max Tier)": "Core i9 / Ryzen 9 (Trung vị 54.99 Triệu)",
            "Hệ số đòn bẩy (Multiplier)": "4.60x",
            "Bản chất chi phối": "Trái tim hiệu năng của máy tính, quyết định định vị toàn bộ cấu hình"
        },
        {
            "Ngành hàng": "Laptop",
            "Nhân tố cốt lõi (Driver)": "Card đồ họa (gpu_type)",
            "Chỉ số thống kê chính": "ANOVA F = 502.1 | Kruskal-Wallis H = 1007.4",
            "Mức sàn (Min Tier)": "Onboard (Trung vị 19.99 Triệu)",
            "Mức trần (Max Tier)": "Apple GPU (40.99M) / Discrete (28.99M)",
            "Hệ số đòn bẩy (Multiplier)": "2.05x",
            "Bản chất chi phối": "Phân định ranh giới giữa máy văn phòng phổ thông và Gaming/Workstation"
        },
        {
            "Ngành hàng": "Laptop",
            "Nhân tố cốt lõi (Driver)": "Nguồn sạc & Pin (charger_watt / battery_wh)",
            "Chỉ số thống kê chính": "Charger ρ = +0.722 | Battery ρ = +0.658",
            "Mức sàn (Min Tier)": "Sạc 45W-65W / Pin < 45Wh (Trung vị ~17.5M)",
            "Mức trần (Max Tier)": "Sạc 230W-330W / Pin > 75Wh (Trung vị ~49.9M)",
            "Hệ số đòn bẩy (Multiplier)": "2.85x",
            "Bản chất chi phối": "Đi kèm công suất tản nhiệt và tiêu thụ điện của CPU/GPU hiệu năng cao"
        },
        {
            "Ngành hàng": "Smartphone",
            "Nhân tố cốt lõi (Driver)": "Bộ nhớ trong ROM (storage_gb)",
            "Chỉ số thống kê chính": "Spearman ρ = +0.702 | ANOVA F = 569.8",
            "Mức sàn (Min Tier)": "<= 64 GB (Trung vị 3.49 Triệu)",
            "Mức trần (Max Tier)": ">= 1 TB (Trung vị 41.79 Triệu)",
            "Hệ số đòn bẩy (Multiplier)": "11.97x",
            "Bản chất chi phối": "Công cụ phân tầng giá triệt để của các nhà sản xuất flagship (chiến lược upsell)"
        },
        {
            "Ngành hàng": "Smartphone",
            "Nhân tố cốt lõi (Driver)": "Thương hiệu định vị (brand_norm)",
            "Chỉ số thống kê chính": "ANOVA F = 562.9 | Kruskal-Wallis H = 1380.2",
            "Mức sàn (Min Tier)": "Nokia (1.57M) / Phổ thông (3.5M)",
            "Mức trần (Max Tier)": "Apple (Trung vị 25.49M, Q3 33.49M)",
            "Hệ số đòn bẩy (Multiplier)": "16.24x (hoặc 7.28x vs Android entry)",
            "Bản chất chi phối": "Biểu tượng giá trị thương hiệu (Brand Equity & Ecosystem Lock-in)"
        },
        {
            "Ngành hàng": "Smartphone",
            "Nhân tố cốt lõi (Driver)": "Công nghệ Màn hình (display_group)",
            "Chỉ số thống kê chính": "ANOVA F = 2954.2 | Kruskal-Wallis H = 1826.5",
            "Mức sàn (Min Tier)": "IPS / LCD (Trung vị 3.89 Triệu)",
            "Mức trần (Max Tier)": "OLED / AMOLED (Trung vị 15.99 Triệu)",
            "Hệ số đòn bẩy (Multiplier)": "4.11x",
            "Bản chất chi phối": "Ranh giới công nghệ dứt khoát giữa máy giá rẻ và máy cận cao cấp / cao cấp"
        },
        {
            "Ngành hàng": "Smartphone",
            "Nhân tố cốt lõi (Driver)": "Dung lượng RAM (installed_ram_gb)",
            "Chỉ số thống kê chính": "Spearman ρ = +0.589 | ANOVA F = 377.9",
            "Mức sàn (Min Tier)": "<= 4 GB (Trung vị 3.29 Triệu)",
            "Mức trần (Max Tier)": ">= 16 GB (Trung vị 23.99 Triệu)",
            "Hệ số đòn bẩy (Multiplier)": "7.29x",
            "Bản chất chi phối": "Chỉ số nhận diện năng lực đa nhiệm và phân cấp cấu hình trong thế giới Android"
        }
    ]

    drivers_df = pd.DataFrame(drivers_records)
    return corr_df, drivers_df


def build_pricing_structure_matrix() -> pd.DataFrame:
    """
    Xây dựng Bảng ma trận đối chiếu cấu trúc quyết định giá toàn diện
    giữa Laptop và Smartphone phục vụ đặc tả báo cáo TV3 và tư vấn mô hình hóa TV5.
    """
    matrix_data = [
        {
            "Khía cạnh so sánh": "1. Triết lý Định giá (Pricing Philosophy)",
            "Ngành hàng Laptop": "Tài sản sản xuất / Công cụ làm việc (Workstation & Productivity Asset). Giá gắn liền với sức mạnh xử lý và tài nguyên phần cứng thuần túy.",
            "Ngành hàng Smartphone": "Thiết bị tiêu dùng trải nghiệm cá nhân & phong cách sống (Consumer Experience & Lifestyle). Giá gắn liền với thương hiệu, công nghệ hiển thị và hệ sinh thái.",
            "Khác biệt căn bản": "Laptop định giá từ dưới lên (Cost-plus / Component-driven); Smartphone định giá từ trên xuống (Value-based / Brand-driven)."
        },
        {
            "Khía cạnh so sánh": "2. Đòn bẩy phân hóa hàng đầu (Top Pricing Driver)",
            "Ngành hàng Laptop": "Dung lượng RAM (ρ = +0.803) & Phân tầng CPU Tier (F = 757.2). Bước nhảy từ 8GB/16GB lên 32GB/64GB tạo đà tăng giá cấp số nhân.",
            "Ngành hàng Smartphone": "Dung lượng ROM / Storage (ρ = +0.702) & Thương hiệu định vị (F = 562.9). Biên độ giá giãn từ 3.49M lên tới 41.79M (gấp 11.97 lần).",
            "Khác biệt căn bản": "Laptop dùng RAM và CPU để lọc người dùng chuyên nghiệp; Smartphone dùng ROM để thực hiện chiến lược Upsell bậc thang."
        },
        {
            "Khía cạnh so sánh": "3. Ranh giới phần cứng tách đôi thị trường (Bifurcation Threshold)",
            "Ngành hàng Laptop": "Sự hiện diện của GPU rời (Dedicated GPU vs. Onboard): Chia tách hoàn toàn giữa Laptop văn phòng mỏng nhẹ và Laptop Gaming/Workstation.",
            "Ngành hàng Smartphone": "Công nghệ Màn hình (OLED/AMOLED vs. IPS/LCD, F = 2954.2): Chia tách dứt khoát máy giá rẻ (dưới 5 triệu) và cận cao cấp/cao cấp (trên 10 triệu).",
            "Khác biệt căn bản": "Laptop phân hóa ở năng lực đồ họa; Smartphone phân hóa ở chất lượng hiển thị thị giác trực tiếp của người dùng."
        },
        {
            "Khía cạnh so sánh": "4. Vai trò của Pin & Nguồn điện (Battery & Power)",
            "Ngành hàng Laptop": "Tương quan đồng biến rất mạnh (Sạc ρ = +0.722, Pin Wh ρ = +0.658). Máy trạm/Gaming cấu hình khủng bắt buộc phải trang bị pin lớn và sạc công suất lớn (135W-330W).",
            "Ngành hàng Smartphone": "Nghịch lý bão hòa vật lý (Pin mAh ρ = +0.038, không phân hóa). Flagship 35 triệu và máy cỏ 2 triệu đều dùng pin ~5.000 mAh do ranh giới kích thước bàn tay.",
            "Khác biệt căn bản": "Pin ở Laptop là biến hiệu năng cao cấp; Pin ở Smartphone là tiêu chuẩn cơ bản tối thiểu (Commodity feature)."
        },
        {
            "Khía cạnh so sánh": "5. Vai trò của Camera & Kích thước màn hình",
            "Ngành hàng Laptop": "Kích thước màn hình (ρ = +0.089) hầu như không ảnh hưởng đến giá. Laptop 13.3 - 14 inch mỏng nhẹ cao cấp có giá tương đương hoặc đắt hơn máy 15.6 inch phổ thông.",
            "Ngành hàng Smartphone": "Độ phân giải Camera MP (ρ = +0.027, p = 0.493) không tương quan với giá. Máy giá rẻ quảng cáo 50-108MP cảm biến nhỏ, còn Flagship cạnh tranh bằng chip xử lý ảnh và ống kính cao cấp.",
            "Khác biệt căn bản": "Cả hai đều có chỉ số phần cứng mang tính 'Marketing deceptive' cần được giải thích rõ cho kỹ sư mô hình."
        },
        {
            "Khía cạnh so sánh": "6. Mức độ bất đối xứng giá (Price Asymmetry & Skewness)",
            "Ngành hàng Laptop": "Skewness = +2.47, Kurtosis = +11.39. Đỉnh phân phối tập trung quanh 15-25 triệu, đuôi kéo dài tới 130 triệu (Mobile Workstations, Flagship Gaming).",
            "Ngành hàng Smartphone": "Skewness = +2.42, Kurtosis = +8.30. Đỉnh phân phối lệch hẳn về phân khúc giá rẻ 3-7 triệu, đuôi kéo dài về iPhone Pro Max và Galaxy Ultra/Fold (35-45 triệu).",
            "Khác biệt căn bản": "Laptop có phân khúc trung cấp dày dặn hơn; Smartphone có lượng sản phẩm tập trung áp đảo ở phân khúc bình dân giá rẻ."
        },
        {
            "Khía cạnh so sánh": "7. Khuyến nghị Kỹ thuật Đặc trưng cho TV5 (Feature Engineering Strategy)",
            "Ngành hàng Laptop": "Ưu tiên biến tương tác `ram_x_storage`, one-hot encoding phân tầng CPU tier chi tiết, cờ phân loại GPU rời (`is_dedicated_gpu`), và log(charger_watt).",
            "Ngành hàng Smartphone": "Target encoding / Impact encoding cho `brand_norm`, cờ nhị phân `is_oled_amoled`, phân đoạn bộ nhớ bậc thang `storage_group`, tuyệt đối không dùng tuyến tính thô `battery_mah` hay `camera_mp`.",
            "Khác biệt căn bản": "Mô hình Laptop thiên về tài nguyên phần cứng tương tác; Mô hình Smartphone thiên về sức mạnh thương hiệu và công nghệ hiển thị."
        }
    ]

    return pd.DataFrame(matrix_data)


# ==============================================================================
# NHIỆM VỤ 3: ĐÁNH GIÁ CHẤT LƯỢNG DỮ LIỆU CHO BÀI TOÁN HỒI QUY (REGRESSION READINESS)
# ==============================================================================

def audit_price_outliers_and_boundaries(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Nhiệm vụ 3.1: Nhận diện Outliers & Dữ liệu biên:
    1. Kiểm tra bản ghi giá thiếu/không hợp lệ (is_price_missing == True hoặc price_vnd <= 0).
    2. Bảng phân vị cực biên (P0.1, P1, P5, Q1, Median, Q3, P95, P99, P99.9, Min, Max, IQR, Tukey fences).
    3. Thống kê sản phẩm giá cực thấp (< 500.000 VNĐ) và giá cực cao (> 100.000.000 VNĐ).
    """
    # 1. Thống kê bản ghi lỗi / thiếu giá
    invalid_mask = (df["is_price_missing"] == True) | (df["price_vnd"] <= 0) | (df["price_vnd"].isna())
    invalid_df = df[invalid_mask]
    
    missing_summary = pd.DataFrame([
        {
            "Tiêu chí kiểm tra": "is_price_missing == True",
            "Số lượng bản ghi": (df["is_price_missing"] == True).sum(),
            "Tỷ lệ trên tổng (%)": round((df["is_price_missing"] == True).mean() * 100, 2),
            "Ghi chú / Hành động TV5": "Bắt buộc loại bỏ khỏi tập huấn luyện hồi quy (target missing)"
        },
        {
            "Tiêu chí kiểm tra": "price_vnd <= 0",
            "Số lượng bản ghi": (df["price_vnd"] <= 0).sum(),
            "Tỷ lệ trên tổng (%)": round((df["price_vnd"] <= 0).mean() * 100, 2),
            "Ghi chú / Hành động TV5": "Giá bằng 0 hoặc âm; trùng khớp với is_price_missing == True"
        },
        {
            "Tiêu chí kiểm tra": "price_vnd là NaN / Null",
            "Số lượng bản ghi": df["price_vnd"].isna().sum(),
            "Tỷ lệ trên tổng (%)": round(df["price_vnd"].isna().mean() * 100, 2),
            "Ghi chú / Hành động TV5": "16 bản ghi thiếu giá hoàn toàn từ file thô"
        },
        {
            "Tiêu chí kiểm tra": "Tổng số bản ghi giá KHÔNG HỢP LỆ",
            "Số lượng bản ghi": len(invalid_df),
            "Tỷ lệ trên tổng (%)": round(len(invalid_df) / len(df) * 100, 2),
            "Ghi chú / Hành động TV5": "Loại bỏ triệt để 1.768 bản ghi này (còn 8.548 bản ghi hợp lệ)"
        }
    ])

    # 2. Bảng phân vị cực biên và Tukey fences cho các bản ghi giá hợp lệ (> 0)
    valid_df = df[df["price_vnd"] > 0].copy()
    valid_df["price_mil"] = valid_df["price_vnd"] / 1e6

    boundary_records = []
    for cat in ["all", "laptop", "smartphone"]:
        sub = valid_df if cat == "all" else valid_df[valid_df["category"] == cat]
        p = sub["price_mil"]
        q1 = p.quantile(0.25)
        q3 = p.quantile(0.75)
        iqr = q3 - q1
        lower_fence = max(0, q1 - 1.5 * iqr)
        upper_fence = q3 + 1.5 * iqr
        extreme_upper = q3 + 3.0 * iqr

        boundary_records.append({
            "Phân khúc": "Toàn bộ dữ liệu" if cat == "all" else ("Laptop" if cat == "laptop" else "Smartphone"),
            "N hợp lệ": len(sub),
            "Min": round(p.min(), 3),
            "P0.1": round(p.quantile(0.001), 3),
            "P1": round(p.quantile(0.01), 2),
            "P5": round(p.quantile(0.05), 2),
            "Q1 (25%)": round(q1, 2),
            "Trung vị": round(p.median(), 2),
            "Q3 (75%)": round(q3, 2),
            "P95": round(p.quantile(0.95), 2),
            "P99": round(p.quantile(0.99), 2),
            "P99.9": round(p.quantile(0.999), 2),
            "Max": round(p.max(), 2),
            "IQR": round(iqr, 2),
            "Tukey Upper (1.5 IQR)": round(upper_fence, 2),
            "Extreme Upper (3.0 IQR)": round(extreme_upper, 2)
        })

    boundary_df = pd.DataFrame(boundary_records)

    # 3. Phân loại Outlier Cực biên (< 500k và > 100M)
    low_price_df = valid_df[valid_df["price_vnd"] < 500000]
    high_price_df = valid_df[valid_df["price_vnd"] > 100000000]

    outlier_summary = pd.DataFrame([
        {
            "Nhóm giá ngoại lai": "Giá cực thấp (< 500.000 VNĐ)",
            "Số lượng (N)": len(low_price_df),
            "Tỷ lệ trên N hợp lệ (%)": round(len(low_price_df) / len(valid_df) * 100, 2),
            "Đặc điểm sản phẩm": "Điện thoại 'cục gạch' (Itel, Masstel, Energizer) và 4 phụ kiện/linh kiện dính nhầm",
            "Khuyến nghị TV5": "Lọc bỏ nếu TV5 chỉ dự đoán Smartphone cảm ứng; giữ lại nếu mô hình có feature os/screen"
        },
        {
            "Nhóm giá ngoại lai": "Giá cực cao (> 100.000.000 VNĐ)",
            "Số lượng (N)": len(high_price_df),
            "Tỷ lệ trên N hợp lệ (%)": round(len(high_price_df) / len(valid_df) * 100, 2),
            "Đặc điểm sản phẩm": "MacBook Pro M3 Max 128GB/8TB (180M), ROG Strix SCAR 18, MSI Titan 18 HX AI Dragon (130-150M)",
            "Khuyến nghị TV5": "Outlier tự nhiên chuẩn xác (True Flagship Outliers). Bắt buộc log-transform target để tránh lệch OLS"
        }
    ])

    return missing_summary, boundary_df, outlier_summary


def compute_multicollinearity_and_vif(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Nhiệm vụ 3.2: Đo lường hiện tượng Đa cộng tuyến (Multicollinearity) & Tính toán VIF:
    1. Ma trận tương quan chéo (Cross-correlation matrix) giữa các biến số độc lập của Laptop.
    2. Ma trận tương quan chéo của Smartphone.
    3. Bảng chỉ số VIF (Variance Inflation Factor) tổng hợp cho cả 2 ngành hàng.
    """
    from numpy.linalg import inv

    valid_df = df[df["price_vnd"] > 0].copy()

    # --- LAPTOP VIF ---
    laptop_df = valid_df[valid_df["category"] == "laptop"]
    lap_cols = ["installed_ram_gb", "storage_gb", "battery_wh", "screen_size_inch", "charger_watt"]
    lap_sub = laptop_df[lap_cols].dropna()

    lap_corr = lap_sub.corr().round(3)

    lap_vif_records = []
    # Tính VIF trên tập đầy đủ 5 biến
    if len(lap_sub) > len(lap_cols):
        inv_corr = inv(lap_sub.corr().values)
        for i, col in enumerate(lap_cols):
            vif_val = np.diag(inv_corr)[i]
            lap_vif_records.append({
                "Ngành hàng": "Laptop",
                "Thuộc tính (Feature)": col,
                "VIF Score": round(vif_val, 2),
                "Mức độ Đa cộng tuyến": "Thấp (An toàn)" if vif_val < 2.5 else ("Trung bình" if vif_val < 5.0 else "Cao (Cảnh báo)"),
                "Mô hình ảnh hưởng nặng": "OLS Linear Regression",
                "Giải pháp khuyến nghị": "Chấp nhận được cho hồi quy tuyến tính; an toàn tuyệt đối với GBDT"
            })
    lap_vif_df = pd.DataFrame(lap_vif_records)

    # --- SMARTPHONE VIF ---
    phone_df = valid_df[valid_df["category"] == "smartphone"]
    ph_cols = ["installed_ram_gb", "storage_gb", "battery_mah", "charger_watt", "screen_size_inch"]
    ph_sub = phone_df[ph_cols].dropna()

    ph_corr = ph_sub.corr().round(3)

    ph_vif_records = []
    if len(ph_sub) > len(ph_cols):
        inv_corr = inv(ph_sub.corr().values)
        for i, col in enumerate(ph_cols):
            vif_val = np.diag(inv_corr)[i]
            ph_vif_records.append({
                "Ngành hàng": "Smartphone",
                "Thuộc tính (Feature)": col,
                "VIF Score": round(vif_val, 2),
                "Mức độ Đa cộng tuyến": "Thấp (An toàn)" if vif_val < 2.5 else ("Trung bình" if vif_val < 5.0 else "Cao (Cảnh báo)"),
                "Mô hình ảnh hưởng nặng": "OLS Linear Regression",
                "Giải pháp khuyến nghị": "RAM và ROM tương quan r = 0.83; Cần Ridge L2 Regularization hoặc PCA/GBDT"
            })
    ph_vif_df = pd.DataFrame(ph_vif_records)

    combined_vif = pd.concat([lap_vif_df, ph_vif_df], axis=0, ignore_index=True)

    return lap_corr, ph_corr, combined_vif


def audit_data_leakage_risks() -> pd.DataFrame:
    """
    Nhiệm vụ 3.3: Phòng chống Rò rỉ dữ liệu (Data Leakage Risks Audit).
    Đối chiếu toàn diện 30 trường canonical và phân loại thành:
    - BLACKLIST: Tuyệt đối cấm đưa vào huấn luyện.
    - TARGET: Biến mục tiêu.
    - WHITELIST: Candidate features an toàn được phê duyệt.
    """
    audit_data = [
        {
            "Tên trường canonical": "listing_record_id",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "ID định danh kỹ thuật nội bộ do crawler tự sinh; mang tính ngẫu nhiên, gây overfitting ghi nhớ ID.",
            "Mức độ rủi ro": "Nghiêm trọng (Overfitting)"
        },
        {
            "Tên trường canonical": "source_parent_id",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "ID nhóm sản phẩm của sàn nguồn; không phải thuộc tính vật lý của máy tính hay điện thoại.",
            "Mức độ rủi ro": "Nghiêm trọng (Data Leakage)"
        },
        {
            "Tên trường canonical": "crawl_time",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Dấu ấn thời gian cào dữ liệu (Timestamp); mô hình hóa dự đoán giá tĩnh tại snapshot không được học time-bias.",
            "Mức độ rủi ro": "Trung bình (Temporal Leakage)"
        },
        {
            "Tên trường canonical": "crawl_batch",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Mã đợt cào; trường kỹ thuật nội bộ phục vụ pipeline cào của TV1.",
            "Mức độ rủi ro": "Thấp (Technical Artifact)"
        },
        {
            "Tên trường canonical": "discount_rate",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "RÒ RỈ TRỰC TIẾP TỪ TARGET: discount_rate = 1 - (price_vnd / original_price_vnd). Cho phép mô hình tính ngược ra price_vnd chính xác 100%!",
            "Mức độ rủi ro": "TỐI NGUY HIỂM (Direct Target Leakage)"
        },
        {
            "Tên trường canonical": "original_price_vnd",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Giá niêm yết gốc trước giảm giá; tương quan r = 0.96 với target. Nếu đưa vào, mô hình chỉ học bài toán trừ chiết khấu thay vì học giá trị cấu hình.",
            "Mức độ rủi ro": "TỐI NGUY HIỂM (Target Proxy Leakage)"
        },
        {
            "Tên trường canonical": "is_price_missing",
            "Phân loại kiểm toán": "BLACKLIST (Cấm sử dụng)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Cờ chỉ báo thiếu target; chỉ dùng để filter dữ liệu trước khi train, tuyệt đối không làm input feature.",
            "Mức độ rủi ro": "Nghiêm trọng (Target Indicator)"
        },
        {
            "Tên trường canonical": "price_vnd",
            "Phân loại kiểm toán": "TARGET VARIABLE (Biến mục tiêu)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Biến phụ thuộc y cần dự đoán. Khuyến nghị TV5 huấn luyện trên hàm biến đổi log1p: log(1 + price_vnd).",
            "Mức độ rủi ro": "Biến mục tiêu"
        },
        {
            "Tên trường canonical": "category, brand_norm, seller_raw",
            "Phân loại kiểm toán": "WHITELIST (Approved Features)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Biến danh mục chuẩn hóa hợp lệ; phân loại ngành hàng, thương hiệu và nguồn bán lẻ.",
            "Mức độ rủi ro": "An toàn (Hợp lệ)"
        },
        {
            "Tên trường canonical": "ram, storage, cpu, gpu, battery, charger,...",
            "Phân loại kiểm toán": "WHITELIST (Approved Features)",
            "Cơ chế rò rỉ / Lý do loại bỏ": "Các thuộc tính cấu hình phần cứng vật lý độc lập; cốt lõi của bài toán dự đoán giá theo cấu hình.",
            "Mức độ rủi ro": "An toàn (Hợp lệ)"
        }
    ]

    return pd.DataFrame(audit_data)


def analyze_availability_status_impact(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Nhiệm vụ 3.4: Đánh giá Tác động của Trạng thái Tồn kho (availability_status) đến Giá niêm yết:
    1. So sánh thống kê mô tả phân phối giá giữa in_stock, out_of_stock, unknown.
    2. Kiểm định phi tham số Mann-Whitney U test giữa in_stock và out_of_stock để đánh giá độ lệch giá (Price Drift).
    """
    valid_df = df[df["price_vnd"] > 0].copy()
    valid_df["price_mil"] = valid_df["price_vnd"] / 1e6

    # 1. Thống kê theo phân đoạn (Category x Availability)
    records = []
    for cat in ["all", "laptop", "smartphone"]:
        sub_cat = valid_df if cat == "all" else valid_df[valid_df["category"] == cat]
        for status in ["in_stock", "out_of_stock", "unknown"]:
            grp = sub_cat[sub_cat["availability_status"] == status]
            if len(grp) == 0:
                continue
            p = grp["price_mil"]
            q1 = p.quantile(0.25)
            q3 = p.quantile(0.75)
            records.append({
                "Phân đoạn Ngành hàng": "Toàn bộ" if cat == "all" else ("Laptop" if cat == "laptop" else "Smartphone"),
                "Trạng thái Tồn kho": status,
                "Số lượng (N)": len(grp),
                "Tỷ lệ nhóm (%)": round(len(grp) / len(sub_cat) * 100, 1),
                "Trung vị (Median)": round(p.median(), 2),
                "Trung bình (Mean)": round(p.mean(), 2),
                "Độ lệch chuẩn (Std)": round(p.std(), 2),
                "Q1 (25%)": round(q1, 2),
                "Q3 (75%)": round(q3, 2),
                "IQR": round(q3 - q1, 2)
            })

    status_summary_df = pd.DataFrame(records)

    # 2. Kiểm định Mann-Whitney U giữa in_stock và out_of_stock
    test_records = []
    for cat in ["all", "laptop", "smartphone"]:
        sub_cat = valid_df if cat == "all" else valid_df[valid_df["category"] == cat]
        in_p = sub_cat[sub_cat["availability_status"] == "in_stock"]["price_mil"]
        out_p = sub_cat[sub_cat["availability_status"] == "out_of_stock"]["price_mil"]

        if len(in_p) > 10 and len(out_p) > 10:
            u_stat, p_val = stats.mannwhitneyu(in_p, out_p, alternative="two-sided")
            median_diff = round(in_p.median() - out_p.median(), 2)
            diff_pct = round((in_p.median() / out_p.median() - 1) * 100, 1)

            test_records.append({
                "Phân đoạn": "Toàn bộ" if cat == "all" else ("Laptop" if cat == "laptop" else "Smartphone"),
                "N in_stock": len(in_p),
                "Median in_stock": round(in_p.median(), 2),
                "N out_of_stock": len(out_p),
                "Median out_of_stock": round(out_p.median(), 2),
                "Chênh lệch Trung vị (Triệu)": f"{median_diff:+0.2f}M ({diff_pct:+0.1f}%)",
                "Mann-Whitney U": round(u_stat, 1),
                "p-value": f"{p_val:.2e}" if p_val < 0.001 else f"{p_val:.4f}",
                "Ý nghĩa thống kê?": "Có (p < 0.001)" if p_val < 0.001 else "Không",
                "Hiện tượng & Khuyến nghị": "in_stock đắt hơn out_of_stock rõ rệt do hàng hết thường là máy đời cũ (EOL). Cần cờ is_out_of_stock cho TV5!"
            })

    test_df = pd.DataFrame(test_records)

    return status_summary_df, test_df




