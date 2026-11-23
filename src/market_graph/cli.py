"""Unified CLI for the 4-step Product Graph Analysis & Market Discovery pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.market_graph.llm_clean import (
    DEFAULT_CACHE,
    DEFAULT_CSV,
    DEFAULT_INPUT,
    DEFAULT_OUTPUT,
    run_step1,
)
from src.market_graph.bipartite_graph import DEFAULT_WORK_DIR, export_price_free_handoff, run_step2
from src.market_graph.louvain_segments import run_step3
from src.market_graph.gaps_and_reports import audit_review_claims, run_step4


def _parse_resolution(value: str) -> float | str:
    if str(value).lower() == "auto":
        return "auto"
    try:
        return float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("resolution must be 'auto' or a number") from exc


def run_step1_5(
    work_dir: Path = DEFAULT_WORK_DIR,
    input_path: Path | None = None,
) -> tuple[Path, Path]:
    """Extract benchmarks from HTML tables and match laptop and smartphone listings."""
    from src.market_graph.benchmark_extract import (
        CPU_HTML,
        GPU_HTML,
        PHONE_CPU_HTML,
        parse_cpu_benchmarks,
        parse_gpu_benchmarks,
        parse_phone_cpu_benchmarks,
    )
    from src.market_graph.laptop_benchmark_match import match_laptops
    from src.market_graph.smartphone_benchmark_match import match_smartphones

    bench_dir = work_dir / "benchmarks"
    bench_dir.mkdir(parents=True, exist_ok=True)
    cpu_csv = bench_dir / "cpu_benchmarks.csv"
    gpu_csv = bench_dir / "gpu_benchmarks.csv"
    phone_csv = bench_dir / "cpu_phone_benchmarks.csv"

    cpu_html = (bench_dir / "notebookcheck_cpu.html") if (bench_dir / "notebookcheck_cpu.html").exists() else CPU_HTML
    gpu_html = (bench_dir / "notebookcheck_gpu.html") if (bench_dir / "notebookcheck_gpu.html").exists() else GPU_HTML
    phone_html = (bench_dir / "notebookcheck_cpu_phone.html") if (bench_dir / "notebookcheck_cpu_phone.html").exists() else PHONE_CPU_HTML

    # Extract each benchmark table independently so one updated HTML does not block the others.
    if cpu_html.exists():
        parse_cpu_benchmarks(cpu_html).to_csv(cpu_csv, index=False, encoding="utf-8-sig")
    if gpu_html.exists():
        parse_gpu_benchmarks(gpu_html).to_csv(gpu_csv, index=False, encoding="utf-8-sig")
    if phone_html.exists():
        parse_phone_cpu_benchmarks(phone_html).to_csv(phone_csv, index=False, encoding="utf-8-sig")

    cleaned_input = input_path or (work_dir / "products_llm_cleaned.jsonl")
    if not cleaned_input.exists():
        print(f"[Step 1.5] Warning: {cleaned_input} not found. Skipping listing match.")
        return cpu_csv, phone_csv

    laptop_out = match_laptops(
        input_path=cleaned_input,
        output_csv=work_dir / "laptop_benchmarks.csv",
        output_jsonl=work_dir / "laptop_benchmarks.jsonl",
        report_csv=bench_dir / "match_report.csv",
        cpu_csv=cpu_csv,
        gpu_csv=gpu_csv,
    )
    phone_out = match_smartphones(
        input_path=cleaned_input,
        output_csv=work_dir / "smartphone_benchmarks.csv",
        output_jsonl=work_dir / "smartphone_benchmarks.jsonl",
        report_csv=bench_dir / "smartphone_match_report.csv",
        phone_cpu_csv=phone_csv,
    )
    return laptop_out, phone_out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.market_graph.cli",
        description="IT4930 Product Graph Analysis & Market Discovery Pipeline (Steps 1-4).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser("step1", help="Export raw CSV & clean/extract specs via DeepSeek API.")
    p1.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    p1.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p1.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    p1.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    p1.add_argument("--export-csv", action=argparse.BooleanOptionalAction, default=True)
    p1.add_argument("--sample-size", type=int, default=None, help="Run pilot on N stratified rows (e.g. 100).")
    p1.add_argument("--batch-size", type=int, default=25)
    p1.add_argument("--model", default="deepseek-chat")
    p1.add_argument("--dry-run", action="store_true")

    p1_5 = sub.add_parser(
        "step1_5",
        aliases=["benchmarks", "step1-5"],
        help="Extract benchmarks & match laptops and smartphones.",
    )
    p1_5.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    p1_5.add_argument("--input", type=Path, default=None, help="Path to products_llm_cleaned.jsonl")

    p2 = sub.add_parser("step2", help="Entity resolution (<= 20 percent price spread) & Bipartite Graph.")
    p2.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    p2.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    p2.add_argument("--max-spread", type=float, default=0.20)

    p3 = sub.add_parser("step3", help="Product-Product Similarity Graph & Louvain segmentation.")
    p3.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    p3.add_argument("--price-tol", type=float, default=0.20, help="Max relative price gap (default: 0.20).")
    p3.add_argument("--perf-tol", type=float, default=0.15, help="Max relative CPU/GPU score gap (default: 0.15).")
    p3.add_argument("--resolution", type=_parse_resolution, default="auto", help="'auto' or a Louvain resolution number.")
    p3.add_argument("--no-benchmarks", dest="use_benchmarks", action="store_false", help="Use legacy cpu_tier/RAM edges.")

    p4 = sub.add_parser("step4", help="Detect structural holes & export 3 core visualizations.")
    p4.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)

    ph = sub.add_parser(
        "handoff",
        help="Export the price-free TV5/TV8 feature table (no price, no segments).",
    )
    ph.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)

    pa = sub.add_parser(
        "audit",
        help="Print the review-claim reconciliation numbers without writing artifacts.",
    )
    pa.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)

    pall = sub.add_parser("run-all", help="Run Steps 1 -> 4 end-to-end.")
    pall.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    pall.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    pall.add_argument("--sample-size", type=int, default=None)
    pall.add_argument("--batch-size", type=int, default=25)
    pall.add_argument("--model", default="deepseek-chat")
    pall.add_argument("--max-spread", type=float, default=0.20)
    pall.add_argument("--price-tol", type=float, default=0.20, help="Max relative price gap (default: 0.20).")
    pall.add_argument("--perf-tol", type=float, default=0.15)
    pall.add_argument("--resolution", type=_parse_resolution, default="auto")
    pall.add_argument("--no-benchmarks", dest="use_benchmarks", action="store_false", help="Use legacy cpu_tier/RAM edges.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "step1":
        run_step1(
            input_path=args.input,
            output_path=args.output,
            csv_path=args.csv,
            cache_path=args.cache,
            export_csv=args.export_csv,
            sample_size=args.sample_size,
            batch_size=args.batch_size,
            model=args.model,
            dry_run=args.dry_run,
        )
    elif args.command in ("step1_5", "benchmarks", "step1-5"):
        run_step1_5(work_dir=args.work_dir, input_path=args.input)
    elif args.command == "step2":
        run_step2(input_path=args.input, work_dir=args.work_dir, max_spread=args.max_spread)
    elif args.command == "step3":
        run_step3(
            work_dir=args.work_dir,
            price_tol=args.price_tol,
            perf_tol=args.perf_tol,
            resolution=args.resolution,
            use_benchmarks=args.use_benchmarks,
        )
    elif args.command == "step4":
        run_step4(work_dir=args.work_dir)
    elif args.command == "handoff":
        export_price_free_handoff(work_dir=args.work_dir)
    elif args.command == "audit":
        audit_review_claims(work_dir=args.work_dir)
    elif args.command == "run-all":
        cleaned_path = run_step1(
            input_path=args.input,
            output_path=args.work_dir / "products_llm_cleaned.jsonl",
            csv_path=args.work_dir / "raw_products_export.csv",
            cache_path=args.work_dir / "llm_spec_cache.jsonl",
            export_csv=True,
            sample_size=args.sample_size,
            batch_size=args.batch_size,
            model=args.model,
        )
        run_step1_5(work_dir=args.work_dir, input_path=cleaned_path)
        run_step2(input_path=cleaned_path, work_dir=args.work_dir, max_spread=args.max_spread)
        run_step3(
            work_dir=args.work_dir,
            price_tol=args.price_tol,
            perf_tol=args.perf_tol,
            resolution=args.resolution,
            use_benchmarks=args.use_benchmarks,
        )
        run_step4(work_dir=args.work_dir)
        export_price_free_handoff(work_dir=args.work_dir)


if __name__ == "__main__":
    main()
