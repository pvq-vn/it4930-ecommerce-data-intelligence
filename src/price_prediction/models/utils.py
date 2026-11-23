import json
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from config import *


def prepare_raw_data(df: pd.DataFrame):
    y = df[TARGET_COL].copy()
    groups = df[GROUP_COL].copy()
    drop_cols = [c for c in [TARGET_COL, GROUP_COL] if c in df.columns]
    X = df.drop(columns=drop_cols).copy()
    return X, y, groups

def _apply_anomaly_train_filter(X_train: pd.DataFrame, y_train: pd.Series, groups_train: pd.Series, mode: str = ANOMALY_FILTER_MODE):
    mode = (mode or 'none').lower().strip()
    
    VALID_MODES = {'none', 'extreme_only', 'drop_combined'}
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid ANOMALY_FILTER_MODE='{mode}'. Must be one of {VALID_MODES}")

    if 'anomaly_severity' not in X_train.columns:
        print(f"[Anomaly Filter] mode={mode} | WARNING: 'anomaly_severity' not found in X_train!")
        return X_train, y_train, groups_train

    if mode == 'none':
        X_clean = X_train.drop(columns=['anomaly_severity'], errors='ignore')
        print(f"[Anomaly Filter] mode={mode} | kept {len(X_clean)}/{len(X_train)} train rows")
        return X_clean, y_train, groups_train

    sev = X_train['anomaly_severity'].fillna('none').astype(str).str.lower().str.strip()
    if mode == 'extreme_only':
        keep_mask = sev != 'extreme'
    elif mode == 'drop_combined':
        keep_mask = sev == 'none'
    else:
        keep_mask = pd.Series(True, index=X_train.index)

    X_clean = X_train.loc[keep_mask].drop(columns=['anomaly_severity'], errors='ignore')
    print(f"[Anomaly Filter] mode={mode} | kept {len(X_clean)}/{len(X_train)} train rows")
    return X_clean, y_train.loc[keep_mask], groups_train.loc[keep_mask]

def split_by_group(X: pd.DataFrame, y: pd.Series, groups: pd.Series, test_size=0.2, anomaly_filter_mode: str = ANOMALY_FILTER_MODE):
    gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=RANDOM_STATE)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    X_train_raw = X.iloc[train_idx]
    y_train_raw = y.iloc[train_idx]
    groups_train_raw = groups.iloc[train_idx]

    X_test = X.iloc[test_idx].drop(columns=['anomaly_severity'], errors='ignore')
    y_test = y.iloc[test_idx]

    X_train, y_train, groups_train = _apply_anomaly_train_filter(X_train_raw, y_train_raw, groups_train_raw, mode=anomaly_filter_mode)

    return X_train, X_test, y_train, y_test, groups_train

def evaluate_metrics(y_true, y_pred):
    return {
        'mae': float(mean_absolute_error(y_true, y_pred)),
        'rmse': float(np.sqrt(mean_squared_error(y_true, y_pred))),
        'r2': float(r2_score(y_true, y_pred))
    }

def save_metrics(metrics, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=4)
