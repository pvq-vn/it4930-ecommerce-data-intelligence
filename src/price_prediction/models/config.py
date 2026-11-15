from pathlib import Path


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR.parent.parent.parent / 'data' / 'processed'
CLEANED_DATA_PATH = DATA_DIR / 'products_cleaned.jsonl'
PROCESSED_DATA_PATH = DATA_DIR / 'products_processed.jsonl'
RESULTS_DIR = BASE_DIR / 'results'
METRICS_DIR = BASE_DIR.parent / 'metrics'

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

TARGET_COL = 'price_vnd'
GROUP_COL = 'source_parent_id'

LEAKAGE_COLS = ['discount_rate', 'original_price_vnd', 'listing_record_id', 'crawl_time', 'crawl_batch', 'is_price_missing', 'product_name', 'raw_specs']

LAPTOP_NUM_FEATURES = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh', 'ram_x_storage', 'is_dedicated_gpu', 'cpu_tier_score', 'is_ram_missing', 'is_battery_missing']
LAPTOP_CAT_FEATURES = ['brand', 'model_clean', 'seller_name', 'cpu_model', 'gpu_model']

SMARTPHONE_NUM_FEATURES = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp', 'is_rom_high', 'is_oled', 'is_ram_missing', 'is_battery_missing']
SMARTPHONE_CAT_FEATURES = ['brand', 'model_clean', 'seller_name', 'display_type_norm', 'network_type_norm', 'cpu_model']
