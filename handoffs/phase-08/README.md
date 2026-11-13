# Phase 8 reproduction and evidence

Run from the Phase 8 release worktree with Python 3.11 or later and Git. On this Windows host, use the pinned OSS CAD Suite's `lib/python3.exe` if `python` resolves to the Store alias.

| Command | Result |
|---|---|
| `python reproduce.py --baseline` | Fresh clean audio reconstruction, regression, FPGA build, and repeat-build verification |
| `python reproduce.py --evaluate-candidates` | Verify the four saved Phase 5 records and report their original ranks and gates |
| `python reproduce.py --validate-selected` | Cross-check the selection and quality-review manifests and verify the selected revision's Git ancestry |
| `python reproduce.py --package` | Verify saved provenance and create a local engineering evidence ZIP |
| `python reproduce.py --full` | Run the clean baseline, verify saved provenance, and create the evidence ZIP |

The commands use Git commit objects already present in the local repository. The clean baseline discovers the registered Phase 4 worktree and its suite by default. Use `--baseline-worktree` and `--suite` to specify their locations. `OSS_CAD_SUITE` also selects the suite. The exact executable hashes are pinned for Windows x64 OSS CAD Suite 2026-11-12. This workflow requires no model credentials.

Outputs default to `.state/phase-08`. Use `--output` to choose another directory. A baseline attempt prints its directory at startup. Use `--baseline --resume PATH` or `--full --resume PATH` to reuse successful checkpoints after the driver, configuration, toolchain and evidence checks pass. Start a fresh attempt when a failed stage leaves partial outputs. Every fresh attempt keeps its own logs.

The evidence ZIP is for local engineering review. The official competition archive and physical Hackster validation remain open.
