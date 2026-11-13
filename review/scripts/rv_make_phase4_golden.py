#!/usr/bin/env python3
"""Subphase-R proposed correction for the Phase 3->Phase 4 handoff gap (O4).

Phase 4 infrastructure/results.py::read_samples() requires the reference CSV
header to be EXACTLY 'index,channel,value' (sequential zero-based index,
channel in {0,1} interleaved L/R, signed decimal value). The Phase 2 handoff
reference_vectors.csv uses 'n,x_in_int16,y_filtered_int16' and omits the echo
channel, so Phase 4's recovered-design path cannot consume it (returns BLOCKED).

This emits BOTH an input stream and a golden OUTPUT stream in Phase 4's schema:
  input :  frame n -> (idx 2n, ch0, x[n]) , (idx 2n+1, ch1, x[n])   # mono dup
  output:  frame n -> (idx 2n, ch0, filtered[n]) , (idx 2n+1, ch1, echo[n]=x[n])
with filtered[n] = sat16((sum_k x[n-k]*h[k] + 2^14) >> 15).

latency: the DUT emits frame n's reply in frame n+2 => latency_words = 2 frames * 2 = 4.

Usage: python rv_make_phase4_golden.py <wav> <nsamples> <coeffs.json> <outdir>
Then self-validates with Phase 4's own read_samples() (imported read-only).
"""
import csv, json, sys, wave, importlib.util, os
from array import array

wav, nss, cj, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
h = [int(x) for x in json.load(open(cj))["coeffs_q15"]]
N = len(h)
def sat16(v): return 32767 if v>32767 else (-32768 if v<-32768 else v)

w = wave.open(wav, "rb"); a = array("h"); a.frombytes(w.readframes(w.getnframes()))
if sys.byteorder == "big": a.byteswap()
ch = w.getnchannels(); x = list(a)[0::ch][:nss]

filt = []
for n in range(len(x)):
    acc = sum((x[n-k] if n-k >= 0 else 0)*h[k] for k in range(N))
    filt.append(sat16((acc + (1<<14)) >> 15))
echo = x[:]

os.makedirs(outdir, exist_ok=True)
def write_stream(path, left, right):
    with open(path, "w", newline="") as f:
        wr = csv.writer(f); wr.writerow(["index","channel","value"])
        for n in range(len(left)):
            wr.writerow([2*n, 0, left[n]]); wr.writerow([2*n+1, 1, right[n]])

inp = os.path.join(outdir, "input.csv")
gold = os.path.join(outdir, "golden_output.csv")
write_stream(inp, x, x)                 # mono duplicated to L/R (matches Phase4 from_wav)
write_stream(gold, filt, echo)          # left=filtered, right=echo
print(f"wrote {inp} and {gold}: {len(x)} audio frames -> {2*len(x)} interleaved words each")
print(f"latency_words to pass to Phase4 compare(): 4  (2-frame pipeline x 2 channels)")

# --- self-validate against Phase 4's OWN contract (read-only import) ---
p4 = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN/.worktrees/phase-04/infrastructure/results.py"
spec = importlib.util.spec_from_file_location("p4results", p4)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r_in = m.read_samples(inp); r_out = m.read_samples(gold)
print(f"Phase4 read_samples(input)  OK: {len(r_in)} words, header accepted")
print(f"Phase4 read_samples(golden) OK: {len(r_out)} words, header accepted")
# demonstrate a passing compare: golden vs itself at latency 0
res = m.compare(gold, gold, tolerance=0, latency_words=0, sample_bits=16)
print(f"Phase4 compare(golden,golden): passed={res['passed']} "
      f"samples={res['samples_compared']} max_abs_err={res['max_abs_error']}")
print("first 6 golden rows:", r_out[:6])
