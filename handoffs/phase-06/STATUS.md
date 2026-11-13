# Challenge 3 Phase 6 verification handoff

- Date and agent — November 13, 2026, Codex build and verification.
- Validation branch — `codex/challenge3-phase-06-validation`, based on Phase 4 commit `e72522f265ac36da713cd7a0dcf8dbc64ab21209`.
- Engineering ownership — `handoffs/phase-06/` and the local Phase 6 build outputs. Candidate RTL, manifests, and branches were preserved.
- Disposition — 05B selection confirmed. Candidate signoff withheld. Clean recovered audio baseline verified in simulation and through bitstream generation.

## Candidate provenance

Phase 5S selected 05B package commit `9e172a865a543b03e226596689fd6691ffa2b779`. The selection JSON is in commit `6d9cacf4e12a7f2357c4f36fa91d9ef87429d046`. The Subphase Q worktree points to the same package and its selection-provenance record points to the same selection JSON. No `handoffs/quality-review/current-best.json` or verified replacement was found in the local Git history or worktrees.

The candidate commit exists. Its RTL tree matches the recorded origin `15a8a6525e225ad82d931b3bc75399f744638b2e`. All 33 distinct paths declared as primary manifest simulation, build, case, or evidence inputs exist at the package SHA. Static module inventory found the declared `fir_audio_top` and both adapter modules. Candidate elaboration, regression, synthesis, place-and-route, bitstream generation, and board checks were not executed. The RTL implements a deliberately hidden filter bypass.

The manifest and its independent receipt declare the same 35 file hashes. Nine match raw Git blobs. Twenty-three more match after converting line endings to CRLF, as does the manifest digest itself. Three still fail, including the synthesis RTL. The package therefore fails its recorded source hash gate. `build/phase06-provenance.json` preserves the per-file audit. [Open issue](candidate-provenance-issue.md).

## Clean baseline verification

The Phase 4 audio-only integration was run against its unchanged Phase 2 reconstruction and software reference from `1befb30e99a506698c45d4ca9394a3c7ec95c966`. The baseline comparison used signed 16-bit words, zero tolerance, and zero post-comparison alignment adjustment.

| Check | Status | Evidence |
|---|---|---|
| Framework suite, restricted process | Failed | 15 ran, 4 errors associated with Icarus access violation `3221225477`. Preserved in `build/phase06-baseline-a/unit-tests.log`. |
| Framework suite, ordinary process | Passed | 15/15 after the environment retry. |
| Supplied golden vectors | Passed | 516 words each at 1 MHz and 625 kHz BCLK, zero mismatches. |
| Software reference | Passed | 5 synthetic cases of 1,028 words each and 2,052 words from the noisy WAV case, zero mismatches. |
| Synthesis and routing | Passed | UP5K/SG48, 10 MHz, seed 1. Icarus compiled/elaborated the simulation top. Yosys `hierarchy -check` and `check -assert` passed. |
| Timing | Passed | nextpnr 14.016 MHz. IceStorm icetime 13.69 MHz, 73.04 ns path delay against a 100 ns constraint. |
| Resources | Passed | 3,179/5,280 logic cells (60.2%), 3/8 global buffers, 5/39 I/O, 0/8 DSP, 0/30 RAM, 0/4 SPRAM. |
| Bitstream repeat and round trip | Passed | Two fresh builds and the pack/unpack/repack comparison produced the same SHA-256. |
| Physical hardware | Not executed | Host device inventory did not identify a Hackster programmer. No device programmed. Board audio, LED behavior, and external I/O timing remain unverified. |

The 104,090-byte clean baseline bitstream is `build/phase06-baseline-b/fpga-build/bitstream.bin` with SHA-256 `5eba9279b177b8859ceea0bd5c685c9ac442a50414906792711626c1b2a38fda`. The build uses the Phase 4 five-pin audio constraints. The two golden cases and six model cases total 8,224 exact comparisons.

## Reproduction

Run from the validation worktree in PowerShell. The commands assume the adjacent Phase 4 worktree has its pinned OSS CAD Suite 2026-11-12 Windows x64 installation. The root Git object database must contain the Phase 2 source SHA. Use ordinary Windows process execution if Icarus fails inside a restricted shell. Each output directory must be fresh.

```powershell
$suite = (Resolve-Path '../phase-04/.tools/oss-cad-suite').Path
$python = Join-Path $suite 'lib/python3.exe'
$root = (Resolve-Path '../..').Path

& $python infrastructure/run.py --suite $suite doctor --output build/phase06-toolchain.json
& $python infrastructure/prepare_recovered.py --source-root $root --ref 1befb30e99a506698c45d4ca9394a3c7ec95c966 --output build/phase06-baseline-inputs
& $python infrastructure/run.py --suite $suite validate --manifest build/phase06-baseline-inputs/manifest.json --output build/phase06-baseline-b
& $python infrastructure/run.py --suite $suite build --manifest build/phase06-baseline-inputs/manifest.json --output build/phase06-baseline-repeat
Get-FileHash -Algorithm SHA256 -LiteralPath 'build/phase06-baseline-b/fpga-build/bitstream.bin','build/phase06-baseline-repeat/fpga-build/bitstream.bin','build/phase06-baseline-b/fpga-build/roundtrip.bin'
```

Python 3.11.6, Git 2.54.0.windows.1, Icarus and vvp 14.0 devel (`s20260301-972-g5bbcab257-dirty`), Yosys 0.70+385 (`098e46a36`), and nextpnr `0.11.1-91-gf934534a` were used. The IceStorm executables expose help. `build/phase06-toolchain.json` identifies them by executable SHA-256. `build/phase06-baseline-inputs/provenance.json` records exact Phase 2 input bytes. Both run directories contain `report.json`, `junit.xml`, and `*.log.json` command receipts with argv, working directory, exit status, and log SHA-256. Their `fpga-build/` subdirectories contain `build-summary.json`, `timing.json`, `icetime.txt`, and `utilization.json`. `artifact-hashes.json` indexes the key local evidence outputs.

## Documentation and delivery

Project Scribe recorded the successful validation as `phase06-clean-baseline` with exit 0 and stable tracked state. A Phase 6-only controller configuration was used because the shared configuration failed Git root resolution for the external 05B worktree. The local evidence preview includes this handoff. External publishing remains disabled.

The validation branch and build outputs are local. No public artifact upload was made. The Phase 5S package remains selected provisionally, and its source hash failure is open. No Phase 6 candidate signoff or physical validation receipt was issued.
