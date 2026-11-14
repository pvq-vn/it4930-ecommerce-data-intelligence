"""Command-line runner for TV6 Step 3.1: Sentiment Classification ML Baseline.

Usage:
    python src/review_nlp/run_step3_1.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time
from src.review_nlp.sentiment_baseline import run_sentiment_baseline_pipeline


def main() -> None:
    t_start = time.time()
    try:
        report = run_sentiment_baseline_pipeline()
        best_model = report.get("best_model_selected", "N/A")
        macro_f1 = report["model_results"][best_model]["test_macro_f1"]
        weighted_f1 = report["model_results"][best_model]["test_weighted_f1"]
        print(f"\n[SUCCESS] Step 3.1 finished in {time.time() - t_start:.2f}s.")
        print(f"[BEST MODEL] {best_model} -> Test Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")
        print("Outputs generated:")
        print("  - Data JSONL : data/tv6/reviews_tv6_sentiment_baseline.jsonl")
        print("  - Metadata   : data/tv6/sentiment_baseline_report.json")
        print("  - Tables     : data/tv6/tables/ (table_3_1, table_3_2, table_3_3)")
        print("  - Figures    : data/tv6/figures/ (fig_3_1, fig_3_2, fig_3_3)")
    except Exception as e:
        print(f"\n[ERROR] Step 3.1 failed with error: {e}", file=sys.stderr)
        raise e


if __name__ == "__main__":
    main()
