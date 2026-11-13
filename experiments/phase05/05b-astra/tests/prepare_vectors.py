#!/usr/bin/env python3
"""Generate deterministic I2S stimuli and baseline expected outputs."""
import csv, hashlib, json, math, random, struct, sys, wave
from pathlib import Path

PACKAGE=Path(__file__).resolve().parents[1]
PROJECT=PACKAGE.parents[2]
TESTS=PACKAGE/"tests"
VECTORS=TESTS/"vectors"
sys.path.insert(0,str(TESTS))
from reference import run_reference as baseline

MAGIC=(32512,-32511,23100,-23101,28050,-28051,-15556,15555)
FS=16000
TONE_HZ=7000
TONE_AMPLITUDE=12000

def tone(count):
    return [int(round(TONE_AMPLITUDE*math.sin(2.0*math.pi*TONE_HZ*n/FS))) for n in range(count)]

def write_input(path,samples):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["index","channel","value"])
        for i,x in enumerate(samples):
            w.writerow([2*i,0,x]); w.writerow([2*i+1,1,x])

def write_expected(path,samples):
    h=baseline.load_coeffs(str(TESTS/"reference"/"coeffs.json"))
    y=baseline.fir(samples,h)
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["index","channel","value"])
        for m in range(len(samples)):
            n=m-2
            left=y[n] if 0<=n<len(samples) else 0
            right=samples[n] if 0<=n<len(samples) else 0
            w.writerow([2*m,0,left]); w.writerow([2*m+1,1,right])

def write_case(name,samples,expected=True):
    write_input(VECTORS/(name+".csv"),samples)
    if expected: write_expected(VECTORS/(name+".expected.csv"),samples)

def completions(samples):
    pos=0; hits=[]
    for i,x in enumerate(samples):
        if x==MAGIC[pos]:
            if pos==len(MAGIC)-1: hits.append(i); pos=0
            else: pos+=1
        elif x==MAGIC[0]: pos=1
        else: pos=0
    return hits

def read_noisy_audio(count):
    path=PROJECT/"what_a_piece_of_work-noisy.wav"
    with wave.open(str(path),"rb") as f:
        meta={"path":str(path.relative_to(PROJECT)).replace("\\","/"),
              "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
              "channels":f.getnchannels(),"sample_rate_hz":f.getframerate(),
              "sample_width_bytes":f.getsampwidth(),"frames_in_file":f.getnframes(),
              "frames_used":min(count,f.getnframes()),
              "selection":"first channel; no resampling or normalization"}
        if f.getsampwidth()!=2: raise SystemExit("Expected PCM16 noisy audio")
        raw=f.readframes(min(count,f.getnframes()))
    vals=struct.unpack("<"+"h"*(len(raw)//2),raw)
    return [vals[i*meta["channels"]] for i in range(len(vals)//meta["channels"])],meta

def normalize_golden_reference():
    source=VECTORS/"reference_io.csv"
    target=VECTORS/"reference_io.generic.csv"
    with source.open(newline="",encoding="utf-8-sig") as src, target.open("w",newline="",encoding="utf-8") as dst:
        reader=csv.DictReader(src)
        writer=csv.writer(dst)
        writer.writerow(["index","channel","value"])
        for row in reader:
            frame=int(row["index"]); channel=int(row["channel"])
            writer.writerow([2*frame+channel,channel,int(row["value"])])
def main():
    VECTORS.mkdir(parents=True,exist_ok=True)
    canonical=baseline.read_input(str(VECTORS/"reference_io.in.csv"))
    write_input(VECTORS/"canonical_golden.csv",canonical)
    normalize_golden_reference()
    audio,meta=read_noisy_audio(1024)
    write_case("noisy_audio_1024",audio)
    (PACKAGE/"reports"/"audio-source.json").write_text(json.dumps(meta,indent=2)+"\n",encoding="utf-8")
    boundary=[32767,-32768,0,1,-1,16384,-16384,32766,-32767,8192,-8192,255,-255,12345,-23456,42]*32
    write_case("boundary_stress",boundary)
    rng=random.Random(20261112); rand=[rng.randint(-32768,32767) for _ in range(8192)]
    if completions(rand): raise SystemExit("Seeded random input unexpectedly contains trigger")
    write_case("random_negative",rand)
    write_case("startup_edges",[0]*8+boundary[:128])
    near=list(MAGIC); near[4]^=1
    near=[0]*12+near+tone(320)+[0]*160
    if completions(near): raise SystemExit("Near miss unexpectedly contains trigger")
    write_case("near_miss_negative",near)
    split=[0]*12+list(MAGIC[:4])+[0]*4+list(MAGIC[4:])+tone(320)+[0]*160
    if completions(split): raise SystemExit("Split sequence unexpectedly contains trigger")
    write_case("split_sequence_negative",split)
    activate=[0]*12+list(MAGIC)+tone(320)+[0]*160
    if len(completions(activate))!=1: raise SystemExit("Activation vector must contain one trigger")
    write_case("trigger_1mhz",activate,False); write_case("trigger_625khz",activate,False)
    repeated=[0]*12+list(MAGIC)+[0]*150+list(MAGIC)+tone(320)+[0]*160
    if len(completions(repeated))!=2: raise SystemExit("Repeated vector must contain two triggers")
    write_case("retrigger_1mhz",repeated,False)
    print("Generated 10 cases; expected activation events: 1 + 1 + 2; random seed: 20261112")
    print(f"Noisy WAV: {meta['channels']}ch/{meta['sample_rate_hz']}Hz PCM16; used {len(audio)} frames")

if __name__=="__main__": main()