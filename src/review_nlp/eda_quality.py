"""Quality EDA and Review Content Profiling for TV6 (Review NLP).

Executes Step 1 of the TV6 pipeline:
1. Profiles rating distribution, source retention, and usability.
2. Analyzes text character and word lengths with parametric/non-parametric statistics.
3. Audits duplicate texts and assesses consumer behavioral patterns.
4. Identifies rating-text mismatch anomalies (accidental ratings, sarcasm, service vs product complaints).
5. Tracks temporal review trends across sources (2019–2026).
6. Audits product-level review coverage and cold-start rates for TV5 Price Prediction handoff.
7. Exports tabular artifacts (CSV + Markdown) and publication-quality figures (PNG, 300 DPI).
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DIM_SOURCE_PARENTS_FILE,
    DOCS_QUALITY_REPORT_FILE,
    DOCS_TV6_DIR,
    FIGURES_TV6_DIR,
    QUALITY_REPORT_FILE,
    RATING_SENTIMENT_MAP,
    REVIEWS_TV6_ALL_FILE,
    REVIEWS_TV6_USABLE_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tv6.step1_eda")

# Visual Styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
PALETTE = ["#2b5c8f", "#d95f02", "#7570b3", "#1b9e77", "#e7298a"]


def save_table(df: pd.DataFrame, base_name: str, tables_dir: Path) -> Tuple[Path, Path]:
    """Save a DataFrame both as CSV and as formatted Markdown."""
    tables_dir.mkdir(parents=True, exist_ok=True)
    csv_path = tables_dir / f"{base_name}.csv"
    md_path = tables_dir / f"{base_name}.md"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with md_path.open("w", encoding="utf-8") as f:
        f.write(df.to_markdown(index=False))

    return csv_path, md_path


def load_dataset() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all reviews, usable reviews, and parent dimensions into DataFrames."""
    logger.info("Loading dataset from %s and %s", REVIEWS_TV6_ALL_FILE, REVIEWS_TV6_USABLE_FILE)

    df_all = pd.read_json(REVIEWS_TV6_ALL_FILE, lines=True)
    df_usable = pd.read_json(REVIEWS_TV6_USABLE_FILE, lines=True)
    df_parents = pd.read_json(DIM_SOURCE_PARENTS_FILE, lines=True)

    logger.info(
        "Loaded %d all reviews, %d usable reviews, %d parent products.",
        len(df_all),
        len(df_usable),
        len(df_parents),
    )
    return df_all, df_usable, df_parents


