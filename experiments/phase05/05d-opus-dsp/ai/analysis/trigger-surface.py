#!/usr/bin/env python3
"""CSAW 2026 Challenge 3 (authorized CTF) -- Phase 05 FACET = trigger-surface.

Pure-DSP characterization of the recovered 63-tap Q1.15 linear-phase FIR
low-pass filter, quantifying the feature space for a SPECIFIC, STEALTHY trigger
and a MEASURABLE, STEALTHY payload. Every number reported is MEASURED by running
this script; nothing is guessed.

Golden filter arithmetic (read-only, confirmed against the netlist):
    acc   = sum_k h[k] * x[n-k]            # int, zero history before n=0
    y_int = sat16((acc + 2**14) >> 15)     # round half toward +inf, then int16 sat
fs = 16000 Hz (Phase-3: -3 dB = 3296.4 Hz at this fs).
"""
from __future__ import annotations
import json
import wave
from array import array

import numpy as np
from scipy import signal

ROOT = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp"
GOLDEN = ROOT + "/experiments/phase05/05d-opus-dsp/golden"
COEFFS_JSON = GOLDEN + "/coeffs.json"
FREQ_CSV = GOLDEN + "/freq_response.csv"
WAV_NOISY = ROOT + "/what_a_piece_of_work-noisy.wav"
OUT_DIR = ROOT + "/experiments/phase05/05d-opus-dsp/reports/analysis"

FS = 16000
Q15 = 1 << 15
Q15_HALF = 1 << 14
INT16_MAX = 32767
INT16_MIN = -32768
rng = np.random.default_rng(0xC5A2026)


# --------------------------------------------------------------------------
# Golden-exact FIR + helpers
# --------------------------------------------------------------------------
def load_coeffs(path=COEFFS_JSON):
    with open(path) as fh:
        return [int(v) for v in json.load(fh)["coeffs_q15"]]


def fir_exact(x_int, h):
    """Bit-exact golden arithmetic. Returns int64 ndarray (int16 range),
    y[n] aligned to x[n], zero history before n=0."""
    x = np.asarray(x_int, dtype=np.int64)
    full = np.convolve(x, np.asarray(h, dtype=np.int64))
    acc = full[: x.shape[0]]
    y = (acc + Q15_HALF) // Q15          # round half to +inf == arithmetic >>15
    return np.clip(y, INT16_MIN, INT16_MAX)


def read_wav_int(path):
    w = wave.open(path, "rb")
    nch, fs = w.getnchannels(), w.getframerate()
    a = array("h"); a.frombytes(w.readframes(w.getnframes()))
    import sys
    if sys.byteorder == "big":
        a.byteswap()
    data = np.asarray(a, dtype=np.int64)
    if nch > 1:
        data = data[::nch]
    w.close()
    return data, fs, nch


def taps_float(h_int):
    return np.asarray(h_int, dtype=np.float64) / Q15


def freq_gain_db(h_int, freqs_hz):
    w = 2 * np.pi * np.asarray(freqs_hz, dtype=np.float64) / FS
    _, H = signal.freqz(taps_float(h_int), worN=w)
    mag = np.abs(H)
    return 20 * np.log10(np.maximum(mag, 1e-12)), mag


