from collections import defaultdict
from statistics import median

import numpy as np
import pandas as pd

from prepare_test_data import load_tv7_flags


CONFIG_COLUMNS = ["brand", "model_clean", "ram_gb", "storage_gb"]
GROUP_COLUMNS = ["category", "model"]


def configuration_and_store(rows):
    labels = rows[["brand", "model_clean", "seller_name"]].fillna("")
    labels = labels.apply(lambda column: column.str.strip().str.casefold())
    ram = pd.to_numeric(rows["ram_gb"], errors="coerce")
    storage = pd.to_numeric(rows["storage_gb"], errors="coerce")
    configs = zip(labels["brand"], labels["model_clean"], ram, storage)
    for config, seller in zip(configs, labels["seller_name"]):
        brand, model, ram_gb, storage_gb = config
        complete = brand and model and pd.notna(ram_gb) and pd.notna(storage_gb)
        yield (config if complete else None), seller


def cross_store_context(split):
    """Compare a test listing against complete configurations in the same category's train set."""
    train_by_config = defaultdict(lambda: defaultdict(list))
    for (config, seller), price in zip(configuration_and_store(split.X_train), split.y_train):
        if config is not None:
            train_by_config[config][seller].append(price)

    context = []
    for config, seller in configuration_and_store(split.X_test):
        other_store_prices = []
        if config is None:
            segment = "missing_configuration"
        elif config not in train_by_config:
            segment = "unseen_configuration"
        elif not seller:
            segment = "unknown_seller"
        else:
            stores = train_by_config[config]
            other_store_prices = [median(prices) for store, prices in stores.items() if store and store != seller]
            if other_store_prices:
                segment = "seen_other_store"
            elif all(stores):
                segment = "seen_same_store_only"
            else:
                segment = "unknown_seller"
        context.append({
            "cross_store_group": segment,
            "other_store_count": len(other_store_prices),
            "other_store_median_price_vnd": median(other_store_prices) if other_store_prices else np.nan,
        })
    return pd.DataFrame(context, index=split.X_test.index)


def test_rows_for_audit(split):
    columns = CONFIG_COLUMNS + ["seller_name", "screen_size_inch"]
    rows = split.test_metadata.join(split.X_test[columns]).join(cross_store_context(split))
    rows["recorded_price_vnd"] = split.y_test
    rows["ram_status"] = np.where(
        pd.to_numeric(rows["ram_gb"], errors="coerce").isna(), "missing", "present"
    )
    prices = rows["recorded_price_vnd"]
    rows["price_tier"] = np.select(
        [prices < 10_000_000, prices < 20_000_000, prices <= 35_000_000],
        ["under_10m", "10m_to_under_20m", "20m_to_35m"],
        default="over_35m",
    )
    return rows


def prediction_rows(test_rows, category, model_key, predictions):
    rows = test_rows.copy()
    rows["category"] = category
    rows["model"] = model_key
    rows["predicted_price_vnd"] = predictions
    rows["signed_error_vnd"] = rows["predicted_price_vnd"] - rows["recorded_price_vnd"]
    rows["absolute_error_vnd"] = rows["signed_error_vnd"].abs()
    rows["absolute_percentage_error_pct"] = 100 * rows["absolute_error_vnd"] / rows["recorded_price_vnd"]
    return rows


def summarize_errors(predictions, dimension):
    summary = (
        predictions.groupby(GROUP_COLUMNS + [dimension], dropna=False)
        .agg(
            n_test=("absolute_error_vnd", "size"),
            mae_vnd=("absolute_error_vnd", "mean"),
            mape_pct=("absolute_percentage_error_pct", "mean"),
            mean_signed_error_vnd=("signed_error_vnd", "mean"),
        )
        .reset_index()
        .rename(columns={dimension: "segment"})
    )
    summary.insert(2, "dimension", dimension)
    return summary


def audit_hypotheses(top):
    """Label review leads, not verified causes of prediction errors."""
    is_laptop = top["category"].eq("laptop")
    desktop_name = top["product_name"].str.contains(
        r"\b(?:imac|mac\s*(?:studio|mini|pro))\b", case=False, na=False
    )
    screen = pd.to_numeric(top["screen_size_inch"], errors="coerce")
    bad_screen = (is_laptop & ((screen < 10) | (screen > 20))) | (
        ~is_laptop & ((screen < 3) | (screen > 11))
    )
    other_prices = top["other_store_median_price_vnd"]
    seller_gap = (top["recorded_price_vnd"] - other_prices).abs() / other_prices
    high_price = top["recorded_price_vnd"] >= 80_000_000
    top["audit_hypothesis"] = np.select(
        [is_laptop & desktop_name, bad_screen, seller_gap >= 0.20, high_price],
        ["review_category", "review_screen_spec", "review_cross_store_price_gap", "review_high_price"],
        default="requires_manual_review",
    )
    top["other_store_price_gap_pct"] = 100 * seller_gap
    return top


def top20_audit(predictions):
    # Select 20 distinct products, using the worst model error for each listing.
    top = (
        predictions.sort_values(["absolute_error_vnd", "listing_record_id", "model"], ascending=[False, True, True])
        .drop_duplicates("listing_record_id")
        .head(20)
    )
    tv7 = load_tv7_flags(["combined_flag", "anomaly_severity", "anomaly_reasons"])
    top = top.merge(tv7, on="listing_record_id", how="left", validate="one_to_one", indicator="tv7_join")
    top.insert(0, "rank", np.arange(1, len(top) + 1))
    return audit_hypotheses(top)


def write_error_tables(predictions, out_dir):
    tables = {
        "test_predictions.csv": predictions,
        "table_10_3_error_by_price_tier.csv": summarize_errors(predictions, "price_tier"),
        "table_10_4_error_by_brand_and_seller.csv": pd.concat([
            summarize_errors(predictions, "brand"), summarize_errors(predictions, "seller_name"),
        ]),
        "table_10_5_error_by_stock_and_missingness.csv": pd.concat([
            summarize_errors(predictions, "availability_status"), summarize_errors(predictions, "ram_status"),
        ]),
        "table_10_6_cross_store_generalization.csv": summarize_errors(predictions, "cross_store_group"),
        "table_10_7_top20_worst_predictions_audit.csv": top20_audit(predictions),
    }
    for name, table in tables.items():
        table.to_csv(out_dir / name, index=False, encoding="utf-8-sig")
