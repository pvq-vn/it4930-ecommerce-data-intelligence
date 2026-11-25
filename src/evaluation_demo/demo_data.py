"""Serve the integrated TV5 models, enriched market catalog, and compatibility rules."""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from explainability import explain_lightgbm, vnd_contributions
from model_loader import canonicalize_input, load_model
from prepare_test_data import REPO_ROOT, load_tv7_flags, prepare_tv5_splits


TV6_REVIEW_FEATURES_PATH = REPO_ROOT / "data" / "tv6" / "tv5_review_features.csv"
UNKNOWN_TOKENS = {"", "unknown", "n/a", "none", "null", "nan"}
DIRTY_NETWORK_RE = re.compile(r"\d[,.]\d{3}|vnđ|vnd", flags=re.IGNORECASE)
NON_APPLE_LAPTOP_CPU_RE = re.compile(
    r"snapdragon|mediatek|dimensity|helio|exynos|unisoc|kirin|tensor|ryzen|amd|pentium|celeron",
    flags=re.IGNORECASE,
)
NON_APPLE_GPU_RE = re.compile(r"rtx|gtx|geforce|nvidia|quadro", flags=re.IGNORECASE)
APPLE_SILICON_CPU_RE = re.compile(r"\bapple\s+[ma]\d|\b[ma][1-9]\b", flags=re.IGNORECASE)

DISPLAY_LABELS = {
    "brand": "Thương hiệu", "model_clean": "Dòng máy", "seller_name": "Nhà bán lẻ",
    "cpu_model": "Mẫu CPU", "gpu_model": "Mẫu GPU", "cpu_tier_score": "Cấp CPU",
    "ram_gb": "RAM", "storage_gb": "Bộ nhớ", "ram_x_storage": "RAM × bộ nhớ",
    "screen_size_inch": "Kích thước màn hình", "display_type_norm": "Công nghệ màn hình",
    "network_type_norm": "Loại mạng", "camera_mp": "Camera",
    "battery_wh": "Pin (Wh)", "battery_mah": "Pin (mAh)", "charger_watt": "Công suất sạc (W)",
    "is_ram_missing": "Thiếu thông tin RAM", "is_battery_missing": "Thiếu thông tin pin",
    "is_charger_missing": "Thiếu thông tin sạc", "is_out_of_stock": "Hết hàng",
    "is_dedicated_gpu": "GPU rời", "is_rom_high": "Bộ nhớ từ 256 GB", "is_oled": "Màn hình OLED",
    "cpu_perf_rating": "Điểm CPU (TV4)", "gpu_perf_rating": "Điểm GPU (TV4)",
    "cpu_benchmark_score": "Điểm CPU tổng hợp (TV4)", "cpu_geekbench_5_multi": "Geekbench 5 Multi (TV4)",
    "cpu_passmark": "PassMark CPU (TV4)", "hw_seller_count": "Số niêm yết cùng cấu hình (TV4)",
    "has_review_data": "Có dữ liệu review (TV6)", "review_count_usable": "Số review hợp lệ (TV6)",
    "avg_sentiment_score": "Điểm cảm xúc TB (TV6)", "sentiment_positive_ratio": "Tỷ lệ review tích cực (TV6)",
    "sentiment_net_score": "Điểm cảm xúc ròng (TV6)", "brand_sentiment_prior": "Uy tín cảm xúc hãng (TV6)",
}
LISTING_KEY = "listing_record_id"


def load_demo_data():
    return prepare_tv5_splits()


def load_demo_model(category, model_key):
    return load_model(category, model_key)


