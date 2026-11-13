#!/usr/bin/env python3
"""INDEPENDENT verification of candidate-05d armed payload.  KEY = verify_payload

Claim under test: "The armed payload is an exact spectral inversion that stays
numerically safe."

This script is written from scratch (it does NOT re-run the author's analysis
scripts). It only *loads* the golden Q1.15 coefficients and, for one tie-out,
imports golden/sw_fir.py (the golden reference model) to confirm my own
bit-exact FIR arithmetic matches the golden datapath.

Three things are checked, all from MEASURED numbers:

(1) SPECTRAL INVERSION  -- build h'[k] = (-1)^k h[k]; via scipy.signal.freqz
    report armed DC/Nyquist gain and armed gain at 250/500/1000/2000/3000 Hz vs
    golden, and confirm the exact identity  H'(w) = conj(H(pi - w))  (i.e. the
    armed response is the golden response shifted by fs/2) to within float error.

(2) LINEAR PHASE  -- confirm h' is still symmetric (=> exactly linear phase);
    report group delay for golden and armed.

(3) NUMERICS  -- confirm sum|h'| == sum|h| (accumulator bound unchanged); compute
    the worst-case |acc| for h' and confirm it still fits the signed 40-bit
    accumulator; and prove that h''s (armed) saturation can never corrupt a
    DISARMED output sample (per-sample coefficient select, accumulator reset per
    sample, so disarmed samples are bit-identical to golden regardless of what an
    adjacent armed sample does, even when the armed sample saturates and the
    disarmed one does not).
"""
from __future__ import annotations
import json, os, sys, random
import numpy as np
from scipy import signal
from scipy.io import wavfile

BASE   = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
COEFFS = os.path.join(BASE, "golden", "coeffs.json")
WAV    = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"
OUT    = os.path.join(BASE, "reports", "analysis", "verify_payload.json")

FS         = 16000
Q15        = 32768.0
INT16_MAX  = 32767
INT16_MIN  = -32768
MAXMAG     = 32768          # max |int16| magnitude (from -32768)
ACC_MAX    = (1 << 39) - 1  # signed 40-bit accumulator
ACC_MIN    = -(1 << 39)

# ---------------------------------------------------------------- load coeffs
with open(COEFFS) as f:
    h = [int(v) for v in json.load(f)["coeffs_q15"]]
N  = len(h)
hp = [((-1) ** k) * h[k] for k in range(N)]       # armed payload h'[k] = (-1)^k h[k]

R: dict = {"key": "verify_payload", "N": N, "fs_hz": FS}
R["coeffs_sum"]            = sum(h)
R["coeffs_sum_is_32768"]   = (sum(h) == 32768)
R["hp_alternating_sum"]    = sum(hp)   # == golden Nyquist numerator == armed DC numerator

# ============================================================ (1) freqz / inversion
def Hc(coeffs, w_rad):
    _, H = signal.freqz(np.asarray(coeffs, float) / Q15, worN=np.asarray(w_rad, float))
    return H

def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-300))

freqs = [0.0, 250.0, 500.0, 1000.0, 2000.0, 3000.0, FS / 2.0]
w_t   = [2 * np.pi * f / FS for f in freqs]
Hg, Hp = Hc(h, w_t), Hc(hp, w_t)

R["gains_vs_freq"] = {
    f"{f:.0f}Hz": {"golden_db": float(db(g)), "armed_db": float(db(p)),
                   "golden_mag": float(abs(g)), "armed_mag": float(abs(p))}
    for f, g, p in zip(freqs, Hg, Hp)
}
R["golden_dc_gain_db"]      = float(db(Hg[0]))
R["golden_nyquist_gain_db"] = float(db(Hg[-1]))
R["armed_dc_gain_db"]       = float(db(Hp[0]))
R["armed_nyquist_gain_db"]  = float(db(Hp[-1]))
# cross check: armed DC magnitude must equal golden Nyquist magnitude (spectral swap)
R["armed_dc_eq_golden_nyquist_err"]      = float(abs(abs(Hp[0]) - abs(Hg[-1])))
R["armed_nyquist_eq_golden_dc_err"]      = float(abs(abs(Hp[-1]) - abs(Hg[0])))

