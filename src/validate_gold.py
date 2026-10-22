"""Read-only validation of Gold grains and representative joins."""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold_v2"
REPORTS = ROOT / "reports"

def rows(name):
    with (GOLD / name).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

def pk_parent(r): return (r.get("source"), r.get("category"), r.get("parent_product_id_raw"))

def main():
    dim = rows("dim_source_parents.jsonl"); listings = rows("fact_listings.jsonl")
    reviews = rows("fact_reviews.jsonl"); replies = rows("fact_review_replies.jsonl")
    parent_listings = defaultdict(list)
    for x in listings: parent_listings[(x.get("source"), x.get("category"), x.get("parent_product_id_raw"))].append(x)
    review_join_sizes = Counter()
    review_to_parent = 0
    for r in reviews:
        n = len(parent_listings.get(pk_parent(r), [])); review_join_sizes[n] += 1
        if n: review_to_parent += 1
    dim_ids = [x.get("source_parent_id") for x in dim]
    listing_ids = [x.get("listing_record_id") for x in listings]
    review_ids = [x.get("review_record_id") for x in reviews]
    reply_ids = [x.get("reply_record_id") for x in replies]
    # A parent-level join is intentionally one-to-many; report its expanded size.
    expanded = sum(review_join_sizes[n] * n for n in review_join_sizes)
    report = {
        "pipeline_stage": "gold_validation",
        "counts": {"dim_source_parents":len(dim),"fact_listings":len(listings),"fact_reviews":len(reviews),"fact_review_replies":len(replies)},
        "unique_keys": {"source_parent_id": len(dim_ids)==len(set(dim_ids)), "listing_record_id":len(listing_ids)==len(set(listing_ids)), "review_record_id":len(review_ids)==len(set(review_ids)), "reply_record_id":len(reply_ids)==len(set(reply_ids))},
        "parent_keys": {"listing_parent_keys":len(parent_listings), "dim_parent_keys":len({(x.get('source'),x.get('category'),x.get('parent_product_id_raw')) for x in dim}), "reviews_with_parent":review_to_parent, "reviews_without_parent":len(reviews)-review_to_parent},
        "review_parent_join_size_distribution": {str(k):v for k,v in sorted(review_join_sizes.items())},
        "hypothetical_parent_join_rows": expanded,
        "join_warning": "Joining reviews to all listing rows by source/category/parent is one-to-many; use variant_link_status before variant-level joins.",
        "cross_store_identity_resolved": False,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS/"gold_v2_validation_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Gold v2 validation", "", "Read-only validation of Gold v2 table grains and joins.", "", f"- Counts: {report['counts']}", f"- Unique keys: {report['unique_keys']}", f"- Reviews with source-scoped parent: {review_to_parent}/{len(reviews)}", f"- Hypothetical rows if every review joins every listing of its parent: {expanded}", "", "The expanded count is diagnostic; it is not a canonical review count."]
    (REPORTS/"gold_v2_validation_report.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__ == "__main__": main()
