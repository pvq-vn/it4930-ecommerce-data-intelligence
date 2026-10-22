"""Validate conservative hardware extraction outputs and produce review samples."""
from pathlib import Path
from collections import Counter
import json
ROOT=Path(__file__).resolve().parents[1]; SILVER=ROOT/"data"/"silver_v2"; REPORT=ROOT/"reports"
def main():
 rows=[]
 with (SILVER/"products_silver_v2.jsonl").open(encoding='utf8') as f:
  rows=[json.loads(x) for x in f if x.strip()]
 conf=Counter(r.get('hardware_extraction_confidence') for r in rows)
 bad=[]; samples={}
 for r in rows:
  if r.get('installed_ram_gb') is not None and r.get('max_ram_gb') is not None and r['installed_ram_gb']>r['max_ram_gb']:
   bad.append({'source':r.get('source'),'category':r.get('category'),'raw_file':r.get('raw_file'),'raw_line_number':r.get('raw_line_number'),'installed_ram_gb':r['installed_ram_gb'],'max_ram_gb':r['max_ram_gb']})
  c=r.get('hardware_extraction_confidence')
  if c not in samples: samples[c]={'raw_file':r.get('raw_file'),'raw_line_number':r.get('raw_line_number'),'attributes_raw':r.get('attributes_raw'),'installed_ram_gb':r.get('installed_ram_gb'),'max_ram_gb':r.get('max_ram_gb'),'battery_mah':r.get('battery_mah'),'battery_wh':r.get('battery_wh'),'charger_watt':r.get('charger_watt')}
 out={'pipeline_stage':'attribute_validation','records':len(rows),'confidence_counts':dict(conf),'ram_current_above_max_count':len(bad),'ram_conflict_examples':bad[:50],'confidence_samples':samples,'status':'REVIEW_REQUIRED' if bad else 'PASSED','notes':['Samples are for human validation; confidence is not ground truth.','No values were overwritten and no rows were removed.']}
 REPORT.mkdir(exist_ok=True); (REPORT/'attribute_validation_report.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8'); print(json.dumps({'status':out['status'],'confidence_counts':dict(conf),'ram_conflicts':len(bad)},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
