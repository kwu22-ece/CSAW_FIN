#!/usr/bin/env python3
"""
FACET = fixed-point  (CSAW 2026 Challenge 3, candidate 05d-opus-dsp)

Characterize the fixed-point numerics of the recovered 63-tap Q1.15 FIR.

Recovered arithmetic (exact, verified against the netlist):
    acc = sum_k h[k] * x[n-k]              # plain-integer MAC, zero history
    y   = sat16( (acc + 2**14) >> 15 )     # round half toward +inf, then int16 clamp

Measures, all with MEASURED numbers (no guessing):
  (1) ROUNDING    - prove  (acc+16384)>>15  ==  floor((acc+16384)/32768)
                    ==  round-half-toward-+inf(acc/32768), exhaustively over a
                    dense range + explicit +/-half cases + random; and report
                    where naive round-half-to-even would differ.
  (2) SATURATION  - max_abs_acc = 32767*sum|h|, bits needed, worst-case input,
                    whether int16 output saturates, min #samples to saturate.
  (3) HEADROOM    - spare accumulator bits / extra MAC terms under a 40-bit
                    signed accumulator.
  (4) COEFF QUANT - response change (dB @ 1 kHz) for +/-1 LSB on the center tap.

Writes:
  reports/analysis/fixed-point.json
  reports/analysis/fixed-point_rounding_diffs.csv
  reports/analysis/fixed-point_coeff_sensitivity.csv
  (PNG only if matplotlib is importable; otherwise skipped)
"""
from __future__ import annotations
import json
import math
import os
import random
from fractions import Fraction

import numpy as np

# -------------------------------------------------------------------- paths
ROOT = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
COEFFS_PATH = os.path.join(ROOT, "golden", "coeffs.json")
FREQ_CSV    = os.path.join(ROOT, "golden", "freq_response.csv")
OUT_DIR     = os.path.join(ROOT, "reports", "analysis")
OUT_JSON    = os.path.join(OUT_DIR, "fixed-point.json")
ROUND_CSV   = os.path.join(OUT_DIR, "fixed-point_rounding_diffs.csv")
SENS_CSV    = os.path.join(OUT_DIR, "fixed-point_coeff_sensitivity.csv")
SAT_CSV     = os.path.join(OUT_DIR, "fixed-point_saturation_fill.csv")
PNG_PATH    = os.path.join(OUT_DIR, "fixed-point_coeff_sensitivity.png")

os.makedirs(OUT_DIR, exist_ok=True)

# -------------------------------------------------------------- constants
FS       = 16000          # nominal audio sample rate (Hz)
Q15_ONE  = 1 << 15        # 32768  (scaling divisor / 1.0 in Q1.15)
Q15_HALF = 1 << 14        # 16384  (round-half bias 2^14)
INT16_MAX = (1 << 15) - 1 # 32767
INT16_MIN = -(1 << 15)    # -32768

# ------------------------------------------------------------------ coeffs
with open(COEFFS_PATH) as fh:
    _c = json.load(fh)
H = [int(v) for v in _c["coeffs_q15"]]
N = len(H)
CENTER = N // 2
assert N == 63 and _c.get("N", 63) == 63
SUM_H = sum(H)
SUM_ABS_H = sum(abs(v) for v in H)

# ------------------------------------------------------ arithmetic kernels
def hw_round_shift(acc: int) -> int:
    """Exactly the hardware form: (acc + 2^14) >>> 15 on a signed accumulator.
    Python's >> on ints is an arithmetic (floor) shift."""
    return (acc + Q15_HALF) >> 15

def floordiv_round(acc: int) -> int:
    """floor((acc + 2^14) / 32768) via Python floor-division."""
    return (acc + Q15_HALF) // Q15_ONE

def round_half_up_indep(acc: int) -> int:
    """INDEPENDENT round-half-toward-+inf of acc/32768, computed with exact
    rationals: floor(acc/D + 1/2). Does NOT reuse the shift, so agreement is a
    genuine cross-check of rounding direction, not a tautology."""
    return math.floor(Fraction(acc, Q15_ONE) + Fraction(1, 2))

