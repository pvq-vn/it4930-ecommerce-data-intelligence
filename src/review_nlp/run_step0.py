"""Runner script for Step 0 (TV6 Review NLP).

Can be executed directly via:
    python src/review_nlp/run_step0.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.build_view import run_build_analytical_view

if __name__ == "__main__":
    manifest = run_build_analytical_view()
    print("\n" + "=" * 60)
    print("STEP 0 EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Pipeline Version : {manifest['pipeline_version']}")
    print(f"Total Reviews    : {manifest['summary']['total_input_reviews']:,}")
    print(f"Usable NLP Set   : {manifest['summary']['usable_nlp_reviews']:,} ({manifest['summary']['usable_nlp_pct']}%)")
    print(f"Unusable Set     : {manifest['summary']['unusable_reviews']:,} ({manifest['summary']['unusable_pct']}%)")
    print(f"Unique Texts     : {manifest['summary']['unique_usable_texts']:,} ({manifest['summary']['unique_text_ratio_pct']}%)")
    print("-" * 60)
    print("Source Breakdown (Usable / Total):")
    for s, data in manifest['breakdown_by_source'].items():
        print(f"  - {s:15s}: {data['usable']:,} / {data['total']:,} ({data['retention_rate_pct']}%)")
    print("-" * 60)
    print("Baseline Sentiment Distribution (from Rating):")
    for label, data in manifest['sentiment_baseline_distribution'].items():
        print(f"  - {label.capitalize():10s}: {data['count']:,} ({data['share_pct']}%)")
    print("=" * 60 + "\n")
