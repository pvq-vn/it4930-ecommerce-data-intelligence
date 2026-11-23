#!/usr/bin/env python3
"""CLI Entry point for TV6 Step 5: Feature Engineering & Aggregation for TV5 (Price Prediction).

Usage:
    python src/review_nlp/run_step5.py
"""

from pathlib import Path
import sys

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.feature_engineering_tv5 import run_feature_engineering_pipeline


def main():
    report = run_feature_engineering_pipeline()
    print("\nSummary Results:")
    print(f"- Total parent products: {report['universe_statistics']['total_parent_products']:,}")
    print(f"- Active products with reviews: {report['universe_statistics']['active_products_with_reviews']:,} ({report['universe_statistics']['coverage_percentage']}%)")
    print(f"- Cold-start products: {report['universe_statistics']['cold_start_products_without_reviews']:,} ({report['universe_statistics']['cold_start_percentage']}%)")
    print(f"- Total reviews aggregated: {report['universe_statistics']['total_reviews_aggregated']:,}")
    print(f"- Anti-leakage audit status: {report['anti_leakage_audit']['status']} (Violations: {report['anti_leakage_audit']['leakage_violations']})")
    print(f"- Features per record: {report['feature_schema']['total_features']}")
    print(f"- Handoff artifacts: tv5_review_features.parquet, tv5_review_features.csv")


if __name__ == "__main__":
    main()
