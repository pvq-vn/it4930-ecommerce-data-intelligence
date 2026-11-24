"""Join TV6 parent-level review features and fit a train-only brand prior."""

import hashlib
import subprocess
from io import BytesIO

import numpy as np
import pandas as pd

from prepare_test_data import REPO_ROOT
from tv4_features import TV4FeatureEngineer, UNKNOWN_LABELS


TV6_COMMIT = "1d53f974d87bbaf3329c0ec51abf7da61ef7143c"
PARENT_KEY = "source_parent_id"
COUNT_COLUMNS = ["has_review_data", "review_count_usable"]
MEAN_SENTIMENT = "avg_sentiment_score"
SENTIMENT_COLUMNS = [
    MEAN_SENTIMENT, "sentiment_positive_ratio",
    "aspect_sentiment_score_battery_power", "aspect_sentiment_score_performance_thermal",
    "aspect_sentiment_score_display_design", "aspect_sentiment_score_camera_audio",
    "aspect_sentiment_score_service_logistics",
]
BRAND_PRIOR = "brand_sentiment_prior"


def load_tv6_reviews():
    artifact = subprocess.check_output(
        ["git", "show", f"{TV6_COMMIT}:data/tv6/tv5_review_features.csv"], cwd=REPO_ROOT,
    )
    features = [*COUNT_COLUMNS, *SENTIMENT_COLUMNS]
    table = pd.read_csv(BytesIO(artifact), usecols=[PARENT_KEY, "category", *features], dtype={PARENT_KEY: str})
    if table[PARENT_KEY].isna().any() or table[PARENT_KEY].duplicated().any():
        raise ValueError("Expected one TV6 row per source parent.")
    numeric = table[features].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(numeric).all().all():
        raise ValueError("TV6 review features must be finite, including absence encoded as zero.")
    count = numeric["review_count_usable"]
    if count.lt(0).any() or count.mod(1).ne(0).any() or not numeric["has_review_data"].eq(count.gt(0)).all():
        raise ValueError("TV6 review counts and coverage flags disagree.")
    if not numeric.loc[count.eq(0), SENTIMENT_COLUMNS].eq(0).all().all():
        raise ValueError("Expected zero placeholders on TV6 rows with no reviews.")
    table[features] = numeric
    return table.set_index(PARENT_KEY), hashlib.sha256(artifact).hexdigest()


def add_tv6_inputs(X, metadata, reviews, category):
    if not X.index.equals(metadata.index):
        raise ValueError("TV6 metadata is not aligned with model rows.")
    parents = metadata[PARENT_KEY]
    if not parents.isin(reviews.index).all() or not parents.map(reviews["category"]).eq(category).all():
        raise ValueError(f"TV6 parent/category join failed for {category}.")
    result = X.copy()
    result[PARENT_KEY] = parents
    for field in [*COUNT_COLUMNS, *SENTIMENT_COLUMNS]:
        result[field] = parents.map(reviews[field])
    return result


class TV6FeatureEngineer(TV4FeatureEngineer):
    def __init__(self, category, cat_dtype="str", include_sentiment=True):
        super().__init__(category, cat_dtype)
        self.include_sentiment = include_sentiment

    def fit(self, X, y=None):
        super().fit(X)
        if self.include_sentiment:
            observed = X["has_review_data"].eq(1)
            parents = pd.DataFrame({
                PARENT_KEY: X.loc[observed, PARENT_KEY],
                "brand": self._brand(X.loc[observed]),
                "sentiment": X.loc[observed, MEAN_SENTIMENT],
            })
            # Variants share a parent score and contribute once to the prior.
            self.reviewed_parents_ = parents.drop_duplicates(PARENT_KEY).set_index(PARENT_KEY)
            conflicted = parents.groupby(PARENT_KEY)["brand"].nunique().gt(1)
            brand_usable = ~self.reviewed_parents_["brand"].isin(UNKNOWN_LABELS) & ~conflicted
            self.brand_totals_ = self.reviewed_parents_.loc[brand_usable].groupby("brand")["sentiment"].agg(["sum", "count"])
            self.global_sum_ = float(self.reviewed_parents_["sentiment"].sum())
            self.parent_brand_ = self.reviewed_parents_.loc[brand_usable, "brand"]
        return self

    def brand_prior(self, X):
        parent = X[PARENT_KEY]
        brand = self._brand(X)
        own_score = parent.map(self.reviewed_parents_["sentiment"])
        own_brand = parent.map(self.parent_brand_)
        same_brand = own_brand.eq(brand).fillna(False)

        # Leave the queried parent out when it appears in the training catalog.
        own_contribution = own_score.fillna(0)
        brand_sum = brand.map(self.brand_totals_["sum"]).fillna(0) - own_contribution.where(same_brand, 0)
        brand_count = brand.map(self.brand_totals_["count"]).fillna(0) - same_brand.astype(int)
        global_count = len(self.reviewed_parents_) - own_score.notna().astype(int)
        global_prior = (self.global_sum_ - own_contribution) / global_count.where(global_count.gt(0))
        prior = brand_sum / brand_count.where(brand_count.gt(0))
        return prior.fillna(global_prior).fillna(0)

    def transform(self, X):
        result = super().transform(X)
        result[COUNT_COLUMNS] = X[COUNT_COLUMNS]
        if self.include_sentiment:
            result[SENTIMENT_COLUMNS] = X[SENTIMENT_COLUMNS]
            result[BRAND_PRIOR] = self.brand_prior(X)
        return result
