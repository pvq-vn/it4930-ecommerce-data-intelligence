"""Command-line runner for TV6 Step 4: Topic Modeling (LDA & NMF) & Aspect-Based Sentiment Analysis.

Usage:
    python src/review_nlp/run_step4.py
"""

from pathlib import Path
import sys
import time

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.topic_aspect_mining import run_step4_pipeline


def main() -> None:
    t_start = time.time()
    try:
        report = run_step4_pipeline()
        runtime = report.get("total_runtime_seconds", round(time.time() - t_start, 2))
        coverage = report.get("aspect_coverage_rate", 0.0)

        print("\n" + "=" * 70)
        print(f"[THÀNH CÔNG] Step 4 Topic & Aspect Mining hoàn tất trong {runtime:.1f}s!")
        print(f"  - Độ phủ khía cạnh trên toàn kho: {coverage}% reviews")
        print("  - Xem báo cáo chi tiết: docs/tv6/step4_topic_aspect_mining.md")
        print("=" * 70 + "\n")
    except Exception as e:
        print(f"\n[LỖI THỰC THI BƯỚC 4] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
