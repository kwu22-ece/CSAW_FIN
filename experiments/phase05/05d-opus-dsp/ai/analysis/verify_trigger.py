#!/usr/bin/env python3
# -I recommended. Independent VALIDATION of the candidate-05d Trojan TRIGGER.
#
# KEY = verify_trigger
# CLAIM: "The activation metric is specific: a genuine fs/3 key tone arms it,
#         but no normal audio and no nearby tone does."
#
# This script implements the multiplier-free Goertzel single-bin detector FROM
# SCRATCH (it does NOT import tests/ref_trojan). The detector is re-derived here
# purely from the documented spec:
#     per sample:   s0 = x - s1 - s2 ;  s2, s1 = s1, s0        (coeff == -1)
#     every 576:    L1 = |s1| + |s2| ;  arm if L1 >= 2**23 ;  reset s1=s2=0
# Two independent implementations (pure-int scalar loop + numpy-vectorized) are
# cross-checked against each other so the measurement engine is self-validated.
#
# All numbers written to reports/analysis/verify_trigger.json are MEASURED.
import json, math, os, sys
import numpy as np
from scipy import signal as spsig
from scipy.io import wavfile

# ---- Detector constants, independently derived from the documented spec ----
FS           = 16000
N_WIN        = 576
K_BIN        = 192
ARM_THRESHOLD = 1 << 23                 # 8388608  (L1 magnitude |s1|+|s2|)
F_KEY        = FS / 3.0                 # 5333.333... Hz  == bin k/N * fs = 192/576*16000

HERE   = os.path.dirname(os.path.abspath(__file__))
PROOT  = os.path.normpath(os.path.join(HERE, "..", ".."))    # .../05d-opus-dsp (ai/analysis is 2 levels deep)
WAVPATH = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"
OUTJSON = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp/reports/analysis/verify_trigger.json"

INT16_MIN, INT16_MAX = -(1 << 15), (1 << 15) - 1


# --------------------------------------------------------------------------- #
#  DETECTOR  (from scratch)                                                    #
# --------------------------------------------------------------------------- #
def goertzel_coeff_check():
    """Independently confirm the multiplier-free premise: at bin k=192,N=576 the
    Goertzel coefficient 2*cos(2*pi*k/N) equals -1 exactly (to fp precision)."""
    c = 2.0 * math.cos(2.0 * math.pi * K_BIN / N_WIN)
    return c

def windows_l1_scalar(x):
    """Pure-integer, from-scratch reference. Returns (list_of_window_L1,
    first_arm_window_or_None). Only COMPLETE 576-sample windows are evaluated
    (matches hardware: arm is only checked at window completion)."""
    s1 = 0
    s2 = 0
    l1s = []
    first_arm = None
    for i in range(len(x)):
        s0 = int(x[i]) - s1 - s2
        s2 = s1
        s1 = s0
        if (i + 1) % N_WIN == 0:
            l1 = abs(s1) + abs(s2)
            w = (i + 1) // N_WIN - 1
            l1s.append(l1)
            if l1 >= ARM_THRESHOLD and first_arm is None:
                first_arm = w
            s1 = 0
            s2 = 0
    return l1s, first_arm

def windows_l1_vec(blocks):
    """Vectorized over independent 576-sample windows. `blocks` is an int64
    array (n_blocks, N_WIN). Returns int64 L1 per block. Same recurrence,
    each block starts from s1=s2=0 (the per-window reset)."""
    blocks = np.ascontiguousarray(blocks, dtype=np.int64)
    nb = blocks.shape[0]
    s1 = np.zeros(nb, dtype=np.int64)
    s2 = np.zeros(nb, dtype=np.int64)
    for i in range(N_WIN):
        s0 = blocks[:, i] - s1 - s2
        s2 = s1
        s1 = s0
    return np.abs(s1) + np.abs(s2)

