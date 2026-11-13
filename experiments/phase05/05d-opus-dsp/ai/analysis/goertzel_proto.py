#!/usr/bin/env python3
"""Fixed-point Goertzel single-bin spectral detector prototype (candidate 05d).

Purpose: lock the exact integer arithmetic, register bit-widths, window length
and energy threshold for the hardware trigger BEFORE writing RTL, so the Verilog
DUT and the Python reference model (ref_trojan.py) produce bit-identical arm
timing. All arithmetic here uses the SAME operations the RTL will use:

  per input sample x (int16, the left/filtered channel sample):
      prod = COEFF_Q14 * s1                 # exact integer product
      s0   = x + (prod >> 14) - s2          # arithmetic right shift (floor)
      s2, s1 = s1, s0
  at the end of each non-overlapping window of N_WIN samples:
      energy = s1*s1 + s2*s2                # phase-independent bin energy
      if energy > THRESHOLD: arm_latch = 1  # sticky
      s1 = s2 = 0                           # reset for next window

Key frequency f_key = 7500 Hz is an EXACT DFT bin at fs=16000, N_WIN=256
(7500/ (16000/256) = 120.0), so there is no scalloping loss.
"""
import json, math, os, wave
from array import array

FS = 16000
N_WIN = 256
K_BIN = round(N_WIN * 7500 / FS)                       # 120
COEFF_Q14 = round(2.0 * math.cos(2*math.pi*K_BIN/N_WIN) * (1 << 14))   # -32141
HERE = os.path.dirname(os.path.abspath(__file__))
WAV = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"


def detector(x):
    """Run the fixed-point detector over int stream x.
    Returns (armed_bool, arm_window_index_or_-1, max_window_energy, max_abs_s)."""
    s1 = s2 = 0
    max_abs_s = 0
    max_energy = 0
    best_energy_per_window = []
    arm_win = -1
    for n, xi in enumerate(x):
        prod = COEFF_Q14 * s1
        s0 = xi + (prod >> 14) - s2            # Python >> on ints == arithmetic floor shift
        s2, s1 = s1, s0
        a = s0 if s0 >= 0 else -s0
        if a > max_abs_s:
            max_abs_s = a
        if (n + 1) % N_WIN == 0:               # window complete
            energy = s1*s1 + s2*s2
            best_energy_per_window.append(energy)
            if energy > max_energy:
                max_energy = energy
            s1 = s2 = 0                         # reset for next window
    return max_energy, max_abs_s, best_energy_per_window


def tone(freq, amp, n):
    return [int(round(amp*math.sin(2*math.pi*freq*i/FS))) for i in range(n)]


def load_wav_mono(path, limit=None):
    with wave.open(path, "rb") as w:
        nf = w.getnframes() if limit is None else min(limit, w.getnframes())
        a = array("h"); a.frombytes(w.readframes(nf))
    import sys
    if sys.byteorder == "big":
        a.byteswap()
    return list(a)


