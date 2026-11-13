#!/usr/bin/env python3
"""Prepare full-recording, baseline-output chunks for the extended I2S regression."""
import csv
import hashlib
import json
import struct
import sys
import wave
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
PROJECT = PACKAGE.parents[2]
TESTS = PACKAGE / "tests"
OUTPUT = PACKAGE / "reports" / "full-audio-vectors"
SOURCE = PROJECT / "what_a_piece_of_work-noisy.wav"
MAX_CASE_FRAMES = 65_536  # Phase 4 limit: 131,072 alternating input words.
FLUSH_FRAMES = 130        # 128 payload frames plus two-frame I2S output latency.
TRIGGER = (32512, -32511, 23100, -23101, 28050, -28051, -15556, 15555)
OVERLAP_FRAMES = len(TRIGGER) - 1

sys.path.insert(0, str(TESTS))
from reference import run_reference as baseline


def read_audio():
    raw_file = SOURCE.read_bytes()
    with wave.open(str(SOURCE), "rb") as stream:
        metadata = {
            "channels": stream.getnchannels(),
            "sample_rate_hz": stream.getframerate(),
            "sample_width_bytes": stream.getsampwidth(),
            "frames": stream.getnframes(),
        }
        if (
            metadata["channels"] != 1
            or metadata["sample_rate_hz"] != 16000
            or metadata["sample_width_bytes"] != 2
            or metadata["frames"] < 1
        ):
            raise SystemExit(f"Expected mono 16 kHz PCM16 WAV, got {metadata}")
        payload = stream.readframes(stream.getnframes())
    if len(payload) != metadata["frames"] * 2:
        raise SystemExit("WAV payload length does not match its declared frame count")
    samples = list(struct.unpack("<" + "h" * metadata["frames"], payload))
    return samples, metadata, hashlib.sha256(raw_file).hexdigest()


def trigger_completions(samples):
    matched = 0
    hits = []
    for index, sample in enumerate(samples):
        if sample == TRIGGER[matched]:
            if matched == len(TRIGGER) - 1:
                hits.append(index)
                matched = 0
            else:
                matched += 1
        elif sample == TRIGGER[0]:
            matched = 1
        else:
            matched = 0
    return hits


def write_csv_pair(input_path, expected_path, samples, coeffs):
    input_path.parent.mkdir(parents=True, exist_ok=True)
    expected_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["index", "channel", "value"])
        for index, value in enumerate(samples):
            writer.writerow([2 * index, 0, value])
            writer.writerow([2 * index + 1, 1, value])

    filtered = baseline.fir(samples, coeffs)
    with expected_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["index", "channel", "value"])
        for frame in range(len(samples)):
            source_frame = frame - 2
            left = filtered[source_frame] if 0 <= source_frame < len(samples) else 0
            right = samples[source_frame] if 0 <= source_frame < len(samples) else 0
            writer.writerow([2 * frame, 0, left])
            writer.writerow([2 * frame + 1, 1, right])


def main():
    audio, metadata, source_hash = read_audio()
    if not audio:
        raise SystemExit("No audio samples found")
    max_source_frames = MAX_CASE_FRAMES - FLUSH_FRAMES
    step = max_source_frames - OVERLAP_FRAMES
    coeffs = baseline.load_coeffs(str(TESTS / "reference" / "coeffs.json"))
    OUTPUT.mkdir(parents=True, exist_ok=True)

    segments = []
    start = 0
    while start < len(audio):
        end = min(start + max_source_frames, len(audio))
        source_samples = audio[start:end]
        samples = source_samples + [0] * FLUSH_FRAMES
        name = f"full-noisy-audio-{len(segments):02d}"
        input_path = OUTPUT / f"{name}.csv"
        expected_path = OUTPUT / f"{name}.expected.csv"
        write_csv_pair(input_path, expected_path, samples, coeffs)
        segments.append({
            "case": name,
            "source_start_frame": start,
            "source_end_frame_exclusive": end,
            "source_frames": len(source_samples),
            "flush_frames": FLUSH_FRAMES,
            "total_input_frames": len(samples),
            "compared_words": 2 * len(samples),
            "input_path": f"reports/full-audio-vectors/{input_path.name}",
            "expected_path": f"reports/full-audio-vectors/{expected_path.name}",
            "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
            "expected_sha256": hashlib.sha256(expected_path.read_bytes()).hexdigest(),
        })
        if end == len(audio):
            break
        start = end - OVERLAP_FRAMES

    summary = {
        "schema_version": 1,
        "source_path": SOURCE.relative_to(PROJECT).as_posix(),
        "source_sha256": source_hash,
        **metadata,
        "source_frames_covered": len(audio),
        "trigger_samples_hex": [f"{value & 0xFFFF:04X}" for value in TRIGGER],
        "trigger_completion_frames": trigger_completions(audio),
        "chunk_overlap_frames": OVERLAP_FRAMES,
        "flush_frames_per_chunk": FLUSH_FRAMES,
        "max_case_frames": MAX_CASE_FRAMES,
        "total_simulated_frames": sum(item["total_input_frames"] for item in segments),
        "total_compared_words": sum(item["compared_words"] for item in segments),
        "segments": segments,
    }
    summary_path = OUTPUT / "source-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_frames": len(audio),
        "source_sha256": source_hash,
        "trigger_completions": summary["trigger_completion_frames"],
        "segments": len(segments),
        "overlap_frames": OVERLAP_FRAMES,
        "flush_frames_per_segment": FLUSH_FRAMES,
        "simulated_frames": summary["total_simulated_frames"],
        "compared_words": summary["total_compared_words"],
        "summary": str(summary_path),
    }, indent=2))


if __name__ == "__main__":
    main()
