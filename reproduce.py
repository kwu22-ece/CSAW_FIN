"""Run the clean FIR baseline and verify saved Challenge 3 evidence."""
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
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

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
    require(selection["schema_version"] == quality["schema_version"] == 1, "Unknown receipt version")
    require(selection["common_baseline_commit_sha"] == quality["baseline_sha"] == baseline,
            "Receipts disagree on the pinned baseline")
    rows = selection["ranking"]
    require({row["candidate_id"] for row in rows} == set(config["candidates"])
            and sorted(row["rank"] for row in rows) == [1, 2, 3, 4], "Invalid saved ranking")
    candidates = {}
    attached = worktrees()
    for row in sorted(rows, key=lambda item: item["rank"]):
        key = row["candidate_id"]
        candidate = config["candidates"][key]
        sha = commit(candidate["snapshot"])
        require(row["snapshot_sha"] == sha, f"Saved result has the wrong snapshot for {key}")
        ancestor(baseline, sha)
        gates = selection["candidate_results"][key]["gate_results"]
        saved = {name: gates[name] for name in GATES}
        require(set(saved.values()) <= SAFE_GATE_VALUES, f"Unrecognized gate status for {key}")
        candidates[key] = {
            "candidate_id": key, "model": candidate["model"], "environment": candidate["environment"],
            "branch": candidate["branch"], "source_commit": sha, "baseline_commit": baseline,
            "registered_worktree": candidate["branch"] in attached,
            "saved_rank": row["rank"], "saved_gates": saved, "execution": "saved_evidence_only",
        }
    selected = selection["winner"]["candidate_id"]
    original = candidates[selected]["source_commit"]
    require(rows[0]["candidate_id"] == selected and rows[0]["rank"] == 1
            and selection["winner"]["immutable_package_commit_sha"] == original
            and quality["selected_candidate_id"] == selected
            and quality["original_selected_candidate_sha"] == original
            and quality["selection_manifest_commit_sha"] == config["selection_commit"],
            "Selection and quality-review receipts disagree")
    best = commit(quality["current_best_known_sha"])
    fix = commit(quality["implementation_fix_sha"])
    ancestor(original, fix)
    ancestor(fix, best)
    ancestor(best, config["quality_review_commit"])
    reports = {
        "selection.json": {
            "selected_candidate": selected, "selection_commit": config["selection_commit"],
            "selection_receipt_sha256": selection_hash, "source_commit": original,
            "baseline_commit": baseline, "status": selection["status"],
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
    print(f"Verified four saved candidate records, selection {selected}, and quality revision {best[:12]}.")
    return reports


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


def package(output, reports):
    members = {name: json_bytes(report) for name, report in reports.items()}
    for name in DOCS:
        contents = (HANDOFF / name).read_bytes()
        require(contents.strip(), f"Missing documentation content: {name}")
        members[name] = contents
    baseline_path = output / "clean-baseline.json"
    if baseline_path.is_file():
        evidence = read_json(baseline_path)
        require(evidence["status"] == "passed" and evidence["evidence_type"] == "executed_clean_baseline",
                "Invalid baseline evidence summary")
        members["clean-baseline.json"] = json_bytes(evidence)
    members["archive-manifest.json"] = json_bytes({
        "archive_type": "engineering_evidence", "official_submission": False,
        "sha256": {name: digest(contents) for name, contents in members.items()},
    })
    archive = output / "phase08-engineering-evidence.zip"
    with tempfile.NamedTemporaryFile(dir=output, delete=False) as stream:
        staged = Path(stream.name)
    try:
        with ZipFile(staged, "w", compression=ZIP_DEFLATED) as zip_file:
            for name, data in sorted(members.items()):
                zip_file.writestr(ZipInfo(name), data, compress_type=ZIP_DEFLATED)
        with ZipFile(staged) as zip_file:
            require(zip_file.testzip() is None and zip_file.namelist() == sorted(members)
                    and all(zip_file.read(name) == data for name, data in members.items()),
                    "Archive verification failed")
        staged.replace(archive)
    finally:
        staged.unlink(missing_ok=True)
    print(f"Verified {archive} (SHA-256 {file_hash(archive)})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ("baseline", "evaluate-candidates", "validate-selected", "package", "full"):
        mode.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--baseline-worktree", type=Path)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / ".state/phase-08")
    parser.add_argument("--resume", type=Path, help="Resume a baseline attempt with verified checkpoints")
    args = parser.parse_args()
    if args.resume and not (args.baseline or args.full):
        parser.error("--resume requires --baseline or --full")
    try:
        config = read_json(CONFIG_PATH)
        require(config["schema_version"] == 1, "Unknown configuration version")
        args.output = args.output.resolve()
        args.output.mkdir(parents=True, exist_ok=True)
        if args.baseline or args.full:
            baseline(config, args, args.output)
        if not args.baseline:
            reports = audit(config, args.output)
            if args.validate_selected:
                print("Selected revision verified by provenance. Candidate execution and physical signoff are open.")
            if args.package or args.full:
                package(args.output, reports)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
