"""Run the TV2 data pipeline in deterministic stages.

The orchestrator never edits data/raw. Each stage writes versioned outputs or
reports and the run stops on the first failed command.
"""
from __future__ import annotations
from pathlib import Path
import json, subprocess, sys, time

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"reports"
STAGES=[
    ("S0_profile_raw", "src/profile_data.py"),
    ("S1_build_staging", "src/build_staging.py"),
    ("S2_audit_keys", "src/audit_keys.py"),
    ("S3_profile_missing", "src/profile_missing.py"),
    ("S4_build_silver_v2", "src/build_silver_v2.py"),
    ("S5_audit_review_metadata", "src/audit_review_metadata.py"),
    ("S6_build_gold_v2", "src/build_gold_v2.py"),
    ("S7_validate_gold", "src/validate_gold.py"),
    ("S8_validate_attributes", "src/validate_attributes.py"),
    ("S9_quality_gates", "src/quality_gates.py"),
    ("S10_release_manifest", "src/build_release_manifest.py"),
]

def main():
    run_id=time.strftime("%Y%m%dT%H%M%S")
    results=[]; ok=True
    for name, script in STAGES:
        start=time.time()
        p=subprocess.run([sys.executable, str(ROOT/script)], cwd=ROOT, text=True, capture_output=True)
        result={"stage":name,"script":script,"returncode":p.returncode,"duration_seconds":round(time.time()-start,3),"stdout_tail":p.stdout[-2000:],"stderr_tail":p.stderr[-2000:]}
        results.append(result)
        if p.returncode!=0:
            ok=False; break
    gate_ready=False
    gate_report=REPORTS/"quality_gate_report.json"
    if ok and gate_report.exists():
        try: gate_ready=bool(json.loads(gate_report.read_text(encoding="utf8")).get("final_release_ready",False))
        except (OSError, json.JSONDecodeError): gate_ready=False
    out={"pipeline":"tv2","run_id":run_id,"status":"PASSED" if ok else "FAILED","stages":results,"raw_immutable":True,"final_release_ready":gate_ready,"note":"final_release_ready is read from quality_gate_report.json after all stages pass."}
    REPORTS.mkdir(exist_ok=True); (REPORTS/"pipeline_run_latest.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"run_id":run_id,"status":out["status"],"stages_completed":len(results),"final_release_ready":gate_ready},ensure_ascii=False,indent=2))
    raise SystemExit(0 if ok else 1)
if __name__=="__main__": main()
