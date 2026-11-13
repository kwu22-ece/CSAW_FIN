#!/usr/bin/env python3
"""CSAW 2026 Challenge 3 -- Phase 05 DSP characterization.

FACET = freq-response.

Characterizes the recovered 63-tap linear-phase Q1.15 FIR low-pass filter in the
frequency domain using scipy.signal.freqz / group_delay on h_float = h/32768.

All reported numbers are MEASURED by running this script (no hand-guessed values).

Outputs (absolute paths):
  reports/analysis/freq-response.json       numeric results
  reports/analysis/freq_response_05d.csv    Hz,mag_dB,phase_rad,group_delay_samples
  reports/analysis/freq_response.png        magnitude+phase plot (skipped if no matplotlib)

Golden artifacts are READ ONLY.
"""
import json
import os
import numpy as np
import scipy.signal as ss
from scipy.optimize import brentq

# ---------------------------------------------------------------- paths
BASE = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
COEFFS = BASE + "/golden/coeffs.json"
GOLDEN_FREQ = BASE + "/golden/freq_response.csv"
OUT_JSON = BASE + "/reports/analysis/freq-response.json"
OUT_CSV = BASE + "/reports/analysis/freq_response_05d.csv"
OUT_PNG = BASE + "/reports/analysis/freq_response.png"

FS = 16000.0          # nominal audio sample rate (Hz)
WORN = 16384          # analysis grid points 0..fs/2 (>= 8192 required)

# ---------------------------------------------------------------- load coeffs
with open(COEFFS) as f:
    meta = json.load(f)
h_int = np.array(meta["coeffs_q15"], dtype=np.int64)
N = len(h_int)
M = (N - 1) / 2.0                       # ideal group delay (samples)
h_float = h_int.astype(np.float64) / 32768.0

# symmetry check (exact linear phase requires h[k] == h[N-1-k])
sym_err = int(np.max(np.abs(h_int - h_int[::-1])))
is_symmetric = (sym_err == 0)
coeff_sum_q15 = int(h_int.sum())
dc_gain_linear = float(h_float.sum())

# ---------------------------------------------------------------- freqz grid
w, H = ss.freqz(h_float, worN=WORN, fs=FS)      # w in Hz, 0..fs/2
mag = np.abs(H)
mag_db = 20.0 * np.log10(np.maximum(mag, 1e-18))
phase = np.unwrap(np.angle(H))

# group delay (samples). group_delay returns gd in samples when fs omitted;
# with fs given, w is in Hz and gd stays in samples.
wg, gd = ss.group_delay((h_float, [1.0]), w=WORN, fs=FS)

# ---------------------------------------------------------------- helper: mag in dB at a single frequency
def mag_db_at(fhz):
    _, Hf = ss.freqz(h_float, worN=np.array([fhz]), fs=FS)
    return 20.0 * np.log10(np.maximum(np.abs(Hf[0]), 1e-18))

# real amplitude function A(f): H(f) = A(f) * exp(-j*omega*M); A real for Type-I.
def amp_A(fhz):
    omega = 2.0 * np.pi * fhz / FS
    _, Hf = ss.freqz(h_float, worN=np.array([fhz]), fs=FS)
    return float((Hf[0] * np.exp(1j * omega * M)).real)

# ---------------------------------------------------------------- DC gain
dc_gain_dB = float(mag_db_at(0.0))

# ---------------------------------------------------------------- crossing finder (monotone rolloff region)
def find_crossing(target_db, flo, fhi):
    """Find f in [flo,fhi] where mag_db(f) == target_db (assumes single crossing)."""
    g = lambda f: mag_db_at(f) - target_db
    return float(brentq(g, flo, fhi, xtol=1e-6, rtol=1e-12))

# The magnitude is ~0 dB in passband and falls monotonically through the transition.
# Bracket the transition using the analysis grid.
cutoff_3dB_Hz = find_crossing(-3.0, 2000.0, 3800.0)
cutoff_6dB_Hz = find_crossing(-6.0, 2000.0, 3800.0)
minus40_Hz = find_crossing(-40.0, cutoff_3dB_Hz, 3900.0)
transition_width_Hz = minus40_Hz - cutoff_3dB_Hz

