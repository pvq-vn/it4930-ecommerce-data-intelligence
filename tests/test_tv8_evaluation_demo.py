"""Regression checks for the TV8 handover and its pinned TV5 evaluation."""

import hashlib
import json
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "src" / "evaluation_demo"
OUTPUT = DEMO / "outputs"
CATEGORIES = {"laptop": (3227, 819), "smartphone": (3300, 797)}
MODELS = ("ridge", "rf", "lgbm")
TABLES = {
    "table_10_1_model_benchmark_3d.csv": {"category", "model", "mae_vnd", "rmse_vnd", "r2", "mae_change_pct"},
    "table_10_2_ablation_and_tv7_sensitivity.csv": {"stage", "category", "model", "n_train", "n_test", "mae_vnd"},
    "table_10_3_error_by_price_tier.csv": {"segment", "n_test", "mae_vnd"},
    "table_10_4_error_by_brand_and_seller.csv": {"dimension", "segment", "n_test", "mae_vnd"},
    "table_10_5_error_by_stock_and_missingness.csv": {"dimension", "segment", "n_test", "mae_vnd"},
    "table_10_6_cross_store_generalization.csv": {"segment", "n_test", "mae_vnd"},
    "table_10_7_top20_worst_predictions_audit.csv": {"listing_record_id", "rank", "anomaly_severity", "absolute_error_vnd"},
}
FIGURES = [
    "fig_10_1_residual_and_actual_vs_pred.png",
    "fig_10_2_error_by_price_tier_and_seller.png",
    "fig_10_3_ablation_and_sensitivity_chart.png",
    "fig_10_4_shap_summary_laptop.png",
    "fig_10_5_shap_summary_smartphone.png",
    "fig_10_6_shap_waterfall_examples.png",
    "fig_10_7_monotonicity_sanity_check.png",
]
SCREENSHOTS = ["01_du_doan_gia.jpg", "02_so_sanh_mo_hinh.jpg", "03_phan_tich_sai_so.jpg", "04_giai_thich_mo_hinh.jpg"]
ALIAS_EXAMPLE = {
    "brand": "apple", "model_clean": "iphone 15 pro max", "seller_name": "fpt shop",
    "cpu_model": "apple a17 pro", "ram_gb": 8, "storage_gb": 256, "screen_size_inch": 6.7,
}


@pytest.fixture(scope="module")
def api():
    with pytest.MonkeyPatch.context() as patch:
        patch.syspath_prepend(str(DEMO))
        yield import_module("demo_data")


@pytest.fixture(scope="module")
def splits(api):
    return api.load_demo_data()


@pytest.fixture(scope="module")
def models(api, splits):
    return {(category, key): api.load_demo_model(category, key) for category in splits for key in MODELS}


@pytest.fixture(scope="module")
def benchmark():
    return pd.read_csv(OUTPUT / "tables" / next(iter(TABLES))).set_index(["category", "model"])


@pytest.mark.parametrize("category", CATEGORIES)
def test_frozen_splits_are_disjoint_and_preserve_test_ids(splits, category):
    split = splits[category]
    assert (len(split.X_train), len(split.X_test)) == CATEGORIES[category]
    assert split.X_train.index.equals(split.y_train.index)
    assert split.X_test.index.equals(split.y_test.index)
    assert split.X_test.index.equals(split.test_metadata.index)
    assert set(split.train_metadata["source_parent_id"]).isdisjoint(split.test_metadata["source_parent_id"])
    assert not {"price_vnd", "source_parent_id", "listing_record_id"}.intersection(split.X_test.columns)
    manifest = json.loads((OUTPUT / "models" / "s4_tv6" / "manifest.json").read_text(encoding="utf-8"))
    reference = next(row for row in manifest["models"] if row["category"] == category)
    test_ids = "\n".join(split.test_metadata["listing_record_id"]).encode()
    assert hashlib.sha256(test_ids).hexdigest() == reference["test_ids_sha256"]


