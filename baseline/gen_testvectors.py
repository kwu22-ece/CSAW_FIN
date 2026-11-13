#!/usr/bin/env python3
"""Generate the Phase 3 input test-vector families as int16 stimulus.

Families (all mono int16, fed to the filter; the bridge mirrors L=R):
  impulse   - single-sample impulses at +/-full-scale and fractional amplitudes
  step      - step to +full, -full, and mid-scale (DC-gain / transient probe)
  sine      - pure tones across pass-, transition-, and stop-band
  chirp     - linear sweep 0 -> Nyquist (full magnitude response in one capture)
  random    - reproducible uniform int16 noise (fixed seed)
  boundary  - sustained rails and alternating extremes (saturation/rounding)

Each family is written as build/vectors/<name>.csv with header "index,value"
(zero-based contiguous index, signed decimal int16 sample). A manifest
build/vectors/manifest.json records lengths, fs, and per-vector parameters.

Lengths are kept modest so the full battery runs through gate-level simulation
in a reasonable time, while still covering every documented behavior.
"""
from __future__ import annotations
import csv
import json
import math
import os

FS = 16000.0                     # sample rate (Hz), from Phase 2 characterization
INT16_MIN, INT16_MAX = -32768, 32767

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "build", "vectors")


def clamp16(v: int) -> int:
    return max(INT16_MIN, min(INT16_MAX, int(v)))


def write_vector(name, samples, params):
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, name + ".csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "value"])
        for i, s in enumerate(samples):
            w.writerow([i, clamp16(s)])
    return {"name": name, "file": "build/vectors/%s.csv" % name,
            "length": len(samples), "fs_hz": FS, **params}


def gen_impulse():
    """Impulses at several Q1.15 amplitudes, each isolated by a long settle.

    -32768 (= -1.0 exactly) makes the output equal -h[n] with no rounding; the
    others confirm linearity and the rounding/saturation path.
    """
    amps = [-32768, 32767, 16384, -16384, 8192, -8192, 1, -1]
    settle = 96                 # > 63 taps, clears the delay line between pulses
    s = [0] * 8                 # lead-in
    marks = []
    for a in amps:
        marks.append(len(s))
        s.append(a)
        s += [0] * settle
    return s, {"amplitudes": amps, "impulse_indices": marks, "settle": settle}


def gen_step():
    out = []
    segs = []
    for level, hold in [(INT16_MAX, 96), (0, 32), (INT16_MIN, 96),
                        (0, 32), (16384, 96), (-16384, 96), (0, 32)]:
        segs.append({"start": len(out), "level": level, "hold": hold})
        out += [level] * hold
    return out, {"segments": segs}


def gen_sine():
    """One concatenated capture of pure tones across the band.

    Amplitude 30000 (near full-scale but below the rail) so pass-band tones do
    not clip but stop-band attenuation is clearly visible.
    """
    freqs = [250, 500, 1000, 2000, 3000, 3300, 3500, 4000, 5000, 6000, 7000]
    amp = 30000
    per = 160                   # samples per tone (10 ms)
    out = []
    segs = []
    for f in freqs:
        segs.append({"start": len(out), "freq_hz": f, "amp": amp, "len": per})
        for n in range(per):
            out.append(clamp16(round(amp * math.sin(2 * math.pi * f * n / FS))))
    return out, {"freqs_hz": freqs, "amp": amp, "samples_per_tone": per}


def gen_chirp():
    """Linear chirp 0 -> Nyquist over the capture (full response sweep)."""
    nlen = 1024
    f0, f1 = 0.0, FS / 2.0
    amp = 28000
    out = []
    phase = 0.0
    for n in range(nlen):
        f = f0 + (f1 - f0) * n / (nlen - 1)
        phase += 2 * math.pi * f / FS
        out.append(clamp16(round(amp * math.sin(phase))))
    return out, {"f0_hz": f0, "f1_hz": f1, "amp": amp, "length": nlen}


def gen_random():
    """Reproducible uniform int16 noise (Mersenne-Twister, fixed seed)."""
    import random
    rng = random.Random(0xC5A3)
    nlen = 512
    out = [rng.randint(INT16_MIN, INT16_MAX) for _ in range(nlen)]
    return out, {"seed": "0xC5A3", "dist": "uniform int16", "length": nlen}


def gen_boundary():
    """Saturation / rounding stressors: sustained rails and alternating extremes."""
    out = []
    segs = []

    def seg(label, data):
        segs.append({"label": label, "start": len(out), "len": len(data)})
        out.extend(data)

    seg("zeros", [0] * 8)
    seg("rail_pos_hold", [INT16_MAX] * 80)        # drive output toward +full DC
    seg("rail_neg_hold", [INT16_MIN] * 80)        # toward -full
    seg("alt_extreme", [INT16_MAX if i % 2 == 0 else INT16_MIN
                        for i in range(80)])       # Nyquist-rate full swing
    seg("pos_neg_block", [INT16_MAX] * 16 + [INT16_MIN] * 16)
    seg("tiny", [1, -1, 1, -1] * 8)               # rounding near zero
    seg("settle", [0] * 80)
    return out, {"segments": segs}


GENERATORS = {
    "impulse": gen_impulse,
    "step": gen_step,
    "sine": gen_sine,
    "chirp": gen_chirp,
    "random": gen_random,
    "boundary": gen_boundary,
}


def main():
    manifest = {"fs_hz": FS, "vectors": []}
    for name, gen in GENERATORS.items():
        samples, params = gen()
        entry = write_vector(name, samples, params)
        manifest["vectors"].append(entry)
        print("%-9s  %4d samples  -> %s" % (name, len(samples), entry["file"]))
    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("manifest: build/vectors/manifest.json  (%d families)"
          % len(manifest["vectors"]))


if __name__ == "__main__":
    main()
