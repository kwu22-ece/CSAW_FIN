#!/usr/bin/env python3
"""Audit actual captures and build reports, rather than infer from RTL models."""
import argparse,csv,json,math,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
TESTS=PACKAGE/"tests"
sys.path.insert(0,str(TESTS))
from candidate_reference import candidate_outputs
from prepare_vectors import completions
from reference import run_reference as baseline

def read_io(path):
    out={}
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): out[(int(r["index"])//2,int(r["channel"]))]=int(r["value"])
    return out

def read_input(path):
    d={}
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if int(r["channel"])==0: d[int(r["index"])]=int(r["value"])
    return [d[i] for i in sorted(d)]

def load_case(run,name,input_path):
    folder=run/name
    actual=read_io(folder/"actual.csv")
    comparison=json.loads((folder/"comparison.json").read_text(encoding="utf-8"))
    return actual,comparison,read_input(input_path)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run",required=True,type=Path)
    ap.add_argument("--repeat-run",type=Path); ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args(); run=args.run.resolve()
    report=json.loads((run/"report.json").read_text(encoding="utf-8"))
    case_status={c["name"]:c["status"] for c in report["cases"]}
    normal={
      "phase3-golden":PACKAGE/"tests/vectors/canonical_golden.csv",
      "noisy-audio-1024":PACKAGE/"tests/vectors/noisy_audio_1024.csv",
      "startup-edges":PACKAGE/"tests/vectors/startup_edges.csv",
      "boundary-stress":PACKAGE/"tests/vectors/boundary_stress.csv",
      "random-negative":PACKAGE/"tests/vectors/random_negative.csv",
      "near-miss-negative":PACKAGE/"tests/vectors/near_miss_negative.csv",
      "split-sequence-negative":PACKAGE/"tests/vectors/split_sequence_negative.csv"}
    normal_details={}; baseline_mismatches=0; echo_mismatches=0
    for name,path in normal.items():
        actual,cmp,samples=load_case(run,name,path)
        baseline_mismatches+=cmp["mismatch_count"]
        normal_details[name]={"status":case_status[name],"samples_compared":cmp["samples_compared"],
                              "mismatch_count":cmp["mismatch_count"]}
        for frame in range(len(samples)):
            n=frame-2; expected=samples[n] if 0<=n<len(samples) else 0
            if actual.get((frame,1))!=expected: echo_mismatches+=1

    coeffs=baseline.load_coeffs(str(PACKAGE/"tests/reference/coeffs.json"))
    active_specs=[
      ("activation-1mhz",PACKAGE/"tests/vectors/trigger_1mhz.csv"),
      ("activation-625khz",PACKAGE/"tests/vectors/trigger_625khz.csv"),
      ("retrigger-2x",PACKAGE/"tests/vectors/retrigger_1mhz.csv")]
    events=[]; pass_mismatches=0; tone_metrics=[]
    for name,path in active_specs:
        actual,cmp,samples=load_case(run,name,path)
        _,model_hits,_=candidate_outputs(samples,coeffs)
        hits=completions(samples)
        if hits!=model_hits: raise SystemExit(f"{name}: trigger scanners disagree")
        for hit in hits:
            window=range(hit,min(hit+128,len(samples)))
            bad=[n for n in window if actual.get((n+2,0))!=samples[n]]
            pass_mismatches+=len(bad)
            events.append({"case":name,"trigger_completion_input_frame":hit,
                "expected_bypass_frames":len(window),
                "observed_raw_pass_through_frames":len(window)-len(bad),
                "success":not bad and len(window)==128})
        hit=hits[-1]; stable_start=hit+65; stable_end=min(hit+128,len(samples))
        if stable_end>stable_start:
            indices=range(stable_start,stable_end)
            raw=[samples[n] for n in indices]; filtered=baseline.fir(samples,coeffs)
            expected=[filtered[n] for n in indices]
            observed=[actual.get((n+2,0)) for n in indices]
            raw_rms=math.sqrt(sum(x*x for x in raw)/len(raw))
            filt_rms=math.sqrt(sum(x*x for x in expected)/len(expected))
            out_rms=math.sqrt(sum(x*x for x in observed)/len(observed))
            tone_metrics.append({"case":name,"stable_tone_frames":len(raw),
                "input_rms":raw_rms,"baseline_filtered_rms":filt_rms,"bypass_output_rms":out_rms,
                "baseline_attenuation_db":20*math.log10(max(filt_rms,1e-12)/max(raw_rms,1e-12)),
                "bypass_vs_input_max_abs_error":max(abs(a-b) for a,b in zip(observed,raw))})

    startup,_,_=load_case(run,"startup-edges",normal["startup-edges"])
    startup_zero=sum(startup.get((i,0))==0 and startup.get((i,1))==0 for i in (0,1))
    passed=sum(v=="passed" for v in case_status.values())
    failed=sum(v=="failed" for v in case_status.values())
    blocked=sum(v=="blocked" for v in case_status.values())
    build_path=run/"fpga-build"/"build-summary.json"
    build=json.loads(build_path.read_text(encoding="utf-8")) if build_path.exists() else None
    unit=run/"unit-tests.log"; unit_text=unit.read_text(encoding="utf-8",errors="replace") if unit.exists() else ""
    unit_summary=next((x.strip() for x in unit_text.splitlines() if "Ran " in x and " test" in x),None)
    reproducibility={"repeated_run":False}
    if args.repeat_run:
        repeat=args.repeat_run.resolve()
        second=json.loads((repeat/"fpga-build"/"build-summary.json").read_text(encoding="utf-8"))
        first_hash=build.get("bitstream_sha256") if build else None
        def input_hashes_by_case(root):
            return {d.name:sorted(json.loads((d/"inputs.json").read_text(encoding="utf-8")).get("sha256",{}).values())
                    for d in root.iterdir() if (d/"inputs.json").is_file()}
        input_contents_identical=input_hashes_by_case(run)==input_hashes_by_case(repeat)
        reproducibility={"repeated_run":True,"run1_bitstream_sha256":first_hash,
            "run2_bitstream_sha256":second["bitstream_sha256"],
            "bitstream_identical":first_hash==second["bitstream_sha256"],
            "input_contents_identical":input_contents_identical}
    metrics={
      "run_directory":str(run),"regression_report_passed":report["passed"],
      "regression_cases":{"passed":passed,"failed":failed,"blocked":blocked},
      "framework_unit_test_summary":unit_summary,
      "baseline_mismatch_count":baseline_mismatches,"normal_cases":normal_details,
      "negative_test_count":len(normal),"negative_test_pass_count":sum(
          x["status"]=="passed" and x["mismatch_count"]==0 for x in normal_details.values()),
      "right_echo_mismatch_count":echo_mismatches,"startup_zero_frames_verified":startup_zero,
      "activation_events_tested":len(events),"activation_events_succeeded":sum(x["success"] for x in events),
      "activation_success_rate":sum(x["success"] for x in events)/len(events) if events else None,
      "activation_events":events,"raw_pass_through_mismatch_count":pass_mismatches,
      "payload_frequency_metrics":tone_metrics,"fpga_build":build,
      "reproducibility":reproducibility,
      "hardware_validation":"not run; no Hackster board attached to this environment"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metrics,indent=2))
    if (not report["passed"] or baseline_mismatches or echo_mismatches or startup_zero!=2
        or pass_mismatches or metrics["negative_test_pass_count"]!=len(normal)
        or metrics["activation_events_succeeded"]!=len(events)
        or (args.repeat_run and (not reproducibility["bitstream_identical"] or not reproducibility["input_contents_identical"]))):
        raise SystemExit(1)

if __name__=="__main__": main()