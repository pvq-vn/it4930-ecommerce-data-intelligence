"""
================================================================================
IT4930 - E-commerce Data Intelligence
TV3: Exploratory Data Analysis (EDA) - Reproducibility Orchestrator
================================================================================
Kịch bản tự động tái lập độc lập 100% kết quả phân tích thống kê, bảng biểu Markdown,
và biểu đồ xuất bản 300 DPI phục vụ Phần 5 Báo cáo Tổng kết Học phần (EDA).

Sử dụng:
    python src/eda/scripts/reproduce_all.py
    python src/eda/scripts/reproduce_all.py --execute-notebooks
"""

import sys
import os
import time
import subprocess
import argparse
from pathlib import Path

# Thiết lập encoding UTF-8 cho stdout trên mọi nền tảng (đặc biệt Windows)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


MANDATORY_TABLES = [
    "table_1_1_source_category_counts.md",
    "table_1_1_source_category_percentages.md",
    "table_1_1_laptop_brand_share.md",
    "table_1_1_smartphone_brand_share.md",
    "table_1_1_seller_distribution.md",
    "table_1_2_price_summary_stats.md",
    "table_1_2_price_log_transform_comparison.md",
    "table_1_2_discount_rate_by_source.md",
    "table_1_3_overall_missingness.md",
    "table_1_3_missingness_by_category.md",
    "table_1_3_missingness_by_source.md",
    "table_1_3_candidate_features_missingness.md",
    "table_2_1_laptop_correlations.md",
    "table_2_1_smartphone_correlations.md",
    "table_2_1_laptop_ram_price.md",
    "table_2_1_laptop_storage_price.md",
    "table_2_1_laptop_cpu_tier_price.md",
    "table_2_1_laptop_gpu_type_price.md",
    "table_2_1_phone_ram_price.md",
    "table_2_1_phone_storage_price.md",
    "table_2_1_phone_display_price.md",
    "table_2_1_phone_brand_price.md",
    "table_2_1_hypothesis_tests.md",
    "table_2_2_pricing_drivers_comparison.md",
    "table_2_2_top_hardware_drivers.md",
    "table_2_2_pricing_structure_matrix.md",
    "table_3_1_price_invalid_records.md",
    "table_3_1_price_percentiles_boundaries.md",
    "table_3_1_price_extreme_outliers.md",
    "table_3_2_multicollinearity_vif.md",
    "table_3_2_cross_correlation_laptop.md",
    "table_3_2_cross_correlation_smartphone.md",
    "table_3_3_data_leakage_audit.md",
    "table_3_4_availability_status_stats.md",
    "table_3_4_availability_hypothesis_test.md",
    "table_1_1_overall_brand_share.md"
]

MANDATORY_FIGURES = [
    "fig_1_1_source_category_distribution.png",
    "fig_1_1_brand_market_share.png",
    "fig_1_1_seller_market_share.png",
    "fig_1_2_price_distribution_and_log_transform.png",
    "fig_1_2_discount_rate_by_source.png",
    "fig_1_3_overall_missingness_ranking.png",
    "fig_1_3_missingness_heatmap_by_source_category.png",
    "fig_1_3_hardware_missingness_laptop_vs_phone.png",
    "fig_2_1_hardware_correlation_heatmaps.png",
    "fig_2_1_hardware_price_relationships_laptop.png",
    "fig_2_1_hardware_price_relationships_smartphone.png",
    "fig_2_2_pricing_drivers_comparison.png",
    "fig_3_1_price_outliers_and_boundaries.png",
    "fig_3_2_multicollinearity_and_vif.png",
    "fig_3_3_availability_price_comparison.png"
]


