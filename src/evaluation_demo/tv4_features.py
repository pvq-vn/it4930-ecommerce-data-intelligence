"""Attach TV4 hardware scores and learn a price-free store count from train."""

import hashlib
import subprocess
from collections import defaultdict
from io import BytesIO

import numpy as np
import pandas as pd

from error_analysis import configuration_and_store
from prepare_test_data import REPO_ROOT
from tv3_features import TV3FeatureEngineer, add_tv3_inputs


TV4_ARTIFACT_COMMIT = "a4874b0da26a1366fe3871e1b930633315acbc6c"
BENCHMARK_COLUMNS = {
    "laptop": ["cpu_perf_rating", "gpu_perf_rating"],
    "smartphone": ["cpu_benchmark_score"],
}
SELLER_COUNT = "hw_seller_count"
UNKNOWN_LABELS = {"", "unknown", "n/a", "none", "null"}


def load_tv4_benchmarks(category):
    path = f"data/market_graph/{category}_benchmarks.csv"
    artifact = subprocess.check_output(
        ["git", "show", f"{TV4_ARTIFACT_COMMIT}:{path}"], cwd=REPO_ROOT,
    )
    key = "listing_record_id"
    columns = BENCHMARK_COLUMNS[category]
    scores = pd.read_csv(BytesIO(artifact), usecols=[key, *columns], dtype={key: str})
    if scores[key].isna().any() or scores[key].duplicated().any():
        raise ValueError(f"Invalid listing keys in {path}")
    for column in columns:
        values = pd.to_numeric(scores[column], errors="coerce")
        scores[column] = values.where(np.isfinite(values) & values.gt(0))
    return scores.set_index(key)[columns], hashlib.sha256(artifact).hexdigest()


def add_tv4_inputs(split, benchmark_scores):
    """Map scores onto the original row indices without adding listing IDs to X."""
    enriched = []
    for X, metadata in zip(add_tv3_inputs(split), (split.train_metadata, split.test_metadata)):
        ids = metadata["listing_record_id"]
        if not ids.isin(benchmark_scores.index).all():
            raise ValueError("Some model rows do not match the pinned TV4 artifact.")
        result = X.drop(columns="charger_watt")
        for column in benchmark_scores.columns:
            result[column] = ids.map(benchmark_scores[column])
        enriched.append(result)
    return tuple(enriched)


def valid_configurations(X):
    for config, seller in configuration_and_store(X):
        if config is not None:
            brand, model, ram, storage = config
            if brand in UNKNOWN_LABELS or model in UNKNOWN_LABELS or not (
                np.isfinite(ram) and ram > 0 and np.isfinite(storage) and storage > 0
            ):
                config = None
        yield config, seller if seller not in UNKNOWN_LABELS else ""


class TV4FeatureEngineer(TV3FeatureEngineer):
    """S2A preprocessing plus benchmark columns and the training catalog count."""

    def __init__(self, category, cat_dtype="str"):
        super().__init__(category, cat_dtype, include_charger=False)

    def fit(self, X, y=None):
        super().fit(X)
        columns = BENCHMARK_COLUMNS[self.category]
        self.benchmark_medians_ = X[columns].median()
        if self.benchmark_medians_.isna().any():
            raise ValueError(f"A TV4 score has no training observations for {self.category}")

        sellers_by_configuration = defaultdict(set)
        for config, seller in valid_configurations(X):
            if config is not None and seller:
                sellers_by_configuration[config].add(seller)
        self.sellers_by_configuration_ = dict(sellers_by_configuration)
        return self

    def store_counts(self, X):
        counts = []
        for config, seller in valid_configurations(X):
            if config is None or not seller:
                counts.append(0)
            else:
                other_sellers = self.sellers_by_configuration_.get(config, set()) - {seller}
                counts.append(1 + len(other_sellers))
        return pd.Series(counts, index=X.index, name=SELLER_COUNT, dtype=int)

    def transform(self, X):
        result = super().transform(X)
        columns = BENCHMARK_COLUMNS[self.category]
        result[columns] = X[columns].fillna(self.benchmark_medians_)
        result[SELLER_COUNT] = self.store_counts(X)
        return result
