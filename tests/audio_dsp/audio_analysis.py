"""Measure injected-noise rejection, clean-signal change, and sample agreement."""
import numpy as np
from scipy import signal

from audio_io import FULL_SCALE, RATE
from noise_generator import STOPBAND_HZ, power, snr_db

BANDS = ((0, 3000), (3000, STOPBAND_HZ), (STOPBAND_HZ, RATE / 2))


def level(samples):
    normalized = samples.astype(np.float64) / FULL_SCALE
    return {
        "samples": len(samples),
        "rms_fs": float(np.sqrt(power(normalized))),
        "peak_fs": float(np.max(np.abs(normalized))),
        "clipped_sample_count": int(np.count_nonzero((samples == -32768) | (samples == 32767))),
        "clip_count_definition": "samples at either PCM rail; may include exact rail hits",
    }


def ratio_db(numerator, denominator):
    if numerator <= 0 or denominator <= 0:
        return None
    return float(10 * np.log10(numerator / denominator))


def psd(values):
    return signal.welch(np.asarray(values, dtype=np.float64) / FULL_SCALE, fs=RATE,
                        nperseg=min(2048, len(values)), nfft=2048, detrend=False,
                        scaling="density")


def spectral_bands(frequencies, density):
    bin_width = frequencies[1] - frequencies[0]
    total = float(np.sum(density) * bin_width)
    result = {}
    for low, high in BANDS:
        inside = (frequencies >= low) & ((frequencies < high) if high < RATE / 2
                                         else (frequencies <= high))
        band = float(np.sum(density[inside]) * bin_width)
        result[f"{low:g}-{high:g}"] = {"power_fs2": band,
                                       "fraction": band / total if total else None}
    return result


def compare(hardware, software):
    if len(hardware) != len(software) or not len(software):
        raise ValueError("Hardware/software comparison requires equal nonzero lengths")
    error = hardware.astype(np.int32) - software
    different = np.flatnonzero(error)
    return {
        "samples": len(error), "mismatches": len(different), "bit_exact": not len(different),
        "first_mismatch_indices": different[:20].tolist(),
        "max_abs_error_lsb": int(np.max(np.abs(error))),
        "rms_error_lsb": float(np.sqrt(power(error))),
        "mean_signed_error_lsb": float(np.mean(error)),
        "positive_errors": int(np.count_nonzero(error > 0)),
        "negative_errors": int(np.count_nonzero(error < 0)),
        "additional_sample_shift": 0,
    }


def analyze(series, clean_filtered, group_delay):
    clean = series["clean"]
    injected = series["noise"]
    input_snr = snr_db(clean, injected)
    levels = {}
    spectra = {}
    for name, samples in series.items():
        levels[name] = level(samples)
        spectra[name] = psd(samples)
        levels[name]["welch_band_power"] = spectral_bands(*spectra[name])
    outputs = {}
    attenuation = {}
    # Exclude FIR startup from both Welch estimates when enough data remains.
    taps_minus_one = 2 * group_delay
    start = taps_minus_one if len(clean) >= taps_minus_one + 2048 else 0
    f, input_density = psd(injected[start:])
    input_bands = spectral_bands(f, input_density)
    for name in ("software", "hardware"):
        if name not in series:
            continue
        residual = series[name].astype(np.int32) - clean_filtered
        output_snr = snr_db(clean_filtered, residual)
        _, output_density = psd(residual[start:])
        output_bands = spectral_bands(f, output_density)
        band_gains = {band: ratio_db(output_bands[band]["power_fs2"], data["power_fs2"])
                      for band, data in input_bands.items()}
        attenuation[name] = (f, input_density, output_density)
        stopband_gain = band_gains[f"{STOPBAND_HZ:g}-{RATE / 2:g}"]
        outputs[name] = {
            "output_snr_db": output_snr,
            "snr_change_db": output_snr - input_snr
            if output_snr is not None and input_snr is not None else None,
            "output_residual_rms_fs": float(np.sqrt(power(residual)) / FULL_SCALE),
            "broadband_noise_gain_db": ratio_db(power(residual), power(injected)),
            "noise_band_gain_db": band_gains,
            "stopband_noise_attenuation_db": -stopband_gain if stopband_gain is not None else None,
        }
    original = clean[:len(clean) - group_delay]
    aligned = clean_filtered[group_delay:]
    clean_change = {
        "group_delay_samples_removed_for_this_measurement": group_delay,
        "compared_samples": len(aligned),
        "rms_difference_fs": float(np.sqrt(power(aligned.astype(np.int32) - original)) / FULL_SCALE)
        if len(aligned) else None,
        "clean_filtered_level": level(clean_filtered),
    }
    return {
        "input_snr_db": input_snr, "levels": levels, "outputs": outputs,
        "clean_signal_change": clean_change,
        "welch_residual_start_sample": start,
        "output_snr_reference": "FIR(clean PCM); residual = filtered noisy PCM - FIR(clean PCM)",
        "undefined_ratio": "null for zero numerator or denominator",
    }, spectra, attenuation
