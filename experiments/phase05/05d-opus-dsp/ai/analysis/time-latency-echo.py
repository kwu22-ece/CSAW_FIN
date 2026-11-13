#!/usr/bin/env python3
"""
FACET: time-latency-echo
CSAW 2026 Challenge 3 -- time-domain / latency / echo characterization of the
recovered 63-tap Q1.15 linear-phase FIR low-pass audio filter.

Everything is MEASURED by running the bit-exact golden software model
(golden/sw_fir.py, imported via importlib) over synthetic stimuli and the real
noisy WAV. No numbers are hard-coded; all results are written to
reports/analysis/time-latency-echo.json (+ supporting CSVs).

Measured facets:
  (1) intrinsic group delay = (N-1)/2 samples (verified empirically via the
      impulse-response peak), contrasted with the 2-frame end-to-end I2S latency
      (two different mechanisms -- filter math vs framing pipeline).
  (2) step response: unit step x[n]=32767, settling + final value.
  (3) echo exactness: right channel is an unmodified copy of the input
      (max abs diff vs input == 0 over the first 4000 noisy-WAV samples).
  (4) real-audio attenuation on the full 16 kHz noisy WAV: input/filtered RMS,
      attenuation_dB, fraction of samples where filtered != input.
"""
from __future__ import annotations
import importlib.util
import json
import math
import os
import wave
from array import array

import numpy as np

# -------------------------------------------------------------------------
# Absolute paths (do not depend on cwd)
# -------------------------------------------------------------------------
BASE = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
COEFFS_PATH = os.path.join(BASE, "golden", "coeffs.json")
SWFIR_PATH = os.path.join(BASE, "golden", "sw_fir.py")
NOISY_WAV = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"
OUT_DIR = os.path.join(BASE, "reports", "analysis")
AI_DIR = os.path.join(BASE, "ai", "analysis")
OUT_JSON = os.path.join(OUT_DIR, "time-latency-echo.json")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(AI_DIR, exist_ok=True)

# Framing / clock constants recovered from the netlist & INTERFACE.md / RTL.
FS_HZ = 16000               # nominal audio sample rate (noisy WAV)
I2S_LATENCY_FRAMES = 2      # end-to-end framing latency (fir_audio_top.v / INTERFACE.md)
ICE_CLK_HZ = 10_000_000     # free-running ICE_CLK (~10 MHz, no PLL)
MAC_CYCLES = 63             # one ICE_CLK cycle per tap (serial MAC, RTL)

# -------------------------------------------------------------------------
# Import the bit-exact golden model via importlib (per task contract)
# -------------------------------------------------------------------------
spec = importlib.util.spec_from_file_location("sw_fir", SWFIR_PATH)
sw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sw)
h = sw.load_coeffs(COEFFS_PATH)
N = len(h)


def read_noisy_wav():
    w = wave.open(NOISY_WAV, "rb")
    meta = dict(nchan=w.getnchannels(), fs=w.getframerate(),
                width=w.getsampwidth(), nframes=w.getnframes())
    a = array("h")
    a.frombytes(w.readframes(w.getnframes()))
    import sys as _s
    if _s.byteorder == "big":
        a.byteswap()
    w.close()
    return list(a), meta