# ---------------------------------------------------------------- passband ripple
# The flat passband oscillates (ripple ~ +-0.015 dB) and then rolls off MONOTONICALLY.
# Taking max|mag_db| up to the -3 dB point would be dominated by the rolloff shoulder
# (the instruction's literal reading), which is NOT ripple. The true passband ripple is
# the oscillation amplitude in the flat region, i.e. max|mag_db| up to the LAST local
# maximum of |H| before the sustained rolloff. Stopband/rolloff produce no local maxima
# above -0.5 dB, so filtering local maxima to mag_db > -0.5 cleanly isolates ripple peaks.
dmag = np.diff(mag)
locmax = np.where((dmag[:-1] > 0) & (dmag[1:] <= 0))[0] + 1      # indices of local maxima
pb_peaks = locmax[mag_db[locmax] > -0.5]
f_onset = float(w[pb_peaks[-1]])                                 # last ripple peak = passband edge
pb_mask = w <= f_onset
passband_ripple_dB = float(np.max(np.abs(mag_db[pb_mask])))
passband_ripple_pp_dB = float(np.max(mag_db[pb_mask]) - np.min(mag_db[pb_mask]))
passband_max_dB = float(np.max(mag_db[pb_mask]))
passband_min_dB = float(np.min(mag_db[pb_mask]))
# literal reading too (max deviation all the way to the -3 dB point), for transparency
pb_to_cut = w <= cutoff_3dB_Hz
passband_ripple_to_3dB_dB = float(np.max(np.abs(mag_db[pb_to_cut])))

# ---------------------------------------------------------------- first null (first zero of A(f) after passband)
# scan grid for first sign change of A(f) above the cutoff, then refine with brentq.
scan_f = np.linspace(cutoff_3dB_Hz, 4200.0, 4000)
A_scan = np.array([amp_A(f) for f in scan_f])
first_null_Hz = None
for i in range(len(scan_f) - 1):
    if A_scan[i] == 0.0:
        first_null_Hz = float(scan_f[i]); break
    if A_scan[i] * A_scan[i + 1] < 0.0:
        first_null_Hz = float(brentq(amp_A, scan_f[i], scan_f[i + 1], xtol=1e-6, rtol=1e-12)); break

# ---------------------------------------------------------------- stopband: worst (least-attenuated) gain for f>=4000
sb_mask = w >= 4000.0
sb_f = w[sb_mask]
sb_db = mag_db[sb_mask]
# refine each local-max lobe peak for a precise worst-case using the grid argmax
k = int(np.argmax(sb_db))
# local refine around grid argmax by maximizing mag_db via dense sampling
lo = sb_f[max(k - 1, 0)]
hi = sb_f[min(k + 1, len(sb_f) - 1)]
ff = np.linspace(lo, hi, 2001)
dd = np.array([mag_db_at(x) for x in ff])
j = int(np.argmax(dd))
stopband_atten_dB = float(dd[j])
stopband_atten_freq_Hz = float(ff[j])

# ---------------------------------------------------------------- phase linearity residual
# Over the contiguous region [0, first_null) the amplitude A>0 and phase is cleanly
# linear (no pi jumps). Fit a straight line to unwrapped phase there; report max residual.
lin_mask = w < (first_null_Hz if first_null_Hz else cutoff_3dB_Hz)
wf = w[lin_mask]
pf = phase[lin_mask]
coef = np.polyfit(wf, pf, 1)                      # slope, intercept
fit = np.polyval(coef, wf)
phase_resid = pf - fit
phase_linearity_residual_rad = float(np.max(np.abs(phase_resid)))
# slope is -2*pi*M/fs rad per Hz; implied group delay = -slope*fs/(2*pi)
implied_gd_from_phase = float(-coef[0] * FS / (2.0 * np.pi))

# also residual restricted to passband [0, cutoff_3dB] (signal-energy region)
pb_lin = w < cutoff_3dB_Hz
wfb = w[pb_lin]; pfb = phase[pb_lin]
cb = np.polyfit(wfb, pfb, 1)
phase_resid_passband_rad = float(np.max(np.abs(pfb - np.polyval(cb, wfb))))

