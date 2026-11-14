"""Runner script for Step 2 (TV6 Text Preprocessing & Tokenization).

Can be executed directly via:
    python src/review_nlp/run_step2.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.preprocess import run_text_preprocessing

if __name__ == "__main__":
    report = run_text_preprocessing()
    vocab = report["vocabulary_statistics"]
    print("\n" + "=" * 65)
    print("STEP 2: VIETNAMESE TEXT PREPROCESSING & TOKENIZATION SUMMARY")
    print("=" * 65)
    print(f"Pipeline Version       : {report['pipeline_version']}")
    print(f"Total Reviews Processed: {report['outputs']['record_count']:,} (100% Retained)")
    print(f"Preprocessed File Size : {report['outputs']['file_size_bytes'] / (1024 * 1024):.2f} MB")
    print("-" * 65)
    print("Corpus Vocabulary Metrics:")
    print(f"  - Total Tokens in Corpus : {vocab['total_tokens_in_corpus']:,}")
    print(f"  - Unique Vocabulary Size : {vocab['unique_vocabulary_size']:,} words")
    print(f"  - Singleton Tokens (Freq 1): {vocab['singleton_tokens_count']:,} ({vocab['singleton_ratio_pct']}%)")
    print(f"  - Tokens / Review        : Median {vocab['median_tokens_per_review']} | Mean {vocab['avg_tokens_per_review']} (Max {vocab['max_tokens_in_review']})")
    print("-" * 65)
    print("Top 10 Most Frequent Normalized Tokens:")
    for item in report["top_tokens"]:
        print(f"  * {item['token']:15s}: {item['frequency']:,} times")
    print("-" * 65)
    print(f"Teencode Dictionary    : {report['teencode_dictionary_size']} slang mappings")
    print(f"Sentiment Whitelist    : {report['sentiment_whitelist_count']} protected polarity tokens")
    print(f"Tables Saved           : data/tv6/tables/ (table_2_1, table_2_2, table_2_3)")
    print(f"Figures Saved          : data/tv6/figures/ (fig_2_1_top_tokens_frequency.png)")
    print("=" * 65 + "\n")