# -----------------------------------------------------------------------------
# TASK 1.1: Rating & Usability Distributions
# -----------------------------------------------------------------------------
def analyze_ratings_and_usability(
    df_all: pd.DataFrame, df_usable: pd.DataFrame, tables_dir: Path, figures_dir: Path
) -> Dict[str, Any]:
    """Analyze rating distributions and usability retention by source and category."""
    logger.info("Task 1.1: Analyzing ratings and usability retention...")

    # Table 1.1: Rating distribution by source
    rating_pivot = (
        pd.crosstab(
            df_all["source"],
            df_all["rating_raw"],
            margins=True,
            margins_name="Total",
        )
        .reset_index()
    )
    save_table(rating_pivot, "table_1_1_rating_source_distribution", tables_dir)

    # Table 1.2: Usable retention by source
    retention_rows = []
    for src, grp in df_all.groupby("source"):
        total = len(grp)
        usable = grp["review_usable"].sum()
        unusable = total - usable
        retention_rows.append({
            "source": src,
            "total_reviews": total,
            "usable_reviews": int(usable),
            "unusable_reviews": int(unusable),
            "retention_rate_pct": round(usable / total * 100, 2),
            "null_text_count": int((grp["review_text_status"] == "NULL").sum()),
            "empty_text_count": int((grp["review_text_status"] == "EMPTY_OR_WHITESPACE").sum()),
            "suspect_metadata_count": int(grp["review_metadata_suspect_candidate"].sum()),
        })

    total_all = len(df_all)
    usable_all = int(df_all["review_usable"].sum())
    retention_rows.append({
        "source": "Total / Overall",
        "total_reviews": total_all,
        "usable_reviews": usable_all,
        "unusable_reviews": total_all - usable_all,
        "retention_rate_pct": round(usable_all / total_all * 100, 2),
        "null_text_count": int((df_all["review_text_status"] == "NULL").sum()),
        "empty_text_count": int((df_all["review_text_status"] == "EMPTY_OR_WHITESPACE").sum()),
        "suspect_metadata_count": int(df_all["review_metadata_suspect_candidate"].sum()),
    })
    df_retention = pd.DataFrame(retention_rows)
    save_table(df_retention, "table_1_2_usable_retention_by_source", tables_dir)

    # Figure 1.1: Rating distribution by source (Usable set)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=300)
    sns.countplot(
        data=df_usable,
        x="rating_raw",
        hue="source",
        palette="Blues_r",
        edgecolor="black",
        linewidth=0.8,
        ax=ax,
    )
    ax.set_title("Phân bố Điểm Đánh giá (Rating 1–5 sao) theo Sàn TMĐT (Tập Usable)", fontsize=13, weight="bold")
    ax.set_xlabel("Điểm Đánh giá Gốc (rating_raw)", fontsize=11)
    ax.set_ylabel("Số lượng Review", fontsize=11)
    ax.legend(title="Sàn TMĐT", frameon=True)
    plt.tight_layout()
    fig1_path = figures_dir / "fig_1_1_rating_distribution_by_source.png"
    fig.savefig(fig1_path)
    plt.close(fig)

    # Figure 1.2: Usable vs Unusable Breakdown
    df_plot_ret = df_retention[df_retention["source"] != "Total / Overall"].copy()
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    bars1 = ax.bar(df_plot_ret["source"], df_plot_ret["usable_reviews"], label="Usable (Đủ điều kiện NLP)", color="#2b5c8f")
    bars2 = ax.bar(
        df_plot_ret["source"],
        df_plot_ret["unusable_reviews"],
        bottom=df_plot_ret["usable_reviews"],
        label="Unusable (Rỗng / Thiếu text / Nghi vấn)",
        color="#d95f02",
    )
    ax.set_title("Tỷ lệ Giữ lại Review Hợp lệ theo Sàn Thu thập", fontsize=13, weight="bold")
    ax.set_xlabel("Sàn TMĐT", fontsize=11)
    ax.set_ylabel("Số lượng Bản ghi", fontsize=11)
    for b1, b2, ret in zip(bars1, bars2, df_plot_ret["retention_rate_pct"]):
        ax.text(
            b1.get_x() + b1.get_width() / 2,
            b1.get_height() / 2,
            f"{ret}%",
            ha="center",
            va="center",
            color="white",
            weight="bold",
            fontsize=10,
        )
    ax.legend(frameon=True)
    plt.tight_layout()
    fig2_path = figures_dir / "fig_1_2_usable_vs_unusable_breakdown.png"
    fig.savefig(fig2_path)
    plt.close(fig)

    return {
        "overall_retention_rate_pct": round(usable_all / total_all * 100, 2),
        "total_reviews": total_all,
        "usable_reviews": usable_all,
        "unusable_reviews": total_all - usable_all,
    }


