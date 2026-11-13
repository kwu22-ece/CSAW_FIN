#!/usr/bin/env python3
"""CSAW 2026 Challenge 3 -- Phase 05 DSP characterization.

FACET: coeffs-impulse
Load the recovered Q1.15 FIR taps and characterize the impulse response.

The impulse response of an FIR filter IS its coefficient set: h[n] = coeffs[n].
This script loads the golden taps, measures every structural/gain property the
facet calls for, writes impulse_response.csv, and emits coeffs-impulse.json.

Run:
  python C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp/ai/analysis/coeffs-impulse.py

All inputs are read from the read-only golden/ artifacts; nothing is modified.
"""
import json
import math
import csv
import os
import sys
import importlib.util

# ---- Absolute paths (do not depend on cwd) ---------------------------------
ROOT = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
COEFFS_PATH = os.path.join(ROOT, "golden", "coeffs.json")
SW_FIR_PATH = os.path.join(ROOT, "golden", "sw_fir.py")
OUT_JSON = os.path.join(ROOT, "reports", "analysis", "coeffs-impulse.json")
OUT_CSV = os.path.join(ROOT, "reports", "analysis", "impulse_response.csv")

Q15 = 32768.0  # 2^15, the Q1.15 scale (coeff/Q15 == float gain)


def load_golden_coeffs():
    """Load taps directly from the golden JSON, and cross-check against the
    golden sw_fir.load_coeffs() loader so we are provably using the same data
    path the bit-exact software model uses."""
    with open(COEFFS_PATH) as f:
        meta = json.load(f)
    coeffs = meta["coeffs_q15"]

    # Cross-check via the golden loader (fidelity guarantee).
    spec = importlib.util.spec_from_file_location("sw_fir_golden", SW_FIR_PATH)
    sw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sw)
    coeffs_via_loader = sw.load_coeffs(COEFFS_PATH)
    assert coeffs_via_loader == coeffs, "golden loader disagreement!"

    return coeffs, meta


def classify_linear_phase_type(h):
    """Type I/II/III/IV per the standard linear-phase FIR taxonomy.

    symmetry  x  N parity  -> type
    symmetric  + N odd       Type I
    symmetric  + N even      Type II
    antisym    + N odd       Type III
    antisym    + N even      Type IV
    """
    N = len(h)
    is_sym = all(h[k] == h[N - 1 - k] for k in range(N))
    is_antisym = all(h[k] == -h[N - 1 - k] for k in range(N))
    n_odd = (N % 2 == 1)
    if is_sym and n_odd:
        t = "Type I"
    elif is_sym and not n_odd:
        t = "Type II"
    elif is_antisym and n_odd:
        t = "Type III"
    elif is_antisym and not n_odd:
        t = "Type IV"
    else:
        t = "none (not linear phase)"
    return t, is_sym, is_antisym


def to_db(ratio):
    if ratio == 0:
        return float("-inf")
    return 20.0 * math.log10(abs(ratio))


