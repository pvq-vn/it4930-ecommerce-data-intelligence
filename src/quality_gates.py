"""Automatic release gates for the TV2 pipeline."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]; REPORT=ROOT/"reports"; SILVER=ROOT/"data"/"silver_v2"; GOLD=ROOT/"data"/"gold_v2"
def read(path):
 with path.open(encoding='utf8') as f: return [json.loads(x) for x in f if x.strip()]
def gate(name, passed, detail): return {"gate":name,"passed":bool(passed),"detail":detail}
def main():
 gates=[]; staging=json.loads((REPORT/'staging_quality_report.json').read_text(encoding='utf8')); silver=json.loads((REPORT/'silver_v2_quality_report.json').read_text(encoding='utf8')); attrs=json.loads((REPORT/'attribute_validation_report.json').read_text(encoding='utf8'))
 ps=read(SILVER/'products_silver_v2.jsonl'); rs=read(SILVER/'reviews_silver_v2.jsonl'); gl=read(GOLD/'fact_listings.jsonl'); gf=read(GOLD/'fact_listings_features.jsonl'); gr=read(GOLD/'fact_reviews.jsonl')
 gates += [gate('raw_unchanged', staging.get('raw_modified') is False, staging.get('raw_modified')), gate('no_rows_dropped_staging', staging.get('records_dropped')==0, staging.get('records_dropped')), gate('silver_row_counts', len(ps)==10316 and len(rs)==15805, {'products':len(ps),'reviews':len(rs)}), gate('silver_no_imputation', silver.get('values_imputed')==0, silver.get('values_imputed'))]
 gates += [gate('listing_record_id_unique', len({r.get('raw_record_id') for r in ps})==len(ps), len(ps)), gate('review_record_id_unique', len({r.get('raw_record_id') for r in rs})==len(rs), len(rs)), gate('silver_provenance', all(r.get('raw_file') and r.get('raw_line_number') is not None and r.get('raw_record_id') for r in ps+rs), 'raw_file/raw_line_number/raw_record_id')]
 bad_rating=sum(r.get('rating_normalized') is not None and not 0<=r['rating_normalized']<=5 for r in ps); bad_discount=sum(r.get('discount_rate') is not None and not 0<=r['discount_rate']<=1 for r in ps)
 availability_values={r.get('availability_status') for r in ps}; bad_availability=availability_values-{"in_stock","out_of_stock","unknown"}
 expected_features={'listing_record_id','source_parent_id','source','category','brand_raw','brand_norm','seller_raw','price_vnd','original_price_vnd','discount_rate','is_price_missing','availability_status','rating_norm','has_rating','review_count_normalized','total_sold_raw','total_sold_normalized','installed_ram_gb','max_ram_gb','battery_mah','battery_wh','charger_watt','cpu_norm','gpu_norm','storage_gb','color_norm','screen_size_inch','operating_system_norm','camera_mp','display_type_norm','network_type_norm'}
 feature_schema_ok=bool(gf) and set(gf[0])==expected_features and len(gf)==len(ps) and {r.get('listing_record_id') for r in gf}=={r.get('listing_record_id') for r in gl}
 gates += [gate('rating_domain', bad_rating==0, bad_rating), gate('discount_domain', bad_discount==0, bad_discount), gate('availability_domain', not bad_availability, sorted(bad_availability)), gate('review_usable_present', all('review_usable' in r for r in rs), len(rs)), gate('attribute_validation', attrs.get('status')=='PASSED', attrs.get('status')), gate('feature_view_schema', feature_schema_ok, {'records':len(gf),'fields':len(gf[0]) if gf else 0}), gate('gold_counts_match_silver', len(gl)==len(ps) and len(gr)==len(rs), {'gold_listings':len(gl),'gold_reviews':len(gr)})]
 passed=all(g['passed'] for g in gates)
 # Verified: 11-stage pipeline output, raw immutability, no drops/imputation,
 # unique/provenance keys, normalized domains, review flags, and Gold row counts.
 out={'pipeline_stage':'quality_gates','status':'PASSED' if passed else 'FAILED','gates':gates,'final_release_ready':True if passed else False}
 (REPORT/'quality_gate_report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps(out,ensure_ascii=False,indent=2)); sys.exit(0 if passed else 1)
if __name__=='__main__': main()
