#!/usr/bin/env python3
"""Real-audio baseline: stream the challenge WAV through both HDL engines, prove
bit-exactness against the golden model, and emit the canonical Phase 4 reference
dataset (index,channel,value) plus its mono input.

Usage: python sim/run_wav.py <wav> <M> [offset]
Outputs:
  handoffs/phase-03/reference_io.in.csv   (index,value)         mono input
  handoffs/phase-03/reference_io.csv      (index,channel,value) framed golden out
  build/reports/wav-cosim.json            per-engine bit-exact comparison
"""
from __future__ import annotations
import csv
import json
import os
import sys
import wave
from array import array

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "baseline"))
import i2s_cosim as cs       # noqa: E402
import ref_fir               # noqa: E402

HANDOFF = os.path.join(ROOT, "handoffs", "phase-03")
REPDIR = os.path.join(ROOT, "build", "reports")


def load_wav(path, M, offset=0):
    w = wave.open(path, "rb")
    assert w.getnchannels() == 1 and w.getsampwidth() == 2, "need 16-bit mono"
    a = array("h")
    a.frombytes(w.readframes(w.getnframes()))
    if sys.byteorder == "big":
        a.byteswap()
    return list(a)[offset:offset + M]


def main():
    wav = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "what_a_piece_of_work-noisy.wav")
    M = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    offset = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    samples = load_wav(wav, M, offset)

    vvp = {e: cs.compile_engine(e) for e in ("netlist", "recon")}
    rn = cs.cosim("netlist", "wav", samples, vvp["netlist"])
    rr = cs.cosim("recon", "wav", samples, vvp["recon"])

    h = ref_fir.load_coeffs()
    res = ref_fir.run(samples, h, latency=2)
    y = res["filtered"]
    ol, orr = res["out_left"], res["out_right"]

    # confirm both engines reproduce the golden filtered + echo bit-for-bit
    net_ok = (rn["filtered_mismatches"] == 0 and rn["echo_mismatches"] == 0)
    rec_ok = (rr["filtered_mismatches"] == 0 and rr["echo_mismatches"] == 0)
    hw_eq = all(a == b for a, b in zip(rn["hw_filtered"], rr["hw_filtered"]))

    os.makedirs(HANDOFF, exist_ok=True)
    with open(os.path.join(HANDOFF, "reference_io.in.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "value"])
        for i, s in enumerate(samples):
            w.writerow([i, s])
    with open(os.path.join(HANDOFF, "reference_io.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "channel", "value"])
        for m in range(M):
            w.writerow([m, 0, ol[m]])
            w.writerow([m, 1, orr[m]])

    report = {
        "wav": os.path.basename(wav), "M": M, "offset": offset,
        "fs_hz": 16000,
        "netlist": {"filtered_mismatches": rn["filtered_mismatches"],
                    "echo_mismatches": rn["echo_mismatches"],
                    "filtered_max_abs_err": rn["filtered_max_abs_err"],
                    "latency": rn["calib"]["latency"],
                    "echo_score": rn["calib"]["echo_score"]},
        "recon": {"filtered_mismatches": rr["filtered_mismatches"],
                  "echo_mismatches": rr["echo_mismatches"],
                  "filtered_max_abs_err": rr["filtered_max_abs_err"],
                  "latency": rr["calib"]["latency"],
                  "echo_score": rr["calib"]["echo_score"]},
        "netlist_eq_recon": hw_eq,
        "input_range": [min(samples), max(samples)],
        "filtered_range": [min(y), max(y)],
        "bit_exact": bool(net_ok and rec_ok and hw_eq),
        "reference_csv": "handoffs/phase-03/reference_io.csv",
        "reference_in_csv": "handoffs/phase-03/reference_io.in.csv",
        "framing": "output frame m: left=filtered(x[m-2]), right=echo(x[m-2]); m<2 = 0",
    }
    os.makedirs(REPDIR, exist_ok=True)
    with open(os.path.join(REPDIR, "wav-cosim.json"), "w") as fh:
        json.dump(report, fh, indent=2)

    print("wav=%s M=%d offset=%d" % (report["wav"], M, offset))
    print("netlist: filt_mis=%d echo_mis=%d lat=%d echo=%.3f"
          % (rn["filtered_mismatches"], rn["echo_mismatches"],
             rn["calib"]["latency"], rn["calib"]["echo_score"]))
    print("recon  : filt_mis=%d echo_mis=%d lat=%d echo=%.3f"
          % (rr["filtered_mismatches"], rr["echo_mismatches"],
             rr["calib"]["latency"], rr["calib"]["echo_score"]))
    print("netlist==recon: %s   BIT-EXACT: %s" % (hw_eq, report["bit_exact"]))
    print("wrote reference_io.csv (%d rows) + reference_io.in.csv (%d rows)"
          % (2 * M, M))
    return 0 if report["bit_exact"] else 1


if __name__ == "__main__":
    sys.exit(main())
