"""Compare TV7 train filters against S4 on the exact same held-out listings."""

import hashlib
import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from ablation_sensitivity import OUTPUT_DIR, TABLE_PATH, file_hash
from evaluate_models import accuracy_metrics
from prepare_test_data import DATA_COMMIT, REPO_ROOT, TV5_MODELS_DIR, prepare_tv5_splits, read_snapshot
from train_tv4 import split_fingerprints
from train_tv6 import S4_MODEL_DIR
from tv4_features import add_tv4_inputs, load_tv4_benchmarks
from tv6_features import add_tv6_inputs, load_tv6_reviews


TV7_COMMIT = "66f089b851889f662491d252dc821d631ca78f82"
TV7_FLAGS = "src/anomaly_detection/outputs/anomaly_flags.csv"
TV7_CODE = "src/anomaly_detection/detect_price_anomalies.py"
DETAILS_PATH = TABLE_PATH.with_name("s5_tv7_sensitivity_details.csv")
MANIFEST_PATH = OUTPUT_DIR / "s5_tv7_manifest.json"
ID = "listing_record_id"
PRICE = "price_vnd"
HIGH_PRICE = 80_000_000


def read_tv7_file(path):
    return subprocess.check_output(["git", "show", f"{TV7_COMMIT}:{path}"], cwd=REPO_ROOT)


def load_delivered_flags():
    artifact = read_tv7_file(TV7_FLAGS)
    columns = [ID, "category_group", PRICE, "anomaly_severity", "combined_flag"]
    flags = pd.read_csv(BytesIO(artifact), usecols=columns, dtype={ID: str, "combined_flag": "boolean"})
    return flag_index(flags), hashlib.sha256(artifact).hexdigest()


def flag_index(flags):
    if flags[ID].isna().any() or flags[ID].duplicated().any():
        raise ValueError("Expected unique TV7 listing IDs.")
    if flags["combined_flag"].isna().any() or not flags["anomaly_severity"].isin(["none", "review", "extreme"]).all():
        raise ValueError("Invalid TV7 flags or severity.")
    if not flags["combined_flag"].eq(flags["anomaly_severity"].ne("none")).all():
        raise ValueError("TV7 severity and combined flag disagree.")
    return flags.set_index(ID)


def align_flags(flags, metadata, prices, category):
    ids = metadata[ID]
    if not ids.isin(flags.index).all():
        raise ValueError(f"Some {category} listings lack a TV7 record.")
    aligned = flags.loc[ids].set_axis(metadata.index)
    if not aligned["category_group"].eq(category).all() or not aligned[PRICE].eq(prices).all():
        raise ValueError(f"TV7 flags use a different category or price for {category}.")
    return aligned


def removal_masks(aligned_flags):
    return {
        "S5a": aligned_flags["anomaly_severity"].eq("extreme"),
        "S5b": aligned_flags["combined_flag"].astype(bool),
    }


def summarize_filter(removed, metadata, y_train):
    excluded_ids = metadata.loc[removed, ID]
    flagship_mask = y_train.ge(HIGH_PRICE)
    return {
        "n_train": int((~removed).sum()),
        "n_train_before": len(removed),
        "n_train_removed": int(removed.sum()),
        "n_train_ge_80m_before": int(flagship_mask.sum()),
        "n_train_removed_ge_80m": int((flagship_mask & removed).sum()),
        "removed_listing_ids_sha256": hashlib.sha256("\n".join(excluded_ids).encode()).hexdigest(),
    }