# exact inversion identity over a dense grid:  H'(w) == conj(H(pi - w))
Npts   = 8193
w      = np.linspace(0.0, np.pi, Npts)
Hp_g   = Hc(hp, w)
Hg_f   = Hc(h, np.pi - w)
R["inversion_identity"] = {
    "grid_points": Npts,
    "max_abs_magnitude_error":          float(np.max(np.abs(np.abs(Hp_g) - np.abs(Hg_f)))),
    "max_abs_complex_error_vs_conjflip": float(np.max(np.abs(Hp_g - np.conj(Hg_f)))),
}

# ============================================================ (2) symmetry / linear phase
R["golden_symmetric"] = (h == h[::-1])
R["armed_symmetric"]  = (hp == hp[::-1])
R["theoretical_group_delay_samples"] = (N - 1) / 2.0

def gd(coeffs, band):
    _, g = signal.group_delay((np.asarray(coeffs, float), 1), w=2 * np.pi * np.asarray(band, float) / FS)
    return g

gd_g = gd(h,  np.arange(50.0, 3000.0, 10.0))     # golden passband (well conditioned)
gd_p = gd(hp, np.arange(5100.0, 7900.0, 10.0))   # armed passband (high, well conditioned)
R["golden_group_delay_median"] = float(np.median(gd_g))
R["golden_group_delay_maxdev"] = float(np.max(np.abs(gd_g - (N - 1) / 2.0)))
R["armed_group_delay_median"]  = float(np.median(gd_p))
R["armed_group_delay_maxdev"]  = float(np.max(np.abs(gd_p - (N - 1) / 2.0)))

# ============================================================ (3) numerics
sum_abs_h  = sum(abs(v) for v in h)
sum_abs_hp = sum(abs(v) for v in hp)
R["sum_abs_h"]      = sum_abs_h
R["sum_abs_hp"]     = sum_abs_hp
R["sum_abs_equal"]  = (sum_abs_h == sum_abs_hp)

def worst_acc(coeffs):
    mx = sum((INT16_MAX * c if c > 0 else INT16_MIN * c) for c in coeffs)
    mn = sum((INT16_MIN * c if c > 0 else INT16_MAX * c) for c in coeffs)
    return mx, mn

mx_h, mn_h = worst_acc(h)
mx_p, mn_p = worst_acc(hp)
bound = sum_abs_h * MAXMAG
R["acc_sumabs_bound"]     = bound
R["worst_case_acc_h"]     = {"max": mx_h, "min": mn_h}
R["worst_case_acc_hp"]    = {"max": mx_p, "min": mn_p}
R["acc_40bit_range"]      = {"min": ACC_MIN, "max": ACC_MAX}
R["h_fits_40bit"]         = (ACC_MIN <= mn_h and mx_h <= ACC_MAX)
R["hp_fits_40bit"]        = (ACC_MIN <= mn_p and mx_p <= ACC_MAX)
R["hp_peak_abs_acc"]      = max(abs(mx_p), abs(mn_p))
R["hp_margin_factor_to_2^39"] = float((1 << 39) / max(abs(mx_p), abs(mn_p)))

# ---- my own bit-exact FIR with per-sample arm select (mirrors ref_trojan datapath) ----
def sat16(v):
    return INT16_MAX if v > INT16_MAX else INT16_MIN if v < INT16_MIN else v

def fir_sel(x, hco, arm):
    """coef[k] for sample n = -h[k] if (arm[n] and k odd) else h[k]."""
    M = len(x); y = [0] * M
    for n in range(M):
        acc = 0; an = arm[n]
        for k in range(min(n + 1, N)):
            c = -hco[k] if (an and (k & 1)) else hco[k]
            acc += c * x[n - k]
        y[n] = sat16((acc + (1 << 14)) >> 15)
    return y

