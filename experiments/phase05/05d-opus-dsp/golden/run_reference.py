#!/usr/bin/env python3
"""Phase 3 golden reference model - Phase 4 entry point.

Satisfies the Codex `reference_command` argv contract:

    {python} handoffs/phase-03/run_reference.py {input} {output} [options]

Reads a stimulus file and writes the EXACT expected I2S output words in the
Phase 4 reference CSV format:  index,channel,value
  * index   : contiguous zero-based output frame (word) index
  * channel : 0 = left = filtered, 1 = right = echo
  * value   : signed decimal int16 sample

Self-contained (no project imports). The recovered Q1.15 arithmetic is embedded
and matched bit-for-bit to the gate-level netlist in Phase 2/3.

Input formats accepted (header optional, auto-detected):
  * "index,value"            - one mono int16 sample per input frame
  * "index,channel,value"    - channel 0 (left) is the sample to filter
                               (the bridge mirrors L=R on input; channel 1 is
                               ignored for filtering and regenerated as echo)

Framing (verified): end-to-end latency is 2 frames. Output frame m carries
left=filtered(x[m-2]) and right=echo(x[m-2]); frames m<2 are power-up zeros.
Use --latency N to change it, or --aligned to emit logical y[n]/x[n] with no
frame shift (y[n] and x[n] at output index n).
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys

Q15_HALF = 1 << 14
INT16_MIN, INT16_MAX = -(1 << 15), (1 << 15) - 1


def find_coeffs(explicit=None):
    if explicit:
        return explicit
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [
        os.path.join(here, "coeffs.json"),
        os.path.join(here, "..", "..", "recovered", "coeffs.json"),
        os.path.join(os.getcwd(), "recovered", "coeffs.json"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    raise SystemExit("coeffs.json not found; pass --coeffs PATH")


def load_coeffs(path):
    with open(path) as fh:
        return [int(v) for v in json.load(fh)["coeffs_q15"]]


def sat16(v):
    return INT16_MAX if v > INT16_MAX else INT16_MIN if v < INT16_MIN else v


def fir(x, h):
    """y[n] = sat16( (sum_k h[k]*x[n-k] + 2^14) >> 15 ), zero history."""
    N = len(h)
    y = [0] * len(x)
    for n in range(len(x)):
        acc = 0
        kmax = n + 1 if n + 1 < N else N
        for k in range(kmax):
            acc += h[k] * x[n - k]
        y[n] = sat16((acc + Q15_HALF) >> 15)
    return y


def read_input(path):
    """Return the mono input sample stream (left channel)."""
    rows = []
    with open(path, newline="") as fh:
        for raw in csv.reader(fh):
            if not raw:
                continue
            cells = [c.strip() for c in raw]
            # skip a header row
            if not cells[-1].lstrip("+-").isdigit():
                continue
            rows.append(cells)
    if not rows:
        return []
    ncol = len(rows[0])
    if ncol >= 3:
        # index,channel,value : take channel 0 (left) in index order
        by_idx = {}
        for c in rows:
            idx, ch, val = int(c[0]), int(c[1]), int(c[2])
            if ch == 0:
                by_idx[idx] = val
        return [by_idx[i] for i in sorted(by_idx)]
    if ncol == 2:
        return [int(c[1]) for c in rows]       # index,value
    return [int(c[0]) for c in rows]           # value only


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--coeffs", default=None)
    ap.add_argument("--latency", type=int, default=2)
    ap.add_argument("--aligned", action="store_true",
                    help="emit logical y[n]/x[n] with no 2-frame shift")
    args = ap.parse_args()

    h = load_coeffs(find_coeffs(args.coeffs))
    x = read_input(args.input)
    y = fir(x, h)
    M = len(x)
    lat = 0 if args.aligned else args.latency

    out_left = [0] * M
    out_right = [0] * M
    for m in range(M):
        s = m - lat
        if 0 <= s < M:
            out_left[m] = y[s]
            out_right[m] = x[s]

    with open(args.output, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "channel", "value"])
        for m in range(M):
            w.writerow([m, 0, out_left[m]])
            w.writerow([m, 1, out_right[m]])

    sys.stderr.write(
        "run_reference: N=%d sum=%d  in=%d frames  latency=%d  wrote %d rows -> %s\n"
        % (len(h), sum(h), M, lat, 2 * M, args.output))


if __name__ == "__main__":
    main()
