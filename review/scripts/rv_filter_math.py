#!/usr/bin/env python3
"""Subphase-R INDEPENDENT filter-math audit.

Re-derives every numerical claim in the Phase 2 report §4 from coeffs.json using
an independently written DTFT / integer analysis (does NOT import or reuse
scripts/analyze_filter.py). Also cross-checks that the reconstructed RTL's
hardcoded COEF[] table is identical to coeffs.json (catches transcription drift).

Usage: python rv_filter_math.py [coeffs.json] [rtl.v] [fs_hz]
Exit 0 iff all exact-integer invariants hold.
"""
import json, re, sys
import numpy as np

coeffs_path = sys.argv[1] if len(sys.argv) > 1 else "recovered/coeffs.json"
rtl_path    = sys.argv[2] if len(sys.argv) > 2 else "recovered/rtl/fir_audio_top.v"
FS          = float(sys.argv[3]) if len(sys.argv) > 3 else 16000.0

d  = json.load(open(coeffs_path))
hq = [int(x) for x in d["coeffs_q15"]]
N  = len(hq)
ok = True
def check(name, cond):
    global ok
    ok = ok and bool(cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

print("== EXACT INTEGER INVARIANTS ==")
check(f"N == 63 (got {N})", N == 63)
sym  = all(hq[i] == hq[N-1-i] for i in range(N))
asym = all(hq[i] == -hq[N-1-i] for i in range(N))
check(f"symmetric h[i]==h[N-1-i] (linear phase, Type-I)", sym)
print(f"       (antisymmetric? {asym})")
s   = sum(hq)
sa  = sum(abs(x) for x in hq)
check(f"sum(h) == 32768 exactly (got {s})", s == 32768)
check(f"center tap h[31] == 13920 (got {hq[31]})", hq[31] == 13920)
check(f"max|tap| == 13920 is the center (got max {max(abs(x) for x in hq)})",
      max(abs(x) for x in hq) == 13920 and hq.index(max(hq)) == 31)
check(f"reported sum_q15 field == computed sum", int(d.get("sum_q15", -1)) == s)
check(f"reported symmetric field == computed", bool(d.get("symmetric")) == sym)
check(f"N odd => single center tap (Type-I)", N % 2 == 1)
print(f"  sum|h|  = {sa}  (= {sa/32768.0:.6f} in Q1.15 -> peak time-domain gain)")

print("\n== RTL COEF[] vs coeffs.json (transcription cross-check) ==")
txt = open(rtl_path).read()
rtl_coef = {}
for m in re.finditer(r"COEF\[(\d+)\]\s*=\s*(-?\d+)\s*;", txt):
    rtl_coef[int(m.group(1))] = int(m.group(2))
have = len(rtl_coef) == N and all(i in rtl_coef for i in range(N))
check(f"RTL declares all {N} taps (got {len(rtl_coef)})", have)
if have:
    mism = [(i, rtl_coef[i], hq[i]) for i in range(N) if rtl_coef[i] != hq[i]]
    check(f"RTL COEF[] identical to coeffs.json (mismatches={len(mism)})", not mism)
    if mism:
        print("       first mismatches:", mism[:8])

print("\n== FREQUENCY RESPONSE (independent DTFT) ==")
h = np.array(hq, dtype=np.float64) / 32768.0
W = np.linspace(0, np.pi, 200001)              # very dense grid
n = np.arange(N)
H = (h[None, :] * np.exp(-1j * np.outer(W, n))).sum(axis=1)
mag = np.abs(H)
magdb = 20*np.log10(np.maximum(mag, 1e-300))
f = W/np.pi*(FS/2)

def edge(th):
    idx = np.where(magdb < th)[0]
    return f[idx[0]] if len(idx) else None

dc_db = 20*np.log10(abs(h.sum()))
print(f"  DC gain          : {h.sum():.8f} = {dc_db:+.4f} dB")
for t in (-1, -3, -6):
    e = edge(t); print(f"  {t:+d} dB edge       : {e:.1f} Hz" if e else f"  {t:+d} dB edge: n/a")
e3 = edge(-3)
if e3:
    pb = mag[f <= e3]
    print(f"  passband ripple  : +{20*np.log10(pb.max()):.4f} / {20*np.log10(pb.min()):.4f} dB (DC..-3dB)")
for fe in (3000, 4000, 5000, 6000):
    sb = magdb[f >= fe]
    print(f"  max gain >= {fe:4d} Hz: {sb.max():.2f} dB")
print(f"  peak |H| overall : {mag.max():.6f} ({20*np.log10(mag.max()):+.4f} dB) at {f[mag.argmax()]:.1f} Hz")

print("\n== LINEAR PHASE (remove linear term, residual imag should ~0) ==")
Hc = H * np.exp(1j*W*(N-1)/2.0)                # zero-phase after removing group delay
resid = np.abs(Hc.imag).max()
print(f"  group delay (symmetry) = (N-1)/2 = {(N-1)/2} samples = {(N-1)/2/FS*1000:.3f} ms")
check(f"linear phase: max|imag(H*e^jw(N-1)/2)| < 1e-9 (got {resid:.2e})", resid < 1e-9)

print("\n== ARITHMETIC HEADROOM / SATURATION REACHABILITY ==")
max_acc = sa * 32768                            # |x|<=32768, worst-case aligned signs
min_bits = max_acc.bit_length() + 1             # +1 sign bit
print(f"  max|acc| = sum|h|*32768 = {max_acc} (needs >= {min_bits} signed bits; RTL uses 40)")
# worst-case pre-round output magnitude in Q1.15 counts:
peak_out = max_acc / 32768.0
print(f"  worst-case |y_preround| = sum|h|*32768/32768 = {peak_out:.1f} counts")
print(f"  int16 range = [-32768, 32767]; saturation reachable? {peak_out > 32767}")
# worst-case input pattern that maximizes |acc|: x[n-k] = 32768*sign(h[k])... but
# input max magnitude is 32768 only for the value -32768 (0x8000); +full scale is 32767.
pos = sum(32767*x for x in hq if x > 0) + sum(-32768*x for x in hq if x < 0)  # maximize +acc
neg = sum(-32768*x for x in hq if x > 0) + sum(32767*x for x in hq if x < 0)  # maximize -acc
def rnd_sat(acc):
    y = (acc + (1<<14)) >> 15
    return 32767 if y > 32767 else (-32768 if y < -32768 else y)
print(f"  max +acc (x=+FS where h>0, -FS where h<0) = {pos} -> y={rnd_sat(pos)}")
print(f"  max -acc (x=-FS where h>0, +FS where h<0) = {neg} -> y={rnd_sat(neg)}")
print(f"  => alternating-sign full-scale DOES drive both rails: "
      f"+{rnd_sat(pos)==32767} / -{rnd_sat(neg)==-32768}")

print("\nRESULT:", "ALL EXACT INVARIANTS PASS" if ok else "SOME INVARIANT FAILED")
sys.exit(0 if ok else 1)