@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("key", MODELS)
def test_tv5_model_reproduces_benchmark(models, splits, benchmark, category, key):
    split = splits[category]
    prediction = models[category, key].predict(split.X_test)
    assert prediction.shape == (CATEGORIES[category][1],)
    assert np.isfinite(prediction).all()
    error = prediction - split.y_test.to_numpy()
    row = benchmark.loc[category, key]
    assert np.abs(error).mean() == pytest.approx(row["mae_vnd"], rel=1e-8)
    assert np.sqrt(np.mean(error ** 2)) == pytest.approx(row["rmse_vnd"], rel=1e-8)


def test_apple_fpt_alias_preserves_reference_price(api, splits, models):
    category = "smartphone"
    aliased = api.prediction_frame(ALIAS_EXAMPLE, category, splits[category])
    canonical = api.prediction_frame({
        **ALIAS_EXAMPLE, "brand": "Apple", "model_clean": "iPhone 15 Pro Max",
        "seller_name": "FPT", "cpu_model": "Apple A17 Pro",
    }, category, splits[category])
    pd.testing.assert_frame_equal(aliased, canonical)
    price = models[category, "rf"].predict(aliased)[0]
    assert price == pytest.approx(24_892_339, abs=2)


@pytest.mark.parametrize("key", MODELS)
def test_demo_contributions_reconstruct_prediction(api, splits, models, key):
    category = "smartphone"
    split = splits[category]
    frame = api.prediction_frame(ALIAS_EXAMPLE, category, split)
    model = models[category, key]
    baseline, contributions = api.local_explanation(model, key, frame, split.X_train)
    assert contributions["feature"].is_unique
    assert np.isfinite(contributions["delta_vnd"]).all()
    assert baseline + contributions["delta_vnd"].sum() == pytest.approx(model.predict(frame)[0], rel=1e-7)


def test_nearby_catalog_is_ranked_independently_of_price(api, splits):
    catalog = api.build_catalog(splits)
    assert len(catalog) == 8143 and catalog["listing_record_id"].is_unique
    product = api.prediction_frame(ALIAS_EXAMPLE, "smartphone", splits["smartphone"]).iloc[0].to_dict()
    matches = api.similar_listings(catalog, "smartphone", product)
    alternative = api.similar_listings(catalog.assign(price_vnd=-catalog["price_vnd"]), "smartphone", product)
    assert len(matches) == 5
    assert matches["category_clean"].eq("smartphone").all()
    assert not matches.duplicated(["seller_name", "brand", "model_clean", "cpu_model", "gpu_model", "ram_gb", "storage_gb"]).any()
    assert matches["listing_record_id"].tolist() == alternative["listing_record_id"].tolist()


@pytest.mark.parametrize("filename", TABLES)
def test_report_tables_are_readable(filename):
    table = pd.read_csv(OUTPUT / "tables" / filename)
    assert not table.empty and TABLES[filename] <= set(table.columns)
    if filename.startswith("table_10_2"):
        assert table.groupby("stage").size().to_dict() == {stage: 6 for stage in ("S1", "S2", "S3", "S4", "S5a", "S5b")}
        assert not table.duplicated(["stage", "category", "model"]).any()
    if filename.startswith("table_10_7"):
        assert len(table) == 20 and table["listing_record_id"].is_unique


@pytest.mark.parametrize("filename", FIGURES)
def test_report_figures_are_valid_300_dpi_png(filename):
    with Image.open(OUTPUT / "figures" / filename) as image:
        assert image.format == "PNG"
        assert image.size[0] >= 2400
        assert image.info.get("dpi") == pytest.approx((300, 300), abs=0.5)
        image.verify()


@pytest.mark.parametrize("filename", SCREENSHOTS)
def test_demo_screenshots_are_valid_jpeg(filename):
    with Image.open(OUTPUT / "demo_screenshots" / filename) as image:
        assert image.format == "JPEG" and image.size[0] >= 1200
        image.verify()


def test_app_can_submit_prediction(api):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(DEMO / "app.py"), default_timeout=60).run()
    assert [tab.label for tab in app.tabs] == ["Dự đoán giá", "So sánh mô hình", "Phân tích sai số", "Giải thích mô hình"]
    assert not app.exception and not app.error
    next(button for button in app.button if button.label == "Dự đoán giá").click().run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "23.498.571 đ"
