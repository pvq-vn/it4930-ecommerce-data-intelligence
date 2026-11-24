"""Compare S3 with review counts and the full TV6 review package on the same split."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from ablation_sensitivity import OUTPUT_DIR, TABLE_PATH, file_hash, write_stage_results
from evaluate_models import accuracy_metrics
from prepare_test_data import DATA_COMMIT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot
from train_tv4 import S3_MODEL_DIR, split_fingerprints
from tv4_features import add_tv4_inputs, load_tv4_benchmarks
from tv6_features import (
    BRAND_PRIOR, COUNT_COLUMNS, PARENT_KEY, SENTIMENT_COLUMNS, TV6_COMMIT,
    TV6FeatureEngineer, add_tv6_inputs, load_tv6_reviews,
)


S4_MODEL_DIR = OUTPUT_DIR / "models" / "s4_tv6"
S4_GROUP_TABLE = TABLE_PATH.with_name("s4_review_comparison.csv")


def build_review_model(s3_model, category, model_key, include_sentiment):
    model = clone(s3_model)
    model.set_params(regressor__features_engineer=TV6FeatureEngineer(
        category, "category" if model_key == "lgbm" else "str", include_sentiment,
    ))
    if model_key == "ridge":
        preprocessor = model.regressor.named_steps["preprocessor"]
        numeric, categorical = preprocessor.transformers
        name, scaler, columns = numeric
        added = COUNT_COLUMNS + (SENTIMENT_COLUMNS + [BRAND_PRIOR] if include_sentiment else [])
        preprocessor.transformers = [(name, scaler, [*columns, *added]), categorical]
    return model


def review_group_scores(actual, predictions, has_review):
    for group, mask in (
        ("all", np.ones(len(actual), dtype=bool)),
        ("with_review", has_review),
        ("without_review", ~has_review),
    ):
        if not mask.any():
            continue
        yield group, int(mask.sum()), {
            variant: accuracy_metrics(actual[mask], guess[mask])
            for variant, guess in predictions.items()
        }


def main():
    reference_path = S3_MODEL_DIR / "manifest.json"
    s3_manifest = json.loads(reference_path.read_text(encoding="utf-8"))
    if s3_manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("S3 uses a different data snapshot.")
    for filename, expected in s3_manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(filename)).hexdigest() != expected:
            raise ValueError(f"Data differs from S3: {filename}")
    for filename, expected in s3_manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / filename) != expected:
            raise ValueError(f"TV5 code differs from S3: {filename}")

    s3_scores = pd.read_csv(TABLE_PATH).query("stage == 'S3'").set_index(["category", "model"])
    if len(s3_scores) != 6 or not s3_scores.index.is_unique:
        raise ValueError("Expected six unique S3 results.")
    reviews, review_hash = load_tv6_reviews()
    manifest = {
        "stage": "S4", "baseline_stage": "S3", "data_commit": DATA_COMMIT,
        "data_sha256": s3_manifest["data_sha256"], "tv5_code_sha256": s3_manifest["tv5_code_sha256"],
        "benchmark_sha256": s3_manifest["benchmark_sha256"],
        "s3_manifest_sha256": file_hash(reference_path),
        "libraries": {name: version(name) for name in s3_manifest["libraries"]},
        "review_commit": TV6_COMMIT, "review_sha256": review_hash,
        "code_sha256": {name: file_hash(Path(__file__).with_name(name)) for name in (
            "train_tv6.py", "tv6_features.py", "tv4_features.py", "tv3_features.py", "prepare_test_data.py",
        )},
        "count_features": COUNT_COLUMNS,
        "sentiment_features": [*SENTIMENT_COLUMNS, BRAND_PRIOR],
        "prior_policy": "Train-only mean of reviewed parents per brand/category, excluding the queried parent. Fallback to the category train mean, then zero.",
        "coverage": {}, "models": [],
    }
    stage_rows, group_rows = [], []
    S4_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for category, split in prepare_tv5_splits().items():
        benchmarks, digest = load_tv4_benchmarks(category)
        if digest != manifest["benchmark_sha256"][category]:
            raise ValueError(f"TV4 input differs from S3: {category}")
        base_train, base_test = add_tv4_inputs(split, benchmarks)
        full_train = add_tv6_inputs(base_train, split.train_metadata, reviews, category)
        full_test = add_tv6_inputs(base_test, split.test_metadata, reviews, category)
        count_train = full_train.drop(columns=[PARENT_KEY, *SENTIMENT_COLUMNS])
        count_test = full_test.drop(columns=[PARENT_KEY, *SENTIMENT_COLUMNS])
        has_review = full_test["has_review_data"].eq(1).to_numpy()
        manifest["coverage"][category] = {
            partition: {"n_rows": len(X), "n_reviewed": int(X["has_review_data"].sum())}
            for partition, X in (("train", full_train), ("test", full_test))
        }
        fingerprints = split_fingerprints(split)
        actual = split.y_test.to_numpy()
        references = [row for row in s3_manifest["models"] if row["category"] == category]
        if sorted(row["model"] for row in references) != ["lgbm", "rf", "ridge"]:
            raise ValueError(f"Expected three unique S3 models for {category}.")
        for reference in references:
            model_key = reference["model"]
            if any(reference[field] != value for field, value in fingerprints.items()):
                raise ValueError(f"Train/test rows differ from S3: {category}")
            old_path = S3_MODEL_DIR / reference["file"]
            if file_hash(old_path) != reference["sha256"]:
                raise ValueError(f"S3 model artifact changed: {old_path}")
            s3_model = joblib.load(old_path)
            predictions = {"s3": s3_model.predict(base_test)}
            baseline = accuracy_metrics(actual, predictions["s3"])
            prior = s3_scores.loc[category, model_key]
            if not all(np.isclose(value, prior[metric], rtol=1e-8, atol=1e-6) for metric, value in baseline.items()):
                raise ValueError(f"Cannot reproduce S3 scores: {category}/{model_key}")

            count_model = build_review_model(s3_model, category, model_key, include_sentiment=False)
            full_model = build_review_model(s3_model, category, model_key, include_sentiment=True)
            count_model.fit(count_train, split.y_train)
            predictions["count"] = count_model.predict(count_test)
            start = perf_counter()
            full_model.fit(full_train, split.y_train)
            train_seconds = perf_counter() - start
            predictions["s4"] = full_model.predict(full_test)
            for variant, model in (("count", count_model), ("s4", full_model)):
                if model.regressor_.named_steps["model"].get_params() != reference["fixed_estimator_params"]:
                    raise ValueError(f"Estimator parameters changed for {variant}: {category}/{model_key}")

            for group, n_test, metrics in review_group_scores(actual, predictions, has_review):
                s3, count, s4 = metrics["s3"], metrics["count"], metrics["s4"]
                group_row = {
                    "category": category, "model": model_key, "test_group": group, "n_test": n_test,
                    **{f"{variant}_{key}": value for variant, values in metrics.items() for key, value in values.items()},
                    "count_change_vs_s3_pct": 100 * (count["mae_vnd"] / s3["mae_vnd"] - 1),
                    "s4_change_vs_count_pct": 100 * (s4["mae_vnd"] / count["mae_vnd"] - 1),
                    "s4_change_vs_s3_pct": 100 * (s4["mae_vnd"] / s3["mae_vnd"] - 1),
                }
                group_rows.append(group_row)
                if group == "all":
                    stage_rows.append({
                        "stage": "S4", "baseline_stage": "S3", "data_commit": DATA_COMMIT,
                        **{key: value for key, value in group_row.items() if key != "test_group"},
                        "n_train": len(full_train), **s4,
                        "train_seconds": train_seconds,
                    })
                    print(
                        f"{category}/{model_key} MAE: S3={s3['mae_vnd']:,.0f}, "
                        f"counts={count['mae_vnd']:,.0f}, S4={s4['mae_vnd']:,.0f} VND "
                        f"({group_row['s4_change_vs_s3_pct']:+.2f}% vs S3)", flush=True,
                    )

            destination = S4_MODEL_DIR / reference["file"]
            joblib.dump(full_model, destination, compress=3)
            manifest["models"].append({
                "category": category, "model": model_key, "file": destination.name,
                "sha256": file_hash(destination), **fingerprints,
                "fixed_estimator_params": reference["fixed_estimator_params"],
            })

    (S4_MODEL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(group_rows).to_csv(S4_GROUP_TABLE, index=False, encoding="utf-8-sig")
    write_stage_results("S4", stage_rows)
    print(f"Results: {TABLE_PATH}")
    print(f"Review subgroups: {S4_GROUP_TABLE}")
    print(f"Saved models: {S4_MODEL_DIR}")


if __name__ == "__main__":
    main()