# -----------------------------------------------------------------------------
# TASK 1.2: Text Length Distribution
# -----------------------------------------------------------------------------
def analyze_text_lengths(
    df_usable: pd.DataFrame, tables_dir: Path, figures_dir: Path
) -> Dict[str, Any]:
    """Analyze character and word lengths of normalized review text."""
    logger.info("Task 1.2: Analyzing text lengths...")

    df_len = df_usable.copy()
    df_len["char_count"] = df_len["review_text_normalized"].astype(str).str.len()
    df_len["word_count"] = df_len["review_text_normalized"].astype(str).str.split().apply(len)

    percentiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    char_desc = df_len["char_count"].describe(percentiles=percentiles)
    word_desc = df_len["word_count"].describe(percentiles=percentiles)

    df_summary = pd.DataFrame({
        "Metric": [
            "Count",
            "Mean",
            "Std",
            "Min (P0)",
            "P1",
            "P5",
            "P10",
            "P25 (Q1)",
            "P50 (Median)",
            "P75 (Q3)",
            "P90",
            "P95",
            "P99",
            "Max (P100)",
        ],
        "Character_Count": [
            int(char_desc["count"]),
            round(char_desc["mean"], 2),
            round(char_desc["std"], 2),
            int(char_desc["min"]),
            int(char_desc["1%"]),
            int(char_desc["5%"]),
            int(char_desc["10%"]),
            int(char_desc["25%"]),
            int(char_desc["50%"]),
            int(char_desc["75%"]),
            int(char_desc["90%"]),
            int(char_desc["95%"]),
            int(char_desc["99%"]),
            int(char_desc["max"]),
        ],
        "Word_Count": [
            int(word_desc["count"]),
            round(word_desc["mean"], 2),
            round(word_desc["std"], 2),
            int(word_desc["min"]),
            int(word_desc["1%"]),
            int(word_desc["5%"]),
            int(word_desc["10%"]),
            int(word_desc["25%"]),
            int(word_desc["50%"]),
            int(word_desc["75%"]),
            int(word_desc["90%"]),
            int(word_desc["95%"]),
            int(word_desc["99%"]),
            int(word_desc["max"]),
        ],
    })
    save_table(df_summary, "table_1_3_text_length_percentiles", tables_dir)

    # Figure 1.3: Text length distribution histogram + boxplot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Characters (log scale histogram)
    sns.histplot(
        df_len["char_count"],
        bins=50,
        kde=True,
        color="#2b5c8f",
        log_scale=True,
        ax=ax1,
    )
    median_chars = int(char_desc["50%"])
    ax1.axvline(median_chars, color="red", linestyle="--", label=f"Trung vị: {median_chars} ký tự")
    ax1.set_title("Phân bố Số Ký tự (Log Scale)", fontsize=12, weight="bold")
    ax1.set_xlabel("Số ký tự (thang log)", fontsize=10)
    ax1.set_ylabel("Tần suất", fontsize=10)
    ax1.legend()

    # Words (up to 99th percentile for clean visualization)
    p99_words = int(word_desc["99%"])
    sns.histplot(
        df_len[df_len["word_count"] <= p99_words]["word_count"],
        bins=35,
        kde=True,
        color="#1b9e77",
        ax=ax2,
    )
    median_words = int(word_desc["50%"])
    ax2.axvline(median_words, color="red", linestyle="--", label=f"Trung vị: {median_words} từ")
    ax2.set_title(f"Phân bố Số Từ (Đến P99 = {p99_words} từ)", fontsize=12, weight="bold")
    ax2.set_xlabel("Số từ", fontsize=10)
    ax2.set_ylabel("Tần suất", fontsize=10)
    ax2.legend()

    plt.tight_layout()
    fig3_path = figures_dir / "fig_1_3_text_length_distribution.png"
    fig.savefig(fig3_path)
    plt.close(fig)

    return {
        "char_median": median_chars,
        "char_mean": round(char_desc["mean"], 2),
        "word_median": median_words,
        "word_mean": round(word_desc["mean"], 2),
        "max_words": int(word_desc["max"]),
    }


# -----------------------------------------------------------------------------
# TASK 1.3: Duplicate Review Analysis
# -----------------------------------------------------------------------------
def analyze_duplicates(df_usable: pd.DataFrame, tables_dir: Path) -> Dict[str, Any]:
    """Analyze exact duplicate texts and high-frequency short comments."""
    logger.info("Task 1.3: Analyzing duplicate review texts...")

    text_counts = df_usable["review_text_normalized"].value_counts()
    total_usable = len(df_usable)
    unique_texts = len(text_counts)

    top_dup_rows = []
    for rank, (txt, count) in enumerate(text_counts.head(15).items(), 1):
        sample_ratings = df_usable[df_usable["review_text_normalized"] == txt]["rating_raw"].value_counts().to_dict()
        top_dup_rows.append({
            "rank": rank,
            "text": txt,
            "frequency": count,
            "pct_of_usable": round(count / total_usable * 100, 2),
            "char_length": len(txt),
            "word_count": len(txt.split()),
            "ratings_breakdown": str(sample_ratings),
        })

    df_top_dup = pd.DataFrame(top_dup_rows)
    save_table(df_top_dup, "table_1_4_top_duplicate_texts", tables_dir)

    return {
        "unique_texts": unique_texts,
        "unique_ratio_pct": round(unique_texts / total_usable * 100, 2),
        "top_frequent_text": top_dup_rows[0]["text"],
        "top_frequent_count": top_dup_rows[0]["frequency"],
    }


