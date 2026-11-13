"""Generate deterministic interference and normalize its RMS before mixing."""
from dataclasses import dataclass

import numpy as np
from scipy import signal

from audio_io import FULL_SCALE, HEADROOM, RATE, pcm16

KINDS = ("white", "pink", "highfreq", "multitone", "bandlimited")
STOPBAND_HZ = 4000  # Phase 3 baseline measurement boundary
DEFAULT_SEED = 2026
SILENCE_NOISE_RMS_FS = 0.01


@dataclass(frozen=True)
class Noise:
    kind: str
    snr_db: float | None
    seed: int
    frequencies: tuple[float, ...] = ()
    band: tuple[float, float] | None = None
    amplitude: float | None = None


def power(values):
    values = np.asarray(values, dtype=np.float64)
    return float(np.mean(values ** 2))


def snr_db(desired, error):
    numerator, denominator = power(desired), power(error)
    if numerator == 0 or denominator == 0:
        return None
    return float(10 * np.log10(numerator / denominator))


def verify_stopband(taps):
    frequencies, response = signal.freqz(np.asarray(taps) / FULL_SCALE, worN=32769,
                                        fs=RATE, include_nyquist=True)
    worst_db = float(20 * np.log10(np.max(np.abs(response[frequencies >= STOPBAND_HZ]))))
    if worst_db > -50:
        raise ValueError("Verified Phase 3 stopband does not match the loaded coefficients")
    return worst_db


def generate(clean, config, taps):
    count = len(clean)
    if count < 2:
        raise ValueError("The selected segment must contain at least two decoded samples")
    rng = np.random.default_rng(config.seed)
    details = {"kind": config.kind, "seed": config.seed,
               "target_snr_db": None if config.amplitude is not None else config.snr_db,
               "requested_noise_rms_fs": config.amplitude}
    if config.frequencies and config.kind not in ("highfreq", "multitone"):
        raise ValueError("Interference frequencies apply to tonal noise only")
    if config.band and config.kind != "bandlimited":
        raise ValueError("Band limits apply to band-limited noise only")

    if config.kind in ("highfreq", "multitone"):
        frequencies = config.frequencies or (
            (1.5 * STOPBAND_HZ,) if config.kind == "highfreq"
            else (1.25 * STOPBAND_HZ, 1.5 * STOPBAND_HZ, 1.75 * STOPBAND_HZ))
        if config.kind == "highfreq" and len(frequencies) != 1:
            raise ValueError("High-frequency noise requires exactly one frequency")
        if config.kind == "multitone" and len(set(frequencies)) < 2:
            raise ValueError("Multi-tone noise requires two or more distinct frequencies")
        if any(not 0 < f < RATE / 2 for f in frequencies):
            raise ValueError(f"Interference frequencies must be between 0 and {RATE / 2:g} Hz")
        times = np.arange(count) / RATE
        phases = rng.uniform(0, 2 * np.pi, len(frequencies))
        noise = sum(np.sin(2 * np.pi * f * times + phase)
                    for f, phase in zip(frequencies, phases))
        _, response = signal.freqz(np.asarray(taps) / FULL_SCALE,
                                   worN=np.asarray(frequencies), fs=RATE)
        details.update(frequencies_hz=list(frequencies), phases_rad=phases.tolist(),
                       expected_tone_gain_db=[
                           float(20 * np.log10(abs(h))) if abs(h) else None for h in response])
    elif config.kind in ("pink", "bandlimited"):
        # Shape random Fourier coefficients on the exact segment grid.
        bins = np.fft.rfftfreq(count, 1 / RATE)
        spectrum = np.fft.rfft(rng.standard_normal(count))
        spectrum[0] = 0
        if config.kind == "pink":
            spectrum[1:] /= np.sqrt(bins[1:])
        else:
            low, high = config.band or (1.125 * STOPBAND_HZ, 1.875 * STOPBAND_HZ)
            if not 0 <= low < high <= RATE / 2:
                raise ValueError("Band limits must satisfy 0 <= LOW < HIGH <= 8000 Hz")
            keep = (bins >= low) & (bins <= high) & (bins > 0)
            if not np.any(keep):
                raise ValueError("No FFT bins in the requested band. Use a longer segment or wider band.")
            spectrum[~keep] = 0
            details.update(band_hz=[low, high], fft_bin_spacing_hz=RATE / count)
        noise = np.fft.irfft(spectrum, n=count)
    elif config.kind == "white":
        noise = rng.standard_normal(count)
    else:
        raise ValueError(f"Unknown noise type: {config.kind}")

    clean_rms = np.sqrt(power(clean))
    if config.amplitude is not None:
        target = config.amplitude
    elif clean_rms:
        with np.errstate(over="ignore", under="ignore"):
            target = clean_rms * np.power(10.0, -config.snr_db / 20)
    else:
        target = SILENCE_NOISE_RMS_FS
        details["note"] = "Input is silent. Used the fallback noise RMS; input SNR is undefined."
    noise_rms = np.sqrt(power(noise))
    if not noise_rms or not np.isfinite(noise_rms) or not np.isfinite(target) or target <= 0:
        raise ValueError("Noise generation did not yield a finite, nonzero RMS")
    return noise * (target / noise_rms), details


def safe_gain(clean, noise):
    peak = max(float(np.max(np.abs(values))) for values in (clean, noise, clean + noise))
    return min(1.0, HEADROOM / peak) if peak else 1.0


def mix(clean, noise, gain, details):
    clean_pcm = pcm16(gain * clean)
    noisy_pcm = pcm16(gain * (clean + noise))
    # Keep the saved noise equal to the exact difference between the two WAVs.
    error = noisy_pcm.astype(np.int32) - clean_pcm
    if np.max(np.abs(error)) > 32767:
        raise ValueError("Quantized injected noise would exceed signed PCM16")
    details.update(
        common_gain=gain,
        headroom_peak_fs=HEADROOM,
        snr_before_pcm_db=snr_db(clean, noise),
        snr_after_pcm_db=snr_db(clean_pcm, error),
        noise_rms_before_pcm_fs=float(gain * np.sqrt(power(noise))),
        noise_rms_after_pcm_fs=float(np.sqrt(power(error)) / FULL_SCALE),
        pcm_conversion_clipped_samples=0,
    )
    return clean_pcm, error.astype("<i2"), noisy_pcm