def signal_max_window_l1(x):
    """Max L1 over all COMPLETE windows of a 1-D integer signal, + first arm
    window index (or None). Uses the vectorized engine."""
    x = np.asarray(x, dtype=np.int64)
    nfull = len(x) // N_WIN
    if nfull == 0:
        return 0, None, 0
    blocks = x[:nfull * N_WIN].reshape(nfull, N_WIN)
    l1 = windows_l1_vec(blocks)
    first = None
    arm_idx = np.nonzero(l1 >= ARM_THRESHOLD)[0]
    if arm_idx.size:
        first = int(arm_idx[0])
    return int(l1.max()), first, nfull


# --------------------------------------------------------------------------- #
#  Signal generators (int16-domain)                                            #
# --------------------------------------------------------------------------- #
def tone(f, A, n, phase=0.0):
    i = np.arange(n)
    s = np.round(A * np.sin(2.0 * np.pi * f * i / FS + phase))
    return np.clip(s, INT16_MIN, INT16_MAX).astype(np.int64)

def tone_phase0_window_l1(f, A):
    """Single-window L1 for a tone starting at phase 0 (the canonical key)."""
    b = tone(f, A, N_WIN, 0.0)[None, :]
    return int(windows_l1_vec(b)[0])

def tone_maxphase_window_l1(f, A, n_phase=720):
    """Worst-case (MAX over start-phase) single-window L1 for a SUSTAINED tone.
    A sustained tone drifts through all window-start phases, so max-over-phase
    is exactly what a long exposure would eventually hit."""
    i = np.arange(N_WIN)
    ph = np.linspace(0.0, 2.0 * np.pi, n_phase, endpoint=False)
    arg = 2.0 * np.pi * f * i / FS
    blk = np.round(A * np.sin(arg[None, :] + ph[:, None]))
    blk = np.clip(blk, INT16_MIN, INT16_MAX).astype(np.int64)
    return int(windows_l1_vec(blk).max())

def tone_phase_l1_stats(f, A, n_phase=720):
    i = np.arange(N_WIN)
    ph = np.linspace(0.0, 2.0 * np.pi, n_phase, endpoint=False)
    arg = 2.0 * np.pi * f * i / FS
    blk = np.round(A * np.sin(arg[None, :] + ph[:, None]))
    blk = np.clip(blk, INT16_MIN, INT16_MAX).astype(np.int64)
    l1 = windows_l1_vec(blk)
    return int(l1.min()), int(l1.max())


# --------------------------------------------------------------------------- #
def db20(ratio):
    return 20.0 * math.log10(ratio) if ratio > 0 else float("-inf")


