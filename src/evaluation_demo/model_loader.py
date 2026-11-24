import sys

from prepare_test_data import TV5_MODELS_DIR, prepare_tv5_splits, use_tv5_modules


MODEL_FOLDERS = {
    "ridge": "ridge",
    "rf": "random_forest",
    "lgbm": "lightgbm",
}
SELLER_ALIASES = {
    "fpt shop": "fpt",
    "fptshop": "fpt",
    "cellphone s": "cellphones",
    "thế giới di động": "tgdđ",
    "hoàng hà mobile": "hoàng hà",
    "hoanghamobile": "hoàng hà",
    "viettel store": "viettel",
}


def model_path(category, model_key):
    if category not in {"laptop", "smartphone"}:
        raise ValueError(f"Loai thiet bi khong ho tro: {category}")
    model_dir = MODEL_FOLDERS[model_key]
    return TV5_MODELS_DIR / "results" / model_dir / f"{model_key}_{category}.pkl"


def load_model(category, model_key):
    """Load the trained model whose file was committed by TV5."""
    path = model_path(category, model_key)
    use_tv5_modules()

    try:
        import joblib

        return joblib.load(path)
    except ModuleNotFoundError as exc:
        if exc.name not in {"joblib", "lightgbm"}:
            raise
        raise SystemExit(
            f"Python dang chay: {sys.executable}\n"
            "Hay chay python -m pip install joblib lightgbm trong moi truong TV8."
        ) from None


def canonicalize_input(product, category, X_train):
    """Map spelling and capitalization to category labels found in TV5 training data."""
    use_tv5_modules()
    from config import LAPTOP_CAT_FEATURES, SMARTPHONE_CAT_FEATURES

    columns = LAPTOP_CAT_FEATURES if category == "laptop" else SMARTPHONE_CAT_FEATURES
    result = dict(product)
    for column in columns:
        value = result.get(column)
        if not isinstance(value, str):
            continue
        known_values = X_train[column].dropna().unique()
        if value in known_values:
            continue
        spelled = value.strip().casefold()
        if column == "seller_name":
            spelled = SELLER_ALIASES.get(spelled, spelled)
        for label in known_values:
            if label.strip().casefold() == spelled:
                result[column] = label
                break
    return result


def main():
    splits = prepare_tv5_splits()
    for category, split in splits.items():
        # Keep the row as a table, and keep the recorded price separate for grading.
        sample = split.X_test.iloc[[1]]
        recorded_price = float(split.y_test.loc[sample.index[0]])
        device = sample.iloc[0]
        print(f"\n{category.title()}: {device['brand']} {device['model_clean']}")
        print(f"Gia ghi nhan: {recorded_price:,.0f} VND")

        for model_key in MODEL_FOLDERS:
            model = load_model(category, model_key)
            prediction = float(model.predict(sample)[0])
            error = abs(prediction - recorded_price)
            print(f"{model_key}: du doan {prediction:,.0f} VND, lech {error:,.0f} VND")


if __name__ == "__main__":
    main()