def build_catalog(splits=None):
    """Use the 8,132 eligible listings enriched with TV7 audit types and TV6 review context."""
    if splits is None:
        splits = load_demo_data()
    parts = []
    for category, split in splits.items():
        partitions = (
            (split.X_train, split.y_train, split.train_metadata),
            (split.X_test, split.y_test, split.test_metadata),
        )
        for raw, price, metadata in partitions:
            provenance = metadata[[LISTING_KEY, "product_name", "availability_status", "source_parent_id"]]
            parts.append(raw.join(provenance).assign(price_vnd=price, category_clean=category))
    catalog = pd.concat(parts, ignore_index=True)

    flags = load_tv7_flags([
        "anomaly_severity",
        "anomaly_reasons",
        "anomaly_type",
        "recommended_action",
        "combined_flag",
        "methods_agree",
    ])
    catalog = catalog.merge(flags, on=LISTING_KEY, how="left", validate="one_to_one")
    if catalog["anomaly_severity"].isna().any():
        raise ValueError("Bảng cờ TV7 thiếu một số dòng trong dữ liệu demo.")
    catalog["anomaly_reasons"] = catalog["anomaly_reasons"].fillna("")
    catalog["anomaly_type"] = catalog["anomaly_type"].replace("", "none").fillna("none")
    catalog["recommended_action"] = catalog["recommended_action"].replace("", "none").fillna("none")

    if TV6_REVIEW_FEATURES_PATH.is_file():
        tv6 = pd.read_csv(TV6_REVIEW_FEATURES_PATH, dtype={"source_parent_id": str})
        desired_tv6 = [
            "has_review_data",
            "review_count_usable",
            "review_count_last_90d",
            "avg_rating",
            "avg_sentiment_score",
            "sentiment_positive_ratio",
            "sentiment_negative_ratio",
            "sentiment_neutral_ratio",
            "sentiment_net_score",
            "aspect_sentiment_score_battery_power",
            "aspect_sentiment_score_performance_thermal",
            "aspect_sentiment_score_display_design",
            "aspect_sentiment_score_camera_audio",
            "aspect_sentiment_score_service_logistics",
        ]
        extra_cols = [col for col in desired_tv6 if col in tv6.columns and col not in catalog.columns]
        if extra_cols:
            tv6_sub = tv6[["source_parent_id", *extra_cols]].drop_duplicates(subset=["source_parent_id"])
            catalog = catalog.merge(tv6_sub, on="source_parent_id", how="left", validate="many_to_one")

    for col in ("has_review_data", "review_count_usable"):
        if col in catalog.columns:
            catalog[col] = pd.to_numeric(catalog[col], errors="coerce").fillna(0).astype(int)

    return catalog


def _clean_labels(series: pd.Series, *, clean_network: bool = False) -> list[str]:
    values = []
    for raw in series.dropna().unique():
        if not isinstance(raw, str):
            continue
        text = raw.strip()
        if not text or text.casefold() in UNKNOWN_TOKENS:
            continue
        if clean_network and DIRTY_NETWORK_RE.search(text):
            continue
        values.append(text)
    return sorted(set(values), key=str.casefold)


def _clean_numbers(series: pd.Series, *, as_int: bool = False) -> list[int | float]:
    nums = pd.to_numeric(series, errors="coerce")
    nums = nums[np.isfinite(nums) & (nums > 0)]
    if nums.empty:
        return []
    if as_int:
        return sorted({int(round(val)) for val in nums})
    return sorted({round(float(val), 1) for val in nums})


def _is_cpu_compatible(category: str, brand: str | None, cpu: str) -> bool:
    b = (brand or "").strip().casefold()
    c = cpu.strip().casefold()
    if b == "apple":
        if category == "smartphone":
            return "apple" in c or bool(re.match(r"^a\d+", c))
        return not bool(NON_APPLE_LAPTOP_CPU_RE.search(c))
    if b:
        if c.startswith("apple ") or bool(re.match(r"^m[1-9]\b|^a1[0-9]\b", c)):
            return False
    return True


def _is_gpu_compatible(category: str, brand: str | None, cpu_model: str | None, gpu: str, device_cpus: list[str] | None = None) -> bool:
    if category != "laptop":
        return True
    b = (brand or "").strip().casefold()
    g = gpu.strip().casefold()
    cpu_text = (cpu_model or "").strip().casefold()
    if b == "apple":
        if NON_APPLE_GPU_RE.search(g):
            return False
        apple_silicon = bool(APPLE_SILICON_CPU_RE.search(cpu_text)) or (
            bool(device_cpus) and all(APPLE_SILICON_CPU_RE.search(x) for x in device_cpus)
        )
        if apple_silicon:
            return "apple" in g
        return True
    if b and g.startswith("apple"):
        return False
    return True


