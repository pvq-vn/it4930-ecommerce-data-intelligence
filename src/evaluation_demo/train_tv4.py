"""Compare the price-free TV4 package with the S2A baseline for all six models."""

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from ablation_sensitivity import OUTPUT_DIR, TABLE_PATH, file_hash, write_stage_results
from compare_charger_features import COMPARISON_PATH, S2_MODEL_DIR, build_stock_model
from evaluate_models import accuracy_metrics
from prepare_test_data import DATA_COMMIT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot
from tv4_features import (
    BENCHMARK_COLUMNS, SELLER_COUNT, TV4_ARTIFACT_COMMIT, TV4FeatureEngineer,
    add_tv4_inputs, load_tv4_benchmarks,
)


S3_MODEL_DIR = OUTPUT_DIR / "models" / "s3_tv4"


def build_tv4_model(stock_model, category, model_key):
    """Keep S2A's estimator and add TV4 inputs to its preprocessing."""
    model = clone(stock_model)
    model.set_params(regressor__features_engineer=TV4FeatureEngineer(
        category, "category" if model_key == "lgbm" else "str",
    ))
    if model_key == "ridge":
        preprocessor = model.regressor.named_steps["preprocessor"]
        numeric, categorical = preprocessor.transformers
        name, scaler, columns = numeric
        preprocessor.transformers = [
            (name, scaler, [*columns, *BENCHMARK_COLUMNS[category], SELLER_COUNT]),
            categorical,
        ]
    return model


def split_fingerprints(split):
    train = split.X_train.index.to_numpy().tobytes()
    test = "\n".join(split.test_metadata["listing_record_id"]).encode()
    return {
        "train_index_sha256": hashlib.sha256(train).hexdigest(),
        "test_ids_sha256": hashlib.sha256(test).hexdigest(),
    }


def main():
    reference_path = S2_MODEL_DIR / "manifest.json"
    reference_manifest = json.loads(reference_path.read_text(encoding="utf-8"))
    if reference_manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("S2 uses a different data snapshot.")
    for filename, expected in reference_manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(filename)).hexdigest() != expected:
            raise ValueError(f"Data differs from S2: {filename}")
    for filename, expected in reference_manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / filename) != expected:
            raise ValueError(f"TV5 code differs from S2: {filename}")

    stock_scores = pd.read_csv(COMPARISON_PATH).query("test_subset == 'all'")
    stock_scores = stock_scores.set_index(["category", "model"])
    if not stock_scores.index.is_unique:
        raise ValueError("S2A has duplicate results for a category and model.")
    manifest = {
        "stage": "S3", "baseline_stage": "S2A", "data_commit": DATA_COMMIT,
        "benchmark_commit": TV4_ARTIFACT_COMMIT, "benchmark_sha256": {},
        "data_sha256": reference_manifest["data_sha256"],
        "tv5_code_sha256": reference_manifest["tv5_code_sha256"],
        "python": platform.python_version(),
        "libraries": {name: version(name) for name in reference_manifest["libraries"]},
        "reference_manifest_sha256": file_hash(reference_path),
        "stock_comparison_sha256": file_hash(COMPARISON_PATH),
        "tv8_code_sha256": {name: file_hash(Path(__file__).with_name(name)) for name in (
            "train_tv4.py", "tv4_features.py", "tv3_features.py", "compare_charger_features.py",
            "prepare_test_data.py", "error_analysis.py",
        )},
        "benchmark_columns": BENCHMARK_COLUMNS,
        "benchmark_missing": "Median of the observed scores in the category's train partition.",
        "seller_count": "Known query seller plus distinct other sellers with the exact raw configuration in train. Zero if the key or query seller is missing.",
        "coverage": {}, "models": [],
    }
    results = []
    S3_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for category, split in prepare_tv5_splits().items():
        benchmark_scores, digest = load_tv4_benchmarks(category)
        manifest["benchmark_sha256"][category] = digest
        X_train, X_test = add_tv4_inputs(split, benchmark_scores)
        columns = BENCHMARK_COLUMNS[category]
        manifest["coverage"][category] = {
            partition: {"n_rows": len(X), "benchmark_observed": X[columns].count().to_dict()}
            for partition, X in (("train", X_train), ("test", X_test))
        }
        fingerprints = split_fingerprints(split)
        actual = split.y_test.to_numpy()
        references = [row for row in reference_manifest["models"] if row["category"] == category]
        if sorted(row["model"] for row in references) != ["lgbm", "rf", "ridge"]:
            raise ValueError(f"Expected three unique S2 models for {category}.")

        for reference in references:
            model_key = reference["model"]
            if any(reference[field] != value for field, value in fingerprints.items()):
                raise ValueError(f"Train/test rows differ from S2: {category}")
            old_path = S2_MODEL_DIR / reference["file"]
            if file_hash(old_path) != reference["sha256"]:
                raise ValueError(f"S2 model artifact changed: {old_path}")

            stock_model = build_stock_model(joblib.load(old_path), model_key)
            stock_model.fit(X_train.drop(columns=columns), split.y_train)
            stock = accuracy_metrics(actual, stock_model.predict(X_test.drop(columns=columns)))
            prior = stock_scores.loc[category, model_key]
            for key, value in stock.items():
                if not np.isclose(value, prior[f"without_charger_{key}"], rtol=1e-8, atol=1e-6):
                    raise ValueError(f"Cannot reproduce S2A {key}: {category}/{model_key}")

            model = build_tv4_model(stock_model, category, model_key)
            if model.regressor.named_steps["model"].get_params() != reference["fixed_estimator_params"]:
                raise ValueError(f"S3 estimator parameters differ from S2: {category}/{model_key}")
            start = perf_counter()
            model.fit(X_train, split.y_train)
            train_seconds = perf_counter() - start
            metrics = accuracy_metrics(actual, model.predict(X_test))
            delta = metrics["mae_vnd"] - stock["mae_vnd"]
            change = 100 * delta / stock["mae_vnd"]
            results.append({
                "stage": "S3", "baseline_stage": "S2A", "category": category, "model": model_key,
                "data_commit": DATA_COMMIT, "n_train": len(X_train), "n_test": len(X_test), **metrics,
                **{f"s2a_{key}": value for key, value in stock.items()},
                "mae_delta_vs_s2a_vnd": delta, "mae_change_vs_s2a_pct": change,
                "train_seconds": train_seconds,
            })

            destination = S3_MODEL_DIR / reference["file"]
            joblib.dump(model, destination, compress=3)
            engineer = model.regressor_.named_steps["features_engineer"]
            for partition, X in (("train", X_train), ("test", X_test)):
                counts = engineer.store_counts(X)
                manifest["coverage"][category][partition][SELLER_COUNT] = {
                    str(count): int(n_rows) for count, n_rows in counts.value_counts().sort_index().items()
                }
            manifest["models"].append({
                "category": category, "model": model_key, "file": destination.name,
                "sha256": file_hash(destination), **fingerprints,
                "fixed_estimator_params": reference["fixed_estimator_params"],
                "benchmark_medians": engineer.benchmark_medians_.to_dict(),
            })
            print(
                f"{category}/{model_key}: S2A MAE={stock['mae_vnd']:,.0f}, "
                f"S3 MAE={metrics['mae_vnd']:,.0f} VND ({change:+.2f}%)",
                flush=True,
            )

    (S3_MODEL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_stage_results("S3", results)
    print(f"Results: {TABLE_PATH}")
    print(f"Models and input coverage: {S3_MODEL_DIR}")


if __name__ == "__main__":
    main()
