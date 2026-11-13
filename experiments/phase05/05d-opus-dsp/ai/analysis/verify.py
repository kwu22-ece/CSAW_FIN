#!/usr/bin/env python3
"""
FACET=verify  -- ADVERSARIAL independent numeric checker (CSAW 2026 Challenge 3, Phase 5).

Fresh, self-contained recomputation (does NOT import analyzers' scripts). Reads only:
  - golden/coeffs.json          (63 signed Q1.15 coefficients)
  - golden/freq_response.csv    (Phase-3 scipy freq data, for crosscheck)
  - the two WAVs                 (real-audio crosscheck)

Recomputes and compares to analyzers' claims:
  sum_h, sum_abs_h, -3 dB cutoff (freqz fs=16000), worst stopband atten above 4 kHz,
  max_abs_acc = 32767*sum_abs_h and accumulator bits, round-half-toward-+inf direction,
  and the key-frequency filter attenuations.
"""
import json, os, sys, wave
import numpy as np
from scipy import signal

BASE = "C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp"
P05  = BASE + "/experiments/phase05/05d-opus-dsp"
COEFFS_JSON = P05 + "/golden/coeffs.json"
FREQ_CSV    = P05 + "/golden/freq_response.csv"
WAV_NOISY   = BASE + "/what_a_piece_of_work-noisy.wav"
OUT_JSON    = P05 + "/reports/analysis/verify.json"

FS = 16000.0
Q  = 15          # fractional bits (Q1.15)
HALF = 1 << (Q-1)  # 2^14 = 16384 rounding add
SCALE = 1 << Q     # 2^15 = 32768

# ---------------------------------------------------------------- load coeffs
with open(COEFFS_JSON) as f:
    cj = json.load(f)
h = np.array(cj["coeffs_q15"], dtype=np.int64)
N = len(h)

# ---------------------------------------------------------------- sanity: arithmetic-shift & int16 model
# numpy >> on signed ints must be arithmetic (sign-preserving / floor)
assert (np.int64(-32768) >> 15) == -1, "numpy >> not arithmetic!"
assert (np.int64(0) >> 15) == 0

def hw_round_sat(acc):
    """y = sat16((acc + 2^14) >> 15); arithmetic shift = round half toward +inf, then int16 saturate."""
    acc = np.asarray(acc, dtype=np.int64)
    y = (acc + HALF) >> Q               # arithmetic (floor) shift == round half toward +inf
    return np.clip(y, -32768, 32767)

