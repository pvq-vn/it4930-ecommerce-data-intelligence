import joblib
import numpy as np
from lightgbm import LGBMRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from config import *
from features import *
from utils import *


def train_and_eval(X, y, groups, num_features, cat_features):
    X_train, X_test, y_train, y_test, groups_train = split_by_group(X, y, groups)
    model = TransformedTargetRegressor(regressor=LGBMRegressor(random_state=RANDOM_STATE, verbose=-1), func=np.log1p, inverse_func=np.expm1)

    param_distributions = {
        'regressor__n_estimators': [200, 400, 600, 800],
        'regressor__learning_rate': [0.02, 0.05, 0.08, 0.1],
        'regressor__num_leaves': [15, 31, 45, 63],
        'regressor__min_child_samples': [10, 20, 35, 50],
        'regressor__subsample': [0.7, 0.85, 1.0],
        'regressor__subsample_freq': [1],
        'regressor__colsample_bytree': [0.6, 0.8, 1.0],
        'regressor__reg_alpha': [0.0, 0.1, 1.0],
        'regressor__reg_lambda': [0.0, 1.0, 5.0]
    }

    gkf = GroupKFold(n_splits=10)
    search = RandomizedSearchCV(model, param_distributions, n_iter=25, cv=gkf, scoring='neg_mean_absolute_error', random_state=RANDOM_STATE, n_jobs=-1)
    search.fit(X_train, y_train, groups=groups_train)
    best_model = search.best_estimator_
    y_pred = best_model.predict(X_test)

    return best_model, evaluate_metrics(y_test, y_pred)

if __name__ == '__main__':
    df_laptop_raw, df_smartphone_raw = load_and_split_data(CLEANED_DATA_PATH, PROCESSED_DATA_PATH)

    df_lap = engineer_laptop(df_laptop_raw)
    df_sma = engineer_smartphone(df_smartphone_raw)

    X_lap, y_lap, g_lap = prepare_modeling_data(df_lap, LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES, cat_dtype='category')
    X_sma, y_sma, g_sma = prepare_modeling_data(df_sma, SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES, cat_dtype='category')

    results = {}

    lgbm_result_dir = RESULTS_DIR / 'lightgbm'
    lgbm_result_dir.mkdir(parents=True, exist_ok=True)

    print("Training LightGBM (Laptop)")
    model_lap, metrics_lap = train_and_eval(X_lap, y_lap, g_lap, LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES)
    joblib.dump(model_lap, lgbm_result_dir / 'lgbm_laptop.pkl')
    results['laptop'] = metrics_lap

    print("Training LightGBM (Smartphone)")
    model_sma, metrics_sma = train_and_eval(X_sma, y_sma, g_sma, SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES)
    joblib.dump(model_sma, lgbm_result_dir / 'lgbm_smartphone.pkl')
    results['smartphone'] = metrics_sma

    save_metrics(results, METRICS_DIR / 'lgbm_scores.json')
    print("LightGBM model trained and saved successfully")
