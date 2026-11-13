"""Decode one audio segment at float precision and read/write FPGA PCM WAVs."""
import hashlib
from pathlib import Path
import re
import subprocess
import wave

import numpy as np

RATE = 16_000
FULL_SCALE = 32_768
HEADROOM = 0.99


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def decode(path, ffmpeg, start, duration, logger):
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError("Input must be an audio file")
    command = [ffmpeg, "-nostdin", "-hide_banner", "-xerror", "-i", str(path)]
    if start:
        command += ["-ss", str(start)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += ["-map", "0:a:0", "-ac", "1", "-ar", str(RATE),
                "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"]
    logger.info("Decode argv: %r", command)
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise ValueError("FFmpeg executable not found. Install it or pass --ffmpeg.") from exc
    diagnostics = result.stderr.decode(errors="replace")
    logger.info("FFmpeg exit %d\n%s", result.returncode, diagnostics)
    if result.returncode:
        raise ValueError("FFmpeg could not decode the selected audio. See execution.log.")
    if len(result.stdout) % 4:
        raise ValueError("FFmpeg returned a partial float sample")
    samples = np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)
    if not len(samples):
        raise ValueError("No samples decoded. Check the input and segment boundaries.")
    if not np.isfinite(samples).all():
        raise ValueError("Decoded audio contains nonfinite samples")
    source_stream = re.search(r"^\s*Stream .*Audio: .*", diagnostics, re.M)
    source_duration = re.search(r"^\s*Duration: ([^,]+)", diagnostics, re.M)
    version = subprocess.check_output([ffmpeg, "-version"], text=True, errors="replace")
    return samples, {
        "source_name": path.name,
        "source_bytes": path.stat().st_size,
        "source_sha256": sha256(path),
        "source_stream": source_stream.group().strip() if source_stream else None,
        "source_duration": source_duration[1] if source_duration else None,
        "decoder": version.splitlines()[0],
        "downmix": "FFmpeg default channel-layout-aware mono rematrixing",
        "start_s": start,
        "requested_duration_s": duration,
        "samples": len(samples),
        "duration_s": len(samples) / RATE,
        "sample_rate_hz": RATE,
        "channels": 1,
        "encoding": "WAV signed 16-bit little-endian PCM",
        "decoded_peak_fs": float(np.max(np.abs(samples))),
        "decoded_samples_at_or_above_full_scale": int(np.count_nonzero(np.abs(samples) >= 1)),
    }


def pcm16(samples):
    rounded = np.rint(samples * FULL_SCALE)
    if np.any((rounded < -32768) | (rounded > 32767)):
        raise ValueError("PCM conversion would clip")
    return rounded.astype("<i2")


def write_wav(path: Path, samples):
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        stream.writeframes(samples.astype("<i2", copy=False).tobytes())


def read_wav(path: Path):
    with wave.open(str(path), "rb") as stream:
        if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(),
                stream.getcomptype()) != (1, 2, RATE, "NONE"):
            raise ValueError(f"{path.name} is not 16 kHz mono signed PCM16")
        count = stream.getnframes()
        samples = np.frombuffer(stream.readframes(count), dtype="<i2")
        if len(samples) != count:
            raise ValueError(f"{path.name} is truncated")
        return samples