def round_half_even(acc: int) -> int:
    """Naive round-half-to-even (banker's rounding) of acc/32768, exact ints."""
    q = acc // Q15_ONE
    r = acc - q * Q15_ONE           # remainder in [0, 32768)
    twice = 2 * r
    if twice < Q15_ONE:
        return q
    if twice > Q15_ONE:
        return q + 1
    return q if (q % 2 == 0) else q + 1   # exact half -> nearest even

def sat16(v: int) -> int:
    if v > INT16_MAX:
        return INT16_MAX
    if v < INT16_MIN:
        return INT16_MIN
    return v

def fir_raw_acc(x, h):
    """Return list of raw integer accumulators acc[n] (pre-round)."""
    Nn = len(h)
    out = []
    for n in range(len(x)):
        acc = 0
        kmax = Nn if n + 1 >= Nn else n + 1
        for k in range(kmax):
            acc += h[k] * x[n - k]
        out.append(acc)
    return out

# =====================================================================
# (1) ROUNDING
# =====================================================================
def analyze_rounding():
    D = Q15_ONE
    test_accs = []

    # dense contiguous range spanning several multiples of 32768
    DENSE_LO, DENSE_HI = -5 * D, 5 * D           # [-163840, 163840]
    dense = range(DENSE_LO, DENSE_HI + 1)

    # explicit exact +half and -half cases: m*32768 +/- 16384, m in -8..8
    explicit = []
    for m in range(-8, 9):
        explicit.append(m * D + Q15_HALF)
        explicit.append(m * D - Q15_HALF)

    # random across the full reachable accumulator magnitude
    rng = random.Random(0xC5A2026)
    MAXA = INT16_MAX * SUM_ABS_H
    rand = [rng.randint(-MAXA, MAXA) for _ in range(200000)]
    # random exact-half values too (acc = m*D + HALF for random m)
    rand_half = [rng.randint(-20000, 20000) * D + Q15_HALF for _ in range(20000)]
    rand_half += [rng.randint(-20000, 20000) * D - Q15_HALF for _ in range(20000)]

    def check_set(it):
        n_tested = 0
        n_mismatch_floordiv = 0
        n_mismatch_roundup = 0
        n_diff_even = 0
        diffs = []   # (acc, x_over_D, hw, even)
        for acc in it:
            hwv = hw_round_shift(acc)
            if floordiv_round(acc) != hwv:
                n_mismatch_floordiv += 1
            if round_half_up_indep(acc) != hwv:
                n_mismatch_roundup += 1
            ev = round_half_even(acc)
            if ev != hwv:
                n_diff_even += 1
                if len(diffs) < 200000:
                    diffs.append((acc, hwv, ev))
            n_tested += 1
        return n_tested, n_mismatch_floordiv, n_mismatch_roundup, n_diff_even, diffs

    # run all sets
    tot_tested = 0
    tot_mm_fd = 0
    tot_mm_ru = 0
    tot_diff_even = 0
    all_diffs = []
    for name, it in [("dense", dense), ("explicit", explicit),
                     ("random", rand), ("random_half", rand_half)]:
        t, fd, ru, de, diffs = check_set(it)
        tot_tested += t
        tot_mm_fd += fd
        tot_mm_ru += ru
        tot_diff_even += de
        all_diffs.extend(diffs)

    # characterize WHERE hw differs from round-half-even within the dense window
    # (these are the exact halfway points acc = m*D + HALF with m even,
    #  i.e. acc == 16384 (mod 65536)).
    dense_diffs = sorted(set(d for d in all_diffs if DENSE_LO <= d[0] <= DENSE_HI))
    negative_halfway_examples = [d for d in dense_diffs if d[0] < 0][:10]
    positive_halfway_examples = [d for d in dense_diffs if d[0] >= 0][:10]

    # verify the modular characterization on the dense window
    predicted = [a for a in range(DENSE_LO, DENSE_HI + 1) if a % (2 * D) == Q15_HALF]
    observed = sorted(d[0] for d in dense_diffs)
    modular_matches = (observed == sorted(predicted))

    # write a CSV of all distinct differing points found (dedup, sorted)
    uniq = sorted(set(all_diffs))
    with open(ROUND_CSV, "w", newline="") as f:
        f.write("acc,acc_over_32768,hw_round_half_up,round_half_even,delta\n")
        for acc, hw, ev in uniq:
            f.write("%d,%.6f,%d,%d,%d\n" % (acc, acc / D, hw, ev, hw - ev))

    return {
        "divisor_D": D,
        "round_bias_2e14": Q15_HALF,
        "num_values_tested": tot_tested,
        "dense_range": [DENSE_LO, DENSE_HI],
        "mismatch_hw_vs_floordiv": tot_mm_fd,        # expect 0
        "mismatch_hw_vs_round_half_toward_posinf": tot_mm_ru,  # expect 0
        "identity_proven": (tot_mm_fd == 0 and tot_mm_ru == 0),
        "num_points_where_round_half_even_differs": tot_diff_even,
        "num_distinct_diff_points_recorded": len(uniq),
        "diff_rule": "hw differs from round-half-even exactly when acc mod 65536 == 16384 (exact +half at even multiple)",
        "diff_modular_characterization_verified": bool(modular_matches),
        "negative_halfway_examples": [
            {"acc": a, "acc_over_D": a / D, "hw(+inf)": hw, "round_half_even": ev,
             "direction": "hw rounds UP toward +inf"} for a, hw, ev in negative_halfway_examples],
        "positive_halfway_examples": [
            {"acc": a, "acc_over_D": a / D, "hw(+inf)": hw, "round_half_even": ev}
            for a, hw, ev in positive_halfway_examples],
        "csv": os.path.basename(ROUND_CSV),
    }