def build_compatibility_options(
    frame: pd.DataFrame,
    category: str,
    brand: str | None = None,
    device: str | None = None,
    cpu_model: str | None = None,
) -> dict[str, object]:
    """Derive physically compatible hardware choices for cascading UI controls."""
    if category not in {"laptop", "smartphone"}:
        raise ValueError(f"Loai thiet bi khong ho tro: {category}")

    cat_df = frame.loc[frame["category_clean"].eq(category)] if "category_clean" in frame.columns else frame
    brands = _clean_labels(cat_df["brand"]) if "brand" in cat_df.columns else []
    sellers = _clean_labels(cat_df["seller_name"]) if "seller_name" in cat_df.columns else []

    if brand and "brand" in cat_df.columns:
        brand_df = cat_df.loc[cat_df["brand"].fillna("").astype(str).str.strip().str.casefold().eq(brand.strip().casefold())]
    else:
        brand_df = cat_df

    devices = _clean_labels(brand_df["model_clean"]) if "model_clean" in brand_df.columns else []
    if device and "model_clean" in brand_df.columns:
        dev_mask = brand_df["model_clean"].fillna("").astype(str).str.strip().str.casefold().eq(device.strip().casefold())
        device_df = brand_df.loc[dev_mask] if dev_mask.any() else brand_df
    else:
        device_df = brand_df

    fallback_used: dict[str, bool] = {}

    raw_dev_cpus = _clean_labels(device_df["cpu_model"]) if "cpu_model" in device_df.columns else []
    cpus = [c for c in raw_dev_cpus if _is_cpu_compatible(category, brand, c)]
    if not cpus and "cpu_model" in brand_df.columns:
        cpus = [c for c in _clean_labels(brand_df["cpu_model"]) if _is_cpu_compatible(category, brand, c)]
        fallback_used["cpu_model"] = True
    else:
        fallback_used["cpu_model"] = False

    gpus: list[str] = []
    if category == "laptop" and "gpu_model" in cat_df.columns:
        gpu_source = device_df
        if cpu_model and "cpu_model" in device_df.columns:
            cpu_mask = device_df["cpu_model"].fillna("").astype(str).str.strip().str.casefold().eq(cpu_model.strip().casefold())
            if cpu_mask.any():
                gpu_source = device_df.loc[cpu_mask]
        gpus = [
            g for g in _clean_labels(gpu_source["gpu_model"])
            if _is_gpu_compatible(category, brand, cpu_model, g, cpus)
        ]
        if not gpus:
            gpus = [
                g for g in _clean_labels(brand_df["gpu_model"])
                if _is_gpu_compatible(category, brand, cpu_model, g, cpus)
            ]
            fallback_used["gpu_model"] = True
        else:
            fallback_used["gpu_model"] = False

    def _numeric_choices(col: str, *, as_int: bool, default_bounds: tuple[float, float]):
        vals = _clean_numbers(device_df[col], as_int=as_int) if col in device_df.columns else []
        used_fb = False
        if not vals and col in brand_df.columns:
            vals = _clean_numbers(brand_df[col], as_int=as_int)
            used_fb = True
        if not vals and col in cat_df.columns:
            vals = _clean_numbers(cat_df[col], as_int=as_int)
            used_fb = True
        fallback_used[col] = used_fb
        bounds = (float(min(vals)), float(max(vals))) if vals else default_bounds
        return vals, bounds

    rams, ram_bounds = _numeric_choices("ram_gb", as_int=True, default_bounds=(4.0, 64.0) if category == "laptop" else (2.0, 24.0))
    storages, storage_bounds = _numeric_choices("storage_gb", as_int=True, default_bounds=(128.0, 4096.0) if category == "laptop" else (32.0, 1024.0))
    screens, screen_bounds = _numeric_choices("screen_size_inch", as_int=False, default_bounds=(11.0, 18.5) if category == "laptop" else (4.0, 8.5))

    displays: list[str] = []
    networks: list[str] = []
    if category == "smartphone":
        if "display_type_norm" in device_df.columns:
            displays = _clean_labels(device_df["display_type_norm"]) or _clean_labels(brand_df["display_type_norm"])
        if "network_type_norm" in device_df.columns:
            networks = _clean_labels(device_df["network_type_norm"], clean_network=True) or _clean_labels(
                brand_df["network_type_norm"], clean_network=True
            )

    return {
        "brands": brands,
        "devices": devices,
        "sellers": sellers,
        "cpu_models": cpus,
        "gpu_models": gpus,
        "ram_gb_options": rams,
        "storage_gb_options": storages,
        "screen_size_options": screens,
        "ram_bounds": ram_bounds,
        "storage_bounds": storage_bounds,
        "screen_bounds": screen_bounds,
        "display_types": displays,
        "network_types": networks,
        "fallback_used": fallback_used,
    }


