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


def get_snapshot_path(category: str, batch_id: str, base_dir: Optional[Path] = None, source: str = "tgdd") -> Path:
    """
    Tạo đường dẫn snapshot bất biến (immutable raw snapshot) cho sản phẩm/biến thể.
    Bảo toàn snapshot cũ, không thực hiện overwrite.
    """
    if base_dir is None:
        source_folder = "cellphoneS" if source.lower() == "cellphones" else source
        base_dir = PROJECT_ROOT / "data" / "raw" / source_folder
    return base_dir / category / f"{batch_id}.jsonl"


def get_review_snapshot_path(category: str, batch_id: str, base_dir: Optional[Path] = None, source: str = "tgdd") -> Path:
    """
    Tạo đường dẫn snapshot bất biến (immutable raw snapshot) cho review/comment.
    Bảo toàn snapshot cũ, không thực hiện overwrite.
    """
    if base_dir is None:
        source_folder = "cellphoneS" if source.lower() == "cellphones" else source
        base_dir = PROJECT_ROOT / "data" / "raw" / source_folder
    return base_dir / f"{category}_reviews" / f"{batch_id}.jsonl"


def ensure_output_path_available(output_path: Path) -> None:
    """
    Đảm bảo output path chưa tồn tại.

    Raw snapshot phải immutable:
    - Không overwrite
    - Không append vào snapshot cũ
    """
    if output_path.exists():
        raise FileExistsError(
            f"Output snapshot đã tồn tại: {output_path}. "
            "Không được overwrite/append vào raw snapshot cũ."
        )


def crawl_category(
    category: str,
    limit: Optional[int] = 50,
    output_file: Optional[str] = None,
    batch_id: Optional[str] = None,
    source: str = "tgdd",
) -> int:
    """
    Chạy spider tương ứng qua subprocess để đảm bảo tiến trình Scrapy / Twisted sạch sẽ.
    Mặc định tạo file immutable raw snapshot dạng <batch_id>.jsonl, bảo toàn snapshot cũ.
    limit=None biểu diễn chế độ FULL CRAWL (unlimited).
    """
    src_key = source.lower()
    if src_key == "tgdd":
        if category == "laptop":
            spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_laptop_spider.py"
        elif category == "smartphone":
            spider_file = PROJECT_ROOT / "crawler" / "tgdd" / "tgdd_smartphone_spider.py"
        else:
            raise ValueError(f"Không hỗ trợ category: {category}")
    elif src_key == "fptshop":
        if category == "laptop":
            spider_file = PROJECT_ROOT / "crawler" / "fptshop" / "fptshop_laptop_spider.py"
        elif category == "smartphone":
            spider_file = PROJECT_ROOT / "crawler" / "fptshop" / "fptshop_smartphone_spider.py"
        else:
            raise ValueError(f"Không hỗ trợ category: {category}")
    elif src_key == "cellphones":
        if category == "laptop":
            spider_file = PROJECT_ROOT / "crawler" / "cellphoneS" / "cellphones_laptop_spider.py"
        elif category == "smartphone":
            spider_file = PROJECT_ROOT / "crawler" / "cellphoneS" / "cellphones_smartphone_spider.py"
        else:
            raise ValueError(f"Không hỗ trợ category: {category}")
    else:
        raise ValueError(f"Không hỗ trợ source: {source}")

    # Xác định batch_id và output paths (product và review riêng biệt)
    actual_batch_id = batch_id or generate_batch_id()
    if output_file:
        target_out = Path(output_file)
        if batch_id is None:
            actual_batch_id = target_out.stem
        review_out = target_out.parent / f"{target_out.stem}_reviews.jsonl"
    else:
        target_out = get_snapshot_path(category, actual_batch_id, source=source)
        review_out = get_review_snapshot_path(category, actual_batch_id, source=source)

    target_out.parent.mkdir(parents=True, exist_ok=True)
    review_out.parent.mkdir(parents=True, exist_ok=True)
    ensure_output_path_available(target_out)
    ensure_output_path_available(review_out)

    limit_desc = f"giới hạn ~{limit} sản phẩm" if limit is not None else "FULL CRAWL (không giới hạn)"
    print("\n========================================================")
    print(f"BẮT ĐẦU CRAWL: [{source.upper()}] category={category.upper()} ({limit_desc})")
    print(f"Spider: {spider_file.name}")
    print(f"Batch ID: {actual_batch_id}")
    print(f"Product Output: {target_out}")
    print(f"Review Output:  {review_out}")
    print("========================================================\n")

    cmd = [
        sys.executable,
        "-m",
        "scrapy",
        "runspider",
        str(spider_file),
        "-a",
        f"batch_id={actual_batch_id}",
        "-o",
        str(target_out),
        "-a",
        f"review_output={str(review_out)}",
    ]
    if limit is not None:
        cmd.extend(["-a", f"max_products={limit}"])
    else:
        cmd.extend(["-a", "max_products=none"])

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print(f"\n[LỖI] Tiến trình crawl [{source.upper()}] {category.upper()} thoát với mã lỗi: {result.returncode}")
        return 0

    record_count = 0
    if target_out.exists():
        with open(target_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record_count += 1

    review_count = 0
    if review_out.exists():
        with open(review_out, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    review_count += 1

    if record_count > 0:
        print(f"\n[KẾT QUẢ] [{source.upper()}] {category.upper()}: Thu thập thành công {record_count} product/variant records vào {target_out}")
        print(f"                                   và {review_count} review records vào {review_out}\n")
    else:
        print(f"\n[CẢNH BÁO] [{source.upper()}] {category.upper()}: Tiến trình hoàn tất nhưng không có record nào được ghi vào {target_out}\n")

    return record_count


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TV1 - Multi-Source Tech E-Commerce Crawler Runner")
    parser.add_argument(
        "--source",
        choices=["tgdd", "fptshop", "cellphones", "all"],
        default="tgdd",
        help="Sàn thương mại điện tử cần crawl (tgdd, fptshop, cellphones, all - mặc định tgdd)",
    )
    parser.add_argument(
        "--category",
        choices=["laptop", "smartphone", "all"],
        default="all",
        help="Danh mục cần crawl (laptop, smartphone, all)",
    )

    # Nhóm mutually exclusive giữa --limit và --full
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Số lượng sản phẩm mục tiêu (mặc định 50 trong chế độ pilot)",
    )
    mode_group.add_argument(
        "--full",
        action="store_true",
        default=False,
        help="Thu thập toàn bộ sản phẩm trong danh mục (unlimited, không giới hạn)",
    )

    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="File đầu ra tùy chỉnh (chỉ dùng khi chọn 1 source và 1 category)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Batch ID tùy chỉnh (mặc định tự động sinh theo timestamp)",
    )
    return parser