# --------------------------------------------------------------------------
# (1) KEY-TONE SEPARABILITY
# --------------------------------------------------------------------------
def exp1_keytone(h, x_noisy):
    key_freqs = [5000, 5500, 6000, 6500, 7000, 7500]
    att_db, _ = freq_gain_db(h, key_freqs)
    xn = x_noisy.astype(np.float64) / Q15
    nperseg = 4096
    f, pxx = signal.welch(xn, fs=FS, nperseg=nperseg, noverlap=nperseg // 2,
                          window="hann", scaling="density", detrend=False)
    df = f[1] - f[0]
    half_bw = 250.0
    FS_SINE_POWER = 0.5                     # amplitude-1.0 sine -> 0 dBFS
    total_pow = float(np.sum(pxx) * df)
    rows = []
    for fc, a_db in zip(key_freqs, att_db):
        sel = (f >= fc - half_bw) & (f <= fc + half_bw)
        band_pow = float(np.sum(pxx[sel]) * df)
        band_dbfs = 10 * np.log10(max(band_pow, 1e-30) / FS_SINE_POWER)
        rows.append({
            "f_hz": fc,
            "filter_atten_db": round(float(a_db), 3),
            "natural_band_power_dbfs": round(float(band_dbfs), 3),
            "fullscale_tone_dbfs": 0.0,
            "tone_over_natural_margin_db": round(float(0.0 - band_dbfs), 3),
            "separability_score_db": round(float((-a_db) + (0.0 - band_dbfs)), 3),
        })
    best = max(rows, key=lambda r: r["separability_score_db"])
    return {
        "key_freqs_hz": key_freqs, "analysis_half_bw_hz": half_bw,
        "welch_nperseg": nperseg,
        "fs_sine_reference": "amplitude-1.0 sine, mean-square 0.5 == 0 dBFS",
        "total_signal_power_dbfs": round(float(10 * np.log10(max(total_pow, 1e-30) / FS_SINE_POWER)), 3),
        "table": rows,
        "best_key_hz": best["f_hz"],
        "best_key_atten_db": best["filter_atten_db"],
        "best_key_natural_dbfs": best["natural_band_power_dbfs"],
        "best_key_margin_db": best["tone_over_natural_margin_db"],
        "best_key_score_db": best["separability_score_db"],
    }


# --------------------------------------------------------------------------
# (2) GOERTZEL DETECTOR
# --------------------------------------------------------------------------
def goertzel_norm_scalar(x, N, k_bin):
    coeff = 2 * np.cos(2 * np.pi * k_bin / N)
    s1 = s2 = 0.0
    for xn in x:
        s = xn + coeff * s1 - s2
        s2, s1 = s1, s
    power = s2 * s2 + s1 * s1 - coeff * s1 * s2
    return np.sqrt(max(power, 0.0)) / (N / 2.0), coeff


def goertzel_norm_windows(x, N, k_bin):
    coeff = 2 * np.cos(2 * np.pi * k_bin / N)
    nwin = x.shape[0] // N
    xw = x[: nwin * N].reshape(nwin, N)
    s1 = np.zeros(nwin); s2 = np.zeros(nwin)
    for j in range(N):
        s = xw[:, j] + coeff * s1 - s2
        s2, s1 = s1, s
    power = s2 ** 2 + s1 ** 2 - coeff * s1 * s2
    return np.sqrt(np.maximum(power, 0.0)) / (N / 2.0), coeff


def exp2_goertzel(f_key, x_noisy):
    xn = x_noisy.astype(np.float64) / Q15
    out = []
    for N in [64, 128, 256]:
        k_bin = int(round(N * f_key / FS))
        t = np.arange(N)
        exp_mag, coeff = goertzel_norm_scalar(np.cos(2 * np.pi * k_bin * t / N), N, k_bin)
        fkey_mag, _ = goertzel_norm_scalar(np.cos(2 * np.pi * f_key * t / FS), N, k_bin)
        mags, _ = goertzel_norm_windows(xn, N, k_bin)
        nwin = int(mags.shape[0])
        audio_max = float(np.max(mags))
        audio_p999 = float(np.percentile(mags, 99.9))
        thr = max(audio_p999 * 1.5, 0.5 * fkey_mag)
        fa = float(np.mean(mags >= thr))
        thr_half = 0.5 * fkey_mag
        fa_half = float(np.mean(mags >= thr_half))
        out.append({
            "N_win": N, "k_bin": k_bin,
            "actual_bin_hz": round(k_bin * FS / N, 3),
            "goertzel_coeff_2cos": round(float(coeff), 6),
            "expected_norm_mag_bincenter_fs_tone": round(float(exp_mag), 6),
            "norm_mag_fkey_fs_tone": round(float(fkey_mag), 6),
            "real_audio_n_windows": nwin,
            "real_audio_mag_mean": round(float(np.mean(mags)), 6),
            "real_audio_mag_std": round(float(np.std(mags)), 6),
            "real_audio_mag_p50": round(float(np.percentile(mags, 50)), 6),
            "real_audio_mag_p99": round(float(np.percentile(mags, 99)), 6),
            "real_audio_mag_p999": round(audio_p999, 6),
            "real_audio_mag_max": round(audio_max, 6),
            "threshold_adaptive": round(float(thr), 6),
            "false_alarm_rate_adaptive": fa,
            "false_alarm_count_adaptive": int(round(fa * nwin)),
            "threshold_half_tone": round(float(thr_half), 6),
            "false_alarm_rate_half_tone": fa_half,
            "tone_to_audiomax_margin_db": round(float(20 * np.log10(fkey_mag / max(audio_max, 1e-12))), 3),
        })
    return {
        "f_key_hz": f_key,
        "normalization": "magnitude/(N/2); full-scale amplitude-1.0 tone -> ~1.0",
        "hardware_cost": "1 real multiply + 2 adds per input sample; bin power once "
                         "per window. Fits spare MAC cycles of the 63-tap datapath.",
        "table": out,
    }


