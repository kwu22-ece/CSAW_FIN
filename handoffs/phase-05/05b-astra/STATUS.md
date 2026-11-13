# Phase 5B Handoff - 05b-astra

Phase: 5B — Independent Candidate B: Reliability and Verification  
Agent: Codex  
Model: Astra label supplied by the user; exact runtime identifier unavailable  
Git branch: `challenge3/05b-astra`  
Source commit SHA: `15a8a6525e225ad82d931b3bc75399f744638b2e` (candidate RTL)  
Test harness commit: `be3a5e1` (full-recording regression infrastructure)  
Owned directories: `experiments/phase05/05b-astra/`, `handoffs/phase-05/05b-astra/`  
Frozen base: `e72522f265ac36da713cd7a0dcf8dbc64ab21209`  
Phase 3 baseline/reference commit: `5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f`

## Candidate

The trigger is eight exact consecutive signed 16-bit left samples (`7F00 8101 5A3C A5C3 6D92 926D C33C 3CC3`). On completion it bypasses the left FIR output for 128 frames, beginning with the trigger's final sample. Normal filtering then resumes. The recovered right echo, I2S serializer, and two-frame output latency are preserved. Core state uses the recovered iCE40 power-up initialization; there is no external reset input.

## Completed tasks and verified results

- Standard validation: 11/11 report cases passed (10 simulation cases and the FPGA build), 0 failed, 0 blocked; all 15 framework unit tests passed.
- Baseline equivalence: 0 mismatches over 22,248 output words in the seven standard no-trigger cases.
- Full supplied noisy audio: all 240,000 source frames at 16 kHz PCM16 were covered by four reset-isolated simulations with seven-frame overlap. The runs compared 481,082 output words, with 0 mismatches and 0 trigger matches. Each chunk included 130 flush frames. Combined standard and full-audio baseline comparisons: 503,330 words.
- Negative tests: 7/7 standard no-trigger cases passed, including seeded random, one-word near miss, interrupted sequence, boundaries, startup, golden, and noisy-audio inputs. Full noisy audio passed 4/4 chunks.
- Activation: 4/4 trigger events passed at 1 MHz and 625 kHz BCLK; one vector has two activations. Each event produced 128/128 raw frames, with 0 pass-through mismatches.
- Startup and echo: 0 right-channel echo mismatches; two startup zero frames verified.
- Reproducibility: standard runs had identical input-content hashes and bitstream SHA-256 `49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b`.
- UP5K/SG48 place-and-route: 3,662/5,280 logic cells (69.4%), 0/8 DSP, 0/30 BRAM, 9/39 IO. This is 483 logic cells (15.2%) above the 3,179-cell Phase 4 baseline. A 10 MHz constraint was met; Fmax was 15.1316 MHz. Pack/unpack round trip passed.

## Failed or pending checks and limitations

- The first Scribe `record-test` attempt used its 300-second default and ended incomplete after three full-audio chunks (`exit_code: null`; no complete run report). The same simulation completed on retry with `--timeout 900`, and all four chunks passed.
- The four full-audio chunks each start from FPGA power-up initialization. Seven-frame overlap covers any eight-sample trigger crossing chunk boundaries, but this is not one uninterrupted 240,000-frame simulation.
- No Hackster board was available. Physical startup, timing, I2S behavior, payload, and exploit demonstration are unverified. LED/RGB pin roles remain provisional.
- The runtime did not provide a raw provider transcript. `ai/session-record.md` is only a provenance summary. The local Project Scribe agent is marked unactivated, so its synthesis service was not run; the test event was recorded and a model-free preview was generated with Google publishing disabled.
- The official final instructions require a physical-board exploit demonstration and comprehensive AI transcripts; both remain outstanding for final submission.

## Generated artifacts

- Candidate package: `experiments/phase05/05b-astra/` (`rtl/`, `tests/`, `reports/`, `ai/`, and `manifest.json`).
- Full-audio capture audit: `experiments/phase05/05b-astra/reports/full-audio-evidence.json`.
- Full-audio input/chunk provenance: `experiments/phase05/05b-astra/reports/full-audio-vectors/source-summary.json`.
- Standard numerical summary: `experiments/phase05/05b-astra/reports/evidence-summary-final.json`.
- Selected Project Scribe command receipts and model-free preview status: `experiments/phase05/05b-astra/reports/scribe-record-test.json`.
- Rejected revisions and fixes: `experiments/phase05/05b-astra/ai/rejected-revisions.md`.

## Exact reproduction commands

Run from the isolated worktree root with the installed OSS CAD Suite:

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

## Documentation status

Project Scribe's supported `record-test` interface recorded the standard validation, full-audio simulation, and full-audio audit at exit code 0 with stable tracked state. The local preview covered 90 queued events; Scribe status confirmed checkpoint cursor 0 after preview. The preview used a temporary external config copy with its supported evidence cap set to 1,000,000 characters and invoked no model synthesis or Google publishing. A compact receipt preserves the selected records; the global event database and preview remain local.

## Dependencies for next phase

Physical Hackster programming and demonstration, raw AI interaction transcripts, and an activated documentation-agent model service remain outstanding. This handoff does not choose an overall winning candidate.

Remote push status: not pushed; implementation remains on the isolated local branch.
