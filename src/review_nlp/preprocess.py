"""Pipeline Preprocessing Script for TV6 (Review NLP).

Executes Step 2 of the TV6 pipeline:
1. Ingests 14,869 usable reviews from data/tv6/reviews_tv6_usable.jsonl.
2. Applies Vietnamese text normalization, emoji mapping, teencode expansion,
   underthesea compound-word tokenization, and sentiment-preserving stopword filtering.
3. Exports processed records to data/tv6/reviews_tv6_preprocessed.jsonl.
4. Generates audit tables:
   - table_2_1_preprocessing_pipeline_stages.{csv,md}: Stage-by-stage comparison.
   - table_2_2_teencode_dictionary.{csv,md}: Teencode dictionary mapping reference.
   - table_2_3_token_frequency_top50.{csv,md}: Top 50 tokens with corpus counts and document frequency.
5. Generates high-res figure:
   - fig_2_1_top_tokens_frequency.png: Horizontal bar chart of top 30 tokens.
6. Exports comprehensive preprocessing_report.json to data/tv6/ and docs/tv6/.
"""

from collections import Counter
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DOCS_PREPROCESSING_REPORT_FILE,
    DOCS_TV6_DIR,
    FIGURES_TV6_DIR,
    PREPROCESSING_REPORT_FILE,
    REVIEWS_TV6_PREPROCESSED_FILE,
    REVIEWS_TV6_USABLE_FILE,
    TABLES_TV6_DIR,
    TV6_PIPELINE_VERSION,
)
from src.review_nlp.vietnamese_nlp_utils import (
    NEGATIVE_EMOJIS,
    POSITIVE_EMOJIS,
    SAFE_STOPWORDS,
    SENTIMENT_WHITELIST,
    TEENCODE_DICT,
    preprocess_text,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tv6.step2_preprocess")


def save_table(df: pd.DataFrame, base_name: str, tables_dir: Path) -> Tuple[Path, Path]:
    """Save a DataFrame both as CSV and as formatted Markdown."""
    tables_dir.mkdir(parents=True, exist_ok=True)
    csv_path = tables_dir / f"{base_name}.csv"
    md_path = tables_dir / f"{base_name}.md"

    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    with md_path.open("w", encoding="utf-8") as f:
        f.write(df.to_markdown(index=False))

    return csv_path, md_path


def run_text_preprocessing(
    input_file: Path = REVIEWS_TV6_USABLE_FILE,
    output_file: Path = REVIEWS_TV6_PREPROCESSED_FILE,
    tables_dir: Path = TABLES_TV6_DIR,
    figures_dir: Path = FIGURES_TV6_DIR,
) -> Dict[str, Any]:
    """Execute Step 2 text preprocessing end-to-end."""
    logger.info("=== STARTING STEP 2: VIETNAMESE NLP PREPROCESSING & TOKENIZATION ===")
    start_time = datetime.now()

    if not input_file.exists():
        raise FileNotFoundError(f"Input usable reviews file not found: {input_file}")

    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    DOCS_TV6_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Read input records
    logger.info("Reading usable reviews from %s", input_file)
    records: List[Dict[str, Any]] = []
    with input_file.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                records.append(json.loads(line_str))

    total_records = len(records)
    logger.info("Loaded %d usable records for NLP preprocessing.", total_records)

    # 2. Process records through pipeline
    processed_records: List[Dict[str, Any]] = []
    token_counter = Counter()
    doc_freq_counter = Counter()
    token_lengths: List[int] = []

    for idx, rec in enumerate(records, 1):
        raw_text = rec.get("review_text_normalized") or ""
        prep_res = preprocess_text(raw_text)

        # Fallback if stopwords removed is completely empty
        clean_text = prep_res["text_stopwords_removed"] or prep_res["text_tokenized"] or raw_text
        tokens = prep_res["tokens_list"] or clean_text.split()

        enriched = dict(rec)
        enriched["text_cleaned"] = prep_res["text_cleaned"]
        enriched["text_tokenized"] = prep_res["text_tokenized"]
        enriched["text_stopwords_removed"] = clean_text
        enriched["tokens_list"] = tokens
        enriched["token_count"] = len(tokens)
        enriched["step2_version"] = TV6_PIPELINE_VERSION

        processed_records.append(enriched)
        token_lengths.append(len(tokens))

        # Accumulate token frequency
        token_counter.update(tokens)
        doc_freq_counter.update(set(tokens))

        if idx % 3000 == 0 or idx == total_records:
            logger.info("Processed %d / %d reviews (%.1f%%)...", idx, total_records, idx / total_records * 100)

    # 3. Export JSONL output
    logger.info("Exporting %d preprocessed records to %s", len(processed_records), output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8", newline="\n") as f:
        for r in processed_records:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")

    # 4. Generate Table 2.1: Preprocessing Pipeline Stages Comparison
    logger.info("Generating Table 2.1: Pipeline stages sample...")
    sample_indices = [0, 1, 2, 5, 10, 50, 100, 500, 1000, 5000]
    sample_rows = []
    for s_idx in sample_indices:
        if s_idx < len(processed_records):
            r = processed_records[s_idx]
            sample_rows.append({
                "sample_id": s_idx + 1,
                "rating": r["rating_raw"],
                "product_name": (r.get("product_name") or "")[:30] + "...",
                "raw_text": (r.get("review_text_normalized") or "")[:70],
                "cleaned": r["text_cleaned"][:70],
                "tokenized": r["text_tokenized"][:70],
                "stopwords_filtered": r["text_stopwords_removed"][:70],
                "token_count": r["token_count"],
            })
    df_samples = pd.DataFrame(sample_rows)
    save_table(df_samples, "table_2_1_preprocessing_pipeline_stages", tables_dir)

    # 5. Generate Table 2.2: Teencode Dictionary Audit
    logger.info("Generating Table 2.2: Teencode dictionary audit...")
    teencode_rows = []
    for slang, standard in sorted(TEENCODE_DICT.items()):
        category = "Negation" if standard == "không" or standard == "chưa" else (
            "Hardware / Domain" if any(w in standard for w in ["điện_thoại", "laptop", "pin", "bảo_hành", "nhân_viên", "thế_giới", "fpt", "cellphones", "sản_phẩm"]) else "Conversational Slang"
        )
        teencode_rows.append({
            "teencode_token": slang,
            "normalized_standard": standard,
            "category": category,
        })
    df_teencode = pd.DataFrame(teencode_rows)
    save_table(df_teencode, "table_2_2_teencode_dictionary", tables_dir)

    # 6. Generate Table 2.3: Top 50 Most Frequent Tokens
    logger.info("Generating Table 2.3: Top 50 frequent tokens...")
    top50_rows = []
    total_tokens_in_corpus = sum(token_counter.values())
    for rank, (token, count) in enumerate(token_counter.most_common(50), 1):
        df_count = doc_freq_counter[token]
        top50_rows.append({
            "rank": rank,
            "token": token,
            "corpus_frequency": count,
            "corpus_share_pct": round(count / total_tokens_in_corpus * 100, 2),
            "doc_frequency": df_count,
            "doc_coverage_pct": round(df_count / total_records * 100, 2),
        })
    df_top50 = pd.DataFrame(top50_rows)
    save_table(df_top50, "table_2_3_token_frequency_top50", tables_dir)

    # 7. Generate Figure 2.1: Top 30 Tokens Visualization
    logger.info("Generating Figure 2.1: Top 30 tokens chart...")
    top30_df = df_top50.head(30).iloc[::-1]  # reverse for horizontal bar chart

    # Assign semantic colors
    colors = []
    for tok in top30_df["token"]:
        if tok in {"tốt", "ok", "rất_tốt", "ưng_ý", "hài_lòng", "mượt", "đẹp", "pos_emoji", "nhanh", "ổn", "tuyệt_vời"}:
            colors.append("#2ca02c")  # Green for positive
        elif tok in {"không", "kém", "chậm", "lỗi", "hỏng", "thất_vọng", "tệ", "neg_emoji"}:
            colors.append("#d62728")  # Red for negative
        elif tok in {"pin", "máy", "màn_hình", "điện_thoại", "sản_phẩm", "nhân_viên", "bảo_hành", "giá", "camera"}:
            colors.append("#1f77b4")  # Blue for domain aspects
        else:
            colors.append("#7f7f7f")  # Grey for general qualifiers

    fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
    bars = ax.barh(top30_df["token"], top30_df["corpus_frequency"], color=colors, edgecolor="black", linewidth=0.5)

    ax.set_title("Top 30 Từ Tố (Tokens) Xuất hiện Nhiều nhất trong Corpus Review (Bước 2)", fontsize=13, weight="bold")
    ax.set_xlabel("Tần suất xuất hiện (Corpus Frequency)", fontsize=11)
    ax.set_ylabel("Token chuẩn hóa", fontsize=11)

    # Value labels
    for bar in bars:
        width = bar.get_width()
        ax.text(width + 30, bar.get_y() + bar.get_height() / 2, f"{int(width):,}", va="center", fontsize=9)

    plt.tight_layout()
    fig_path = figures_dir / "fig_2_1_top_tokens_frequency.png"
    fig.savefig(fig_path)
    plt.close(fig)
    logger.info("Saved figure to %s", fig_path)

    # 8. Compute Manifest & Quality Metrics
    vocab_size = len(token_counter)
    singletons = sum(1 for c in token_counter.values() if c == 1)

    report_metrics = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "step": "step2_text_preprocessing",
        "inputs": {
            "usable_reviews_file": str(input_file.relative_to(input_file.parents[2])),
            "record_count": total_records,
        },
        "outputs": {
            "preprocessed_file": str(output_file.relative_to(output_file.parents[2])),
            "record_count": len(processed_records),
            "file_size_bytes": output_file.stat().st_size,
        },
        "vocabulary_statistics": {
            "total_tokens_in_corpus": total_tokens_in_corpus,
            "unique_vocabulary_size": vocab_size,
            "singleton_tokens_count": singletons,
            "singleton_ratio_pct": round(singletons / vocab_size * 100, 2) if vocab_size else 0.0,
            "avg_tokens_per_review": round(float(np.mean(token_lengths)), 2),
            "median_tokens_per_review": int(np.median(token_lengths)),
            "max_tokens_in_review": int(np.max(token_lengths)),
        },
        "top_tokens": [
            {"token": row["token"], "frequency": row["corpus_frequency"]}
            for _, row in df_top50.head(10).iterrows()
        ],
        "teencode_dictionary_size": len(TEENCODE_DICT),
        "safe_stopwords_count": len(SAFE_STOPWORDS),
        "sentiment_whitelist_count": len(SENTIMENT_WHITELIST),
    }

    report_json_str = json.dumps(report_metrics, ensure_ascii=False, indent=2)
    PREPROCESSING_REPORT_FILE.write_text(report_json_str, encoding="utf-8")
    DOCS_PREPROCESSING_REPORT_FILE.write_text(report_json_str, encoding="utf-8")
    logger.info("Saved preprocessing report to %s and %s", PREPROCESSING_REPORT_FILE, DOCS_PREPROCESSING_REPORT_FILE)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info("=== STEP 2 COMPLETED IN %.2f SECONDS ===", duration)

    return report_metrics


if __name__ == "__main__":
    run_text_preprocessing()
