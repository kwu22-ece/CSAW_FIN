#!/usr/bin/env python3
"""FINAL multiplier-free spectral trigger prototype (candidate 05d).

Resource-aware redesign: the first RTL used a Goertzel at 7500 Hz whose
coefficient (-1.9616) and s1^2+s2^2 energy needed real multipliers; synthesized
without DSP inference that cost 9176/5280 LC (173%, over budget).

Fix (pure DSP): pick the key frequency at fs/3 = 5333.33 Hz, an EXACT DFT bin
k=64 at window N=192, where the Goertzel coefficient 2*cos(2*pi/3) = -1 EXACTLY.
The recurrence collapses to  s0 = x - s1 - s2  (adds only, NO multiply), and we
threshold on the L1 magnitude |s1|+|s2| at the window boundary (abs+add, NO
squares). Zero multipliers -> tiny LUT cost. 5333 Hz is still deep in the filter
stopband (~ -60 dB) so the key tone is masked and normal audio is weak there.
"""
import json, math, os, wave
from array import array

FS = 16000
N_WIN = 576
K_BIN = 192                     # fs*192/576 = fs/3 = 5333.33 Hz  -> coeff = 2cos(2pi/3) = -1
F_KEY = FS * K_BIN / N_WIN
WAV = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"
HERE = os.path.dirname(os.path.abspath(__file__))


def detector_l1(x):
    """coeff=-1 Goertzel: s0 = x - s1 - s2. Returns (max_window_L1, max_abs_s)."""
    s1 = s2 = 0
    max_l1 = 0
    max_abs_s = 0
    for n, xi in enumerate(x):
        s0 = xi - s1 - s2
        s2, s1 = s1, s0
        if abs(s0) > max_abs_s:
            max_abs_s = abs(s0)
        if (n + 1) % N_WIN == 0:
            l1 = abs(s1) + abs(s2)
            if l1 > max_l1:
                max_l1 = l1
            s1 = s2 = 0
    return max_l1, max_abs_s


def tone(freq, amp, n):
    return [int(round(amp * math.sin(2 * math.pi * freq * i / FS))) for i in range(n)]


def load_wav(path):
    with wave.open(path, "rb") as w:
        a = array("h"); a.frombytes(w.readframes(w.getnframes()))
    import sys
    if sys.byteorder == "big":
        a.byteswap()
    return list(a)