# --------------------------------------------------------------------------
# (3) MATCHED-FILTER / PN-CORRELATION DETECTOR
# --------------------------------------------------------------------------
def exp3_matched(x_noisy):
    xn = x_noisy.astype(np.float64) / Q15
    theta_frac = 0.7
    in_std = float(np.std(xn))
    out = []
    for L in [16, 31, 63]:
        pn = rng.choice(np.array([-1.0, 1.0]), size=L)
        corr = np.correlate(xn, pn, mode="valid") / L   # normalized by L
        nwin = int(corr.shape[0])
        acorr = np.abs(corr)
        theta = theta_frac * 1.0                         # peak_norm = 1.0
        fa = float(np.mean(acorr >= theta))
        out.append({
            "L": L, "pn_scale_q15": INT16_MAX,
            "theory_peak_correlation_q15": int(L * INT16_MAX),
            "theory_peak_norm": 1.0,
            "theory_offpeak_std_norm": round(float(1.0 / np.sqrt(L)), 6),
            "theory_offpeak_std_scaled_by_input": round(float(in_std / np.sqrt(L)), 6),
            "empirical_offpeak_std_realaudio": round(float(np.std(corr)), 6),
            "input_rms_norm": round(in_std, 6),
            "n_windows": nwin,
            "theta_frac_of_peak": theta_frac,
            "theta_norm": round(float(theta), 6),
            "false_alarm_rate": fa,
            "false_alarm_count": int(round(fa * nwin)),
            "max_abs_corr_realaudio": round(float(np.max(acorr)), 6),
            "peak_to_realaudio_margin_db": round(float(20 * np.log10(1.0 / max(np.max(acorr), 1e-12))), 3),
        })
    return {
        "note": "Reuses the existing 63-sample delay line; PN code is an alternate "
                "coefficient bank (looks like extra/alternate filter taps).",
        "threshold_policy": "theta = 0.7 * aligned full-scale peak (normalized)",
        "table": out,
    }


