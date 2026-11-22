"""Step 5: Feature Engineering & Aggregation for TV5 (Price Prediction Handoff).

This module aggregates review-level NLP signals into product-level canonical features:
1. Ingests canonical parent products universe from dim_source_parents.jsonl (7,051 products).
2. Ingests enriched reviews from reviews_tv6_aspects.jsonl (14,869 reviews).
3. Executes rigorous Anti-Leakage audit (ensuring review_time_raw <= crawl_time).
4. Aggregates multi-dimensional signals at source_parent_id granularity:
   - Volume & recency (usable reviews count, 90-day volume, review span days).
   - Star rating distribution (mean, standard deviation, min, max).
   - PhoBERT deep sentiment continuous score & discrete distribution (pos, neg, neu ratios, net sentiment).
   - 5-aspect tech polarity scores & mention frequencies (battery, performance, screen, camera, service).
   - 5-topic latent thematic proportions (LDA topic shares).
   - Cold-start flag (has_review_data: 0 for 5,154 products, 1 for 1,897 products).
5. Exports production Parquet and CSV files for TV5 modeling with full audit manifest and documentation.
"""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DIM_SOURCE_PARENTS_FILE,
    DOCS_STEP5_REPORT_FILE,
    DOCS_TV5_FEATURE_REPORT_FILE,
    DOCS_TV6_DIR,
    FIGURES_TV6_DIR,
    REVIEWS_TV6_ALL_FILE,
    REVIEWS_TV6_ASPECTS_FILE,
    TABLES_TV6_DIR,
    TV5_FEATURE_REPORT_FILE,
    TV5_FEATURES_ACTIVE_CSV,
    TV5_FEATURES_ACTIVE_PARQUET,
    TV5_FEATURES_CSV,
    TV5_FEATURES_PARQUET,
    TV6_PIPELINE_VERSION,
)

ASPECT_KEYS = [
    "battery_power",
    "performance_thermal",
    "display_design",
    "camera_audio",
    "service_logistics",
]

TOPIC_ID_TO_FEATURE_NAME = {
    0: "topic_share_performance_setup",
    1: "topic_share_screen_camera",
    2: "topic_share_battery_charging",
    3: "topic_share_service_delivery",
    4: "topic_share_usage_experience",
}


