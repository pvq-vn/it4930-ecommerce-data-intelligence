"""Build TV6 Analytical Views and Audit Manifest.

This module implements Step 0 of the TV6 (Review NLP Sentiment Analysis) pipeline:
1. Ingests raw Gold v2 review data (fact_reviews.jsonl) and product metadata (dim_source_parents.jsonl).
2. Performs relational enrichment (maps source_parent_id to normalized product name).
3. Projects records into strict canonical schemas conforming to feature_contracts_tv3_tv8.md.
4. Segregates usable reviews from unusable/suspect records (maintaining zero data loss).
5. Exports three analytical JSONL tables under data/tv6/:
   - reviews_tv6_all.jsonl (15,805 records): Master audit view with full provenance.
   - reviews_tv6_usable.jsonl (14,869 records): Clean text dataset ready for NLP & sentiment models.
   - reviews_tv6_unusable.jsonl (936 records): Unusable/suspect records isolated for governance audit.
6. Computes comprehensive summary statistics and exports a cryptographically verifiable manifest.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
import re
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.review_nlp.config import (
    DATA_TV6_DIR,
    DIM_SOURCE_PARENTS_FILE,
    DOCS_STEP0_MANIFEST_FILE,
    DOCS_TV6_DIR,
    FACT_REVIEWS_FILE,
    RATING_SENTIMENT_MAP,
    REVIEWS_TV6_ALL_FILE,
    REVIEWS_TV6_UNUSABLE_FILE,
    REVIEWS_TV6_USABLE_FILE,
    STEP0_MANIFEST_FILE,
    TV6_CANONICAL_FIELDS,
    TV6_PIPELINE_VERSION,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("tv6.step0")


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def normalize_product_name(raw_name: Optional[str]) -> Optional[str]:
    """Clean and standardize representative product names by stripping promotional noise.

    Follows the TV2 Gold standard regex normalization rules.
    """
    if not isinstance(raw_name, str):
        return raw_name

    # Remove leading pre-order text
    s = re.sub(r"^\s*đặt trước\s+", "", raw_name, flags=re.I)
    # Remove official store suffixes
    s = re.sub(r"\s+chính hãng\s+tại\s+viettel store!?$", "", s, flags=re.I)
    # Remove trailing warranty/promotion tokens
    s = re.sub(
        r"\s*(?:-\s*|\|\s*)(?:bảo hành\b.*|chính hãng\b.*|nhập khẩu chính hãng\b.*|đã kích hoạt\b.*)$",
        "",
        s,
        flags=re.I,
    )
    return s.strip()


def normalize_review_rating(rating_raw: Any) -> Optional[float]:
    """Normalize raw rating into bounded [0.0, 5.0] float scale."""
    try:
        val = float(rating_raw)
        return val if 0.0 <= val <= 5.0 else None
    except (TypeError, ValueError):
        return None


def load_dim_source_parents(
    parents_file: Path,
) -> Dict[str, str]:
    """Load dim_source_parents into a mapping: source_parent_id -> normalized product_name."""
    if not parents_file.exists():
        raise FileNotFoundError(f"Source parents file not found: {parents_file}")

    parent_map: Dict[str, str] = {}
    logger.info("Loading dim_source_parents from %s", parents_file)

    with parents_file.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            rec = json.loads(line_str)
            pid = rec.get("source_parent_id")
            raw_name = rec.get("representative_parent_name_raw")
            if pid:
                parent_map[pid] = normalize_product_name(raw_name) or "Unknown Product"

    logger.info("Loaded %d source parent products for enrichment.", len(parent_map))
    return parent_map


def stream_fact_reviews(
    reviews_file: Path,
) -> Generator[Dict[str, Any], None, None]:
    """Yield parsed JSON records from fact_reviews.jsonl."""
    if not reviews_file.exists():
        raise FileNotFoundError(f"Fact reviews file not found: {reviews_file}")

    with reviews_file.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                rec = json.loads(line_str)
                yield rec
            except json.JSONDecodeError as err:
                logger.error("JSON decode error at line %d: %s", line_no, err)
                raise


def transform_review_record(
    rec: Dict[str, Any],
    parent_map: Dict[str, str],
) -> Dict[str, Any]:
    """Transform and project a single Gold fact_review into canonical TV6 schema."""
    source_parent_id = rec.get("source_parent_id") or ""
    product_name = parent_map.get(source_parent_id)

    rating_raw = rec.get("rating_raw")
    rating_norm = normalize_review_rating(rating_raw)

    transformed: Dict[str, Any] = {
        "review_record_id": rec.get("review_record_id") or rec.get("raw_record_id"),
        "source_parent_id": source_parent_id,
        "product_name": product_name,
        "source": rec.get("source"),
        "category": rec.get("category"),
        "rating_raw": rating_raw,
        "rating_norm": rating_norm,
        "review_text_normalized": rec.get("review_text_normalized"),
        "review_time_raw": rec.get("review_time_raw"),
        "author_raw": rec.get("author_raw"),
        "review_usable": bool(rec.get("review_usable")),
        "review_text_status": rec.get("review_text_status"),
        "review_time_status": rec.get("review_time_status"),
        "is_reply_present": bool(rec.get("is_reply_present")),
        "is_attachment_present": bool(rec.get("is_attachment_present")),
        "review_metadata_suspect_candidate": bool(
            rec.get("review_metadata_suspect_candidate")
        ),
        "crawl_batch": rec.get("crawl_batch"),
        "crawl_time": rec.get("crawl_time"),
        "raw_record_id": rec.get("raw_record_id"),
        "raw_file": rec.get("raw_file"),
        "raw_line_number": rec.get("raw_line_number"),
        "gold_version": rec.get("gold_version") or "tv2-gold-2.0",
        "tv6_pipeline_version": TV6_PIPELINE_VERSION,
    }

    # Ensure all canonical fields are present in the dictionary
    for field in TV6_CANONICAL_FIELDS:
        if field not in transformed:
            transformed[field] = None

    return transformed


def calculate_percentiles(values: List[float], percentiles: List[float]) -> Dict[str, float]:
    """Calculate given percentiles from a list of numbers."""
    if not values:
        return {f"p{int(p)}": 0.0 for p in percentiles}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    res: Dict[str, float] = {}
    for p in percentiles:
        k = (n - 1) * (p / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            val = sorted_vals[int(k)]
        else:
            val = sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f)
        res[f"p{int(p)}"] = round(val, 2)
    return res


def compute_statistics(
    all_records: List[Dict[str, Any]],
    usable_records: List[Dict[str, Any]],
    unusable_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute detailed dataset statistics and quality audit metrics."""
    total_count = len(all_records)
    usable_count = len(usable_records)
    unusable_count = len(unusable_records)

    # Breakdown by Source
    source_counts = Counter(r["source"] for r in all_records)
    source_usable_counts = Counter(r["source"] for r in usable_records)

    # Breakdown by Category
    category_counts = Counter(r["category"] for r in all_records)
    category_usable_counts = Counter(r["category"] for r in usable_records)

    # Breakdown by Rating
    rating_counts = Counter(r["rating_raw"] for r in all_records)
    rating_usable_counts = Counter(r["rating_raw"] for r in usable_records)

    # Sentiment distribution according to baseline rating map
    sentiment_counts = Counter(
        RATING_SENTIMENT_MAP.get(r["rating_raw"], "unknown")
        for r in usable_records
    )

    # Text length metrics for usable reviews
    char_lengths: List[float] = []
    word_lengths: List[float] = []
    for r in usable_records:
        text = r.get("review_text_normalized") or ""
        char_lengths.append(float(len(text)))
        words = text.split()
        word_lengths.append(float(len(words)))

    char_stats = {
        "min": min(char_lengths) if char_lengths else 0,
        "max": max(char_lengths) if char_lengths else 0,
        "mean": round(sum(char_lengths) / len(char_lengths), 2) if char_lengths else 0.0,
        **calculate_percentiles(char_lengths, [25, 50, 75, 90, 95, 99]),
    }
    word_stats = {
        "min": min(word_lengths) if word_lengths else 0,
        "max": max(word_lengths) if word_lengths else 0,
        "mean": round(sum(word_lengths) / len(word_lengths), 2) if word_lengths else 0.0,
        **calculate_percentiles(word_lengths, [25, 50, 75, 90, 95, 99]),
    }

    # Unusable text reasons
    unusable_status = Counter(r.get("review_text_status") for r in unusable_records)
    unusable_by_source = Counter(r.get("source") for r in unusable_records)
    suspect_count = sum(1 for r in all_records if r.get("review_metadata_suspect_candidate"))

    # Missingness across canonical fields
    missing_rates: Dict[str, Dict[str, Any]] = {}
    for field in TV6_CANONICAL_FIELDS:
        missing_cnt = sum(1 for r in all_records if r.get(field) is None or r.get(field) == "")
        missing_rates[field] = {
            "missing_count": missing_cnt,
            "missing_rate_pct": round(missing_cnt / total_count * 100.0, 2) if total_count else 0.0,
        }

    # Unique text ratio
    unique_usable_texts = len(set(r.get("review_text_normalized") for r in usable_records))

    stats: Dict[str, Any] = {
        "pipeline_version": TV6_PIPELINE_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_input_reviews": total_count,
            "usable_nlp_reviews": usable_count,
            "usable_nlp_pct": round(usable_count / total_count * 100.0, 2) if total_count else 0.0,
            "unusable_reviews": unusable_count,
            "unusable_pct": round(unusable_count / total_count * 100.0, 2) if total_count else 0.0,
            "unique_usable_texts": unique_usable_texts,
            "unique_text_ratio_pct": round(unique_usable_texts / usable_count * 100.0, 2) if usable_count else 0.0,
            "suspect_metadata_candidates": suspect_count,
        },
        "breakdown_by_source": {
            s: {
                "total": source_counts.get(s, 0),
                "usable": source_usable_counts.get(s, 0),
                "retention_rate_pct": round(
                    source_usable_counts.get(s, 0) / source_counts.get(s, 1) * 100.0, 2
                ),
            }
            for s in sorted(source_counts.keys())
        },
        "breakdown_by_category": {
            c: {
                "total": category_counts.get(c, 0),
                "usable": category_usable_counts.get(c, 0),
                "retention_rate_pct": round(
                    category_usable_counts.get(c, 0) / category_counts.get(c, 1) * 100.0, 2
                ),
            }
            for c in sorted(category_counts.keys())
        },
        "breakdown_by_rating": {
            "total_records": dict(sorted(rating_counts.items())),
            "usable_records": dict(sorted(rating_usable_counts.items())),
        },
        "sentiment_baseline_distribution": {
            label: {
                "count": count,
                "share_pct": round(count / usable_count * 100.0, 2) if usable_count else 0.0,
            }
            for label, count in sentiment_counts.items()
        },
        "text_length_distribution": {
            "characters": char_stats,
            "words": word_stats,
        },
        "unusable_breakdown": {
            "status_reasons": dict(unusable_status),
            "by_source": dict(unusable_by_source),
        },
        "field_missingness": missing_rates,
    }

    return stats


