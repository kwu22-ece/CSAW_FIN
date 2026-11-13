#!/usr/bin/env python3
"""Subphase-R INDEPENDENT adversarial arithmetic experiment.

Targets two under-tested corners of the Phase 2 reconstruction:
  (1) ACCUMULATOR-WIDTH / SATURATION: does the ORIGINAL (netlist) saturate to the
      int16 rails exactly as an infinite-precision-then-saturate model predicts?
      (The sw model uses Python bignum; if the original's accumulator were too
      narrow it would wrap, not saturate, and diverge on worst-case input.)
  (2) ROUNDING MODE: is the rule really round-half-toward-+inf, or is that
      underdetermined? Compare the netlist against 5 candidate rules.

Independent of scripts/: own stimulus generator, own decoder (echo-calibrated),
own arithmetic models. Uses the netlist as ground truth.

Modes:
  gen   <coeffs.json>            -> writes stim_l.hex stim_r.hex rv_stim.json
  check <coeffs.json>            -> reads capture.txt, compares netlist vs models
"""
import json, sys, math

def load_h(p): return [int(x) for x in json.load(open(p))["coeffs_q15"]]

def build_stim(h):
    N = len(h); FS_POS = 32767; FS_NEG = -32768
    L = []                                 # left input samples (what gets filtered)
    marks = {}
    def emit(seq): L.extend(seq)
    emit([0]*64)                           # lead-in
    emit([0]*160)                          # flush delay line (<=64) + margin
    # (1a) worst-case +acc window: x_time[j] = +FS where h[j]>0 else -FS
    marks["worst_pos_meas"] = len(L) + (N-1)
    emit([FS_POS if h[j] > 0 else FS_NEG for j in range(N)])
    emit([0]*96)
    # (1b) worst-case -acc window
    marks["worst_neg_meas"] = len(L) + (N-1)
    emit([FS_NEG if h[j] > 0 else FS_POS for j in range(N)])
    emit([0]*96)
    # (1c) near-rail: 90% of worst-case (+), should NOT prematurely saturate
    marks["near_pos_meas"] = len(L) + (N-1)
    emit([int(0.90*FS_POS) if h[j] > 0 else int(0.90*FS_NEG) for j in range(N)])
    emit([0]*96)
    # (2) tie probes: single impulses at +/-16384 (h*0.5 ties when h odd)
    for A in (16384, -16384, 8192, -8192, 24576, -24576):
        emit([A]); emit([0]*96)
    # (2/general) pseudo-random full-scale run (deterministic LCG; heavy rounding)
    seed = 0x12345678
    rnd = []
    for _ in range(400):
        seed = (1103515245*seed + 12345) & 0x7fffffff
        rnd.append((seed % 65536) - 32768)
    marks["rand_start"] = len(L)
    emit(rnd)
    emit([0]*96)
    return L, marks, N

def s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x

def sat16(v):
    return 32767 if v > 32767 else (-32768 if v < -32768 else v)

# candidate pre-saturation rounding rules on integer acc (scale 2^15)
def r_halfup(acc):   return (acc + (1 << 14)) >> 15                 # ties -> +inf (floor+bias)
def r_floor(acc):    return acc >> 15                               # truncate toward -inf
def r_trunc(acc):    return int(acc / 32768)                        # truncate toward 0
def r_half_even(acc):
    q, rem = divmod(acc, 32768)
    if rem*2 < 32768: return q
    if rem*2 > 32768: return q+1
    return q if q % 2 == 0 else q+1                                 # ties -> even
def r_half_away(acc):
    f = acc / 32768.0
    return math.floor(f+0.5) if f >= 0 else math.ceil(f-0.5)        # ties -> away from 0
RULES = {"half_up(+inf)": r_halfup, "floor(-inf)": r_floor,
         "trunc(->0)": r_trunc, "half_even": r_half_even, "half_away": r_half_away}

