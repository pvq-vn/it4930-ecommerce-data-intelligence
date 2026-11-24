import os
from pathlib import Path


BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent.parent.parent
DATA_DIR = PROJECT_ROOT / 'data' / 'processed'
MARKET_GRAPH_DIR = PROJECT_ROOT / 'data' / 'market_graph'
REVIEW_NLP_DIR = PROJECT_ROOT / 'data' / 'tv6'
ANOMALY_OUTPUTS_DIR = PROJECT_ROOT / 'src' / 'anomaly_detection' / 'outputs'

CLEANED_DATA_PATH = DATA_DIR / 'products_cleaned.jsonl'
PROCESSED_DATA_PATH = DATA_DIR / 'products_processed.jsonl'
LISTING_ID_CROSSWALK_PATH = DATA_DIR / 'listing_id_crosswalk.csv'
LAPTOP_BENCHMARK_PATH = MARKET_GRAPH_DIR / 'laptop_benchmarks.csv'
SMARTPHONE_BENCHMARK_PATH = MARKET_GRAPH_DIR / 'smartphone_benchmarks.csv'
REVIEW_FEATURES_PATH = REVIEW_NLP_DIR / 'tv5_review_features.csv'
ANOMALY_FLAGS_PATH = ANOMALY_OUTPUTS_DIR / 'anomaly_flags.csv'

RESULTS_DIR = BASE_DIR / 'results'
METRICS_DIR = BASE_DIR.parent / 'metrics'

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

TARGET_COL = 'price_vnd'
GROUP_COL = 'source_parent_id'

# Chế độ phân tích độ nhạy trên tập Train: "none" | "extreme_only" | "drop_combined"
ANOMALY_FILTER_MODE = os.getenv('ANOMALY_FILTER_MODE', 'none').strip().lower()

LEAKAGE_COLS = [
    'discount_rate',
    'original_price_vnd',
    'listing_record_id',
    'crawl_time',
    'crawl_batch',
    'is_price_missing',
    'product_name',
    'raw_specs',
    'availability_status',
    'community_id',
    'segment_label',
    'price_band',
    'price_median',
    'price_min',
    'price_max',
    'rule_flag',
    'iqr_flag',
    'iqr_extreme_flag',
    'isolation_forest_flag',
    'isolation_score',
    'methods_agree',
    'combined_flag',
    'anomaly_severity',
    'anomaly_reasons',
]

LAPTOP_NUM_FEATURES = [
    'ram_gb',
    'storage_gb',
    'screen_size_inch',
    'battery_wh',
    'charger_watt',
    'ram_x_storage',
    'is_dedicated_gpu',
    'cpu_tier_score',
    'is_ram_missing',
    'is_battery_missing',
    'is_charger_missing',
    'is_out_of_stock',
    'cpu_perf_rating',
    'gpu_perf_rating',
    'hw_seller_count',
    'has_review_data',
    'review_count_usable',
    'avg_sentiment_score',
    'sentiment_positive_ratio',
    'sentiment_net_score',
    'brand_sentiment_prior',
]

LAPTOP_CAT_FEATURES = ['brand', 'model_clean', 'seller_name', 'cpu_model', 'gpu_model']

SMARTPHONE_NUM_FEATURES = [
    'ram_gb',
    'storage_gb',
    'screen_size_inch',
    'battery_mah',
    'camera_mp',
    'is_rom_high',
    'is_oled',
    'is_ram_missing',
    'is_battery_missing',
    'is_out_of_stock',
    'cpu_benchmark_score',
    'cpu_geekbench_5_multi',
    'cpu_passmark',
    'hw_seller_count',
    'has_review_data',
    'review_count_usable',
    'avg_sentiment_score',
    'sentiment_positive_ratio',
    'sentiment_net_score',
    'brand_sentiment_prior',
]

SMARTPHONE_CAT_FEATURES = ['brand', 'model_clean', 'seller_name', 'display_type_norm', 'network_type_norm', 'cpu_model']
