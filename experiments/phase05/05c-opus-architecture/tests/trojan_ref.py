#!/usr/bin/env python3
"""Trojan-aware reference model for the Phase 5C candidate C active tests.

Reuses the AUTHORITATIVE baseline FIR arithmetic (sw_fir.fir_filter) unchanged;
adds ONLY the independently-specified trigger + payload behaviour:

  TRIGGER  : an ordered 3-frame magic knock on the RIGHT I2S slot
             (MAGIC0=0xC0DE, 0xFACE, 0xBEEF). The baseline ignores the right
             input entirely; the Trojan captures it per frame. seq_idx advances
             on an exact match, resets on mismatch (restart credit on MAGIC0).
             `armed` latches at the 3rd consecutive match (sticky).
  PAYLOAD  : once armed, the left ("filtered") output slot carries the raw input
             sample (filter bypass) instead of the FIR result.

Output convention is identical to recovered_reference.py: alternating stereo
frames, LATENCY=2, left=filtered-or-passthrough, right=echo(raw left input).

Interfaces match recovered_reference.py so this can drive the harness directly:
  --model <sw_fir.py> --coefficients <coeffs.json> --input <csv> --output <csv>
             [--latency-frames 2]
"""
import argparse, importlib.util
from pathlib import Path
import sys
for _p in Path(__file__).resolve().parents:
    if (_p / "infrastructure" / "results.py").exists():
        sys.path.insert(0, str(_p / "infrastructure"))
        break
from results import read_samples, write_samples  # harness CSV helpers

MAGIC = (0xC0DE, 0xFACE, 0xBEEF)


def to_s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def arm_index(right_samples):
    """Return the left-sample/frame index at which `armed` becomes effective
    (the frame of the 3rd consecutive magic match), or None if never armed.
    Mirrors the RTL detector semantics exactly (restart credit on MAGIC0)."""
    idx = 0
    for f, rv in enumerate(right_samples):
        rv16 = rv & 0xFFFF
        if idx == 0:
            idx = 1 if rv16 == MAGIC[0] else 0
        elif idx == 1:
            idx = 2 if rv16 == MAGIC[1] else (1 if rv16 == MAGIC[0] else 0)
        elif idx == 2:
            if rv16 == MAGIC[2]:
                return f            # armed effective at this frame's load
            idx = 1 if rv16 == MAGIC[0] else 0
    return None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--coefficients', type=Path, required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--latency-frames', type=int, default=2)
    args = p.parse_args()

    rows = read_samples(args.input)
    if len(rows) % 2 or any(r['channel'] != i % 2 for i, r in enumerate(rows)):
        raise ValueError('Expected complete alternating stereo frames')
    left = [r['value'] for r in rows[0::2]]
    right = [r['value'] for r in rows[1::2]]
    if not 0 <= args.latency_frames < len(left):
        raise ValueError('Invalid latency')

    spec = importlib.util.spec_from_file_location('supplied_phase2_model', args.model)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    filtered = model.fir_filter(left, model.load_coeffs(str(args.coefficients)))
    if len(filtered) != len(left):
        raise ValueError('Supplied model output length differs')

    a = arm_index(right)   # None => never armed => pure baseline
    out = []
    for frame in range(len(left)):
        n = frame - args.latency_frames
        if n < 0:
            out.extend([0, 0])
        else:
            armed = a is not None and n >= a
            left_out = left[n] if armed else filtered[n]
            out.extend([left_out, left[n]])   # right = echo of raw input
    write_samples(args.output, out)


if __name__ == '__main__':
    main()
