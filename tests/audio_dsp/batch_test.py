"""Run an audio DSP noise/SNR matrix with one common gain and a single decode."""
import argparse
import itertools
import sys

from audio_io import decode, pcm16
from audio_test import (ERRORS, common_arguments, csv_file, exit_status, finite, json_file,
                        new_run, run_case, run_logger, summarize, validate_common)
from backends import Hardware, Reference
from noise_generator import KINDS, Noise, generate, safe_gain


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    common_arguments(parser)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--noise", choices=KINDS, action="append", help="repeat to select noise types")
    selection.add_argument("--all-noise-types", action="store_true", help="run all five noise types")
    parser.add_argument("--snr-db", type=finite, nargs="+", default=[30, 20, 10, 0])
    parser.add_argument("--max-cases", type=int, help="cap the number of matrix cases")
    parser.add_argument("--hardware-cases", type=int, default=1,
                        help="number of cases to stream in --mode both (default 1); hardware-only streams all")
    args = parser.parse_args()
    validate_common(parser, args)
    if args.max_cases is not None and args.max_cases < 1:
        parser.error("--max-cases must be positive")
    if args.hardware_cases < 1:
        parser.error("--hardware-cases must be positive")
    kinds = tuple(dict.fromkeys(args.noise or KINDS))
    configs = [Noise(kind, snr, args.seed)
               for kind, snr in itertools.product(kinds, dict.fromkeys(args.snr_db))]
    if args.max_cases is not None:
        configs = configs[:args.max_cases]

    directory = new_run(args.output_dir)
    logger, handler = run_logger(directory)
    try:
        clean, metadata = decode(args.input, args.ffmpeg, args.start, args.duration, logger)
        reference = Reference()
        gain = 1.0
        for config in configs:
            noise, _ = generate(clean, config, reference.taps)
            gain = min(gain, safe_gain(clean, noise))
        clean_filtered = reference.run(pcm16(gain * clean))
        hardware = Hardware(args, reference, directory, logger) if args.mode != "software" else None
        rows, outcomes = [], []
        for index, config in enumerate(configs, 1):
            noise, details = generate(clean, config, reference.taps)
            case = f"{index:02d}-{config.kind}"
            hardware_deferred = args.mode == "both" and index > args.hardware_cases
            mode = "software" if hardware_deferred else args.mode
            metrics = run_case(directory / case, clean, metadata, noise, details, gain, mode,
                               reference, hardware, clean_filtered)
            rows.append(dict(case=case, **summarize(metrics),
                             hardware_deferred_by_batch_limit=hardware_deferred))
            outcomes.append(exit_status(metrics))
            # Retain completed cases if a later case errors.
            csv_file(directory / "summary.csv", rows)
            json_file(directory / "summary.json", {"common_gain": gain, "requested_mode": args.mode,
                                                   "cases": rows})
        print(f"{directory}\nCompleted {len(rows)} case(s).")
        return 1 if 1 in outcomes else 2 if 2 in outcomes else 0
    except ERRORS as exc:
        logger.error("%s", exc)
        print(f"Audio matrix failed: {exc}\nArtifacts: {directory}", file=sys.stderr)
        return 1
    finally:
        logger.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    sys.exit(main())