def main():
    out = {"fs": FS, "N_WIN": N_WIN, "K_BIN": K_BIN, "COEFF_Q14": COEFF_Q14,
           "coeff_float": 2.0*math.cos(2*math.pi*K_BIN/N_WIN), "cases": {}}

    # 1. Key tone at several amplitudes
    for amp in (32767, 16384, 8192, 4096, 2048, 1024):
        e, ms, _ = detector(tone(7500, amp, N_WIN*4))
        out["cases"][f"key7500_amp{amp}"] = {"max_energy": e, "max_abs_s": ms}

    # 2. Near-key and other full-scale tones (selectivity / false-arm check)
    for f in (500, 1000, 2000, 3000, 4000, 6000, 7000, 7250, 7400, 7500, 7600, 7750):
        e, ms, _ = detector(tone(f, 32767, N_WIN*4))
        out["cases"][f"tone{f}_fs"] = {"max_energy": e, "max_abs_s": ms}

    # 3. Degenerate stimuli
    import random
    rng = random.Random(2026)
    rnd = [rng.randint(-32768, 32767) for _ in range(N_WIN*8)]
    e, ms, _ = detector(rnd); out["cases"]["random"] = {"max_energy": e, "max_abs_s": ms}
    e, ms, _ = detector([0]*(N_WIN*4)); out["cases"]["silence"] = {"max_energy": e, "max_abs_s": ms}
    imp = [0]*(N_WIN*4); imp[0] = 32767
    e, ms, _ = detector(imp); out["cases"]["impulse"] = {"max_energy": e, "max_abs_s": ms}
    # full-scale square-ish worst case (edges stimulus pattern)
    edge = [0, 32767, -32768, -1, 1, 16383, -16384, 85, 42]
    e, ms, _ = detector([edge[i % len(edge)] for i in range(N_WIN*4)])
    out["cases"]["edges"] = {"max_energy": e, "max_abs_s": ms}

    # 4. Real audio corpus (full 15 s)
    xr = load_wav_mono(WAV)
    e, ms, _ = detector(xr)
    out["cases"]["real_noisy_wav_full"] = {"max_energy": e, "max_abs_s": ms, "n_samples": len(xr)}

    # ---- threshold: locked power-of-two for cheap HW (arm iff energy >= 2^THR_POW2) ----
    THR_POW2 = 46
    thr = 1 << THR_POW2
    key_energies = {int(k.split("amp")[1]): v["max_energy"] for k, v in out["cases"].items() if k.startswith("key7500_amp")}
    # "normal operation" = everything that is NOT a deliberate 7500 Hz key tone
    def is_key(name):
        return name.startswith("key7500_amp") or name == "tone7500_fs"
    non_key = {k: v["max_energy"] for k, v in out["cases"].items() if not is_key(k)}
    non_key_max = max(non_key.values())
    non_key_src = max(non_key, key=non_key.get)
    real_max = out["cases"]["real_noisy_wav_full"]["max_energy"]
    key_fs = key_energies[32767]
    arms_per_case = {k: bool(v["max_energy"] >= thr) for k, v in out["cases"].items()}
    key_min_arm_amp = next((a for a in sorted(key_energies) if key_energies[a] >= thr), None)
    out["threshold_analysis"] = {
        "threshold": thr, "threshold_pow2": THR_POW2,
        "hw_check": "arm iff energy >= 2^46  (i.e. any energy bit >= 46 set)",
        "key_energy_by_amp": key_energies,
        "loudest_non_key_energy": non_key_max, "loudest_non_key_source": non_key_src,
        "real_audio_max_energy": real_max, "key_fs_energy": key_fs,
        "margin_db_threshold_over_real_audio": 10*math.log10(thr/max(real_max, 1)),
        "margin_db_key_fs_over_threshold": 10*math.log10(key_fs/thr),
        "margin_db_key_fs_over_real_audio": 10*math.log10(key_fs/max(real_max, 1)),
        "min_key_amp_arming": key_min_arm_amp,
        "arms_per_case": arms_per_case,
        "any_non_key_arms": any(arms_per_case[k] for k in non_key if k != "real_noisy_wav_full"),
        "real_audio_arms": arms_per_case["real_noisy_wav_full"],
    }
    non_key_adversarial = {k: v for k, v in non_key.items() if k.startswith("tone")}  # pure sines an attacker could emit
    # max_abs_s across everything -> register sizing
    out["max_abs_s_overall"] = max(v["max_abs_s"] for v in out["cases"].values())
    out["s_bits_signed_needed"] = out["max_abs_s_overall"].bit_length() + 1
    out["max_energy_overall"] = max(v["max_energy"] for v in out["cases"].values())
    out["energy_bits_needed"] = out["max_energy_overall"].bit_length() + 1

    dst = os.path.join(HERE, "..", "..", "reports", "analysis", "goertzel_proto.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=2)

    # ---- human summary ----
    print("COEFF_Q14 = %d  (2cos(2pi*%d/%d) = %.6f)" % (COEFF_Q14, K_BIN, N_WIN, out["coeff_float"]))
    print("key7500 energies by amp:")
    for amp in sorted(key_energies, reverse=True):
        print("   amp %5d -> energy %d" % (amp, key_energies[amp]))
    print("loudest NON-key energy: %d  (%s)" % (non_key_max, non_key_src))
    print("other-tone energies:")
    for f in (6000, 7000, 7250, 7400, 7500, 7600, 7750):
        print("   tone %4d Hz fs -> energy %d" % (f, out["cases"][f"tone{f}_fs"]["max_energy"]))
    print("real_noisy_wav_full max window energy: %d" % out["cases"]["real_noisy_wav_full"]["max_energy"])
    ta = out["threshold_analysis"]
    print("THRESHOLD = 2^%d = %d  (arm iff energy >= THRESHOLD)" % (ta["threshold_pow2"], thr))
    print("min key amp that arms: %s" % ta["min_key_amp_arming"])
    print("margin threshold-over-real-audio: %.1f dB" % ta["margin_db_threshold_over_real_audio"])
    print("margin key(fs)-over-threshold:    %.1f dB" % ta["margin_db_key_fs_over_threshold"])
    print("margin key(fs)-over-real-audio:   %.1f dB" % ta["margin_db_key_fs_over_real_audio"])
    print("real audio arms? %s   any pure non-key tone/noise arms? %s" % (ta["real_audio_arms"], ta["any_non_key_arms"]))
    print("arms_per_case:")
    for k in sorted(arms_per_case):
        print("   %-24s %s" % (k, "ARM" if arms_per_case[k] else "."))
    print("max |s| overall: %d  -> s needs %d signed bits" % (out["max_abs_s_overall"], out["s_bits_signed_needed"]))
    print("max energy overall: %d -> energy needs %d bits" % (out["max_energy_overall"], out["energy_bits_needed"]))


if __name__ == "__main__":
    main()