def main():
    out = {"fs": FS, "N_WIN": N_WIN, "K_BIN": K_BIN, "f_key_hz": F_KEY,
           "coeff": 2 * math.cos(2 * math.pi * K_BIN / N_WIN), "metric": "L1=|s1|+|s2|", "cases": {}}
    for amp in (32767, 16384, 8192, 4096, 2048, 1024):
        l1, ms = detector_l1(tone(F_KEY, amp, N_WIN * 4))
        out["cases"][f"key_amp{amp}"] = {"max_l1": l1, "max_abs_s": ms}
    for f in (500, 1000, 2000, 3000, 4000, 4500, 5000, 5200, 5333.333, 5467, 5600, 6000, 7000, 7500):
        l1, ms = detector_l1(tone(f, 32767, N_WIN * 4))
        out["cases"][f"tone_{int(round(f))}_fs"] = {"max_l1": l1, "max_abs_s": ms}
    import random
    rng = random.Random(2026)
    for nm, seq in (("random", [rng.randint(-32768, 32767) for _ in range(N_WIN * 8)]),
                    ("silence", [0] * (N_WIN * 4)),
                    ("impulse", [32767] + [0] * (N_WIN * 4 - 1)),
                    ("edges", [[0, 32767, -32768, -1, 1, 16383, -16384][i % 7] for i in range(N_WIN * 4)])):
        l1, ms = detector_l1(seq)
        out["cases"][nm] = {"max_l1": l1, "max_abs_s": ms}
    l1, ms = detector_l1(load_wav(WAV))
    out["cases"]["real_noisy_wav_full"] = {"max_l1": l1, "max_abs_s": ms}

    # ---- lock a power-of-two L1 threshold with margin over normal operation ----
    key_l1 = {int(k.split("amp")[1]): v["max_l1"] for k, v in out["cases"].items() if k.startswith("key_amp")}
    def is_key(nm):
        return nm.startswith("key_amp") or nm == "tone_5333_fs"
    non_key = {k: v["max_l1"] for k, v in out["cases"].items() if not is_key(k)}
    real_max = out["cases"]["real_noisy_wav_full"]["max_l1"]
    # Lock the largest power-of-two threshold that a FULL-SCALE key tone still
    # clears (maximizes the margin over real audio while a full-scale key arms).
    kfs = key_l1[32767]
    p = 1
    while (1 << (p + 1)) <= kfs:
        p += 1
    THR_POW2 = p
    thr = 1 << THR_POW2
    arms = {k: bool(v["max_l1"] >= thr) for k, v in out["cases"].items()}
    out["threshold_analysis"] = {
        "threshold": thr, "threshold_pow2": THR_POW2,
        "hw_check": f"arm iff (|s1|+|s2|) >= 2^{THR_POW2}",
        "key_l1_by_amp": key_l1,
        "loudest_non_key_l1": max(non_key.values()),
        "loudest_non_key_src": max(non_key, key=non_key.get),
        "real_audio_max_l1": real_max,
        "key_fs_l1": key_l1[32767],
        "margin_db_threshold_over_real_audio": 20 * math.log10(thr / max(real_max, 1)),
        "margin_db_key_fs_over_threshold": 20 * math.log10(key_l1[32767] / thr),
        "margin_db_key_fs_over_real_audio": 20 * math.log10(key_l1[32767] / max(real_max, 1)),
        "min_key_amp_arming": next((a for a in sorted(key_l1) if key_l1[a] >= thr), None),
        "real_audio_arms": arms["real_noisy_wav_full"],
        "any_non_key_arms": any(arms[k] for k in non_key if k != "real_noisy_wav_full"),
        "arms_per_case": arms,
    }
    out["max_abs_s_overall"] = max(v["max_abs_s"] for v in out["cases"].values())
    out["s_bits_signed_needed"] = out["max_abs_s_overall"].bit_length() + 1
    out["max_l1_overall"] = max(v["max_l1"] for v in out["cases"].values())

    with open(os.path.join(HERE, "..", "..", "reports", "analysis", "trigger_final_proto.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    ta = out["threshold_analysis"]
    print("f_key=%.3f Hz  N_WIN=%d  coeff=%.4f  metric=L1" % (F_KEY, N_WIN, out["coeff"]))
    print("key L1 by amp:", {a: key_l1[a] for a in sorted(key_l1, reverse=True)})
    print("THRESHOLD = 2^%d = %d" % (ta["threshold_pow2"], thr))
    print("loudest non-key L1: %d (%s)   real-audio L1: %d" % (ta["loudest_non_key_l1"], ta["loudest_non_key_src"], real_max))
    print("margins: thr/real=%.1f dB  keyfs/thr=%.1f dB  keyfs/real=%.1f dB"
          % (ta["margin_db_threshold_over_real_audio"], ta["margin_db_key_fs_over_threshold"], ta["margin_db_key_fs_over_real_audio"]))
    print("min key amp arming: %s   real arms? %s   any non-key arms? %s"
          % (ta["min_key_amp_arming"], ta["real_audio_arms"], ta["any_non_key_arms"]))
    print("max|s|=%d (%d signed bits)" % (out["max_abs_s_overall"], out["s_bits_signed_needed"]))
    print("arming non-key tones:")
    for k in sorted(out["cases"]):
        if k.startswith("tone_") and arms[k]:
            print("   ARM:", k, out["cases"][k]["max_l1"])


if __name__ == "__main__":
    main()
