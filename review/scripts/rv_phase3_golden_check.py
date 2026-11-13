#!/usr/bin/env python3
"""Subphase-R cross-check of the Phase 3 (challenge3/03-baseline @ 5dedf4c) golden
reference against this reviewer's independent model, and against Phase 4's reader.

Two separate questions:
  (A) Are Phase 3's golden VALUES correct?  (compare to an independent FIR model)
  (B) Does Phase 3's golden FORMAT satisfy Phase 4 results.read_samples()?

Extract the Phase 3 files first (read-only):
  git show origin/challenge3/03-baseline:handoffs/phase-03/reference_io.in.csv > p3_in.csv
  git show origin/challenge3/03-baseline:handoffs/phase-03/reference_io.csv    > p3_io.csv

Usage: python rv_phase3_golden_check.py p3_in.csv p3_io.csv recovered/coeffs.json \
         [path/to/phase-04/infrastructure/results.py]
"""
import csv, json, sys, importlib.util
inp, gold, cj = sys.argv[1], sys.argv[2], sys.argv[3]
p4 = sys.argv[4] if len(sys.argv) > 4 else None
h = [int(x) for x in json.load(open(cj))["coeffs_q15"]]; N = len(h)
def sat16(v): return 32767 if v > 32767 else (-32768 if v < -32768 else v)
def fir(x):
    o = []
    for n in range(len(x)):
        o.append(sat16((sum((x[n-k] if n-k >= 0 else 0)*h[k] for k in range(N)) + (1 << 14)) >> 15))
    return o

xi = [int(r["value"]) for r in csv.DictReader(open(inp))]
myf, mye = fir(xi), xi[:]
rows = list(csv.DictReader(open(gold)))
pf = [int(r["value"]) for r in rows if int(r["channel"]) == 0]
pe = [int(r["value"]) for r in rows if int(r["channel"]) == 1]

print("== (A) VALUE CHECK: Phase3 golden vs independent model (latency-shift sweep) ==")
best = None
for s in range(0, 6):
    mf = sum(1 for n in range(s, len(pf)) if n-s < len(myf) and pf[n] == myf[n-s]); tf = len(pf)-s
    me = sum(1 for n in range(s, len(pe)) if n-s < len(mye) and pe[n] == mye[n-s]); te = len(pe)-s
    print(f"  shift={s}: filtered {mf}/{tf}  echo {me}/{te}")
    sc = (mf/tf if tf else 0) + (me/te if te else 0)
    if best is None or sc > best[0]: best = (sc, s, mf, tf, me, te)
_, s, mf, tf, me, te = best
print(f"  => best shift={s}: filtered {mf}/{tf}, echo {me}/{te} "
      f"(values {'CORRECT' if mf==tf and me==te else 'DIVERGE'}; latency baked into the stream)")

print("\n== (B) FORMAT CHECK: Phase3 golden vs Phase4 results.read_samples() ==")
if p4:
    spec = importlib.util.spec_from_file_location("p4", p4); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    try:
        r = m.read_samples(gold); print(f"  ACCEPTED: {len(r)} rows")
    except Exception as e:
        print(f"  REJECTED: {type(e).__name__} - {e}")
        # show why: index column is frame-index, not sequential word index
        idx = [int(x["index"]) for x in rows[:6]]
        print(f"  first 6 index values: {idx}  (Phase4 requires 0,1,2,3,4,5 = per-row word index)")
else:
    print("  (pass Phase4 results.py path as arg 4 to run this check)")
