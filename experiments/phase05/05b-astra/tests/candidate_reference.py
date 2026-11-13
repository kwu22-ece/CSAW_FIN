#!/usr/bin/env python3
"""Phase 3 golden FIR plus the explicit candidate FSM reference."""
import csv, json, sys
from pathlib import Path
from reference import run_reference as baseline

MAGIC=(32512,-32511,23100,-23101,28050,-28051,-15556,15555)
BYPASS_FRAMES=128

def candidate_outputs(samples,coeffs):
    filtered=baseline.fir(samples,coeffs)
    active_after=[]; pos=0; active=False; remaining=0; hits=[]
    for i,x in enumerate(samples):
        if active:
            pos=0
            if remaining<=1: remaining=0; active=False
            else: remaining-=1
        elif x==MAGIC[pos]:
            if pos==len(MAGIC)-1:
                pos=0; remaining=BYPASS_FRAMES; active=True; hits.append(i)
            else: pos+=1
        elif x==MAGIC[0]: pos=1
        else: pos=0
        active_after.append(active)
    output=[]
    for frame in range(len(samples)):
        n=frame-2
        if 0<=n<len(samples):
            left=samples[n] if active_after[n] else filtered[n]
            right=samples[n]
        else: left=0; right=0
        output.append((left,right))
    return output,hits,active_after

def main():
    if len(sys.argv)!=3: raise SystemExit("usage: candidate_reference.py INPUT.csv OUTPUT.csv")
    in_path,out_path=map(Path,sys.argv[1:])
    samples=baseline.read_input(str(in_path))
    coeffs=baseline.load_coeffs(str(Path(__file__).resolve().parent/"reference"/"coeffs.json"))
    output,hits,active=candidate_outputs(samples,coeffs)
    with out_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["index","channel","value"])
        for i,(l,r) in enumerate(output): w.writerow([2*i,0,l]); w.writerow([2*i+1,1,r])
    sys.stderr.write(json.dumps({"frames":len(samples),"trigger_completions":hits,
        "trigger_events":len(hits),"active_frames":sum(active),
        "bypass_frames_per_trigger":128,"latency_frames":2})+"\n")

if __name__=="__main__": main()