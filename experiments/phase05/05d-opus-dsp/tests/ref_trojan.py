#!/usr/bin/env python3
"""Reference model of the candidate-05d TROJANED FIR (harness-native).

Trojan = a frequency-domain hardware Trojan on the recovered 63-tap FIR:
  * TRIGGER: a multiplier-free Goertzel single-bin spectral detector at
    f_key = fs/3 = 5333.33 Hz (exact DFT bin k=192, window N_WIN=576) where the
    Goertzel coefficient is exactly -1, so s0 = x - s1 - s2 (adds only). When a
    non-overlapping window's L1 magnitude |s1|+|s2| reaches ARM_THRESHOLD=2^23,
    a sticky arm latch sets.
  * PAYLOAD: while armed, the FIR coefficients are spectrally inverted
    h'[k] = (-1)^k h[k] (odd-index taps negated) => the low-pass becomes a
    high-pass. The datapath/arithmetic/echo are otherwise identical.

Bit-exactness contract: when the 7500 Hz key tone is absent, the arm latch never
sets, coef_used==golden, and output is bit-identical to golden/ref_golden.py.
The arm set at the end of window w affects input samples strictly AFTER that
window (the MAC for sample n uses the latch value captured before sample n's
Goertzel window-update), matching the RTL ordering exactly.

Constants locked in ai/analysis/trigger_final_proto.py (validated: real audio
never arms, ~35 dB margin; a full-scale fs/3 tone arms in window 0).

Contract: {python} ref_trojan.py {input} {output} --coeffs PATH [--latency N]
          {python} ref_trojan.py --selftest --coeffs PATH
Input  CSV: index,channel,value (channel 0 = left = sample to filter).
Output CSV: index,channel,value (sequential index; channel 0=filtered,1=echo).
"""
from __future__ import annotations
import argparse, csv, json, math, os, sys

Q15_HALF = 1 << 14
INT16_MIN, INT16_MAX = -(1 << 15), (1 << 15) - 1

# ---- Multiplier-free Goertzel trigger constants (locked; see ai/analysis/trigger_final_proto.py) ----
# Key frequency = fs/3 = 5333.33 Hz (exact DFT bin k=192 at window N=576) so the
# Goertzel coefficient 2*cos(2*pi/3) = -1 EXACTLY, making the recurrence
# s0 = x - s1 - s2 (adds only, NO multiply). Arm metric is the L1 magnitude
# |s1|+|s2| (abs+add, NO squares). N=576 gives ~35 dB margin over real audio and
# keeps the detector tiny on iCE40 (the s1^2+s2^2 / 7500 Hz version cost 173% LC).
FS = 16000
N_WIN = 576
K_BIN = 192                                                  # fs/3 exact bin => coeff = -1
ARM_THRESHOLD = 1 << 23                                      # 8388608 (L1 magnitude)


def load_coeffs(path):
    with open(path) as fh:
        return [int(v) for v in json.load(fh)["coeffs_q15"]]


def sat16(v):
    return INT16_MAX if v > INT16_MAX else INT16_MIN if v < INT16_MIN else v


def run_trojan(x, h):
    """Apply Goertzel arm + spectral-inversion payload. Returns (y, armed_at).

    y[n]        : int16 filtered output logically aligned to x[n]
    armed_at[n] : the arm-latch value used by the MAC for sample n (0/1)
    """
    N = len(h)
    M = len(x)
    y = [0] * M
    armed_at = [0] * M
    s1 = s2 = 0
    arm = 0
    for n in range(M):
        arm_n = arm                       # latch value in force for this sample's MAC
        armed_at[n] = arm_n
        acc = 0
        kmax = min(n + 1, N)
        for k in range(kmax):
            c = -h[k] if (arm_n and (k & 1)) else h[k]   # spectral inversion when armed
            acc += c * x[n - k]
        y[n] = sat16((acc + Q15_HALF) >> 15)
        # Multiplier-free Goertzel recurrence (coeff = -1): s0 = x - s1 - s2.
        s0 = x[n] - s1 - s2
        s2, s1 = s1, s0
        if (n + 1) % N_WIN == 0:
            l1 = abs(s1) + abs(s2)         # new s1 = s0, new s2 = old s1
            if l1 >= ARM_THRESHOLD:
                arm = 1                    # sticky; affects n+1 onward
            s1 = s2 = 0                    # reset for next window
    return y, armed_at


def read_left(path):
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


def golden_fir(x, h):
    """Golden (untriggered) FIR for the self-test cross-check."""
    N = len(h); y = [0] * len(x)
    for n in range(len(x)):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += h[k] * x[n - k]
        y[n] = sat16((acc + Q15_HALF) >> 15)
    return y


def selftest(h):
    import random
    rng = random.Random(7)
    # 1) No key tone -> must equal golden exactly, never arm.
    x = [rng.randint(-32768, 32767) for _ in range(3000)]
    y, armed = run_trojan(x, h)
    g = golden_fir(x, h)
    assert y == g, "TROJAN DIVERGED FROM GOLDEN ON NON-KEY INPUT"
    assert not any(armed), "armed on non-key random input"
    # 2) 1 kHz full-scale tone -> still no arm, still golden.
    x2 = [int(round(32767 * math.sin(2 * math.pi * 1000 * i / FS))) for i in range(3000)]
    y2, a2 = run_trojan(x2, h)
    assert y2 == golden_fir(x2, h) and not any(a2), "1 kHz tone wrongly armed/diverged"
    # 3) fs/3 full-scale key tone -> arms after window 0 (sample N_WIN onward).
    fkey = FS / 3.0
    xk = [int(round(32767 * math.sin(2 * math.pi * fkey * i / FS))) for i in range(N_WIN * 2)]
    yk, ak = run_trojan(xk, h)
    first_arm = next((i for i, v in enumerate(ak) if v), None)
    assert first_arm == N_WIN, f"expected arm at n={N_WIN}, got {first_arm}"
    g = golden_fir(xk, h)
    assert yk[:N_WIN] == g[:N_WIN], "pre-arm samples differ from golden"
    assert yk[N_WIN + 16:] != g[N_WIN + 16:], "post-arm samples did not change"
    print("SELFTEST PASS: non-key==golden & no-arm; 1 kHz no-arm; fs/3 key arms@n=%d, payload active after." % N_WIN)
    print("  N_WIN=%d  K_BIN=%d (fs/3=%.2f Hz)  coeff=-1  ARM_THRESHOLD=2^23=%d" % (N_WIN, K_BIN, fkey, ARM_THRESHOLD))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?")
    ap.add_argument("output", nargs="?")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--coeffs", default=os.path.join(here, "..", "golden", "coeffs.json"))
    ap.add_argument("--latency", type=int, default=2)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    h = load_coeffs(args.coeffs)
    if args.selftest:
        selftest(h)
        return
    if not args.input or not args.output:
        ap.error("input and output required unless --selftest")

    x = read_left(args.input)
    y, armed = run_trojan(x, h)
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
    n_armed = sum(armed)
    sys.stderr.write("ref_trojan: in=%d  lat=%d  samples_armed=%d  first_arm=%s  wrote %d rows\n"
                     % (M, lat, n_armed, next((i for i, v in enumerate(armed) if v), None), wi))


if __name__ == "__main__":
    main()
