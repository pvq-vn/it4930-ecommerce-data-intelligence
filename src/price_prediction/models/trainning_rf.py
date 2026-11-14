import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.model_selection import GroupKFold, RandomizedSearchCV
from config import *
from features import *
from utils import *


def build_rf_pipeline(num_features, cat_features):
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), cat_features)
        ],
        remainder='passthrough'
    )

    rf = RandomForestRegressor(random_state=RANDOM_STATE)
    pipeline = Pipeline(
        steps=[
            ('preprocessor', preprocessor),
            ('model', rf)
        ]
    )

    return TransformedTargetRegressor(regressor=pipeline, func=np.log1p, inverse_func=np.expm1)

def train_and_eval(X, y, groups, num_features, cat_features):
    X_train, X_test, y_train, y_test, groups_train = split_by_group(X, y, groups)
    model = build_rf_pipeline(num_features, cat_features)

    param_distributions = {
        'regressor__model__n_estimators': [200, 300, 500],
        'regressor__model__max_depth': [12, 18, 25, None],
        'regressor__model__min_samples_split': [2, 5, 10, 15],
        'regressor__model__min_samples_leaf': [1, 2, 4, 8],
        'regressor__model__max_features': ['sqrt', 0.5, 0.7, 1.0]
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

    X_lap, y_lap, g_lap = prepare_modeling_data(df_lap, LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES)
    X_sma, y_sma, g_sma = prepare_modeling_data(df_sma, SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES)

    results = {}

    rf_result_dir = RESULTS_DIR / 'random_forest'
    rf_result_dir.mkdir(parents=True, exist_ok=True)

    print("Training Random Forest (Laptop)")
    model_lap, metrics_lap = train_and_eval(X_lap, y_lap, g_lap, LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES)
    joblib.dump(model_lap, rf_result_dir / 'rf_laptop.pkl')
    results['laptop'] = metrics_lap

    print("Training Random Forest (Smartphone)")
    model_sma, metrics_sma = train_and_eval(X_sma, y_sma, g_sma, SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES)
    joblib.dump(model_sma, rf_result_dir / 'rf_smartphone.pkl')
    results['smartphone'] = metrics_sma

    save_metrics(results, METRICS_DIR / 'rf_scores.json')
    print("Random Forest model trained and saved successfully")
