# CSAW 2026 Challenge 3 submission draft

The primary implementation is the independently selected 05B quality revision `fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6`. The current 05S-005 checkpoint reconfirmed that source without silently replacing its RTL; it adds clock-drift, release-overlay and provenance evidence. This archive includes source, simulation and build evidence, AI interaction exports, Phase F provenance summaries and development history. Physical Hackster evidence and reviewed judge-channel raw-transcript delivery remain open.

The original bitstream was unpacked and reconstructed with IceStorm, then compared against a software reference and serial testbench. The recovered filter is a symmetric 63-tap Q1.15 FIR with signed 16-bit samples, rounding and saturation. The serial interface uses Philips I2S and a two-frame output latency. The application processor supplies BCLK and word select, while the FPGA samples the interface using its 10 MHz system clock. BCLK is limited to 1 MHz in the documented interface. The clean recovered implementation and reference models are preserved in the Git history.

Four independent model environments produced candidates from baseline `e72522f265ac36da713cd7a0dcf8dbc64ab21209`. The requested labels were Luna 5.6, Astra, Claude Opus Architecture and Claude Opus DSP. Runtime evidence is retained independently of these labels. Original 05B records identify `gpt-6-luna`; its subsequent quality work identifies `gpt-6-astra`. The release workflow reuses the deterministic scripts authored in those phases. The AI exports include visible user prompts, assistant responses and tool interactions, with recorded credential redactions and source hashes.

The selected design recognizes the exact left-channel sequence `7F00 8101 5A3C A5C3 6D92 926D C33C 3CC3`. Starting with the final trigger sample, it passes raw input through the left output for 128 frames. The FIR continues computing and normal filtering resumes after the bounded window. The right-channel echo and two-frame latency are preserved. The accepted quality change corrected recognition of the first eligible trigger sample after this window. Directed tests cover both sides of the boundary and altered or misplaced trigger words.

The root `rtl/` directory contains the selected top, adapter and Hackster constraints. The complete runnable layout is under `selected/`. The `tb/` directory contains the serial bench. Fresh simulation captures and build outputs are under `evidence/`. The expected selected bitstream hash is `2742912e31ec6c058756e5623d84736285dc2d46695d8ece616494e3152a89b0`. Historical source README metrics refer to earlier candidate revisions.

To reproduce from the archive without access to GitHub, clone the bundled history and select the release branch:

```text
git clone history/development.bundle reproduction
git -C reproduction switch codex/challenge3-phase-08-release
git -C reproduction worktree add --detach ../phase04 e72522f265ac36da713cd7a0dcf8dbc64ab21209
cd reproduction
python reproduce.py --evaluate-candidates
python reproduce.py --validate-selected --selected-suite ABSOLUTE_QUALITY_SUITE
python reproduce.py --baseline --baseline-worktree ../phase04 --suite ABSOLUTE_BASELINE_SUITE
```

Python 3.11+ and Git are required. The clean baseline uses Windows x64 OSS CAD Suite 2026-11-12. Exact selected bitstream reproduction uses the quality review's OSS CAD Suite 2026-09-13, including Yosys 0.69+24 and nextpnr 0.11.1-26. Executable hashes are pinned separately in the release configuration. The Phase 4 bootstrap script and pinned download checksum are in the baseline worktree. Simulation and build reproduction requires no AI service. The selected command exports the pinned source, runs the existing quality suite, repeats synthesis and routing, and runs uninterrupted audio. Its standard activation tests supply the trigger and compare captured serial output with the expected 128-frame behavior.

Physical-board demonstration is pending. The `official/` directory preserves the supplied programming and streaming utilities and interface documentation. A future physical receipt must identify the actual device, programmed bitstream hash, input/output captures, normal-operation comparison and activation observation. The available evidence currently supports digital simulation and FPGA build claims.

The `ai/index.json` records transcript sources, raw snapshot hashes, visible-record exports, runtime model identifiers, credential redaction counts and capture cutoff. `ai-provenance/` adds the hash-verified Phase F model list and transcript-provenance summary. The Phase F source manifest has nine stale entries; those artifacts are deliberately excluded and named in `remediation/manifest-integrity.json`. Available records span all four candidate attempts and later project phases; raw transcripts remain a reviewed private judge-channel deliverable.

The `history/development.bundle` retains all four candidate branches and the selected improvement lineage. Candidate implementations remain independent. The `optional/05BB/` directory contains a separately validated synthetic-message experiment and its archived simulation evidence. Its `CSAW26-BONUS-B` message, measured rates and error counts refer to simulation. It has its own RTL and is not part of the primary selected build.

See `requirements-audit.json`, `evidence/selected-validation.json`, and `archive-manifest.json` for readiness, execution and content-hash records. No official score or complete physical submission is claimed.
