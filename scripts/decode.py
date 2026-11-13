#!/usr/bin/env python3
"""Decode capture.txt from the netlist I2S sim, self-calibrate with the echo
channel, and extract the FIR impulse response (= coefficients)."""
import json, sys
from collections import defaultdict

cap = open("capture.txt").read().split("\n")
plan = json.load(open("stim_plan.json"))
nframes = plan["nframes"]

# bits[g] for g = frame*32 + slot
SDIN = {}; SDOUT = {}; WSv = {}
maxg = -1
for line in cap:
    line = line.strip()
    if not line: continue
    f, p, ws, sdin, sdout = line.split()
    g = int(f)*32 + int(p)
    SDIN[g] = int(sdin); SDOUT[g] = int(sdout); WSv[g] = int(ws)
    if g > maxg: maxg = g
NF = (maxg+1)//32

def word(bits, start, msb_first=True):
    v = 0
    for i in range(16):
        b = bits.get(start+i, 0)
        if msb_first: v |= b << (15-i)
        else:         v |= b << i
    return v

def s16(x):
    x &= 0xFFFF
    return x-0x10000 if x & 0x8000 else x

# --- sanity: decode SD_IN as sent (MSB-first, left=slots0..15) ---
def dec_in_left(f, msb_first=True, boff=0):
    return word(SDIN, f*32+0+boff, msb_first)
def dec_in_right(f, msb_first=True, boff=0):
    return word(SDIN, f*32+16+boff, msb_first)

# load stimulus to compare
stl = [int(x,16) for x in open("stim_l.hex").read().split()]
in_ok = sum(1 for f in range(min(NF,len(stl))) if dec_in_left(f)==stl[f])
print("INPUT decode (MSB-first, L=slots0..15): %d/%d frames match stimulus" %
      (in_ok, min(NF,len(stl))))

# --- calibrate OUTPUT via echo channel ---
# echo (output right channel) should equal input-left sent LAT frames earlier.
best = None
for msb in (True, False):
    for boff in range(-2, 3):
        for lat in range(0, 7):
            match = 0; total = 0
            for f in range(lat, NF):
                total += 1
                outR = s16(word(SDOUT, f*32+16+boff, msb))
                inL  = s16(stl[f-lat]) if f-lat < len(stl) else 0
                if outR == inL: match += 1
            score = match/total if total else 0
            if best is None or score > best[0]:
                best = (score, msb, boff, lat, match, total)
score, msb, boff, lat, match, total = best
print("ECHO calibration: best msb_first=%s boff=%d LAT=%d  echo match %d/%d (%.4f)"
      % (msb, boff, lat, match, total, score))

# --- extract impulse responses ---
def outL(f): return s16(word(SDOUT, f*32+0+boff, msb))
def outR(f): return s16(word(SDOUT, f*32+16+boff, msb))

print("\n=== Impulse responses per amplitude (output-left after LAT) ===")
all_h = {}
for seg in plan["segments"]:
    A = seg["amp"]; imp = seg["impulse_frame"]; tail = seg["tail"]
    # response appears starting at frame imp+LAT (output-left)
    h = [outL(imp+lat+k) for k in range(tail)]
    # also echo check right at impulse
    echo_imp = outR(imp+lat)
    # trim trailing zeros
    last = max([i for i,v in enumerate(h) if v!=0], default=-1)
    hh = h[:last+1]
    all_h[A] = hh
    print("A=%6d  echo@impulse=%6d (want %6d)  taps(nonzero span)=%d  first12=%s" %
          (A, echo_imp, s16(A), len(hh), hh[:12]))

# Coefficients from A=-32768 (== -1.0 exactly -> output = -h, exact):
if -32768 in all_h:
    h_exact = [-v for v in all_h[-32768]]
    N = len(h_exact)
    print("\n=== EXACT coefficients from A=-32768 (h[n] = -out) ===")
    print("N (nonzero span) =", N)
    print("h =", h_exact)
    # linear-phase symmetry check
    sym = all(h_exact[i]==h_exact[N-1-i] for i in range(N))
    asym = all(h_exact[i]==-h_exact[N-1-i] for i in range(N))
    print("symmetric (linear phase, even):", sym, " antisymmetric:", asym)
    print("sum(h) =", sum(h_exact), " = %.6f in Q1.15" % (sum(h_exact)/32768.0))
    print("max|h| =", max(abs(x) for x in h_exact))
    # save
    json.dump({"coeffs_q15": h_exact, "N": N, "symmetric": sym,
               "sum_q15": sum(h_exact), "LAT": lat, "msb_first": msb, "boff": boff},
              open("coeffs.json","w"), indent=1)
    print("saved coeffs.json")
