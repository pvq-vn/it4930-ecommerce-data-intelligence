"""Build a reversible, non-destructive staging layer from data/raw.

Raw records are copied unchanged and enriched with provenance, typed candidates,
and quality flags. No record is removed and no raw field is overwritten.
Standard library only.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "staging"
REPORTS = ROOT / "reports"
VERSION = "staging-v1"


def is_empty(value):
    return value is None or value == "" or value == [] or value == {}


def missing_text(value):
    return value is None or (isinstance(value, str) and not value.strip())


def has_attachment(value):
    """Detect actual media while treating structural empty containers as empty."""
    if value is None or value == "":
        return False
    if isinstance(value, str):
        try:
            return has_attachment(json.loads(value))
        except (json.JSONDecodeError, TypeError):
            return bool(value.strip())
    if isinstance(value, list):
        return any(has_attachment(item) for item in value)
    if isinstance(value, dict):
        if "images" in value or "videos" in value:
            return bool(value.get("images")) or bool(value.get("videos"))
        return bool(value)
    return True


def parse_money(value):
    """Return (numeric candidate, status), without mutating raw value."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, "MISSING"
    if isinstance(value, bool):
        return None, "UNPARSED"
    if isinstance(value, (int, float)):
        return value, "PARSED"
    if not isinstance(value, str):
        return None, "UNPARSED"
    text = value.strip()
    if text.lower() in {"liên hệ", "lien he", "contact"}:
        return None, "CONTACT"
    if not re.search(r"\d", text):
        return None, "UNPARSED"
    # Raw money strings in this package use integer VND notation. Preserve
    # ambiguity rather than inventing decimals for unknown formats.
    if re.fullmatch(r"[\d\s.,]+(?:₫|đ|vnd)?", text, flags=re.IGNORECASE):
        digits = re.sub(r"\D", "", text)
        return (int(digits), "PARSED") if digits else (None, "UNPARSED")
    return None, "UNPARSED"


def record_id(relative_path: str, line_number: int, raw_line: bytes) -> str:
    payload = relative_path.encode("utf-8") + b"\0" + str(line_number).encode("ascii") + b"\0" + raw_line
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path):
    relative = path.relative_to(ROOT).as_posix()
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            if not raw_line.strip():
                continue
            obj = json.loads(raw_line.decode("utf-8"))
            yield relative, line_number, raw_line.rstrip(b"\r\n"), obj


def base_provenance(relative, line_number, raw_line):
    return {
        "raw_file": relative,
        "raw_line_number": line_number,
        "raw_record_id": record_id(relative, line_number, raw_line),
        "pipeline_version": VERSION,
    }


def product_staging(relative, line_number, raw_line, row):
    out = dict(row)
    out.update(base_provenance(relative, line_number, raw_line))
    price, price_status = parse_money(row.get("price_raw"))
    original, original_status = parse_money(row.get("original_price_raw"))
    rating = row.get("rating_raw")
    review_count = row.get("review_count_raw")
    variant_missing = all(is_empty(row.get(k)) for k in ("variant_sku_raw", "variant_name_raw", "variant_color_raw"))
    out.update({
        "price_value": price,
        "price_parse_status": price_status,
        "original_price_value": original,
        "original_price_parse_status": original_status,
        "is_price_missing": price_status == "MISSING",
        "is_price_zero": price == 0,
        "is_original_price_missing": original_status == "MISSING",
        "is_price_relation_issue": bool(price is not None and original is not None and price > original),
        "rating_value": rating if isinstance(rating, (int, float)) and not isinstance(rating, bool) else None,
        "rating_status": (
            "MISSING" if is_empty(rating) else
            "OUT_OF_DECLARED_RANGE" if isinstance(rating, (int, float)) and rating > 5 else
            "ZERO_WITH_NO_REVIEWS" if rating == 0 and review_count == 0 else
            "OBSERVED"
        ),
        "is_rating_out_of_declared_range": bool(isinstance(rating, (int, float)) and rating > 5),
        "is_review_count_missing": is_empty(review_count),
        "is_total_sold_missing": is_empty(row.get("total_sold_raw")) or (isinstance(row.get("total_sold_raw"), str) and not row["total_sold_raw"].strip()),
        "is_attributes_empty": is_empty(row.get("attributes_raw")),
        "is_variant_identity_missing": variant_missing,
        "is_payload_present": isinstance(row.get("raw_payload"), dict),
    })
    return out


