import joblib
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from config import *
from features import *
from utils import *


def build_ridge_pipeline(category, num_features, cat_features):
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', RobustScaler(), num_features),
            ('cat', OneHotEncoder(handle_unknown='ignore'), cat_features)
        ]
    )

    pipeline = Pipeline(
        steps=[
            ('features_engineer', HardwareFeatureEngineer(category=category)),
            ('preprocessor', preprocessor),
            ('model', Ridge(alpha=1.0))
        ]
    )

    return TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)

def train_and_eval(X, y, groups, category, num_features, cat_features):
    X_train, X_test, y_train, y_test, _ = split_by_group(X, y, groups)
    model = build_ridge_pipeline(category, num_features, cat_features)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    return model, evaluate_metrics(y_test, y_pred)

if __name__ == '__main__':
    df_lap, df_sma = load_and_split_data(CLEANED_DATA_PATH, PROCESSED_DATA_PATH)
    X_lap, y_lap, g_lap = prepare_raw_data(df_lap)
    X_sma, y_sma, g_sma = prepare_raw_data(df_sma)

    results = {}

    baseline_result_dir = RESULTS_DIR / 'ridge'
    baseline_result_dir.mkdir(parents=True, exist_ok=True)

    print("Training Ridge Baseline (Laptop)")
    model_lap, metrics_lap = train_and_eval(X_lap, y_lap, g_lap, 'laptop', LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES)
    joblib.dump(model_lap, baseline_result_dir / 'ridge_laptop.pkl')
    results['laptop'] = metrics_lap

    print("Training Ridge Baseline (Smartphone)")
    model_sma, metrics_sma = train_and_eval(X_sma, y_sma, g_sma, 'smartphone', SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES)
    joblib.dump(model_sma, baseline_result_dir / 'ridge_smartphone.pkl')
    results['smartphone'] = metrics_sma

    save_metrics(results, METRICS_DIR / 'baseline_scores.json')
    print("Baseline model trained and saved successfully")
