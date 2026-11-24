import re
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from config import *


BRAND_CONFLICT_TOKENS = {
    'apple': ['iphone', 'ipad', 'macbook'],
    'samsung': ['samsung', 'galaxy'],
    'oppo': ['oppo', 'reno'],
    'xiaomi': ['xiaomi', 'redmi', 'poco'],
    'honor': ['honor'],
    'vivo': ['vivo', 'iqoo'],
    'realme': ['realme'],
    'tecno': ['tecno', 'camon', 'pova'],
    'nubia': ['nubia', 'redmagic'],
    'nokia': ['nokia']
}
DESKTOP_IN_LAPTOP_PATTERN = re.compile(r'\bimac\b|\bmac\s*studio\b|\bmac\s*mini\b|\bmac\s*pro\b', flags=re.IGNORECASE)
LAPTOP_BENCH_COLS = ['cpu_perf_rating', 'gpu_perf_rating', 'hw_seller_count']
SMARTPHONE_BENCH_COLS = ['cpu_benchmark_score', 'cpu_geekbench_5_multi', 'cpu_passmark', 'hw_seller_count']
REVIEW_BASE_COLS = ['has_review_data', 'review_count_usable', 'avg_sentiment_score', 'sentiment_positive_ratio', 'sentiment_net_score']

def _extract_storage_from_text(text):
    if not isinstance(text, str):
        return np.nan

    match_tb = re.search(r'\b([1-4])\s*TB\b', text, flags=re.IGNORECASE)
    if match_tb:
        return float(match_tb.group(1)) * 1024

    match_gb = re.search(r'\b(128|256|512|1024|2048)\s*GB\b', text, flags=re.IGNORECASE)
    if match_gb:
        return float(match_gb.group(1))

    return np.nan

def _extract_screen_size_from_text(text, category):
    if not isinstance(text, str):
        return np.nan

    match_explicit = re.search(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch\b|\'\'|")', text, flags=re.IGNORECASE)
    if match_explicit:
        val = float(match_explicit.group(1))
        if ((category == 'laptop' and 11 <= val <= 19) or (category == 'smartphone' and 4 <= val <= 8.5)):
            return val

    if category == 'laptop':
        if re.search(r'\b(?:scar|strix|blade|gram|rog)\s*18\b', text, flags=re.IGNORECASE):
            return 18.0
        if re.search(r'\b(?:hp|dell|vivobook|ideapad|thinkpad|inspiron|latitude|vostro)\s*15\b', text, flags=re.IGNORECASE):
            return 15.6
        if re.search(r'\b(?:thinkpad|ideapad|vivobook|zenbook|dell|hp)\s*14\b', text, flags=re.IGNORECASE):
            return 14.0

    return np.nan

def _is_corrupted_record(df: pd.DataFrame):
    unknown_model = df['model_clean'].fillna('unknown').astype(str).str.lower().str.strip() == 'unknown'

    brand = df['brand'].fillna('unknown').astype(str).str.lower().str.strip()
    name = df['product_name'].fillna('unknown').astype(str).str.lower().str.strip()

    def has_brand_conflict(b, n):
        for other_brand, tokens in BRAND_CONFLICT_TOKENS.items():
            if other_brand != b and any(re.search(rf'\b{tok}\b', n) for tok in tokens):
                return True
        return False

    brand_conflict = pd.Series(
        [has_brand_conflict(b, n) for b, n in zip(brand, name)],
        index=df.index
    )

    screen_num = pd.to_numeric(df['screen_size_inch'], errors='coerce')
    fake_feature_phone = ((df['category_clean'] == 'smartphone') & (screen_num < 3.5) & (df[TARGET_COL] > 3000000))
    desktop_in_laptop = (df['category_clean'] == 'laptop') & name.apply(
        lambda x: bool(DESKTOP_IN_LAPTOP_PATTERN.search(x))
    )

    return unknown_model | brand_conflict | fake_feature_phone | desktop_in_laptop