# =====================================================================
# (2) SATURATION
# =====================================================================
def analyze_saturation():
    D = Q15_ONE
    max_abs_acc = INT16_MAX * SUM_ABS_H
    acc_bits_needed = math.ceil(math.log2(max_abs_acc)) + 1   # +1 for sign

    # 40-bit signed accumulator capacity
    lim40_max = (1 << 39) - 1
    lim40_min = -(1 << 39)
    fits_40 = (max_abs_acc <= lim40_max) and (-max_abs_acc >= lim40_min)

    # saturation thresholds on the raw accumulator (before clamp)
    #   positive clamp triggers when (acc+HALF)>>15 > 32767  i.e. >= 32768
    #      => acc >= 32768*D - HALF
    pos_sat_acc_min = 32768 * D - Q15_HALF        # 1073725440
    #   negative clamp triggers when (acc+HALF)>>15 < -32768  i.e. <= -32769
    #      => acc <= -32768*D - HALF - 1
    neg_sat_acc_max = -32768 * D - Q15_HALF - 1   # -1073758209

    # worst-case input x[k] = sign(h[k]) * 32767  (63 samples)
    sgn = lambda v: 1 if v > 0 else (-1 if v < 0 else 0)
    x_worst = [sgn(c) * INT16_MAX for c in H]
    n_zero_sign = sum(1 for c in H if c == 0)

    accs = fir_raw_acc(x_worst, H)
    ys = [sat16(hw_round_shift(a)) for a in accs]
    peak_acc = max(accs)
    peak_acc_idx = int(np.argmax(accs))
    y_unclamped_peak = hw_round_shift(peak_acc)
    y_peak = sat16(y_unclamped_peak)
    saturation_reachable = (y_unclamped_peak > INT16_MAX) or (y_unclamped_peak < INT16_MIN)
    # peak acc at n=62 must equal max_abs_acc by symmetry
    peak_equals_maxabs = (peak_acc == max_abs_acc)

    # minimum number of input samples to reach saturation.
    # At output index n the usable taps are h[0..min(n,N-1)] and every input
    # is free, so max|acc(n)| = 32767 * cumsum|h|[0..min(n,N-1)].
    cum = 0
    min_samples = None
    first_sat_out_idx = None
    cum_series = []
    for n in range(N):
        cum += abs(H[n])
        cum_series.append(cum)
        max_acc_n = INT16_MAX * cum
        if min_samples is None and max_acc_n >= pos_sat_acc_min:
            first_sat_out_idx = n          # 0-based output index
            min_samples = n + 1            # need x[0..n]  => n+1 samples

    # how many of the worst-case outputs actually clamp
    n_clamped = sum(1 for v in ys if v == INT16_MAX or v == INT16_MIN)
    first_clamped_worstcase = next((i for i, v in enumerate(ys)
                                    if v == INT16_MAX or v == INT16_MIN), None)

    # write saturation fill CSV
    with open(SAT_CSV, "w", newline="") as f:
        f.write("out_index,n_taps_active,cumsum_abs_h,max_abs_acc_at_n,"
                "worstcase_acc,worstcase_y,clamped\n")
        for n in range(N):
            f.write("%d,%d,%d,%d,%d,%d,%d\n" % (
                n, min(n + 1, N), cum_series[n], INT16_MAX * cum_series[n],
                accs[n], ys[n], int(ys[n] in (INT16_MAX, INT16_MIN))))

    return {
        "sum_abs_h": SUM_ABS_H,
        "sum_h": SUM_H,
        "max_abs_acc": max_abs_acc,
        "max_abs_acc_log2": math.log2(max_abs_acc),
        "accumulator_bits_needed_signed": acc_bits_needed,
        "fits_in_40bit_signed": bool(fits_40),
        "fits_in_32bit_signed": bool(max_abs_acc <= (1 << 31) - 1),
        "pos_saturation_acc_threshold": pos_sat_acc_min,
        "neg_saturation_acc_threshold": neg_sat_acc_max,
        "worstcase_input_rule": "x[k] = sign(h[k]) * 32767",
        "worstcase_n_zero_sign_taps": n_zero_sign,
        "peak_acc": peak_acc,
        "peak_acc_out_index": peak_acc_idx,
        "peak_acc_equals_max_abs_acc": bool(peak_equals_maxabs),
        "y_unclamped_at_peak": y_unclamped_peak,
        "y_clamped_at_peak": y_peak,
        "saturation_reachable": bool(saturation_reachable),
        "worstcase_num_outputs_clamped": n_clamped,
        "worstcase_first_clamped_out_index": first_clamped_worstcase,
        "min_input_samples_to_saturate": min_samples,
        "first_saturating_out_index": first_sat_out_idx,
        "note_min_samples": ("earliest output index n whose adversarial-max "
                             "|acc| = 32767*cumsum|h|[0..n] reaches the positive "
                             "clamp threshold; needs n+1 input samples"),
        "csv": os.path.basename(SAT_CSV),
    }