def audit_listing_fair_value(listing_row, split, model, mdape_pct: float = 10.0) -> dict[str, object]:
    """Compare a real market SKU's listed price against its Hedonic Fair Value."""
    row_dict = listing_row.to_dict() if hasattr(listing_row, "to_dict") else dict(listing_row)
    frame = pd.DataFrame([{col: row_dict.get(col) for col in split.X_train.columns}], columns=split.X_train.columns)
    fair_value = float(model.predict(frame)[0])
    recorded_price = float(row_dict["price_vnd"])
    band = max(0.0, float(mdape_pct)) / 100.0
    low_fair = max(0.0, fair_value * (1.0 - band))
    high_fair = fair_value * (1.0 + band)
    gap_vnd = recorded_price - fair_value
    gap_pct = 100.0 * gap_vnd / fair_value if fair_value > 0 else 0.0

    if gap_pct < -float(mdape_pct):
        verdict = "undervalued"
        verdict_label = "Giá hời / Thấp hơn mặt bằng cấu hình"
    elif gap_pct > float(mdape_pct):
        verdict = "overvalued"
        verdict_label = "Cao hơn mặt bằng cấu hình — kiểm tra Brand Premium / chính sách sàn"
    else:
        verdict = "fair"
        verdict_label = "Hợp lý trong dải tham chiếu thị trường"

    return {
        "frame": frame,
        "recorded_price_vnd": recorded_price,
        "fair_value_vnd": fair_value,
        "low_fair_vnd": low_fair,
        "high_fair_vnd": high_fair,
        "gap_vnd": gap_vnd,
        "gap_pct": gap_pct,
        "band_pct": float(mdape_pct),
        "verdict": verdict,
        "verdict_label": verdict_label,
    }


def prediction_frame(product, category, split):
    """Map aliases to the trained labels and let TV5 handle absent specifications."""
    trimmed = {
        key: (value.strip() or None) if isinstance(value, str) else value
        for key, value in product.items()
    }
    normalized = canonicalize_input(trimmed, category, split.X_train)
    normalized["category_clean"] = category
    return pd.DataFrame([normalized], columns=split.X_train.columns)


def _name(value):
    return "" if pd.isna(value) else str(value).strip().casefold()


def similar_listings(catalog, category, product, limit=5):
    """Rank by brand/model and hardware; use the ID only to break ties."""
    if limit < 0:
        raise ValueError("limit must be nonnegative")
    candidates = catalog.loc[catalog["category_clean"].eq(category)]
    brand = _name(product.get("brand"))
    model = _name(product.get("model_clean"))
    same_brand = candidates["brand"].map(_name).eq(brand) & bool(brand)
    same_model = candidates["model_clean"].map(_name).eq(model) & bool(model)
    if brand:
        same_model &= same_brand
    missing = pd.Series(0, index=candidates.index)
    distance = pd.Series(0.0, index=candidates.index)
    for field in ("ram_gb", "storage_gb"):
        desired = pd.to_numeric(product.get(field), errors="coerce")
        if pd.isna(desired) or not np.isfinite(desired) or desired <= 0:
            continue
        observed = pd.to_numeric(candidates[field], errors="coerce")
        observed = observed.where(observed.gt(0) & np.isfinite(observed))
        missing += observed.isna().astype(int)
        distance += (np.log2(observed) - np.log2(desired)).abs().fillna(0)
    ranked = candidates.assign(_model=same_model, _brand=same_brand, _missing=missing, _distance=distance)
    ranked = ranked.sort_values(
        ["_model", "_brand", "_missing", "_distance", LISTING_KEY],
        ascending=[False, False, True, True, True],
    )
    configuration = ["seller_name", "brand", "model_clean", "cpu_model", "gpu_model", "ram_gb", "storage_gb"]
    return ranked.drop_duplicates(configuration).head(limit).drop(columns=["_model", "_brand", "_missing", "_distance"])