def _normalize_smartphone_network(df: pd.DataFrame):
    raw_net = df['network_type_norm'].fillna('unknown').astype(str).str.lower().str.strip()

    def map_raw_net(val):
        if '5g' in val:
            return '5g'
        if '4g' in val or 'lte' in val:
            return '4g'
        if any(k in val for k in ['3g', '2g', 'gsm']):
            return '2g_3g'
        return 'unknown'

    norm_net = raw_net.apply(map_raw_net)

    name = df['product_name'].fillna('unknown').astype(str).str.lower().str.strip()
    model = df['model_clean'].fillna('unknown').astype(str).str.lower().str.strip()
    specs = df['raw_specs'].fillna('unknown').astype(str).str.lower().str.strip()
    combined_text = name + ' ' + model + ' ' + specs

    unknown_net = norm_net == 'unknown'

    has_5g_kw = combined_text.str.contains(r'\b5g\b', regex=True)
    has_4g_kw = combined_text.str.contains(r'\b(?:4g|lte)\b', regex=True)
    is_5g_iphone = combined_text.str.contains(r'\biphone\s*(?:1[2-9]|air|se\s*(?:2022|3))\b', regex=True)

    norm_net.loc[unknown_net & (has_5g_kw | is_5g_iphone)] = '5g'
    norm_net.loc[(norm_net == 'unknown') & has_4g_kw] = '4g'

    return norm_net

def _compute_hw_seller_count(df: pd.DataFrame) -> pd.Series:
    hw_key = (
        df['category_clean'].fillna('unknown').astype(str).str.lower().str.strip()
        + '|' + df['brand'].fillna('unknown').astype(str).str.lower().str.strip()
        + '|' + df['model_clean'].fillna('unknown').astype(str).str.lower().str.strip()
        + '|' + pd.to_numeric(df['ram_gb'], errors='coerce').fillna(-1).astype(str)
        + '|' + pd.to_numeric(df['storage_gb'], errors='coerce').fillna(-1).astype(str)
    )
    return hw_key.map(hw_key.value_counts()).fillna(1).astype(float)

def _merge_auxiliary_features(df: pd.DataFrame) -> pd.DataFrame:
    df_out = df.copy()
    for col in set(LAPTOP_BENCH_COLS + SMARTPHONE_BENCH_COLS + REVIEW_BASE_COLS):
        if col != 'hw_seller_count' and col not in df_out.columns:
            df_out[col] = np.nan

    if 'listing_record_id' in df_out.columns:
        if LAPTOP_BENCHMARK_PATH.exists():
            df_lap_bm = pd.read_csv(LAPTOP_BENCHMARK_PATH)
            lap_cols = [c for c in ['listing_record_id', 'cpu_perf_rating', 'gpu_perf_rating'] if c in df_lap_bm.columns]
            if len(lap_cols) > 1:
                df_lap_bm = df_lap_bm[lap_cols].drop_duplicates(subset=['listing_record_id'])
                df_out = pd.merge(df_out, df_lap_bm, on='listing_record_id', how='left', suffixes=('', '_bm_lap'))
                for col in ['cpu_perf_rating', 'gpu_perf_rating']:
                    bm_col = f'{col}_bm_lap'
                    if bm_col in df_out.columns:
                        df_out[col] = pd.to_numeric(df_out[col], errors='coerce').fillna(
                            pd.to_numeric(df_out[bm_col], errors='coerce')
                        )
                        df_out = df_out.drop(columns=[bm_col])

        if SMARTPHONE_BENCHMARK_PATH.exists():
            df_sma_bm = pd.read_csv(SMARTPHONE_BENCHMARK_PATH)
            sma_cols = [
                c for c in ['listing_record_id', 'cpu_benchmark_score', 'cpu_geekbench_5_multi', 'cpu_passmark']
                if c in df_sma_bm.columns
            ]
            if len(sma_cols) > 1:
                df_sma_bm = df_sma_bm[sma_cols].drop_duplicates(subset=['listing_record_id'])
                df_out = pd.merge(df_out, df_sma_bm, on='listing_record_id', how='left', suffixes=('', '_bm_sma'))
                for col in ['cpu_benchmark_score', 'cpu_geekbench_5_multi', 'cpu_passmark']:
                    bm_col = f'{col}_bm_sma'
                    if bm_col in df_out.columns:
                        df_out[col] = pd.to_numeric(df_out[col], errors='coerce').fillna(
                            pd.to_numeric(df_out[bm_col], errors='coerce')
                        )
                        df_out = df_out.drop(columns=[bm_col])

    df_out['hw_seller_count'] = _compute_hw_seller_count(df_out)

    if REVIEW_FEATURES_PATH.exists() and GROUP_COL in df_out.columns:
        df_rev = pd.read_csv(REVIEW_FEATURES_PATH)
        if GROUP_COL in df_rev.columns:
            aspect_cols = [c for c in df_rev.columns if c.startswith('aspect_sentiment_score_')]
            selected_cols = [GROUP_COL] + [c for c in REVIEW_BASE_COLS if c in df_rev.columns] + aspect_cols
            df_rev = df_rev[selected_cols].drop_duplicates(subset=[GROUP_COL])
            df_out = pd.merge(df_out, df_rev, on=GROUP_COL, how='left', suffixes=('', '_rev'))
            for col in [c for c in REVIEW_BASE_COLS + aspect_cols if c != GROUP_COL]:
                dup_col = f'{col}_rev'
                if dup_col in df_out.columns:
                    df_out[col] = pd.to_numeric(df_out[col], errors='coerce').fillna(
                        pd.to_numeric(df_out[dup_col], errors='coerce')
                    )
                    df_out = df_out.drop(columns=[dup_col])

    df_out['has_review_data'] = pd.to_numeric(df_out['has_review_data'], errors='coerce').fillna(0.0)
    df_out['review_count_usable'] = pd.to_numeric(df_out['review_count_usable'], errors='coerce').fillna(0.0)

    return df_out

