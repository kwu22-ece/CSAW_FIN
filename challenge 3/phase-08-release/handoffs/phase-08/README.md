# Phase 8 improved-candidate reproduction

Run from the release worktree with Python 3.11 or later and Git. The clean baseline uses Windows x64 OSS CAD Suite 2026-11-12. The selected quality revision uses OSS CAD Suite 2026-09-13. Both executable sets are independently hash-pinned. The bundled `lib/python3.exe` works on this host.

| Command | Behavior |
|---|---|
| `python reproduce.py --baseline` | Reconstruct and validate the clean Phase 2 audio design, then repeat its FPGA build |
| `python reproduce.py --evaluate-candidates` | Verify saved independent candidate records, the latest selection, and the selected improvement lineage |
| `python reproduce.py --validate-selected` | Execute the selected improvement's quality suite, repeated build, and continuous-audio simulation from immutable Git snapshots |
| `python reproduce.py --package --transcript-root PRIVATE_EXPORT` | Verify execution receipts, preserve development history, and create the local submission ZIP |
| `python reproduce.py --full --transcript-root PRIVATE_EXPORT` | Run baseline, saved candidate evaluation, selected validation, and packaging |

Use `--config PATH` for another reviewed configuration, `--suite PATH` or `OSS_CAD_SUITE` for the clean-baseline suite, `--selected-suite PATH` or `SELECTED_OSS_CAD_SUITE` for the quality suite, and `--baseline-worktree PATH` for a Phase 4 worktree at the pinned baseline. The quality suite defaults to `~/oss-cad-suite` and must pass all pinned executable hashes before use. Git worktree registration supplies candidate environment locations. Model and environment labels are carried in the configuration and source manifests. The original four candidate SHAs stay pinned independently of the selected improvement.

`--full --stages evaluate,selected,package` runs an ordered subset. Saved evaluation and package creation require no AI credentials. A fresh AI development run additionally requires each environment's CLI or API, an available model, credentials and external resources. No verified common generation entry point was found.

Outputs default to `.state/phase-08-cycle-03`. Each baseline or selected run prints a fresh attempt directory. `--resume PATH` resumes a baseline attempt. `--resume-selected PATH` resumes a selected attempt. A checkpoint is reusable only when its configuration, driver, runtime, toolchain and evidence hashes pass. Failed stages with partial output require a fresh attempt. The selected run checkpoints its complete existing quality suite, repeat build, and continuous-audio stage.

Create the private visible-interaction export with `python release_transcripts.py --plan PRIVATE_PLAN.json --output PRIVATE_EXPORT`. The plan is a JSON array of `phase`, `path`, and optional `expected_sha256` entries. Packaging verifies export hashes and requires records for all four candidates and the quality revision. Its readiness audit still requires closed-session completeness review.

The ZIP contains the selected source tree, top-level RTL and serial bench, source constraints, Cycle 005 selection evidence, executed verification evidence, an offline Git bundle preserving the four histories, available visible AI records, the Phase F AI-provenance summary, and the separate 05BB experiment. It is private local output. `--strict` returns failure while official submission requirements remain open, after retaining the verified archive and audit.
