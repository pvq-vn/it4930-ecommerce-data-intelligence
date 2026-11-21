"""Serve the original TV5 models and their reference catalog in the TV8 demo."""

from io import BytesIO

import numpy as np
import pandas as pd

from explainability import explain_lightgbm, vnd_contributions
from model_loader import canonicalize_input, load_model
from prepare_test_data import prepare_tv5_splits
from train_tv7_sensitivity import TV7_FLAGS, read_tv7_file


DISPLAY_LABELS = {
    "brand": "Thương hiệu", "model_clean": "Dòng máy", "seller_name": "Nhà bán lẻ",
    "cpu_model": "Mẫu CPU", "gpu_model": "Mẫu GPU", "cpu_tier_score": "Cấp CPU",
    "ram_gb": "RAM", "storage_gb": "Bộ nhớ", "ram_x_storage": "RAM × bộ nhớ",
    "screen_size_inch": "Kích thước màn hình", "display_type_norm": "Công nghệ màn hình",
    "network_type_norm": "Loại mạng", "camera_mp": "Camera",
    "battery_wh": "Pin (Wh)", "battery_mah": "Pin (mAh)",
    "is_ram_missing": "Thiếu thông tin RAM", "is_battery_missing": "Thiếu thông tin pin",
    "is_dedicated_gpu": "GPU rời", "is_rom_high": "Bộ nhớ từ 256 GB", "is_oled": "Màn hình OLED",
}
LISTING_KEY = "listing_record_id"


def load_demo_data():
    return prepare_tv5_splits()


def load_demo_model(category, model_key):
    return load_model(category, model_key)


def build_catalog(splits=None):
    """Use the 8,143 eligible listings from the same snapshot as TV5 evaluation."""
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
    flags = pd.read_csv(
        BytesIO(read_tv7_file(TV7_FLAGS)), dtype={LISTING_KEY: str},
        usecols=[LISTING_KEY, "anomaly_severity", "anomaly_reasons"],
    )
    catalog = catalog.merge(flags, on=LISTING_KEY, how="left", validate="one_to_one")
    if catalog["anomaly_severity"].isna().any():
        raise ValueError("Bảng cờ TV7 thiếu một số dòng trong dữ liệu demo.")
    catalog["anomaly_reasons"] = catalog["anomaly_reasons"].fillna("")
    return catalog


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
