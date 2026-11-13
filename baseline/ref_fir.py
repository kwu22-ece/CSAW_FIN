#!/usr/bin/env python3
"""Phase 3 golden reference model of the original FIR audio filter.

This is an INDEPENDENT re-implementation of the recovered fixed-point filter,
written from the documented arithmetic (Phase 2) rather than copied from the
Phase 2 model (`scripts/sw_fir.py`). The two are cross-checked bit-for-bit by
`baseline/validate_models.py`; agreement between two independently coded models
is part of the Phase 3 evidence.

Recovered arithmetic (iCE40-UP5K bitstream, verified by gate-level simulation):
  * 63-tap Type-I linear-phase (symmetric) low-pass FIR.
  * Coefficients h[k] are signed Q1.15 integers (recovered/coeffs.json);
    sum(h) = 32768 = exactly 1.0 (0 dB DC gain).
  * Per output sample, with x,h treated as plain integers (int16):
        acc   = sum_k  x[n-k] * h[k]           # exact integer accumulate
        y_int = (acc + 2**14) >> 15            # round half toward +inf (arith >>)
        y_int = clamp(y_int, -32768, 32767)    # saturate to int16
  * History before index 0 is zero (power-up state; iCE40 FFs/BRAM reset to 0).
  * The right output channel is an unmodified echo of the input sample.
  * End-to-end stream latency is 2 I2S frames (applied by the framing layer, not
    by this pure function). See `apply_framing()`.

Design notes for independence:
  - Uses an explicit integer rounding via floor-division identity rather than
    Python's `>>` on the raw accumulator, then asserts the two agree, so a sign
    or rounding-direction bug in either path is caught here.
  - `round_shift15()` implements "add half, arithmetic right shift by 15" for a
    signed integer, matching a hardware `(acc + 2^14) >>> 15`.
"""
from __future__ import annotations
import json
import os

Q15_ONE = 1 << 15          # 32768
Q15_HALF = 1 << 14         # 16384 (round-half bias)
INT16_MIN = -(1 << 15)     # -32768
INT16_MAX = (1 << 15) - 1  # 32767

_DEFAULT_COEFFS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "recovered", "coeffs.json",
)


def load_coeffs(path: str = _DEFAULT_COEFFS) -> list[int]:
    """Load the recovered Q1.15 integer taps."""
    with open(path) as fh:
        d = json.load(fh)
    h = [int(v) for v in d["coeffs_q15"]]
    return h


def round_shift15(acc: int) -> int:
    """Round half toward +infinity, then arithmetic shift right by 15.

    Hardware form: y = (acc + 2^14) >>> 15 on a signed accumulator.
    Implemented with floor division (which in Python rounds toward -inf for the
    shifted quantity exactly as an arithmetic right shift does) and verified
    against the raw-shift form.
    """
    biased = acc + Q15_HALF
    y_floordiv = biased // Q15_ONE          # floor division == arithmetic >>15
    y_shift = biased >> 15                   # Python >> on ints is arithmetic
    assert y_floordiv == y_shift, (acc, y_floordiv, y_shift)
    return y_floordiv


def sat16(v: int) -> int:
    """Saturate an integer to the signed 16-bit range."""
    if v > INT16_MAX:
        return INT16_MAX
    if v < INT16_MIN:
        return INT16_MIN
    return v


def filtered(x_int, h) -> list[int]:
    """Pure FIR: return y[n] for x[n] (same length, zero history before 0).

    y[n] is the filtered value logically corresponding to input x[n] (the
    filter's inherent (N-1)/2 = 31-sample group delay is intrinsic to h and is
    NOT removed here). No I2S frame latency is applied here.
    """
    x = [int(v) for v in x_int]
    n_in = len(x)
    N = len(h)
    y = [0] * n_in
    for n in range(n_in):
        acc = 0
        # accumulate h[k] * x[n-k]; terms with n-k < 0 are zero history
        kmax = N if n + 1 >= N else n + 1
        for k in range(kmax):
            acc += h[k] * x[n - k]
        y[n] = sat16(round_shift15(acc))
    return y


def echo(x_int) -> list[int]:
    """Right channel: unmodified echo of the input sample."""
    return [int(v) for v in x_int]


def apply_framing(y_filt, x_echo, latency: int = 2):
    """Map the pure filtered/echo streams to the physical I2S output frames.

    On the wire, the reply to input frame n appears in output frame n+latency:
    output frame m carries {left = y_filt[m-latency], right = x_echo[m-latency]},
    with zeros for m < latency. Returns (out_left, out_right), each a list the
    same length as the inputs (the first `latency` entries are the power-up
    zeros; the last `latency` logical samples spill past the captured window and
    are dropped, matching a fixed-length capture).
    """
    n = len(y_filt)
    assert len(x_echo) == n
    out_l = [0] * n
    out_r = [0] * n
    for m in range(n):
        src = m - latency
        if src >= 0:
            out_l[m] = y_filt[src]
            out_r[m] = x_echo[src]
    return out_l, out_r


def run(x_int, h=None, latency: int = 2):
    """Convenience: returns dict with pure and framed streams."""
    if h is None:
        h = load_coeffs()
    yf = filtered(x_int, h)
    xe = echo(x_int)
    ol, orr = apply_framing(yf, xe, latency)
    return {
        "filtered": yf, "echo": xe,
        "out_left": ol, "out_right": orr,
        "latency": latency, "N": len(h), "sum_h": sum(h),
    }


if __name__ == "__main__":
    import sys
    h = load_coeffs(sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_COEFFS)
    print("N=%d  sum(h)=%d (%.6f)  symmetric=%s  center=h[%d]=%d" % (
        len(h), sum(h), sum(h) / Q15_ONE,
        all(h[i] == h[len(h) - 1 - i] for i in range(len(h))),
        len(h) // 2, h[len(h) // 2]))
    if len(sys.argv) > 1:
        import wave
        from array import array
        w = wave.open(sys.argv[1], "rb")
        a = array("h")
        a.frombytes(w.readframes(w.getnframes()))
        if sys.byteorder == "big":
            a.byteswap()
        y = filtered(list(a), h)
        print("filtered %d samples; first 10 = %s" % (len(y), y[:10]))
