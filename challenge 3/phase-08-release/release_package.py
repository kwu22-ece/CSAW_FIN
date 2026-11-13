"""Build and verify a private competition archive from pinned source and receipts."""
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from reproduce import (ROOT, HANDOFF, CONFIG_PATH, DOCS, commit, digest, file_hash, git,
                       json_bytes, publish, read_json, read_receipt, require, snapshot,
                       tree_hashes, verify_files)
from release_transcripts import TOKEN

SECRET_PATH = re.compile(r"(^|/)(\.env(?:\.[^/]*)?|config\.json|[^/]*(?:credentials|service-account|refresh-token)[^/]*\.json|[^/]+\.(?:pem|key))$", re.I)
HISTORY_BRANCHES = (
    "challenge3/02-reverse-engineering", "challenge3/03-baseline", "challenge3/04-infrastructure",
    "challenge3/05a-luna", "challenge3/05b-astra", "challenge3/05c-opus-architecture",
    "challenge3/05d-opus-dsp", "challenge3/quality-winner", "challenge3/05s-selection",
    "challenge3/05s-cycle-02", "challenge3/05s-cycle-05", "challenge3/05bb-bonus-b",
    "codex/challenge3-phase-06-validation", "codex/challenge3-final-report-agent",
    "challenge3/phase-f-remediation", "codex/challenge3-phase-08-release",
)
REVIEWED_REDACTION_FIXTURE = "3a9a886ee15a06ecd5b885117e69719f033002fac6666978cc166a795606bfef"


def check_publication_bytes(name, data):
    require(not SECRET_PATH.search(name), f"Credential filename requires review: {name}")
    # This exact existing Scribe unit-test blob supplies synthetic secrets to its redactor.
    if name == "DocumentAgent/openclaw-project-scribe/test/scribe.test.mjs" and digest(data) == REVIEWED_REDACTION_FIXTURE:
        return
    if b"\0" not in data:
        require(not TOKEN.search(data.decode("utf-8", errors="replace")),
                f"Credential pattern requires review: {name}")