def write_results(summaries, details):
    # Publish both primary variants together and keep S1–S4 rows in the same table.
    previous = pd.read_csv(TABLE_PATH)
    previous = previous.loc[~previous["stage"].isin(["S5a", "S5b"])]
    updated = pd.concat([previous, pd.DataFrame(summaries)], ignore_index=True)
    updated = updated.sort_values(["stage", "category", "model"])
    with NamedTemporaryFile(dir=TABLE_PATH.parent, suffix=".csv", delete=False) as temp:
        pending = Path(temp.name)
    try:
        updated.to_csv(pending, index=False, encoding="utf-8-sig")
        pending.replace(TABLE_PATH)
    finally:
        pending.unlink(missing_ok=True)
    pd.DataFrame(details).to_csv(DETAILS_PATH, index=False, encoding="utf-8-sig")


def main():
    reference_path = S4_MODEL_DIR / "manifest.json"
    s4_manifest = json.loads(reference_path.read_text(encoding="utf-8"))
    if s4_manifest["data_commit"] != DATA_COMMIT:
        raise ValueError("S4 uses a different data snapshot.")
    for filename, expected in s4_manifest["data_sha256"].items():
        if hashlib.sha256(read_snapshot(filename)).hexdigest() != expected:
            raise ValueError(f"Data differs from S4: {filename}")
    for filename, expected in s4_manifest["tv5_code_sha256"].items():
        if file_hash(TV5_MODELS_DIR / filename) != expected:
            raise ValueError(f"TV5 code differs from S4: {filename}")
    for filename, expected in s4_manifest["code_sha256"].items():
        if file_hash(Path(__file__).with_name(filename)) != expected:
            raise ValueError(f"TV8 code differs from S4: {filename}")

    historical, flag_hash = load_delivered_flags()
    source_code = read_tv7_file(TV7_CODE).decode("utf-8").replace("\r\n", "\n")
    if (REPO_ROOT / TV7_CODE).read_text(encoding="utf-8") != source_code:
        raise ValueError("TV7 detector source differs from the pinned version.")
    sys.path.insert(0, str(REPO_ROOT))
    from src.anomaly_detection.detect_price_anomalies import detect

    processed = pd.read_json(BytesIO(read_snapshot("products_processed.jsonl")), lines=True).set_index(ID, drop=False)
    if not processed.index.is_unique:
        raise ValueError("The pinned processed data has duplicate listing IDs.")
    s4_scores = pd.read_csv(TABLE_PATH).query("stage == 'S4'").set_index(["category", "model"])
    if len(s4_scores) != 6 or not s4_scores.index.is_unique:
        raise ValueError("Expected six unique S4 results.")
    reviews, review_hash = load_tv6_reviews()
    if review_hash != s4_manifest["review_sha256"]:
        raise ValueError("TV6 input differs from S4.")

    manifest = {
        "baseline_stage": "S4", "data_commit": DATA_COMMIT, "tv7_commit": TV7_COMMIT,
        "delivered_flags_sha256": flag_hash, "tv7_detector_sha256": hashlib.sha256(source_code.encode()).hexdigest(),
        "s4_manifest_sha256": file_hash(reference_path), "script_sha256": file_hash(Path(__file__)),
        "flag_sources": {
            "delivered": "Retrospective: TV7 flags from the full snapshot, including held-out prices.",
            "train_only": "Same detector refit only on the original S4 training listings in each category.",
        },
        "filters": {"S5a": "anomaly_severity == extreme", "S5b": "combined_flag is true"},
        "high_price_vnd": HIGH_PRICE, "categories": {},
    }
    summaries, details = [], []
    for category, split in prepare_tv5_splits().items():
        benchmarks, digest = load_tv4_benchmarks(category)
        if digest != s4_manifest["benchmark_sha256"][category]:
            raise ValueError(f"TV4 input differs from S4: {category}")
        base_train, base_test = add_tv4_inputs(split, benchmarks)
        X_train = add_tv6_inputs(base_train, split.train_metadata, reviews, category)
        X_test = add_tv6_inputs(base_test, split.test_metadata, reviews, category)
        fingerprints = split_fingerprints(split)
        actual = split.y_test.to_numpy()
        expensive = actual >= HIGH_PRICE

        delivered_train = align_flags(historical, split.train_metadata, split.y_train, category)
        align_flags(historical, split.test_metadata, split.y_test, category)
        train_raw = processed.loc[split.train_metadata[ID]].reset_index(drop=True)
        recalculated, _ = detect(train_raw)
        strict_train = align_flags(flag_index(recalculated), split.train_metadata, split.y_train, category)
        flags = {"delivered": removal_masks(delivered_train), "train_only": removal_masks(strict_train)}
        counts = {
            source: {stage: summarize_filter(mask, split.train_metadata, split.y_train) for stage, mask in variants.items()}
            for source, variants in flags.items()
        }
        manifest["categories"][category] = {
            **fingerprints, "n_test": len(actual), "n_test_ge_80m": int(expensive.sum()), "filters": counts,
        }
        references = [row for row in s4_manifest["models"] if row["category"] == category]
        if sorted(row["model"] for row in references) != ["lgbm", "rf", "ridge"]:
            raise ValueError(f"Expected three unique S4 models for {category}.")
        for reference in references:
            model_key = reference["model"]
            if any(reference[field] != value for field, value in fingerprints.items()):
                raise ValueError(f"Original train/test rows differ from S4: {category}")
            old_path = S4_MODEL_DIR / reference["file"]
            if file_hash(old_path) != reference["sha256"]:
                raise ValueError(f"S4 model artifact changed: {old_path}")
            s4_model = joblib.load(old_path)
            baseline_prediction = s4_model.predict(X_test)
            baseline = accuracy_metrics(actual, baseline_prediction)
            prior = s4_scores.loc[category, model_key]
            if not all(np.isclose(value, prior[metric], rtol=1e-8, atol=1e-6) for metric, value in baseline.items()):
                raise ValueError(f"Cannot reproduce S4 scores: {category}/{model_key}")

            for source, variants in flags.items():
                for stage, removed in variants.items():
                    model = clone(s4_model)
                    retained = ~removed
                    start = perf_counter()
                    model.fit(X_train.loc[retained], split.y_train.loc[retained])
                    train_seconds = perf_counter() - start
                    if model.regressor_.named_steps["model"].get_params() != reference["fixed_estimator_params"]:
                        raise ValueError(f"Estimator parameters changed for {stage}: {category}/{model_key}")
                    prediction = model.predict(X_test)
                    common = {
                        "stage": stage, "baseline_stage": "S4", "flag_source": source,
                        "category": category, "model": model_key, "data_commit": DATA_COMMIT,
                        **counts[source][stage], "train_seconds": train_seconds,
                    }
                    for tier, mask in (
                        ("all", np.ones(len(actual), dtype=bool)), ("under_80m", ~expensive), ("ge_80m", expensive),
                    ):
                        if not mask.any():
                            continue
                        scores = accuracy_metrics(actual[mask], prediction[mask])
                        s4 = accuracy_metrics(actual[mask], baseline_prediction[mask])
                        delta = 100 * (scores["mae_vnd"] / s4["mae_vnd"] - 1)
                        metrics = {
                            **common, "n_test": int(mask.sum()), **scores,
                            **{f"s4_{metric}": value for metric, value in s4.items()},
                            "mae_change_vs_s4_pct": delta,
                            "rmse_change_vs_s4_pct": 100 * (scores["rmse_vnd"] / s4["rmse_vnd"] - 1),
                            "r2_change_vs_s4": scores["r2"] - s4["r2"],
                        }
                        details.append({**metrics, "test_price_tier": tier})
                        if tier == "all":
                            if source == "delivered":
                                summaries.append(metrics)
                            print(f"{category}/{model_key} {stage} ({source}): MAE {scores['mae_vnd']:,.0f} VND ({delta:+.2f}%)", flush=True)

    write_results(summaries, details)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Main results: {TABLE_PATH}")
    print(f"Two flag sources and price tiers: {DETAILS_PATH}")


if __name__ == "__main__":
    main()
