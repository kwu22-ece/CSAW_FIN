# CSAW 2026 Challenge 3 - Candidate B (Astra Reliability)

This isolated candidate recognizes an exact left-channel sample sequence and bypasses the FIR output for 128 frames. The candidate RTL is based on the recovered Phase 3 audio design and uses the Phase 4 simulation and iCE40 build framework.

## Candidate behavior

The trigger is eight consecutive exact 16-bit left samples: `7F00 8101 5A3C A5C3 6D92 926D C33C 3CC3`. The 128-frame bypass begins with the trigger's final sample; normal filtering resumes when the counter expires. The FIR continues running. The right-channel echo, I2S serializer, and two-frame baseline output latency are preserved.

The recovered core has no external reset. Its internal state uses the recovered iCE40 power-up initialization. The test adapter wires I2S signals directly and does not gate them with the generic bench reset.

## Measured verification

The final standard validation passed 11/11 report cases (10 simulations and the FPGA build), with 0 failed and 0 blocked cases. The runner's 15 framework unit tests also passed.

- Baseline equivalence: 0 mismatches across 22,248 output words in the seven standard no-trigger cases.
- Full noisy recording: all 240,000 source frames at 16 kHz PCM16 were simulated in four reset-isolated chunks with seven-frame overlaps. The chunks compared 481,082 output words, with 0 mismatches and no trigger sequence. Each chunk included 130 zero frames to flush the 128-frame payload window and two-frame output latency. The combined baseline comparison count is 503,330 words.
- False-positive checks: all seven standard no-trigger cases passed, including 8,192 seeded random frames, a one-word near miss, an interrupted trigger sequence, boundary values, startup edges, the Phase 3 golden vector, and 1,024 frames from the noisy recording. The complete noisy file also passed in 4/4 chunks.
- Activation: 4/4 trigger events passed at 1 MHz and 625 kHz BCLK, including two activations in one stream. Every event produced exactly 128 raw pass-through frames; total pass-through mismatches were 0.
- Startup and echo: 0 right-channel echo mismatches; the first two output frames were zero as expected.
- Reproducibility: standard runs 7 and the fresh Scribe-recorded continuation produced identical input-content hashes and bitstream SHA-256 `49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b`.

For iCE40 UP5K SG48 with a 10 MHz constraint, place-and-route used 3,662/5,280 logic cells (69.4%), 0/8 DSPs, 0/30 block RAMs, and 9/39 IO cells. The recovered Phase 4 baseline used 3,179 logic cells, so this candidate adds 483 cells (15.2% over that baseline). Fmax was 15.1316 MHz, and the bitstream pack/unpack round trip passed. No physical board test was run.

The captured numerical evidence is in `reports/evidence-summary-final.json` and `reports/full-audio-evidence.json`. The full-audio source hash, chunk ranges, and input/golden hashes are in `reports/full-audio-vectors/source-summary.json`. The detailed standard run 7 report and build summary are retained under `reports/validation-run-7/`. `reports/scribe-record-test.json` contains the selected Scribe command receipts, including the incomplete first full-audio attempt and the successful retries.

## Reproduction

Run from this worktree root with the OSS CAD Suite tools listed in the validation report:

```powershell
$Suite = 'C:\Users\lowbr\Documents\College\AI\CSAW_FIN\.worktrees\phase-04\.tools\oss-cad-suite'
$Python = Join-Path $Suite 'lib\python3.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $Python experiments/phase05/05b-astra/tests/prepare_vectors.py
& $Python experiments/phase05/05b-astra/tests/prepare_full_audio.py
& $Python infrastructure/run.py --suite $Suite validate --manifest experiments/phase05/05b-astra/manifest.json --output experiments/phase05/05b-astra/reports/reproduction-run
& $Python experiments/phase05/05b-astra/tests/audit_results.py --run experiments/phase05/05b-astra/reports/reproduction-run --repeat-run experiments/phase05/05b-astra/reports/validation-run-7 --output experiments/phase05/05b-astra/reports/reproduction-evidence.json
& $Python infrastructure/run.py --suite $Suite sim --manifest experiments/phase05/05b-astra/tests/full_audio_manifest.json --output experiments/phase05/05b-astra/reports/full-audio-run
& $Python experiments/phase05/05b-astra/tests/audit_full_audio.py --run experiments/phase05/05b-astra/reports/full-audio-run --summary experiments/phase05/05b-astra/reports/full-audio-vectors/source-summary.json --output experiments/phase05/05b-astra/reports/full-audio-evidence.json
```

The Scribe `record-test` wrapper needs a longer timeout for the full-audio run; `--timeout 900` allowed all four chunks to finish. The default 300-second attempt ended incomplete after three chunks and was not counted as a test pass.

## Package map

- `rtl/fir_audio_top.v`: AI-authored candidate top.
- `rtl/baseline/fir_audio_top.v`: unchanged recovered baseline.
- `rtl/phase4_dut.sv`: local direct-wire adapter for the generic testbench.
- `tests/reference/` and `tests/vectors/`: baseline reference, coefficients, preserved Phase 3 golden data, and directed/seeded stimuli.
- `tests/prepare_full_audio.py`, `tests/full_audio_manifest.json`, and `tests/audit_full_audio.py`: full-recording negative simulation and capture audit. Generated full-audio vectors are kept under ignored `reports/full-audio-vectors/`.
- `reports/`: captured regression and build evidence; generated outputs are local unless explicitly tracked.
- `ai/`: model provenance, source hashes, session summary, and rejected revisions.
- `manifest.json`: Phase 4 schema-version-1 `verified_design` manifest with candidate metadata and source hashes.

## Provenance and limits

The competition-specific trigger, payload, RTL changes, test/reference additions, manifest, and documentation were AI-authored for this candidate. The baseline RTL and original Phase 3 golden data are unchanged. The requested model label was Astra; the runtime did not expose an exact model identifier. `ai/session-record.md` is a provenance summary, not a raw conversation transcript.

The Project Scribe `record-test` interface recorded the standard validation, full-audio simulation, and full-audio audit commands with exit code 0 and stable tracked state. Its latest local preview included 90 queued events and left the checkpoint at cursor 0; a temporary config copy raised the local evidence-size cap to the supported 1,000,000 characters. The preview used no model synthesis or Google Docs publishing; the Scribe setup is still marked unactivated. No public remote was updated and this candidate does not select an overall winner.

The full noisy WAV was simulated as four independent power-up runs, not as one continuous hardware stream. Physical board behavior, board timing, and the physical exploit demonstration remain unverified. LED/RGB pin roles remain provisional. The official finals instructions require a physical-board exploit demonstration and comprehensive AI transcripts; those items remain outstanding.