def history_bundle(config, staging):
    """Preserve reachable history, including every frozen candidate snapshot."""
    refs = {}
    for branch in HISTORY_BRANCHES:
        refs["refs/heads/" + branch] = git("rev-parse", "refs/heads/" + branch).strip()
    for name, sha in (("challenge3/04-infrastructure", config["baseline_commit"]),
                      ("challenge3/05s-cycle-05", config["selection_commit"]),
                      ("challenge3/phase-f-remediation", config["remediation_commit"]),
                      ("challenge3/05bb-bonus-b", config["bonus_commit"])):
        require(refs["refs/heads/" + name] == sha, f"History branch advanced. Refresh configuration: {name}")
    objects = git("rev-list", "--objects", *refs.values()).splitlines()
    identifiers = {row.split(" ", 1)[0]: row.split(" ", 1)[1] if " " in row else "" for row in objects}
    request = staging / "history-objects.txt"
    request.write_text("\n".join(identifiers) + "\n")
    scanned = 0
    with request.open("rb") as stream:
        process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=stream,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for oid in identifiers:
                header = process.stdout.readline().split()
                require(len(header) == 3 and header[0].decode() == oid, "Git object stream failed")
                data = process.stdout.read(int(header[2]))
                require(process.stdout.read(1) == b"\n", "Truncated Git object stream")
                if header[1] == b"blob":
                    check_publication_bytes(identifiers[oid], data)
                    scanned += 1
            require(process.wait(timeout=120) == 0, "History scan failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    bundle = staging / "development.bundle"
    subprocess.run(["git", "-c", "pack.threads=1", "bundle", "create", str(bundle), *refs],
                   cwd=ROOT, check=True, timeout=240)
    with (staging / "bundle-verification.log").open("wb") as log:
        subprocess.run(["git", "bundle", "verify", str(bundle)], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    current = {ref: git("rev-parse", ref).strip() for ref in refs}
    require(current == refs, "Branch changed while preserving history")
    return bundle, {"refs": refs, "scanned_git_blobs": scanned, "bundle_sha256": file_hash(bundle),
                    "credential_pattern_scan": "passed", "private_submission_artifact": True,
                    "reviewed_test_fixture_sha256": REVIEWED_REDACTION_FIXTURE}


def manifest_file_status(root, relative_manifest):
    """Classify Phase F manifest files without admitting mismatched evidence."""
    manifest_path = (root / relative_manifest).resolve()
    require(manifest_path.is_relative_to(root.resolve()) and manifest_path.is_file(),
            "Remediation manifest is missing")
    manifest = read_json(manifest_path)
    require(manifest.get("schema_version") == 1 and manifest.get("phase") == "F"
            and manifest.get("cycle") == 2 and isinstance(manifest.get("files"), list),
            "Unexpected remediation manifest")
    files = {}
    rejected = []
    for entry in manifest["files"]:
        name = entry.get("path")
        require(isinstance(name, str) and name not in files
                and name not in {item["path"] for item in rejected}, "Invalid remediation manifest entry")
        path = (root / name).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file(),
                f"Remediation evidence changed or missing: {name}")
        actual = {"path": name, "declared_bytes": entry.get("bytes"),
                  "declared_sha256": entry.get("sha256"), "actual_bytes": path.stat().st_size,
                  "actual_sha256": file_hash(path)}
        if actual["actual_bytes"] == actual["declared_bytes"] and actual["actual_sha256"] == actual["declared_sha256"]:
            files[name] = path
        else:
            rejected.append(actual)
    return manifest, files, rejected


def verified_manifest_files(root, relative_manifest):
    """Return every manifest file only when the source manifest is complete."""
    manifest, files, rejected = manifest_file_status(root, relative_manifest)
    if rejected:
        raise ValueError(f"Remediation evidence changed or missing: {rejected[0]['path']}")
    return manifest, files


def selected_evidence(config, output, configuration_path=None):
    evidence = read_json(output / "selected-validation.json")
    require(evidence["status"] == "passed" and evidence["selected_commit"] == config["selected_commit"],
            "Run --validate-selected for the pinned candidate before packaging")
    if configuration_path is not None:
        require(evidence["config_sha256"] == file_hash(configuration_path), "Validation configuration changed")
    attempt = (output / evidence["attempt"]).resolve()
    require(attempt.parent == output.resolve(), "Invalid selected evidence directory")
    verify_files(attempt, evidence["checkpoint_sha256"])
    for name, directory in (("quality-suite.json", "quality"), ("repeat-build.json", "repeat"),
                            ("continuous-audio.json", "continuous")):
        receipt = read_json(attempt / name)
        require(receipt["exit_code"] == 0, f"Failed checkpoint {name}")
        verify_files(attempt / directory, receipt["outputs"])
    require(file_hash(attempt / "toolchain.json") == evidence["toolchain_sha256"], "Toolchain receipt changed")
    return evidence, attempt


def build_package(config, args, reports):
    output = args.output.resolve()
    evidence, attempt = selected_evidence(config, output, args.config.resolve())
    require(args.transcript_root is not None, "Supply --transcript-root with a reviewed local interaction export")
    transcript_root = args.transcript_root.resolve()
    transcripts = read_json(transcript_root / "index.json")
    phases = {entry["phase"] for entry in transcripts["entries"] if entry["visible_records"] > 0}
    require({"05A", "05B", "05C", "05D", "quality"} <= phases, "Transcript export lacks an original candidate or quality session")
    for entry in transcripts["entries"]:
        verify_files(transcript_root, {entry["file"]: entry["export_sha256"]})

    staging = Path(tempfile.mkdtemp(prefix="package-", dir=output))
    source = snapshot(config["selected_commit"], staging / "selected")
    evaluation = snapshot(config["selection_commit"], staging / "evaluation")
    remediation = snapshot(config["remediation_commit"], staging / "remediation")
    remediation_manifest, remediation_files, remediation_rejected = manifest_file_status(
        remediation, "handoffs/phase-f/manifest.json")
    provenance_core = {"submission/ai-provenance/PROVENANCE.md",
                       "submission/ai-provenance/README.md",
                       "submission/ai-provenance/model-list.json"}
    require(provenance_core <= set(remediation_files), "Core Phase F provenance summary is not hash-verified")
    bonus = snapshot(config["bonus_commit"], staging / "bonus")
    python = sys.executable
    verify = bonus / "experiments/phase05/05bb-bonus-b/tools/verify_package.py"
    with (staging / "bonus-verification.log").open("wb") as log:
        subprocess.run([python, "-B", str(verify)], cwd=bonus, stdout=log,
                       stderr=subprocess.STDOUT, check=True, timeout=120)
    bonus_handoff, _ = read_receipt(config["bonus_commit"], "handoffs/phase-05/bonus-b.json")
    bonus_dir = bonus / "experiments/phase05/05bb-bonus-b"
    require(file_hash(bonus_dir / "verification-evidence.zip") == bonus_handoff["evidence_archive"]["sha256"],
            "Bonus evidence archive differs from its handoff")
    history, history_info = history_bundle(config, staging)
    members = {}

    def add(name, data):
        require(name not in members and not PurePosixPath(name).is_absolute()
                and ".." not in PurePosixPath(name).parts and "\\" not in name, "Unsafe or duplicate archive name")
        contents = data.read_bytes() if isinstance(data, Path) else data
        check_publication_bytes(name, contents)
        members[name] = contents

    package_dir = source / "experiments/phase05/05b-astra"
    # Preserve the canonical source layout for all existing relative-path scripts.
    for name in tree_hashes(source):
        if name.startswith(("infrastructure/", "experiments/quality/", "handoffs/")) or (
                name.startswith("experiments/phase05/05b-astra/") and "/reports/" not in name) or name.endswith(".wav"):
            add("selected/" + name, source / name)
    for path in (package_dir / "rtl").glob("*"):
        if path.is_file():
            add("rtl/" + path.name, path)
    add("rtl/hackster.pcf", package_dir / "constraints/hackster.pcf")
    for path in (source / "infrastructure/hdl").glob("*.sv"):
        add("tb/" + path.name, path)
    add("tb/README.md", b"Run the frozen test and model scripts from selected/ using the reproduction commands in README.md.\nThe serial testbench is tb_i2s.sv. The canonical adapter and candidate sources are in selected/experiments/phase05/05b-astra/rtl/.\n")

    for name in ("reproduce.py", "release_package.py", "release_transcripts.py"):
        add(name, ROOT / name)
    for name in DOCS:
        add("handoffs/phase-08/" + name, HANDOFF / name)
    add("handoffs/phase-08/reproduction.json", args.config.resolve())
    add("handoffs/phase-08/candidate-manifest.schema.json", HANDOFF / "candidate-manifest.schema.json")
    add("handoffs/phase-08/submission-README.md", HANDOFF / "submission-README.md")
    add("handoffs/phase-08/documentation-receipt.json", HANDOFF / "documentation-receipt.json")
    for name in ("phase-05/selection.json", "quality-review/current-best.json"):
        add("handoffs/" + name, ROOT / "handoffs" / name)
    checkpoint = evaluation / "handoffs/phase-05/cycles" / config["selection_checkpoint"]
    require(checkpoint.is_dir(), "Selection checkpoint is missing from the frozen evaluation tree")
    for name in tree_hashes(checkpoint):
        add("handoffs/phase-05/cycles/" + config["selection_checkpoint"] + "/" + name,
            checkpoint / name)
    add("remediation/manifest.json", remediation / "handoffs/phase-f/manifest.json")
    add("remediation/manifest-integrity.json", json_bytes({
        "source_commit": config["remediation_commit"], "declared_entries": len(remediation_manifest["files"]),
        "included_verified_entries": len(remediation_files), "excluded_stale_entries": remediation_rejected,
        "policy": "Only files whose Phase F manifest bytes and SHA-256 match the frozen Git tree are packaged.",
    }))
    for name, path in remediation_files.items():
        prefix = "ai-provenance/" if name.startswith("submission/ai-provenance/") else "remediation/"
        archive_name = prefix + (name.removeprefix("submission/ai-provenance/")
                                 if prefix == "ai-provenance/" else name)
        add(archive_name, path)
    for name, report in reports.items():
        if name == "current-best.json":
            report = dict(report, phase8_validation="simulation_and_build_passed",
                          validation_receipt="evidence/selected-validation.json")
            publish(output / name, json_bytes(report))
        add("evidence/" + name, json_bytes(report))
    add("evidence/selected-validation.json", output / "selected-validation.json")
    add("evidence/toolchain.json", attempt / "toolchain.json")
    for checkpoint in evidence["checkpoint_sha256"]:
        add("evidence/checkpoints/" + checkpoint, attempt / checkpoint)
    for folder in ("quality", "repeat", "continuous"):
        for name in tree_hashes(attempt / folder):
            if name.startswith("source/") or name == "source.tar":
                continue
            add("evidence/" + folder + "/" + name, attempt / folder / name)
    for name in ("quality-suite.log", "repeat-build.log", "continuous-audio.log"):
        add("evidence/" + name, attempt / name)
    if (output / "clean-baseline.json").exists():
        clean = read_json(output / "clean-baseline.json")
        require(clean["status"] == "passed" and clean["baseline_commit"] == config["baseline_commit"],
                "Invalid clean baseline control")
        add("evidence/clean-baseline.json", output / "clean-baseline.json")
    add("demo/README.md", b"Physical Hackster demonstration is pending.\nThe evidence/ directory contains digital simulation captures, comparison receipts and FPGA build results.\nNo physical capture or board signoff is asserted.\n")
    add("history/development.bundle", history)
    add("history/index.json", json_bytes(history_info))
    for entry in transcripts["entries"]:
        add("ai/" + entry["file"], transcript_root / entry["file"])
    add("ai/index.json", transcript_root / "index.json")
    for name in tree_hashes(bonus_dir):
        if not name.endswith(".pyc"):
            add("optional/05BB/" + name, bonus_dir / name)
    add("optional/05BB/handoff.json", json_bytes(bonus_handoff))
    add("optional/05BB/verification.log", staging / "bonus-verification.log")
    # Inspect archived evidence as well as the outer ZIP.
    inventory = read_json(bonus_dir / "evidence-inventory.json")
    with ZipFile(bonus_dir / "verification-evidence.zip") as archive:
        require(set(archive.namelist()) == set(inventory["files"]), "Bonus archive contains unlisted entries")
        for name, sha in inventory["files"].items():
            data = archive.read(name)
            require(digest(data) == sha, f"Bonus artifact differs: {name}")
            check_publication_bytes(name, data)

    audit = {
        "selected_execution_at_utc": evidence["executed_at_utc"],
        "source": "https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026/blob/main/finals/challenge_3/README.md",
        "submission_ready": False, "archive_integrity": "passed",
        "selected_implementation": config["selected_commit"],
        "selection_checkpoint": config["selection_checkpoint"],
        "phase_f_manifest": {"declared_entries": len(remediation_manifest["files"]),
                             "included_verified_entries": len(remediation_files),
                             "excluded_stale_entries": len(remediation_rejected)},
        "requirements": {"modified_rtl": "included_and_built", "testbench_and_verification": "included_and_executed",
                         "technical_brief": "included", "four_histories": "included_in_git_bundle",
                         "ai_interactions": "sanitized_visible_sessions_and_verified_provenance_summary_included",
                         "physical_demonstration": "missing"},
        "open_items": ["Physical normal-operation and activation evidence",
                       "Judge-channel raw-transcript delivery and direct 05B transcript-to-RTL authorship review",
                       "Phase F source-manifest refresh for nine excluded stale-hash artifacts"],
        "score": {"official_total": None, "base_maximum": 100, "bonus_maximum": 30,
                  "hardware_points_supported": 0, "bonus_b": "simulation-only evidence; no official award claimed"},
        "bonus_b_validation": "saved_archive_and_source_hash_verification",
        "transcripts": {"sessions": len(transcripts["entries"]), "credential_redactions":
                        sum(e["credential_redactions"] for e in transcripts["entries"]),
                        "capture_cutoff": transcripts["captured_at_utc"],
                        "provenance_manifest": "ai-provenance/provenance-audit-results.json"},
    }
    add("requirements-audit.json", json_bytes(audit))
    brief = (HANDOFF / "submission-README.md").read_bytes()
    add("README.md", brief)
    add("official/challenge-README.md", bonus_dir / "official/challenge-README.md")
    add("official/ice40_audio_filter_IP.md", bonus_dir / "official/ice40_audio_filter_IP.md")
    for path in (bonus_dir / "official/tools").glob("*.py"):
        add("official/tools/" + path.name, path)
    for path in (bonus_dir / "official/fpga").iterdir():
        if path.is_file():
            add("official/fpga/" + path.name, path)
    add("archive-manifest.json", json_bytes({"schema_version": 1, "selected_commit": config["selected_commit"],
                                          "sha256": {name: digest(data) for name, data in members.items()}}))
    temporary = staging / "submission.zip"
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for name, data in sorted(members.items()):
            info = ZipInfo(name)
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=6)
    with ZipFile(temporary) as archive:
        require(archive.testzip() is None and archive.namelist() == sorted(members), "Archive members failed verification")
        for name, data in members.items():
            require(archive.read(name) == data, f"Archive bytes differ: {name}")
        require({"README.md", "rtl/fir_audio_top.v", "tb/tb_i2s.sv", "demo/README.md", "ai/index.json"} <= set(archive.namelist()),
                "Official directory layout incomplete")
    destination = output / "submission.zip"
    temporary.replace(destination)
    receipt = {"archive": destination.name, "sha256": file_hash(destination), "files": len(members),
               "selected_commit": config["selected_commit"], "integrity": "passed",
               "submission_ready": False, "history": history_info,
               "open_items": audit["open_items"]}
    publish(output / "requirements-audit.json", json_bytes(audit))
    publish(output / "package-verification.json", json_bytes(receipt))
    print(json.dumps({k: v for k, v in receipt.items() if k != "history"}, indent=2))
    if args.strict:
        raise ValueError("Archive verified. Official submission remains incomplete; see requirements-audit.json")
