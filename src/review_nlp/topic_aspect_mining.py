"""Step 4: Topic Modeling (LDA & NMF), Aspect-Based Sentiment Mining (ABSA), and Keyword Visualization.

Implements deep semantic and keyword extraction for e-commerce reviews:
1. Topic Modeling with Latent Dirichlet Allocation (LDA) & Non-negative Matrix Factorization (NMF).
2. Domain-specific Aspect-Based Sentiment Analysis (ABSA) across 5 tech dimensions:
   - Battery & Power (pin & sạc)
   - Performance & Thermal (hiệu năng & nhiệt độ)
   - Display & Design (màn hình & thiết kế)
   - Camera & Audio (camera & âm thanh)
   - Customer Service & Logistics (dịch vụ & giao vận)
3. WordCloud generation for Positive vs Negative corpora.
4. Exporting enriched dataset with topic and aspect features for downstream consumption.
"""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import LatentDirichletAllocation, NMF
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from wordcloud import WordCloud

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DOCS_STEP4_REPORT_FILE,
    DOCS_TOPIC_ASPECT_REPORT_FILE,
    DOCS_TV6_DIR,
    FIGURES_TV6_DIR,
    REVIEWS_TV6_ASPECTS_FILE,
    REVIEWS_TV6_PREPROCESSED_FILE,
    REVIEWS_TV6_SENTIMENT_BASELINE_FILE,
    REVIEWS_TV6_SENTIMENT_PHOBERT_FILE,
    TABLES_TV6_DIR,
    TOPIC_ASPECT_REPORT_FILE,
    TV6_PIPELINE_VERSION,
)

# -----------------------------------------------------------------------------
# Domain Aspect Lexicons for Tech E-Commerce
# -----------------------------------------------------------------------------
ASPECT_LEXICON: Dict[str, Dict[str, Any]] = {
    "battery_power": {
        "display_name": "Pin & Sạc (Battery & Power)",
        "keywords": [
            "pin", "pin_trâu", "pin_hẻo", "sạc", "sạc_nhanh", "hao_pin",
            "sập_nguồn", "chai_pin", "củ_sạc", "dây_sạc", "dung_lượng",
            "dung_lượng_pin", "thời_lượng_pin", "sạc_đầy", "tuột_pin",
            "tụt_pin", "hết_pin", "pin_yếu", "pin_khỏe"
        ],
    },
    "performance_thermal": {
        "display_name": "Hiệu năng & Tản nhiệt (Performance & Thermal)",
        "keywords": [
            "mượt", "mượt_mà", "lag", "giật", "giật_lag", "đơ", "nóng_máy",
            "nóng", "tản_nhiệt", "chip", "cpu", "ram", "cấu_hình", "chơi_game",
            "game", "fps", "đồ_họa", "sập_nguồn", "chậm", "load", "tác_vụ",
            "đa_nhiệm", "máy_nóng", "khỏe", "mạnh", "yếu"
        ],
    },
    "display_design": {
        "display_name": "Màn hình & Thiết kế (Display & Design)",
        "keywords": [
            "màn_hình", "màn", "thiết_kế", "màu_sắc", "sắc_nét", "amoled",
            "oled", "ips", "tần_số_quét", "120hz", "sáng", "độ_sáng", "góc_nhìn",
            "viền", "mỏng", "nhẹ", "gọn", "sang_trọng", "đẹp", "ngoại_hình",
            "cầm_nắm", "bàn_phím", "touchpad", "vỏ", "kim_loại"
        ],
    },
    "camera_audio": {
        "display_name": "Camera & Âm thanh (Camera & Audio)",
        "keywords": [
            "camera", "chụp_ảnh", "chụp_hình", "quay_phim", "nét", "sống_động",
            "chụp_đêm", "camera_sau", "camera_trước", "loa", "loa_rè", "loa_nhỏ",
            "loa_to", "âm_thanh", "mic", "đàm_thoại", "tai_nghe", "bass", "nghe_nhạc"
        ],
    },
    "service_logistics": {
        "display_name": "Dịch vụ & Giao vận (Service & Logistics)",
        "keywords": [
            "giao_hàng", "đóng_gói", "nhân_viên", "shop", "tư_vấn", "nhiệt_tình",
            "thái_độ", "bảo_hành", "đổi_trả", "giao_hàng_nhanh", "shipper",
            "phục_vụ", "hỗ_trợ", "gọi_điện", "chăm_sóc", "uy_tín", "chính_hãng"
        ],
    },
}

