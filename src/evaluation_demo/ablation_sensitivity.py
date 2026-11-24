"""Run TV8 feature ablation and TV7 sensitivity experiments on the frozen test split."""

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import Pipeline

from evaluate_models import accuracy_metrics
from model_loader import MODEL_FOLDERS, load_model, model_path
from prepare_test_data import DATA_COMMIT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot, use_tv5_modules
from tv3_features import TV3_NUM_FEATURES, TV3FeatureEngineer, add_tv3_inputs


OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
MODEL_DIR = OUTPUT_DIR / "models" / "s1_baseline"
TABLE_PATH = OUTPUT_DIR / "tables" / "table_10_2_ablation_and_tv7_sensitivity.csv"
SUMMARY_PATH = OUTPUT_DIR / "baseline_summary.md"
SEED = 42
TREE_COUNT = 200
WORKERS = 4
STAGE_MODULES = {
    "S2A": "compare_charger_features",
    "S3": "train_tv4",
    "S4": "train_tv6",
    "S5": "train_tv7_sensitivity",
}


def build_baseline_model(category, model_key):
    """Keep TV5's preprocessing and log target, with fixed estimator parameters."""
    use_tv5_modules()
    from config import (
        LAPTOP_CAT_FEATURES, LAPTOP_NUM_FEATURES,
        SMARTPHONE_CAT_FEATURES, SMARTPHONE_NUM_FEATURES,
    )
    from features import HardwareFeatureEngineer
    from training_baseline import build_ridge_pipeline
    from training_rf import build_rf_pipeline

    cat_features = LAPTOP_CAT_FEATURES if category == "laptop" else SMARTPHONE_CAT_FEATURES
    num_features = LAPTOP_NUM_FEATURES if category == "laptop" else SMARTPHONE_NUM_FEATURES
    if model_key == "ridge":
        return build_ridge_pipeline(category, num_features, cat_features)
    if model_key == "rf":
        return build_rf_pipeline(category, cat_features).set_params(
            regressor__model__n_estimators=TREE_COUNT,
            regressor__model__n_jobs=WORKERS,
        )
    if model_key == "lgbm":
        pipeline = Pipeline([
            ("features_engineer", HardwareFeatureEngineer(category, cat_dtype="category")),
            ("model", LGBMRegressor(
                n_estimators=TREE_COUNT,
                random_state=SEED,
                n_jobs=WORKERS,
                deterministic=True,
                force_col_wise=True,
                verbose=-1,
            )),
        ])
        return TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)
    raise ValueError(f"Unknown model: {model_key}")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_summary(results):
    lines = [
        "# Mốc cơ sở trước khi thêm đặc trưng",
        "",
        f"Dữ liệu được đọc từ commit `{DATA_COMMIT}` và chia bằng chính mã của TV5.",
        "Laptop có 3.227 dòng train và 819 dòng test. Smartphone có 3.300 dòng train và 797 dòng test.",
        "Toàn bộ bước điền thông số thiếu, mã hóa và huấn luyện chỉ fit trên tập train.",
        "",
        "Ridge dùng alpha=1.0. Random Forest dùng 200 cây và random_state=42.",
        "LightGBM dùng 200 cây, learning_rate=0.1, num_leaves=31 và random_state=42.",
        "Các tham số khác giữ mặc định của thư viện. Hai thuật toán cây dùng tối đa 4 luồng.",
        "Bộ tham số này được chọn trước khi xem điểm test và sẽ được giữ cố định khi thêm đặc trưng.",
        "",
        "TV5 đã tìm tham số cho Random Forest và LightGBM bằng cross-validation trên tập train.",
        "Ridge của TV5 vốn dùng alpha=1.0, giống bản cơ sở này.",
        "Random Forest TV5 cũng có 200 cây, nhưng max_features=0.5; bản cơ sở dùng max_features=1.0.",
        "LightGBM TV5 có 400 cây và các tham số đã tối ưu khác với bản cơ sở 200 cây.",
        "Cột thay đổi MAE tính theo (MAE cơ sở / MAE TV5 - 1) × 100. Số âm nghĩa là sai số giảm.",
        "",
        "| Loại máy | Mô hình | MAE TV5 (VNĐ) | MAE cơ sở (VNĐ) | Thay đổi MAE | RMSE cơ sở (VNĐ) | R² cơ sở |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['category']} | {row['model']} | {row['tv5_mae_vnd']:,.0f} | "
            f"{row['mae_vnd']:,.0f} | {row['mae_change_vs_tv5_pct']:+.2f}% | "
            f"{row['rmse_vnd']:,.0f} | {row['r2']:.4f} |"
        )
    lines.extend([
        "",
        "Điểm TV5 trong bảng được tính lại từ sáu mô hình đã bàn giao trên cùng tập test.",
        "So sánh này phản ánh thay đổi cấu hình huấn luyện. Các thí nghiệm bổ sung đặc trưng sẽ lấy S1 làm mốc.",
        "Báo cáo này mô tả riêng S1 với các đặc trưng TV5. So sánh S2 được lưu riêng ở `tv3_stage_summary.md` khi chạy.",
        "",
        "Chạy lại từ môi trường Python có đủ thư viện bằng `python src/evaluation_demo/ablation_sensitivity.py`.",
        "Chi tiết phiên bản thư viện, mã băm dữ liệu và tham số được ghi trong `models/s1_baseline/manifest.json`.",
    ])
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage_results(stage, results):
    """Replace only this stage, preserving results from other stages."""
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_rows = pd.DataFrame(results)
    if TABLE_PATH.exists():
        old_rows = pd.read_csv(TABLE_PATH)
        new_rows = pd.concat([old_rows.loc[old_rows["stage"].ne(stage)], new_rows], ignore_index=True)
    new_rows.sort_values(["stage", "category", "model"]).to_csv(
        TABLE_PATH, index=False, encoding="utf-8-sig",
    )