def _resolve_processed_listing_ids(df_clean: pd.DataFrame, df_proc: pd.DataFrame) -> pd.Series:
    direct = df_clean['listing_record_id'].astype(str)
    proc_ids = set(df_proc['listing_record_id'].astype(str))
    if direct.isin(proc_ids).all() or not LISTING_ID_CROSSWALK_PATH.exists():
        return direct
    crosswalk = pd.read_csv(
        LISTING_ID_CROSSWALK_PATH,
        usecols=['listing_record_id_cleaned', 'listing_record_id_processed'],
        dtype=str,
    ).drop_duplicates(subset=['listing_record_id_cleaned'])
    id_map = crosswalk.set_index('listing_record_id_cleaned')['listing_record_id_processed']
    mapped = direct.map(id_map)
    return direct.where(direct.isin(proc_ids), mapped.fillna(direct))

def load_and_split_data(cleaned_filepath, processed_filepath):
    df_clean = pd.read_json(cleaned_filepath, lines=True)
    df_proc = pd.read_json(processed_filepath, lines=True)

    cols_to_extract = [
        'listing_record_id',
        GROUP_COL,
        'battery_wh',
        'battery_mah',
        'charger_watt',
        'camera_mp',
        'display_type_norm',
        'network_type_norm',
        'availability_status',
    ]
    available_cols = [c for c in cols_to_extract if c in df_proc.columns]
    df_proc = df_proc[available_cols].drop_duplicates(subset=['listing_record_id'])

    join_col = '_proc_listing_id'
    df_clean[join_col] = _resolve_processed_listing_ids(df_clean, df_proc)
    df_proc_join = df_proc.rename(columns={'listing_record_id': join_col})

    df = pd.merge(df_clean, df_proc_join, on=join_col, how='left', suffixes=('', '_proc'))
    for col in [c for c in available_cols if c != 'listing_record_id']:
        dup_col = f'{col}_proc'
        if dup_col in df.columns:
            if col in df.columns:
                df[col] = df[col].fillna(df[dup_col])
            else:
                df[col] = df[dup_col]
            df = df.drop(columns=[dup_col])

    df[GROUP_COL] = df[GROUP_COL].fillna(df['listing_record_id'])

    # Ghép tạm anomaly_severity để lọc độ nhạy trên tập Train trong utils.py, sau đó loại khỏi X
    if ANOMALY_FLAGS_PATH.exists() and 'listing_record_id' in df.columns:
        df_anom = pd.read_csv(ANOMALY_FLAGS_PATH)
        anom_cols = [c for c in ['listing_record_id', 'anomaly_severity'] if c in df_anom.columns]
        if len(anom_cols) > 1:
            df_anom = df_anom[anom_cols].drop_duplicates(subset=['listing_record_id'])
            anom_ids = set(df_anom['listing_record_id'].astype(str))
            anom_key = join_col if df[join_col].astype(str).isin(anom_ids).any() else 'listing_record_id'
            df_anom_join = df_anom.rename(columns={'listing_record_id': anom_key})
            df = pd.merge(df, df_anom_join, on=anom_key, how='left')

    df = df.drop(columns=[join_col], errors='ignore')

    is_valid_laptop = (df['category_clean'] == 'laptop') & (df[TARGET_COL] >= 3000000)
    is_valid_phone = (df['category_clean'] == 'smartphone') & (df[TARGET_COL] >= 1000000)
    not_corrupted = ~_is_corrupted_record(df)
    df_valid = df[(is_valid_laptop | is_valid_phone) & not_corrupted].copy()

    bad_storage_mask = (df_valid['category_clean'] == 'laptop') & (df_valid['storage_gb'].isna() | (df_valid['storage_gb'] < 64))
    if bad_storage_mask.any():
        df_valid.loc[bad_storage_mask, 'storage_gb'] = df_valid.loc[bad_storage_mask, 'product_name'].apply(_extract_storage_from_text)

    screen_num = pd.to_numeric(df_valid['screen_size_inch'], errors='coerce')
    invalid_screen = (((df_valid['category_clean'] == 'laptop') & ((screen_num < 11) | (screen_num > 19))) | ((df_valid['category_clean'] == 'smartphone') & ((screen_num < 4) | (screen_num > 8.5))))
    screen_num.loc[invalid_screen] = np.nan
    missing_screen = screen_num.isna()
    if missing_screen.any():
        screen_num.loc[missing_screen] = df_valid.loc[missing_screen].apply(
            lambda r: _extract_screen_size_from_text(r['product_name'], r['category_clean']),
            axis=1,
        )
    df_valid['screen_size_inch'] = screen_num

    phone_mask = df_valid['category_clean'] == 'smartphone'
    if phone_mask.any() and 'network_type_norm' in df_valid.columns:
        df_valid.loc[phone_mask, 'network_type_norm'] = _normalize_smartphone_network(df_valid.loc[phone_mask])

    df_valid['is_out_of_stock'] = (df_valid['availability_status'].astype(str).str.lower().str.strip() == 'out_of_stock').astype(int)

    df_valid = _merge_auxiliary_features(df_valid)

    cols_to_drop = [c for c in LEAKAGE_COLS if c in df_valid.columns and c != 'anomaly_severity']
    df_valid = df_valid.drop(columns=cols_to_drop)

    df_laptop = df_valid[df_valid['category_clean'] == 'laptop']
    df_smartphone = df_valid[df_valid['category_clean'] == 'smartphone']

    return df_laptop.reset_index(drop=True), df_smartphone.reset_index(drop=True)

class HardwareFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self, category, cat_dtype='str'):
        self.category = category
        self.cat_dtype = cat_dtype

    def _prepare_stateless(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.category == 'laptop':
            raw_num = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh', 'charger_watt'] + LAPTOP_BENCH_COLS + REVIEW_BASE_COLS
            cat_cols = LAPTOP_CAT_FEATURES
        else:
            raw_num = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp'] + SMARTPHONE_BENCH_COLS + REVIEW_BASE_COLS
            cat_cols = SMARTPHONE_CAT_FEATURES

        required_cols = raw_num + cat_cols
        df_out = df.reindex(columns=df.columns.union(required_cols, sort=False)).copy()

        for col in raw_num:
            df_out[col] = pd.to_numeric(df_out[col], errors='coerce')

        if 'is_out_of_stock' in df_out.columns:
            df_out['is_out_of_stock'] = pd.to_numeric(df_out['is_out_of_stock'], errors='coerce').fillna(0).astype(int)
        elif 'availability_status' in df_out.columns:
            df_out['is_out_of_stock'] = (df_out['availability_status'].astype(str).str.lower().str.strip() == 'out_of_stock').astype(int)
        else:
            df_out['is_out_of_stock'] = 0
        
        if self.category == 'laptop':
            invalid_screen = (df_out['screen_size_inch'] < 11) | (df_out['screen_size_inch'] > 19)
        else:
            invalid_screen = (df_out['screen_size_inch'] < 4) | (df_out['screen_size_inch'] > 8.5)

        df_out.loc[invalid_screen, 'screen_size_inch'] = np.nan

        df_out['is_ram_missing'] = df_out['ram_gb'].isnull().astype(int)
        bat_col = 'battery_wh' if self.category == 'laptop' else 'battery_mah'
        df_out['is_battery_missing'] = df_out[bat_col].isnull().astype(int)

        if self.category == 'laptop':
            df_out['is_charger_missing'] = df_out['charger_watt'].isnull().astype(int)
            df_out['is_dedicated_gpu'] = df_out['gpu_model'].apply(
                lambda x: 1 if pd.notnull(x) and any(
                    kw in str(x).lower() for kw in ['rtx', 'gtx', 'radeon', 'rx', 'arc']
                ) else 0
            )

            def assign_cpu_tier(cpu):
                cpu = re.sub(r'[\s\-]+', '', str(cpu).lower())
                if any(k in cpu for k in ['i9', 'r9', 'ryzen9', 'ultra9', 'core9']):
                    return 5
                if 'apple' in cpu or cpu.startswith(('m1', 'm2', 'm3', 'm4', 'm5')):
                    return 4
                if any(k in cpu for k in ['i7', 'r7', 'ryzen7', 'ultra7', 'core7']):
                    return 3
                if any(k in cpu for k in ['i5', 'r5', 'ryzen5', 'ultra5', 'core5']):
                    return 2
                if any(k in cpu for k in ['i3', 'r3', 'ryzen3', 'ultra3', 'core3']):
                    return 1
                return 0

            df_out['cpu_tier_score'] = df_out['cpu_model'].apply(assign_cpu_tier)

        else:
            df_out['is_oled'] = df_out['display_type_norm'].apply(
                lambda x: 1 if pd.notnull(x) and any(
                    kw in str(x).lower() for kw in ['oled', 'amoled', 'retina']
                ) else 0
            )

        for col in cat_cols:
            df_out[col] = df_out[col].fillna('unknown').astype(str).str.lower().str.strip()

        return df_out

    def fit(self, X: pd.DataFrame, y=None):
        df_prep = self._prepare_stateless(X)
        bench_cols = LAPTOP_BENCH_COLS if self.category == 'laptop' else SMARTPHONE_BENCH_COLS
        base_num = (
            ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh', 'charger_watt']
            if self.category == 'laptop'
            else ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp']
        )
        self.num_to_impute_ = base_num + bench_cols + REVIEW_BASE_COLS

        self.by_brand_medians_ = {}
        self.global_medians_ = {}

        for col in self.num_to_impute_:
            self.by_brand_medians_[col] = df_prep.groupby(df_prep['brand'])[col].median().dropna().to_dict()
            global_med = df_prep[col].median()
            self.global_medians_[col] = 0.0 if pd.isna(global_med) or not np.isfinite(global_med) else float(global_med)

        if 'avg_sentiment_score' in df_prep.columns:
            self.by_brand_sentiment_prior_ = (
                df_prep.groupby(df_prep['brand'])['avg_sentiment_score'].mean().dropna().to_dict()
            )
            global_sent = df_prep['avg_sentiment_score'].mean()
            self.global_sentiment_prior_ = (
                0.0 if pd.isna(global_sent) or not np.isfinite(global_sent) else float(global_sent)
            )
        else:
            self.by_brand_sentiment_prior_ = {}
            self.global_sentiment_prior_ = 0.0

        self.cat_dtype_ = {}
        for col in (LAPTOP_CAT_FEATURES if self.category == 'laptop' else SMARTPHONE_CAT_FEATURES):
            cats = sorted(df_prep[col].dropna().unique().tolist())

            if 'unknown' not in cats:
                cats.append('unknown')

            self.cat_dtype_[col] = pd.CategoricalDtype(categories=cats)

        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        df_out = self._prepare_stateless(X)
        brand_clean = df_out['brand'].str.lower().str.strip()

        df_out['brand_sentiment_prior'] = (
            brand_clean.map(self.by_brand_sentiment_prior_).fillna(self.global_sentiment_prior_)
        )

        for col in self.num_to_impute_:
            global_fill = self.global_medians_.get(col, 0.0)
            fill_vals = brand_clean.map(self.by_brand_medians_.get(col, {})).fillna(global_fill)
            df_out[col] = df_out[col].fillna(fill_vals).fillna(0.0)

        if self.category == 'laptop':
            df_out['ram_x_storage'] = df_out['ram_gb'] * df_out['storage_gb']
            num_cols, cat_cols = LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES
        else:
            df_out['is_rom_high'] = (df_out['storage_gb'] >= 256).astype(int)
            num_cols, cat_cols = SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES

        for col in num_cols:
            if col in df_out.columns:
                arr = pd.to_numeric(df_out[col], errors='coerce').to_numpy(dtype=float)
                df_out[col] = np.where(np.isfinite(arr), arr, 0.0)

        for col in cat_cols:
            if self.cat_dtype == 'category':
                cat_type = getattr(self, 'cat_dtype_', {}).get(col)
                if cat_type is not None:
                    s = df_out[col].where(df_out[col].isin(cat_type.categories), 'unknown')
                    df_out[col] = s.astype(cat_type)

                else:
                    df_out[col] = df_out[col].astype('category')

            else:
                df_out[col] = df_out[col].astype(str)

        return df_out[num_cols + cat_cols]
