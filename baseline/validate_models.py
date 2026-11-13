#!/usr/bin/env python3
"""Cross-check the Phase 3 independent reference model against the Phase 2
software model, and assert the exact-arithmetic invariants.

Two independently coded fixed-point implementations:
  * baseline/ref_fir.py        (Phase 3, this effort)
  * scripts/sw_fir.py          (Phase 2)

If they disagree on any sample for any stimulus, the shared arithmetic claim is
unproven. This script also checks:
  * sum(h) == 32768, exact Type-I symmetry, center tap 13920
  * the -1.0 (A=-32768) impulse identity: filtered impulse response == -h[n]
  * saturation reaches both int16 rails on the boundary family
  * round-half-toward-+inf behavior on crafted accumulator values

Reads vectors from build/vectors/*.csv (run gen_testvectors.py first), plus
large random streams generated here. Emits build/reports/model-crosscheck.json.
"""
from __future__ import annotations
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                              # ref_fir
sys.path.insert(0, os.path.join(ROOT, "scripts"))    # sw_fir

import ref_fir                                        # noqa: E402
import sw_fir                                         # noqa: E402

VECDIR = os.path.join(ROOT, "build", "vectors")
REPDIR = os.path.join(ROOT, "build", "reports")


def read_vector(path):
    out = []
    with open(path) as fh:
        r = csv.reader(fh)
        next(r)  # header
        for row in r:
            if not row:
                continue
            out.append(int(row[1]))
    return out


def compare(name, x, h, results):
    a = ref_fir.filtered(x, h)
    b = sw_fir.fir_filter(x, h)
    assert len(a) == len(b) == len(x)
    mism = [(i, a[i], b[i]) for i in range(len(x)) if a[i] != b[i]]
    maxerr = max((abs(a[i] - b[i]) for i in range(len(x))), default=0)
    results.append({"stimulus": name, "n": len(x),
                    "mismatches": len(mism), "max_abs_err": maxerr,
                    "out_min": min(a) if a else 0, "out_max": max(a) if a else 0,
                    "first_mismatches": mism[:5]})
    tag = "OK " if not mism else "FAIL"
    print("  [%s] %-16s n=%4d  mism=%d  max|err|=%d  out=[%d,%d]"
          % (tag, name, len(x), len(mism), maxerr,
             min(a) if a else 0, max(a) if a else 0))
    return len(mism) == 0


def main():
    os.makedirs(REPDIR, exist_ok=True)
    h = ref_fir.load_coeffs()
    N = len(h)
    report = {"coeffs": {}, "model_crosscheck": [], "invariants": {}, "pass": True}

    # --- coefficient invariants ---
    symmetric = all(h[i] == h[N - 1 - i] for i in range(N))
    report["coeffs"] = {"N": N, "sum": sum(h), "symmetric": symmetric,
                        "center_tap": h[N // 2], "max_abs": max(abs(v) for v in h)}
    print("coeffs: N=%d sum=%d symmetric=%s center=h[%d]=%d max|h|=%d"
          % (N, sum(h), symmetric, N // 2, h[N // 2], max(abs(v) for v in h)))
    ok_coeff = (N == 63 and sum(h) == 32768 and symmetric and h[N // 2] == 13920)
    report["invariants"]["coeff_facts"] = ok_coeff

    # --- model cross-check on all vector families ---
    print("\nmodel cross-check (ref_fir vs sw_fir):")
    all_ok = True
    if os.path.isdir(VECDIR):
        for fn in sorted(os.listdir(VECDIR)):
            if fn.endswith(".csv"):
                x = read_vector(os.path.join(VECDIR, fn))
                all_ok &= compare(fn[:-4], x, h, report["model_crosscheck"])
    # large random streams (independent of the HDL battery)
    for seed in (1, 2, 3):
        rng = random.Random(seed)
        x = [rng.randint(-32768, 32767) for _ in range(4000)]
        all_ok &= compare("rand_seed%d" % seed, x, h, report["model_crosscheck"])
    report["invariants"]["models_agree"] = all_ok

    # --- exact -1.0 impulse identity: filtered impulse == -h[n] ---
    imp = [-32768] + [0] * (N - 1)
    y = ref_fir.filtered(imp, h)
    ident = (y == [-v for v in h])
    print("\n-1.0 impulse identity  filtered == -h : %s" % ident)
    report["invariants"]["neg_one_impulse_equals_minus_h"] = ident

    # --- saturation reaches both rails (boundary family) ---
    bpath = os.path.join(VECDIR, "boundary.csv")
    sat_hi = sat_lo = False
    if os.path.isfile(bpath):
        yb = ref_fir.filtered(read_vector(bpath), h)
        sat_hi = (max(yb) == 32767)
        sat_lo = (min(yb) == -32768)
    print("saturation: hits +32767=%s  hits -32768=%s" % (sat_hi, sat_lo))
    report["invariants"]["saturates_both_rails"] = bool(sat_hi and sat_lo)

    # --- round-half-toward-+inf on crafted accumulator values ---
    # (acc + 2^14) >> 15 : exact-half cases round up (toward +inf)
    cases = {
        16384: 1,     # +0.5 LSB -> rounds to +1
        -16384: 0,    # -0.5 LSB -> rounds to 0 (toward +inf)
        16383: 0,     # just below +0.5 -> 0
        -16385: -1,   # just below -0.5 -> -1
        49152: 2,     # +1.5 -> 2
        -49152: -1,   # -1.5 -> -1 (toward +inf)
    }
    round_ok = all(ref_fir.round_shift15(a) == e for a, e in cases.items())
    print("round-half-toward-+inf on crafted values: %s" % round_ok)
    report["invariants"]["round_half_toward_plus_inf"] = round_ok

    report["pass"] = bool(ok_coeff and all_ok and ident and sat_hi and sat_lo and round_ok)
    with open(os.path.join(REPDIR, "model-crosscheck.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print("\nPASS=%s  -> build/reports/model-crosscheck.json" % report["pass"])
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
