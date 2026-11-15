"""Configuration module for TV6 (Review NLP Sentiment Analysis).

Defines canonical field lists, directory paths, file names, and pipeline parameters
compliant with the TV2-TV8 feature contract (docs/feature_contracts_tv3_tv8.md).
"""

from pathlib import Path

# Project root directory
ROOT_DIR = Path(__file__).resolve().parents[2]

# Input directories and files
GOLD_V2_DIR = ROOT_DIR / "data" / "gold_v2"
FACT_REVIEWS_FILE = GOLD_V2_DIR / "fact_reviews.jsonl"
DIM_SOURCE_PARENTS_FILE = GOLD_V2_DIR / "dim_source_parents.jsonl"
FACT_REVIEW_REPLIES_FILE = GOLD_V2_DIR / "fact_review_replies.jsonl"

PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWS_PROCESSED_FILE = PROCESSED_DIR / "reviews_processed.jsonl"

# Output directories
DATA_TV6_DIR = ROOT_DIR / "data" / "tv6"
DOCS_TV6_DIR = ROOT_DIR / "docs" / "tv6"
FIGURES_TV6_DIR = DATA_TV6_DIR / "figures"
TABLES_TV6_DIR = DATA_TV6_DIR / "tables"

# Step 0 Output files
REVIEWS_TV6_ALL_FILE = DATA_TV6_DIR / "reviews_tv6_all.jsonl"
REVIEWS_TV6_USABLE_FILE = DATA_TV6_DIR / "reviews_tv6_usable.jsonl"
REVIEWS_TV6_UNUSABLE_FILE = DATA_TV6_DIR / "reviews_tv6_unusable.jsonl"
STEP0_MANIFEST_FILE = DATA_TV6_DIR / "view_manifest_step0.json"
DOCS_STEP0_MANIFEST_FILE = DOCS_TV6_DIR / "view_manifest_step0.json"

# Step 1 Output files
QUALITY_REPORT_FILE = DATA_TV6_DIR / "quality_report.json"
DOCS_QUALITY_REPORT_FILE = DOCS_TV6_DIR / "quality_report.json"
DOCS_STEP1_REPORT_FILE = DOCS_TV6_DIR / "step1_quality_eda.md"

# Step 2 Output files
REVIEWS_TV6_PREPROCESSED_FILE = DATA_TV6_DIR / "reviews_tv6_preprocessed.jsonl"
PREPROCESSING_REPORT_FILE = DATA_TV6_DIR / "preprocessing_report.json"
DOCS_PREPROCESSING_REPORT_FILE = DOCS_TV6_DIR / "preprocessing_report.json"
DOCS_STEP2_REPORT_FILE = DOCS_TV6_DIR / "step2_text_preprocessing.md"

# Step 3 Sentiment Output files (Baseline + PhoBERT)
DOCS_STEP3_REPORT_FILE = DOCS_TV6_DIR / "step3_sentiment_analysis.md"
REVIEWS_TV6_SENTIMENT_BASELINE_FILE = DATA_TV6_DIR / "reviews_tv6_sentiment_baseline.jsonl"
SENTIMENT_BASELINE_REPORT_FILE = DATA_TV6_DIR / "sentiment_baseline_report.json"
DOCS_SENTIMENT_BASELINE_REPORT_FILE = DOCS_TV6_DIR / "sentiment_baseline_report.json"
DOCS_STEP3_1_REPORT_FILE = DOCS_TV6_DIR / "step3_sentiment_analysis.md"

# Step 3.2 PhoBERT Fine-Tuning Output files
REVIEWS_TV6_SENTIMENT_PHOBERT_FILE = DATA_TV6_DIR / "reviews_tv6_sentiment_phobert.jsonl"
SENTIMENT_PHOBERT_REPORT_FILE = DATA_TV6_DIR / "sentiment_phobert_report.json"
DOCS_SENTIMENT_PHOBERT_REPORT_FILE = DOCS_TV6_DIR / "sentiment_phobert_report.json"
DOCS_STEP3_2_REPORT_FILE = DOCS_TV6_DIR / "step3_sentiment_analysis.md"
PHOBERT_MODEL_DIR = DATA_TV6_DIR / "models" / "phobert_sentiment"
PHOBERT_PRETRAINED_NAME = "vinai/phobert-base-v2"
PHOBERT_FALLBACK_NAME = "vinai/phobert-base"

# Step 4 Topic Modeling & Aspect Mining Output files
REVIEWS_TV6_ASPECTS_FILE = DATA_TV6_DIR / "reviews_tv6_aspects.jsonl"
TOPIC_ASPECT_REPORT_FILE = DATA_TV6_DIR / "topic_aspect_report.json"
DOCS_TOPIC_ASPECT_REPORT_FILE = DOCS_TV6_DIR / "topic_aspect_report.json"
DOCS_STEP4_REPORT_FILE = DOCS_TV6_DIR / "step4_topic_aspect_mining.md"

# Step 5 TV5 Feature Engineering & Handoff Output files
TV5_FEATURES_PARQUET = DATA_TV6_DIR / "tv5_review_features.parquet"
TV5_FEATURES_CSV = DATA_TV6_DIR / "tv5_review_features.csv"
TV5_FEATURES_ACTIVE_PARQUET = DATA_TV6_DIR / "tv5_review_features_active_only.parquet"
TV5_FEATURES_ACTIVE_CSV = DATA_TV6_DIR / "tv5_review_features_active_only.csv"
TV5_FEATURE_REPORT_FILE = DATA_TV6_DIR / "tv5_feature_report.json"
DOCS_TV5_FEATURE_REPORT_FILE = DOCS_TV6_DIR / "tv5_feature_report.json"
DOCS_STEP5_REPORT_FILE = DOCS_TV6_DIR / "step5_tv5_feature_handoff.md"

# Pipeline Metadata
TV6_PIPELINE_VERSION = "tv6-v1.0.0"

# Canonical & Provenance Fields for TV6 Analytical View
TV6_CANONICAL_FIELDS = [
    # Primary & Relational Keys
    "review_record_id",
    "source_parent_id",
    "product_name",
    "source",
    "category",
    # Core Review Attributes
    "rating_raw",
    "rating_norm",
    "review_text_normalized",
    "review_time_raw",
    "author_raw",
    # Quality & Usability Flags
    "review_usable",
    "review_text_status",
    "review_time_status",
    "is_reply_present",
    "is_attachment_present",
    "review_metadata_suspect_candidate",
    # Provenance & Audit Traceability
    "crawl_batch",
    "crawl_time",
    "raw_record_id",
    "raw_file",
    "raw_line_number",
    "gold_version",
    "tv6_pipeline_version",
]

# Rating-to-Sentiment mapping guidelines
# Rating 1-2: Negative, Rating 3: Neutral, Rating 4-5: Positive
RATING_SENTIMENT_MAP = {
    1: "negative",
    2: "negative",
    3: "neutral",
    4: "positive",
    5: "positive",
}