def main():
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.full and args.limit is not None:
        parser.error(
            "Không được chỉ định đồng thời cả --full và --limit. "
            "Chọn --full để crawl toàn bộ hoặc --limit <N> để đặt số lượng cụ thể."
        )

    if args.output and (args.category == "all" or args.source == "all"):
        parser.error("Tùy chọn --output chỉ có thể dùng khi crawl 1 source và 1 category cụ thể.")

    if args.full:
        effective_limit = None
    elif args.limit is not None:
        effective_limit = args.limit
    else:
        effective_limit = 50

    sources = ["tgdd", "fptshop", "cellphones"] if args.source == "all" else [args.source]
    categories = ["laptop", "smartphone"] if args.category == "all" else [args.category]

    start_time = datetime.now()
    results = {}

    try:
        for src in sources:
            for cat in categories:
                key = f"{src}_{cat}"
                count = crawl_category(
                    cat,
                    limit=effective_limit,
                    output_file=args.output if len(sources) == 1 and len(categories) == 1 else None,
                    batch_id=args.batch_id,
                    source=src,
                )
                results[key] = count
    except FileExistsError as exc:
        print(f"\n[LỖI] {exc}\n")
        sys.exit(1)

    duration = datetime.now() - start_time
    mode_label = "FULL CRAWL" if effective_limit is None else f"PILOT CRAWL (limit={effective_limit})"
    print("========================================================")
    print(f"TỔNG HỢP KẾT QUẢ {mode_label}:")
    for key, cnt in results.items():
        status_label = f"{cnt} records" if cnt > 0 else "THẤT BẠI / 0 records"
        print(f"  - {key.upper()}: {status_label}")
    print(f"Thời gian thực hiện: {duration.total_seconds():.1f}s")
    print("========================================================")

    if any(cnt == 0 for cnt in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
