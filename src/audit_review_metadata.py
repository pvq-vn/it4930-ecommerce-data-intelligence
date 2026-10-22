"""Audit review metadata, with explicit Viettel Store checks."""
from pathlib import Path
from collections import Counter
import json, re
ROOT=Path(__file__).resolve().parents[1]; ST=ROOT/"data"/"staging"; RAW=ROOT/"data"/"raw"; REPORT=ROOT/"reports"
def rows(p):
 with p.open(encoding='utf8') as f:
  return [json.loads(x) for x in f if x.strip()]
def empty(v): return v is None or (isinstance(v,str) and not v.strip())
def main():
 reviews=rows(ST/'reviews_staging.jsonl'); products=rows(ST/'products_staging.jsonl')
 by=Counter(); scopes={}
 for r in reviews:
  s=f"{r.get('source')}/{r.get('category')}"; z=scopes.setdefault(s,Counter()); z['records']+=1
  z['text_missing_or_empty']+=empty(r.get('review_text_raw')); z['time_missing']+=empty(r.get('review_time_raw'))
  z['rating_missing']+=empty(r.get('rating_raw')); z['rating_out_of_1_5']+=bool(isinstance(r.get('rating_raw'),(int,float)) and not 1<=r['rating_raw']<=5)
  if r.get('source')=='viettelstore': z['all_rating_five_candidate']+=str(r.get('rating_raw')) in {'5','5.0'}
  by[s]+=1
 # Product payload review totals and observed top-level review totals.
 product_meta=[]
 for p in products:
  payload=p.get('raw_payload'); ld=payload.get('json_ld') if isinstance(payload,dict) else None
  review_meta=ld.get('review') if isinstance(ld,dict) else None
  if isinstance(review_meta,dict):
   product_meta.append({'source':p.get('source'),'category':p.get('category'),'product_line':p.get('raw_line_number'),'payload_review_id':review_meta.get('@id'),'payload_rating':review_meta.get('reviewRating'),'payload_review_count':review_meta.get('reviewCount'),'payload_author':review_meta.get('author')})
 out={'pipeline_stage':'review_metadata_audit','scopes':{k:dict(v) for k,v in sorted(scopes.items())},'viettel_checks':{},'product_payload_review_metadata_records':len(product_meta),'notes':['Metadata candidates are evidence for review quality, not proof of fabricated reviews.','No review was removed or relabeled.']}
 vt=[r for r in reviews if r.get('source')=='viettelstore']; out['viettel_checks']={'reviews':len(vt),'text_missing_or_empty':sum(empty(r.get('review_text_raw')) for r in vt),'time_missing':sum(empty(r.get('review_time_raw')) for r in vt),'ratings':dict(Counter(str(r.get('rating_raw')) for r in vt)),'payload_present':sum(isinstance(r.get('raw_payload'),dict) for r in vt),'metadata_candidate_flagged':sum(bool(r.get('review_metadata_suspect_candidate')) for r in vt)}
 REPORT.mkdir(exist_ok=True); (REPORT/'review_metadata_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(out['viettel_checks'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
