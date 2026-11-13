"""Reproduce the clean baseline, selected improvement, and submission evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tarfile

ROOT = Path(__file__).resolve().parent
HANDOFF = ROOT / "handoffs/phase-08"
CONFIG_PATH = HANDOFF / "reproduction.json"
SELECTION_PATH = "handoffs/phase-05/selection.json"
QUALITY_PATH = "handoffs/quality-review/current-best.json"
DOCS = ("README.md", "engineering.md", "requirements.md", "scribe.md", "github.md")
GATES = ("baseline_simulation", "synthesis", "resource_timing", "ai_provenance", "physical")
SAFE_GATE_VALUES = {"pass", "fail", "not_run", "incomplete", "incomplete_main_session"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def publish(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        staged = Path(stream.name)
    try:
        staged.write_bytes(data)
        staged.replace(path)
    finally:
        staged.unlink(missing_ok=True)


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd, timeout=60).decode("utf-8")


def commit(sha):
    require(re.fullmatch(r"[0-9a-f]{40}", sha), "Expected a full Git commit SHA")
    require(git("rev-parse", "--verify", f"{sha}^{{commit}}").strip() == sha, f"Missing commit {sha}")
    return sha


def ancestor(older, newer):
    require(git("merge-base", older, newer).strip() == older, f"{older} is outside {newer}'s ancestry")


def worktrees():
    entries = {}
    for record in git("worktree", "list", "--porcelain", "-z").split("\0\0"):
        fields = dict(line.split(" ", 1) for line in record.split("\0") if " " in line)
        if "branch" in fields:
            entries[fields["branch"].removeprefix("refs/heads/")] = Path(fields["worktree"])
    return entries


def read_receipt(sha, path):
    data = subprocess.check_output(["git", "show", f"{commit(sha)}:{path}"], cwd=ROOT, timeout=60)
    return json.loads(data), digest(data)


def audit(config, output):
    baseline = commit(config["baseline_commit"])
    selection, selection_hash = read_receipt(config["selection_commit"], SELECTION_PATH)
    quality, quality_hash = read_receipt(config["quality_review_commit"], QUALITY_PATH)
    require(selection["schema_version"] in (1, 2, 3) and quality["schema_version"] in (1, 2, 3),
            "Unknown receipt version")
    require(selection["common_baseline_commit_sha"] == quality["baseline_sha"] == baseline,
            "Receipts disagree on the pinned baseline")
    rows = selection["ranking"]
    require({row["candidate_id"] for row in rows} == set(config["candidates"])
            and sorted(row["rank"] for row in rows) == [1, 2, 3, 4], "Invalid saved ranking")
    candidates = {}
    attached = worktrees()
    historical, _ = read_receipt(config["original_selection_commit"], SELECTION_PATH)
    for row in sorted(rows, key=lambda item: item["rank"]):
        key = row["candidate_id"]
        candidate = config["candidates"][key]
        sha = commit(candidate["snapshot"])
        require(row["snapshot_sha"] == sha, f"Saved result has the wrong snapshot for {key}")
        ancestor(baseline, sha)
        gates = historical["candidate_results"][key]["gate_results"]
        saved = {name: gates[name] for name in GATES}
        require(set(saved.values()) <= SAFE_GATE_VALUES, f"Unrecognized gate status for {key}")
        candidates[key] = {
            "candidate_id": key, "model": candidate["model"], "environment": candidate["environment"],
            "branch": candidate["branch"], "source_commit": sha, "baseline_commit": baseline,
            "registered_worktree": candidate["branch"] in attached,
            "saved_rank": row["rank"], "saved_gates": saved, "execution": "saved_evidence_only",
            "latest_reviewed_commit": commit(selection.get("last_reviewed_candidate_shas", {}).get(key, sha)),
            "current_gates": selection.get("gate_results", {}).get(key, saved),
        }
    selected = selection["winner"]["candidate_id"]
    original = candidates[selected]["source_commit"]
    require(rows[0]["candidate_id"] == selected and rows[0]["rank"] == 1
            and selection["winner"]["immutable_package_commit_sha"] == original
            and quality["selected_candidate_id"] == selected
            and quality["original_selected_candidate_sha"] == original
            and quality["selection_manifest_commit_sha"] == config["original_selection_commit"],
            "Selection and quality-review receipts disagree")
    best = commit(quality["current_best_known_sha"])
    require(best == config["selected_commit"] == selection.get("current_best_known_sha", best),
            "Selected implementation differs from current quality and selection receipts")
    fix = commit(quality["implementation_fix_sha"])
    ancestor(original, fix)
    ancestor(fix, best)
    ancestor(best, config["quality_review_commit"])
    checkpoint = selection.get("last_evaluation_cycle_id")
    require(checkpoint == config["selection_checkpoint"], "Selection checkpoint differs from reviewed configuration")
    require(quality.get("last_evaluation_cycle_id") == checkpoint,
            "Selection and quality review checkpoint identifiers disagree")
    prior_phase8 = selection["best_results"]["independent_phase8_reproduction"]
    require(prior_phase8["source_sha"] == config["prior_release_commit"]
            and prior_phase8["source_sha"] == commit(prior_phase8["source_sha"]),
            "Saved Phase 8 evidence is not anchored to the prior release")
    drift = selection["new_evidence"]["main_clock_drift"]
    require(drift["simulations_passed"] == 51 and drift["compared_words"] == 48888
            and drift["mismatches"] == 0 and drift["directed_window_checks_passed"] == 45,
            "Cycle checkpoint clock-drift evidence is incomplete")
    reports = {
        "selection.json": {
            "selected_candidate": selected, "selection_commit": config["selection_commit"],
            "selection_receipt_sha256": selection_hash, "source_commit": original,
            "baseline_commit": baseline, "status": selection["status"], "checkpoint": checkpoint,
            "saved_cycle_evidence": {
                "clock_drift_simulations": drift["simulations_passed"],
                "clock_drift_words": drift["compared_words"],
                "clock_drift_mismatches": drift["mismatches"],
                "prior_phase8_release": prior_phase8["source_sha"],
            },
        },
        "current-best.json": {
            "selected_candidate": selected, "quality_review_commit": config["quality_review_commit"],
            "quality_receipt_sha256": quality_hash, "original_source_commit": original,
            "current_best_commit": best, "baseline_commit": baseline,
            "recorded_review_status": quality["status"],
            "phase8_validation": "provenance_only", "physical_signoff": "not_run",
        },
        "candidate-evidence.json": {"schema_version": 1, "candidates": candidates},
    }
    for name, report in reports.items():
        publish(output / name, json_bytes(report))
    for path, receipt in ((SELECTION_PATH, selection), (QUALITY_PATH, quality)):
        destination = ROOT / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        publish(destination, json_bytes(receipt))
    print(f"Verified four saved candidate records, selection {selected}, and quality revision {best[:12]}.")
    return reports


def snapshot(sha, destination):
    """Extract an immutable Git tree and reject links or unsafe archive paths."""
    archive = destination.with_suffix(".tar")
    commit(sha)
    # `git archive` otherwise inherits the host's global core.autocrlf setting on
    # Windows, which changes byte-manifested evidence during extraction.
    subprocess.run(["git", "-c", "core.autocrlf=false", "archive", "--format=tar", "--output=" + str(archive), sha],
                   cwd=ROOT, check=True, timeout=120)
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        for member in stream.getmembers():
            path = destination / member.name
            require(path.resolve().is_relative_to(destination.resolve())
                    and (member.isfile() or member.isdir()), "Unsafe Git archive member")
        stream.extractall(destination)
    return destination


def tree_hashes(root):
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def verify_files(root, hashes):
    require(bool(hashes), "Empty evidence inventory")
    for name, expected in hashes.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file()
                and file_hash(path) == expected, f"Evidence changed or missing: {name}")


def selected(config, args, output):
    """Execute the existing quality suite against a frozen selected source tree."""
    audit(config, output)
    suite = Path(args.selected_suite or os.environ.get("SELECTED_OSS_CAD_SUITE")
                 or config["selected_suite_default"]).expanduser().resolve()
    require(suite.is_dir(), "Supply the quality-review toolchain using --selected-suite")
    env = dict(os.environ, OSS_CAD_SUITE=str(suite), PYTHONDONTWRITEBYTECODE="1")
    python = str(Path(sys.executable).resolve())
    identity = {"selected_commit": config["selected_commit"], "config_sha256": file_hash(CONFIG_PATH),
                "python_sha256": file_hash(Path(python)), "driver_sha256": file_hash(Path(__file__)),
                "suite": str(suite)}
    if args.resume_selected:
        attempt = args.resume_selected.resolve()
        require(attempt.parent == output and attempt.name.startswith("selected-"), "Invalid selected checkpoint")
        require(read_json(attempt / "identity.json") == identity, "Selected checkpoint inputs changed")
    else:
        attempt = Path(tempfile.mkdtemp(prefix="selected-", dir=output))
        publish(attempt / "identity.json", json_bytes(identity))
        snapshot(config["selected_commit"], attempt / "source")
        snapshot(config["selection_commit"], attempt / "evaluation")
    print(f"Selected candidate attempt {attempt}", flush=True)
    source = attempt / "source"
    package_root = source / "experiments/phase05/05b-astra"
    doctor = attempt / "toolchain.json"
    subprocess.run([python, str(source / "infrastructure/run.py"), "--suite", str(suite),
                    "doctor", "--output", str(doctor)], cwd=source, env=env,
                   stdout=subprocess.DEVNULL, timeout=120, check=True)
    tools = read_json(doctor)["tools"]
    for name, sha in config["selected_tools"].items():
        require(tools[name]["available"] and tools[name]["sha256"] == sha, f"Tool mismatch: {name}")

    def stage(name, command, directory):
        receipt = attempt / (name + ".json")
        if args.resume_selected and receipt.is_file():
            saved = read_json(receipt)
            require(saved["argv"] == command and saved["exit_code"] == 0, "Checkpoint command changed")
            verify_files(directory, saved["outputs"])
            print(f"Resumed {name} with verified evidence", flush=True)
            return
        require(not directory.exists(), f"Partial {name} outputs exist. Start a fresh selected attempt.")
        with (attempt / (name + ".log")).open("wb") as log:
            result = subprocess.run(command, cwd=source, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=2400, check=False)
        require(result.returncode == 0, f"{name} failed with exit {result.returncode}. See {attempt / (name + '.log')}")
        publish(receipt, json_bytes({"argv": command, "exit_code": 0, "outputs": tree_hashes(directory)}))

    run = attempt / "quality"
    stage("quality-suite", [python, str(source / "experiments/quality/run.py"), "--suite", str(suite),
                            "--output", str(run)], run)
    repeat = attempt / "repeat"
    stage("repeat-build", [python, str(source / "infrastructure/run.py"), "--suite", str(suite),
                            "build", "--manifest", str(package_root / "manifest.json"),
                            "--output", str(repeat)], repeat)
    continuous = attempt / "continuous"
    stage("continuous-audio", [python, str(attempt / "evaluation/experiments/phase05s/cycle-02/run_continuous.py"),
                                "--repo", str(ROOT), "--ref", config["selected_commit"],
                                "--suite", str(suite), "--output", str(continuous)], continuous)
    standard = read_json(run / "standard-audit.json")
    directed = read_json(run / "directed-audit.json")
    audio = read_json(run / "audio-audit.json")
    uninterrupted = read_json(continuous / "receipt.json")
    inventory = read_json(run / "inventory-audit.json")
    require(inventory["passed"] and inventory["entries"] == 41, "Selected inventory failed")
    for name, count in (("standard", 11), ("common", 2), ("directed", 30), ("full-audio", 4), ("baseline-build", 1)):
        report = read_json(run / name / "report.json")
        require(report["passed"] and len(report["cases"]) == count
                and all(c["status"] == "passed" for c in report["cases"]), f"Suite coverage failed: {name}")
    unit_log = (run / "standard/unit-tests.log").read_text()
    require("Ran 15 tests" in unit_log and unit_log.rstrip().endswith("OK")
            and "skipped" not in unit_log.lower(), "Framework tests incomplete")
    require(directed["passed"] and directed["passed_cases"] == 30, "Directed checks failed")
    require(audio["compared_words"] == 481082 and audio["baseline_mismatch_count"] == 0,
            "Full audio checks failed")
    require(uninterrupted["passed"] and uninterrupted["source_commit_sha"] == config["selected_commit"]
            and uninterrupted["comparison"]["samples_compared"] == 480260
            and uninterrupted["comparison"]["mismatch_count"] == 0, "Continuous audio failed")
    for folder in (run / "standard", repeat):
        summary = read_json(folder / "fpga-build/build-summary.json")
        require(summary["passed"] and summary["constrained_pins"] and summary["seed"] == 1
                and summary["frequency_mhz"] == 10 and summary["fmax"]
                and all(clock["achieved"] >= clock["constraint"] for clock in summary["fmax"].values()),
                "Selected build failed")
        for filename in ("bitstream.bin", "roundtrip.bin"):
            require(file_hash(folder / "fpga-build" / filename) == config["selected_bitstream_sha256"],
                    "Selected bitstream differs from the verified quality result")
    evidence = {"status": "passed", "evidence_type": "executed_selected_candidate", **identity,
                "executed_at_utc": datetime.now(timezone.utc).isoformat(),
                "attempt": attempt.name, "framework_tests": 15, "simulations": 47,
                "normal_words": sum(c["samples_compared"] for c in standard["normal_cases"].values()),
                "normal_mismatches": standard["baseline_mismatch_count"],
                "full_audio_words": audio["compared_words"], "continuous_words": 480260,
                "directed_cases": 30, "source_inventory_entries": 41,
                "build": standard["fpga_build"], "repeat_and_roundtrip": "passed",
                "physical_hardware": "not_run", "toolchain_sha256": file_hash(doctor),
                "checkpoint_sha256": {n: file_hash(attempt / n) for n in
                                      ("identity.json", "quality-suite.json", "repeat-build.json", "continuous-audio.json")}}
    publish(output / "selected-validation.json", json_bytes(evidence))
    best_report = read_json(output / "current-best.json")
    best_report.update(phase8_validation="simulation_and_build_passed", validation_receipt="selected-validation.json")
    publish(output / "current-best.json", json_bytes(best_report))
    print("Selected candidate passed 47 simulations, 15 framework tests, and repeatable FPGA builds.", flush=True)
    return evidence


def baseline(config, args, output):
    phase4 = args.baseline_worktree or worktrees().get("challenge3/04-infrastructure")
    require(phase4 is not None, "Supply the pinned Phase 4 worktree with --baseline-worktree")
    phase4 = phase4.resolve()
    pinned = commit(config["baseline_commit"])
    recovered = commit(config["reconstruction_commit"])
    require(git("rev-parse", "HEAD", cwd=phase4).strip() == pinned, "Incorrect Phase 4 HEAD")
    require(not git("status", "--porcelain", "--untracked-files=all", "--",
                    "infrastructure", "what_a_piece_of_work-noisy.wav", cwd=phase4).strip(),
            "Phase 4 runner and audio inputs must match the pinned worktree")
    suite = Path(args.suite or os.environ.get("OSS_CAD_SUITE") or phase4 / ".tools/oss-cad-suite").resolve()
    require(suite.is_dir(), "Supply the pinned OSS CAD Suite using --suite or OSS_CAD_SUITE")
    expected = config["clean_baseline"]
    lock = read_json(phase4 / "infrastructure/toolchain-lock.json")
    require(lock["release"] == expected["suite_release"], "Suite release differs from Phase 4 lock")

    # Each attempt gets fresh outputs. A successful checkpoint may be resumed only
    # after its configuration, command, dependencies, and evidence still match.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    python = str(Path(sys.executable).resolve())
    runner = [python, "infrastructure/run.py", "--suite", str(suite)]
    run_key = {"config": file_hash(CONFIG_PATH), "driver": file_hash(Path(__file__)),
               "python": file_hash(Path(python)), "git": git("--version").strip(),
               "phase4": str(phase4), "suite": str(suite)}
    if args.resume:
        attempt = Path(args.resume).resolve()
        require(attempt.parent == output and attempt.name.startswith("baseline-"),
                "--resume must refer to a baseline attempt in --output")
        require(read_json(attempt / "inputs.json") == run_key, "Checkpoint inputs changed")
    else:
        attempt = Path(tempfile.mkdtemp(prefix="baseline-", dir=output))
        publish(attempt / "inputs.json", json_bytes(run_key))
    print(f"Baseline attempt {attempt}", flush=True)

    def stage(name, command, files):
        receipt = attempt / f"{name}.json"
        if args.resume and receipt.exists():
            saved = read_json(receipt)
            require(saved == {"argv": command, "sha256": {str(p): file_hash(p) for p in files}},
                    f"{name} checkpoint does not match its evidence")
            print(f"Resumed {name} from verified checkpoint", flush=True)
            return
        require(not any(p.exists() for p in files), f"Partial {name} outputs exist. Start a fresh attempt.")
        with (attempt / f"{name}.log").open("wb") as log:
            result = subprocess.run(command, cwd=phase4, env=env, stdout=log,
                                    stderr=subprocess.STDOUT, timeout=900, check=False)
        if result.returncode != 0:
            raise ValueError(f"{name} exited {result.returncode}. See {attempt / (name + '.log')}")
        publish(receipt, json_bytes({"argv": command, "sha256": {str(p): file_hash(p) for p in files}}))

    doctor = attempt / "toolchain.json"
    # Probe current executable versions and hashes even when resuming.
    subprocess.run([*runner, "doctor", "--output", str(doctor)], cwd=phase4, env=env,
                   stdout=subprocess.DEVNULL, check=True, timeout=120)
    tools = read_json(doctor)["tools"]
    for name, sha in expected["tools"].items():
        require(tools[name]["available"] and tools[name]["sha256"] == sha, f"Unexpected tool {name}")
    inputs = attempt / "recovered"
    manifest = inputs / "manifest.json"
    stage("prepare", [python, "infrastructure/prepare_recovered.py", "--source-root", str(ROOT),
                      "--ref", recovered, "--output", str(inputs)], [manifest, inputs / "provenance.json"])
    provenance = read_json(inputs / "provenance.json")
    require(provenance["source_commit"] == recovered, "Wrong reconstruction source")
    for name, sha in provenance["sha256"].items():
        path = phase4 / "what_a_piece_of_work-noisy.wav" if name == "input_wav_sha256" else inputs / name
        require(path.resolve().is_relative_to(attempt) or path.parent == phase4, "Invalid reconstruction path")
        require(file_hash(path) == sha, f"Reconstruction input changed: {name}")

    def build_files(folder):
        return [folder / "report.json", folder / "fpga-build/build-summary.json",
                folder / "fpga-build/bitstream.bin", folder / "fpga-build/roundtrip.bin"]

    run = attempt / "validation"
    repeat = attempt / "repeat"
    stage("validate", [*runner, "validate", "--manifest", str(manifest), "--output", str(run)],
          [*build_files(run), run / "unit-tests.log", run / "junit.xml"])
    report = read_json(run / "report.json")
    require(report["passed"] and report["metadata"]["git_head"] == pinned
            and report["metadata"]["manifest_sha256"] == file_hash(manifest), "Invalid clean baseline report")
    cases = {item["name"]: item for item in report["cases"]}
    counts = expected["sample_counts"]
    require(set(cases) == set(counts) | {"fpga-build"}, "Unexpected regression coverage")
    for name, count in counts.items():
        require(cases[name]["status"] == "passed" and cases[name]["detail"] == f"{count} samples, max error 0",
                f"Unexpected result for {name}")
    stage("repeat-build", [*runner, "build", "--manifest", str(manifest), "--output", str(repeat)],
          build_files(repeat))
    summaries = [read_json(folder / "fpga-build/build-summary.json") for folder in (run, repeat)]
    for folder, summary in zip((run, repeat), summaries):
        require(summary["passed"] and summary["constrained_pins"] and summary["seed"] == 1
                and summary["frequency_mhz"] == 10 and summary["fmax"]
                and all(clock["achieved"] >= clock["constraint"] for clock in summary["fmax"].values()),
                "Invalid clean FPGA build metrics")
        require(all(file_hash(path) == expected["expected_bitstream_sha256"] for path in build_files(folder)[2:]),
                "Clean baseline bitstream differs from the pinned result")
    evidence = {
        "status": "passed", "evidence_type": "executed_clean_baseline",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": pinned, "reconstruction_commit": recovered,
        "python_version": sys.version.split()[0], "git_version": run_key["git"],
        "suite_release": expected["suite_release"], "tool_sha256": expected["tools"],
        "sample_counts": counts, "sample_total": sum(counts.values()), "max_error": 0,
        "framework_tests": "passed", "nextpnr_fmax_mhz": min(x["achieved"] for x in summaries[0]["fmax"].values()),
        "constraint_mhz": summaries[0]["frequency_mhz"], "logic_cells": summaries[0]["utilization"]["ICESTORM_LC"],
        "bitstream_sha256": expected["expected_bitstream_sha256"], "bitstream_repeat_and_roundtrip": "passed",
        "physical_hardware": "not_run",
    }
    publish(output / "clean-baseline.json", json_bytes(evidence))
    print(f"Clean baseline passed with {evidence['sample_total']} exact sample comparisons.")


def package(config, args, reports):
    from release_package import build_package
    build_package(config, args, reports)


def main():
    global CONFIG_PATH
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("baseline", "evaluate-candidates", "validate-selected", "package", "full"):
        mode.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--baseline-worktree", type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--selected-suite", type=Path, help="Quality-review OSS CAD Suite, independently pinned from the clean baseline")
    parser.add_argument("--output", type=Path, default=ROOT / ".state/phase-08-cycle-03")
    parser.add_argument("--resume", type=Path, help="Resume a baseline attempt with verified checkpoints")
    parser.add_argument("--resume-selected", type=Path, help="Resume a selected-candidate attempt with verified evidence")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--transcript-root", type=Path, help="Private prepared transcript export directory")
    parser.add_argument("--strict", action="store_true", help="Return nonzero if official submission requirements remain open")
    parser.add_argument("--stages", default="baseline,evaluate,selected,package",
                        help="Ordered subset for --full: baseline,evaluate,selected,package")
    args = parser.parse_args()
    if args.resume and not (args.baseline or args.full):
        parser.error("--resume requires --baseline or --full")
    if args.resume_selected and not (args.validate_selected or args.full):
        parser.error("--resume-selected requires --validate-selected or --full")
    try:
        CONFIG_PATH = args.config.resolve()
        config = read_json(CONFIG_PATH)
        require(config["schema_version"] == 1, "Unknown configuration version")
        args.output = args.output.resolve()
        args.output.mkdir(parents=True, exist_ok=True)
        stages = args.stages.split(",") if args.full else []
        require(len(stages) == len(set(stages)) and set(stages) <= {"baseline", "evaluate", "selected", "package"},
                "Invalid full-workflow stage list")
        if args.full:
            for name in stages:
                if name == "baseline":
                    baseline(config, args, args.output)
                elif name == "selected":
                    selected(config, args, args.output)
                elif name == "evaluate":
                    audit(config, args.output)
                else:
                    package(config, args, audit(config, args.output))
            return 0
        if args.baseline:
            baseline(config, args, args.output)
        if not args.baseline:
            reports = audit(config, args.output)
            if args.validate_selected:
                selected(config, args, args.output)
            if args.package:
                package(config, args, reports)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