def main():
    R = {"meta": {}, "coeff_check": {}, "key_tone": {}, "coarse_sweep": {},
         "fine_sweep_bandwidth": {}, "real_wav": {}, "white_noise": {},
         "chord": {}, "chirp": {}, "margins_dB": {}, "verdict": {}}

    R["meta"] = {
        "FS": FS, "N_WIN": N_WIN, "K_BIN": K_BIN,
        "ARM_THRESHOLD": ARM_THRESHOLD, "F_KEY_Hz": F_KEY,
        "bin_spacing_Hz": FS / N_WIN,
        "note": "Detector reimplemented from scratch; ref_trojan NOT imported.",
    }

    # 0) Independent self-validation: scalar vs vectorized on a random signal,
    #    and the multiplier-free coeff premise.
    coeff = goertzel_coeff_check()
    rng0 = np.random.default_rng(12345)
    xchk = rng0.integers(INT16_MIN, INT16_MAX + 1, size=N_WIN * 7).astype(np.int64)
    l1_scal, _ = windows_l1_scalar(xchk)
    nfull = len(xchk) // N_WIN
    l1_vec = windows_l1_vec(xchk[:nfull * N_WIN].reshape(nfull, N_WIN))
    engines_match = (list(map(int, l1_scal)) == list(map(int, l1_vec)))
    # also verify scalar first_arm logic on the key tone below is consistent
    R["coeff_check"] = {
        "two_cos_2pi_k_over_N": coeff,
        "equals_minus_one_exactly": (coeff == -1.0),
        "abs_err_from_-1": abs(coeff - (-1.0)),
        "scalar_vs_vector_engines_match": bool(engines_match),
    }

    # 1) KEY TONE at exact fs/3, canonical sine phase, listed amplitudes.
    amps = [32767, 26214, 16384, 8192]
    kt = {}
    for A in amps:
        l1_0 = tone_phase0_window_l1(F_KEY, A)
        l1min, l1max = tone_phase_l1_stats(F_KEY, A, n_phase=720)
        kt[str(A)] = {
            "L1_phase0": l1_0,
            "armed_phase0": bool(l1_0 >= ARM_THRESHOLD),
            "L1_min_over_phase": l1min,
            "L1_max_over_phase": l1max,
            "armed_all_phases": bool(l1min >= ARM_THRESHOLD),
            "armed_some_phase": bool(l1max >= ARM_THRESHOLD),
            "L1_over_threshold_ratio_dB_phase0": db20(l1_0 / ARM_THRESHOLD),
        }
    # also: first-arm window index via the integer scalar engine for full-scale
    xk = tone(F_KEY, 32767, N_WIN * 3, 0.0)
    _, first_arm_scalar = windows_l1_scalar(xk)
    kt["full_scale_first_arm_window_scalar"] = first_arm_scalar

    # lowest amplitude that arms (canonical phase-0), binary search on integer A
    def arms_phase0(A):
        return tone_phase0_window_l1(F_KEY, A) >= ARM_THRESHOLD
    lo, hi = 1, 32767
    # ensure monotonic-ish: full scale arms
    A_min_phase0 = None
    if arms_phase0(32767):
        lo, hi = 1, 32767
        while lo < hi:
            mid = (lo + hi) // 2
            if arms_phase0(mid):
                hi = mid
            else:
                lo = mid + 1
        A_min_phase0 = lo
    # lowest amplitude that arms at BEST phase, and that arms at ALL phases
    def arms_bestphase(A):
        _, mx = tone_phase_l1_stats(F_KEY, A, n_phase=360)
        return mx >= ARM_THRESHOLD
    def arms_allphase(A):
        mn, _ = tone_phase_l1_stats(F_KEY, A, n_phase=360)
        return mn >= ARM_THRESHOLD
    def bsearch(pred):
        if not pred(32767):
            return None
        lo, hi = 1, 32767
        while lo < hi:
            mid = (lo + hi) // 2
            if pred(mid):
                hi = mid
            else:
                lo = mid + 1
        return lo
    kt["A_min_arm_phase0"] = A_min_phase0
    kt["A_min_arm_bestphase"] = bsearch(arms_bestphase)
    kt["A_min_arm_allphase"] = bsearch(arms_allphase)
    kt["A_min_arm_phase0_pct_fullscale"] = (100.0 * A_min_phase0 / 32767) if A_min_phase0 else None
    R["key_tone"] = kt

    # 2) COARSE SWEEP 200..7800 Hz / 100 Hz, full scale, worst-case over phase.
    fs_coarse = list(range(200, 7801, 100))
    coarse_arm = []
    coarse_rows = []
    for f in fs_coarse:
        l1 = tone_maxphase_window_l1(float(f), 32767, n_phase=720)
        armed = l1 >= ARM_THRESHOLD
        coarse_rows.append({"f_Hz": f, "L1_maxphase": l1, "armed": bool(armed)})
        if armed:
            coarse_arm.append(f)
    # nearest grid points to fs/3
    R["coarse_sweep"] = {
        "n_freqs": len(fs_coarse),
        "step_Hz": 100,
        "amplitude": 32767,
        "metric": "max over 720 start-phases of single-window L1 (sustained-tone worst case)",
        "freqs_that_arm": coarse_arm,
        "any_arm": len(coarse_arm) > 0,
        "nearest_grid_to_fkey": [5300, 5400],
        "L1_at_5300": next(r["L1_maxphase"] for r in coarse_rows if r["f_Hz"] == 5300),
        "L1_at_5400": next(r["L1_maxphase"] for r in coarse_rows if r["f_Hz"] == 5400),
        "global_max_L1_excluding_none": max(r["L1_maxphase"] for r in coarse_rows),
        "rows": coarse_rows,
    }

    # 3) FINE SWEEP around fs/3 to find arming bandwidth (worst-case over phase).
    # scan +/- 60 Hz at 0.25 Hz; find max |offset| that still arms.
    offsets = np.round(np.arange(-60.0, 60.0 + 1e-9, 0.25), 4)
    fine_rows = []
    arming_offsets = []
    for off in offsets:
        f = F_KEY + float(off)
        l1 = tone_maxphase_window_l1(f, 32767, n_phase=1440)
        armed = l1 >= ARM_THRESHOLD
        fine_rows.append({"offset_Hz": float(off), "f_Hz": f,
                          "L1_maxphase": int(l1), "armed": bool(armed)})
        if armed:
            arming_offsets.append(float(off))
    if arming_offsets:
        half_bw_pos = max(o for o in arming_offsets)
        half_bw_neg = min(o for o in arming_offsets)
        max_abs_off = max(abs(half_bw_pos), abs(half_bw_neg))
    else:
        half_bw_pos = half_bw_neg = max_abs_off = None
    R["fine_sweep_bandwidth"] = {
        "scan_range_Hz": [-60.0, 60.0], "step_Hz": 0.25,
        "amplitude": 32767, "n_phase": 1440,
        "arming_offset_max_pos_Hz": half_bw_pos,
        "arming_offset_max_neg_Hz": half_bw_neg,
        "max_abs_arming_offset_Hz": max_abs_off,
        "full_arming_bandwidth_Hz": (half_bw_pos - half_bw_neg) if arming_offsets else 0.0,
        "comment": "largest |f-5333.33| (Hz) at full scale that still arms; "
                   "beyond this a full-scale tone no longer arms",
        "bin_spacing_Hz": FS / N_WIN,
        "rows": fine_rows,
    }

    # 4) REAL WAV (all complete windows).
    sr, wav = wavfile.read(WAVPATH)
    wav = np.asarray(wav)
    if wav.ndim > 1:
        wav = wav[:, 0]
    wav = wav.astype(np.int64)
    wav_max_l1, wav_first_arm, wav_nwin = signal_max_window_l1(wav)
    R["real_wav"] = {
        "path": WAVPATH, "sample_rate": int(sr), "n_samples": int(len(wav)),
        "duration_s": len(wav) / FS, "n_complete_windows": wav_nwin,
        "max_window_L1": wav_max_l1,
        "any_window_arms": wav_first_arm is not None,
        "first_arm_window": wav_first_arm,
        "peak_abs_sample": int(np.abs(wav).max()),
    }

    # 5) WHITE NOISE, several seeds, full-scale uniform int16, 15 s each.
    noise_rows = []
    wn_global_max = 0
    wn_any_arm = False
    for seed in [1, 2, 3, 7, 42, 1234]:
        rng = np.random.default_rng(seed)
        xn = rng.integers(INT16_MIN, INT16_MAX + 1, size=FS * 15).astype(np.int64)
        m, fa, nw = signal_max_window_l1(xn)
        noise_rows.append({"seed": seed, "max_window_L1": m,
                           "n_windows": nw, "any_arm": fa is not None})
        wn_global_max = max(wn_global_max, m)
        wn_any_arm = wn_any_arm or (fa is not None)
    R["white_noise"] = {
        "amplitude": "full-scale uniform int16 [-32768,32767]",
        "duration_s_each": 15, "seeds": [r["seed"] for r in noise_rows],
        "global_max_window_L1": wn_global_max, "any_window_arms": wn_any_arm,
        "rows": noise_rows,
    }

    # 6) 3-TONE MUSICAL CHORD (A major triad: 440, 554.37, 659.25 Hz), full scale.
    chord_freqs = [440.0, 554.37, 659.25]
    n_chord = FS * 8
    i = np.arange(n_chord)
    mix = sum(np.sin(2.0 * np.pi * f * i / FS) for f in chord_freqs)
    mix = mix / np.max(np.abs(mix)) * 32767.0          # normalize peak to full scale
    xc = np.clip(np.round(mix), INT16_MIN, INT16_MAX).astype(np.int64)
    ch_m, ch_fa, ch_nw = signal_max_window_l1(xc)
    R["chord"] = {
        "freqs_Hz": chord_freqs, "duration_s": n_chord / FS,
        "amplitude": "peak-normalized to 32767", "n_windows": ch_nw,
        "max_window_L1": ch_m, "any_window_arms": ch_fa is not None,
        "first_arm_window": ch_fa,
    }

    # 7) LINEAR CHIRP 100 -> 7900 Hz, full scale, 15 s (DOES pass through fs/3).
    T = 15.0
    n_ch = int(FS * T)
    t = np.arange(n_ch) / FS
    f0, f1 = 100.0, 7900.0
    chirp = spsig.chirp(t, f0=f0, f1=f1, t1=T, method="linear")
    xch = np.clip(np.round(chirp * 32767.0), INT16_MIN, INT16_MAX).astype(np.int64)
    chm, chfa, chnw = signal_max_window_l1(xch)
    # locate which window holds the peak L1 and its instantaneous frequency
    blocks = xch[:chnw * N_WIN].reshape(chnw, N_WIN)
    l1all = windows_l1_vec(blocks)
    peak_win = int(np.argmax(l1all))
    t_center = (peak_win * N_WIN + N_WIN / 2) / FS
    inst_f_at_peak = f0 + (f1 - f0) * (t_center / T)
    sweep_rate = (f1 - f0) / T
    R["chirp"] = {
        "f0_Hz": f0, "f1_Hz": f1, "duration_s": T,
        "sweep_rate_Hz_per_s": sweep_rate, "n_windows": chnw,
        "max_window_L1": chm, "any_window_arms": chfa is not None,
        "first_arm_window": chfa,
        "peak_window_index": peak_win,
        "inst_freq_at_peak_window_Hz": inst_f_at_peak,
        "passes_through_fkey": (f0 <= F_KEY <= f1),
        "samples_within_arming_band": None,  # filled below
    }
    # how many samples the chirp spends within the measured arming half-bandwidth
    if max_abs_off:
        band = max_abs_off
        inst_f = f0 + (f1 - f0) * (t / T)
        in_band = int(np.sum(np.abs(inst_f - F_KEY) <= band))
        R["chirp"]["samples_within_arming_band"] = in_band
        R["chirp"]["windows_within_arming_band_approx"] = in_band / N_WIN

    # 8) MARGINS (dB, 20*log10 of L1 ratios; L1 is an amplitude-like magnitude).
    key_fs_l1 = R["key_tone"]["32767"]["L1_phase0"]
    worst_realaudio = wav_max_l1
    worst_nonkey = max(wav_max_l1, wn_global_max, ch_m, chm,
                       R["coarse_sweep"]["global_max_L1_excluding_none"])
    R["margins_dB"] = {
        "full_scale_key_above_threshold_dB": db20(key_fs_l1 / ARM_THRESHOLD),
        "threshold_above_worst_realaudio_window_dB": db20(ARM_THRESHOLD / worst_realaudio),
        "threshold_above_worst_nonkey_window_dB": db20(ARM_THRESHOLD / worst_nonkey),
        "full_scale_key_above_worst_realaudio_dB": db20(key_fs_l1 / worst_realaudio),
        "worst_realaudio_window_L1": worst_realaudio,
        "worst_nonkey_window_L1": worst_nonkey,
        "full_scale_key_L1_phase0": key_fs_l1,
    }

    # 9) VERDICT per the task's confirmed-condition.
    fullscale_key_arms = R["key_tone"]["32767"]["armed_phase0"]
    no_realaudio_arm   = not R["real_wav"]["any_window_arms"]
    no_noise_arm       = not R["white_noise"]["any_window_arms"]
    no_chord_arm       = not R["chord"]["any_window_arms"]
    no_chirp_arm       = not R["chirp"]["any_window_arms"]
    narrow_band        = (max_abs_off is not None) and (max_abs_off < (FS / N_WIN))  # < one bin
    only_near_fkey_arm = (len(coarse_arm) == 0) or all(abs(f - F_KEY) <= (FS / N_WIN) for f in coarse_arm)
    confirmed = bool(fullscale_key_arms and no_realaudio_arm and no_noise_arm
                     and no_chord_arm and no_chirp_arm and narrow_band and only_near_fkey_arm)
    R["verdict"] = {
        "fullscale_key_arms": fullscale_key_arms,
        "no_realaudio_window_arms": no_realaudio_arm,
        "no_white_noise_window_arms": no_noise_arm,
        "no_chord_window_arms": no_chord_arm,
        "no_chirp_window_arms": no_chirp_arm,
        "arming_band_narrower_than_one_bin": narrow_band,
        "only_near_fkey_tones_arm": only_near_fkey_arm,
        "CONFIRMED": confirmed,
    }

    os.makedirs(os.path.dirname(OUTJSON), exist_ok=True)
    with open(OUTJSON, "w") as fh:
        json.dump(R, fh, indent=2)

    # ---- console summary (MEASURED) ----
    print("=== verify_trigger (independent) ===")
    print("coeff 2cos(2pi*192/576) = %.17g  (==-1 exactly: %s)"
          % (coeff, coeff == -1.0))
    print("scalar vs vector engines match: %s" % engines_match)
    print("-- KEY TONE @ fs/3=%.4f Hz (sine phase) --" % F_KEY)
    for A in amps:
        d = R["key_tone"][str(A)]
        print("  A=%5d  L1=%10d  armed=%s  (%.2f dB vs thr)"
              % (A, d["L1_phase0"], d["armed_phase0"], d["L1_over_threshold_ratio_dB_phase0"]))
    print("  full-scale first-arm window (scalar) = %s" % first_arm_scalar)
    print("  lowest arming amp: phase0=%s  bestphase=%s  allphase=%s"
          % (kt["A_min_arm_phase0"], kt["A_min_arm_bestphase"], kt["A_min_arm_allphase"]))
    print("-- COARSE SWEEP 200..7800/100Hz @FS: freqs that arm = %s" % coarse_arm)
    print("   L1@5300=%d  L1@5400=%d  thr=%d"
          % (R["coarse_sweep"]["L1_at_5300"], R["coarse_sweep"]["L1_at_5400"], ARM_THRESHOLD))
    print("-- ARMING BANDWIDTH: max|offset| that arms = %s Hz  (bin spacing=%.3f Hz)"
          % (max_abs_off, FS / N_WIN))
    print("-- REAL WAV: max L1=%d  arms=%s  (windows=%d)"
          % (wav_max_l1, wav_first_arm is not None, wav_nwin))
    print("-- WHITE NOISE: global max L1=%d  arms=%s" % (wn_global_max, wn_any_arm))
    print("-- CHORD: max L1=%d  arms=%s" % (ch_m, ch_fa is not None))
    print("-- CHIRP 100->7900: max L1=%d  arms=%s  peak@inst_f=%.1f Hz  in-band samples=%s"
          % (chm, chfa is not None, inst_f_at_peak, R["chirp"]["samples_within_arming_band"]))
    print("-- MARGINS: key +%.2f dB over thr; thr +%.2f dB over worst real audio; thr +%.2f dB over worst non-key"
          % (R["margins_dB"]["full_scale_key_above_threshold_dB"],
             R["margins_dB"]["threshold_above_worst_realaudio_window_dB"],
             R["margins_dB"]["threshold_above_worst_nonkey_window_dB"]))
    print("CONFIRMED = %s" % confirmed)
    print("wrote %s" % OUTJSON)
    return R


if __name__ == "__main__":
    main()
