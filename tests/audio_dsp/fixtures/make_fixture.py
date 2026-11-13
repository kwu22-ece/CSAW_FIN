"""Generate a short, license-free stereo MP3 fixture with distinct channel tones."""
import argparse
from pathlib import Path
import subprocess
import wave

import numpy as np


def make_mp3(path, ffmpeg, seconds=1.0):
    rate = 48_000
    t = np.arange(round(rate * seconds)) / rate
    left = 0.65 * np.sin(2 * np.pi * 500 * t) + 0.18 * np.sin(2 * np.pi * 13_000 * t)
    right = 0.45 * np.sin(2 * np.pi * 1000 * t)
    data = np.rint(np.column_stack((left, right)) * 32768).astype("<i2")
    pcm = path.with_suffix(".source.wav")
    with wave.open(str(pcm), "wb") as stream:
        stream.setparams((2, 2, rate, 0, "NONE", "not compressed"))
        stream.writeframes(data.tobytes())
    subprocess.run([ffmpeg, "-v", "error", "-nostdin", "-y", "-i", str(pcm),
                    "-c:a", "libmp3lame", "-b:a", "192k", str(path)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    make_mp3(args.output, args.ffmpeg)