def write_jsonl(file_path: Path, records: List[Dict[str, Any]]) -> None:
    """Write list of dictionaries to JSONL format."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8", newline="\n") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    logger.info("Exported %d records to %s", len(records), file_path)


def run_build_analytical_view(
    fact_reviews_path: Path = FACT_REVIEWS_FILE,
    dim_parents_path: Path = DIM_SOURCE_PARENTS_FILE,
    output_dir: Path = DATA_TV6_DIR,
) -> Dict[str, Any]:
    """Execute Step 0 end-to-end: Load, validate, transform, split, and generate manifest."""
    logger.info("=== STARTING STEP 0: TV6 REVIEW ANALYTICAL VIEW CREATION ===")
    start_time = datetime.now()

    # 1. Validation & Input Integrity Check
    if not fact_reviews_path.exists():
        raise FileNotFoundError(f"Input fact_reviews file does not exist: {fact_reviews_path}")
    if not dim_parents_path.exists():
        raise FileNotFoundError(f"Input dim_source_parents file does not exist: {dim_parents_path}")

    input_reviews_sha256 = compute_file_sha256(fact_reviews_path)
    input_parents_sha256 = compute_file_sha256(dim_parents_path)

    # 2. Load Parents Reference for Enrichment
    parent_map = load_dim_source_parents(dim_parents_path)

    # 3. Stream & Transform Reviews
    all_records: List[Dict[str, Any]] = []
    usable_records: List[Dict[str, Any]] = []
    unusable_records: List[Dict[str, Any]] = []

    for rec in stream_fact_reviews(fact_reviews_path):
        transformed = transform_review_record(rec, parent_map)
        all_records.append(transformed)

        if transformed["review_usable"] is True and transformed["review_text_normalized"]:
            usable_records.append(transformed)
        else:
            unusable_records.append(transformed)

    logger.info(
        "Processed %d reviews: %d usable, %d unusable.",
        len(all_records),
        len(usable_records),
        len(unusable_records),
    )

    # 4. Export JSONL Views
    output_dir.mkdir(parents=True, exist_ok=True)
    DOCS_TV6_DIR.mkdir(parents=True, exist_ok=True)

    write_jsonl(REVIEWS_TV6_ALL_FILE, all_records)
    write_jsonl(REVIEWS_TV6_USABLE_FILE, usable_records)
    write_jsonl(REVIEWS_TV6_UNUSABLE_FILE, unusable_records)

    # 5. Compute Statistics & Manifest
    manifest = compute_statistics(all_records, usable_records, unusable_records)
    manifest["inputs"] = {
        "fact_reviews_file": str(fact_reviews_path.relative_to(fact_reviews_path.parents[2])),
        "fact_reviews_sha256": input_reviews_sha256,
        "dim_parents_file": str(dim_parents_path.relative_to(dim_parents_path.parents[2])),
        "dim_parents_sha256": input_parents_sha256,
    }
    manifest["outputs"] = {
        "reviews_tv6_all": {
            "path": str(REVIEWS_TV6_ALL_FILE.relative_to(output_dir.parents[1])),
            "record_count": len(all_records),
            "sha256": compute_file_sha256(REVIEWS_TV6_ALL_FILE),
        },
        "reviews_tv6_usable": {
            "path": str(REVIEWS_TV6_USABLE_FILE.relative_to(output_dir.parents[1])),
            "record_count": len(usable_records),
            "sha256": compute_file_sha256(REVIEWS_TV6_USABLE_FILE),
        },
        "reviews_tv6_unusable": {
            "path": str(REVIEWS_TV6_UNUSABLE_FILE.relative_to(output_dir.parents[1])),
            "record_count": len(unusable_records),
            "sha256": compute_file_sha256(REVIEWS_TV6_UNUSABLE_FILE),
        },
    }

    manifest_json_str = json.dumps(manifest, ensure_ascii=False, indent=2)

    # Write manifest to data/tv6 and docs/tv6
    STEP0_MANIFEST_FILE.write_text(manifest_json_str, encoding="utf-8")
    DOCS_STEP0_MANIFEST_FILE.write_text(manifest_json_str, encoding="utf-8")
    logger.info("Manifest exported to %s and %s", STEP0_MANIFEST_FILE, DOCS_STEP0_MANIFEST_FILE)

    duration = (datetime.now() - start_time).total_seconds()
    logger.info("=== STEP 0 COMPLETED IN %.2f SECONDS ===", duration)

    return manifest


if __name__ == "__main__":
    run_build_analytical_view()
