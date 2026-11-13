#!/usr/bin/env python3
"""Independent frequency-response analysis of the recovered FIR.

Phase 2 characterized the filter with a hand-written DTFT loop. This script
cross-checks those numbers with scipy.signal (freqz, group_delay) as an
independent method, and emits landmark metrics + a response CSV.

Usage: python analyze_response.py [fs_hz]   (default fs = 16000)
Outputs: build/reports/freq-metrics.json, build/reports/freq-response.csv
"""
from __future__ import annotations
import csv
import json
import os
import sys

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ref_fir  # noqa: E402

REPDIR = os.path.join(ROOT, "build", "reports")


def main():
    fs = float(sys.argv[1]) if len(sys.argv) > 1 else 16000.0
    hq = ref_fir.load_coeffs()
    N = len(hq)
    h = np.asarray(hq, dtype=np.float64) / 32768.0     # Q1.15 -> float

    # H(e^jw) on a dense grid via scipy.freqz (independent of Phase 2's loop)
    nfft = 1 << 16
    w, H = signal.freqz(h, worN=nfft)
    f = w / np.pi * (fs / 2.0)
    mag = np.abs(H)
    magdb = 20.0 * np.log10(np.maximum(mag, 1e-15))

    def first_below(thresh_db):
        idx = np.where(magdb < thresh_db)[0]
        return float(f[idx[0]]) if len(idx) else None

    dc_db = 20.0 * np.log10(abs(np.sum(h)))
    edges = {("%+d_db" % t): first_below(t) for t in (-1, -3, -6)}

    e3 = first_below(-3)
    pb = mag[f <= e3] if e3 else mag[:1]
    ripple_db = {"max_db": float(20 * np.log10(pb.max())),
                 "min_db": float(20 * np.log10(pb.min()))}

    stopband = {}
    for fe in (3000, 4000, 5000, 6000):
        if fe < fs / 2:
            stopband["above_%d_hz_max_db" % fe] = float(magdb[f >= fe].max())

    # group delay (samples) and linear-phase residual
    wg, gd = signal.group_delay((h, 1), w=nfft)
    gd_pass = gd[f[:len(gd)] <= (e3 or fs / 4)]
    # Type-I symmetric FIR: factor out linear phase e^{-j w (N-1)/2}; residual
    # of H * e^{+j w (N-1)/2} should be ~ purely real.
    hlin = H * np.exp(1j * w * (N - 1) / 2.0)
    lin_resid = float(np.max(np.abs(hlin.imag)))

    metrics = {
        "fs_hz": fs, "N": N,
        "sum_h_q15": int(sum(hq)), "dc_gain_db": dc_db,
        "edges_hz": edges,
        "passband_ripple_to_-3dB": ripple_db,
        "stopband": stopband,
        "group_delay_samples_mean_passband": float(np.mean(gd_pass)),
        "group_delay_expected": (N - 1) / 2.0,
        "linear_phase_residual_imag": lin_resid,
        "method": "scipy.signal.freqz / group_delay, nfft=%d" % nfft,
    }

    os.makedirs(REPDIR, exist_ok=True)
    with open(os.path.join(REPDIR, "freq-metrics.json"), "w") as fh:
        json.dump(metrics, fh, indent=2)
    # coarse CSV for the report
    with open(os.path.join(REPDIR, "freq-response.csv"), "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["freq_hz", "mag", "mag_db"])
        step = max(1, len(f) // 2048)
        for i in range(0, len(f), step):
            wr.writerow(["%.2f" % f[i], "%.6f" % mag[i], "%.3f" % magdb[i]])

    print("fs=%g Hz  N=%d" % (fs, N))
    print("DC gain       : %.4f dB  (sum=%d)" % (dc_db, sum(hq)))
    for k, v in edges.items():
        print("  %-7s edge : %s Hz" % (k, ("%.1f" % v) if v else "n/a"))
    print("passband ripple to -3dB : +%.3f / %.3f dB"
          % (ripple_db["max_db"], ripple_db["min_db"]))
    for k, v in stopband.items():
        print("  %-24s : %.1f dB" % (k, v))
    print("group delay (passband)  : %.3f samples (expected %.3f)"
          % (metrics["group_delay_samples_mean_passband"], (N - 1) / 2.0))
    print("linear-phase residual   : %.2e (imag part after delinearization)"
          % lin_resid)
    print("-> build/reports/freq-metrics.json, freq-response.csv")


if __name__ == "__main__":
    main()