LOCAL_POSITIVE_WORDS = {
    "tốt", "đẹp", "mượt", "trâu", "nhanh", "ưng", "ngon", "thích", "chuẩn",
    "ổn", "hài_lòng", "tuyệt", "tuyệt_vời", "khỏe", "bền", "sắc_nét", "sang",
    "đỉnh", "xuất_sắc", "yên_tâm", "rất_tốt", "quá_đẹp", "rất_mượt", "nhiệt_tình",
}

LOCAL_NEGATIVE_WORDS = {
    "tệ", "kém", "chậm", "lag", "yếu", "hẻo", "rè", "nóng", "chán", "thất_vọng",
    "lỗi", "chai", "hỏng", "sập_nguồn", "đơ", "giật", "rất_tệ", "quá_tệ",
    "nhỏ", "mờ", "xấu", "thua", "chán_đời", "chập_chờn",
}

NEGATION_TOKENS = {"không", "chẳng", "chưa", "không_bị", "không_hề", "ko"}


# -----------------------------------------------------------------------------
# Data Ingestion
# -----------------------------------------------------------------------------
def load_corpus_for_aspect_mining() -> pd.DataFrame:
    """Load reviews prioritizing PhoBERT scored output, falling back to Baseline or Preprocessed."""
    candidates = [
        REVIEWS_TV6_SENTIMENT_PHOBERT_FILE,
        REVIEWS_TV6_SENTIMENT_BASELINE_FILE,
        REVIEWS_TV6_PREPROCESSED_FILE,
    ]
    filepath = None
    for cand in candidates:
        if cand.exists():
            filepath = cand
            break

    if filepath is None:
        raise FileNotFoundError("No input review file found in data/tv6/. Run previous steps first.")

    records = []
    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    df = pd.DataFrame(records)
    print(f"[INPUT LOADED] Đã đọc {len(df):,} bản ghi từ: {filepath.name}")

    # Ensure required text fields
    if "text_clean" not in df.columns:
        df["text_clean"] = df["text_stopwords_removed"].replace("", np.nan).fillna(df["text_tokenized"])
        df["text_clean"] = df["text_clean"].fillna(df["review_text_normalized"])

    # Ensure sentiment fields exist
    if "sentiment_pred" not in df.columns:
        label_map = {1: "NEGATIVE", 2: "NEGATIVE", 3: "NEUTRAL", 4: "POSITIVE", 5: "POSITIVE"}
        df["sentiment_pred"] = df["rating_raw"].map(label_map).fillna("POSITIVE")
    if "sentiment_score" not in df.columns:
        score_map = {"POSITIVE": 0.8, "NEUTRAL": 0.0, "NEGATIVE": -0.8}
        df["sentiment_score"] = df["sentiment_pred"].map(score_map).fillna(0.0)

    return df


