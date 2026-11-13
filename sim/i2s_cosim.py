#!/usr/bin/env python3
"""Phase 3 I2S co-simulation harness (independent decoder).

Drives a test-vector stimulus through a chosen HDL engine and decodes the I2S
output *independently* of the Phase 2 decoder, then compares the result to the
golden reference model (baseline/ref_fir.py).

Engines (both expose the raw netlist port names via the `chip` module):
  netlist : recovered/netlist/fir_audio_top_sim.v   (gate-level, from bitstream)
  recon   : recovered/rtl/fir_audio_top.v + scripts/recon_chip_wrap.v (clean RTL)

Both are driven by the proven Phase 2 I2S controller testbench
(scripts/tb_capture.v), which reproduces the RP2040 PIO waveform. The decoder
here re-derives I2S bit-order / latency / channel framing from the echo channel
(output-right == input delayed), rather than trusting Phase 2's constants, so a
pass is an independent confirmation.

Output per (engine, vector): decoded filtered[] and echo[] aligned to the input
sample index, plus a comparison dict against ref_fir.
"""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "baseline"))
import ref_fir  # noqa: E402

YOSYS = os.environ.get("YOSYSHQ_ROOT", "/c/Users/lowbr/oss-cad-suite").rstrip("/")
CELLS = os.path.join(YOSYS, "share", "yosys", "ice40", "cells_sim.v")
TB = os.path.join(ROOT, "scripts", "tb_capture.v")
NETLIST = os.path.join(ROOT, "recovered", "netlist", "fir_audio_top_sim.v")
RECON = os.path.join(ROOT, "recovered", "rtl", "fir_audio_top.v")
RECON_WRAP = os.path.join(ROOT, "scripts", "recon_chip_wrap.v")

SIMDIR = os.path.join(ROOT, "build", "sim")
FLUSH = 96      # zero lead-in frames: clears the <=64-deep delay line/pipeline
TAIL = 8        # trailing zero frames: flush out response past the 2-frame latency

ENGINES = {
    "netlist": [TB, NETLIST, CELLS],
    "recon": [TB, RECON, RECON_WRAP],
}


def _run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("cmd failed (%d): %s\n%s\n%s"
                           % (p.returncode, " ".join(cmd), p.stdout, p.stderr))
    return p


def compile_engine(engine):
    os.makedirs(SIMDIR, exist_ok=True)
    vvp = os.path.join(SIMDIR, engine + ".vvp")
    cmd = ["iverilog", "-g2012", "-s", "tb", "-o", vvp] + ENGINES[engine]
    _run(cmd)
    return vvp


def read_vector(path):
    out = []
    with open(path) as fh:
        r = csv.reader(fh)
        next(r)
        for row in r:
            if row:
                out.append(int(row[1]))
    return out


def write_stim(rundir, samples):
    """Frames = FLUSH zeros + samples + TAIL zeros, mirrored on L and R."""
    lw = [0] * FLUSH + [s & 0xFFFF for s in samples] + [0] * TAIL
    rw = list(lw)
    with open(os.path.join(rundir, "stim_l.hex"), "w") as fh:
        fh.write("\n".join("%04x" % x for x in lw) + "\n")
    with open(os.path.join(rundir, "stim_r.hex"), "w") as fh:
        fh.write("\n".join("%04x" % x for x in rw) + "\n")
    return len(lw)


def _s16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def decode_capture(path, sent_left, nframes):
    """Independently decode SD_OUT -> per-frame (left, right) words.

    Calibrates (msb_first, bit_offset, latency) by maximizing agreement of the
    output-right channel with the sent input delayed by `latency` (the echo
    oracle). Returns (out_left_by_frame, out_right_by_frame, calib).
    """
    sd_out = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            f, p, ws, sdin, sdout = line.split()
            sd_out[int(f) * 32 + int(p)] = int(sdout)

    def word(start, msb):
        v = 0
        for i in range(16):
            b = sd_out.get(start + i, 0)
            v |= (b << (15 - i)) if msb else (b << i)
        return v

    best = None
    for msb in (True, False):
        for boff in range(-2, 3):
            for lat in range(0, 7):
                match = total = 0
                for f in range(lat, nframes):
                    total += 1
                    out_r = _s16(word(f * 32 + 16 + boff, msb))
                    want = sent_left[f - lat] if f - lat < len(sent_left) else 0
                    if out_r == _s16(want):
                        match += 1
                score = match / total if total else 0.0
                if best is None or score > best[0]:
                    best = (score, msb, boff, lat, match, total)
    score, msb, boff, lat, match, total = best
    out_l = [_s16(word(f * 32 + 0 + boff, msb)) for f in range(nframes)]
    out_r = [_s16(word(f * 32 + 16 + boff, msb)) for f in range(nframes)]
    calib = {"msb_first": msb, "bit_offset": boff, "latency": lat,
             "echo_match": match, "echo_total": total, "echo_score": score}
    return out_l, out_r, calib


def cosim(engine, vec_name, samples, vvp):
    rundir = os.path.join(SIMDIR, engine, vec_name)
    os.makedirs(rundir, exist_ok=True)
    nframes = write_stim(rundir, samples)
    sent_left = [0] * FLUSH + [s & 0xFFFF for s in samples] + [0] * TAIL
    _run(["vvp", vvp, "+nframes=%d" % nframes], cwd=rundir)
    out_l, out_r, calib = decode_capture(os.path.join(rundir, "capture.txt"),
                                         sent_left, nframes)
    lat = calib["latency"]
    M = len(samples)
    # hardware filtered/echo aligned to input sample index n
    hw_filt = [out_l[FLUSH + n + lat] for n in range(M)]
    hw_echo = [out_r[FLUSH + n + lat] for n in range(M)]
    # golden model on the same (flushed) stream
    h = ref_fir.load_coeffs()
    x = [0] * FLUSH + samples
    y_full = ref_fir.filtered(x, h)
    sw_filt = y_full[FLUSH:FLUSH + M]
    sw_echo = samples[:]

    f_mis = [(n, hw_filt[n], sw_filt[n]) for n in range(M) if hw_filt[n] != sw_filt[n]]
    e_mis = [(n, hw_echo[n], sw_echo[n]) for n in range(M) if hw_echo[n] != sw_echo[n]]
    f_maxerr = max((abs(hw_filt[n] - sw_filt[n]) for n in range(M)), default=0)
    return {
        "engine": engine, "vector": vec_name, "samples": M,
        "calib": calib,
        "filtered_mismatches": len(f_mis), "filtered_max_abs_err": f_maxerr,
        "echo_mismatches": len(e_mis),
        "filtered_first_mismatches": f_mis[:5],
        "echo_first_mismatches": e_mis[:5],
        "hw_filtered": hw_filt, "hw_echo": hw_echo,
        "sw_filtered": sw_filt,
    }


if __name__ == "__main__":
    # CLI: python i2s_cosim.py <engine> <vector.csv>
    eng = sys.argv[1]
    vecpath = sys.argv[2]
    vvp = compile_engine(eng)
    s = read_vector(vecpath)
    r = cosim(eng, os.path.basename(vecpath)[:-4], s, vvp)
    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("hw_filtered", "hw_echo", "sw_filtered")},
                     indent=2))
