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

    match_explicit = re.search(r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inch|\'\'|")\b', text, flags=re.IGNORECASE)
    if match_explicit:
        val = float(match_explicit.group(1))
        if ((category == 'laptop' and 11 <= val <= 19) or (category == 'smartphone' and 4 <= val <= 8.5)):
            return val

    if category == 'laptop':
        if re.search(r'\b(?:scar|strix|blade|gram|rog)\s*18\b', text, flags=re.IGNORECASE):
            return 18.0
        if re.search(r'\b(?:hp|dell|vivobook|ideapad|thinkpad|inspiron|latitude|vostro)\s*15\b', text, flags=re.IGNORECASE):
            return 15.6
        if re.search(r'\b(?:thinkpad\s*e|ideapad|vivobook|zenbook|dell|hp)\s*14\b', text, flags=re.IGNORECASE):
            return 14.0

    return np.nan

def _is_corrupted_record(df: pd.DataFrame):
    unknown_model = df['model_clean'].fillna('unknown').astype(str).str.lower().str.strip() == 'unknown'

    brand = df['brand'].fillna('unknown').astype(str).str.lower().str.strip()
    name = df['product_name'].fillna('unknown').astype(str).str.lower().str.strip()

    def has_brand_conflict(brand, name):
        for other_brand, tokens in BRAND_CONFLICT_TOKENS.items():
            if other_brand != brand and any(re.search(rf'\b{tok}\b', name) for tok in tokens):
                return True
        return False

    brand_conflict = pd.Series(
        [has_brand_conflict(b, n) for b, n in zip(brand, name)],
        index=df.index
    )

    screen_num = pd.to_numeric(df['screen_size_inch'], errors='coerce')
    fake_feature_phone = ((df['category_clean'] == 'smartphone') & (screen_num < 3.5) & (df[TARGET_COL] > 3000000))

    return unknown_model | brand_conflict | fake_feature_phone

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

def load_and_split_data(cleaned_filepath, processed_filepath):
    df_clean = pd.read_json(cleaned_filepath, lines=True)
    df_proc = pd.read_json(processed_filepath, lines=True)

    cols_to_extract = ['listing_record_id', GROUP_COL, 'battery_wh', 'battery_mah', 'camera_mp', 'display_type_norm', 'network_type_norm']
    available_cols = [c for c in cols_to_extract if c in df_proc.columns]
    df_proc = df_proc[available_cols].drop_duplicates(subset=['listing_record_id'])

    df = pd.merge(df_clean, df_proc, on='listing_record_id', how='left')
    df[GROUP_COL] = df[GROUP_COL].fillna(df['listing_record_id'])

    is_valid_laptop = (df['category_clean'] == 'laptop') & (df[TARGET_COL] >= 3000000)
    is_valid_phone = (df['category_clean'] == 'smartphone') & (df[TARGET_COL] >= 1000000)
    not_corrupted = ~_is_corrupted_record(df)
    df_valid = df[(is_valid_laptop | is_valid_phone) & not_corrupted].copy()

    bad_storage_mask = (df_valid['category_clean'] == 'laptop') & (df_valid['storage_gb'].isna() | (df_valid['storage_gb'] < 64))
    if bad_storage_mask.any():
        df_valid.loc[bad_storage_mask, 'storage_gb'] = df_valid.loc[bad_storage_mask, 'product_name'].apply(_extract_storage_from_text)

    screen_num = pd.to_numeric(df_valid['screen_size_inch'], errors='coerce')
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

    df_valid.drop(columns=[c for c in LEAKAGE_COLS if c in df_valid.columns], inplace=True)
    df_laptop = df_valid[df_valid['category_clean'] == 'laptop']
    df_smartphone = df_valid[df_valid['category_clean'] == 'smartphone']

    return df_laptop.reset_index(drop=True), df_smartphone.reset_index(drop=True)

class HardwareFeatureEngineer(BaseEstimator, TransformerMixin):
    def __init__(self, category, cat_dtype='str'):
        self.category = category
        self.cat_dtype = cat_dtype

    def _prepare_stateless(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.category == 'laptop':
            raw_num = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh']
            cat_cols = LAPTOP_CAT_FEATURES
        else:
            raw_num = ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp']
            cat_cols = SMARTPHONE_CAT_FEATURES

        required_cols = raw_num + cat_cols
        df_out = df.reindex(columns=df.columns.union(required_cols, sort=False)).copy()

        for col in raw_num:
            df_out[col] = pd.to_numeric(df_out[col], errors='coerce')

        if self.category == 'laptop':
            invalid_screen = (df_out['screen_size_inch'] < 11) | (df_out['screen_size_inch'] > 19)
        else:
            invalid_screen = (df_out['screen_size_inch'] < 4) | (df_out['screen_size_inch'] > 8.5)

        df_out.loc[invalid_screen, 'screen_size_inch'] = np.nan

        df_out['is_ram_missing'] = df_out['ram_gb'].isnull().astype(int)
        bat_col = 'battery_wh' if self.category == 'laptop' else 'battery_mah'
        df_out['is_battery_missing'] = df_out[bat_col].isnull().astype(int)

        if self.category == 'laptop':
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
        self.num_to_impute_ = (
            ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_wh']
            if self.category == 'laptop'
            else ['ram_gb', 'storage_gb', 'screen_size_inch', 'battery_mah', 'camera_mp']
        )

        self.by_brand_medians_ = {}
        self.global_medians_ = {}

        for col in self.num_to_impute_:
            self.by_brand_medians_[col] = df_prep.groupby(df_prep['brand'])[col].median().dropna().to_dict()
            global_med = df_prep[col].median()
            self.global_medians_[col] = np.nan if pd.isna(global_med) else float(global_med)

        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        df_out = self._prepare_stateless(X)
        brand_clean = df_out['brand'].str.lower().str.strip()

        for col in self.num_to_impute_:
            fill_vals = brand_clean.map(self.by_brand_medians_[col]).fillna(self.global_medians_[col])
            df_out[col] = df_out[col].fillna(fill_vals)

        if self.category == 'laptop':
            df_out['ram_x_storage'] = df_out['ram_gb'] * df_out['storage_gb']
            num_cols, cat_cols = LAPTOP_NUM_FEATURES, LAPTOP_CAT_FEATURES
        else:
            df_out['is_rom_high'] = (df_out['storage_gb'] >= 256).astype(int)
            num_cols, cat_cols = SMARTPHONE_NUM_FEATURES, SMARTPHONE_CAT_FEATURES

        for col in cat_cols:
            if self.cat_dtype == 'category':
                df_out[col] = df_out[col].astype('category')
            else:
                df_out[col] = df_out[col].astype(str)

        return df_out[num_cols + cat_cols]
