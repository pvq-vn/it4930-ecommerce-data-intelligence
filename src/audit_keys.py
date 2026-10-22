"""Audit record grain, candidate keys, and review-to-product links.

Read-only with respect to raw and staging records. Produces reports only;
does not create a Gold table or resolve cross-store product identity.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "staging"
REPORTS = ROOT / "reports"


def rows(name):
    path = STAGING / name
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def key(row, *fields):
    return tuple(row.get(field) for field in fields)


def nonempty(value):
    return value is not None and value != "" and value != [] and value != {}


def has_variant_url(row):
    url = row.get("variant_url_raw")
    if not isinstance(url, str) or not url:
        return False
    return bool(re.search(r"[?&](sku|code|variant|color)=", url, flags=re.I))


def candidate_variant_status(row):
    if nonempty(row.get("variant_sku_raw")):
        return "SKU_PRESENT"
    if has_variant_url(row):
        return "URL_PARAMETER"
    if nonempty(row.get("variant_name_raw")) or nonempty(row.get("variant_color_raw")):
        return "NAME_COLOR_CANDIDATE"
    return "UNKNOWN"


def stable_candidate_hash(row):
    payload = json.dumps(
        {
            "source": row.get("source"),
            "category": row.get("category"),
            "parent": row.get("parent_product_id_raw"),
            "variant_name": row.get("variant_name_raw"),
            "variant_color": row.get("variant_color_raw"),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def duplicate_groups(values):
    groups = defaultdict(list)
    for index, value in enumerate(values, 1):
        if value is not None:
            groups[value].append(index)
    return {str(k): v for k, v in groups.items() if len(v) > 1}


def product_audit(product_rows):
    parent_groups = defaultdict(list)
    sku_groups = defaultdict(list)
    sku_across_parents = defaultdict(list)
    candidate_groups = defaultdict(list)
    statuses = Counter()
    for row in product_rows:
        parent_groups[key(row, "source", "category", "parent_product_id_raw")].append(row)
        if nonempty(row.get("variant_sku_raw")):
            sku_groups[key(row, "source", "category", "parent_product_id_raw", "variant_sku_raw")].append(row)
            sku_across_parents[key(row, "source", "category", "variant_sku_raw")].append(row)
        status = candidate_variant_status(row)
        statuses[status] += 1
        if status == "NAME_COLOR_CANDIDATE":
            candidate_groups[(key(row, "source", "category", "parent_product_id_raw"), stable_candidate_hash(row))].append(row)
    duplicate_skus = {
        "|".join(map(str, k)): [r["raw_line_number"] for r in values]
        for k, values in sku_groups.items() if len(values) > 1
    }
    duplicate_skus_across_parents = {
        "|".join(map(str, k)): [
            {"line": r["raw_line_number"], "parent": r.get("parent_product_id_raw")}
            for r in values
        ]
        for k, values in sku_across_parents.items()
        if len({r.get("parent_product_id_raw") for r in values}) > 1
    }
    candidate_collisions = {
        "|".join(map(str, k)): [r["raw_line_number"] for r in values]
        for k, values in candidate_groups.items() if len(values) > 1
    }
    return {
        "records": len(product_rows),
        "source_category_parent_keys": len(parent_groups),
        "parent_size_distribution": dict(sorted(Counter(len(v) for v in parent_groups.values()).items())),
        "variant_identity_status_counts": dict(statuses),
        "duplicate_sku_within_parent": duplicate_skus,
        "duplicate_sku_across_parents": duplicate_skus_across_parents,
        "name_color_candidate_collisions": candidate_collisions,
        "listing_record_id_unique": len({r["raw_record_id"] for r in product_rows}) == len(product_rows),
        "grain_statement": "one observed source listing/variant row per raw_record_id; parent grouping is separate",
    }


def review_audit(review_rows, product_rows):
    product_by_parent = defaultdict(list)
    product_sku = defaultdict(list)
    for row in product_rows:
        parent = key(row, "source", "category", "parent_product_id_raw")
        product_by_parent[parent].append(row)
        if nonempty(row.get("variant_sku_raw")):
            product_sku[(parent, row["variant_sku_raw"])].append(row)

    review_keys = [key(r, "source", "category", "parent_product_id_raw", "review_id_raw") for r in review_rows]
    duplicate_review_keys = duplicate_groups(review_keys)
    orphan_lines = []
    variant_status = Counter()
    link_methods = Counter()
    multiplicity = Counter()
    unresolved_examples = []
    fpt_or_tgdd_code_not_found = []
    for row in review_rows:
        parent = key(row, "source", "category", "parent_product_id_raw")
        products = product_by_parent.get(parent, [])
        if not products:
            orphan_lines.append(row["raw_line_number"])
            variant_status["PARENT_ORPHAN"] += 1
            link_methods["NONE"] += 1
            continue
        multiplicity[len(products)] += 1
        sku = row.get("variant_sku_raw")
        product_code = row.get("review_product_code_raw")
        matches = []
        method = "NONE"
        if nonempty(sku):
            matches = product_sku.get((parent, sku), [])
            method = "REVIEW_VARIANT_SKU"
        elif row.get("source") in {"fptshop", "tgdd"} and nonempty(product_code):
            matches = product_sku.get((parent, product_code), [])
            method = "REVIEW_PRODUCT_CODE_AS_VARIANT_CANDIDATE"
            if not matches:
                fpt_or_tgdd_code_not_found.append(row["raw_line_number"])
        if len(matches) == 1:
            variant_status["VARIANT_MATCHED"] += 1
            link_methods[method] += 1
        elif len(matches) > 1:
            variant_status["VARIANT_AMBIGUOUS"] += 1
            link_methods[method] += 1
        elif method != "NONE":
            variant_status["VARIANT_UNRESOLVED"] += 1
            link_methods[method] += 1
        else:
            variant_status["PARENT_ONLY"] += 1
            link_methods["PARENT_ID"] += 1
        if len(unresolved_examples) < 10 and (not matches or len(matches) != 1):
            unresolved_examples.append({
                "review_line": row["raw_line_number"],
                "source": row.get("source"),
                "parent": row.get("parent_product_id_raw"),
                "review_id": row.get("review_id_raw"),
                "review_product_code": product_code,
                "variant_sku": sku,
                "parent_listing_lines": [p["raw_line_number"] for p in products[:10]],
            })
    return {
        "records": len(review_rows),
        "review_key_unique": len(set(review_keys)) == len(review_keys),
        "duplicate_review_keys": duplicate_review_keys,
        "parent_orphan_lines": orphan_lines,
        "variant_link_status_counts": dict(variant_status),
        "link_method_counts": dict(link_methods),
        "parent_listing_multiplicity_for_reviews": dict(sorted(multiplicity.items())),
        "source_code_candidate_not_found_lines": fpt_or_tgdd_code_not_found,
        "unresolved_examples": unresolved_examples,
        "grain_statement": "one top-level review per raw_record_id; replies are separate records",
    }


def reply_audit(reply_rows_data):
    keys = [key(r, "parent_review_record_id", "reply_index") for r in reply_rows_data]
    return {
        "records": len(reply_rows_data),
        "reply_key_unique": len(keys) == len(set(keys)),
        "grain_statement": "one direct reply element per parent review and reply_index",
    }


def main():
    products = rows("products_staging.jsonl")
    reviews = rows("reviews_staging.jsonl")
    replies = rows("review_replies_staging.jsonl")
    product_result = product_audit(products)
    review_result = review_audit(reviews, products)
    reply_result = reply_audit(replies)
    result = {
        "pipeline_stage": "key-audit",
        "inputs": {
            "products": len(products),
            "reviews": len(reviews),
            "replies": len(replies),
        },
        "products": product_result,
        "reviews": review_result,
        "replies": reply_result,
        "cross_store_identity_resolved": False,
        "gold_tables_created": False,
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "key_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Key and grain audit",
        "",
        "Read-only audit over staging. No Gold tables or cross-store canonical IDs were created.",
        "",
        f"- Product rows: {len(products)}; source/category/parent keys: {product_result['source_category_parent_keys']}",
        f"- Review rows: {len(reviews)}; review keys unique: {review_result['review_key_unique']}",
        f"- Reply rows: {len(replies)}; reply keys unique: {reply_result['reply_key_unique']}",
        f"- Product listing identity statuses: `{product_result['variant_identity_status_counts']}`",
        f"- Review variant link statuses: `{review_result['variant_link_status_counts']}`",
        f"- Review parent orphans: {len(review_result['parent_orphan_lines'])}",
        f"- Duplicate SKU groups within parent: {len(product_result['duplicate_sku_within_parent'])}",
        f"- Duplicate SKU groups across parents: {len(product_result['duplicate_sku_across_parents'])}",
        f"- Name/color candidate collisions: {len(product_result['name_color_candidate_collisions'])}",
        "",
        "## Interpretation",
        "",
        "`raw_record_id` is the stable observed-row identifier. Parent keys are source-scoped. A review may be linked to a parent while remaining unresolved at variant level. Candidate keys are audit evidence, not automatic entity resolution.",
    ]
    (REPORTS / "key_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "products": len(products),
        "reviews": len(reviews),
        "replies": len(replies),
        "parent_keys": product_result["source_category_parent_keys"],
        "variant_identity_status": product_result["variant_identity_status_counts"],
        "review_variant_status": review_result["variant_link_status_counts"],
        "parent_orphans": len(review_result["parent_orphan_lines"]),
        "duplicate_sku_groups": len(product_result["duplicate_sku_within_parent"]),
        "duplicate_sku_across_parents": len(product_result["duplicate_sku_across_parents"]),
        "gold_tables_created": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
