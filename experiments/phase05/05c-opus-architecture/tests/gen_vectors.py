#!/usr/bin/env python3
"""Generate directed input vectors for Phase 5C candidate C.

Produces, under tests/vectors/, input CSVs (index,channel,value; left=even,
right=odd). Expected CSVs are generated afterwards by invoking the reference
models (recovered_reference.py for near-miss, trojan_ref.py for active) so the
expected outputs come from an explicit model, not from the DUT.

ACTIVE cases arm the Trojan via the right-slot magic knock and then present a
stopband signal on the left channel; near-miss cases drive sequences that must
NOT arm, with real audio on the left to prove untriggered bit-identity.
"""
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
for _p in HERE.parents:
    if (_p / "infrastructure" / "results.py").exists():
        sys.path.insert(0, str(_p / "infrastructure"))
        break
from results import write_samples  # noqa: E402

VEC = HERE / "vectors"
VEC.mkdir(parents=True, exist_ok=True)

MAGIC0, MAGIC1, MAGIC2 = 0xC0DE, 0xFACE, 0xBEEF
AMP = 30000
FLUSH = 2  # trailing zero frames so the last filtered results are emitted


def stopband_sine(n, period=4):
    """A deep-stopband tone (period=4 samples => Fs/4, far above the ~3.3 kHz
    low-pass corner) that the baseline FIR strongly attenuates."""
    return [int(round(AMP * math.sin(2 * math.pi * i / period))) for i in range(n)]


def inband_sine(n, period=40):
    """An in-band tone the baseline passes (for near-miss left content)."""
    return [int(round(AMP * math.sin(2 * math.pi * i / period))) for i in range(n)]


def s16(v):
    """Signed 16-bit interpretation of a 16-bit code (CSV values must be signed
    decimals in [-32768,32767]; the serialized two's-complement bit pattern is
    identical, so a magic code like 0xC0DE is written as -16162)."""
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def frames_to_flat(frames):
    """frames: list of (left, right) -> flat [L0,R0,L1,R1,...] (signed int16)."""
    flat = []
    for l, r in frames:
        flat += [s16(l), s16(r)]
    return flat


def write_case(name, frames):
    flat = frames_to_flat(frames + [(0, 0)] * FLUSH)
    write_samples(VEC / f"{name}-input.csv", flat)
    print(f"  {name}: {len(frames)+FLUSH} frames")


def build():
    # ----- ACTIVE: arm then stopband tone -----------------------------------
    tone = stopband_sine(128)
    arm = [(0, MAGIC0), (0, MAGIC1), (0, MAGIC2)]           # arms at frame 2
    guard = [(0, 0)] * 5
    write_case("active-arm-tone", arm + guard + [(v, 0) for v in tone])

    # ----- ACTIVE: arm then single impulse (passthrough = single sample) ----
    imp = [(0, 0)] * 2 + [(AMP, 0)] + [(0, 0)] * 40
    write_case("active-arm-impulse", arm + guard + imp)

    # ----- ACTIVE: restart-credit overlap (C0DE,C0DE,FACE,BEEF arms) --------
    overlap = [(0, MAGIC0), (0, MAGIC0), (0, MAGIC1), (0, MAGIC2)]
    write_case("active-overlap-restart", overlap + guard + [(v, 0) for v in tone])

    # ----- NEAR-MISS: must NOT arm; left carries in-band audio --------------
    left = inband_sine(140)
    L = [(v, 0) for v in left]

    def nm(name, right_seq):
        frames = []
        for i, (l, _) in enumerate(L):
            r = right_seq[i] if i < len(right_seq) else 0
            frames.append((l, r))
        write_case(name, frames)

    nm("nm-2of3", [MAGIC0, MAGIC1, 0x0000])
    nm("nm-perturbed", [MAGIC0, MAGIC1, MAGIC2 ^ 0x0001])     # last off by 1 LSB
    nm("nm-interrupted", [MAGIC0, MAGIC1, 0x0000, MAGIC2])
    nm("nm-nonconsecutive", [MAGIC0, 0x0000, MAGIC1, 0x0000, MAGIC2])
    nm("nm-wrongorder", [MAGIC2, MAGIC1, MAGIC0])


if __name__ == "__main__":
    print("Generating directed vectors ->", VEC)
    build()
    print("done")