# ---------------------------------------------------------------- 1. sums
sum_h      = int(h.sum())
sum_abs_h  = int(np.abs(h).sum())
center_tap = int(h[N//2])
is_sym     = bool(np.array_equal(h, h[::-1]))
max_tap    = int(h.max()); min_tap = int(h.min())

# ---------------------------------------------------------------- 2. frequency response (freqz, fs=16000)
NFFT = 1 << 20                                   # ~1.05M bins -> ~0.0076 Hz resolution
w, H = signal.freqz(h.astype(np.float64), worN=NFFT, fs=FS)   # w in Hz
mag = np.abs(H)
dc  = mag[0]
mag_rel = mag / dc
mag_db  = 20.0 * np.log10(np.maximum(mag_rel, 1e-300))

def crossing(freqs, db, thr):
    """first downward crossing of threshold thr (dB), linear-interpolated."""
    below = db <= thr
    idx = np.argmax(below)          # first True
    if idx == 0 or not below[idx]:
        return None
    f0, f1 = freqs[idx-1], freqs[idx]
    d0, d1 = db[idx-1], db[idx]
    return float(f0 + (thr - d0) * (f1 - f0) / (d1 - d0))

cut_3p0103 = crossing(w, mag_db, 10*np.log10(0.5))   # half-power, -3.0103 dB
cut_3p0    = crossing(w, mag_db, -3.0)               # literal -3.0 dB
cut_6p0    = crossing(w, mag_db, -6.0)               # literal -6.0 dB
cut_6p0206 = crossing(w, mag_db, 20*np.log10(0.5))   # half-amplitude, -6.0206 dB

# worst stopband attenuation above 4 kHz (highest sidelobe => least negative dB)
mask = w > 4000.0
i_worst = np.argmax(mag_db[mask])
worst_stop_db  = float(mag_db[mask][i_worst])
worst_stop_hz  = float(w[mask][i_worst])

# ---------------------------------------------------------------- 3. accumulator sizing
max_abs_acc_32767 = 32767 * sum_abs_h            # task-specified formula
max_abs_acc_32768 = 32768 * sum_abs_h            # looser bound using |-32768|
def bits_signed(v):
    # minimal N such that signed N-bit range covers [-v, v]:  2^(N-1)-1 >= v
    n = 1
    while (1 << (n-1)) - 1 < v:
        n += 1
    return n
acc_bits_32767 = bits_signed(max_abs_acc_32767)
acc_bits_32768 = bits_signed(max_abs_acc_32768)
fits32 = bool(max_abs_acc_32767 <= (1 << 31) - 1)
log2_32767 = float(np.log2(max_abs_acc_32767))

# ---------------------------------------------------------------- 4. rounding direction (round half toward +inf)
r_m16384 = int(hw_round_sat(np.int64(-16384)))   # -0.5  -> expect 0
r_m49152 = int(hw_round_sat(np.int64(-49152)))   # -1.5  -> expect -1
r_p16384 = int(hw_round_sat(np.int64( 16384)))   # +0.5  -> expect 1
r_p49152 = int(hw_round_sat(np.int64( 49152)))   # +1.5  -> expect 2
r_m114688= int(hw_round_sat(np.int64(-114688)))  # -3.5  -> expect -3 (toward +inf)
round_ok = (r_m16384 == 0 and r_m49152 == -1 and r_p16384 == 1 and r_p49152 == 2 and r_m114688 == -3)

# exhaustive proof vs round-half-up over a dense range of acc
accs = np.arange(-200000, 200001, dtype=np.int64)
hw = (accs + HALF) >> Q
ref = np.floor(accs/ SCALE + 0.5).astype(np.int64)   # round half toward +inf
round_identity_mismatches = int(np.count_nonzero(hw != ref))

# ---------------------------------------------------------------- 5. key-frequency attenuations
key_freqs = [5500.0, 6000.0, 6500.0, 7000.0]
wk = 2*np.pi*np.array(key_freqs)/FS
_, Hk = signal.freqz(h.astype(np.float64), worN=wk)
atten = {str(int(f)): float(20*np.log10(abs(Hk[i])/dc)) for i, f in enumerate(key_freqs)}
best_key = min(atten, key=lambda k: atten[k])     # deepest (most negative) attenuation

# ---------------------------------------------------------------- 6. golden CSV crosscheck (stopband above 4 kHz)
csv = np.genfromtxt(FREQ_CSV, delimiter=",", names=True)
cf, cdb = csv["freq_hz"], csv["mag_db"]
cmask = cf > 4000.0
ci = np.argmax(cdb[cmask])
golden_worst_db = float(cdb[cmask][ci]); golden_worst_hz = float(cf[cmask][ci])
# golden 3dB crossing (half-power) from CSV
golden_cut_3p0103 = crossing(cf, cdb, 10*np.log10(0.5))

# ---------------------------------------------------------------- 7. real-audio crosscheck (noisy WAV)
with wave.open(WAV_NOISY, "rb") as wf:
    nch, sw, fr, nfr = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
    raw = wf.readframes(nfr)
x = np.frombuffer(raw, dtype="<i2").astype(np.int64)
if nch > 1:
    x = x[::nch]
acc_full = np.convolve(x, h)[:len(x)]            # acc[n] = sum_k h[k] x[n-k], zero history
y = hw_round_sat(acc_full)
rms_in  = float(np.sqrt(np.mean(x.astype(np.float64)**2)))
rms_out = float(np.sqrt(np.mean(y.astype(np.float64)**2)))
realaudio_atten_db = float(20*np.log10(rms_out/rms_in))
realaudio_sat = int(np.count_nonzero((acc_full + HALF) >> Q != y))  # clamped count
peak_acc_real = int(np.max(np.abs(acc_full)))

# ---------------------------------------------------------------- assemble
m = {
    "N": N, "is_symmetric": is_sym,
    "sum_h": sum_h, "sum_abs_h": sum_abs_h,
    "center_tap_h31": center_tap, "max_tap": max_tap, "min_tap": min_tap,
    "fs_hz": FS,
    "cutoff_3dB_Hz_halfpower_-3.0103dB": round(cut_3p0103, 4),
    "cutoff_3dB_Hz_literal_-3.0dB": round(cut_3p0, 4),
    "cutoff_6dB_Hz_literal_-6.0dB": round(cut_6p0, 4),
    "cutoff_6dB_Hz_halfamp_-6.0206dB": round(cut_6p0206, 4),
    "worst_stopband_atten_dB_above_4kHz": round(worst_stop_db, 4),
    "worst_stopband_freq_Hz": round(worst_stop_hz, 4),
    "golden_csv_worst_stopband_dB_above_4kHz": round(golden_worst_db, 4),
    "golden_csv_worst_stopband_freq_Hz": round(golden_worst_hz, 4),
    "golden_csv_cutoff_3dB_Hz_halfpower": round(golden_cut_3p0103, 4),
    "max_abs_acc_32767xsum_abs_h": max_abs_acc_32767,
    "max_abs_acc_32768xsum_abs_h": max_abs_acc_32768,
    "max_abs_acc_log2_32767": round(log2_32767, 6),
    "acc_bits_signed_from_32767": acc_bits_32767,
    "acc_bits_signed_from_32768": acc_bits_32768,
    "fits_in_32bit_signed": fits32,
    "round_neg_half_acc_-16384_y": r_m16384,
    "round_neg_1p5_acc_-49152_y": r_m49152,
    "round_pos_half_acc_16384_y": r_p16384,
    "round_pos_1p5_acc_49152_y": r_p49152,
    "round_neg_3p5_acc_-114688_y": r_m114688,
    "round_half_toward_posinf_confirmed": bool(round_ok),
    "round_identity_mismatches_vs_floor(x/D+0.5)_over_400k": round_identity_mismatches,
    "key_tone_atten_dB": atten,
    "best_key_freq_Hz": int(best_key),
    "best_key_freq_atten_dB": round(atten[best_key], 4),
    "realaudio_fs_hz": fr, "realaudio_nchannels": nch, "realaudio_n_samples": len(x),
    "realaudio_input_rms": round(rms_in, 3), "realaudio_filtered_rms": round(rms_out, 3),
    "realaudio_attenuation_db": round(realaudio_atten_db, 4),
    "realaudio_filtered_saturated_samples": realaudio_sat,
    "realaudio_peak_abs_acc": peak_acc_real,
}
os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
with open(OUT_JSON, "w") as f:
    json.dump(m, f, indent=2)

for k, v in m.items():
    print(f"{k:55s} = {v}")
print("\nwrote", OUT_JSON)
