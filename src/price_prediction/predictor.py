import sys
import joblib
import pandas as pd
from pathlib import Path

MODELS_DIR = Path(__file__).parent / 'models'
sys.path.insert(0, str(MODELS_DIR))

from config import *
from features import *


class PricePredictor:
    def __init__(self, laptop_model='lgbm', smartphone_model='lgbm'):
        self.models = {
            'laptop': self._load_model('laptop', laptop_model),
            'smartphone': self._load_model('smartphone', smartphone_model)
        }

    def _load_model(self, category, model):
        path_map = {
            'rf': RESULTS_DIR / 'random_forest' / f"rf_{category}.pkl",
            'lgbm': RESULTS_DIR / 'lightgbm' / f"lgbm_{category}.pkl",
        }
        return joblib.load(path_map[model])

    def predict(self, product_info: dict):
        category = str(product_info.get('category', '')).lower().strip()
        if category not in ('laptop', 'smartphone'):
            raise ValueError("The 'category' field must be either 'laptop' or 'smartphone'")

        df_raw = pd.DataFrame([product_info])
        pred_price = float(self.models[category].predict(df_raw)[0])

        return {
            'category': category,
            'predicted_price_vnd': round(pred_price, -3)
        }


if __name__ == '__main__':
    predictor = PricePredictor()

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
    print(f"[Test 1 - Laptop đầy đủ]: {predictor.predict(laptop_sample)['predicted_price_vnd']:,.0f} VNĐ")

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
    print(f"[Test 2 - Smartphone đầy đủ]: {predictor.predict(smartphone_sample)['predicted_price_vnd']:,.0f} VNĐ")

    minimal_laptop = {
        "category": "laptop",
        "brand": "dell",
        "ram_gb": 8,
        "storage_gb": 256
    }
    print(f"[Test 3 - Laptop thiếu thông số]: {predictor.predict(minimal_laptop)['predicted_price_vnd']:,.0f} VNĐ")

    try:
        predictor.predict({"category": "tablet", "brand": "apple"})
    except ValueError as e:
        print(f"[Test 4 - Bắt lỗi category hợp lệ]: Đã bắt được ValueError -> '{e}'")

    print("\nTất cả test cases chạy thành công! Sẵn sàng bàn giao cho TV8.")