# -----------------------------------------------------------------------------
# TASK 1.4: Rating-Text Mismatch Audit
# -----------------------------------------------------------------------------
def analyze_rating_text_mismatch(df_usable: pd.DataFrame, tables_dir: Path) -> Dict[str, Any]:
    """Audit disconnects between declared rating and textual sentiment."""
    logger.info("Task 1.4: Auditing rating-text mismatches...")

    strong_negative_tokens = [
        "quá tệ",
        "rất tệ",
        "thất vọng",
        "rất kém",
        "máy lỗi",
        "hỏng",
        "lừa đảo",
        "tiền mất tật mang",
        "chậm đơ",
        "liên tục sập",
        "không hài lòng",
    ]
    strong_positive_tokens = [
        "rất tốt",
        "tuyệt vời",
        "rất mượt",
        "ưng ý",
        "quá tốt",
        "hoàn hảo",
        "rất hài lòng",
        "xuất sắc",
    ]

    neg_pattern = re.compile("|".join(re.escape(tok) for tok in strong_negative_tokens), re.IGNORECASE)
    pos_pattern = re.compile("|".join(re.escape(tok) for tok in strong_positive_tokens), re.IGNORECASE)

    # Type A: High Rating (4–5 stars) but negative text keywords
    high_rating_neg = df_usable[
        (df_usable["rating_raw"] >= 4) & (df_usable["review_text_normalized"].str.contains(neg_pattern, na=False))
    ]

    # Type B: Low Rating (1–2 stars) but positive text keywords
    low_rating_pos = df_usable[
        (df_usable["rating_raw"] <= 2) & (df_usable["review_text_normalized"].str.contains(pos_pattern, na=False))
    ]

    sample_rows = []
    # Sample 5 of High Rating Neg
    for _, row in high_rating_neg.head(5).iterrows():
        sample_rows.append({
            "mismatch_type": "High Rating (4-5★) with Negative Content",
            "review_record_id": row["review_record_id"][:12] + "...",
            "source": row["source"],
            "rating_raw": row["rating_raw"],
            "product_name": str(row["product_name"])[:35] + "...",
            "text_excerpt": (row["review_text_normalized"][:80] + "...").replace("\n", " "),
        })

    # Sample 5 of Low Rating Pos
    for _, row in low_rating_pos.head(5).iterrows():
        sample_rows.append({
            "mismatch_type": "Low Rating (1-2★) with Positive Phrase (Contextual)",
            "review_record_id": row["review_record_id"][:12] + "...",
            "source": row["source"],
            "rating_raw": row["rating_raw"],
            "product_name": str(row["product_name"])[:35] + "...",
            "text_excerpt": (row["review_text_normalized"][:80] + "...").replace("\n", " "),
        })

    df_mismatch = pd.DataFrame(sample_rows)
    save_table(df_mismatch, "table_1_5_rating_text_mismatch_audit", tables_dir)

    return {
        "high_rating_negative_count": len(high_rating_neg),
        "low_rating_positive_count": len(low_rating_pos),
        "total_mismatch_detected": len(high_rating_neg) + len(low_rating_pos),
    }