def fir_direct(x, coeffs):
    M = len(x); y = [0] * M
    for n in range(M):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += coeffs[k] * x[n - k]
        y[n] = sat16((acc + (1 << 14)) >> 15)
    return y

def n_sat(x, coeffs):
    c = 0
    for n in range(len(x)):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += coeffs[k] * x[n - k]
        r = (acc + (1 << 14)) >> 15
        if r > INT16_MAX or r < INT16_MIN:
            c += 1
    return c

# tie-out: my disarmed FIR == golden/sw_fir.fir_filter (bit-exact)
sys.path.insert(0, os.path.join(BASE, "golden"))
import sw_fir as GOLD
rng = random.Random(0xC5A2)
xr  = [rng.randint(INT16_MIN, INT16_MAX) for _ in range(800)]
g_ref   = GOLD.fir_filter(xr, h)
g_mine  = fir_sel(xr, h, [0] * len(xr))
R["golden_bitexact_tieout_vs_sw_fir"] = (g_mine == g_ref)

# armed-every-sample == direct h' filter
hp_armed  = fir_sel(xr, h, [1] * len(xr))
hp_direct = fir_direct(xr, hp)
R["armed_equals_direct_hprime"] = (hp_armed == hp_direct)

# ISOLATION: random per-sample arm schedule -> each sample must equal
#   golden[n] if disarmed else pure-h'[n], with NO cross-contamination.
sched = [rng.randint(0, 1) for _ in range(len(xr))]
mixed = fir_sel(xr, h, sched)
expect = [hp_direct[n] if sched[n] else g_ref[n] for n in range(len(xr))]
R["random_schedule_isolation_ok"] = (mixed == expect)
R["random_schedule_mismatches"]   = sum(1 for n in range(len(xr)) if mixed[n] != expect[n])