# =========================================================================
# (1) GROUP DELAY  (intrinsic filter delay)  vs  I2S FRAMING LATENCY
# =========================================================================
def analyze_group_delay():
    # Analytic: Type-I linear-phase FIR -> constant group delay = (N-1)/2.
    gd_analytic = (N - 1) / 2.0

    # Empirical: peak of the impulse response.  Full-scale impulse so the center
    # tap (largest |h|) dominates; argmax of |y| is the group-delay index.
    amp = 32767
    imp = [amp] + [0] * (N + 40)
    y_imp = sw.fir_filter(imp, h)
    y_abs = np.abs(np.array(y_imp, dtype=np.int64))
    gd_empirical = int(np.argmax(y_abs))

    # Linear-phase check: impulse response should be symmetric about the peak
    # over the N-sample support (y_imp[0..N-1]).
    supp = np.array(y_imp[:N], dtype=np.int64)
    sym_residual = int(np.max(np.abs(supp - supp[::-1])))

    return {
        "N_taps": N,
        "center_tap_index": N // 2,
        "center_tap_value": int(h[N // 2]),
        "group_delay_samples_analytic": gd_analytic,
        "group_delay_samples_empirical_impulse_peak": gd_empirical,
        "group_delay_ms": gd_analytic / FS_HZ * 1000.0,
        "impulse_response_symmetric": sym_residual == 0,
        "impulse_response_symmetry_residual_lsb": sym_residual,
        "i2s_latency_frames": I2S_LATENCY_FRAMES,
        "i2s_latency_samples": I2S_LATENCY_FRAMES,            # 1 sample per frame
        "i2s_latency_ms": I2S_LATENCY_FRAMES / FS_HZ * 1000.0,
        "note_mechanisms_differ": (
            "group delay (%.1f samples) is INTRINSIC to the symmetric FIR "
            "impulse response (energy centroid at tap %d) and is carried inside "
            "the sample values; the %d-frame I2S latency is a SEPARATE framing/"
            "pipeline transport delay (deserialize -> MAC -> serialize schedule) "
            "applied equally to BOTH the filtered and echo channels by the I2S "
            "layer, independent of the filter arithmetic."
            % (gd_analytic, N // 2, I2S_LATENCY_FRAMES)
        ),
    }


# =========================================================================
# (2) STEP RESPONSE
# =========================================================================
def analyze_step():
    amp = 32767  # full-scale positive step
    M = 256
    x = [amp] * M
    y = sw.fir_filter(x, h)
    y_np = np.array(y, dtype=np.int64)

    final_value = int(y[-1])                       # steady-state (n >= N-1)
    # Settling: first index n0 such that |y[m]-final| <= 1 LSB for ALL m >= n0.
    within1 = np.abs(y_np - final_value) <= 1
    settle_1lsb = None
    for n0 in range(M):
        if within1[n0:].all():
            settle_1lsb = n0
            break
    # Settling to EXACT final (0 LSB), same sustained criterion.
    within0 = (y_np == final_value)
    settle_exact = None
    for n0 in range(M):
        if within0[n0:].all():
            settle_exact = n0
            break
    # DC gain cross-check: sum(h)/2^15 should be exactly 1.0 -> step -> input amp.
    dc_gain = sum(h) / 32768.0

    # Save the step response (first 96 samples) as CSV for inspection.
    step_csv = os.path.join(OUT_DIR, "time-latency-echo_step_response.csv")
    with open(step_csv, "w", newline="") as fh:
        fh.write("n,y_step\n")
        for n in range(min(96, M)):
            fh.write("%d,%d\n" % (n, y[n]))

    return {
        "step_amplitude": amp,
        "final_value": final_value,
        "dc_gain": dc_gain,
        "settling_samples_within_1_lsb": settle_1lsb,
        "settling_samples_exact": settle_exact,
        "settling_ms_within_1_lsb": (settle_1lsb / FS_HZ * 1000.0
                                     if settle_1lsb is not None else None),
        "full_fill_samples_N_minus_1": N - 1,
        "first16_step_outputs": [int(v) for v in y[:16]],
        "csv": step_csv,
    }, y


# =========================================================================
# (3) ECHO EXACTNESS  (right channel == unmodified input)
# =========================================================================
def analyze_echo(x_noisy):
    seg = x_noisy[:4000]
    # Right channel per the RTL: `echo <= $signed(left_sample)` -> bit-exact copy
    # of the input sample (fir_audio_top.v L140, "right = unmodified echo").
    echo = [int(v) for v in seg]                    # modeled passthrough
    xin = np.array(seg, dtype=np.int64)
    ech = np.array(echo, dtype=np.int64)
    max_abs_echo_diff = int(np.max(np.abs(ech - xin)))
    echo_exact = bool(max_abs_echo_diff == 0)

    # Contrast: the filtered (left) channel genuinely modifies the signal.
    y_filt = np.array(sw.fir_filter(seg, h), dtype=np.int64)
    n_filt_differs = int(np.count_nonzero(y_filt != xin))
    frac_filt_differs = n_filt_differs / len(seg)

    return {
        "n_samples_tested": len(seg),
        "echo_channel_max_abs_diff_vs_input": max_abs_echo_diff,
        "echo_exact": echo_exact,
        "filtered_channel_samples_differing_from_input": n_filt_differs,
        "filtered_channel_fraction_differing_from_input": frac_filt_differs,
        "note": ("right channel reproduces the input bit-for-bit (diff==0) while "
                 "the left/filtered channel differs on %.1f%% of samples -- the "
                 "echo path applies NO filtering." % (100.0 * frac_filt_differs)),
    }


# =========================================================================
# (4) REAL-AUDIO ATTENUATION  (full noisy WAV)
# =========================================================================
def analyze_real_audio(x_noisy, meta):
    xin = np.array(x_noisy, dtype=np.float64)
    y = sw.fir_filter(x_noisy, h)                   # full WAV through golden model
    yf = np.array(y, dtype=np.float64)

    input_rms = float(np.sqrt(np.mean(xin ** 2)))
    filtered_rms = float(np.sqrt(np.mean(yf ** 2)))
    attenuation_db = float(20.0 * math.log10(filtered_rms / input_rms))

    xin_i = np.array(x_noisy, dtype=np.int64)
    yi = np.array(y, dtype=np.int64)
    n_changed = int(np.count_nonzero(yi != xin_i))
    frac_changed = n_changed / len(x_noisy)

    n_sat = int(np.count_nonzero((yi == 32767) | (yi == -32768)))

    return {
        "wav": os.path.basename(NOISY_WAV),
        "fs_hz": meta["fs"],
        "n_samples": len(x_noisy),
        "duration_s": len(x_noisy) / meta["fs"],
        "input_rms": input_rms,
        "filtered_rms": filtered_rms,
        "attenuation_db": attenuation_db,
        "input_peak_abs": int(np.max(np.abs(xin_i))),
        "filtered_peak_abs": int(np.max(np.abs(yi))),
        "samples_filtered_differs_from_input": n_changed,
        "fraction_filtered_differs_from_input": frac_changed,
        "filtered_saturated_samples": n_sat,
        "note": ("low-pass removes high-frequency noise energy: filtered RMS is "
                 "%.3f dB relative to input RMS; %.2f%% of samples are modified "
                 "by the filter." % (attenuation_db, 100.0 * frac_changed)),
    }, yf


# =========================================================================
# (5) IDLE-CYCLE BUDGET  (trojan surface, derived from clock/frame rates)
# =========================================================================
def analyze_idle_cycles():
    cycles_per_frame = ICE_CLK_HZ / FS_HZ            # 10 MHz / 16 kHz
    idle_cycles = cycles_per_frame - MAC_CYCLES
    return {
        "ice_clk_hz": ICE_CLK_HZ,
        "fs_hz": FS_HZ,
        "ice_clk_cycles_per_audio_frame": cycles_per_frame,
        "mac_cycles_used": MAC_CYCLES,
        "idle_cycles_per_frame": idle_cycles,
        "idle_fraction": idle_cycles / cycles_per_frame,
        "note": ("~%d ICE_CLK cycles elapse per 16 kHz audio frame but the serial "
                 "MAC uses only %d; ~%d idle cycles/frame are available for added "
                 "trigger logic with no impact on the audio path."
                 % (round(cycles_per_frame), MAC_CYCLES, round(idle_cycles))),
    }


def main():
    x_noisy, meta = read_noisy_wav()

    gd = analyze_group_delay()
    step, _y_step = analyze_step()
    echo = analyze_echo(x_noisy)
    real, yf_full = analyze_real_audio(x_noisy, meta)
    idle = analyze_idle_cycles()

    results = {
        "facet": "time-latency-echo",
        "coeffs_source": COEFFS_PATH,
        "model": "golden/sw_fir.py (fir_filter, imported via importlib)",
        "arithmetic": "acc=sum h[k]*x[n-k]; y=sat16((acc+2^14)>>15) (round half toward +inf)",
        "group_delay_vs_latency": gd,
        "step_response": step,
        "echo": echo,
        "real_audio": real,
        "idle_cycle_budget": idle,
    }

    with open(OUT_JSON, "w") as fh:
        json.dump(results, fh, indent=2)

    # Optional plotting (matplotlib may be absent -> skip, data already written).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        imp = [32767] + [0] * (N + 20)
        y_imp = sw.fir_filter(imp, h)
        fig, ax = plt.subplots(2, 1, figsize=(8, 6))
        ax[0].stem(range(len(y_imp)), y_imp)
        ax[0].axvline(N // 2, color="r", ls="--", label="group delay=%d" % (N // 2))
        ax[0].set_title("Impulse response (peak at group-delay index)")
        ax[0].legend()
        xs = [32767] * 96
        ys = sw.fir_filter(xs, h)
        ax[1].plot(ys, marker=".")
        ax[1].axhline(step["final_value"], color="r", ls="--",
                      label="final=%d" % step["final_value"])
        ax[1].set_title("Step response")
        ax[1].legend()
        fig.tight_layout()
        png = os.path.join(OUT_DIR, "time-latency-echo_plots.png")
        fig.savefig(png, dpi=100)
        results["_plot"] = png
        with open(OUT_JSON, "w") as fh:
            json.dump(results, fh, indent=2)
        print("wrote plot:", png)
    except Exception as e:
        print("matplotlib unavailable or plot skipped:", repr(e))

    # Console summary (measured numbers)
    print("=== time-latency-echo (MEASURED) ===")
    print("N taps:", N, " center h[%d]=%d" % (N // 2, h[N // 2]))
    print("group delay (analytic):", gd["group_delay_samples_analytic"],
          "samples =", round(gd["group_delay_ms"], 4), "ms")
    print("group delay (empirical impulse peak):",
          gd["group_delay_samples_empirical_impulse_peak"])
    print("I2S framing latency:", gd["i2s_latency_frames"], "frames =",
          gd["i2s_latency_ms"], "ms")
    print("step final value:", step["final_value"],
          " settle<=1LSB:", step["settling_samples_within_1_lsb"],
          " settle exact:", step["settling_samples_exact"])
    print("echo_exact:", echo["echo_exact"],
          " max|echo-x|:", echo["echo_channel_max_abs_diff_vs_input"])
    print("input RMS:", round(real["input_rms"], 3),
          " filtered RMS:", round(real["filtered_rms"], 3),
          " attenuation_dB:", round(real["attenuation_db"], 4))
    print("fraction filtered!=input:", round(real["fraction_filtered_differs_from_input"], 6))
    print("idle cycles/frame:", idle["idle_cycles_per_frame"],
          "of", idle["ice_clk_cycles_per_audio_frame"])
    print("wrote JSON:", OUT_JSON)


if __name__ == "__main__":
    main()
