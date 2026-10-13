import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reconfigure stdout/stderr to UTF-8 for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def generate_batch_id(dt: Optional[datetime] = None) -> str:
    """Tạo batch_id từ timestamp (mặc định là datetime hiện tại)."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")


def get_snapshot_path(category: str, batch_id: str, base_dir: Optional[Path] = None) -> Path:
    """
    Tạo đường dẫn snapshot bất biến (immutable raw snapshot).
    Bảo toàn snapshot cũ, không thực hiện overwrite.
    """
    if base_dir is None:
        base_dir = PROJECT_ROOT / "data" / "raw" / "tgdd"
    return base_dir / category / f"{batch_id}.jsonl"


def crawl_category(
    category: str,
    limit: int,
    output_file: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> int:
    """
    Chạy spider tương ứng qua subprocess để đảm bảo tiến trình Scrapy / Twisted sạch sẽ.
    Mặc định tạo file immutable raw snapshot dạng <batch_id>.jsonl, bảo toàn snapshot cũ.
    """
    if category == "laptop":
        spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_laptop_spider.py"
    elif category == "smartphone":
        spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_smartphone_spider.py"
    else:
        raise ValueError(f"Không hỗ trợ category: {category}")

    # Xác định batch_id và output path
    actual_batch_id = batch_id or generate_batch_id()
    if output_file:
        target_out = Path(output_file)
        if batch_id is None:
            actual_batch_id = target_out.stem
    else:
        target_out = get_snapshot_path(category, actual_batch_id)

    target_out.parent.mkdir(parents=True, exist_ok=True)

    print("\n========================================================")
    print(f"BẮT ĐẦU CRAWL: category={category.upper()} (giới hạn ~{limit} sản phẩm)")
    print(f"Spider: {spider_file.name}")
    print(f"Batch ID: {actual_batch_id}")
    print(f"Output: {target_out}")
    print("========================================================\n")

    cmd = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(spider_file),
        "-a",
        f"max_products={limit}",
        "-a",
        f"batch_id={actual_batch_id}",
        "-o",
        str(target_out),
    ]

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"\n[LỖI] Tiến trình crawl {category.upper()} thoát với mã lỗi: {result.returncode}")
        return 0

    record_count = 0
    if target_out.exists():
        with open(target_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record_count += 1

    if record_count > 0:
        print(f"\n[KẾT QUẢ] {category.upper()}: Thu thập thành công {record_count} records vào {target_out}\n")
    else:
        print(f"\n[CẢNH BÁO] {category.upper()}: Tiến trình hoàn tất nhưng không có record nào được ghi vào {target_out}\n")

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
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Batch ID tùy chỉnh (mặc định tự động sinh theo timestamp)",
    )
    args = parser.parse_args()

    if args.output and args.category == "all":
        parser.error("Tùy chọn --output chỉ có thể dùng khi crawl 1 category (laptop hoặc smartphone), không áp dụng cho 'all'.")

    start_time = datetime.now()
    results = {}

    if args.category in ("laptop", "all"):
        count = crawl_category(
            "laptop",
            args.limit,
            output_file=args.output if args.category == "laptop" else None,
            batch_id=args.batch_id if args.category == "laptop" else None,
        )
        results["laptop"] = count

    if args.category in ("smartphone", "all"):
        count = crawl_category(
            "smartphone",
            args.limit,
            output_file=args.output if args.category == "smartphone" else None,
            batch_id=args.batch_id if args.category == "smartphone" else None,
        )
        results["smartphone"] = count

    duration = datetime.now() - start_time
    print("========================================================")
    print("TỔNG HỢP KẾT QUẢ PILOT CRAWL:")
    for cat, cnt in results.items():
        status_label = f"{cnt} records" if cnt > 0 else "THẤT BẠI / 0 records"
        print(f"  - {cat.capitalize()}: {status_label}")
    print(f"Thời gian thực hiện: {duration.total_seconds():.1f}s")
    print("========================================================")

    if any(cnt == 0 for cnt in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