# -----------------------------------------------------------------------------
# TASK 1.5: Temporal Review Trends
# -----------------------------------------------------------------------------
def analyze_temporal_trends(
    df_usable: pd.DataFrame, tables_dir: Path, figures_dir: Path
) -> Dict[str, Any]:
    """Analyze review volume over time (2019–2026)."""
    logger.info("Task 1.5: Analyzing temporal trends...")

    df_time = df_usable.copy()
    dt_series = pd.to_datetime(df_time["review_time_raw"], format="mixed", utc=True)
    df_time["year_month"] = dt_series.dt.to_period("M")
    df_time["year"] = dt_series.dt.year

    # Monthly aggregation
    monthly_counts = df_time.groupby(["year_month", "source"]).size().unstack(fill_value=0)
    monthly_total = monthly_counts.sum(axis=1)

    # Yearly aggregation for table
    yearly_df = df_time.groupby(["year", "source"]).size().unstack(fill_value=0).reset_index()
    yearly_df["Total"] = yearly_df.drop(columns=["year"]).sum(axis=1)
    save_table(yearly_df, "table_1_7_temporal_distribution", tables_dir)

    # Figure 1.4: Monthly time series
    fig, ax = plt.subplots(figsize=(11, 5), dpi=300)
    monthly_counts_plot = monthly_counts.loc["2020-01":"2026-10"]  # Filter stable period
    monthly_counts_plot.plot(ax=ax, linewidth=1.8, colormap="tab10")

    ax.set_title("Xu hướng Đánh giá Sản phẩm theo Thời gian (Hàng tháng, 2020–2026)", fontsize=13, weight="bold")
    ax.set_xlabel("Thời gian (Năm - Tháng)", fontsize=11)
    ax.set_ylabel("Số lượng Review Hợp lệ", fontsize=11)
    ax.legend(title="Sàn TMĐT", frameon=True)
    plt.tight_layout()
    fig4_path = figures_dir / "fig_1_4_temporal_trend_reviews.png"
    fig.savefig(fig4_path)
    plt.close(fig)

    return {
        "min_timestamp": str(dt_series.min()),
        "max_timestamp": str(dt_series.max()),
        "peak_year": int(yearly_df.sort_values(by="Total", ascending=False).iloc[0]["year"]),
        "peak_year_count": int(yearly_df["Total"].max()),
    }


# -----------------------------------------------------------------------------
# TASK 1.6: Product Coverage & Cold Start Audit (FOR TV5 HANDOFF)
# -----------------------------------------------------------------------------
def analyze_product_coverage(
    df_parents: pd.DataFrame, df_usable: pd.DataFrame, tables_dir: Path, figures_dir: Path
) -> Dict[str, Any]:
    """Audit review coverage over all parent products for TV5 feature design."""
    logger.info("Task 1.6: Auditing product coverage for TV5 handoff...")

    total_parents = len(df_parents)
    usable_counts = df_usable["source_parent_id"].value_counts().to_dict()

    df_cov = df_parents.copy()
    df_cov["usable_review_count"] = df_cov["source_parent_id"].map(usable_counts).fillna(0).astype(int)
    df_cov["has_usable_reviews"] = df_cov["usable_review_count"] > 0

    # Summary by source
    rows = []
    for src, grp in df_cov.groupby("source"):
        p_total = len(grp)
        p_covered = grp["has_usable_reviews"].sum()
        p_zero = p_total - p_covered
        rev_counts = grp["usable_review_count"]
        rows.append({
            "source": src,
            "total_parents": p_total,
            "parents_with_reviews": int(p_covered),
            "parents_zero_reviews": int(p_zero),
            "coverage_rate_pct": round(p_covered / p_total * 100, 2),
            "cold_start_rate_pct": round(p_zero / p_total * 100, 2),
            "total_reviews": int(rev_counts.sum()),
            "avg_reviews_per_parent": round(rev_counts.mean(), 2),
            "max_reviews_per_parent": int(rev_counts.max()),
        })

    # Overall summary row
    p_covered_all = df_cov["has_usable_reviews"].sum()
    p_zero_all = total_parents - p_covered_all
    rev_all = df_cov["usable_review_count"]
    rows.append({
        "source": "Total / Overall",
        "total_parents": total_parents,
        "parents_with_reviews": int(p_covered_all),
        "parents_zero_reviews": int(p_zero_all),
        "coverage_rate_pct": round(p_covered_all / total_parents * 100, 2),
        "cold_start_rate_pct": round(p_zero_all / total_parents * 100, 2),
        "total_reviews": int(rev_all.sum()),
        "avg_reviews_per_parent": round(rev_all.mean(), 2),
        "max_reviews_per_parent": int(rev_all.max()),
    })

    df_table_cov = pd.DataFrame(rows)
    save_table(df_table_cov, "table_1_6_product_coverage_audit", tables_dir)

    # Figure 1.5: Product review distribution (Cold Start Pie + Non-zero review distribution)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300)

    # Pie chart: Coverage vs Cold Start
    labels = [f"Có Review\n({p_covered_all:,})", f"Không có Review (Cold-Start)\n({p_zero_all:,})"]
    ax1.pie(
        [p_covered_all, p_zero_all],
        labels=labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=["#2b5c8f", "#d95f02"],
        explode=(0.06, 0),
        textprops={"fontsize": 11, "weight": "bold"},
    )
    ax1.set_title("Mức độ Bao phủ Review trên 7.051 Sản phẩm Cha", fontsize=12, weight="bold")

    # Histogram of review counts among covered products (capped at 99th percentile)
    covered_revs = rev_all[rev_all > 0]
    p95_revs = int(np.percentile(covered_revs, 95))
    sns.histplot(covered_revs[covered_revs <= p95_revs], bins=25, kde=True, color="#7570b3", ax=ax2)
    ax2.axvline(covered_revs.median(), color="red", linestyle="--", label=f"Trung vị: {int(covered_revs.median())} reviews")
    ax2.set_title(f"Phân bố Số Review trên Sản phẩm có Đánh giá (Đến P95 = {p95_revs})", fontsize=12, weight="bold")
    ax2.set_xlabel("Số lượng review / sản phẩm", fontsize=10)
    ax2.set_ylabel("Số lượng sản phẩm", fontsize=10)
    ax2.legend()

    plt.tight_layout()
    fig5_path = figures_dir / "fig_1_5_product_review_coverage.png"
    fig.savefig(fig5_path)
    plt.close(fig)

    return {
        "total_parent_products": total_parents,
        "parents_with_reviews": int(p_covered_all),
        "parents_zero_reviews": int(p_zero_all),
        "coverage_rate_pct": round(p_covered_all / total_parents * 100, 2),
        "cold_start_rate_pct": round(p_zero_all / total_parents * 100, 2),
        "avg_reviews_among_covered": round(covered_revs.mean(), 2),
        "median_reviews_among_covered": int(covered_revs.median()),
        "max_reviews_on_single_product": int(rev_all.max()),
    }


