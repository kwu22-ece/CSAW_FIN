"""Inject controlled noise into audio and measure the original Challenge 3 FIR."""
import argparse
import csv
import json
import logging
import math
from pathlib import Path
import subprocess
import sys
import uuid
import wave
from datetime import datetime, timezone

from audio_analysis import analyze, compare
from audio_io import decode, write_wav
from backends import Hardware, PortUnavailable, Reference
from noise_generator import DEFAULT_SEED, KINDS, Noise, generate, mix, safe_gain

HERE = Path(__file__).resolve().parent
ERRORS = (OSError, ValueError, wave.Error, subprocess.SubprocessError)


def json_file(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def csv_file(path, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def finite(text):
    number = float(text)
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError("expected a finite number")
    return number


def common_arguments(parser):
    parser.add_argument("--input", required=True, type=Path, help="input MP3 or FFmpeg-readable audio")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable or absolute path")
    parser.add_argument("--mode", choices=("software", "hardware", "both"), default="software")
    parser.add_argument("--challenge-dir", type=Path, help="official finals/challenge_3 directory")
    parser.add_argument("--port", help="confirmed Hackster application port (or HACKSTER_APP_PORT)")
    parser.add_argument("--confirm-stock", action="store_true",
                        help="confirm the board is available and the original bitstream is programmed")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--start", type=finite, default=0, metavar="SECONDS")
    parser.add_argument("--duration", type=finite, metavar="SECONDS", help="limit decoded segment")
    parser.add_argument("--output-dir", type=Path, default=HERE / "output",
                        help="parent for a new uniquely named run directory")


def validate_common(parser, args):
    if args.start < 0 or (args.duration is not None and args.duration <= 0):
        parser.error("--start must be nonnegative and --duration must be positive")
    if args.seed < 0:
        parser.error("--seed must be nonnegative")


def new_run(parent):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = parent.resolve() / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True)
    return directory


def run_logger(directory):
    logger = logging.getLogger(str(directory))
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(directory / "execution.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger, handler


def status_table(report):
    return {name: data["state"] for name, data in report["modes"].items()}


def summarize(report):
    row = {"noise": report["noise"]["kind"], "target_snr_db": report["noise"]["target_snr_db"],
           "samples": report["alignment"]["input_samples"], "input_snr_db": report["input_snr_db"]}
    row.update({f"{name}_status": state for name, state in status_table(report).items()})
    for name, output in report["outputs"].items():
        for key in ("output_snr_db", "snr_change_db", "stopband_noise_attenuation_db"):
            row[f"{name}_{key}"] = output[key]
    if report["comparison"]:
        for key in ("mismatches", "max_abs_error_lsb", "rms_error_lsb", "bit_exact"):
            row[f"comparison_{key}"] = report["comparison"][key]
    return row


def write_report(directory, report):
    json_file(directory / "metrics.json", report)
    if report["comparison"] is not None:
        json_file(directory / "comparison.json", report["comparison"])
    row = summarize(report)
    csv_file(directory / "metrics.csv", [row])
    lines = ["# Audio DSP test", "", "## Execution modes", ""]
    for name, state in report["modes"].items():
        reason = state.get("reason")
        lines.append(f"- {name}: **{state['state']}**" + (f" — {reason}" if reason else ""))
    lines += ["", "## Measurements", ""]
    for key, value in row.items():
        if not key.endswith("_status"):
            shown = f"{value:.3f}" if isinstance(value, float) else value
            lines.append(f"- {key}: {'undefined' if shown is None else shown}")
    lines += [
        "", "Output SNR uses the FIR-filtered clean PCM as its desired signal. "
        "The residual includes fixed-point rounding and any saturation or hardware error.",
        "The intrinsic FIR group delay is retained in the WAVs. Clean-signal change "
        "uses a separately delay-aligned comparison.",
        "", "## Artifacts", "",
        "- [Waveforms](plots/waveforms.png)",
        "- [Spectrograms](plots/spectrograms.png)",
        "- [Spectra and frequency-dependent gain](plots/frequency.png)",
        "- [Performance summary](plots/performance.png)",
        "- [Full metrics](metrics.json)",
        "- [Noise parameters](noise_metadata.json)",
        "- [Execution log](execution.log)",
    ]
    (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_case(directory, clean, source_metadata, noise, details, gain, mode,
             reference, hardware, clean_filtered=None):
    directory.mkdir(exist_ok=True)
    logger, handler = run_logger(directory)
    try:
        logger.info("Input SHA-256 %s, %d samples", source_metadata["source_sha256"], len(clean))
        clean_pcm, noise_pcm, noisy_pcm = mix(clean, noise, gain, details)
        series = {"clean": clean_pcm, "noise": noise_pcm, "noisy": noisy_pcm}
        for name, samples in series.items():
            write_wav(directory / f"{name}.wav", samples)
        metadata = dict(source_metadata, common_gain=gain, fir=reference.provenance)
        json_file(directory / "metadata.json", metadata)
        json_file(directory / "noise_metadata.json", details)

        modes = {name: {"state": "not_requested"} for name in ("software", "hardware", "comparison")}
        if clean_filtered is None:
            clean_filtered = reference.run(clean_pcm)
        if mode in ("software", "both"):
            series["software"] = reference.run(noisy_pcm)
            write_wav(directory / "filtered_software.wav", series["software"])
            modes["software"] = {"state": "passed"}
        if mode in ("hardware", "both"):
            modes["hardware"] = dict(hardware.status)
            if hardware.status["state"] == "ready":
                temporary = directory / "hardware_capture.partial.wav"
                try:
                    series["hardware"] = hardware.capture(
                        directory / "noisy.wav", temporary, len(noisy_pcm))
                    temporary.replace(directory / "filtered_hardware.wav")
                    modes["hardware"].update(state="passed", echo="passed")
                except ERRORS as exc:
                    series.pop("hardware", None)
                    logger.error("Hardware capture: %s", exc)
                    state = "unverified" if isinstance(exc, PortUnavailable) else "failed"
                    hardware.status.update(state=state, reason=str(exc))
                    modes["hardware"].update(state=state, reason=str(exc))

        agreement = None
        if mode == "both":
            if "hardware" in series:
                agreement = compare(series["hardware"], series["software"])
                modes["comparison"] = {"state": "passed" if agreement["bit_exact"] else "failed"}
            else:
                modes["comparison"] = {"state": "unverified", "reason": "No valid hardware capture."}
        delay = reference.provenance["group_delay_samples"]
        metrics, spectra, attenuation = analyze(series, clean_filtered, delay)
        metrics.update(modes=modes, comparison=agreement, noise=details, alignment={
            "input_samples": len(noisy_pcm),
            "output_samples": {name: len(series[name]) for name in ("software", "hardware")
                               if name in series},
            "fir_group_delay_samples_retained": delay,
            "hardware_transport_delay_frames": 2 if "hardware" in series else None,
            "extra_output_shift_samples": 0,
            "initial_history": "zero",
        })
        logger.info("Mode status: %s", status_table(metrics))
        from plots import render

        write_report(directory, metrics)
        render(directory / "plots", series, spectra, attenuation, reference.taps, metrics)
        return metrics
    except ERRORS as exc:
        logger.error("%s", exc)
        raise
    finally:
        logger.removeHandler(handler)
        handler.close()


def exit_status(metrics):
    states = status_table(metrics).values()
    if "failed" in states:
        return 1
    if "unverified" in states:
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    common_arguments(parser)
    parser.add_argument("--noise", choices=KINDS, default="white")
    level = parser.add_mutually_exclusive_group()
    level.add_argument("--snr-db", type=finite, help="target input SNR in dB (default 20)")
    level.add_argument("--noise-amplitude", type=finite, help="noise RMS in full-scale units before gain")
    parser.add_argument("--frequency", type=finite, action="append",
                        help="interference frequency in Hz, repeat for multiple tones")
    parser.add_argument("--band", type=finite, nargs=2, metavar=("LOW", "HIGH"), help="noise band in Hz")
    args = parser.parse_args()
    validate_common(parser, args)
    if args.noise_amplitude is not None and not 0 < args.noise_amplitude <= 1:
        parser.error("--noise-amplitude must be in (0, 1]")
    directory = new_run(args.output_dir)
    logger, handler = run_logger(directory)
    try:
        clean, metadata = decode(args.input, args.ffmpeg, args.start, args.duration, logger)
        reference = Reference()
        config = Noise(args.noise, 20 if args.snr_db is None else args.snr_db, args.seed,
                       tuple(args.frequency or ()), tuple(args.band) if args.band else None,
                       args.noise_amplitude)
        noise, details = generate(clean, config, reference.taps)
        gain = safe_gain(clean, noise)
        hardware = Hardware(args, reference, directory, logger) if args.mode != "software" else None
        metrics = run_case(directory, clean, metadata, noise, details, gain,
                           args.mode, reference, hardware)
        print(f"{directory}\n{status_table(metrics)}")
        return exit_status(metrics)
    except ERRORS as exc:
        logger.error("%s", exc)
        print(f"Audio test failed: {exc}\nArtifacts: {directory}", file=sys.stderr)
        return 1
    finally:
        logger.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    sys.exit(main())
