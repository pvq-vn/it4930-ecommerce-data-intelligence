"""Explain the saved S4 models and produce data for figures 10.4–10.7."""

import hashlib
import json

import joblib
import numpy as np
import pandas as pd

from ablation_sensitivity import OUTPUT_DIR, TABLE_PATH, file_hash
from evaluate_models import accuracy_metrics
from prepare_test_data import DATA_COMMIT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot
from train_tv4 import split_fingerprints
from train_tv6 import S4_MODEL_DIR
from tv4_features import add_tv4_inputs, load_tv4_benchmarks
from tv6_features import add_tv6_inputs, load_tv6_reviews


PLOT_DATA = OUTPUT_DIR / "explainability_data.json"
SWEEP_TABLE = OUTPUT_DIR / "tables" / "monotonicity_sweeps.csv"
FIXTURES = {
    "laptop": (
        "2a89dcb6850ab319de04471b2f3c8f58708120f5be18826c6f620d38add345cd",
        "ASUS Vivobook 15 OLED A1505VA",
    ),
    "smartphone": (
        "06c4b94234199495968797347fd21c0d54bc2e50c24668798cefe0ccb79a994e",
        "OPPO Find N3",
    ),
}
SWEEP_GRIDS = {"ram_gb": [8, 16, 32, 64], "storage_gb": [128, 256, 512, 1024]}
FEATURE_LABELS = {
    "cpu_model": "CPU model", "gpu_model": "GPU model", "ram_gb": "RAM (GB)",
    "ram_x_storage": "RAM x storage", "storage_gb": "Storage (GB)", "brand": "Brand",
    "gpu_perf_rating": "GPU benchmark", "cpu_perf_rating": "CPU benchmark",
    "cpu_benchmark_score": "CPU benchmark", "model_clean": "Device model",
    "seller_name": "Retailer", "hw_seller_count": "Retailer count",
    "screen_size_inch": "Screen size", "display_type_norm": "Display type",
    "network_type_norm": "Network type", "camera_mp": "Camera (MP)",
    "battery_wh": "Battery (Wh)", "battery_mah": "Battery (mAh)",
    "is_battery_missing": "Battery missing", "is_ram_missing": "RAM missing",
    "is_dedicated_gpu": "Dedicated GPU", "cpu_tier_score": "CPU tier",
    "is_out_of_stock": "Out of stock", "is_rom_high": "Storage at least 256GB", "is_oled": "OLED display",
    "review_count_usable": "Review count", "has_review_data": "Has reviews",
    "avg_sentiment_score": "Mean review sentiment", "brand_sentiment_prior": "Brand sentiment",
    "sentiment_positive_ratio": "Positive reviews",
    "aspect_sentiment_score_battery_power": "Battery sentiment",
    "aspect_sentiment_score_performance_thermal": "Performance sentiment",
    "aspect_sentiment_score_display_design": "Display sentiment",
    "aspect_sentiment_score_camera_audio": "Camera / audio sentiment",
    "aspect_sentiment_score_service_logistics": "Service sentiment",
}


def label(feature):
    return FEATURE_LABELS.get(feature, feature.replace("_", " "))


def explain_lightgbm(model, X):
    """Use the LightGBM tree contribution API on the exact transformed DataFrame."""
    steps = model.regressor_.named_steps
    features = steps["features_engineer"].transform(X)
    estimator = steps["model"]
    if features.columns.tolist() != estimator.feature_name_:
        raise ValueError("Transformed columns do not match the fitted LightGBM model.")
    decomposition = estimator.predict(features, pred_contrib=True, validate_features=True)
    if decomposition.shape != (len(X), features.shape[1] + 1):
        raise ValueError("Expected one SHAP value per feature plus a baseline.")
    phi, base_log = decomposition[:, :-1], decomposition[:, -1]
    prediction = model.predict(X)
    np.testing.assert_allclose(base_log + phi.sum(axis=1), np.log1p(prediction), rtol=0, atol=1e-10)
    return features, phi, base_log, prediction


