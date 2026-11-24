"""Compare stock + screen cleanup against the same setup with S2 charger fields."""

import hashlib
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from ablation_sensitivity import OUTPUT_DIR, TABLE_PATH, file_hash
from evaluate_models import accuracy_metrics
from prepare_test_data import DATA_COMMIT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot
from tv3_features import TV3FeatureEngineer, add_tv3_inputs


S2_MODEL_DIR = OUTPUT_DIR / "models" / "s2_tv3"
COMPARISON_PATH = TABLE_PATH.with_name("s2_charger_comparison.csv")
CHARGER_COLUMNS = {"charger_watt", "is_charger_missing"}


def build_stock_model(full_model, model_key):
    """Clone S2's training recipe with the two charger inputs disabled."""
    model = clone(full_model).set_params(regressor__features_engineer__include_charger=False)
    if model_key == "ridge":
        preprocessor = model.regressor.named_steps["preprocessor"]
        preprocessor.transformers = [
            (name, transformer, [column for column in columns if column not in CHARGER_COLUMNS])
            for name, transformer, columns in preprocessor.transformers
        ]
    return model


def main():
    manifest = json.loads((S2_MODEL_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("The current snapshot is different from the one used for S2.")
    for filename, recorded_hash in manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(filename)).hexdigest() != recorded_hash:
            raise ValueError(f"Data changed since S2: {filename}")
    for filename, recorded_hash in manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / filename) != recorded_hash:
            raise ValueError(f"TV5 code changed since S2: {filename}")

    stage_scores = pd.read_csv(TABLE_PATH).set_index(["stage", "category", "model"])
    splits = prepare_tv5_splits()
    rows = []
    for reference in manifest["models"]:
        category, model_key = reference["category"], reference["model"]
        split = splits[category]
        test_ids = "\n".join(split.test_metadata["listing_record_id"]).encode()
        train_indices = split.X_train.index.to_numpy().tobytes()
        if hashlib.sha256(test_ids).hexdigest() != reference["test_ids_sha256"]:
            raise ValueError(f"Test listings changed since S2: {category}")
        if hashlib.sha256(train_indices).hexdigest() != reference["train_index_sha256"]:
            raise ValueError(f"Train rows changed since S2: {category}")

        model_path = S2_MODEL_DIR / reference["file"]
        if file_hash(model_path) != reference["sha256"]:
            raise ValueError(f"S2 model artifact changed: {model_path}")
        full_model = joblib.load(model_path)
        stock_model = build_stock_model(full_model, model_key)
        if stock_model.regressor.named_steps["model"].get_params() != reference["fixed_estimator_params"]:
            raise ValueError(f"Estimator parameters differ from S2: {category}/{model_key}")

        X_train, X_test = add_tv3_inputs(split)
        actual = split.y_test.to_numpy()
        observed = TV3FeatureEngineer._charger(X_test).notna().to_numpy()
        full_pred = full_model.predict(X_test)
        full_metrics = accuracy_metrics(actual, full_pred)
        expected = stage_scores.loc["S2", category, model_key]
        for metric, value in full_metrics.items():
            if not np.isclose(value, expected[metric], rtol=1e-8, atol=1e-6):
                raise ValueError(f"Cannot reproduce S2 {metric}: {category}/{model_key}")

        stock_model.fit(X_train.drop(columns="charger_watt"), split.y_train)
        stock_pred = stock_model.predict(X_test.drop(columns="charger_watt"))
        for subset, mask in (
            ("all", np.ones(len(X_test), dtype=bool)),
            ("charger_observed", observed),
            ("charger_missing", ~observed),
        ):
            if not mask.any():
                continue
            a = accuracy_metrics(actual[mask], stock_pred[mask])
            b = accuracy_metrics(actual[mask], full_pred[mask])
            delta = b["mae_vnd"] - a["mae_vnd"]
            rows.append({
                "category": category,
                "model": model_key,
                "test_subset": subset,
                "n_test": int(mask.sum()),
                "n_train": len(X_train),
                "data_commit": DATA_COMMIT,
                **{f"without_charger_{key}": value for key, value in a.items()},
                **{f"with_charger_{key}": value for key, value in b.items()},
                "mae_delta_with_minus_without_vnd": delta,
                "mae_delta_with_minus_without_pct": 100 * delta / a["mae_vnd"],
            })
            if subset == "all":
                print(
                    f"{category}/{model_key}: A={a['mae_vnd']:,.0f} VND, "
                    f"B={b['mae_vnd']:,.0f} VND, B-A={delta:+,.0f} VND",
                    flush=True,
                )

    pd.DataFrame(rows).to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    print(f"Results: {COMPARISON_PATH}")


if __name__ == "__main__":
    main()