# ---------------------------------------------------------------- group delay (constant) in passband
gd_pb = gd[(wg > 10.0) & (wg < cutoff_3dB_Hz)]
group_delay_samples_median = float(np.median(gd_pb))
group_delay_samples_mean = float(np.mean(gd_pb))
group_delay_samples_std = float(np.std(gd_pb))
group_delay_ideal_samples = float(M)

# ---------------------------------------------------------------- key-tone attenuation (trojan)
key_tones = [5500.0, 6000.0, 6500.0, 7000.0]
key_tone_atten_dB = {str(int(f)): float(mag_db_at(f)) for f in key_tones}

# ---------------------------------------------------------------- cross-check vs golden csv
gold = np.genfromtxt(GOLDEN_FREQ, delimiter=",", names=True)
g_f = gold["freq_hz"]
g_db = gold["mag_db"]
# -3 dB from golden by linear interpolation on the monotone rolloff
roll = (g_f >= 2500.0) & (g_f <= 3900.0)
gf_r = g_f[roll]; gdb_r = g_db[roll]
order = np.argsort(gf_r)
gf_r = gf_r[order]; gdb_r = gdb_r[order]
# interpolate freq as function of db along monotone descending segment
desc = np.where(np.diff(gdb_r) < 0)[0]
# build monotone descending slice
seg_lo = desc[0]
seg = slice(seg_lo, len(gdb_r))
db_desc = gdb_r[seg][::-1]      # ascending in db
f_desc = gf_r[seg][::-1]
golden_cut3_Hz = float(np.interp(-3.0, db_desc, f_desc))
delta_cut3_Hz = cutoff_3dB_Hz - golden_cut3_Hz
# stopband worst from golden for f>=4000
g_sb = g_db[g_f >= 4000.0]
g_sb_f = g_f[g_f >= 4000.0]
gi = int(np.argmax(g_sb))
golden_stopband_dB = float(g_sb[gi])
golden_stopband_freq_Hz = float(g_sb_f[gi])
delta_stopband_dB = stopband_atten_dB - golden_stopband_dB

# ---------------------------------------------------------------- stealthy coefficient payload: cutoff-shift sensitivity
# Bandwidth-rescale perturbation direction (model-free, from golden h and its discrete derivative):
#   scaling the ideal response bandwidth by (1+eps) moves cutoff by ~eps*fc while PRESERVING the LPF shape.
#   d/deps { (1+eps) h((1+eps)(n-M)) }|_0  =  h[n] + (n-M)*h'[n],  h'[n] ~ central difference.
hp = np.zeros(N)
hp[1:-1] = (h_float[2:] - h_float[:-2]) / 2.0
g_dir = h_float + (np.arange(N) - M) * hp         # perturbation direction (float, Q1.15 scale after *32768)

def measure_cut3(hfl):
    gfn = lambda f: (20.0*np.log10(np.maximum(np.abs(ss.freqz(hfl, worN=np.array([f]), fs=FS)[1][0]),1e-18))) - (-3.0 - (20.0*np.log10(hfl.sum()) if hfl.sum()>0 else 0.0))
    # measure -3 dB relative to this filter's own DC gain
    dc = 20.0*np.log10(max(abs(hfl.sum()),1e-18))
    gg = lambda f: (20.0*np.log10(np.maximum(np.abs(ss.freqz(hfl, worN=np.array([f]), fs=FS)[1][0]),1e-18)) - dc) + 3.0
    return float(brentq(gg, 2000.0, 3800.0, xtol=1e-6, rtol=1e-12))

