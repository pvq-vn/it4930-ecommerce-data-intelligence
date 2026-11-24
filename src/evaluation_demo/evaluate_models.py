import argparse
import csv
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
from sklearn.metrics import r2_score

from error_analysis import prediction_rows, test_rows_for_audit, write_error_tables
from model_loader import MODEL_FOLDERS, load_model, model_path
from prepare_test_data import prepare_tv5_splits


TABLE_PATH = (
    Path(__file__).resolve().parent
    / "outputs" / "tables" / "table_10_1_model_benchmark_3d.csv"
)


def accuracy_metrics(recorded_prices, predictions):
    errors = predictions - recorded_prices
    absolute_errors = abs(errors)
    # The TV5 price filters guarantee positive recorded prices.
    percentage_errors = 100 * absolute_errors / recorded_prices
    return {
        "mae_vnd": float(absolute_errors.mean()),
        "mdae_vnd": float(np.median(absolute_errors)),
        "rmse_vnd": float(np.sqrt(np.mean(errors ** 2))),
        "mape_pct": float(percentage_errors.mean()),
        "mdape_pct": float(np.median(percentage_errors)),
        "r2": float(r2_score(recorded_prices, predictions)),
    }


def mask_hardware(X_test):
    """Hide 20% of observed values in each of RAM and storage."""
    rng = np.random.default_rng(42)
    masked = X_test.copy()
    counts = {}
    for column in ("ram_gb", "storage_gb"):
        observed = X_test.index[X_test[column].notna()]
        selected = rng.choice(observed, size=round(len(observed) * 0.2), replace=False)
        masked.loc[selected, column] = np.nan
        counts[f"{column}_values_masked"] = len(selected)
    return masked, counts


def measure_latency(model, samples):
    """Measure individual predict calls on a model that has already predicted."""
    start = perf_counter()
    for sample in samples:
        model.predict(sample)
    return (perf_counter() - start) * 1000 / len(samples)


def evaluate_models(*, errors_only=False):
    results = []
    all_prediction_rows = []
    for category, split in prepare_tv5_splits().items():
        X_test = split.X_test
        recorded_prices = split.y_test.to_numpy()
        test_rows = test_rows_for_audit(split)
        if not errors_only:
            # Reuse identical missing values and timing samples for every model.
            masked_test, counts = mask_hardware(X_test)
            timing_positions = np.linspace(0, len(X_test) - 1, num=min(30, len(X_test)), dtype=int)
            timing_samples = [X_test.iloc[[position]] for position in timing_positions]
        for model_key in MODEL_FOLDERS:
            model = load_model(category, model_key)
            predictions = model.predict(X_test)
            all_prediction_rows.append(prediction_rows(test_rows, category, model_key, predictions))
            if errors_only:
                continue
            accuracy = accuracy_metrics(recorded_prices, predictions)
            latency = measure_latency(model, timing_samples)

            masked_predictions = model.predict(masked_test)
            masked_mae = float(abs(masked_predictions - recorded_prices).mean())
            mae_change = 100 * (masked_mae - accuracy["mae_vnd"]) / accuracy["mae_vnd"]
            results.append({
                "category": category,
                "model": model_key,
                "n_test": len(X_test),
                **accuracy,
                "latency_ms_per_sample": latency,
                "latency_n_samples": len(timing_samples),
                "model_size_mb": model_path(category, model_key).stat().st_size / 1_000_000,
                **counts,
                "masked_mae_vnd": masked_mae,
                "mae_change_pct": mae_change,
            })
    return results, pd.concat(all_prediction_rows, ignore_index=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--errors-only", action="store_true", help="Only write predictions and tables 10.3-10.7.")
    args = parser.parse_args()
    results, predictions = evaluate_models(errors_only=args.errors_only)
    TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_error_tables(predictions, TABLE_PATH.parent)
    print(f"\nDa ghi bang 10.3-10.7 va {len(predictions)} du doan tai: {TABLE_PATH.parent}")
    if args.errors_only:
        return

    try:
        with TABLE_PATH.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
    except PermissionError:
        if not TABLE_PATH.is_file():
            raise
        print(f"Khong ghi de duoc bang 10.1: {TABLE_PATH}. Dong tep neu dang mo va chay lai de cap nhat.")
    else:
        print(f"Da ghi bang 10.1: {TABLE_PATH}")

    print("\nLoai may / Mo hinh: MAE | Thoi gian suy luan | Dung luong | Thay doi MAE khi thieu thong so")
    for result in results:
        print(
            f"{result['category']} / {result['model']}: {result['mae_vnd']:,.0f} VND | "
            f"{result['latency_ms_per_sample']:.2f} ms | {result['model_size_mb']:.3f} MB | "
            f"{result['mae_change_pct']:+.2f}%"
        )


if __name__ == "__main__":
    main()