def main():
    h, meta = load_golden_coeffs()
    N = len(h)

    # ---- Structural symmetry -----------------------------------------------
    ftype, is_symmetric, is_antisymmetric = classify_linear_phase_type(h)

    # Per-element symmetry defects (which taps, if any, break h[k]==h[N-1-k]).
    asymmetry_defects = [
        {"k": k, "h_k": h[k], "h_mirror": h[N - 1 - k], "diff": h[k] - h[N - 1 - k]}
        for k in range(N // 2)
        if h[k] != h[N - 1 - k]
    ]
    max_abs_asymmetry = max((abs(d["diff"]) for d in asymmetry_defects), default=0)

    # ---- Gains --------------------------------------------------------------
    sum_h = sum(h)                       # H(e^j0) numerator == DC gain * Q15
    sum_abs_h = sum(abs(v) for v in h)   # L1 norm -> accumulator bound
    center_tap = h[31]
    max_tap = max(h)
    min_tap = min(h)
    max_tap_index = h.index(max_tap)
    min_tap_index = h.index(min_tap)

    dc_gain_linear = sum_h / Q15
    dc_gain_dB = to_db(dc_gain_linear)

    # Nyquist (f = fs/2) gain: H(e^{j*pi}) = sum_k (-1)^k h[k]
    nyquist_gain = sum(((-1) ** k) * h[k] for k in range(N))
    nyquist_gain_linear = nyquist_gain / Q15
    nyquist_gain_dB = to_db(nyquist_gain_linear)

    # ---- Group delay / linear phase ----------------------------------------
    # For a symmetric FIR, H(e^jw) = A(w) * exp(-j w (N-1)/2) with A(w) real.
    # The phase is exactly -w*(N-1)/2 (linear), group delay constant.
    group_delay_samples = (N - 1) / 2.0
    # Nominal audio sample rate for an absolute-time reading.
    fs = 16000.0
    group_delay_seconds = group_delay_samples / fs

    # ---- Accumulator bound from L1 norm ------------------------------------
    # acc = sum_k h[k]*x[n-k]; |x| <= 32768 (int16 value -32768 has magnitude
    # 2^15). Worst-case |acc| = 32768 * sum_abs_h.
    max_input_magnitude = 32768
    max_abs_acc = max_input_magnitude * sum_abs_h
    # Signed two's-complement width that holds [-max_abs_acc, +max_abs_acc].
    acc_bits_signed = max_abs_acc.bit_length() + 1  # +1 sign bit

    # Center-tap dominance (trojan-relevant: how much of the DC gain is h[31]).
    center_tap_fraction_of_q15 = center_tap / Q15      # h[31]/32768
    center_tap_fraction_of_sum_h = center_tap / sum_h  # share of DC gain
    center_tap_fraction_of_sum_abs = center_tap / sum_abs_h

    # ---- impulse_response.csv ----------------------------------------------
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "h_q15", "h_float"])
        for n in range(N):
            w.writerow([n, h[n], f"{h[n] / Q15:.10f}"])

    # ---- Optional plot (matplotlib may be absent) --------------------------
    plot_path = None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.stem(range(N), h)
        ax.axvline(group_delay_samples, color="r", ls="--", lw=0.8,
                   label=f"center / group delay = {group_delay_samples:g}")
        ax.set_title("Recovered 63-tap FIR impulse response (Q1.15)")
        ax.set_xlabel("tap index n")
        ax.set_ylabel("h[n] (Q1.15 int)")
        ax.legend()
        fig.tight_layout()
        plot_path = os.path.join(ROOT, "reports", "analysis", "impulse_response.png")
        fig.savefig(plot_path, dpi=110)
        plt.close(fig)
    except Exception as e:  # matplotlib missing or headless failure -> skip
        plot_path = None
        sys.stderr.write(f"[info] plot skipped: {e}\n")

    # ---- Results ------------------------------------------------------------
    results = {
        "facet": "coeffs-impulse",
        "source_coeffs": COEFFS_PATH,
        "N": N,
        "is_symmetric": is_symmetric,
        "is_antisymmetric": is_antisymmetric,
        "symmetry_defects": asymmetry_defects,
        "max_abs_asymmetry": max_abs_asymmetry,
        "sum_h": sum_h,
        "center_tap": center_tap,
        "max_tap": max_tap,
        "max_tap_index": max_tap_index,
        "min_tap": min_tap,
        "min_tap_index": min_tap_index,
        "sum_abs_h": sum_abs_h,
        "dc_gain_linear": dc_gain_linear,
        "dc_gain_dB": dc_gain_dB,
        "nyquist_gain": nyquist_gain,
        "nyquist_gain_linear": nyquist_gain_linear,
        "nyquist_gain_dB": nyquist_gain_dB,
        "group_delay_samples": group_delay_samples,
        "group_delay_seconds_at_fs16000": group_delay_seconds,
        "fs_hz": fs,
        "filter_type": ftype,
        "linear_phase": is_symmetric or is_antisymmetric,
        "max_input_magnitude": max_input_magnitude,
        "max_abs_acc": max_abs_acc,
        "acc_bits_signed": acc_bits_signed,
        "center_tap_fraction_of_q15": center_tap_fraction_of_q15,
        "center_tap_fraction_of_sum_h": center_tap_fraction_of_sum_h,
        "center_tap_fraction_of_sum_abs_h": center_tap_fraction_of_sum_abs,
        "golden_meta": {
            "symmetric": meta.get("symmetric"),
            "sum_q15": meta.get("sum_q15"),
            "LAT": meta.get("LAT"),
            "msb_first": meta.get("msb_first"),
            "boff": meta.get("boff"),
        },
        "outputs": {
            "impulse_response_csv": OUT_CSV,
            "impulse_response_png": plot_path,
        },
        "notes": {
            "impulse_response": "For an FIR, the impulse response equals the "
                "coefficient vector h[n]; impulse_response.csv lists it directly.",
            "linear_phase_proof": "h symmetric (h[k]=h[N-1-k]) => "
                "H(e^jw)=A(w)*exp(-j w (N-1)/2) with A(w) real, so phase = "
                "-w*(N-1)/2 is exactly linear and group delay = (N-1)/2 is "
                "constant at all frequencies.",
            "accumulator_bound": "|acc| <= 32768 * sum_abs_h; a signed "
                f"{acc_bits_signed}-bit accumulator holds the worst case with "
                "no overflow.",
        },
    }

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)

    # ---- Console summary ----------------------------------------------------
    print("=== coeffs-impulse ===")
    print(f"N                     = {N}")
    print(f"is_symmetric          = {is_symmetric}")
    print(f"filter_type           = {ftype}")
    print(f"sum_h                 = {sum_h}")
    print(f"center_tap h[31]      = {center_tap}")
    print(f"max_tap               = {max_tap} @ index {max_tap_index}")
    print(f"min_tap               = {min_tap} @ index {min_tap_index}")
    print(f"sum_abs_h             = {sum_abs_h}")
    print(f"dc_gain_dB            = {dc_gain_dB:.6f} dB (linear {dc_gain_linear:.8f})")
    print(f"nyquist_gain          = {nyquist_gain}  ({nyquist_gain_dB:.4f} dB)")
    print(f"group_delay_samples   = {group_delay_samples:g}  ({group_delay_seconds*1000:.4f} ms @ {fs:g} Hz)")
    print(f"max_abs_acc           = {max_abs_acc}  -> signed {acc_bits_signed}-bit acc")
    print(f"center_tap/32768      = {center_tap_fraction_of_q15:.6f}")
    print(f"center_tap/sum_h      = {center_tap_fraction_of_sum_h:.6f}")
    print(f"wrote JSON            = {OUT_JSON}")
    print(f"wrote CSV             = {OUT_CSV}")
    print(f"wrote PNG             = {plot_path}")


if __name__ == "__main__":
    main()