# =====================================================================
# (3) HEADROOM
# =====================================================================
def analyze_headroom(max_abs_acc):
    lim40_max = (1 << 39) - 1               # 549755813887
    spare_value = lim40_max - max_abs_acc   # positive headroom to 40-bit signed max
    spare_bits_int = 39 - math.ceil(math.log2(max_abs_acc))
    spare_bits_float = 39 - math.log2(max_abs_acc)

    # candidate "extra MAC term" magnitudes for a parallel trigger correlator
    full_scale_mac = INT16_MAX * INT16_MAX          # Q15 x Q15 full scale = 1073676289
    center_term    = abs(H[CENTER]) * INT16_MAX     # filter's own largest term
    avg_filter_term = max_abs_acc / N               # mean |h|*32767 term

    extra_full_scale_terms = spare_value // full_scale_mac
    extra_center_like_terms = spare_value // center_term
    extra_avg_like_terms = int(spare_value // int(avg_filter_term))

    # how many *entire extra 63-tap worst-case FIRs* fit in the headroom
    extra_full_firs = spare_value // max_abs_acc

    return {
        "acc_40bit_signed_max": lim40_max,
        "acc_40bit_signed_min": -(1 << 39),
        "max_abs_acc": max_abs_acc,
        "spare_value_to_40bit_max": spare_value,
        "spare_bits_integer": spare_bits_int,
        "spare_bits_float": spare_bits_float,
        "full_scale_mac_term_q15xq15": full_scale_mac,
        "center_tap_term": center_term,
        "avg_filter_term": avg_filter_term,
        "extra_full_scale_mac_terms": int(extra_full_scale_terms),
        "extra_center_tap_like_terms": int(extra_center_like_terms),
        "extra_avg_filter_like_terms": int(extra_avg_like_terms),
        "extra_full_63tap_worstcase_firs": int(extra_full_firs),
    }

# =====================================================================
# (4) COEFF QUANTIZATION SENSITIVITY  (dB @ 1 kHz, +/-1 LSB center tap)
# =====================================================================
def freq_response(h, freqs_hz):
    """Normalized magnitude response |H(f)| with DC gain = sum(h)/32768.
    H(f) = (1/32768) * sum_k h[k] exp(-j 2pi f k / fs).  DC -> sum_h/32768 = 1.0."""
    k = np.arange(len(h))
    h = np.asarray(h, dtype=np.float64)
    out = []
    for f in freqs_hz:
        val = np.sum(h * np.exp(-1j * 2 * np.pi * f * k / FS)) / Q15_ONE
        out.append(val)
    return np.array(out)

def analyze_coeff_sensitivity():
    f1k = 1000.0
    H_nom = freq_response(H, [f1k])[0]
    h_plus = list(H); h_plus[CENTER] += 1
    h_minus = list(H); h_minus[CENTER] -= 1
    H_plus = freq_response(h_plus, [f1k])[0]
    H_minus = freq_response(h_minus, [f1k])[0]

    def db(x):
        return 20.0 * math.log10(abs(x))

    db_nom, db_plus, db_minus = db(H_nom), db(H_plus), db(H_minus)

    # validate against golden Phase-3 CSV at 1 kHz (grid is fs/1024 = 15.625 Hz)
    golden_1k_mag = golden_1k_db = None
    try:
        arr = np.genfromtxt(FREQ_CSV, delimiter=",", names=True)
        fcol = arr["freq_hz"]
        idx = int(np.argmin(np.abs(fcol - f1k)))
        golden_1k_freq = float(fcol[idx])
        golden_1k_mag = float(arr["mag"][idx])
        golden_1k_db = float(arr["mag_db"][idx])
    except Exception as e:  # pragma: no cover
        golden_1k_freq = None
        golden_1k_err = str(e)

    # also report the DC-gain shift from a center-tap LSB (0 dB reference drift)
    H_nom_dc = abs(freq_response(H, [0.0])[0])
    H_plus_dc = abs(freq_response(h_plus, [0.0])[0])
    dc_delta_db = 20.0 * math.log10(H_plus_dc / H_nom_dc)

    # fine-grained sensitivity CSV across the audio band for the record
    fsweep = np.linspace(0, FS / 2, 513)
    Hn = np.abs(freq_response(H, fsweep))
    Hp = np.abs(freq_response(h_plus, fsweep))
    Hm = np.abs(freq_response(h_minus, fsweep))
    with open(SENS_CSV, "w", newline="") as f:
        f.write("freq_hz,mag_nom,mag_plus1lsb,mag_minus1lsb,"
                "ddb_plus1lsb,ddb_minus1lsb\n")
        for i, fq in enumerate(fsweep):
            dnp = 20.0 * math.log10(Hp[i] / Hn[i]) if Hn[i] > 0 else float("nan")
            dnm = 20.0 * math.log10(Hm[i] / Hn[i]) if Hn[i] > 0 else float("nan")
            f.write("%.4f,%.9f,%.9f,%.9f,%.6e,%.6e\n"
                    % (fq, Hn[i], Hp[i], Hm[i], dnp, dnm))

    # optional PNG
    png_written = False
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(2, 1, figsize=(8, 6))
        ax[0].plot(fsweep, 20 * np.log10(np.maximum(Hn, 1e-12)), label="nominal")
        ax[0].set_ylabel("|H| (dB)"); ax[0].legend(); ax[0].grid(True)
        ax[0].set_title("63-tap FIR magnitude; center-tap +/-1 LSB sensitivity")
        ddbp = 20 * np.log10(np.maximum(Hp, 1e-12) / np.maximum(Hn, 1e-12))
        ddbm = 20 * np.log10(np.maximum(Hm, 1e-12) / np.maximum(Hn, 1e-12))
        ax[1].plot(fsweep, ddbp * 1e3, label="+1 LSB")
        ax[1].plot(fsweep, ddbm * 1e3, label="-1 LSB")
        ax[1].axvline(1000, color="k", ls=":", lw=0.8)
        ax[1].set_xlabel("Hz"); ax[1].set_ylabel("delta (milli-dB)")
        ax[1].legend(); ax[1].grid(True)
        fig.tight_layout(); fig.savefig(PNG_PATH, dpi=110)
        png_written = True
    except Exception:
        png_written = False

    return {
        "center_tap_index": CENTER,
        "center_tap_value": H[CENTER],
        "one_lsb_q15": 1.0 / Q15_ONE,
        "eval_freq_hz": f1k,
        "mag_nom": abs(H_nom),
        "mag_plus1lsb": abs(H_plus),
        "mag_minus1lsb": abs(H_minus),
        "db_nom_at_1k": db_nom,
        "db_plus1lsb_at_1k": db_plus,
        "db_minus1lsb_at_1k": db_minus,
        "delta_db_plus1lsb_at_1k": db_plus - db_nom,
        "delta_db_minus1lsb_at_1k": db_minus - db_nom,
        "dc_gain_delta_db_plus1lsb": dc_delta_db,
        "golden_csv_1k_freq": golden_1k_freq,
        "golden_csv_1k_mag": golden_1k_mag,
        "golden_csv_1k_db": golden_1k_db,
        "validation_mag_abs_err_vs_golden": (abs(abs(H_nom) - golden_1k_mag)
                                             if golden_1k_mag is not None else None),
        "png_written": png_written,
        "csv": os.path.basename(SENS_CSV),
    }

# =====================================================================
# main
# =====================================================================
def main():
    rounding = analyze_rounding()
    saturation = analyze_saturation()
    headroom = analyze_headroom(saturation["max_abs_acc"])
    coeff = analyze_coeff_sensitivity()

    # smallest value perturbation that is bit-observable at the output
    smallest = {
        "coeff_lsb_q15": 1,
        "coeff_lsb_value": 1.0 / Q15_ONE,
        "accumulator_lsb": 1,
        "explanation": ("A single accumulator LSB (acc += 1) flips y by 1 exactly "
                        "when acc == 16384 (mod 32768), i.e. acc sits on a rounding "
                        "boundary. A +/-1 LSB coefficient change perturbs acc by up "
                        "to +/-32767 (the input sample), so it is readily bit-"
                        "observable at boundary-crossing inputs; its steady-state "
                        "spectral footprint at 1 kHz is "
                        + "%.3e dB." % coeff["delta_db_plus1lsb_at_1k"]),
    }

    result = {
        "facet": "fixed-point",
        "candidate": "05d-opus-dsp",
        "fs_hz": FS,
        "N_taps": N,
        "center_tap": {"index": CENTER, "value": H[CENTER]},
        "sum_h": SUM_H,
        "sum_abs_h": SUM_ABS_H,
        "arithmetic": "y = sat16((sum_k h[k]*x[n-k] + 2^14) >> 15)",
        "rounding": rounding,
        "saturation": saturation,
        "headroom": headroom,
        "coeff_quantization": coeff,
        "smallest_bit_observable_perturbation": smallest,
        "trojan_implications": {
            "saturation_exploitable": (
                "Positive/negative int16 clamp IS reachable with an adversarial "
                "full-scale input (x[k]=sign(h[k])*32767); peak unclamped value "
                "%d >> 32767. Normal audio never approaches this, so saturation "
                "state is a clean, rare, attacker-forceable condition usable as a "
                "Trojan TRIGGER without altering untriggered output (clamp is part "
                "of the golden spec)." % saturation["y_unclamped_at_peak"]),
            "accumulator_headroom": (
                "Filter needs %d signed bits; a 40-bit signed accumulator leaves "
                "%d spare bits (~%d extra full-scale Q15xQ15 MAC terms, or ~%d "
                "extra taps of the center-tap magnitude). Ample room to run a "
                "parallel trigger correlator in the same datapath with no overflow "
                "and no change to the golden result."
                % (saturation["accumulator_bits_needed_signed"],
                   headroom["spare_bits_integer"],
                   headroom["extra_full_scale_mac_terms"],
                   headroom["extra_center_tap_like_terms"])),
            "smallest_bit_observable": (
                "1 accumulator LSB (or 1 Q15 coeff LSB = %.3e) is bit-observable at "
                "rounding boundaries; the round-half-toward-+inf asymmetry adds a "
                "deterministic +1 bias on exact negative half-way accs where round-"
                "half-even would go the other way, a potential fingerprint/channel."
                % (1.0 / Q15_ONE)),
        },
    }

    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)

    # ---- console summary (measured numbers) ----
    print("== FIXED-POINT FACET (measured) ==")
    print("N=%d  sum_h=%d  sum_abs_h=%d  center h[%d]=%d"
          % (N, SUM_H, SUM_ABS_H, CENTER, H[CENTER]))
    print("[rounding] tested=%d  hw==floordiv mism=%d  hw==round+inf mism=%d  proven=%s"
          % (rounding["num_values_tested"], rounding["mismatch_hw_vs_floordiv"],
             rounding["mismatch_hw_vs_round_half_toward_posinf"],
             rounding["identity_proven"]))
    print("           round-half-even differs at %d pts (modular rule verified=%s)"
          % (rounding["num_points_where_round_half_even_differs"],
             rounding["diff_modular_characterization_verified"]))
    if rounding["negative_halfway_examples"]:
        e = rounding["negative_halfway_examples"][0]
        print("           neg half example acc=%d -> hw=%d  even=%d"
              % (e["acc"], e["hw(+inf)"], e["round_half_even"]))
    print("[sat] max_abs_acc=%d  bits_needed=%d  fits40=%s  fits32=%s"
          % (saturation["max_abs_acc"], saturation["accumulator_bits_needed_signed"],
             saturation["fits_in_40bit_signed"], saturation["fits_in_32bit_signed"]))
    print("      worstcase peak_acc=%d  y_unclamped=%d  y_clamped=%d  reachable=%s"
          % (saturation["peak_acc"], saturation["y_unclamped_at_peak"],
             saturation["y_clamped_at_peak"], saturation["saturation_reachable"]))
    print("      min_input_samples_to_saturate=%s (first sat out idx=%s)"
          % (saturation["min_input_samples_to_saturate"],
             saturation["first_saturating_out_index"]))
    print("[headroom] spare_bits=%d  spare_value=%d  extra_fullscale_terms=%d"
          % (headroom["spare_bits_integer"], headroom["spare_value_to_40bit_max"],
             headroom["extra_full_scale_mac_terms"]))
    print("[coeff] 1kHz nom=%.6f (%.4f dB)  +1LSB d=%.4e dB  -1LSB d=%.4e dB"
          % (coeff["mag_nom"], coeff["db_nom_at_1k"],
             coeff["delta_db_plus1lsb_at_1k"], coeff["delta_db_minus1lsb_at_1k"]))
    print("        golden CSV @%.2fHz mag=%.6f (abs err=%.2e)"
          % (coeff["golden_csv_1k_freq"], coeff["golden_csv_1k_mag"],
             coeff["validation_mag_abs_err_vs_golden"]))
    print("JSON ->", OUT_JSON)


if __name__ == "__main__":
    main()