sens = []
for target_dHz in [25.0, 50.0, 100.0, 200.0]:
    eps = target_dHz / cutoff_3dB_Hz
    h_new = h_float + eps * g_dir
    h_new_q = np.round(h_new * 32768.0).astype(np.int64)        # quantize to Q1.15 (payload = integer coeffs)
    h_new_qf = h_new_q.astype(np.float64) / 32768.0
    actual_cut = measure_cut3(h_new_qf)
    dcut = actual_cut - cutoff_3dB_Hz
    lsb_delta = (h_new_q - h_int)
    sens.append({
        "target_shift_Hz": target_dHz,
        "bandwidth_scale_eps": float(eps),
        "measured_cutoff_shift_Hz": float(dcut),
        "measured_cutoff_Hz": float(actual_cut),
        "max_tap_change_LSB": int(np.max(np.abs(lsb_delta))),
        "rms_tap_change_LSB": float(np.sqrt(np.mean(lsb_delta.astype(float)**2))),
        "max_tap_change_pct_of_peak": float(100.0 * np.max(np.abs(lsb_delta)) / np.max(np.abs(h_int))),
        "num_taps_changed": int(np.count_nonzero(lsb_delta)),
    })
# slope Hz per LSB (from the smallest, most-stealthy step)
hz_per_maxLSB = sens[0]["measured_cutoff_shift_Hz"] / max(sens[0]["max_tap_change_LSB"], 1)

# ---------------------------------------------------------------- write CSV
gd_interp = np.interp(w, wg, gd)       # align gd grid to w (same WORN so identical, but safe)
with open(OUT_CSV, "w") as f:
    f.write("Hz,mag_dB,phase_rad,group_delay_samples\n")
    for i in range(len(w)):
        f.write("%.6f,%.6f,%.9f,%.6f\n" % (w[i], mag_db[i], phase[i], gd_interp[i]))

# ---------------------------------------------------------------- plot (optional)
png_written = False
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    ax[0].plot(w, mag_db, lw=1.0)
    ax[0].axhline(-3, color="r", ls="--", lw=0.7)
    ax[0].axvline(cutoff_3dB_Hz, color="r", ls=":", lw=0.7)
    ax[0].set_ylabel("Magnitude (dB)"); ax[0].set_ylim(-120, 5); ax[0].grid(True, alpha=0.3)
    ax[0].set_title("Recovered 63-tap FIR -- magnitude (fs=16000 Hz), -3dB=%.1f Hz" % cutoff_3dB_Hz)
    ax[1].plot(w, phase, lw=1.0)
    ax[1].set_ylabel("Unwrapped phase (rad)"); ax[1].set_xlabel("Frequency (Hz)"); ax[1].grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(OUT_PNG, dpi=110); plt.close(fig)
    png_written = True
except Exception as e:
    print("matplotlib unavailable or plot failed (continuing):", repr(e))

# ---------------------------------------------------------------- assemble results
results = {
    "facet": "freq-response",
    "source_coeffs": COEFFS,
    "fs_Hz": FS,
    "worN": WORN,
    "N_taps": N,
    "symmetric": bool(is_symmetric),
    "symmetry_abs_err_LSB": sym_err,
    "coeff_sum_q15": coeff_sum_q15,
    "dc_gain_linear": dc_gain_linear,
    "measurements": {
        "dc_gain_dB": dc_gain_dB,
        "cutoff_3dB_Hz": cutoff_3dB_Hz,
        "cutoff_6dB_Hz": cutoff_6dB_Hz,
        "passband_ripple_dB": passband_ripple_dB,
        "passband_ripple_pp_dB": passband_ripple_pp_dB,
        "passband_ripple_to_3dB_dB": passband_ripple_to_3dB_dB,
        "passband_max_dB": passband_max_dB,
        "passband_min_dB": passband_min_dB,
        "passband_edge_onset_Hz": f_onset,
        "first_null_Hz": first_null_Hz,
        "stopband_atten_dB": stopband_atten_dB,
        "stopband_atten_freq_Hz": stopband_atten_freq_Hz,
        "transition_width_Hz": transition_width_Hz,
        "minus40dB_Hz": minus40_Hz,
        "phase_linearity_residual_rad": phase_linearity_residual_rad,
        "phase_linearity_residual_passband_rad": phase_resid_passband_rad,
        "group_delay_samples": group_delay_samples_median,
        "group_delay_samples_mean": group_delay_samples_mean,
        "group_delay_samples_std": group_delay_samples_std,
        "group_delay_ideal_(N-1)/2": group_delay_ideal_samples,
        "implied_group_delay_from_phase_samples": implied_gd_from_phase,
    },
    "cross_check_vs_golden": {
        "golden_csv": GOLDEN_FREQ,
        "golden_cutoff_3dB_Hz_interp": golden_cut3_Hz,
        "my_cutoff_3dB_Hz": cutoff_3dB_Hz,
        "delta_cutoff_3dB_Hz": delta_cut3_Hz,
        "phase3_reported_3dB_Hz": 3296.4,
        "golden_stopband_worst_dB": golden_stopband_dB,
        "golden_stopband_worst_freq_Hz": golden_stopband_freq_Hz,
        "my_stopband_worst_dB": stopband_atten_dB,
        "my_stopband_worst_freq_Hz": stopband_atten_freq_Hz,
        "delta_stopband_dB": delta_stopband_dB,
        "note": "golden csv grid=15.625 Hz (worN=512 one-sided); my worN=16384 resolves lobe peaks finer, so small deltas expected.",
    },
    "trojan_implications": {
        "key_tone_attenuation_dB": key_tone_atten_dB,
        "cutoff_shift_sensitivity": sens,
        "hz_per_max_LSB_change": hz_per_maxLSB,
        "perturbation_model": "bandwidth-rescale direction g[n]=h[n]+(n-M)*h'[n]; preserves LPF shape, moves cutoff ~eps*fc",
    },
    "artifacts": {
        "csv": OUT_CSV,
        "png": OUT_PNG if png_written else None,
        "script": BASE + "/ai/analysis/freq-response.py",
    },
}