# -----------------------------------------------------------------------------
# Task 4.1: Topic Modeling (LDA & NMF)
# -----------------------------------------------------------------------------
def run_topic_modeling(
    df: pd.DataFrame,
    n_topics: int = 5,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    """Train Latent Dirichlet Allocation (LDA) and NMF on preprocessed review texts."""
    texts = df["text_clean"].tolist()

    print(f"\n1. Huấn luyện Mô hình Chủ đề (LDA & NMF, K={n_topics} Topics)...")

    # 1. CountVectorizer for LDA
    count_vec = CountVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=5,
        max_df=0.85,
    )
    X_counts = count_vec.fit_transform(texts)
    count_feature_names = np.array(count_vec.get_feature_names_out())

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=random_state,
        max_iter=15,
        learning_method="online",
        n_jobs=-1,
    )
    lda_doc_topics = lda.fit_transform(X_counts)

    # 2. TfidfVectorizer for NMF
    tfidf_vec = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        min_df=5,
        max_df=0.85,
        sublinear_tf=True,
    )
    X_tfidf = tfidf_vec.fit_transform(texts)
    tfidf_feature_names = np.array(tfidf_vec.get_feature_names_out())

    nmf = NMF(
        n_components=n_topics,
        random_state=random_state,
        max_iter=150,
        init="nndsvd",
    )
    nmf_doc_topics = nmf.fit_transform(X_tfidf)

    # 3. Label interpretability dictionary for LDA
    topic_labels = {
        0: "Hiệu năng & Tốc độ máy",
        1: "Màn hình & Camera",
        2: "Thời lượng pin & Phụ kiện sạc",
        3: "Dịch vụ shop & Giao hàng",
        4: "Trải nghiệm sử dụng & Sự cố",
    }

    # Extract Top 10 Keywords per Topic
    lda_records = []
    dominant_lda_topics = np.argmax(lda_doc_topics, axis=1)
    topic_counts = Counter(dominant_lda_topics)

    for i, topic_dist in enumerate(lda.components_):
        top_idx = topic_dist.argsort()[:-11:-1]
        top_words = count_feature_names[top_idx].tolist()
        share_pct = round(100.0 * topic_counts[i] / len(df), 2)
        lda_records.append({
            "topic_id": i,
            "topic_name": topic_labels.get(i, f"Chủ đề {i}"),
            "top_keywords": ", ".join(top_words),
            "dominant_doc_count": int(topic_counts[i]),
            "corpus_share_pct": share_pct,
        })

    lda_df = pd.DataFrame(lda_records)

    # Extract NMF Topics
    nmf_records = []
    dominant_nmf_topics = np.argmax(nmf_doc_topics, axis=1)
    nmf_counts = Counter(dominant_nmf_topics)

    for i, topic_dist in enumerate(nmf.components_):
        top_idx = topic_dist.argsort()[:-11:-1]
        top_words = tfidf_feature_names[top_idx].tolist()
        share_pct = round(100.0 * nmf_counts[i] / len(df), 2)
        nmf_records.append({
            "topic_id": i,
            "top_keywords": ", ".join(top_words),
            "dominant_doc_count": int(nmf_counts[i]),
            "corpus_share_pct": share_pct,
        })

    nmf_df = pd.DataFrame(nmf_records)

    print(f"   LDA Perplexity: {lda.perplexity(X_counts):.2f}")
    print(f"   NMF Reconstruction Error: {nmf.reconstruction_err_:.2f}")

    return lda_df, nmf_df, dominant_lda_topics, lda_doc_topics