def review_staging(relative, line_number, raw_line, row):
    out = dict(row)
    out.update(base_provenance(relative, line_number, raw_line))
    text = row.get("review_text_raw")
    source = row.get("source")
    payload = row.get("raw_payload")
    variant_missing = all(is_empty(row.get(k)) for k in ("review_product_code_raw", "variant_code_raw", "variant_sku_raw"))
    viettel_candidate = (
        source == "viettelstore" and missing_text(text) and is_empty(row.get("review_time_raw"))
        and isinstance(payload, dict) and set(payload).issubset({"@type", "author", "reviewRating"})
    )
    out.update({
        "is_review_text_missing": text is None,
        "is_review_text_whitespace": isinstance(text, str) and bool(text) and not text.strip(),
        "is_review_text_unusable": missing_text(text),
        "is_review_time_missing": is_empty(row.get("review_time_raw")),
        "is_variant_reference_missing": variant_missing,
        "is_reply_present": not is_empty(row.get("reply_raw")),
        "is_attachment_present": has_attachment(row.get("attached_files_raw")),
        "review_metadata_suspect_candidate": viettel_candidate,
        "rating_status": (
            "MISSING" if is_empty(row.get("rating_raw")) else
            "OUT_OF_DECLARED_RANGE" if isinstance(row.get("rating_raw"), (int, float)) and not 1 <= row["rating_raw"] <= 5 else
            "OBSERVED"
        ),
    })
    return out


def reply_rows(relative, line_number, parent_id, row):
    replies = row.get("reply_raw")
    if not isinstance(replies, list):
        return []
    result = []
    for index, reply in enumerate(replies):
        if not isinstance(reply, dict):
            continue
        item = dict(reply)
        item.update({
            "parent_review_record_id": parent_id,
            "reply_index": index,
            "raw_file": relative,
            "raw_line_number": line_number,
            "pipeline_version": VERSION,
        })
        result.append(item)
    return result


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    products, reviews, replies = [], [], []
    source_counts = Counter()
    flag_counts = Counter()
    input_files = []
    for path in sorted((RAW / "products").glob("*.jsonl")):
        input_files.append(path.relative_to(ROOT).as_posix())
        for rel, line, raw_line, row in read_jsonl(path):
            staged = product_staging(rel, line, raw_line, row)
            products.append(staged)
            source_counts["products"] += 1
            for key, value in staged.items():
                if key.startswith("is_") and value is True:
                    flag_counts[key] += 1
    for path in sorted((RAW / "reviews").glob("*.jsonl")):
        input_files.append(path.relative_to(ROOT).as_posix())
        for rel, line, raw_line, row in read_jsonl(path):
            staged = review_staging(rel, line, raw_line, row)
            reviews.append(staged)
            replies.extend(reply_rows(rel, line, staged["raw_record_id"], row))
            source_counts["reviews"] += 1
            for key, value in staged.items():
                if key.startswith("is_") and value is True:
                    flag_counts[key] += 1
    write_jsonl(OUT / "products_staging.jsonl", products)
    write_jsonl(OUT / "reviews_staging.jsonl", reviews)
    write_jsonl(OUT / "review_replies_staging.jsonl", replies)
    report = {
        "pipeline_version": VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_files": input_files,
        "products": len(products),
        "reviews": len(reviews),
        "replies": len(replies),
        "flag_counts": dict(sorted(flag_counts.items())),
        "review_metadata_suspect_candidates": sum(bool(row.get("review_metadata_suspect_candidate")) for row in reviews),
        "raw_fields_preserved": True,
        "records_dropped": 0,
        "raw_modified": False,
    }
    (REPORTS / "staging_quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