# ADVERSARIAL saturating case: near-Nyquist full-scale tone.
# Armed (high-pass) passes it and SATURATES; golden (low-pass) attenuates it and
# does NOT. Arm OFF first half, ON second half -> prove disarmed first half is
# bit-identical to golden even though the armed second half saturates.
Mn   = 700
fhi  = 7850.0
xhi  = [int(round(32767 * np.sin(2 * np.pi * fhi * i / FS))) for i in range(Mn)]
g_hi, hp_hi = fir_direct(xhi, h), fir_direct(xhi, hp)
R["nearnyq_golden_saturations"] = n_sat(xhi, h)
R["nearnyq_armed_saturations"]  = n_sat(xhi, hp)
sched2 = [0] * (Mn // 2) + [1] * (Mn - Mn // 2)
mix2   = fir_sel(xhi, h, sched2)
R["nearnyq_disarmed_firsthalf_eq_golden"] = (mix2[:Mn // 2] == g_hi[:Mn // 2])
R["nearnyq_armed_secondhalf_eq_hprime"]   = (mix2[Mn // 2:] == hp_hi[Mn // 2:])

# DELIBERATE saturation-divergence search: tile the worst-case-for-h' sign pattern
# so armed (h') outputs saturate hard; golden (h) on the same stream saturates
# differently (or not at all). Then prove: with arm forced OFF the WHOLE stream is
# bit-identical to golden (disarmed path never corrupted), with arm forced ON it is
# bit-identical to pure h', and a per-sample alternating mix selects correctly -- at
# EVERY index, including the ones where the two filters saturate differently.
pat = [(INT16_MAX if hp[N - 1 - j] > 0 else INT16_MIN) for j in range(N)]
xsat = (pat * 8)[:400]
g_s  = fir_direct(xsat, h)       # golden (low-pass) stream
p_s  = fir_direct(xsat, hp)      # armed  (high-pass) stream

def sat_mask(x, coeffs):
    m = []
    for n in range(len(x)):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += coeffs[k] * x[n - k]
        r = (acc + (1 << 14)) >> 15
        m.append(r > INT16_MAX or r < INT16_MIN)
    return m

mg, mp = sat_mask(xsat, h), sat_mask(xsat, hp)
diff_sat = [n for n in range(len(xsat)) if mg[n] != mp[n]]       # saturate differently
R["satsearch_len"]              = len(xsat)
R["satsearch_golden_sats"]      = int(sum(mg))
R["satsearch_armed_sats"]       = int(sum(mp))
R["satsearch_diff_sat_count"]   = len(diff_sat)
dis_off = fir_sel(xsat, h, [0] * len(xsat))
dis_on  = fir_sel(xsat, h, [1] * len(xsat))
R["satsearch_disarmed_eq_golden_everywhere"] = (dis_off == g_s)
R["satsearch_armed_eq_hprime_everywhere"]    = (dis_on == p_s)
alt = [n & 1 for n in range(len(xsat))]
mix_alt = fir_sel(xsat, h, alt)
exp_alt = [p_s[n] if alt[n] else g_s[n] for n in range(len(xsat))]
R["satsearch_alt_schedule_ok"] = (mix_alt == exp_alt)
# corruption = any disarmed sample whose value differs from golden at a differing-sat index
R["satsearch_disarmed_corrupted_at_diffsat"] = any(dis_off[n] != g_s[n] for n in diff_sat)

# constructed acc-maximizing input for h': confirm measured acc == worst_acc(hp).max,
# fits 40-bit, and (run disarmed) still equals golden exactly.
x_wc = [(INT16_MAX if hp[N - 1 - j] > 0 else INT16_MIN) for j in range(N)]
acc_wc = sum(hp[k] * x_wc[N - 1 - k] for k in range(N))
R["constructed_wc_acc_hp"]            = acc_wc
R["constructed_wc_eq_worstcase_max"]  = (acc_wc == mx_p)
R["constructed_wc_fits_40bit"]        = (ACC_MIN <= acc_wc <= ACC_MAX)
wc_dis = fir_sel(x_wc, h, [0] * N)
wc_gold = fir_direct(x_wc, h)
R["constructed_wc_disarmed_eq_golden"] = (wc_dis == wc_gold)

# real-audio tie-out (bounded): my bit-exact golden vs sw_fir on actual samples,
# and disarmed trojan == golden on real audio.
try:
    rate, data = wavfile.read(WAV)
    if data.ndim > 1:
        data = data[:, 0]
    nchk = min(3000, len(data))
    xw = [int(v) for v in data[:nchk]]
    R["wav_rate"]   = int(rate)
    R["wav_total_samples"] = int(len(data))
    R["wav_checked_samples"] = nchk
    gw_ref  = GOLD.fir_filter(xw, h)
    gw_mine = fir_sel(xw, h, [0] * nchk)
    R["wav_golden_bitexact_tieout"] = (gw_ref == gw_mine)
    R["wav_disarmed_eq_golden"]     = (fir_sel(xw, h, [0] * nchk) == gw_ref)
except Exception as e:  # pragma: no cover
    R["wav_error"] = repr(e)

# ============================================================ verdict
tol = 1e-9
exact_inversion = (
    R["inversion_identity"]["max_abs_complex_error_vs_conjflip"] < tol and
    R["inversion_identity"]["max_abs_magnitude_error"] < tol and
    R["armed_dc_eq_golden_nyquist_err"] < tol and
    R["armed_nyquist_eq_golden_dc_err"] < tol and
    all(R["gains_vs_freq"][f"{f:.0f}Hz"]["armed_db"] < -40.0 for f in (250.0, 500.0, 1000.0))
)
linear_phase = (
    R["armed_symmetric"] and R["golden_symmetric"] and
    abs(R["armed_group_delay_median"] - (N - 1) / 2.0) < 1e-6 and
    R["armed_group_delay_maxdev"] < 1e-6 and
    R["golden_group_delay_maxdev"] < 1e-6
)
bound_unchanged = (
    R["sum_abs_equal"] and R["h_fits_40bit"] and R["hp_fits_40bit"] and
    R["random_schedule_isolation_ok"] and
    R["nearnyq_disarmed_firsthalf_eq_golden"] and
    R["nearnyq_armed_secondhalf_eq_hprime"] and
    R["constructed_wc_fits_40bit"] and R["constructed_wc_disarmed_eq_golden"] and
    R["golden_bitexact_tieout_vs_sw_fir"] and R["armed_equals_direct_hprime"]
)
R["criterion_exact_spectral_inversion"] = bool(exact_inversion)
R["criterion_linear_phase_preserved"]   = bool(linear_phase)
R["criterion_bound_saturation_unchanged"] = bool(bound_unchanged)
R["confirmed"] = bool(exact_inversion and linear_phase and bound_unchanged)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(R, f, indent=2)

# human-readable summary -------------------------------------------------------
print("=== verify_payload (independent) ===")
print(f"N={N}  sum h={sum(h)} (==32768: {R['coeffs_sum_is_32768']})  "
      f"alt-sum(h')={sum(hp)}")
print("-- (1) spectral inversion --")
print(f"golden DC={R['golden_dc_gain_db']:.3f} dB   golden Nyq={R['golden_nyquist_gain_db']:.3f} dB")
print(f"armed  DC={R['armed_dc_gain_db']:.3f} dB   armed  Nyq={R['armed_nyquist_gain_db']:.3f} dB")
for f in (250.0, 500.0, 1000.0, 2000.0, 3000.0):
    gg = R["gains_vs_freq"][f"{f:.0f}Hz"]
    print(f"  {f:6.0f} Hz : golden {gg['golden_db']:8.3f} dB   armed {gg['armed_db']:9.3f} dB")
print(f"identity |.| err = {R['inversion_identity']['max_abs_magnitude_error']:.3e}   "
      f"complex err = {R['inversion_identity']['max_abs_complex_error_vs_conjflip']:.3e}")
print("-- (2) linear phase --")
print(f"symmetric: golden={R['golden_symmetric']} armed={R['armed_symmetric']}   "
      f"group delay (theory)={(N-1)/2.0}")
print(f"  golden gd median={R['golden_group_delay_median']:.6f} maxdev={R['golden_group_delay_maxdev']:.2e}")
print(f"  armed  gd median={R['armed_group_delay_median']:.6f} maxdev={R['armed_group_delay_maxdev']:.2e}")
print("-- (3) numerics --")
print(f"sum|h|={sum_abs_h}  sum|h'|={sum_abs_hp}  equal={R['sum_abs_equal']}")
print(f"worst acc h'=[{mn_p}, {mx_p}]  40-bit=[{ACC_MIN}, {ACC_MAX}]  fits={R['hp_fits_40bit']}  "
      f"margin x{R['hp_margin_factor_to_2^39']:.1f}")
print(f"tieout vs sw_fir={R['golden_bitexact_tieout_vs_sw_fir']}  "
      f"armed==direct h'={R['armed_equals_direct_hprime']}")
print(f"random-schedule isolation ok={R['random_schedule_isolation_ok']} "
      f"(mismatches={R['random_schedule_mismatches']})")
print(f"near-Nyquist: golden sats={R['nearnyq_golden_saturations']} armed sats={R['nearnyq_armed_saturations']}  "
      f"disarmed-half==golden={R['nearnyq_disarmed_firsthalf_eq_golden']}  "
      f"armed-half==h'={R['nearnyq_armed_secondhalf_eq_hprime']}")
print(f"wav tieout={R.get('wav_golden_bitexact_tieout')} disarmed==golden={R.get('wav_disarmed_eq_golden')}")
print("-- verdict --")
print(f"exact_inversion={R['criterion_exact_spectral_inversion']}  "
      f"linear_phase={R['criterion_linear_phase_preserved']}  "
      f"bound_unchanged={R['criterion_bound_saturation_unchanged']}")
print(f"CONFIRMED={R['confirmed']}")
print(f"wrote {OUT}")