# -----------------------------------------------------------------------------
# Task 4.2: Aspect-Based Sentiment Analysis (ABSA)
# -----------------------------------------------------------------------------
def analyze_aspect_sentiments(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Extract fine-grained aspect mentions and aspect-level sentiments per review."""
    print("\n2. Thực hiện Phân tích Cảm xúc theo Khía cạnh (Aspect-Based Sentiment Analysis)...")

    aspect_mentions_list: List[List[str]] = []
    aspect_sentiments_list: List[Dict[str, str]] = []

    # Aspect statistics trackers
    stats: Dict[str, Dict[str, int]] = {
        asp: {"total": 0, "POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
        for asp in ASPECT_LEXICON
    }

    category_stats: Dict[str, Dict[str, int]] = {
        "smartphone": {asp: 0 for asp in ASPECT_LEXICON},
        "laptop": {asp: 0 for asp in ASPECT_LEXICON},
    }

    for idx, row in df.iterrows():
        text_tokenized = str(row.get("text_tokenized", "")).lower()
        tokens = text_tokenized.split()
        overall_sentiment = str(row.get("sentiment_pred", "POSITIVE"))
        cat = str(row.get("category", "smartphone")).lower()

        row_mentions = []
        row_sentiments = {}

        for asp_key, asp_info in ASPECT_LEXICON.items():
            keywords = asp_info["keywords"]
            found_kw_indices = []

            for i, tok in enumerate(tokens):
                if any(kw in tok for kw in keywords):
                    found_kw_indices.append(i)

            if found_kw_indices:
                row_mentions.append(asp_key)
                stats[asp_key]["total"] += 1
                if cat in category_stats:
                    category_stats[cat][asp_key] += 1

                # Local window context search for polarity cues (window +- 4 words)
                pos_cues = 0
                neg_cues = 0

                for kw_idx in found_kw_indices:
                    start_w = max(0, kw_idx - 4)
                    end_w = min(len(tokens), kw_idx + 5)
                    window_tokens = tokens[start_w:end_w]

                    for w_i, w in enumerate(window_tokens):
                        # Negation check
                        is_negated = False
                        if w_i > 0 and window_tokens[w_i - 1] in NEGATION_TOKENS:
                            is_negated = True

                        if w in LOCAL_POSITIVE_WORDS:
                            if is_negated:
                                neg_cues += 1
                            else:
                                pos_cues += 1
                        elif w in LOCAL_NEGATIVE_WORDS:
                            if is_negated:
                                pos_cues += 1  # e.g., "không bị lag" -> positive
                            else:
                                neg_cues += 1

                # Determine aspect sentiment
                if pos_cues > neg_cues:
                    asp_sent = "POSITIVE"
                elif neg_cues > pos_cues:
                    asp_sent = "NEGATIVE"
                else:
                    # Fallback to document-level sentiment
                    asp_sent = overall_sentiment

                row_sentiments[asp_key] = asp_sent
                stats[asp_key][asp_sent] += 1

        aspect_mentions_list.append(row_mentions)
        aspect_sentiments_list.append(row_sentiments)

    df["aspect_mentions"] = aspect_mentions_list
    df["aspect_sentiments"] = aspect_sentiments_list
    df["aspect_count"] = [len(m) for m in aspect_mentions_list]

    # Build summary aspect distribution table
    summary_records = []
    total_reviews = len(df)

    for asp_key, counts in stats.items():
        total_m = counts["total"]
        pct_mention = round(100.0 * total_m / total_reviews, 2)
        pos_pct = round(100.0 * counts["POSITIVE"] / max(total_m, 1), 2)
        neu_pct = round(100.0 * counts["NEUTRAL"] / max(total_m, 1), 2)
        neg_pct = round(100.0 * counts["NEGATIVE"] / max(total_m, 1), 2)

        summary_records.append({
            "aspect_key": asp_key,
            "aspect_name": ASPECT_LEXICON[asp_key]["display_name"],
            "total_mentions": total_m,
            "mention_rate_pct": pct_mention,
            "positive_pct": pos_pct,
            "neutral_pct": neu_pct,
            "negative_pct": neg_pct,
        })

    aspect_summary_df = pd.DataFrame(summary_records)

    # Category comparison summary
    cat_records = []
    smart_total = sum(df["category"] == "smartphone")
    lap_total = sum(df["category"] == "laptop")

    for asp_key in ASPECT_LEXICON:
        s_count = category_stats.get("smartphone", {}).get(asp_key, 0)
        l_count = category_stats.get("laptop", {}).get(asp_key, 0)
        cat_records.append({
            "aspect_key": asp_key,
            "aspect_name": ASPECT_LEXICON[asp_key]["display_name"],
            "smartphone_count": s_count,
            "smartphone_rate_pct": round(100.0 * s_count / max(smart_total, 1), 2),
            "laptop_count": l_count,
            "laptop_rate_pct": round(100.0 * l_count / max(lap_total, 1), 2),
        })

    cat_comparison_df = pd.DataFrame(cat_records)

    meta = {
        "aspect_stats": stats,
        "category_stats": category_stats,
        "aspect_summary_df": aspect_summary_df,
        "category_comparison_df": cat_comparison_df,
    }

    return df, meta


# -----------------------------------------------------------------------------
# Task 4.3: Word Cloud & High-Resolution Visualization
# -----------------------------------------------------------------------------
def generate_step4_figures_and_tables(
    df: pd.DataFrame,
    lda_df: pd.DataFrame,
    nmf_df: pd.DataFrame,
    meta: Dict[str, Any],
) -> None:
    """Generate high-resolution (300 DPI) figures and markdown/CSV tables."""
    FIGURES_TV6_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_TV6_DIR.mkdir(parents=True, exist_ok=True)

    print("\n3. Sinh Biểu đồ Trực quan hóa (300 DPI) và Bảng Thống kê Markdown/CSV...")

    # Set visualization theme
    sns.set_theme(style="whitegrid", font="sans-serif")
    palette = sns.color_palette("muted")

    # 1. Figure 4.1: WordClouds by Sentiment Class (Positive vs Negative)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), dpi=300)

    pos_texts = " ".join(df[df["sentiment_pred"] == "POSITIVE"]["text_clean"].dropna().tolist())
    neg_texts = " ".join(df[df["sentiment_pred"] == "NEGATIVE"]["text_clean"].dropna().tolist())

    wc_pos = WordCloud(
        width=800,
        height=500,
        background_color="white",
        colormap="Greens",
        max_words=100,
        random_state=42,
    ).generate(pos_texts if pos_texts.strip() else "tốt đẹp mượt hài_lòng")

    wc_neg = WordCloud(
        width=800,
        height=500,
        background_color="white",
        colormap="Reds",
        max_words=100,
        random_state=42,
    ).generate(neg_texts if neg_texts.strip() else "tệ lỗi chậm lag sập_nguồn")

    axes[0].imshow(wc_pos, interpolation="bilinear")
    axes[0].set_title("WordCloud: Đánh Giá Tích Cực (Positive Reviews, 4–5 sao)", fontsize=13, weight="bold", pad=12)
    axes[0].axis("off")

    axes[1].imshow(wc_neg, interpolation="bilinear")
    axes[1].set_title("WordCloud: Đánh Giá Tiêu Cực (Negative Reviews, 1–2 sao)", fontsize=13, weight="bold", pad=12)
    axes[1].axis("off")

    plt.tight_layout()
    fig_4_1_path = FIGURES_TV6_DIR / "fig_4_1_wordclouds_by_sentiment.png"
    fig.savefig(fig_4_1_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"   Đã lưu: {fig_4_1_path.name}")

    # 2. Figure 4.2: LDA Topic Distribution
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    sns.barplot(
        data=lda_df,
        x="corpus_share_pct",
        y="topic_name",
        palette="crest",
        ax=ax,
    )
    for p in ax.patches:
        val = p.get_width()
        ax.annotate(f"{val:.1f}%", (val + 0.5, p.get_y() + p.get_height() / 2),
                    va="center", fontsize=10, weight="bold")
    ax.set_title("Phân Bố Tỷ Trọng 5 Chủ Đề Thảo Luận Tiềm Ẩn (LDA Topic Modeling)", fontsize=13, weight="bold", pad=14)
    ax.set_xlabel("Tỷ lệ % trong toàn bộ kho ngữ liệu", fontsize=11)
    ax.set_ylabel("Chủ đề thảo luận (Topic)", fontsize=11)
    ax.set_xlim(0, max(lda_df["corpus_share_pct"]) + 5)
    plt.tight_layout()
    fig_4_2_path = FIGURES_TV6_DIR / "fig_4_2_topic_distribution.png"
    fig.savefig(fig_4_2_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"   Đã lưu: {fig_4_2_path.name}")

    # 3. Figure 4.3: Aspect Sentiment Breakdown (Stacked Bar)
    aspect_df = meta["aspect_summary_df"]
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)

    y_pos = np.arange(len(aspect_df))
    p1 = ax.barh(y_pos, aspect_df["positive_pct"], color="#2ca02c", label="Tích cực (Positive)", alpha=0.85)
    p2 = ax.barh(y_pos, aspect_df["neutral_pct"], left=aspect_df["positive_pct"], color="#ffbb78", label="Trung tính (Neutral)", alpha=0.85)
    p3 = ax.barh(y_pos, aspect_df["negative_pct"], left=aspect_df["positive_pct"] + aspect_df["neutral_pct"], color="#d62728", label="Tiêu cực (Negative)", alpha=0.85)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(aspect_df["aspect_name"], fontsize=10.5)
    ax.set_xlabel("Tỷ lệ cảm xúc (%)", fontsize=11)
    ax.set_title("Phân Bố Sắc Thái Cảm Xúc Theo Từng Khía Cạnh Sản Phẩm (ABSA Breakdown)", fontsize=13, weight="bold", pad=14)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=True)
    ax.set_xlim(0, 100)

    for i in range(len(aspect_df)):
        pos_val = aspect_df.loc[i, "positive_pct"]
        neg_val = aspect_df.loc[i, "negative_pct"]
        if pos_val > 15:
            ax.text(pos_val / 2, i, f"{pos_val:.1f}%", va="center", ha="center", color="white", weight="bold", fontsize=9.5)
        if neg_val > 5:
            ax.text(100 - neg_val / 2, i, f"{neg_val:.1f}%", va="center", ha="center", color="white", weight="bold", fontsize=9.5)

    plt.tight_layout()
    fig_4_3_path = FIGURES_TV6_DIR / "fig_4_3_aspect_sentiment_matrix.png"
    fig.savefig(fig_4_3_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"   Đã lưu: {fig_4_3_path.name}")

    # 4. Figure 4.4: Aspect Mentions Comparison between Smartphone & Laptop
    cat_df = meta["category_comparison_df"]
    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=300)

    x = np.arange(len(cat_df))
    width = 0.35
    ax.bar(x - width/2, cat_df["smartphone_rate_pct"], width, label="Smartphone", color="#1f77b4", alpha=0.85)
    ax.bar(x + width/2, cat_df["laptop_rate_pct"], width, label="Laptop", color="#ff7f0e", alpha=0.85)

    ax.set_ylabel("Tỷ lệ review đề cập (%)", fontsize=11)
    ax.set_title("Mức Độ Quan Tâm Khía Cạnh: Smartphone vs Laptop", fontsize=13, weight="bold", pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels([name.split("(")[0].strip() for name in cat_df["aspect_name"]], fontsize=10.5)
    ax.legend(frameon=True)
    plt.tight_layout()
    fig_4_4_path = FIGURES_TV6_DIR / "fig_4_4_aspect_by_category.png"
    fig.savefig(fig_4_4_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"   Đã lưu: {fig_4_4_path.name}")

    # Export Tables (Markdown & CSV)
    tables_to_export = [
        ("table_4_1_lda_topics", lda_df),
        ("table_4_2_nmf_topics", nmf_df),
        ("table_4_3_aspect_sentiment_distribution", aspect_df),
        ("table_4_4_category_aspect_comparison", cat_df),
    ]

    for name, t_df in tables_to_export:
        csv_p = TABLES_TV6_DIR / f"{name}.csv"
        md_p = TABLES_TV6_DIR / f"{name}.md"
        t_df.to_csv(csv_p, index=False, encoding="utf-8")
        md_table = t_df.to_markdown(index=False)
        with md_p.open("w", encoding="utf-8") as f:
            f.write(md_table + "\n")
        print(f"   Đã xuất: {name}.csv & {name}.md")


# -----------------------------------------------------------------------------
# Task 4.4: Enriched Corpus & Metadata Report Export
# -----------------------------------------------------------------------------
def export_enriched_aspect_corpus_and_report(
    df: pd.DataFrame,
    lda_df: pd.DataFrame,
    nmf_df: pd.DataFrame,
    dominant_lda_topics: np.ndarray,
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Export reviews_tv6_aspects.jsonl and topic_aspect_report.json."""
    print("\n4. Xuất Kho Dữ liệu Gán Nhãn Khía cạnh & Báo cáo Metadata JSON...")

    # Assign dominant topic name
    topic_map = dict(zip(lda_df["topic_id"], lda_df["topic_name"]))
    df["dominant_topic_id"] = dominant_lda_topics.tolist()
    df["dominant_topic_name"] = df["dominant_topic_id"].map(topic_map)

    # Write enriched JSONL
    exported_count = 0
    with REVIEWS_TV6_ASPECTS_FILE.open("w", encoding="utf-8") as f:
        for idx, row in df.iterrows():
            record = {
                "review_record_id": row.get("review_record_id"),
                "source_parent_id": row.get("source_parent_id"),
                "product_name": row.get("product_name"),
                "source": row.get("source"),
                "category": row.get("category"),
                "rating_raw": row.get("rating_raw"),
                "review_time_raw": row.get("review_time_raw"),
                "review_usable": row.get("review_usable", True),
                "sentiment_pred": row.get("sentiment_pred"),
                "sentiment_score": float(row.get("sentiment_score", 0.0)),
                "sentiment_confidence": float(row.get("sentiment_confidence", 1.0)),
                "dominant_topic_id": int(row.get("dominant_topic_id")),
                "dominant_topic_name": row.get("dominant_topic_name"),
                "aspect_mentions": row.get("aspect_mentions", []),
                "aspect_sentiments": row.get("aspect_sentiments", {}),
                "aspect_count": int(row.get("aspect_count", 0)),
                "tv6_pipeline_version": TV6_PIPELINE_VERSION,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            exported_count += 1

    print(f"   Đã ghi {exported_count:,} bản ghi vào: {REVIEWS_TV6_ASPECTS_FILE}")

    # Build report dict
    aspect_df = meta["aspect_summary_df"]
    cat_df = meta["category_comparison_df"]

    report = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step": "step4_topic_aspect_mining",
        "total_reviews_analyzed": len(df),
        "lda_topics": lda_df.to_dict(orient="records"),
        "nmf_topics": nmf_df.to_dict(orient="records"),
        "aspect_distribution": aspect_df.to_dict(orient="records"),
        "category_comparison": cat_df.to_dict(orient="records"),
        "aspect_coverage_rate": round(100.0 * float((df["aspect_count"] > 0).mean()), 2),
        "avg_aspects_per_review": round(float(df["aspect_count"].mean()), 2),
    }

    # Save to both data/tv6 and docs/tv6
    for out_path in [TOPIC_ASPECT_REPORT_FILE, DOCS_TOPIC_ASPECT_REPORT_FILE]:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"   Đã lưu báo cáo tại: {out_path}")

    return report


