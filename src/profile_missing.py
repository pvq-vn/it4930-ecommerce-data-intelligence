"""Profile missingness and sentinel values by source/category (read-only)."""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]; STAGING=ROOT/"data"/"staging"; REPORTS=ROOT/"reports"
PRODUCT_FIELDS=["product_id_raw","parent_product_id_raw","product_name_raw","parent_product_name_raw","variant_name_raw","variant_color_raw","variant_sku_raw","availability_raw","price_raw","original_price_raw","seller_raw","rating_raw","review_count_raw","attributes_raw","brand_raw","total_sold_raw","raw_payload"]
REVIEW_FIELDS=["parent_product_id_raw","review_id_raw","rating_raw","review_text_raw","author_raw","review_time_raw","like_count_raw","review_product_code_raw","variant_code_raw","variant_sku_raw","buy_date_raw","reply_raw","attached_files_raw","raw_payload"]

def classify(v):
    if v is None: return "NULL"
    if isinstance(v,str) and not v.strip(): return "EMPTY_OR_WHITESPACE"
    if v == [] or v == {}: return "EMPTY_CONTAINER"
    if v == 0 or v == "0": return "ZERO_SENTINEL_CANDIDATE"
    if isinstance(v,str) and v.strip().lower() in {"n/a","na","none","null","unknown","không có","khong co","liên hệ","lien he"}: return "SPECIAL_STRING_CANDIDATE"
    return "PRESENT"

def run(file, fields):
    by=defaultdict(lambda: {f:Counter() for f in fields}); totals=Counter()
    with (STAGING/file).open(encoding="utf-8") as h:
        for line in h:
            if not line.strip(): continue
            r=json.loads(line); scope=f"{r.get('source')}/{r.get('category')}"; totals[scope]+=1
            for f in fields: by[scope][f][classify(r.get(f))]+=1
    return {scope:{f:dict(c) for f,c in fields_c.items()} for scope,fields_c in sorted(by.items())}, dict(totals)

def main():
    products, pt=run("products_staging.jsonl",PRODUCT_FIELDS); reviews, rt=run("reviews_staging.jsonl",REVIEW_FIELDS)
    out={"pipeline_stage":"missing_profile","read_only":True,"products":{"records_by_scope":pt,"fields":products},"reviews":{"records_by_scope":rt,"fields":reviews},"interpretation":["NULL, empty strings, empty containers and zero are reported separately.","Special strings are candidates for source-specific review, not automatic missing values.","No values were imputed, dropped or overwritten."]}
    REPORTS.mkdir(exist_ok=True); (REPORTS/"missing_profile.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    # Compact markdown for human review.
    lines=["# Missing profile by source/category","","Read-only profile over Staging. No values were changed.","","Legend: `NULL`, `EMPTY_OR_WHITESPACE`, `EMPTY_CONTAINER`, `ZERO_SENTINEL_CANDIDATE`, `SPECIAL_STRING_CANDIDATE`, `PRESENT`.",""]
    for label, data, totals in [("Products",products,pt),("Reviews",reviews,rt)]:
        lines += [f"## {label}",""]
        for scope in sorted(data):
            lines.append(f"### {scope} ({totals[scope]} records)")
            lines.append("")
            for field, counts in data[scope].items():
                unusual={k:v for k,v in counts.items() if k!="PRESENT"}
                if unusual: lines.append(f"- `{field}`: {unusual}")
            lines.append("")
    (REPORTS/"missing_profile.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"product_scopes":len(pt),"review_scopes":len(rt),"report":"reports/missing_profile.md"},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
