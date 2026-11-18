import joblib
import numpy as np
from catboost import CatBoostRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import TransformedTargetRegressor
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from config import *
from features import *
from utils import *


def train_and_eval(X, y, groups, category, cat_features):
    X_train, X_test, y_train, y_test, groups_train = split_by_group(X, y, groups)

    pipeline = Pipeline(
        steps=[
            ('features_engineer', HardwareFeatureEngineer(category=category, cat_dtype='str')),
            ('model', CatBoostRegressor(cat_features=tuple(cat_features), random_seed=RANDOM_STATE, verbose=0))
        ]
    )
    model = TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)

    param_distributions = {
        'regressor__model__iterations': [500, 800, 1200],
        'regressor__model__learning_rate': [0.03, 0.05, 0.08],
        'regressor__model__depth': [4, 6, 8],
        'regressor__model__l2_leaf_reg': [1, 3, 5, 10],
        'regressor__model__random_strength': [0.5, 1.0, 2.0]
    }

    gkf = GroupKFold(n_splits=10)
    search = RandomizedSearchCV(
        model, param_distributions, n_iter=25, cv=gkf,
        scoring='neg_mean_absolute_error', random_state=RANDOM_STATE, n_jobs=1
    )
    search.fit(X_train, y_train, groups=groups_train)
    best_model = search.best_estimator_
    y_pred = best_model.predict(X_test)

    return best_model, evaluate_metrics(y_test, y_pred)


if __name__ == '__main__':
    df_lap, df_sma = load_and_split_data(CLEANED_DATA_PATH, PROCESSED_DATA_PATH)
    X_lap, y_lap, g_lap = prepare_raw_data(df_lap)
    X_sma, y_sma, g_sma = prepare_raw_data(df_sma)

    results = {}

    cb_result_dir = RESULTS_DIR / 'catboost'
    cb_result_dir.mkdir(parents=True, exist_ok=True)

    print("Training CatBoost (Laptop)")
    model_lap, metrics_lap = train_and_eval(X_lap, y_lap, g_lap, 'laptop', LAPTOP_CAT_FEATURES)
    joblib.dump(model_lap, cb_result_dir / 'cb_laptop.pkl')
    results['laptop'] = metrics_lap

    print("Training CatBoost (Smartphone)")
    model_sma, metrics_sma = train_and_eval(X_sma, y_sma, g_sma, 'smartphone', SMARTPHONE_CAT_FEATURES)
    joblib.dump(model_sma, cb_result_dir / 'cb_smartphone.pkl')
    results['smartphone'] = metrics_sma

    save_metrics(results, METRICS_DIR / 'cb_scores.json')
    print("CatBoost model trained and saved successfully")
