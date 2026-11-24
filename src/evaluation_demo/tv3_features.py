"""Train-only preprocessing for the S2 TV3 feature experiment."""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from prepare_test_data import use_tv5_modules


TV3_NUM_FEATURES = ["is_out_of_stock", "charger_watt", "is_charger_missing"]


def add_tv3_inputs(split):
    """Use listing-aligned metadata without changing TV5's original inputs."""
    enriched = []
    for X, metadata in (
        (split.X_train, split.train_metadata), (split.X_test, split.test_metadata),
    ):
        if not X.index.equals(metadata.index):
            raise ValueError("TV3 metadata is not aligned with the model rows.")
        result = X.copy()
        for field in ("availability_status", "charger_watt"):
            result[field] = metadata[field]
        enriched.append(result)
    return tuple(enriched)


class TV3FeatureEngineer(TransformerMixin, BaseEstimator):
    """Preserve TV5 features, sanitize screen=300, and add stock and optional charger fields."""

    # S2 artifacts saved before this option was added used the charger fields.
    include_charger = True

    def __init__(self, category, cat_dtype="str", include_charger=True):
        self.category = category
        self.cat_dtype = cat_dtype
        self.include_charger = include_charger

    @staticmethod
    def _sanitize_screen(X):
        result = X.copy()
        screen = pd.to_numeric(result["screen_size_inch"], errors="coerce")
        result["screen_size_inch"] = screen.mask(screen.eq(300))
        return result

    @staticmethod
    def _charger(X):
        values = pd.to_numeric(X["charger_watt"], errors="coerce")
        return values.where(np.isfinite(values) & values.gt(0))

    @staticmethod
    def _brand(X):
        return X["brand"].fillna("unknown").astype(str).str.casefold().str.strip()

    def fit(self, X, y=None):
        use_tv5_modules()
        from features import HardwareFeatureEngineer

        clean = self._sanitize_screen(X)
        self.base_ = HardwareFeatureEngineer(self.category, self.cat_dtype).fit(clean)
        if self.include_charger:
            charger = self._charger(clean)
            self.charger_by_brand_ = charger.groupby(self._brand(clean)).median().dropna().to_dict()
            median = charger.median()
            self.charger_global_ = 0.0 if pd.isna(median) else float(median)
        return self

    def transform(self, X):
        clean = self._sanitize_screen(X)
        result = self.base_.transform(clean)
        stock = clean["availability_status"].fillna("unknown").astype(str).str.casefold().str.strip()
        # Zero means "not marked out_of_stock"; it does not assert in_stock.
        result["is_out_of_stock"] = stock.eq("out_of_stock").astype(int)
        if self.include_charger:
            charger = self._charger(clean)
            result["is_charger_missing"] = charger.isna().astype(int)
            fill = self._brand(clean).map(self.charger_by_brand_).fillna(self.charger_global_)
            result["charger_watt"] = charger.fillna(fill)
        return result