def swarm_offsets(values, width, rng):
    # Pack points in each horizontal bin on alternating sides of the feature row.
    bins = np.floor(values / width).astype(int)
    offsets = np.zeros(len(values))
    for group in np.unique(bins):
        positions = rng.permutation(np.flatnonzero(bins == group))
        pack = np.arange(len(positions))
        signed = ((pack + 1) // 2) * np.where(pack % 2 == 1, 1, -1)
        offsets[positions] = 0.35 * signed / max(2, len(positions) // 2)
    return offsets


def global_summary(category, features, phi, limit=10):
    magnitude = np.abs(phi).mean(axis=0)
    order = np.argsort(-magnitude, kind="stable")
    axis_width = max(float(np.ptp(phi[:, order[:limit]])) / 75, 1e-6)
    rng = np.random.default_rng(42)
    summary = []
    for index in order[:limit]:
        name = features.columns[index]
        values = features[name]
        effects = phi[:, index]
        offsets = swarm_offsets(effects, axis_width, rng)
        colors = [None] * len(values)
        if pd.api.types.is_numeric_dtype(values):
            ranks = values.rank(method="average")
            width = ranks.max() - ranks.min()
            scaled = (ranks - ranks.min()) / width if width > 0 else pd.Series(0.5, index=values.index)
            colors = [None if pd.isna(value) else float(value) for value in scaled]
        summary.append({
            "name": name, "label": label(name), "mean_abs": float(magnitude[index]),
            "points": [
                {"shap": float(value), "offset": float(offset), "color_value": color}
                for value, offset, color in zip(effects, offsets, colors)
            ],
        })
    return {
        "category": category, "n_test": len(features), "features": summary,
        "importance_all": [
            {"name": features.columns[i], "mean_abs": float(magnitude[i])} for i in order
        ],
    }


def vnd_contributions(base_log, phi):
    """Allocate the VND difference in proportion to log-scale SHAP values."""
    total = float(phi.sum())
    slope = np.exp(base_log) * (np.expm1(total) / total if total != 0 else 1.0)
    return float(np.expm1(base_log)), phi * slope


def local_examples(contexts):
    all_candidates = pd.concat([
        context["metadata"].assign(category=category, price=context["actual"])
        for category, context in contexts.items()
    ], ignore_index=True)
    tiers = [
        ("Budget", 0, 10_000_000, 7_000_000),
        ("Mid-range", 15_000_000, 25_000_000, 20_000_000),
        ("Premium", 40_000_000, 100_000_000, 55_000_000),
    ]
    examples = []
    for tier, low, high, target in tiers:
        candidates = all_candidates.loc[all_candidates["price"].between(low, high, inclusive="left")]
        candidates = candidates.assign(distance=(candidates["price"] - target).abs())
        chosen = candidates.sort_values(["distance", "listing_record_id"]).iloc[0]
        context = contexts[chosen["category"]]
        position = int(np.flatnonzero(context["metadata"]["listing_record_id"].eq(chosen["listing_record_id"]))[0])
        phi = context["phi"][position]
        baseline, delta = vnd_contributions(context["base_log"][position], phi)
        prediction = float(context["prediction"][position])
        order = np.argsort(-np.abs(delta), kind="stable")
        names = context["features"].columns
        contributions = [(names[i], delta[i]) for i in order[:5]]
        contributions.append(("Other features", delta[order[5:]].sum()))
        steps, running = [], baseline
        for name, amount in contributions:
            endpoint = running + float(amount)
            steps.append({
                "name": name, "label": label(name), "start_vnd": running,
                "end_vnd": endpoint, "delta_vnd": float(amount),
            })
            running = endpoint
        np.testing.assert_allclose(running, prediction, rtol=1e-10, atol=1e-4)
        examples.append({
            "tier": tier, "category": chosen["category"], "listing_id": chosen["listing_record_id"],
            "name": chosen["product_name"], "baseline_vnd": baseline, "predicted_vnd": prediction,
            "actual_vnd": float(chosen["price"]), "steps": steps,
        })
    return examples


def run_sweeps(category, split, X_train, X_test, models):
    fixture_id, fixture_name = FIXTURES[category]
    match = split.test_metadata["listing_record_id"].eq(fixture_id)
    if match.sum() != 1:
        raise ValueError(f"Expected one test listing for {fixture_name}.")
    fixture = X_test.loc[match]
    if fixture[list(SWEEP_GRIDS)].isna().any().any():
        raise ValueError("The sweep fixture must have recorded RAM and storage.")
    engineer = models["lgbm"].regressor_.named_steps["features_engineer"]
    original_store_count = int(engineer.store_counts(fixture).iloc[0])
    panels, rows = [], []
    for field, grid in SWEEP_GRIDS.items():
        changed = pd.concat([fixture] * len(grid), ignore_index=True)
        changed[field] = grid
        current_counts = engineer.store_counts(changed)
        if not current_counts.eq(original_store_count).all():
            raise ValueError("The fixture is not suitable: the retailer count changes with hardware.")
        train_counts = [int(pd.to_numeric(X_train[field], errors="coerce").eq(value).sum()) for value in grid]
        panel = {
            "category": category, "field": field, "fixture_name": fixture_name, "listing_id": fixture_id,
            "original_ram_gb": float(fixture["ram_gb"].iloc[0]),
            "original_storage_gb": float(fixture["storage_gb"].iloc[0]),
            "retailer_count": original_store_count, "grid": grid, "train_counts": train_counts, "models": [],
        }
        for key, model in models.items():
            prediction = model.predict(changed)
            if not np.isfinite(prediction).all():
                raise ValueError(f"Non-finite result for {category}/{key}/{field}.")
            delta = np.diff(prediction)
            decreases = [f"{grid[i]} -> {grid[i + 1]}" for i in np.flatnonzero(delta < -0.01)]
            panel["models"].append({
                "model": key, "predictions_vnd": prediction.tolist(), "decreases": decreases,
            })
            for i, value in enumerate(grid):
                rows.append({
                    "category": category, "fixture_name": fixture_name, "listing_record_id": fixture_id,
                    "field": field, "tested_value_gb": value, "train_rows_with_value": train_counts[i],
                    "model": key, "predicted_vnd": float(prediction[i]),
                    "change_from_prior_vnd": float(delta[i - 1]) if i else None,
                    "decreased_from_prior": bool(i and delta[i - 1] < -0.01),
                    "retailer_count": original_store_count,
                })
        panels.append(panel)
    return panels, rows


def main():
    manifest_path = S4_MODEL_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("S4 used a different snapshot.")
    for name, expected in manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(name)).hexdigest() != expected:
            raise ValueError(f"Snapshot data differs from S4: {name}")
    for name, expected in manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / name) != expected:
            raise ValueError(f"Prediction code differs from S4: {name}")
    reviews, review_hash = load_tv6_reviews()
    if review_hash != manifest["review_sha256"]:
        raise ValueError("TV6 features differ from S4.")
    recorded = pd.read_csv(TABLE_PATH).query("stage == 'S4'").set_index(["category", "model"])
    output = {
        "data_commit": DATA_COMMIT, "stage": "S4", "model_manifest_sha256": file_hash(manifest_path),
        "shap_method": "LightGBM path-dependent TreeSHAP, log1p(VND). Local VND contributions allocate the total difference from the log baseline proportionally.",
        "sweep_policy": "One raw hardware field changes at a time; fitted transforms recompute its dependent features. Chosen fixtures retain the same retailer count throughout.",
        "global": [], "sweeps": [],
    }
    sweeps, contexts = [], {}
    for category, split in prepare_tv5_splits().items():
        benchmarks, digest = load_tv4_benchmarks(category)
        if digest != manifest["benchmark_sha256"][category]:
            raise ValueError(f"TV4 inputs differ from S4 for {category}.")
        base_train, base_test = add_tv4_inputs(split, benchmarks)
        X_train = add_tv6_inputs(base_train, split.train_metadata, reviews, category)
        X_test = add_tv6_inputs(base_test, split.test_metadata, reviews, category)
        models = {}
        fingerprints = split_fingerprints(split)
        actual = split.y_test.to_numpy()
        for reference in manifest["models"]:
            if reference["category"] != category:
                continue
            key = reference["model"]
            path = S4_MODEL_DIR / reference["file"]
            if file_hash(path) != reference["sha256"] or any(reference[k] != v for k, v in fingerprints.items()):
                raise ValueError(f"Saved S4 model or input rows changed: {category}/{key}")
            model = joblib.load(path)
            metrics = accuracy_metrics(actual, model.predict(X_test))
            expected = recorded.loc[category, key]
            if not all(np.isclose(v, expected[k], rtol=1e-8, atol=1e-6) for k, v in metrics.items()):
                raise ValueError(f"Cannot reproduce S4 results for {category}/{key}.")
            models[key] = model
        if set(models) != {"ridge", "rf", "lgbm"}:
            raise ValueError(f"Expected all three S4 models for {category}.")
        features, phi, base_log, prediction = explain_lightgbm(models["lgbm"], X_test)
        output["global"].append(global_summary(category, features, phi))
        contexts[category] = {
            "features": features, "phi": phi, "base_log": base_log, "prediction": prediction,
            "metadata": split.test_metadata, "actual": actual,
        }
        panels, rows = run_sweeps(category, split, X_train, X_test, models)
        output["sweeps"].extend(panels)
        sweeps.extend(rows)
        leaders = output["global"][-1]["features"][:3]
        print(f"{category}: {len(X_test)} TreeSHAP checks; leading features: {', '.join(x['label'] for x in leaders)}")
    output["local"] = local_examples(contexts)
    for example in output["local"]:
        print(f"{example['tier']}: recorded {example['actual_vnd']:,.0f}, predicted {example['predicted_vnd']:,.0f} VND")
    PLOT_DATA.write_text(json.dumps(output, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    pd.DataFrame(sweeps).to_csv(SWEEP_TABLE, index=False, encoding="utf-8-sig")
    print(f"Data for figures: {PLOT_DATA}")
    print(f"Sweep details: {SWEEP_TABLE}")


if __name__ == "__main__":
    main()