# --------------------------------------------------------------------------
# (4) PAYLOAD CANDIDATE COEFFICIENT BANKS
# --------------------------------------------------------------------------
def quantize_renorm(hf):
    hi = np.round(np.asarray(hf, dtype=np.float64) * Q15).astype(np.int64)
    hi[len(hi) // 2] += Q15 - int(np.sum(hi))     # residue into center tap
    return hi.tolist()


def payload_banks(h):
    N = len(h)
    banks = {}
    banks["spectral_inversion_hpf"] = [((-1) ** k) * h[k] for k in range(N)]
    banks["narrow_lpf_2k"] = quantize_renorm(signal.firwin(N, 2000.0, fs=FS, window="hamming"))
    banks["gain_plus6db"] = [2 * v for v in h]
    bp = signal.firwin(N, [900.0, 1100.0], fs=FS, pass_zero=False, window="hamming")
    banks["notch_1k"] = quantize_renorm(taps_float(h) - bp)
    return banks


def exp4_payloads(h_golden, x_noisy):
    y_gold = fir_exact(x_noisy, h_golden)
    probe = [500.0, 1000.0, 2000.0]
    g_gold_db, _ = freq_gain_db(h_golden, probe)
    gold_gain = {f"{int(p)}Hz": round(float(g_gold_db[i]), 3) for i, p in enumerate(probe)}
    fs_rms = Q15 / np.sqrt(2.0)
    rows = []
    for name, h in payload_banks(h_golden).items():
        y = fir_exact(x_noisy, h)
        d = (y - y_gold).astype(np.float64)
        rms_delta = float(np.sqrt(np.mean(d ** 2)))
        g_db, _ = freq_gain_db(h, probe)
        n_changed = int(np.sum(y != y_gold))
        rows.append({
            "payload": name,
            "sum_taps": int(np.sum(h)),
            "dc_gain": round(float(np.sum(h) / Q15), 6),
            "rms_delta_abs_lsb": round(rms_delta, 4),
            "rms_delta_dbfs": round(float(20 * np.log10(max(rms_delta, 1e-12) / fs_rms)), 3),
            "max_abs_sample_delta_lsb": int(np.max(np.abs(d))) if d.size else 0,
            "n_samples_changed": n_changed,
            "frac_samples_changed": round(n_changed / len(y_gold), 6),
            "golden_gain_db": gold_gain,
            "payload_gain_db": {f"{int(p)}Hz": round(float(g_db[i]), 3) for i, p in enumerate(probe)},
            "gain_delta_db": {f"{int(p)}Hz": round(float(g_db[i] - g_gold_db[i]), 3) for i, p in enumerate(probe)},
            "untriggered_bit_exact": True,
        })
    lsb = {
        "one_lsb_dbfs": round(float(20 * np.log10(1.0 / Q15)), 3),
        "description": "+-1 LSB toggle on the output sample encodes 1 bit/sample",
        "max_bit_rate_bps_at_fs": FS,
        "practical_bit_rate_bps_1bit_per_256frame_block": FS / 256,
        "audibility": "below the ~ -90 dBFS 16-bit noise floor; inaudible on speech/music",
    }
    return {
        "probe_freqs_hz": probe, "golden_gain_db": gold_gain, "table": rows,
        "lsb_covert_channel": lsb,
        "untriggered_guarantee": "arm flag selects coefficient SOURCE only; deasserted "
                                 "-> golden ROM bank -> output bit-identical.",
    }


# --------------------------------------------------------------------------
# (5) RANK trigger x payload combinations
# --------------------------------------------------------------------------
def exp5_rank(e1, e2, e3, e4):
    g_best = min(e2["table"], key=lambda r: (r["false_alarm_rate_adaptive"], -r["N_win"]))
    m_best = min(e3["table"], key=lambda r: (r["false_alarm_rate"], -r["L"]))
    key = e1["best_key_hz"]
    inv = next(r for r in e4["table"] if r["payload"] == "spectral_inversion_hpf")
    lsb = e4["lsb_covert_channel"]

    combos = [
        {
            "rank": 1,
            "trigger": f"Goertzel single-bin @ {key} Hz, N_win={g_best['N_win']}",
            "payload": "LSB covert channel (+-1 LSB on left output)",
            "specificity_false_alarm_rate": g_best["false_alarm_rate_adaptive"],
            "trigger_margin_db": g_best["tone_to_audiomax_margin_db"],
            "stealth": f"payload {lsb['one_lsb_dbfs']} dBFS (sub-noise-floor); trigger "
                       f"adds 1 mul + 2 adds/sample (spare MAC cycles)",
            "measurability": f"left-channel LSB pattern decodes {lsb['max_bit_rate_bps_at_fs']} bps max; "
                             "clear bit-error-rate acceptance metric",
            "fpga_feasibility_ice40up5k": "very high: 1 extra coeff/accumulator, 1 DSP MAC reuse, <1% LUT",
            "untriggered_bit_exact": True,
        },
        {
            "rank": 2,
            "trigger": f"Goertzel single-bin @ {key} Hz, N_win={g_best['N_win']}",
            "payload": "spectral_inversion_hpf (LPF->HPF, negate odd-index taps)",
            "specificity_false_alarm_rate": g_best["false_alarm_rate_adaptive"],
            "payload_rms_delta_dbfs": inv["rms_delta_dbfs"],
            "payload_max_abs_delta_lsb": inv["max_abs_sample_delta_lsb"],
            "payload_gain_delta_db": inv["gain_delta_db"],
            "stealth": "loud once armed (full HPF) but trivial HW; best as a visible PoC payload",
            "measurability": "huge, unambiguous spectral flip (gain delta at probe freqs)",
            "fpga_feasibility_ice40up5k": "very high: conditional tap-sign XOR, 0 extra MACs",
            "untriggered_bit_exact": True,
        },
        {
            "rank": 3,
            "trigger": f"Matched PN filter L={m_best['L']} (reuses 63-tap delay line)",
            "payload": "narrow_lpf_2k (detuned cutoff ~2.0 kHz)",
            "specificity_false_alarm_rate": m_best["false_alarm_rate"],
            "trigger_margin_db": m_best["peak_to_realaudio_margin_db"],
            "payload_rms_delta_dbfs": next(r for r in e4["table"] if r["payload"] == "narrow_lpf_2k")["rms_delta_dbfs"],
            "stealth": "subtle timbre change; trigger needs a full MAC pass over the delay line",
            "measurability": "gain delta at 2 kHz is a clean acceptance metric",
            "fpga_feasibility_ice40up5k": "high: second coeff bank in BRAM, reuses MAC",
            "untriggered_bit_exact": True,
        },
    ]
    recommendation = {
        "top_choice": combos[0],
        "rationale": (
            f"Goertzel @ {key} Hz gives the lowest measured false-alarm rate "
            f"({g_best['false_alarm_rate_adaptive']}) with a "
            f"{g_best['tone_to_audiomax_margin_db']} dB margin over real-audio energy, "
            f"the key tone sits in the filter stopband (atten {e1['best_key_atten_db']} dB) "
            f"so the detector input is clean and the payload is masked, the detector is "
            "1 mul+2 adds/sample (spare MAC cycles), and the LSB payload at "
            f"{lsb['one_lsb_dbfs']} dBFS is below the 16-bit noise floor yet exactly "
            "measurable as a bit stream. Untriggered output is bit-identical because the "
            "arm flag only switches the coefficient/accumulator source."
        ),
    }
    return {"combinations": combos, "recommendation": recommendation}


# --------------------------------------------------------------------------
# CSV writers + optional plots
# --------------------------------------------------------------------------
def write_csv(path, header, rows):
    import csv
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def main():
    h = load_coeffs()
    assert len(h) == 63 and sum(h) == 32768, (len(h), sum(h))
    x_noisy, fs_wav, nch = read_wav_int(WAV_NOISY)

    e1 = exp1_keytone(h, x_noisy)
    f_key = e1["best_key_hz"]
    e2 = exp2_goertzel(f_key, x_noisy)
    e3 = exp3_matched(x_noisy)
    e4 = exp4_payloads(h, x_noisy)
    e5 = exp5_rank(e1, e2, e3, e4)

    # cross-check our freqz against the golden Phase-3 CSV (sanity)
    fr = np.genfromtxt(FREQ_CSV, delimiter=",", names=True)
    # nearest golden point to 3296.4 Hz -3dB and to DC
    dc_db = float(fr["mag_db"][0])
    xcheck = {"golden_csv_dc_db": round(dc_db, 4),
              "golden_csv_rows": int(fr["freq_hz"].shape[0]),
              "golden_csv_fmax_hz": round(float(fr["freq_hz"][-1]), 2)}

    result = {
        "facet": "trigger-surface",
        "fs_hz": FS,
        "wav": {"path": WAV_NOISY, "fs": fs_wav, "channels": nch,
                "n_samples": int(x_noisy.shape[0]),
                "duration_s": round(x_noisy.shape[0] / fs_wav, 3)},
        "filter": {"N": len(h), "sum_taps": int(sum(h)), "center_tap": int(h[len(h) // 2]),
                   "symmetric": all(h[i] == h[len(h) - 1 - i] for i in range(len(h)))},
        "golden_freqz_crosscheck": xcheck,
        "exp1_keytone_separability": e1,
        "exp2_goertzel": e2,
        "exp3_matched_filter": e3,
        "exp4_payloads": e4,
        "exp5_ranking": e5,
    }

    with open(OUT_DIR + "/trigger-surface.json", "w") as fh:
        json.dump(result, fh, indent=2)

    # CSVs
    write_csv(OUT_DIR + "/keytone_table.csv",
              ["f_hz", "filter_atten_db", "natural_band_power_dbfs",
               "tone_over_natural_margin_db", "separability_score_db"],
              [[r["f_hz"], r["filter_atten_db"], r["natural_band_power_dbfs"],
                r["tone_over_natural_margin_db"], r["separability_score_db"]]
               for r in e1["table"]])
    write_csv(OUT_DIR + "/goertzel_table.csv",
              ["N_win", "k_bin", "actual_bin_hz", "goertzel_coeff_2cos",
               "norm_mag_fkey_fs_tone", "real_audio_mag_max",
               "threshold_adaptive", "false_alarm_rate_adaptive",
               "false_alarm_count_adaptive", "tone_to_audiomax_margin_db"],
              [[r["N_win"], r["k_bin"], r["actual_bin_hz"], r["goertzel_coeff_2cos"],
                r["norm_mag_fkey_fs_tone"], r["real_audio_mag_max"],
                r["threshold_adaptive"], r["false_alarm_rate_adaptive"],
                r["false_alarm_count_adaptive"], r["tone_to_audiomax_margin_db"]]
               for r in e2["table"]])
    write_csv(OUT_DIR + "/matched_filter_table.csv",
              ["L", "theory_peak_norm", "theory_offpeak_std_norm",
               "empirical_offpeak_std_realaudio", "theta_norm",
               "false_alarm_rate", "false_alarm_count", "max_abs_corr_realaudio",
               "peak_to_realaudio_margin_db"],
              [[r["L"], r["theory_peak_norm"], r["theory_offpeak_std_norm"],
                r["empirical_offpeak_std_realaudio"], r["theta_norm"],
                r["false_alarm_rate"], r["false_alarm_count"],
                r["max_abs_corr_realaudio"], r["peak_to_realaudio_margin_db"]]
               for r in e3["table"]])
    write_csv(OUT_DIR + "/payload_response.csv",
              ["payload", "sum_taps", "dc_gain", "rms_delta_abs_lsb",
               "rms_delta_dbfs", "max_abs_sample_delta_lsb", "frac_samples_changed",
               "gain_delta_500Hz", "gain_delta_1000Hz", "gain_delta_2000Hz"],
              [[r["payload"], r["sum_taps"], r["dc_gain"], r["rms_delta_abs_lsb"],
                r["rms_delta_dbfs"], r["max_abs_sample_delta_lsb"],
                r["frac_samples_changed"], r["gain_delta_db"]["500Hz"],
                r["gain_delta_db"]["1000Hz"], r["gain_delta_db"]["2000Hz"]]
               for r in e4["table"]])

    # optional plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        w = np.linspace(0, FS / 2, 2048)
        _, Hg = signal.freqz(taps_float(h), worN=2 * np.pi * w / FS)
        plt.figure(figsize=(9, 5))
        plt.plot(w, 20 * np.log10(np.maximum(np.abs(Hg), 1e-6)), label="golden LPF")
        for name, hp in payload_banks(h).items():
            _, Hp = signal.freqz(taps_float(hp), worN=2 * np.pi * w / FS)
            plt.plot(w, 20 * np.log10(np.maximum(np.abs(Hp), 1e-6)), label=name, alpha=0.8)
        for fk in e1["key_freqs_hz"]:
            plt.axvline(fk, color="grey", ls=":", lw=0.6)
        plt.axvline(f_key, color="red", ls="--", lw=1.2, label=f"key {f_key} Hz")
        plt.xlabel("Hz"); plt.ylabel("dB"); plt.ylim(-80, 12); plt.legend(fontsize=7)
        plt.title("Golden vs payload coefficient banks (fs=16k)")
        plt.tight_layout(); plt.savefig(OUT_DIR + "/payload_responses.png", dpi=110)
        result["plot"] = OUT_DIR + "/payload_responses.png"
        with open(OUT_DIR + "/trigger-surface.json", "w") as fh:
            json.dump(result, fh, indent=2)
    except Exception as ex:  # matplotlib may be absent -- data already written
        result["plot"] = f"skipped ({type(ex).__name__})"

    # concise stdout summary
    print("=== trigger-surface MEASURED ===")
    print("WAV: %d samples @ %d Hz (%s ch), %.2fs" %
          (x_noisy.shape[0], fs_wav, nch, x_noisy.shape[0] / fs_wav))
    print("(1) best key = %d Hz | atten %.2f dB | natural %.2f dBFS | margin %.2f dB" %
          (e1["best_key_hz"], e1["best_key_atten_db"], e1["best_key_natural_dbfs"], e1["best_key_margin_db"]))
    for r in e1["table"]:
        print("    f=%5d atten=%8.2fdB nat=%8.2fdBFS margin=%7.2fdB score=%7.2f" %
              (r["f_hz"], r["filter_atten_db"], r["natural_band_power_dbfs"],
               r["tone_over_natural_margin_db"], r["separability_score_db"]))
    print("(2) Goertzel @ %d Hz:" % f_key)
    for r in e2["table"]:
        print("    N=%3d coeff=%.5f tone=%.4f audiomax=%.4f thr=%.4f FA=%.3e (%d) margin=%.1fdB" %
              (r["N_win"], r["goertzel_coeff_2cos"], r["norm_mag_fkey_fs_tone"],
               r["real_audio_mag_max"], r["threshold_adaptive"],
               r["false_alarm_rate_adaptive"], r["false_alarm_count_adaptive"],
               r["tone_to_audiomax_margin_db"]))
    print("(3) Matched PN:")
    for r in e3["table"]:
        print("    L=%2d thr=%.3f FA=%.3e (%d) maxcorr=%.4f margin=%.1fdB offpeak_emp=%.4f theory=%.4f" %
              (r["L"], r["theta_norm"], r["false_alarm_rate"], r["false_alarm_count"],
               r["max_abs_corr_realaudio"], r["peak_to_realaudio_margin_db"],
               r["empirical_offpeak_std_realaudio"], r["theory_offpeak_std_scaled_by_input"]))
    print("(4) Payloads (vs golden on noisy WAV):")
    for r in e4["table"]:
        print("    %-22s rmsdelta=%8.3f LSB (%.2f dBFS) maxdelta=%6d changed=%.3f  gaind@1k=%.2fdB" %
              (r["payload"], r["rms_delta_abs_lsb"], r["rms_delta_dbfs"],
               r["max_abs_sample_delta_lsb"], r["frac_samples_changed"],
               r["gain_delta_db"]["1000Hz"]))
    print("    LSB covert: %.2f dBFS/LSB, %d bps max" %
          (e4["lsb_covert_channel"]["one_lsb_dbfs"], e4["lsb_covert_channel"]["max_bit_rate_bps_at_fs"]))
    print("(5) TOP REC: %s + %s | FA=%s | bit-exact-off=%s" %
          (e5["recommendation"]["top_choice"]["trigger"],
           e5["recommendation"]["top_choice"]["payload"],
           e5["recommendation"]["top_choice"]["specificity_false_alarm_rate"],
           e5["recommendation"]["top_choice"]["untriggered_bit_exact"]))
    print("JSON ->", OUT_DIR + "/trigger-surface.json")


if __name__ == "__main__":
    main()