with open(OUT_JSON, "w") as f:
    json.dump(results, f, indent=2)

# ---------------------------------------------------------------- console summary
print("=== FREQ-RESPONSE (measured) ===")
print("symmetric:", is_symmetric, " sum_q15:", coeff_sum_q15, " dc_gain_dB:", round(dc_gain_dB, 6))
print("cutoff_3dB_Hz  :", round(cutoff_3dB_Hz, 4))
print("cutoff_6dB_Hz  :", round(cutoff_6dB_Hz, 4))
print("passband_ripple_dB:", round(passband_ripple_dB, 6), " (pp:", round(passband_ripple_pp_dB, 6), ")")
print("first_null_Hz  :", round(first_null_Hz, 4) if first_null_Hz else None)
print("stopband worst :", round(stopband_atten_dB, 4), "dB @", round(stopband_atten_freq_Hz, 2), "Hz")
print("transition_width_Hz (-3dB->-40dB):", round(transition_width_Hz, 4), " (-40dB@", round(minus40_Hz,2),")")
print("phase residual (0..first_null) rad:", phase_linearity_residual_rad)
print("phase residual (passband) rad     :", phase_resid_passband_rad)
print("group_delay samples (median/mean/std):", round(group_delay_samples_median,6),
      round(group_delay_samples_mean,6), round(group_delay_samples_std,6))
print("implied gd from phase slope:", round(implied_gd_from_phase, 6), " ideal (N-1)/2:", M)
print("--- cross-check vs golden ---")
print("golden -3dB interp:", round(golden_cut3_Hz,4), " mine:", round(cutoff_3dB_Hz,4),
      " delta:", round(delta_cut3_Hz,4), "Hz")
print("golden stopband worst:", round(golden_stopband_dB,4), "@", round(golden_stopband_freq_Hz,2),
      " mine:", round(stopband_atten_dB,4), "@", round(stopband_atten_freq_Hz,2),
      " delta:", round(delta_stopband_dB,4), "dB")
print("--- trojan key-tone attenuation ---")
for t, v in key_tone_atten_dB.items():
    print("  ", t, "Hz:", round(v, 3), "dB")
print("--- cutoff-shift sensitivity (stealthy coeff payload) ---")
for s in sens:
    print("   target +%.0f Hz -> measured %+.2f Hz | max tap dLSB=%d (%.2f%% of peak), rms=%.1f LSB, taps changed=%d"
          % (s["target_shift_Hz"], s["measured_cutoff_shift_Hz"], s["max_tap_change_LSB"],
             s["max_tap_change_pct_of_peak"], s["rms_tap_change_LSB"], s["num_taps_changed"]))
print("wrote:", OUT_JSON)
print("wrote:", OUT_CSV)
print("wrote png:", png_written)
