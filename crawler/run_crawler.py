import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reconfigure stdout/stderr to UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def crawl_category(category: str, limit: int, output_file: str = None) -> int:
    """
    Chạy spider tương ứng qua subprocess để đảm bảo tiến trình Scrapy / Twisted sạch sẽ.
    """
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    if category == "laptop":
        spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_laptop_spider.py"
        out_dir = PROJECT_ROOT / "data" / "raw" / "tgdd" / "laptop"
        default_out = out_dir / "pilot.jsonl"
    elif category == "smartphone":
        spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_smartphone_spider.py"
        out_dir = PROJECT_ROOT / "data" / "raw" / "tgdd" / "smartphone"
        default_out = out_dir / "pilot.jsonl"
    else:
        raise ValueError(f"Không hỗ trợ category: {category}")

    out_dir.mkdir(parents=True, exist_ok=True)
    target_out = Path(output_file) if output_file else default_out

    # Nếu file đã tồn tại, xóa để ghi mới đợt crawl
    if target_out.exists():
        target_out.unlink()

    print(f"\n========================================================")
    print(f"BẮT ĐẦU CRAWL: category={category.upper()} (giới hạn ~{limit} sản phẩm)")
    print(f"Spider: {spider_file.name}")
    print(f"Output: {target_out}")
    print(f"========================================================\n")

    cmd = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(spider_file),
        "-a",
        f"max_products={limit}",
        "-o",
        str(target_out),
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"[LỖI] Tiến trình crawl {category} thoát với mã lỗi: {result.returncode}")
        return 0

    record_count = 0
    if target_out.exists():
        with open(target_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record_count += 1

    print(f"\n[KẾT QUẢ] {category.upper()}: Thu thập thành công {record_count} records vào {target_out.name}\n")
    return record_count


def main():
    parser = argparse.ArgumentParser(description="TV1 - TGDĐ Web Crawler Runner")
    parser.add_argument(
        "--category",
        choices=["laptop", "smartphone", "all"],
        default="all",
        help="Danh mục cần crawl (laptop, smartphone, all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Số lượng sản phẩm mục tiêu (mặc định 50)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="File đầu ra tùy chỉnh (chỉ dùng khi chọn 1 category)",
    )
    args = parser.parse_args()

    start_time = datetime.now()
    results = {}

    if args.category in ("laptop", "all"):
        count = crawl_category("laptop", args.limit, args.output if args.category == "laptop" else None)
        results["laptop"] = count

    if args.category in ("smartphone", "all"):
        count = crawl_category("smartphone", args.limit, args.output if args.category == "smartphone" else None)
        results["smartphone"] = count

    duration = datetime.now() - start_time
    print("========================================================")
    print("TỔNG HỢP KẾT QUẢ PILOT CRAWL:")
    for cat, cnt in results.items():
        print(f"  - {cat.capitalize()}: {cnt} records")
    print(f"Thời gian thực hiện: {duration.total_seconds():.1f}s")
    print("========================================================")


if __name__ == "__main__":
    main()
