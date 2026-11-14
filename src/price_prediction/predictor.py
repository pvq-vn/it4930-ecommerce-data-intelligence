import sys
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

MODELS_DIR = Path(__file__).parent / 'models'
sys.path.insert(0, str(MODELS_DIR))

from config import *
from features import *


class PricePredictor:
    RAW_EXPECTED_COLS = {
        'laptop': ['brand', 'ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh', 'gpu_model', 'cpu_model'],
        'smartphone': ['brand', 'ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp', 'display_type_norm', 'network_type_norm']
    }
    def __init__(self, laptop_model='lgbm', smartphone_model='rf'):
        self.models = {
            'laptop': self._load_model('laptop', laptop_model),
            'smartphone': self._load_model('smartphone', smartphone_model)
        }

        self.model_names = {
            'laptop': laptop_model,
            'smartphone': smartphone_model
        }

    def _load_model(self, category, model):
        path_map = {
            'rf': RESULTS_DIR / 'random_forest' / f"rf_{category}.pkl",
            'lgbm': RESULTS_DIR / 'lightgbm' / f"lgbm_{category}.pkl",
            'catboost': RESULTS_DIR / 'catboost' / f"cb_{category}.pkl"
        }
        return joblib.load(path_map[model])

    def predict(self, product_info: dict):
        category = str(product_info.get('category', '')).lower().strip()
        if category not in ('laptop', 'smartphone'):
            raise ValueError("Trường category phải là 'laptop' hoặc 'smartphone")

        df_raw = pd.DataFrame([product_info])

        for col in self.RAW_EXPECTED_COLS[category]:
            if col not in df_raw.columns:
                df_raw[col] = np.nan

        if category == 'laptop':
            df_feat = engineer_laptop(df_raw)
            num_cols, cat_cols = LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES
        else:
            df_feat = engineer_smartphone(df_raw)
            num_cols, cat_cols = SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES

        for col in cat_cols:
            if self.model_names[category] == 'lgbm':
                df_feat[col] = df_feat[col].astype('category')

        X_input = df_feat[num_cols + cat_cols]
        pred_price = float(self.models[category].predict(X_input)[0])

        return {
            'category': category,
            'predicted_price_vnd': round(pred_price, -3)
        }

if __name__ == '__main__':
    predictor = PricePredictor()

    # Test 1: Laptop cấu hình đầy đủ
    laptop_sample = {
        "category": "laptop",
        "brand": "asus",
        "model_clean": "vivobook 15",
        "seller_name": "cellphones",
        "ram_gb": 16,
        "storage_gb": 512,
        "cpu_model": "core i5-13500h",
        "gpu_model": "iris xe graphics",
        "screen_size_inch": 15.6
    }
    res_lap = predictor.predict(laptop_sample)
    print(f"[Test 1 - Laptop đầy đủ]: {res_lap['predicted_price_vnd']:,.0f} VNĐ")

    # Test 2: Smartphone cấu hình đầy đủ
    smartphone_sample = {
        "category": "smartphone",
        "brand": "apple",
        "model_clean": "iphone 15 pro max",
        "seller_name": "fpt shop",
        "ram_gb": 8,
        "storage_gb": 256,
        "cpu_model": "apple a17 pro",
        "screen_size_inch": 6.7
    }
    res_sma = predictor.predict(smartphone_sample)
    print(f"[Test 2 - Smartphone đầy đủ]: {res_sma['predicted_price_vnd']:,.0f} VNĐ")

    # Test 3: Dữ liệu thiếu thông số (người dùng chỉ nhập vài trường cơ bản trên form Demo)
    minimal_laptop = {
        "category": "laptop",
        "brand": "dell",
        "ram_gb": 8,
        "storage_gb": 256
    }
    res_min = predictor.predict(minimal_laptop)
    print(f"[Test 3 - Laptop thiếu thông số]: {res_min['predicted_price_vnd']:,.0f} VNĐ")

    # Test 4: Kiểm tra bắt lỗi khi truyền sai category
    try:
        predictor.predict({"category": "tablet", "brand": "apple"})
    except ValueError as e:
        print(f"[Test 4 - Bắt lỗi category hợp lệ]: Đã bắt được ValueError -> '{e}'")

    print("\nTất cả test cases chạy thành công! Sẵn sàng bàn giao cho TV8.")
