#!/usr/bin/env python3
"""Audit full-recording simulation captures against the generated source manifest."""
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    run_dir = args.run.resolve()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    statuses = {case["name"]: case["status"] for case in report["cases"]}
    details = []
    for segment in summary["segments"]:
        name = segment["case"]
        case_dir = run_dir / name
        comparison = json.loads((case_dir / "comparison.json").read_text(encoding="utf-8"))
        inputs = json.loads((case_dir / "inputs.json").read_text(encoding="utf-8"))
        simulation = json.loads((case_dir / "simulation.log.json").read_text(encoding="utf-8"))
        detail = {
            "case": name,
            "status": statuses.get(name, "missing"),
            "source_start_frame": segment["source_start_frame"],
            "source_end_frame_exclusive": segment["source_end_frame_exclusive"],
            "source_frames": segment["source_frames"],
            "flush_frames": segment["flush_frames"],
            "compared_words": comparison["samples_compared"],
            "mismatch_count": comparison["mismatch_count"],
            "simulation_exit_code": simulation["exit_code"],
            "input_hash_matches": segment["input_sha256"] in inputs["sha256"].values(),
            "expected_hash_matches": segment["expected_sha256"] in inputs["sha256"].values(),
        }
        details.append(detail)

    total_words = sum(item["compared_words"] for item in details)
    mismatch_count = sum(item["mismatch_count"] for item in details)
    evidence = {
        "schema_version": 1,
        "scope": "Complete provided noisy WAV, split into reset-isolated I2S simulations with seven-frame overlap.",
        "source_path": summary["source_path"],
        "source_sha256": summary["source_sha256"],
        "source_frames": summary["source_frames_covered"],
        "sample_rate_hz": summary["sample_rate_hz"],
        "trigger_completion_frames": summary["trigger_completion_frames"],
        "trigger_hit_count": len(summary["trigger_completion_frames"]),
        "segment_count": len(details),
        "segments_passed": sum(item["status"] == "passed" for item in details),
        "segments_failed": sum(item["status"] == "failed" for item in details),
        "segments_blocked": sum(item["status"] == "blocked" for item in details),
        "total_simulated_frames": summary["total_simulated_frames"],
        "compared_words": total_words,
        "baseline_mismatch_count": mismatch_count,
        "segments": details,
        "run_report_sha256": sha256(run_dir / "report.json"),
        "hardware_validation": "not run; no physical board was available",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    if (
        not report["passed"]
        or evidence["segments_passed"] != len(details)
        or evidence["segments_failed"]
        or evidence["segments_blocked"]
        or mismatch_count
        or evidence["trigger_hit_count"]
        or any(
            item["simulation_exit_code"] != 0
            or not item["input_hash_matches"]
            or not item["expected_hash_matches"]
            for item in details
        )
        or total_words != summary["total_compared_words"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
