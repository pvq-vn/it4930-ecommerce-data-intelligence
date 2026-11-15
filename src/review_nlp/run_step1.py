"""Runner script for Step 1 (TV6 Review Quality EDA).

Can be executed directly via:
    python src/review_nlp/run_step1.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.eda_quality import run_step1_quality_eda

if __name__ == "__main__":
    report = run_step1_quality_eda()
    m = report["metrics"]
    print("\n" + "=" * 65)
    print("STEP 1: REVIEW QUALITY PROFILING & EDA SUMMARY")
    print("=" * 65)
    print(f"Pipeline Version      : {report['pipeline_version']}")
    print(f"Total Reviews Audited : {m['ratings_and_usability']['total_reviews']:,}")
    print(f"Usable Reviews        : {m['ratings_and_usability']['usable_reviews']:,} ({m['ratings_and_usability']['overall_retention_rate_pct']}%)")
    print(f"Unusable Reviews      : {m['ratings_and_usability']['unusable_reviews']:,}")
    print("-" * 65)
    print("Text Characteristics (Usable Reviews):")
    print(f"  - Character Length  : Median {m['text_lengths']['char_median']} | Mean {m['text_lengths']['char_mean']}")
    print(f"  - Word Count        : Median {m['text_lengths']['word_median']} | Mean {m['text_lengths']['word_mean']} (Max {m['text_lengths']['max_words']})")
    print(f"  - Unique Texts      : {m['duplicate_texts']['unique_texts']:,} ({m['duplicate_texts']['unique_ratio_pct']}%)")
    print(f"  - Top Duplicate     : '{m['duplicate_texts']['top_frequent_text']}' ({m['duplicate_texts']['top_frequent_count']} times)")
    print("-" * 65)
    print("Sentiment / Rating Inconsistencies:")
    print(f"  - Total Mismatches  : {m['rating_text_mismatches']['total_mismatch_detected']:,}")
    print(f"    * High Rating (4-5★) with Negative Content : {m['rating_text_mismatches']['high_rating_negative_count']}")
    print(f"    * Low Rating (1-2★) with Positive Content  : {m['rating_text_mismatches']['low_rating_positive_count']}")
    print("-" * 65)
    print("Product Coverage for TV5 Price Prediction:")
    print(f"  - Total Products    : {m['tv5_product_coverage']['total_parent_products']:,}")
    print(f"  - With Reviews      : {m['tv5_product_coverage']['parents_with_reviews']:,} ({m['tv5_product_coverage']['coverage_rate_pct']}%)")
    print(f"  - Cold Start (0 rev): {m['tv5_product_coverage']['parents_zero_reviews']:,} ({m['tv5_product_coverage']['cold_start_rate_pct']}%)")
    print(f"  - Reviews / Product : Median {m['tv5_product_coverage']['median_reviews_among_covered']} | Mean {m['tv5_product_coverage']['avg_reviews_among_covered']} (Max {m['tv5_product_coverage']['max_reviews_on_single_product']})")
    print("=" * 65)
    print(f"Tables saved to       : data/tv6/tables/ ({len(report['artifacts_generated']['tables'])} files)")
    print(f"Figures saved to      : data/tv6/figures/ ({len(report['artifacts_generated']['figures'])} files)")
    print("=" * 65 + "\n")
