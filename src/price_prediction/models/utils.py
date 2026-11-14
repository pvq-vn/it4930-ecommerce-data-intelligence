import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from config import *


def prepare_modeling_data(df: pd.DataFrame, num_features: list, cat_features: list, cat_dtype='str'):
    X = df[num_features + cat_features].copy()
    y = df[TARGET_COL].copy()
    groups = df[GROUP_COL].copy()

    for col in cat_features:
        if cat_dtype == 'category':
            X[col] = X[col].astype('category')

    return X, y, groups

def split_by_group(X: pd.DataFrame, y: pd.DataFrame, groups: pd.DataFrame, test_size=0.2):
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))
    return X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx], groups.iloc[train_idx]

def evaluate_metrics(y_true, y_pred):
    return {
        'mae': float(mean_absolute_error(y_true, y_pred)),
        'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
        'r2': float(r2_score(y_true, y_pred))
    }

def save_metrics(metrics, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=4)