def _ridge_feature_groups(preprocessor):
    """Map each transformed column back to its source feature after one-hot encoding."""
    numeric, categorical = preprocessor.transformers_[:2]
    encoder, cat_fields = categorical[1:]
    groups = list(numeric[2])
    for index, (field, values) in enumerate(zip(cat_fields, encoder.categories_)):
        dropped = encoder.drop_idx_ is not None and encoder.drop_idx_[index] is not None
        groups.extend([field] * (len(values) - int(dropped)))
    return groups


def _permutation_shap(estimator, instance, reference_rows, count=128):
    """Approximate interventional SHAP with deterministic, complete feature orders."""
    rng = np.random.default_rng(42)
    instance = np.asarray(instance).ravel()
    reference_rows = np.asarray(reference_rows)
    width = instance.size
    references = reference_rows[rng.integers(len(reference_rows), size=count)]
    orders = np.stack([rng.permutation(width) for _ in range(count)])
    paths = np.empty((count, width + 1, width))
    for i, order in enumerate(orders):
        state = references[i].copy()
        paths[i, 0] = state
        for j, feature in enumerate(order, 1):
            state[feature] = instance[feature]
            paths[i, j] = state
    raw = estimator.predict(paths.reshape(-1, width)).reshape(count, width + 1)
    phi = np.zeros(width)
    np.add.at(phi, orders.ravel(), np.diff(raw, axis=1).ravel() / count)
    return phi, float(raw[:, 0].mean())


def local_explanation(model, model_key, frame, background):
    """Return a VND baseline and grouped, signed contributions for one prediction."""
    if len(frame) != 1:
        raise ValueError("Giải thích cục bộ cần đúng một dòng đầu vào.")
    approximated = False
    if model_key == "lgbm":
        features, phis, bases, predictions = explain_lightgbm(model, frame)
        names, phi, base_log = features.columns, phis[0], float(bases[0])
        prediction = float(predictions[0])
    elif model_key in {"ridge", "rf"}:
        steps = model.regressor_.named_steps
        engineer, preprocessor, estimator = (steps[key] for key in ("features_engineer", "preprocessor", "model"))
        transformed = preprocessor.transform(engineer.transform(frame))
        if model_key == "ridge":
            if background is None or background.empty:
                raise ValueError("Ridge cần tập train để tính mức tham chiếu.")
            center = np.asarray(preprocessor.transform(engineer.transform(background)).mean(axis=0)).ravel()
            row = transformed.toarray() if hasattr(transformed, "toarray") else transformed
            phi = estimator.coef_.ravel() * (np.asarray(row).ravel() - center)
            base_log = float(estimator.intercept_ + estimator.coef_.ravel() @ center)
            names = _ridge_feature_groups(preprocessor)
        else:
            try:
                from shap import TreeExplainer
            except ImportError:
                if background is None or background.empty:
                    raise ValueError("Random Forest cần tập train để tính mức tham chiếu.") from None
                references = preprocessor.transform(engineer.transform(background))
                phi, base_log = _permutation_shap(estimator, transformed, references)
                approximated = True
            else:
                explainer = TreeExplainer(estimator, feature_perturbation="tree_path_dependent")
                phi = np.asarray(explainer.shap_values(transformed)).ravel()
                base_log = float(np.asarray(explainer.expected_value).item())
            names = [name.split("__", 1)[-1] for name in preprocessor.get_feature_names_out()]
        prediction = float(model.predict(frame)[0])
    else:
        raise ValueError(f"Mô hình không được hỗ trợ: {model_key}")
    grouped = pd.Series(phi, index=names).groupby(level=0, sort=False).sum()
    baseline, delta = vnd_contributions(base_log, grouped.to_numpy())
    if not np.isclose(baseline + delta.sum(), prediction, rtol=1e-7, atol=1e-4):
        raise ValueError("Tổng đóng góp không khớp giá dự đoán.")
    contributions = grouped.rename_axis("feature").rename("shap_log").reset_index()
    contributions["label"] = contributions["feature"].map(lambda feature: DISPLAY_LABELS.get(feature, feature))
    contributions["delta_vnd"] = delta
    contributions = contributions.sort_values("delta_vnd", key=abs, ascending=False, kind="stable").reset_index(drop=True)
    contributions.attrs["approximated"] = approximated
    return baseline, contributions
