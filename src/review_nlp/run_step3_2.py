"""Command-line runner for TV6 Step 3.2: PhoBERT Sentiment Classification Fine-Tuning.

Usage:
    python src/review_nlp/run_step3_2.py
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time


def main() -> None:
    # 1. Check prerequisite dependencies
    missing = []
    try:
        import torch
    except ImportError:
        missing.append("torch")

    try:
        import transformers
    except ImportError:
        missing.append("transformers")

    try:
        import accelerate
    except ImportError:
        missing.append("accelerate")

    if missing:
        print("\n" + "=" * 70, file=sys.stderr)
        print("[LỖI THIẾU THƯ VỊ CHẠY PHOBERT]", file=sys.stderr)
        print(f"Các thư viện sau chưa được cài đặt: {', '.join(missing)}", file=sys.stderr)
        print("\nVui lòng mở PowerShell và chạy 2 lệnh sau để cài đặt:", file=sys.stderr)
        print("  1. Cài đặt PyTorch hỗ trợ GPU CUDA 12.x:", file=sys.stderr)
        print("     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121", file=sys.stderr)
        print("  2. Cài đặt Transformers & Accelerate:", file=sys.stderr)
        print("     pip install transformers accelerate", file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
        sys.exit(1)

    # 2. Run pipeline
    from src.review_nlp.phobert_sentiment import run_phobert_pipeline

    t_start = time.time()
    try:
        report = run_phobert_pipeline()
        metrics = report.get("test_metrics", {})
        macro_f1 = metrics.get("test_macro_f1", 0.0)
        weighted_f1 = metrics.get("test_weighted_f1", 0.0)
        acc = metrics.get("test_accuracy", 0.0)

        print("\n" + "=" * 70)
        print(f"[THÀNH CÔNG] Step 3.2 PhoBERT hoàn tất trong {time.time() - t_start:.2f}s.")
        print(f"[KẾT QUẢ ĐỈNH CAO] Accuracy: {acc*100:.2f}% | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")
        print("Tệp đầu ra đã tạo:")
        print("  - Dữ liệu gán điểm : data/tv6/reviews_tv6_sentiment_phobert.jsonl")
        print("  - Báo cáo JSON     : data/tv6/sentiment_phobert_report.json")
        print("  - Bảng đối sánh    : data/tv6/tables/ (table_3_4, table_3_5)")
        print("  - Đồ thị huấn luyện: data/tv6/figures/ (fig_3_4, fig_3_5)")
        print("  - Weights mô hình  : data/tv6/models/phobert_sentiment/best_model/")
        print("=" * 70 + "\n")
    except Exception as e:
        print(f"\n[LỖI] Pipeline PhoBERT gặp lỗi: {e}", file=sys.stderr)
        raise e


if __name__ == "__main__":
    main()