def model(L, h, rule):
    N = len(h); out = []
    for n in range(len(L)):
        acc = sum((L[n-k] if n-k >= 0 else 0)*h[k] for k in range(N))
        out.append(sat16(rule(acc)))
    return out

if __name__ == "__main__":
    mode = sys.argv[1]; h = load_h(sys.argv[2] if len(sys.argv) > 2 else "recovered/coeffs.json")
    if mode == "gen":
        L, marks, N = build_stim(h)
        R = L[:]                                   # mirror bridge (right unused by DUT)
        with open("stim_l.hex","w") as f: f.write("\n".join("%04x"%(x&0xFFFF) for x in L)+"\n")
        with open("stim_r.hex","w") as f: f.write("\n".join("%04x"%(x&0xFFFF) for x in R)+"\n")
        json.dump({"nframes":len(L),"marks":marks,"N":N}, open("rv_stim.json","w"), indent=1)
        print("gen: nframes=%d marks=%s" % (len(L), marks))
    elif mode == "check":
        plan = json.load(open("rv_stim.json")); N = plan["N"]; marks = plan["marks"]
        L = [s16(int(x,16)) for x in open("stim_l.hex").read().split()]
        cap = [ln.split() for ln in open("capture.txt").read().split("\n") if ln.strip()]
        SDOUT = {}; nf = 0
        for f,p,ws,sdin,sdout in cap:
            g = int(f)*32 + int(p); SDOUT[g] = int(sdout); nf = max(nf, int(f)+1)
        def word(d, start, msb=True):
            return sum((d.get(start+i,0) << (15-i if msb else i)) for i in range(16))
        def outL(f): return s16(word(SDOUT, f*32+0))
        def outR(f): return s16(word(SDOUT, f*32+16))
        # calibrate LAT via echo (outR[f] == L[f-lat])
        best=None
        for lat in range(0,7):
            m=sum(1 for f in range(lat,min(nf,len(L))) if outR(f)==(L[f-lat] if f-lat>=0 else 0))
            t=min(nf,len(L))-lat
            if best is None or m/t>best[0]: best=(m/t,lat,m,t)
        _,lat,em,et = best
        print("echo calibration: LAT=%d echo match %d/%d" % (lat, em, et))
        # netlist output aligned to input frame n: outL(n+lat)
        nl = [outL(n+lat) for n in range(len(L)) if n+lat < nf]
        Lc = L[:len(nl)]
        # compare each rounding rule
        print("\n== ROUNDING-RULE DISCRIMINATION (netlist vs models, %d frames) ==" % len(nl))
        results={}
        for name,rule in RULES.items():
            mdl = model(Lc, h, rule)
            mism = [(n,nl[n],mdl[n]) for n in range(len(nl)) if nl[n]!=mdl[n]]
            results[name]=len(mism)
            tag = "  <== MATCHES NETLIST" if not mism else ""
            print("  %-15s mismatches=%5d%s" % (name, len(mism), tag))
            if 0 < len(mism) <= 3: print("      e.g.", mism[:3])
        # saturation checks at worst-case frames
        print("\n== SATURATION / ACCUMULATOR-WIDTH (netlist ground truth) ==")
        hm = model(Lc, h, r_halfup)
        for key in ("worst_pos_meas","worst_neg_meas","near_pos_meas"):
            n = marks[key]
            if n < len(nl):
                acc = sum((Lc[n-k] if n-k>=0 else 0)*h[k] for k in range(N))
                print("  %-15s frame=%d acc=%d netlist=%d model=%d %s"
                      % (key, n, acc, nl[n], hm[n], "OK" if nl[n]==hm[n] else "**DIVERGE**"))
        rails = sum(1 for v in nl if v in (32767,-32768))
        print("  frames hitting a rail: %d (saturation exercised: %s)" % (rails, rails>0))
        winner = [k for k,v in results.items() if v==0]
        print("\nRESULT: rules matching netlist exactly:", winner,
              "| unique round-half-+inf:", winner==["half_up(+inf)"])