def load_parent_universe(parents_file: Path = DIM_SOURCE_PARENTS_FILE) -> pd.DataFrame:
    """Load all 7,051 parent products from dim_source_parents.jsonl."""
    records = []
    with open(parents_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    df = pd.DataFrame(records)
    print(f"Loaded {len(df):,} parent products from {parents_file.name}")
    return df


def audit_anti_leakage(reviews_all_file: Path = REVIEWS_TV6_ALL_FILE) -> Dict[str, Any]:
    """Verify that no review was submitted after the crawl snapshot timestamp (review_time_raw <= crawl_time)."""
    total_audited = 0
    valid_pairs = 0
    missing_time = 0
    leakage_violations = 0
    max_crawl_dt = None
    max_review_dt = None

    with open(reviews_all_file, "r", encoding="utf-8") as f:
        for line in f:
            total_audited += 1
            rec = json.loads(line.strip())
            rt_str = rec.get("review_time_raw")
            ct_str = rec.get("crawl_time")

            if not rt_str or not ct_str:
                missing_time += 1
                continue

            try:
                rt_dt = datetime.fromisoformat(rt_str.replace("Z", "+00:00"))
                ct_dt = datetime.fromisoformat(ct_str.replace("Z", "+00:00"))
                valid_pairs += 1

                if max_crawl_dt is None or ct_dt > max_crawl_dt:
                    max_crawl_dt = ct_dt
                if max_review_dt is None or rt_dt > max_review_dt:
                    max_review_dt = rt_dt

                if rt_dt > ct_dt:
                    leakage_violations += 1
            except Exception:
                pass

    audit_result = {
        "status": "PASS" if leakage_violations == 0 else "FAIL",
        "total_reviews_audited": total_audited,
        "valid_time_pairs": valid_pairs,
        "missing_time_records": missing_time,
        "leakage_violations": leakage_violations,
        "snapshot_boundary_max_crawl_time": max_crawl_dt.isoformat() if max_crawl_dt else None,
        "max_review_time_observed": max_review_dt.isoformat() if max_review_dt else None,
    }
    print(f"Anti-leakage audit: {audit_result['status']} (Violations: {leakage_violations}/{valid_pairs:,})")
    return audit_result


def aggregate_review_features_per_parent(
    reviews_file: Path = REVIEWS_TV6_ASPECTS_FILE,
    snapshot_time: Optional[datetime] = None,
) -> Dict[str, Dict[str, Any]]:
    """Aggregate review-level NLP predictions into parent-level summary dictionaries."""
    parent_reviews: Dict[str, List[Dict[str, Any]]] = {}

    with open(reviews_file, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line.strip())
            pid = rec["source_parent_id"]
            if pid not in parent_reviews:
                parent_reviews[pid] = []
            parent_reviews[pid].append(rec)

    print(f"Aggregating features for {len(parent_reviews):,} active parent products...")

    if snapshot_time is None:
        # Default snapshot based on dataset max crawl time (October 17, 2026)
        snapshot_time = datetime(2026, 10, 17, 23, 59, 59, tzinfo=timezone.utc)

    agg_features: Dict[str, Dict[str, Any]] = {}

    for pid, revs in parent_reviews.items():
        n = len(revs)
        ratings = [r["rating_raw"] for r in revs if r.get("rating_raw") is not None]
        sentiment_scores = [r["sentiment_score"] for r in revs if r.get("sentiment_score") is not None]
        preds = [r["sentiment_pred"] for r in revs]

        # Ratings
        avg_rating = round(float(np.mean(ratings)), 4) if ratings else None
        rating_std = round(float(np.std(ratings, ddof=1)), 4) if len(ratings) > 1 else 0.0
        rating_min = int(np.min(ratings)) if ratings else None
        rating_max = int(np.max(ratings)) if ratings else None

        # Sentiment PhoBERT
        avg_sent_score = round(float(np.mean(sentiment_scores)), 4) if sentiment_scores else 0.0
        pos_count = sum(1 for p in preds if p == "POSITIVE")
        neg_count = sum(1 for p in preds if p == "NEGATIVE")
        neu_count = sum(1 for p in preds if p == "NEUTRAL")

        pos_ratio = round(pos_count / n, 4)
        neg_ratio = round(neg_count / n, 4)
        neu_ratio = round(neu_count / n, 4)
        net_score = round(pos_ratio - neg_ratio, 4)

        # Aspects
        aspect_dict = {}
        for asp in ASPECT_KEYS:
            mentions = [r for r in revs if asp in r.get("aspect_mentions", [])]
            m_count = len(mentions)
            mention_rate = round(m_count / n, 4)
            aspect_dict[f"aspect_mention_rate_{asp}"] = mention_rate

            if m_count > 0:
                # Polarity score: POSITIVE = 1.0, NEUTRAL = 0.0, NEGATIVE = -1.0
                pol_values = []
                for m in mentions:
                    sent = m.get("aspect_sentiments", {}).get(asp, "NEUTRAL")
                    if sent == "POSITIVE":
                        pol_values.append(1.0)
                    elif sent == "NEGATIVE":
                        pol_values.append(-1.0)
                    else:
                        pol_values.append(0.0)
                aspect_dict[f"aspect_sentiment_score_{asp}"] = round(float(np.mean(pol_values)), 4)
            else:
                aspect_dict[f"aspect_sentiment_score_{asp}"] = 0.0

        # Topics (LDA)
        topic_counts = Counter(r.get("dominant_topic_id", 0) for r in revs)
        topic_dict = {}
        for tid, feat_name in TOPIC_ID_TO_FEATURE_NAME.items():
            topic_dict[feat_name] = round(topic_counts.get(tid, 0) / n, 4)

        # Temporal dynamics
        review_dates = []
        recent_90d_count = 0
        for r in revs:
            t_str = r.get("review_time_raw")
            if t_str:
                try:
                    dt = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                    review_dates.append(dt)
                    delta_days = (snapshot_time - dt).total_seconds() / 86400.0
                    if 0 <= delta_days <= 90:
                        recent_90d_count += 1
                except Exception:
                    pass

        if review_dates:
            earliest_dt = min(review_dates)
            latest_dt = max(review_dates)
            span_days = round((latest_dt - earliest_dt).total_seconds() / 86400.0, 1)
            earliest_str = earliest_dt.isoformat()
            latest_str = latest_dt.isoformat()
        else:
            earliest_str = None
            latest_str = None
            span_days = 0.0

        p_name = revs[0].get("product_name") or ""
        agg_features[pid] = {
            "product_name_rev": p_name,
            "has_review_data": 1,
            "review_count_usable": n,
            "review_count_last_90d": recent_90d_count,
            "avg_rating": avg_rating,
            "rating_std": rating_std,
            "rating_min": rating_min,
            "rating_max": rating_max,
            "avg_sentiment_score": avg_sent_score,
            "sentiment_positive_ratio": pos_ratio,
            "sentiment_negative_ratio": neg_ratio,
            "sentiment_neutral_ratio": neu_ratio,
            "sentiment_net_score": net_score,
            **aspect_dict,
            **topic_dict,
            "earliest_review_time": earliest_str,
            "latest_review_time": latest_str,
            "review_span_days": span_days,
        }

    return agg_features


def build_full_handoff_dataset(
    parents_df: pd.DataFrame,
    agg_features: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    """Join 7,051 parent products with aggregated features, establishing explicit cold-start defaults."""
    rows = []
    cold_start_count = 0
    active_count = 0

    for _, row in parents_df.iterrows():
        pid = row["source_parent_id"]
        source = row.get("source", "")
        category = row.get("category", "")
        rep_name = row.get("representative_parent_name_raw") or ""
        if not rep_name and pid in agg_features:
            rep_name = agg_features[pid].get("product_name_rev") or ""

        base_info = {
            "source_parent_id": pid,
            "source": source,
            "category": category,
            "product_name_rep": rep_name,
        }

        if pid in agg_features:
            active_count += 1
            feat = dict(agg_features[pid])
            feat.pop("product_name_rev", None)
            row_data = {**base_info, **feat, "tv6_pipeline_version": TV6_PIPELINE_VERSION}
        else:
            cold_start_count += 1
            # Explicit cold-start defaults
            cold_data = {
                "has_review_data": 0,
                "review_count_usable": 0,
                "review_count_last_90d": 0,
                "avg_rating": None,
                "rating_std": 0.0,
                "rating_min": None,
                "rating_max": None,
                "avg_sentiment_score": 0.0,
                "sentiment_positive_ratio": 0.0,
                "sentiment_negative_ratio": 0.0,
                "sentiment_neutral_ratio": 0.0,
                "sentiment_net_score": 0.0,
            }
            # Aspect defaults
            for asp in ASPECT_KEYS:
                cold_data[f"aspect_mention_rate_{asp}"] = 0.0
                cold_data[f"aspect_sentiment_score_{asp}"] = 0.0
            # Topic defaults
            for feat_name in TOPIC_ID_TO_FEATURE_NAME.values():
                cold_data[feat_name] = 0.0
            # Temporal defaults
            cold_data["earliest_review_time"] = None
            cold_data["latest_review_time"] = None
            cold_data["review_span_days"] = 0.0
            cold_data["tv6_pipeline_version"] = TV6_PIPELINE_VERSION

            row_data = {**base_info, **cold_data}

        rows.append(row_data)

    df_full = pd.DataFrame(rows)
    print(f"Full dataset assembled: {len(df_full):,} rows (Active: {active_count:,}, Cold-Start: {cold_start_count:,})")
    return df_full


def generate_feature_dictionary_table() -> Tuple[pd.DataFrame, str]:
    """Generate Table 5.1: TV5 Feature Contract & ML Usage Guide."""
    data = [
        # Identifiers
        {"feature_name": "source_parent_id", "data_type": "string", "value_range": "32-char hex hash", "null_policy_cold_start": "Primary Key (No Null)", "description_and_usage_tv5": "Khóa định danh sản phẩm cha để join trực tiếp với dim_source_parents và fact_listings_features."},
        {"feature_name": "source", "data_type": "string", "value_range": "cellphones, fptshop, tgdd...", "null_policy_cold_start": "Preserved", "description_and_usage_tv5": "Sàn thương mại điện tử phân phối sản phẩm, phục vụ phân nhóm hoặc target encoding."},
        {"feature_name": "category", "data_type": "string", "value_range": "laptop, smartphone", "null_policy_cold_start": "Preserved", "description_and_usage_tv5": "Danh mục phần cứng công nghệ."},
        {"feature_name": "product_name_rep", "data_type": "string", "value_range": "Text", "null_policy_cold_start": "Preserved", "description_and_usage_tv5": "Tên sản phẩm đại diện dùng cho kiểm toán và hiển thị."},
        # Cold start
        {"feature_name": "has_review_data", "data_type": "int8", "value_range": "0 or 1", "null_policy_cold_start": "0", "description_and_usage_tv5": "Cờ nhị phân phân tách sản phẩm có review vs Cold-Start (73.1%). Feature cực kỳ quan trọng cho mô hình cây (LightGBM/XGBoost)."},
        # Volume
        {"feature_name": "review_count_usable", "data_type": "int32", "value_range": "0 to 171", "null_policy_cold_start": "0", "description_and_usage_tv5": "Khối lượng đánh giá hợp lệ. Phản ánh độ phổ biến và thanh khoản của sản phẩm trên thị trường."},
        {"feature_name": "review_count_last_90d", "data_type": "int32", "value_range": "0 to 45", "null_policy_cold_start": "0", "description_and_usage_tv5": "Số lượng review trong 90 ngày gần nhất tính đến snapshot crawl. Thước đo động lượng bán hàng (sales momentum)."},
        # Star ratings
        {"feature_name": "avg_rating", "data_type": "float32", "value_range": "[1.0, 5.0]", "null_policy_cold_start": "null (NaN in CSV)", "description_and_usage_tv5": "Điểm đánh giá sao trung bình. TV5 có thể điền median thị trường (4.50) kết hợp với cờ has_review_data=0."},
        {"feature_name": "rating_std", "data_type": "float32", "value_range": "[0.0, 2.83]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Độ lệch chuẩn điểm rating. Đo lường mức độ đồng thuận hay phân cực của người mua đối với sản phẩm."},
        {"feature_name": "rating_min", "data_type": "int8", "value_range": "[1, 5]", "null_policy_cold_start": "null", "description_and_usage_tv5": "Điểm sao thấp nhất từng nhận được. Đo lường rủi ro trải nghiệm xấu."},
        {"feature_name": "rating_max", "data_type": "int8", "value_range": "[1, 5]", "null_policy_cold_start": "null", "description_and_usage_tv5": "Điểm sao cao nhất từng nhận được."},
        # PhoBERT Sentiment
        {"feature_name": "avg_sentiment_score", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0 (Neutral)", "description_and_usage_tv5": "Điểm cảm xúc thực chất liên tục từ PhoBERT SOTA. Hiệu chỉnh các trường hợp đánh giá bất nhất (rating 5★ nhưng chê sản phẩm)."},
        {"feature_name": "sentiment_positive_ratio", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ lệ review mang sắc thái khen ngợi, hài lòng."},
        {"feature_name": "sentiment_negative_ratio", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ lệ review mang sắc thái phàn nàn, sự cố phần cứng hoặc bảo hành kém."},
        {"feature_name": "sentiment_neutral_ratio", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ lệ review trung tính hoặc pha trộn khen chê."},
        {"feature_name": "sentiment_net_score", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Chỉ số Net Sentiment = pos_ratio - neg_ratio. Đại diện cho thiện cảm thương hiệu tổng hòa."},
        # Aspects
        {"feature_name": "aspect_mention_rate_battery_power", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tần suất người dùng đề cập đến thời lượng pin, tốc độ sạc hoặc củ sạc đi kèm."},
        {"feature_name": "aspect_sentiment_score_battery_power", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Điểm hài lòng riêng về pin và củ sạc (-1 tiêu cực, 0 trung tính, +1 tích cực)."},
        {"feature_name": "aspect_mention_rate_performance_thermal", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tần suất đề cập đến hiệu năng CPU/GPU, FPS game, độ mượt, tản nhiệt hoặc tiếng quạt."},
        {"feature_name": "aspect_sentiment_score_performance_thermal", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Điểm đánh giá về sức mạnh cấu hình và nhiệt độ (yếu tố ảnh hưởng mạnh đến phân khúc giá cao cấp)."},
        {"feature_name": "aspect_mention_rate_display_design", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tần suất đề cập đến màn hình sắc nét, màu sắc, viền mỏng, độ phân giải, vỏ kim loại/nhựa."},
        {"feature_name": "aspect_sentiment_score_display_design", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Điểm đánh giá thẩm mỹ và trải nghiệm thị giác của sản phẩm."},
        {"feature_name": "aspect_mention_rate_camera_audio", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tần suất đề cập đến camera chụp đêm, góc rộng, âm lượng loa, mic thoại."},
        {"feature_name": "aspect_sentiment_score_camera_audio", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Điểm đánh giá khả năng quay chụp và giải trí đa phương tiện."},
        {"feature_name": "aspect_mention_rate_service_logistics", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tần suất đề cập đến tư vấn, đóng gói, giao hàng, bảo hành của shop."},
        {"feature_name": "aspect_sentiment_score_service_logistics", "data_type": "float32", "value_range": "[-1.0, +1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Điểm đánh giá chất lượng phục vụ của kênh bán lẻ."},
        # Topics
        {"feature_name": "topic_share_performance_setup", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ trọng đánh giá thuộc chủ đề LDA 0 (Cấu hình, thông số, bảo hành kỹ thuật)."},
        {"feature_name": "topic_share_screen_camera", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ trọng đánh giá thuộc chủ đề LDA 1 (Màn hình hiển thị, quay chụp camera)."},
        {"feature_name": "topic_share_battery_charging", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ trọng đánh giá thuộc chủ đề LDA 2 (Pin sạc, phụ kiện đi kèm)."},
        {"feature_name": "topic_share_service_delivery", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ trọng đánh giá thuộc chủ đề LDA 3 (Giao hàng, đóng gói, chăm sóc khách hàng)."},
        {"feature_name": "topic_share_usage_experience", "data_type": "float32", "value_range": "[0.0, 1.0]", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Tỷ trọng đánh giá thuộc chủ đề LDA 4 (Trải nghiệm thực tế, mượt mà, sự cố phát sinh)."},
        # Temporal
        {"feature_name": "earliest_review_time", "data_type": "string (ISO)", "value_range": "2019 to 2026", "null_policy_cold_start": "null", "description_and_usage_tv5": "Thời điểm nhận review đầu tiên của model sản phẩm."},
        {"feature_name": "latest_review_time", "data_type": "string (ISO)", "value_range": "2019 to 2026", "null_policy_cold_start": "null", "description_and_usage_tv5": "Thời điểm nhận review gần nhất trước ngày snapshot cào dữ liệu."},
        {"feature_name": "review_span_days", "data_type": "float32", "value_range": ">= 0.0", "null_policy_cold_start": "0.0", "description_and_usage_tv5": "Số ngày tồn tại trên thị trường có hoạt động review (ước lượng vòng đời sản phẩm lifecycle)."},
        # Provenance
        {"feature_name": "tv6_pipeline_version", "data_type": "string", "value_range": "tv6-v1.0.0", "null_policy_cold_start": "tv6-v1.0.0", "description_and_usage_tv5": "Phiên bản mã nguồn pipeline TV6 đảm bảo tính truy nguyên khoa học dữ liệu."},
    ]
    df = pd.DataFrame(data)
    md = df.to_markdown(index=False)
    return df, md


def generate_summary_metrics_table(df_full: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Generate Table 5.2: Summary Statistics of Handoff Features (Full Universe vs Active Only)."""
    df_active = df_full[df_full["has_review_data"] == 1]

    cols_to_summarize = [
        "review_count_usable",
        "review_count_last_90d",
        "avg_rating",
        "rating_std",
        "avg_sentiment_score",
        "sentiment_positive_ratio",
        "sentiment_negative_ratio",
        "sentiment_net_score",
        "aspect_sentiment_score_battery_power",
        "aspect_sentiment_score_performance_thermal",
        "aspect_sentiment_score_display_design",
        "aspect_sentiment_score_camera_audio",
        "aspect_sentiment_score_service_logistics",
        "review_span_days",
    ]

    records = []
    for col in cols_to_summarize:
        s_full = df_full[col].dropna()
        s_act = df_active[col].dropna()

        records.append({
            "Feature Name": col,
            "Universe Mean (N=7,051)": round(float(s_full.mean()), 4),
            "Universe Median": round(float(s_full.median()), 4),
            "Active Mean (N=1,897)": round(float(s_act.mean()), 4),
            "Active Std": round(float(s_act.std()), 4),
            "Active Min": round(float(s_act.min()), 4),
            "Active Median": round(float(s_act.median()), 4),
            "Active Max": round(float(s_act.max()), 4),
        })

    df_summary = pd.DataFrame(records)
    md = df_summary.to_markdown(index=False)
    return df_summary, md


def generate_top_reviewed_products_table(df_full: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
    """Generate Table 5.3: Top 15 Reviewed Parent Products and their NLP Feature Profiles."""
    df_top = df_full.sort_values(by="review_count_usable", ascending=False).head(15)

    display_cols = [
        "source",
        "category",
        "product_name_rep",
        "review_count_usable",
        "avg_rating",
        "avg_sentiment_score",
        "sentiment_positive_ratio",
        "sentiment_negative_ratio",
        "sentiment_net_score",
        "aspect_sentiment_score_performance_thermal",
        "review_span_days",
    ]

    df_disp = df_top[display_cols].copy()
    # Format names for cleaner display
    df_disp["product_name_rep"] = df_disp["product_name_rep"].apply(lambda s: s[:38] + "..." if len(s) > 40 else s)
    df_disp.rename(columns={
        "source": "Sàn",
        "category": "Ngành hàng",
        "product_name_rep": "Tên sản phẩm đại diện",
        "review_count_usable": "Số Review",
        "avg_rating": "Rating Sao",
        "avg_sentiment_score": "PhoBERT Sentiment",
        "sentiment_positive_ratio": "Tỷ lệ Pos",
        "sentiment_negative_ratio": "Tỷ lệ Neg",
        "sentiment_net_score": "Net Sentiment",
        "aspect_sentiment_score_performance_thermal": "Score Hiệu năng",
        "review_span_days": "Vòng đời (Ngày)",
    }, inplace=True)

    md = df_disp.to_markdown(index=False)
    return df_disp, md


def plot_feature_figures(df_full: pd.DataFrame, figures_dir: Path = FIGURES_TV6_DIR):
    """Generate professional 300-DPI visualizations for Step 5."""
    df_active = df_full[df_full["has_review_data"] == 1].copy()

    # 1. Figure 5.1: Feature Correlation Heatmap (Active Products)
    corr_cols = [
        "review_count_usable",
        "avg_rating",
        "avg_sentiment_score",
        "sentiment_positive_ratio",
        "sentiment_negative_ratio",
        "sentiment_net_score",
        "aspect_sentiment_score_battery_power",
        "aspect_sentiment_score_performance_thermal",
        "aspect_sentiment_score_display_design",
        "aspect_sentiment_score_camera_audio",
        "aspect_sentiment_score_service_logistics",
        "review_span_days",
    ]
    corr_labels = [
        "Review Count",
        "Avg Rating",
        "PhoBERT Score",
        "Pos Ratio",
        "Neg Ratio",
        "Net Sentiment",
        "Score Battery",
        "Score Performance",
        "Score Display",
        "Score Camera",
        "Score Service",
        "Review Span Days",
    ]

    corr_matrix = df_active[corr_cols].corr()

    plt.figure(figsize=(11, 9))
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".2f",
        cmap="coolwarm",
        vmin=-1,
        vmax=1,
        square=True,
        xticklabels=corr_labels,
        yticklabels=corr_labels,
        cbar_kws={"label": "Pearson Correlation (r)"},
        linewidths=0.5,
    )
    plt.title("Ma trận Tương quan Tuyến tính giữa các Đặc trưng Review TV6 (N=1,897 sản phẩm)", fontsize=13, weight="bold", pad=14)
    plt.xticks(rotation=45, ha="right", fontsize=9)
    plt.yticks(rotation=0, fontsize=9)
    plt.tight_layout()
    fig1_path = figures_dir / "fig_5_1_feature_correlation_matrix.png"
    plt.savefig(fig1_path, dpi=300)
    plt.close()
    print(f"Saved: {fig1_path.name}")

    # 2. Figure 5.2: Sentiment Score vs Star Rating Calibration Scatter Plot
    plt.figure(figsize=(9, 6))
    palette = {"laptop": "#1f77b4", "smartphone": "#ff7f0e"}
    sns.scatterplot(
        data=df_active,
        x="avg_rating",
        y="avg_sentiment_score",
        hue="category",
        alpha=0.6,
        s=35,
        palette=palette,
        edgecolor="none",
    )
    # Regression trend line
    sns.regplot(
        data=df_active,
        x="avg_rating",
        y="avg_sentiment_score",
        scatter=False,
        color="#333333",
        line_kws={"linestyle": "--", "linewidth": 2, "label": "Đường xu thế tổng thể"},
    )
    plt.title("Đối chiếu Điểm Sao Gốc (Avg Rating) vs Điểm Cảm xúc PhoBERT (Avg Sentiment)", fontsize=12, weight="bold", pad=12)
    plt.xlabel("Điểm Đánh giá Sao Trung bình (1.0 - 5.0★)", fontsize=11)
    plt.ylabel("Điểm Cảm xúc PhoBERT Trung bình (-1.0 đến +1.0)", fontsize=11)
    plt.axhline(0, color="gray", linestyle=":", alpha=0.7)
    plt.axvline(3, color="gray", linestyle=":", alpha=0.7)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(title="Danh mục", loc="upper left", frameon=True)
    plt.tight_layout()
    fig2_path = figures_dir / "fig_5_2_sentiment_vs_rating_scatter.png"
    plt.savefig(fig2_path, dpi=300)
    plt.close()
    print(f"Saved: {fig2_path.name}")

    # 3. Figure 5.3: Aspect Sentiment Scores Distribution Boxplot
    aspect_score_cols = [f"aspect_sentiment_score_{a}" for a in ASPECT_KEYS]
    aspect_labels = [
        "Pin & Sạc",
        "Hiệu năng & Nhiệt",
        "Màn hình & Thiết kế",
        "Camera & Âm thanh",
        "Dịch vụ & Giao vận",
    ]

    # Filter to products where aspect mention rate > 0
    melted_data = []
    for col, label, asp in zip(aspect_score_cols, aspect_labels, ASPECT_KEYS):
        mentioned_subset = df_active[df_active[f"aspect_mention_rate_{asp}"] > 0][col]
        for val in mentioned_subset:
            melted_data.append({"Khía cạnh": label, "Điểm Cảm xúc": val})

    df_melt = pd.DataFrame(melted_data)

    plt.figure(figsize=(10, 6))
    sns.boxplot(
        data=df_melt,
        x="Khía cạnh",
        y="Điểm Cảm xúc",
        palette="Set2",
        showmeans=True,
        meanprops={"marker": "o", "markerfacecolor": "red", "markeredgecolor": "black", "markersize": 7},
    )
    plt.title("Phân bố Điểm Cảm xúc 5 Khía cạnh Kỹ thuật & Dịch vụ trên các Sản phẩm Cha", fontsize=12, weight="bold", pad=12)
    plt.xlabel("Khía cạnh Đánh giá (ASBSA)", fontsize=11)
    plt.ylabel("Điểm Cảm xúc Khía cạnh (-1.0 đến +1.0)", fontsize=11)
    plt.axhline(0, color="gray", linestyle="--", alpha=0.7)
    plt.grid(True, linestyle=":", alpha=0.6, axis="y")
    plt.xticks(rotation=15, ha="right", fontsize=10)
    plt.tight_layout()
    fig3_path = figures_dir / "fig_5_3_aspect_scores_distribution.png"
    plt.savefig(fig3_path, dpi=300)
    plt.close()
    print(f"Saved: {fig3_path.name}")


def run_feature_engineering_pipeline() -> Dict[str, Any]:
    """Execute the end-to-end Step 5 Feature Engineering and Handoff pipeline."""
    start_time = time.time()
    print("\n" + "=" * 80)
    print("TV6 STEP 5: FEATURE ENGINEERING & HANDOFF FOR TV5 (PRICE PREDICTION)")
    print("=" * 80)

    TABLES_TV6_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_TV6_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Anti-leakage audit
    leakage_audit = audit_anti_leakage(REVIEWS_TV6_ALL_FILE)

    # 2. Ingest parent products universe
    parents_df = load_parent_universe(DIM_SOURCE_PARENTS_FILE)

    # 3. Aggregate review features per parent
    agg_features = aggregate_review_features_per_parent(REVIEWS_TV6_ASPECTS_FILE)

    # 4. Assemble full canonical dataset
    df_full = build_full_handoff_dataset(parents_df, agg_features)

    # 5. Export production files
    print("\nExporting TV5 Feature artifacts...")
    # Full universe (7,051 records)
    df_full.to_parquet(TV5_FEATURES_PARQUET, index=False, engine="pyarrow")
    print(f"Exported: {TV5_FEATURES_PARQUET} ({TV5_FEATURES_PARQUET.stat().st_size / 1024:.1f} KB)")
    df_full.to_csv(TV5_FEATURES_CSV, index=False, encoding="utf-8")
    print(f"Exported: {TV5_FEATURES_CSV} ({TV5_FEATURES_CSV.stat().st_size / 1024:.1f} KB)")

    # Active subset only (1,897 records)
    df_active = df_full[df_full["has_review_data"] == 1].copy()
    df_active.to_parquet(TV5_FEATURES_ACTIVE_PARQUET, index=False, engine="pyarrow")
    print(f"Exported: {TV5_FEATURES_ACTIVE_PARQUET} ({TV5_FEATURES_ACTIVE_PARQUET.stat().st_size / 1024:.1f} KB)")
    df_active.to_csv(TV5_FEATURES_ACTIVE_CSV, index=False, encoding="utf-8")
    print(f"Exported: {TV5_FEATURES_ACTIVE_CSV} ({TV5_FEATURES_ACTIVE_CSV.stat().st_size / 1024:.1f} KB)")

    # 6. Generate Tables
    print("\nGenerating Tables for TV5 Handoff Documentation...")
    df_dict, md_dict = generate_feature_dictionary_table()
    df_dict.to_csv(TABLES_TV6_DIR / "table_5_1_feature_dictionary.csv", index=False, encoding="utf-8")
    with open(TABLES_TV6_DIR / "table_5_1_feature_dictionary.md", "w", encoding="utf-8") as f:
        f.write(md_dict)

    df_sum, md_sum = generate_summary_metrics_table(df_full)
    df_sum.to_csv(TABLES_TV6_DIR / "table_5_2_handoff_summary_metrics.csv", index=False, encoding="utf-8")
    with open(TABLES_TV6_DIR / "table_5_2_handoff_summary_metrics.md", "w", encoding="utf-8") as f:
        f.write(md_sum)

    df_top, md_top = generate_top_reviewed_products_table(df_full)
    df_top.to_csv(TABLES_TV6_DIR / "table_5_3_top_reviewed_products_features.csv", index=False, encoding="utf-8")
    with open(TABLES_TV6_DIR / "table_5_3_top_reviewed_products_features.md", "w", encoding="utf-8") as f:
        f.write(md_top)

    # 7. Generate Figures
    print("\nGenerating Visualizations (300 DPI)...")
    plot_feature_figures(df_full, FIGURES_TV6_DIR)

    # 8. Compile Metadata Report
    elapsed_sec = round(time.time() - start_time, 2)
    report = {
        "pipeline_step": "Step 5: Feature Engineering & TV5 Handoff",
        "pipeline_version": TV6_PIPELINE_VERSION,
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": elapsed_sec,
        "anti_leakage_audit": leakage_audit,
        "universe_statistics": {
            "total_parent_products": len(df_full),
            "active_products_with_reviews": len(df_active),
            "cold_start_products_without_reviews": len(df_full) - len(df_active),
            "coverage_percentage": round(len(df_active) / len(df_full) * 100, 2),
            "cold_start_percentage": round((len(df_full) - len(df_active)) / len(df_full) * 100, 2),
            "total_reviews_aggregated": int(df_full["review_count_usable"].sum()),
            "avg_reviews_per_active_product": round(float(df_active["review_count_usable"].mean()), 2),
            "max_reviews_single_product": int(df_active["review_count_usable"].max()),
        },
        "feature_schema": {
            "total_features": len(df_full.columns),
            "columns": list(df_full.columns),
        },
        "artifacts_generated": {
            "parquet_full": str(TV5_FEATURES_PARQUET.name),
            "csv_full": str(TV5_FEATURES_CSV.name),
            "parquet_active": str(TV5_FEATURES_ACTIVE_PARQUET.name),
            "csv_active": str(TV5_FEATURES_ACTIVE_CSV.name),
            "tables": [
                "table_5_1_feature_dictionary",
                "table_5_2_handoff_summary_metrics",
                "table_5_3_top_reviewed_products_features",
            ],
            "figures": [
                "fig_5_1_feature_correlation_matrix.png",
                "fig_5_2_sentiment_vs_rating_scatter.png",
                "fig_5_3_aspect_scores_distribution.png",
            ],
        },
    }

    # Save reports
    for out_path in [TV5_FEATURE_REPORT_FILE, DOCS_TV5_FEATURE_REPORT_FILE]:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Saved: {out_path}")

    print("\n" + "=" * 80)
    print(f"STEP 5 COMPLETED SUCCESSFULLY in {elapsed_sec}s")
    print("=" * 80)
    return report


if __name__ == "__main__":
    run_feature_engineering_pipeline()
