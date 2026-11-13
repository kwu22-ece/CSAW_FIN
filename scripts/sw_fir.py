#!/usr/bin/env python3
"""Software reference model of the recovered FIR, bit-exact to the hardware.

Arithmetic (recovered & confirmed against the netlist):
  acc   = sum_k  x_int[n-k] * h_int[k]      # int, x/h are int16 (Q1.15)
  y_int = (acc + 2**14) >> 15               # round half toward +inf, arithmetic shift
  y_int = sat16(y_int)                      # saturate to [-32768, 32767]
"""
import json

def load_coeffs(path="recovered/coeffs.json"):
    return json.load(open(path))["coeffs_q15"]

def sat16(v):
    if v > 32767:  return 32767
    if v < -32768: return -32768
    return v

def fir_filter(x_int, h):
    """x_int: list of int16 input samples (no leading flush needed; history is
    zero before index 0). Returns list of int16 outputs, same length, aligned so
    y[n] corresponds to x[n] (the filter's internal group delay is inherent)."""
    N = len(h)
    y = []
    for n in range(len(x_int)):
        acc = 0
        for k in range(N):
            idx = n - k
            xk = x_int[idx] if idx >= 0 else 0
            acc += xk * h[k]
        y.append(sat16((acc + (1 << 14)) >> 15))
    return y

if __name__ == "__main__":
    import sys, wave
    from array import array
    h = load_coeffs(sys.argv[2] if len(sys.argv) > 2 else "recovered/coeffs.json")
    w = wave.open(sys.argv[1], "rb")
    a = array("h"); a.frombytes(w.readframes(w.getnframes()))
    import sys as _s
    if _s.byteorder == "big": a.byteswap()
    y = fir_filter(list(a), h)
    print("filtered %d samples; first 10 out = %s" % (len(y), y[:10]))
