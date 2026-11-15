"""Flag suspicious product prices without deleting records.

Run from the repository root:
    python src/anomaly_detection/detect_price_anomalies.py

Writes row-level flags and a compact summary under src/anomaly_detection/outputs/.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer


ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "data" / "processed" / "products_processed.jsonl"
OUT = ROOT / "src" / "anomaly_detection" / "outputs"
MIN_GROUP_SIZE = 20
IQR_MULTIPLIER = 1.5
EXTREME_IQR_MULTIPLIER = 3.0
ISOLATION_CONTAMINATION = 0.02
ISOLATION_RANDOM_STATE = 42
ISOLATION_N_ESTIMATORS = 300

NUMERIC_FEATURES = {
    "laptop": [
        "_log_price", "installed_ram_gb", "max_ram_gb", "storage_gb",
        "screen_size_inch", "battery_wh", "charger_watt",
    ],
    "smartphone": [
        "_log_price", "installed_ram_gb", "storage_gb", "screen_size_inch",
        "battery_mah", "charger_watt", "camera_mp",
    ],
}
CATEGORICAL_FEATURES = [
    "brand_norm", "source", "cpu_norm", "gpu_norm", "display_type_norm",
    "operating_system_norm", "network_type_norm",
]


def _category(row: pd.Series) -> str:
    value = str(row.get("category", "unknown")).strip().lower()
    return value if value in {"laptop", "smartphone"} else "other"


def _append_reason(df: pd.DataFrame, idx: object, reason: str) -> None:
    current = str(df.at[idx, "anomaly_reasons"] or "")
    df.at[idx, "anomaly_reasons"] = "; ".join(filter(None, [current, reason]))


def _isolation_features(group: pd.DataFrame, category: str) -> tuple[np.ndarray, list[str]]:
    """Build numeric features for Isolation Forest without ordinal category codes.

    Categorical values are represented by their frequency inside the category. A
    rare brand/source/specification therefore contributes a low frequency value,
    while avoiding an artificial order such as Apple < Dell < Lenovo.
    """
    feature_frame = pd.DataFrame(index=group.index)
    feature_names: list[str] = []

    for column in NUMERIC_FEATURES[category]:
        feature_frame[column] = pd.to_numeric(
            group[column] if column in group else np.nan, errors="coerce"
        )
        feature_frame[f"{column}_missing"] = feature_frame[column].isna().astype(float)
        feature_names.extend([column, f"{column}_missing"])

    for column in CATEGORICAL_FEATURES:
        values = (
            group[column] if column in group else pd.Series("unknown", index=group.index)
        ).fillna("unknown").astype(str).str.strip().replace("", "unknown")
        frequencies = values.map(values.value_counts(normalize=True))
        feature_name = f"{column}_frequency"
        feature_frame[feature_name] = frequencies.astype(float)
        feature_names.append(feature_name)

    imputer = SimpleImputer(strategy="median")
    return imputer.fit_transform(feature_frame), feature_names


def _apply_isolation_forest(df: pd.DataFrame, valid: pd.Series) -> None:
    """Add category-specific multivariate anomaly scores and flags in place."""
    df["isolation_forest_flag"] = False
    df["isolation_score"] = np.nan
    df["isolation_feature_count"] = 0

    for category in ("laptop", "smartphone"):
        idx = df.index[valid & df["category_group"].eq(category)]
        if len(idx) < 2:
            continue
        matrix, feature_names = _isolation_features(df.loc[idx], category)
        model = IsolationForest(
            n_estimators=ISOLATION_N_ESTIMATORS,
            contamination=ISOLATION_CONTAMINATION,
            random_state=ISOLATION_RANDOM_STATE,
            n_jobs=-1,
        )
        predictions = model.fit_predict(matrix)
        # Negating score_samples makes larger values mean "more anomalous".
        df.loc[idx, "isolation_score"] = -model.score_samples(matrix)
        df.loc[idx, "isolation_forest_flag"] = predictions == -1
        df.loc[idx, "isolation_feature_count"] = len(feature_names)


def detect(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.copy()
    df["price_vnd"] = pd.to_numeric(df.get("price_vnd"), errors="coerce")
    df["category_group"] = df.apply(_category, axis=1)
    df["price_status"] = "valid"
    df.loc[df["price_vnd"].isna(), "price_status"] = "missing_or_unparseable"
    df.loc[df["price_vnd"].le(0), "price_status"] = "non_positive"
    df["rule_flag"] = False
    df["iqr_flag"] = False
    df["iqr_extreme_flag"] = False
    df["anomaly_severity"] = "none"
    df["anomaly_reasons"] = ""
    df["comparison_group"] = df["category_group"]

    valid = df["price_vnd"].gt(0) & df["category_group"].isin(["laptop", "smartphone"])
    # Analyze log prices because retail prices are strongly right-skewed.
    df["_log_price"] = np.nan
    df.loc[valid, "_log_price"] = np.log(df.loc[valid, "price_vnd"])
    brands = df.get("brand_norm", pd.Series("unknown", index=df.index)).fillna("unknown").astype(str)
    df["_brand"] = brands
    # Use category + brand only when there are enough observations; otherwise
    # fall back to category to avoid unstable quartiles in tiny groups.
    for cat in ("laptop", "smartphone"):
        cat_idx = df.index[valid & df["category_group"].eq(cat)]
        for idx in cat_idx:
            brand_idx = df.index[valid & df["category_group"].eq(cat) & df["_brand"].eq(df.at[idx, "_brand"])]
            grp = brand_idx if len(brand_idx) >= MIN_GROUP_SIZE else cat_idx
            df.at[idx, "comparison_group"] = f"{cat}|brand:{df.at[idx, '_brand']}" if len(brand_idx) >= MIN_GROUP_SIZE else cat
        for group_name, idxs in df.loc[cat_idx].groupby("comparison_group").groups.items():
            values = df.loc[list(idxs), "_log_price"]
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            low, high = q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr
            extreme_low = q1 - EXTREME_IQR_MULTIPLIER * iqr
            extreme_high = q3 + EXTREME_IQR_MULTIPLIER * iqr
            for ix in idxs:
                val = df.at[ix, "_log_price"]
                reasons = []
                if val < low:
                    reasons.append("giá thấp hơn ngưỡng IQR của nhóm")
                if val > high:
                    reasons.append("giá cao hơn ngưỡng IQR của nhóm")
                if reasons:
                    df.at[ix, "iqr_flag"] = True
                    df.at[ix, "iqr_extreme_flag"] = val < extreme_low or val > extreme_high
                    _append_reason(df, ix, "; ".join(reasons))
    # Absolute plausibility flags are review prompts, not automatic exclusions.
    floors = df["category_group"].map({"laptop": 3_000_000, "smartphone": 1_000_000})
    low_mask = valid & df["price_vnd"].lt(floors)
    for ix in df.index[low_mask]:
        reason = "giá dưới ngưỡng kiểm tra tối thiểu theo EDA (cần xác minh sản phẩm/giá)"
        df.at[ix, "rule_flag"] = True
        _append_reason(df, ix, reason)

    _apply_isolation_forest(df, valid)
    for ix in df.index[df["isolation_forest_flag"]]:
        _append_reason(df, ix, "Isolation Forest: tổ hợp giá/cấu hình khác thường trong danh mục")

    method_cols = ["rule_flag", "iqr_flag", "isolation_forest_flag"]
    df["methods_agree"] = df[method_cols].sum(axis=1).astype(int)
    df["anomaly_flag"] = df["methods_agree"].gt(0)
    df.loc[df["anomaly_flag"], "anomaly_severity"] = "review"
    df.loc[df["iqr_extreme_flag"] | df["methods_agree"].ge(2), "anomaly_severity"] = "extreme"
    df["combined_flag"] = df["anomaly_flag"]

    summary = (df.groupby(["category_group", "price_status", "anomaly_severity"], dropna=False)
                 .size().rename("records").reset_index())
    return df, summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = pd.read_json(INPUT, lines=True)
    result, summary = detect(data)
    export_cols = [c for c in ["listing_record_id", "source_parent_id", "product_name", "source", "category_group",
        "brand_norm", "price_vnd", "price_status", "comparison_group", "rule_flag", "iqr_flag",
        "iqr_extreme_flag", "isolation_forest_flag", "isolation_score", "isolation_feature_count",
        "methods_agree", "combined_flag", "anomaly_flag", "anomaly_severity", "anomaly_reasons"] if c in result]
    result[export_cols].to_csv(OUT / "anomaly_flags.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUT / "anomaly_summary.csv", index=False, encoding="utf-8-sig")
    flagged = result[result["anomaly_flag"]]
    method_summary = pd.DataFrame([
        {"method": "EDA rule", "flagged": int(result["rule_flag"].sum())},
        {"method": "IQR", "flagged": int(result["iqr_flag"].sum())},
        {"method": "Isolation Forest", "flagged": int(result["isolation_forest_flag"].sum())},
        {"method": "Combined union", "flagged": int(result["combined_flag"].sum())},
        {"method": "At least 2 methods", "flagged": int(result["methods_agree"].ge(2).sum())},
    ])
    method_summary.to_csv(OUT / "anomaly_method_summary.csv", index=False, encoding="utf-8-sig")
    report = ["# Phát hiện bất thường giá sản phẩm", "",
        f"- Đầu vào: `data/processed/products_processed.jsonl` ({len(result):,} bản ghi).",
        "- Phương pháp: IQR trên log(giá), so sánh laptop/smartphone riêng; dùng nhóm thương hiệu khi có ít nhất 20 bản ghi, nếu không dùng nhóm danh mục.",
        f"- Isolation Forest chạy riêng cho laptop/smartphone với {ISOLATION_N_ESTIMATORS} cây, `contamination={ISOLATION_CONTAMINATION}` và `random_state={ISOLATION_RANDOM_STATE}`; mô hình dùng log giá, cấu hình, cờ thiếu và tần suất của đặc trưng phân loại.",
        "- Giá thấp hơn ngưỡng tham chiếu EDA (laptop 3 triệu, smartphone 1 triệu) được gắn cờ xem xét.",
        "- Các cờ chỉ là tín hiệu rà soát; không xóa bản ghi và không khẳng định mọi giá trị bị gắn cờ là lỗi.",
        f"- Giá hợp lệ: {(result.price_status == 'valid').sum():,}; cờ tổng hợp: {len(flagged):,}; mức extreme: {(flagged.anomaly_severity == 'extreme').sum():,}.", "",
        "## Tổng hợp theo phương pháp", "", method_summary.to_markdown(index=False), "",
        "## Tổng hợp theo danh mục", "", summary.to_markdown(index=False), "",
        "## Cách đọc kết quả", "",
        "`rule_flag`, `iqr_flag` và `isolation_forest_flag` cho biết phương pháp nào đã gắn cờ. `isolation_score` càng lớn thì tổ hợp đặc trưng càng khác thường trong danh mục. `methods_agree >= 2` được ưu tiên kiểm tra và xếp mức `extreme`; cờ IQR vượt 3 IQR cũng là `extreme`. `combined_flag` là hợp của ba phương pháp.", "",
        "## Hạn chế", "", "Isolation Forest là mô hình không giám sát và `contamination=0.02` buộc mô hình chọn khoảng 2% bản ghi giá hợp lệ trong mỗi danh mục. Cờ này không phải xác suất lỗi hoặc gian lận. IQR và Isolation Forest đều có thể đánh dấu flagship hay sản phẩm hiếm hợp lệ. Cần đối chiếu raw data/trang nguồn và rà soát thủ công trước khi lọc. Nhóm dự đoán có thể dùng các cờ để so sánh độ nhạy giữa giữ nguyên dữ liệu, chỉ bỏ lỗi đã xác minh và bỏ toàn bộ anomaly.", ""]
    (OUT / "anomaly_report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"rows": len(result), "flagged": len(flagged), "outputs": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