def find_repo_root() -> Path:
    """Xác định thư mục gốc của repository chứa data/processed."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "data" / "processed" / "products_processed.jsonl").exists():
            return current
        current = current.parent
    cwd = Path.cwd().resolve()
    while cwd != cwd.parent:
        if (cwd / "data" / "processed" / "products_processed.jsonl").exists():
            return cwd
        cwd = cwd.parent
    raise FileNotFoundError("Không tìm thấy thư mục gốc repository chứa 'data/processed/products_processed.jsonl'!")


def run_command(cmd: list, cwd: Path, desc: str) -> bool:
    """Thực thi một lệnh CLI và hiển thị tiến độ thời gian thực."""
    print(f"\n[{time.strftime('%H:%M:%S')}] >>> {desc}...")
    start_time = time.time()
    env = os.environ.copy()
    scripts_path = str(cwd / "src" / "eda" / "scripts")
    env["PYTHONPATH"] = scripts_path + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            check=True,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = time.time() - start_time
        print(f"  [OK] Hoàn thành sau {elapsed:.2f}s")
        return True
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"  [LỖI] Thất bại sau {elapsed:.2f}s:")
        print(f"--- STDOUT ---\n{e.stdout}")
        print(f"--- STDERR ---\n{e.stderr}")
        return False


def verify_artifacts(repo_root: Path) -> dict:
    """Kiểm tra và kiểm toán tính đầy đủ, hợp lệ và nhất quán của toàn bộ artifacts."""
    tables_dir = repo_root / "src" / "eda" / "outputs" / "tables"
    figures_dir = repo_root / "src" / "eda" / "outputs" / "figures"

    missing_mandatory = []
    empty_files = []
    sanity_errors = []

    # 1. Kiểm tra tồn tại và kích thước các file bắt buộc
    for tbl_name in MANDATORY_TABLES:
        md_path = tables_dir / tbl_name
        csv_path = tables_dir / (Path(tbl_name).stem + ".csv")
        if not md_path.exists():
            missing_mandatory.append(f"tables/{tbl_name}")
        elif md_path.stat().st_size == 0:
            empty_files.append(f"tables/{tbl_name}")

        if not csv_path.exists():
            missing_mandatory.append(f"tables/{csv_path.name}")
        elif csv_path.stat().st_size == 0:
            empty_files.append(f"tables/{csv_path.name}")

    for fig_name in MANDATORY_FIGURES:
        fig_path = figures_dir / fig_name
        if not fig_path.exists():
            missing_mandatory.append(f"figures/{fig_name}")
        elif fig_path.stat().st_size == 0:
            empty_files.append(f"figures/{fig_name}")

    # 2. Sanity check nội dung dữ liệu tái lập
    if not missing_mandatory:
        # Kiểm tra tổng quan listing count
        try:
            with open(tables_dir / "table_1_1_source_category_counts.md", "r", encoding="utf-8") as f:
                c1_1 = f.read()
            if "10316" not in c1_1 and "10,316" not in c1_1:
                sanity_errors.append("Bảng 1.1 không khớp tổng số 10.316 bản ghi.")

            with open(tables_dir / "table_3_1_price_invalid_records.md", "r", encoding="utf-8") as f:
                c3_1 = f.read()
            if "1768" not in c3_1 and "1,768" not in c3_1:
                sanity_errors.append("Bảng 3.1A không khớp số lượng 1.768 bản ghi không hợp lệ.")

            with open(tables_dir / "table_3_2_multicollinearity_vif.md", "r", encoding="utf-8") as f:
                c3_2 = f.read()
            if "5.44" not in c3_2:
                sanity_errors.append("Bảng 3.2C không khớp chỉ số VIF = 5.44 của Smartphone RAM.")
        except Exception as e:
            sanity_errors.append(f"Lỗi kiểm toán nội dung bảng: {e}")

    md_tables = list(tables_dir.glob("*.md")) if tables_dir.exists() else []
    csv_tables = list(tables_dir.glob("*.csv")) if tables_dir.exists() else []
    png_figures = list(figures_dir.glob("*.png")) if figures_dir.exists() else []

    return {
        "md_count": len(md_tables),
        "csv_count": len(csv_tables),
        "fig_count": len(png_figures),
        "missing_mandatory": missing_mandatory,
        "empty_files": empty_files,
        "sanity_errors": sanity_errors,
        "tables_dir": str(tables_dir),
        "figures_dir": str(figures_dir),
    }


def execute_notebooks(repo_root: Path) -> bool:
    """Thực thi và lưu output cho toàn bộ 5 notebook trong src/eda/notebooks/."""
    try:
        import nbformat
        from nbclient import NotebookClient
    except ImportError:
        print("\n[!] Cảnh báo: Cần cài đặt 'nbformat' và 'nbclient' để chạy notebook:")
        print("    pip install nbformat nbclient")
        return False

    notebooks_dir = repo_root / "src" / "eda" / "notebooks"
    nb_files = sorted(notebooks_dir.glob("*.ipynb"))
    if not nb_files:
        print("  [!] Không tìm thấy notebook nào tại:", notebooks_dir)
        return False

    print(f"\n[+] Bắt đầu thực thi và lưu output cho {len(nb_files)} Jupyter Notebooks...")
    all_ok = True

    for nb_path in nb_files:
        print(f"  -> Đang thực thi {nb_path.name}...")
        t0 = time.time()
        try:
            with open(nb_path, "r", encoding="utf-8") as f:
                nb = nbformat.read(f, as_version=4)

            client = NotebookClient(
                nb,
                timeout=600,
                kernel_name="python3",
                resources={"metadata": {"path": str(repo_root)}}
            )
            client.execute()

            with open(nb_path, "w", encoding="utf-8") as f:
                nbformat.write(nb, f)

            print(f"     [OK] {nb_path.name} thành công sau {time.time() - t0:.2f}s")
        except Exception as ex:
            print(f"     [LỖI] {nb_path.name} thất bại: {ex}")
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Tái lập toàn bộ kết quả EDA dự án IT4930")
    parser.add_argument(
        "--execute-notebooks",
        action="store_true",
        help="Thực thi và nhúng output vào cả 5 file .ipynb"
    )
    args = parser.parse_args()

    repo_root = find_repo_root()
    print("=" * 80)
    print("IT4930 - TÁI LẬP KẾT QUẢ PHÂN TÍCH KHÁM PHÁ DỮ LIỆU (TV3 - EDA)")
    print(f"Thư mục gốc: {repo_root}")
    print(f"Thời điểm khởi chạy: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # 1. Kiểm tra file dữ liệu đầu vào
    data_file = repo_root / "data" / "processed" / "products_processed.jsonl"
    if not data_file.exists():
        print(f"[LỖI CHÍ MẠNG] Không tìm thấy dữ liệu: {data_file}")
        sys.exit(1)

    file_size_mb = data_file.stat().st_size / (1024 * 1024)
    print(f"[*] Dữ liệu đầu vào: {data_file.relative_to(repo_root)} ({file_size_mb:.2f} MB)")

    # 2. Danh sách các script thực thi nhiệm vụ
    scripts_to_run = [
        ("run_task_1_1.py", "Nhiệm vụ 1.1: Phân bố Sản phẩm, Thị phần Nguồn cào & Hãng"),
        ("run_task_1_2.py", "Nhiệm vụ 1.2: Phân tích Phân phối Giá & Mức độ Chiết khấu"),
        ("run_task_1_3.py", "Nhiệm vụ 1.3: Bức tranh Mức độ Thiếu Dữ liệu (Missingness)"),
        ("run_task_2_1.py", "Nhiệm vụ 2.1: Phân tích Tương quan Cấu hình Phần cứng - Giá bán"),
        ("run_task_2_2.py", "Nhiệm vụ 2.2: So sánh Đối đầu Laptop vs Smartphone & Quyết định Giá"),
        ("run_task_3.py",   "Nhiệm vụ 3.0: Kiểm toán Chất lượng Dữ liệu cho Hồi quy (VIF, Outliers)"),
    ]

    total_start = time.time()
    success_count = 0

    python_exe = sys.executable
    scripts_dir = repo_root / "src" / "eda" / "scripts"

    for script_name, description in scripts_to_run:
        script_path = scripts_dir / script_name
        if not script_path.exists():
            print(f"[!] Không tìm thấy script: {script_path}")
            continue

        cmd = [python_exe, str(script_path)]
        if run_command(cmd, cwd=repo_root, desc=description):
            success_count += 1
        else:
            print(f"[CẢNH BÁO] Script {script_name} kết thúc với mã lỗi!")

    # 3. Tùy chọn thực thi Notebooks
    nb_status = "Bỏ qua (Chạy nhanh với scripts)"
    nb_ok = True
    if args.execute_notebooks:
        nb_ok = execute_notebooks(repo_root)
        nb_status = "Thành công (100%)" if nb_ok else "Có lỗi trong notebook"

    # 4. Kiểm toán Artifacts
    artifacts = verify_artifacts(repo_root)
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 80)
    print("BẢNG TỔNG KẾT KIỂM TOÁN TÁI LẬP (REPRODUCIBILITY AUDIT REPORT)")
    print("=" * 80)
    print(f"1. Tổng số tác vụ EDA hoàn thành:      {success_count}/{len(scripts_to_run)}")
    print(f"2. Bảng biểu Markdown sinh ra (.md):    {artifacts['md_count']} bảng (Bắt buộc: {len(MANDATORY_TABLES)})")
    print(f"3. Bảng dữ liệu trích xuất (.csv):      {artifacts['csv_count']} file (Bắt buộc: {len(MANDATORY_TABLES)})")
    print(f"4. Biểu đồ xuất bản chuẩn 300 DPI:     {artifacts['fig_count']} hình ảnh (Bắt buộc: {len(MANDATORY_FIGURES)})")
    print(f"5. Thực thi Notebooks (.ipynb):         {nb_status}")
    print(f"6. Tổng thời gian tái lập toàn bộ:      {total_elapsed:.2f} giây")

    # Hiển thị chi tiết lỗi kiểm toán (nếu có)
    if artifacts["missing_mandatory"]:
        print(f"\n[!] Danh sách file bắt buộc bị thiếu ({len(artifacts['missing_mandatory'])}):")
        for m in artifacts["missing_mandatory"]:
            print(f"    - {m}")

    if artifacts["empty_files"]:
        print(f"\n[!] Danh sách file rỗng 0 bytes ({len(artifacts['empty_files'])}):")
        for e in artifacts["empty_files"]:
            print(f"    - {e}")

    if artifacts["sanity_errors"]:
        print(f"\n[!] Lỗi bất thường dữ liệu ({len(artifacts['sanity_errors'])}):")
        for s in artifacts["sanity_errors"]:
            print(f"    - {s}")

    print("=" * 80)

    # ĐIỀU KIỆN THOÁT NGHIÊM NGẶT (STRICT EXIT CONDITION)
    all_scripts_ok = (success_count == len(scripts_to_run))
    artifacts_ok = (len(artifacts["missing_mandatory"]) == 0) and (len(artifacts["empty_files"]) == 0) and (len(artifacts["sanity_errors"]) == 0)
    notebooks_ok = (not args.execute_notebooks) or (nb_ok is True)

    overall_success = all_scripts_ok and artifacts_ok and notebooks_ok

    if overall_success:
        print(">>> KẾT LUẬN: TOÀN BỘ KẾT QUẢ ĐÃ ĐƯỢC TÁI LẬP THÀNH CÔNG VÀ ĐỘC LẬP 100%! <<<")
    else:
        print(">>> KẾT LUẬN: QUÁ TRÌNH TÁI LẬP THẤT BẠI HOẶC CHƯA ĐẠT CHUẨN ĐẦU RA! <<<")
        if not all_scripts_ok:
            print(f"  - Chỉ có {success_count}/{len(scripts_to_run)} script chạy thành công.")
        if not artifacts_ok:
            print("  - Có file kết quả bắt buộc bị thiếu, rỗng hoặc số liệu không nhất quán.")
        if not notebooks_ok:
            print("  - Tồn tại lỗi trong quá trình thực thi Jupyter Notebooks.")
        sys.exit(1)


if __name__ == "__main__":
    main()
