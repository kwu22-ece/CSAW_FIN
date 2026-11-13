# Challenge 3 — Phase 8 Release

This directory contains the reproducible Phase 8 workflow and reviewed handoffs for the current 05S-005 selection checkpoint.

The selected implementation remains candidate 05B at commit `fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6`. The four original candidates and the common baseline are pinned in `handoffs/phase-08/reproduction.json`; the latest selection and quality receipts are included under `handoffs/`.

## Reproduction

Run from this directory with Python 3.11+ and Git:

```text
python reproduce.py --evaluate-candidates
python reproduce.py --baseline --baseline-worktree PATH --suite PATH
python reproduce.py --validate-selected --selected-suite PATH
python reproduce.py --package --transcript-root PRIVATE_EXPORT
```

The baseline and selected validation use separately pinned OSS CAD Suite installations. Their executable hashes and expected build outputs are in the configuration. Completed checkpoints can be resumed with `--resume` or `--resume-selected`. Candidate evaluation reuses saved results and does not start AI generation.

`submission.zip`, execution logs, private interaction exports, and local Scribe state are intentionally not committed. Create the competition archive locally after providing a reviewed transcript export; see `handoffs/phase-08/README.md` and `submission-README.md`.

## Current verification and open requirements

The verified run passed the clean baseline (8,224 exact comparisons) and selected candidate (47 simulations, 15 framework tests, repeat FPGA builds, and continuous audio). The submission archive is structurally verified, but official readiness remains open for physical Hackster evidence, reviewed private raw-transcript delivery and direct 05B authorship review, and correction of nine stale hashes in the Phase F source manifest. No official score is claimed.

The official challenge materials are maintained in the [CSAW AI Hardware Attack Challenge 2026 repository](https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026).