# -----------------------------------------------------------------------------
# MAIN STEP 1 RUNNER
# -----------------------------------------------------------------------------
def run_step1_quality_eda(
    tables_dir: Path = TABLES_TV6_DIR,
    figures_dir: Path = FIGURES_TV6_DIR,
) -> Dict[str, Any]:
    """Execute Step 1 end-to-end and generate quality report."""
    logger.info("=== STARTING STEP 1: TV6 REVIEW QUALITY PROFILING & EDA ===")
    start_time = datetime.now()

    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    DOCS_TV6_DIR.mkdir(parents=True, exist_ok=True)

    df_all, df_usable, df_parents = load_dataset()

    res_ratings = analyze_ratings_and_usability(df_all, df_usable, tables_dir, figures_dir)
    res_lengths = analyze_text_lengths(df_usable, tables_dir, figures_dir)
    res_duplicates = analyze_duplicates(df_usable, tables_dir)
    res_mismatches = analyze_rating_text_mismatch(df_usable, tables_dir)
    res_temporal = analyze_temporal_trends(df_usable, tables_dir, figures_dir)
    res_coverage = analyze_product_coverage(df_parents, df_usable, tables_dir, figures_dir)

    quality_report = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step": "step1_quality_eda",
        "metrics": {
            "ratings_and_usability": res_ratings,
            "text_lengths": res_lengths,
            "duplicate_texts": res_duplicates,
            "rating_text_mismatches": res_mismatches,
            "temporal_trends": res_temporal,
            "tv5_product_coverage": res_coverage,
        },
        "artifacts_generated": {
            "tables": [str(p.name) for p in tables_dir.glob("*.csv")],
            "figures": [str(p.name) for p in figures_dir.glob("*.png")],
        },
    }

    report_json_str = json.dumps(quality_report, ensure_ascii=False, indent=2)
    QUALITY_REPORT_FILE.write_text(report_json_str, encoding="utf-8")
    DOCS_QUALITY_REPORT_FILE.write_text(report_json_str, encoding="utf-8")
    logger.info("Saved quality report to %s and %s", QUALITY_REPORT_FILE, DOCS_QUALITY_REPORT_FILE)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info("=== STEP 1 COMPLETED IN %.2f SECONDS ===", duration)

    return quality_report


if __name__ == "__main__":
    run_step1_quality_eda()
