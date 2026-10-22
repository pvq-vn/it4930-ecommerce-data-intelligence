"""Build a reproducible TV2 release manifest and lineage checks."""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"
GOLD = ROOT / "data" / "gold_v2"
REPORTS = ROOT / "reports"

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()
def count(path):
    with path.open(encoding="utf-8") as f: return sum(1 for x in f if x.strip())
def rows(path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip(): yield json.loads(line)

def main():
    raw_files=[]
    for p in sorted(RAW.rglob("*.jsonl")):
        raw_files.append({"file":str(p.relative_to(ROOT)).replace("\\","/"),"records":count(p),"sha256":sha(p)})
    stage_files=[]; gold_files=[]
    for base, out in [(STAGING,stage_files),(GOLD,gold_files)]:
        for p in sorted(base.glob("*.jsonl")):
            out.append({"file":str(p.relative_to(ROOT)).replace("\\","/"),"records":count(p),"sha256":sha(p)})
    # Provenance checks: Gold records must retain source and raw_record_id where applicable.
    prov = {}
    for name in ["fact_listings.jsonl","fact_reviews.jsonl"]:
        rs=list(rows(GOLD/name)); prov[name]={"records":len(rs),"missing_raw_record_id":sum(not r.get("raw_record_id") for r in rs),"missing_raw_file":sum(not r.get("raw_file") for r in rs),"missing_raw_line_number":sum(r.get("raw_line_number") is None for r in rs)}
    rr=list(rows(GOLD/"fact_review_replies.jsonl")); prov["fact_review_replies.jsonl"]={"records":len(rr),"missing_parent_review_record_id":sum(not r.get("parent_review_record_id") for r in rr)}
    manifest={"release":"tv2-data-v1","pipeline_version":"tv2-gold-2.0","raw_immutable":True,"raw_files":raw_files,"staging_files":stage_files,"gold_files":gold_files,"provenance_checks":prov,"quality_reports":["reports/staging_quality_report.json","reports/key_audit.json","reports/gold_v2_quality_report.json","reports/gold_v2_validation_report.json","reports/quality_gate_report.json"],"notes":["Gold is source-scoped and does not resolve cross-store identity.","No raw or staging records were deleted or overwritten.","Quality flags describe observations; they are not automatic deletion decisions."]}
    REPORTS.mkdir(exist_ok=True); (REPORTS/"release_manifest_tv2_v1.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"release":manifest["release"],"raw_files":len(raw_files),"staging_files":len(stage_files),"gold_files":len(gold_files),"provenance_checks":prov},ensure_ascii=False,indent=2))
if __name__=="__main__": main()
