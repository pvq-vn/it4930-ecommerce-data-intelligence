"""Build Gold v2 from Silver v2, retaining raw provenance and normalized fields."""
from pathlib import Path
from collections import defaultdict
import hashlib,json
import re
ROOT=Path(__file__).resolve().parents[1]; IN=ROOT/'data'/'silver_v2'; OUT=ROOT/'data'/'gold_v2'; PROCESSED=ROOT/'data'/'processed'; REPORT=ROOT/'reports'
FEATURE_FIELDS=["listing_record_id","source_parent_id","source","category","brand_raw","brand_norm","seller_raw","price_vnd","original_price_vnd","discount_rate","is_price_missing","availability_status","rating_norm","has_rating","review_count_normalized","total_sold_raw","total_sold_normalized","installed_ram_gb","max_ram_gb","battery_mah","battery_wh","charger_watt","cpu_norm","gpu_norm","storage_gb","color_norm","screen_size_inch","operating_system_norm","camera_mp","display_type_norm","network_type_norm"]
def read(n):
 with (IN/n).open(encoding='utf8') as f:return [json.loads(x) for x in f if x.strip()]
def non(v): return v is not None and v not in ('',[],{})
def review_rating_norm(v, source):
 try:
  x=float(v)
 except (TypeError,ValueError):
  return None
 # All observed review sources use the native 1–5 star scale; preserve
 # the raw value and expose a bounded numeric value for downstream analysis.
 return x if 0 <= x <= 5 else None
def normalize_product_name(v):
 if not isinstance(v,str): return v
 # Remove a confirmed commercial suffix while preserving the raw parent name in Gold.
 s=re.sub(r'^\s*\u0111\u1eb7t tr\u01b0\u1edbc\s+','',v,flags=re.I)
 s=re.sub(r'\s+ch\u00ednh h\u00e3ng\s+t\u1ea1i\s+viettel store!?$','',s,flags=re.I)
 return re.sub(r'\s*(?:-\s*|\|\s*)(?:b\u1ea3o h\u00e0nh\b.*|ch\u00ednh h\u00e3ng\b.*|nh\u1eadp kh\u1ea9u ch\u00ednh h\u00e3ng\b.*|\u0111\u00e3 k\u00edch ho\u1ea1t\b.*)$','',s,flags=re.I).strip()
def pk(r): return (r.get('source'),r.get('category'),r.get('parent_product_id_raw'))
def pid(k): return hashlib.sha256(json.dumps(k,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def write(n,rs):
 with (OUT/n).open('w',encoding='utf8',newline='\n') as f:
  for r in rs:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
def write_processed(n,rs):
 with (PROCESSED/n).open('w',encoding='utf8',newline='\n') as f:
  for r in rs:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
def main():
 ps=read('products_silver_v2.jsonl'); rs=read('reviews_silver_v2.jsonl'); reps=read('review_replies_silver_v2.jsonl'); groups=defaultdict(list)
 for r in ps:groups[pk(r)].append(r)
 ids={k:pid(k) for k in groups}; dims=[]
 for k,items in sorted(groups.items(),key=lambda x:str(x[0])):
  vals=lambda f:sorted({str(r.get(f)) for r in items if non(r.get(f))}); names,urls=vals('parent_product_name_raw'),vals('parent_url_raw'); first=items[0]
  dims.append({'source_parent_id':ids[k],'source':k[0],'category':k[1],'parent_product_id_raw':k[2],'representative_parent_name_raw':first.get('parent_product_name_raw'),'representative_parent_url_raw':first.get('parent_url_raw'),'listing_count':len(items),'distinct_parent_names':names,'distinct_parent_urls':urls,'parent_conflict_flag':len(names)>1 or len(urls)>1,'representative_raw_record_id':first.get('raw_record_id')})
 listings=[]
 for r in ps:
  x=dict(r); x.update({'listing_record_id':r.get('raw_record_id'),'source_parent_id':ids[pk(r)],'gold_version':'tv2-gold-2.0'}); listings.append(x)
 review_parent={}; reviews=[]
 for r in rs:
  x=dict(r); x.update({'review_record_id':r.get('raw_record_id'),'source_parent_id':ids.get(pk(r)),'gold_version':'tv2-gold-2.0'}); reviews.append(x); review_parent[r.get('raw_record_id')]=ids.get(pk(r))
 replies=[]
 for r in reps:
  x=dict(r); x.update({'reply_record_id':f"{r.get('parent_review_record_id')}::{r.get('reply_index')}",'source_parent_id':review_parent.get(r.get('parent_review_record_id')),'gold_version':'tv2-gold-2.0'}); replies.append(x)
 features=[{k:r.get(k) for k in FEATURE_FIELDS} for r in listings]
 parent_names={d['source_parent_id']:normalize_product_name(d.get('representative_parent_name_raw')) for d in dims}
 processed_products=[{'listing_record_id':r.get('listing_record_id'),'source_parent_id':r.get('source_parent_id'),'product_name':parent_names.get(r.get('source_parent_id')),**{k:v for k,v in r.items() if k not in {'listing_record_id','source_parent_id','brand_raw','total_sold_raw'}}} for r in features]
 processed_reviews=[{'review_record_id':r.get('review_record_id'),'source_parent_id':r.get('source_parent_id'),'product_name':parent_names.get(r.get('source_parent_id')),**{k:r.get(k) for k in ['source','category','rating_raw']},'rating_norm':review_rating_norm(r.get('rating_raw'),r.get('source')),**{k:r.get(k) for k in ['review_text_normalized','author_raw','review_time_raw','review_usable','is_reply_present','is_attachment_present','review_metadata_suspect_candidate']}} for r in reviews]
 OUT.mkdir(parents=True,exist_ok=True); PROCESSED.mkdir(parents=True,exist_ok=True); write('dim_source_parents.jsonl',dims);write('fact_listings.jsonl',listings);write('fact_listings_features.jsonl',features);write('fact_reviews.jsonl',reviews);write('fact_review_replies.jsonl',replies);write_processed('products_processed.jsonl',processed_products);write_processed('reviews_processed.jsonl',processed_reviews)
 report={'pipeline_stage':'gold_v2','source':'silver_v2','outputs':{'dim_source_parents':len(dims),'fact_listings':len(listings),'fact_listings_features':len(features),'fact_reviews':len(reviews),'fact_review_replies':len(replies),'products_processed':len(features),'reviews_processed':len(processed_reviews)},'feature_fields':FEATURE_FIELDS,'processed_review_fields':list(processed_reviews[0]) if processed_reviews else [],'normalized_fields_in_listings':all('price_vnd' in r and 'availability_status' in r for r in listings),'raw_provenance_preserved':all(r.get('raw_record_id') and r.get('raw_file') for r in listings+reviews),'cross_store_identity_resolved':False}
 REPORT.mkdir(exist_ok=True);(REPORT/'gold_v2_quality_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
