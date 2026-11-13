#!/usr/bin/env python3
"""Harness-native GOLDEN reference command for candidate 05d.

Wraps the bit-exact recovered FIR arithmetic (identical to golden/sw_fir.py and
golden/ref_fir.py) and emits the Phase-4 reference CSV with SEQUENTIAL word
indices (0,1,2,...), as infrastructure/results.py:read_samples requires.

Rationale: the Phase-3 golden/run_reference.py emits FRAME indices (0,0,1,1,...)
in the index column (reconstruction-review finding R-001); infrastructure's
read_samples() rejects that (it needs index == row number). This wrapper fixes
ONLY the index column -- every sample VALUE is the unmodified golden arithmetic:

    acc   = sum_k  h[k] * x[n-k]          (int, zero history before 0)
    y_int = (acc + 2^14) >> 15            (round half toward +inf, arith shift)
    y_int = clamp(y_int, -32768, 32767)   (int16 saturate)
    out frame m: {left = y[m-LAT], right = x[m-LAT]}, zeros for m < LAT

Contract:  {python} ref_golden.py {input} {output} --coeffs PATH [--latency N]
Input  CSV: index,channel,value  (channel 0 = left = the sample to filter).
Output CSV: index,channel,value  (sequential index; channel 0=filtered,1=echo).
"""
from __future__ import annotations
import argparse, csv, json, os, sys

Q15_HALF = 1 << 14
INT16_MIN, INT16_MAX = -(1 << 15), (1 << 15) - 1


def load_coeffs(path):
    with open(path) as fh:
        return [int(v) for v in json.load(fh)["coeffs_q15"]]


def sat16(v):
    return INT16_MAX if v > INT16_MAX else INT16_MIN if v < INT16_MIN else v


def fir(x, h):
    N = len(h)
    y = [0] * len(x)
    for n in range(len(x)):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += h[k] * x[n - k]
        y[n] = sat16((acc + Q15_HALF) >> 15)
    return y


def read_left(path):
    """Return the left-channel (channel 0) sample stream in index order."""
    rows = []
    with open(path, newline="") as fh:
        for raw in csv.reader(fh):
            if not raw:
                continue
            c = [s.strip() for s in raw]
            if not c or not c[-1].lstrip("+-").isdigit():
                continue
            rows.append(c)
    by = {}
    for c in rows:
        if len(c) >= 3:
            idx, ch, val = int(c[0]), int(c[1]), int(c[2])
            if ch == 0:
                by[idx] = val
        elif len(c) == 2:
            by[int(c[0])] = int(c[1])
        else:
            by[len(by)] = int(c[0])
    return [by[i] for i in sorted(by)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--coeffs", default=os.path.join(here, "..", "golden", "coeffs.json"))
    ap.add_argument("--latency", type=int, default=2)
    args = ap.parse_args()

    h = load_coeffs(args.coeffs)
    x = read_left(args.input)
    y = fir(x, h)
    M = len(x)
    lat = args.latency

    with open(args.output, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "channel", "value"])
        wi = 0
        for m in range(M):
            s = m - lat
            left = y[s] if 0 <= s < M else 0
            right = x[s] if 0 <= s < M else 0
            w.writerow([wi, 0, left]); wi += 1
            w.writerow([wi, 1, right]); wi += 1

    sys.stderr.write("ref_golden: N=%d sum=%d  in=%d  lat=%d  wrote %d rows\n"
                     % (len(h), sum(h), M, lat, wi))


if __name__ == "__main__":
    main()