def train_s1():
    splits = prepare_tv5_splits()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "stage": "S1",
        "data_commit": DATA_COMMIT,
        "python": platform.python_version(),
        "libraries": {name: version(name) for name in (
            "numpy", "pandas", "scikit-learn", "lightgbm", "joblib", "scipy",
        )},
        "data_sha256": {name: hashlib.sha256(read_snapshot(name)).hexdigest() for name in (
            "products_cleaned.jsonl", "products_processed.jsonl",
        )},
        "tv5_code_sha256": {name: file_hash(TV5_MODELS_DIR / name) for name in (
            "config.py", "features.py", "utils.py", "training_baseline.py", "training_rf.py",
        )},
        "models": [],
    }
    results = []
    for category, split in splits.items():
        recorded_prices = split.y_test.to_numpy()
        for model_key in MODEL_FOLDERS:
            print(f"Training {category} / {model_key} ...", flush=True)
            baseline = build_baseline_model(category, model_key)
            start = perf_counter()
            baseline.fit(split.X_train, split.y_train)
            train_seconds = perf_counter() - start
            baseline_predictions = baseline.predict(split.X_test)
            metrics = accuracy_metrics(recorded_prices, baseline_predictions)

            tv5 = load_model(category, model_key)
            tv5_predictions = tv5.predict(split.X_test)
            tv5_metrics = accuracy_metrics(recorded_prices, tv5_predictions)
            filename = f"{model_key}_{category}.pkl"
            destination = MODEL_DIR / filename
            joblib.dump(baseline, destination, compress=3)

            results.append({
                "stage": "S1",
                "category": category,
                "model": model_key,
                "data_commit": DATA_COMMIT,
                "n_train": len(split.X_train),
                "n_test": len(split.X_test),
                **metrics,
                **{f"tv5_{key}": value for key, value in tv5_metrics.items()},
                "mae_change_vs_tv5_pct": 100 * (metrics["mae_vnd"] / tv5_metrics["mae_vnd"] - 1),
                "rmse_change_vs_tv5_pct": 100 * (metrics["rmse_vnd"] / tv5_metrics["rmse_vnd"] - 1),
                "r2_change_vs_tv5": metrics["r2"] - tv5_metrics["r2"],
                "train_seconds": train_seconds,
            })
            manifest["models"].append({
                "category": category,
                "model": model_key,
                "file": filename,
                "sha256": file_hash(destination),
                "tv5_model_sha256": file_hash(model_path(category, model_key)),
                "fixed_estimator_params": baseline.regressor_.named_steps["model"].get_params(),
                "tv5_estimator_params": tv5.regressor_.named_steps["model"].get_params(),
                "train_index_sha256": hashlib.sha256(split.X_train.index.to_numpy().tobytes()).hexdigest(),
                "test_ids_sha256": hashlib.sha256("\n".join(split.test_metadata["listing_record_id"]).encode()).hexdigest(),
            })
            print(
                f"MAE S1={metrics['mae_vnd']:,.0f}; TV5={tv5_metrics['mae_vnd']:,.0f} VND; "
                f"training={train_seconds:.2f}s", flush=True,
            )
            del baseline, tv5

    write_stage_results("S1", results)
    (MODEL_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    save_summary(results)
    print(f"Saved six S1 models to {MODEL_DIR}")
    print(f"Results: {TABLE_PATH}")
    print(f"Summary: {SUMMARY_PATH}")


def build_tv3_model(category, model_key):
    model = build_baseline_model(category, model_key)
    model.set_params(regressor__features_engineer=TV3FeatureEngineer(
        category, "category" if model_key == "lgbm" else "str",
    ))
    if model_key == "ridge":
        preprocessor = model.regressor.named_steps["preprocessor"]
        preprocessor.transformers = [
            (name, transformer, list(columns) + TV3_NUM_FEATURES if name == "num" else columns)
            for name, transformer, columns in preprocessor.transformers
        ]
    return model


def input_coverage(category, partition, X):
    charger = TV3FeatureEngineer._charger(X)
    return {
        "category": category, "partition": partition, "n_rows": len(X),
        "out_of_stock": int(X["availability_status"].eq("out_of_stock").sum()),
        "in_stock": int(X["availability_status"].eq("in_stock").sum()),
        "stock_unknown": int((~X["availability_status"].isin(["out_of_stock", "in_stock"])).sum()),
        "charger_observed": int(charger.notna().sum()),
        "charger_missing_pct": 100 * float(charger.isna().mean()),
        "screen_300_replaced": int(pd.to_numeric(X["screen_size_inch"], errors="coerce").eq(300).sum()),
    }


def save_tv3_summary(results, coverage):
    lines = [
        "# S2: Kiểm tra gói đặc trưng TV3",
        "",
        f"Dữ liệu vẫn ở commit `{DATA_COMMIT}`. Giữ nguyên toàn bộ dòng train/test và tham số mô hình của S1.",
        "S2 bổ sung `is_out_of_stock`, `charger_watt`, `is_charger_missing` cho cả ba thuật toán.",
        "`is_out_of_stock=1` khi trạng thái là out_of_stock; 0 nghĩa là không được đánh dấu hết hàng (có thể unknown).",
        "Sạc thiếu/không dương được điền bằng trung vị cùng hãng trên train, sau đó trung vị toàn train nếu hãng không có dữ liệu.",
        "Nếu toàn train không có công suất sạc hợp lệ thì dùng 0 và giữ cờ thiếu bằng 1.",
        "Giá trị màn hình đúng bằng 300 inch được đổi thành thiếu ở cả train/test, rồi điền theo cách của TV5, chỉ fit trên train.",
        "Không xóa dòng test. Không tối ưu lại alpha hoặc tham số cây trong thí nghiệm này.",
        "",
        "| Loại máy | Mô hình | MAE S1 (VNĐ) | MAE S2 (VNĐ) | Thay đổi MAE | RMSE S2 (VNĐ) | R² S2 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            f"| {row['category']} | {row['model']} | {row['s1_mae_vnd']:,.0f} | {row['mae_vnd']:,.0f} | "
            f"{row['mae_change_vs_s1_pct']:+.2f}% | {row['rmse_vnd']:,.0f} | {row['r2']:.4f} |"
        )
    lines.extend([
        "", "Số âm ở cột thay đổi MAE nghĩa là sai số giảm so với S1.",
        "Đây là tác động của cả gói S2; chưa tách riêng tác động của tồn kho, sạc và sửa màn hình.",
        "Kết quả trên một phép chia dữ liệu chưa phải bằng chứng về độ cải thiện ổn định hay quan hệ nhân quả.",
        "", "| Loại máy | Tập | Số dòng | Có sạc | Thiếu sạc | Hết hàng | Còn hàng | Tồn kho unknown | Screen=300 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in coverage:
        lines.append(
            f"| {row['category']} | {row['partition']} | {row['n_rows']} | {row['charger_observed']} | "
            f"{row['charger_missing_pct']:.2f}% | {row['out_of_stock']} | {row['in_stock']} | "
            f"{row['stock_unknown']} | {row['screen_300_replaced']} |"
        )
    lines.extend([
        "", "Chạy bằng `python src/evaluation_demo/ablation_sensitivity.py --stage S2`.",
        "Sáu mô hình và thông tin truy nguyên nằm trong `models/s2_tv3/`.",
        "Dự đoán từng dòng được lưu ở `s2_test_predictions.csv`; độ phủ trường mới ở `tables/s2_input_coverage.csv`.",
        "Các bước TV4, TV6 và TV7 chưa được chạy trong S2.",
    ])
    (OUTPUT_DIR / "tv3_stage_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def train_s2():
    s1_manifest = json.loads((MODEL_DIR / "manifest.json").read_text(encoding="utf-8"))
    s1_rows = pd.read_csv(TABLE_PATH).query("stage == 'S1'")
    if len(s1_rows) != 6 or s1_rows.duplicated(["category", "model"]).any():
        raise ValueError("Expected exactly six unique S1 results before training S2.")
    if s1_manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("S1 uses a different data commit.")
    for name, expected in s1_manifest["libraries"].items():
        if version(name) != expected:
            raise ValueError(f"Library version differs from S1: {name}.")
    for name, expected in s1_manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(name)).hexdigest() != expected:
            raise ValueError(f"Data differs from S1: {name}.")
    for name, expected in s1_manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / name) != expected:
            raise ValueError(f"TV5 code differs from S1: {name}.")

    destination_dir = OUTPUT_DIR / "models" / "s2_tv3"
    destination_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "stage": "S2", "data_commit": DATA_COMMIT,
        "libraries": s1_manifest["libraries"], "data_sha256": s1_manifest["data_sha256"],
        "tv5_code_sha256": s1_manifest["tv5_code_sha256"],
        "s1_manifest_sha256": file_hash(MODEL_DIR / "manifest.json"),
        "tv8_code_sha256": {name: file_hash(Path(__file__).parent / name) for name in (
            "ablation_sensitivity.py", "prepare_test_data.py", "tv3_features.py",
        )},
        "added_features": TV3_NUM_FEATURES,
        "screen_policy": "Replace exactly 300 inch with missing; impute from train; preserve all rows.",
        "models": [],
    }
    results, coverage, predictions = [], [], []
    for category, split in prepare_tv5_splits().items():
        X_train, X_test = add_tv3_inputs(split)
        coverage.extend([
            input_coverage(category, "train", X_train), input_coverage(category, "test", X_test),
        ])
        for model_key in MODEL_FOLDERS:
            reference = next(row for row in s1_manifest["models"] if (
                row["category"] == category and row["model"] == model_key
            ))
            if hashlib.sha256(split.X_train.index.to_numpy().tobytes()).hexdigest() != reference["train_index_sha256"]:
                raise ValueError("Train rows differ from S1.")
            if hashlib.sha256("\n".join(split.test_metadata["listing_record_id"]).encode()).hexdigest() != reference["test_ids_sha256"]:
                raise ValueError("Test rows differ from S1.")
            s1_path = MODEL_DIR / reference["file"]
            if file_hash(s1_path) != reference["sha256"]:
                raise ValueError("Saved S1 model changed.")
            baseline = joblib.load(s1_path)
            s1_predictions = baseline.predict(split.X_test)
            s1_metrics = accuracy_metrics(split.y_test.to_numpy(), s1_predictions)
            expected = s1_rows.query("category == @category and model == @model_key").iloc[0]
            if not all(np.isclose(value, expected[key], rtol=1e-8, atol=1e-6) for key, value in s1_metrics.items()):
                raise ValueError("Saved S1 model no longer reproduces S1 metrics.")

            model = build_tv3_model(category, model_key)
            if model.regressor.named_steps["model"].get_params() != reference["fixed_estimator_params"]:
                raise ValueError("S2 estimator parameters differ from S1.")
            print(f"Training S2 {category} / {model_key} ...", flush=True)
            start = perf_counter()
            model.fit(X_train, split.y_train)
            train_seconds = perf_counter() - start
            prediction = model.predict(X_test)
            metrics = accuracy_metrics(split.y_test.to_numpy(), prediction)
            change = 100 * (metrics["mae_vnd"] / s1_metrics["mae_vnd"] - 1)
            results.append({
                "stage": "S2", "category": category, "model": model_key, "data_commit": DATA_COMMIT,
                "n_train": len(X_train), "n_test": len(X_test), **metrics,
                **{f"s1_{key}": value for key, value in s1_metrics.items()},
                "mae_change_vs_s1_pct": change,
                "rmse_change_vs_s1_pct": 100 * (metrics["rmse_vnd"] / s1_metrics["rmse_vnd"] - 1),
                "r2_change_vs_s1": metrics["r2"] - s1_metrics["r2"], "train_seconds": train_seconds,
            })
            audit = split.test_metadata.copy()
            audit["category"], audit["model"] = category, model_key
            audit["actual_price"] = split.y_test
            audit["s1_predicted_price"], audit["s2_predicted_price"] = s1_predictions, prediction
            predictions.append(audit)
            destination = destination_dir / reference["file"]
            joblib.dump(model, destination, compress=3)
            engineer = model.regressor_.named_steps["features_engineer"]
            manifest["models"].append({
                "category": category, "model": model_key, "file": destination.name,
                "sha256": file_hash(destination), "s1_model_sha256": file_hash(s1_path),
                "fixed_estimator_params": model.regressor_.named_steps["model"].get_params(),
                "train_index_sha256": reference["train_index_sha256"], "test_ids_sha256": reference["test_ids_sha256"],
                "charger_by_brand": engineer.charger_by_brand_, "charger_global": engineer.charger_global_,
            })
            print(f"MAE S1={s1_metrics['mae_vnd']:,.0f}; S2={metrics['mae_vnd']:,.0f} VND ({change:+.2f}%)", flush=True)

    write_stage_results("S2", results)
    (destination_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(coverage).to_csv(OUTPUT_DIR / "tables" / "s2_input_coverage.csv", index=False, encoding="utf-8-sig")
    pd.concat(predictions, ignore_index=True).to_csv(OUTPUT_DIR / "s2_test_predictions.csv", index=False, encoding="utf-8-sig")
    save_tv3_summary(results, coverage)
    save_summary(s1_rows.to_dict("records"))
    print(f"Saved six S2 models to {destination_dir}")
    print(f"Results: {TABLE_PATH}")
    print(f"Summary: {OUTPUT_DIR / 'tv3_stage_summary.md'}")


def render_ablation_figure():
    """Use the same Windows renderer as the standalone Figure 10.3 command."""
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        raise SystemExit("Figure 10.3 uses Windows PowerShell. The experiment tables can be generated separately.")
    script = Path(__file__).with_name("plot_ablation.ps1")
    subprocess.run([powershell, "-NoProfile", "-File", str(script)], check=True)


def run_stage(stage):
    if stage == "S1":
        train_s1()
    elif stage == "S2":
        train_s2()
    elif stage == "plot":
        render_ablation_figure()
    else:
        import_module(STAGE_MODULES[stage]).main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    stages = ("S1", "S2", *STAGE_MODULES, "plot")
    parser.add_argument(
        "--stage", choices=(*stages, "all"), default="S1",
        help="S5 runs S5a and S5b. all runs S1 through S5 and then draws Figure 10.3 (Windows).",
    )
    args = parser.parse_args()
    for stage in stages if args.stage == "all" else (args.stage,):
        run_stage(stage)


if __name__ == "__main__":
    main()