# -----------------------------------------------------------------------------
# Main Orchestrator
# -----------------------------------------------------------------------------
def run_step4_pipeline() -> Dict[str, Any]:
    """Execute complete Step 4 pipeline: Topic Modeling, ABSA, WordCloud, and Reporting."""
    t0 = time.time()
    print("=" * 75)
    print("TV6 BƯỚC 4: TOPIC MODELING (LDA/NMF) & ASPECT-BASED SENTIMENT MINING (ABSA)")
    print("=" * 75)

    # 1. Ingest preprocessed & sentiment-scored data
    df = load_corpus_for_aspect_mining()

    # 2. Topic Modeling (LDA & NMF)
    lda_df, nmf_df, dominant_lda_topics, lda_doc_topics = run_topic_modeling(df)

    # 3. Aspect-Based Sentiment Analysis
    df, meta = analyze_aspect_sentiments(df)

    # 4. Generate Figures and Tables
    generate_step4_figures_and_tables(df, lda_df, nmf_df, meta)

    # 5. Export Enriched Dataset and JSON Report
    report = export_enriched_aspect_corpus_and_report(
        df, lda_df, nmf_df, dominant_lda_topics, meta
    )

    elapsed = round(time.time() - t0, 2)
    report["total_runtime_seconds"] = elapsed
    print("\n" + "=" * 75)
    print(f"[HOÀN THÀNH] Bước 4 hoàn tất trong {elapsed:.1f} giây!")
    print(f"  • Độ phủ khía cạnh (Aspect Coverage): {report['aspect_coverage_rate']}% reviews")
    print(f"  • Trung bình khía cạnh / review: {report['avg_aspects_per_review']}")
    print("=" * 75 + "\n")

    return report


if __name__ == "__main__":
    run_step4_pipeline()
