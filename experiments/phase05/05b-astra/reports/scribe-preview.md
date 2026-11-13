# CSAW_FIN Phase 5B 05b-astra — project documentation

Report: 2026-11-13T03-23-48.646Z-9ae7fd39
Observed: 2026-11-13T03:23:48.265Z
Coverage: events 1–1; 0 queued for a later report; 1 events retained.

This report separates model interpretation, agent claims, Git observations, and recorded command results. Citations identify evidence, not a guarantee that a claim is true.

## Evidence preview

No model synthesis or Google Docs write was performed.

## Sessions observed (historical totals)

- test-runner / phase05b-final-validation: 1 events; last seen 2026-11-13T03:19:06.485Z.

## Git evidence

### [git:0] C:\Users\lowbr\Documents\College\AI\CSAW_FIN_worktrees\05b-astra

Branch: challenge3/05b-astra; HEAD: e72522f265ac36da713cd7a0dcf8dbc64ab21209.
Previous HEAD: (first observation); continuous ancestry: false.

Status:
```text
?? experiments/phase05/05b-astra/README.md
?? experiments/phase05/05b-astra/ai/model-provenance.json
?? experiments/phase05/05b-astra/ai/rejected-revisions.md
?? experiments/phase05/05b-astra/ai/session-record.md
?? experiments/phase05/05b-astra/ai/source-hashes.json
?? experiments/phase05/05b-astra/constraints/hackster.pcf
?? experiments/phase05/05b-astra/manifest.json
?? experiments/phase05/05b-astra/rtl/baseline/fir_audio_top.v
?? experiments/phase05/05b-astra/rtl/fir_audio_top.v
?? experiments/phase05/05b-astra/rtl/phase4_dut.sv
?? experiments/phase05/05b-astra/tests/BASELINE_PROVENANCE.md
?? experiments/phase05/05b-astra/tests/audit_results.py
?? experiments/phase05/05b-astra/tests/candidate_reference.py
?? experiments/phase05/05b-astra/tests/prepare_vectors.py
?? experiments/phase05/05b-astra/tests/reference/README.md
?? experiments/phase05/05b-astra/tests/reference/__init__.py
?? experiments/phase05/05b-astra/tests/reference/coeffs.json
?? experiments/phase05/05b-astra/tests/reference/run_reference.py
?? experiments/phase05/05b-astra/tests/vectors/boundary_stress.csv
?? experiments/phase05/05b-astra/tests/vectors/boundary_stress.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/canonical_golden.csv
?? experiments/phase05/05b-astra/tests/vectors/near_miss_negative.csv
?? experiments/phase05/05b-astra/tests/vectors/near_miss_negative.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/noisy_audio_1024.csv
?? experiments/phase05/05b-astra/tests/vectors/noisy_audio_1024.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/random_negative.csv
?? experiments/phase05/05b-astra/tests/vectors/random_negative.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/reference_io.csv
?? experiments/phase05/05b-astra/tests/vectors/reference_io.generic.csv
?? experiments/phase05/05b-astra/tests/vectors/reference_io.in.csv
?? experiments/phase05/05b-astra/tests/vectors/retrigger_1mhz.csv
?? experiments/phase05/05b-astra/tests/vectors/split_sequence_negative.csv
?? experiments/phase05/05b-astra/tests/vectors/split_sequence_negative.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/startup_edges.csv
?? experiments/phase05/05b-astra/tests/vectors/startup_edges.expected.csv
?? experiments/phase05/05b-astra/tests/vectors/trigger_1mhz.csv
?? experiments/phase05/05b-astra/tests/vectors/trigger_625khz.csv
?? handoffs/phase-05/05b-astra/STATUS.md

```
Staged changes:
```text
(none)
```
Unstaged changes:
```text
(none)
```
Committed changes since checkpoint:
```text
(none or no continuous baseline)
```
Commits (bounded):
```text
e72522f 2026-11-12T20:09:54-05:00 docs: record recovered audio integration and timing validation
8fd929a 2026-11-12T20:07:53-05:00 feat: integrate verified Phase 2 audio RTL vectors and reference model
2da1d72 2026-11-12T19:10:12-05:00 docs: hand off verified Phase 4 infrastructure evidence and dependencies
2c04dba 2026-11-12T19:08:47-05:00 fix: widen simulation watchdog arithmetic for long captures
f8da331 2026-11-12T19:06:41-05:00 build: integrate one-command RTL regression and repeatable iCE40 builds
3715e40 2026-11-12T19:06:41-05:00 test: add strict numerical comparisons vectors and regression reports
027b357 2026-11-12T19:06:40-05:00 test: add configurable I2S drivers monitors and literal protocol fixture
764873b 2026-11-12T19:04:08-05:00 build: configure checksum-pinned FPGA and simulation toolchain
dc064b2 2026-11-12T18:29:44-05:00 docs: add Phase 1 initialization and research milestone report
9893aed 2026-11-12T18:10:50-05:00 Import CSAW_FINALS project work
92876d5 2026-11-12T15:08:34-08:00 Initial commit

```
- Git status and log are bounded observations, not authorship or test verification. Untracked file contents are not read.
- Patch contents disabled.

[source:0:0] Source: experiments/phase05/05b-astra/README.md; SHA-256 0ba132e6db28becde65181aefcbf7494685029d47762c0747d558890e1cdadea
```text
﻿# CSAW 2026 Challenge 3 - Candidate B (Astra Reliability)

This isolated candidate implements a deterministic, exact-sequence trigger and a 128-frame left-channel filter bypass. It is based on the recovered Phase 3 audio design and is checked with the Phase 4 generic runner.

## Candidate behavior

The matcher accepts eight consecutive exact 16-bit left samples: `7F00 8101 5A3C A5C3 6D92 926D C33C 3CC3`. On the final sample, the left output passes the current and next 127 samples directly, for 128 frames. The FIR continues to run; when the counter expires, the normal filtered output resumes. The right echo, I2S serializer, and two-frame baseline output latency are retained. State starts from the recovered iCE40 power-up initialization; there is no external reset on the core.

The test interface uses 16 BCLK periods per channel slot with Philips one-bit MSB delay, matching the recovered design's successful Phase 4 integration. The package-local adapter in `rtl/phase4_dut.sv` maps the generic testbench ports directly and does not gate I2S signals with the bench reset.

## Measured verification

Validation runs 5, 6, and 7 each passed all ten simulation cases and the FPGA build: 11/11 report cases, 0 failed, 0 blocked. Each `validate` run also passed 15 framework unit tests.

- Baseline mismatch count: 0 over 22,248 compared words across the seven normal-operation cases.
- Right-channel echo mismatch count: 0; the first two startup output frames were zero as expected.
- Negative tests: 7/7 passed, including seeded random data, a one-word near miss, and a sequence split by an interruption.
- Trigger events: 4/4 passed at 1 MHz, 625 kHz, and two repeated activations. Each event produced exactly 128 raw pass-through frames; total pass-through mismatches: 0.
- Boundary, noisy-audio, startup, and sequential retrigger tests matched their expected results exactly.
- Reproducibility: validation runs 6 and 7 had identical per-case input-content hashes and identical bitstream SHA-256 `49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b`.

For iCE40 UP5K SG48 at a 10 MHz constraint, place-and-route used 3,662/5,280 logic cells (69.4%), 0/8 DSPs, 0/30 block RAMs, and 9/39 IO cells. Reported Fmax was 15.1316 MHz. The bitstream pack/unpack round trip passed. No physical board was available; hardware operation is unverified.

See `reports/evidence-summary-final.json`, `reports/validation-run-7/report.json`, and `reports/validation-run-7/fpga-build/build-summary.json` for captured results and tool versions. Failed harness/configuration attempts and their fixes are summarized in `ai/rejected-revisions.md`.

## Reproduction

Run these commands from the isolated worktree root. Use an OSS CAD Suite installation with the Icarus, Yosys, nextpnr-ice40, IceStorm, and icetime tools listed in the validation report.

```powershell
$Suite = 'C:\Users\lowbr\Documents\College\AI\CSAW_FIN\.worktrees\phase-04\.tools\oss-cad-suite'
$Python = Join-Path $Suite 'lib\python3.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $Python experiments/phase05/05b-astra/tests/prepare_vectors.py
& $Python infrastructure/run.py --suite $Suite validate --manifest experiments/phase05/05b-astra/manifest.json --output experiments/phase05/05b-astra/reports/reproduction-run
& $Python experiments/phase05/05b-astra/tests/audit_results.py --run experiments/phase05/05b-astra/reports/validation-run-6 --repeat-run experiments/phase05/05b-astra/reports/reproduction-run --output experiments/phase05/05b-astra/reports/reproduction-evidence.json
```

`manifest.json` records the runner configuration, exact source hashes, trigger behavior, verification status, and baseline source commit. `ai/source-hashes.json` repeats the hash inventory and records the manifest hash. The Phase 3 golden inputs and outputs remain byte-preserved; `reference_io.generic.csv` is a separate runner-compatible copy.

## Package map

- `rtl/fir_audio_top.v`: AI-authored candidate top.
- `rtl/baseline/fir_audio_top.v`: unchanged recovered baseline.
- `rtl/phase4_dut.sv`: local copy of the validated direct-wire adapter.
- `tests/reference/` and `tests/vectors/`: golden reference, coefficients, preserved Phase 3 data, and deterministic stimuli.
- `tests/prepare_vectors.py`, `tests/candidate_reference.py`, `tests/audit_results.py`: AI-authored vector, expected-result, and capture-audit code.
- `reports/`: regression reports, actual captures, build outputs, and evidence summary.
- `ai/`: model provenance, source hashes, session record, and rejected revisions.
- `manifest.json`: Phase 4 schema-version-1 `verified_design` manifest with candidate metadata.

## Provenance and limits

The competition-specific trigger, payload, RTL changes, test/reference additions, manifest, and documentation were AI-authored for this candidate. The baseline RTL and original golden data were copied unchanged from Phase 3. The requested model label was Astra; the runtime does not expose an exact model identifier. The Phase 2 audio top is a behavioral reconstruction rather than a gate-level copy. Hackster board testing remains outstanding, and LED/RGB pin roles remain provisional. No public remote was updated, and this candidate does not select an overall winner.

```

[source:0:1] Source: experiments/phase05/05b-astra/manifest.json; SHA-256 44d70faa315362377a5f7abc2176e0a34832b64eeb94e9fa02fb08adba23e33c
```text
﻿{
    "schema_version":  1,
    "name":  "05b-astra",
    "kind":  "verified_design",
    "ready":  true,
    "candidate_id":  "05b-astra",
    "candidate_name":  "Independent Candidate B - Astra Reliability",
    "branch":  "challenge3/05b-astra",
    "base_commit":  "e72522f265ac36da713cd7a0dcf8dbc64ab21209",
    "baseline_source_commit":  "5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f",
    "model_provenance":  {
                             "agent":  "Codex",
                             "model_label":  "Astra; exact runtime identifier unavailable",
                             "provider":  "OpenAI"
                         },
    "source_sha256":  {
                          "rtl/fir_audio_top.v":  "2c868b30d4140f40dc5cb419bbd611d9c848aa6578d902ab509b6c4e666518e4",
                          "rtl/phase4_dut.sv":  "1d53da1d936deea3e491c1f35e38d48ff4f9408b80311badb1d7a898b9eed28c",
                          "rtl/baseline/fir_audio_top.v":  "3f7da4476296bc02bfee2d973e3c206a9bde7a661b7d68aa0c3bf779cf66b7d1",
                          "tests/audit_results.py":  "a4408ab5ac8f8cf7d4990ad045454bffd9f6091df6fd96b49da537cfbff21a78",
                          "tests/BASELINE_PROVENANCE.md":  "23213b12b0c92fbab9372ede458380f570a44c517ceb7334eaad5d36619de228",
                          "tests/candidate_reference.py":  "f63f386044529c1e2bed8db12b73dfd10e9c1596e3576fb6f99fb1c31ca6e298",
                          "tests/prepare_vectors.py":  "0214f9ae31b0e164eb163f9f5922a04581cf5e50c6b8a1abb3a0ffd081ad5443",
                          "tests/reference/coeffs.json":  "b7e9fad6e3905f7c22f0a4431ccb3bdb058dce36d9b24afd2e2a9d2a6cf057ca",
                          "tests/reference/README.md":  "bfc2942de13e567469dcb88024ee775f85718d979ea578f865f192305ba7f532",
                          "tests/reference/run_reference.py":  "fe9bfdf1a2778541c2d2cf31dc6bd408319d518a9edb5482fa453d3e7c91a891",
                          "tests/reference/__init__.py":  "c820d672a1a2279a9acae9c4fbd9cbcf8381edb6d848911853d3d55791cd7b0a",
                          "tests/vectors/boundary_stress.csv":  "4b4cb57847246e50b1827c64069160ae59244db75a600f2a733d4c6ea8adee84",
                          "tests/vectors/boundary_stress.expected.csv":  "3eff64df2b9af75d72346944b2cb3821ff48af7c1e0036c81e54a32be7e0f982",
                          "tests/vectors/canonical_golden.csv":  "4ab5e214833e5fb56ac39a1b0c9e1a1b7ff125b1df57e6154b5283269ec1cdfe",
                          "tests/vectors/near_miss_negative.csv":  "d9bd7b06c972cb8cc73263f5ff59720b147179242dcb2a52a0aeb62bb6e74a7f",
                          "tests/vectors/near_miss_negative.expected.csv":  "582124b3e2af4b78eaa259586812f5d4855fbaa331792d8ccb963adf1d957f17",
                          "tests/vectors/noisy_audio_1024.csv":  "964ef9e9fead75e73dd62d5924cbe0b68f9fed26242f19a2ff369a9a889ea6e0",
                          "tests/vectors/noisy_audio_1024.expected.csv":  "ba337edbcb675c75f25b954317089cf27d1264b943379417c098f14a6ec703d6",
                          "tests/vectors/random_negative.csv":  "c433acd030e31671b27a6e94bf2c371b80c48baee670bb6a8fcad5cc3b0019a4",
                          "tests/vectors/random_negative.expected.csv":  "d1940d92c197545dcb4ff19e30508b0fad86015410d955ab10e7c22a170a1942",
                          "tests/vectors/reference_io.csv":  "f1a5d1c031090d856b581835b74b44702258721a6ebe441914ced31691945ef5",
                          "tests/vectors/reference_io.generic.csv":  "bedfcf49619f4d069de44ec1147190a2fc3259fb5cfcf5dd1942c7e6042bf50f",
                          "tests/vectors/reference_io.in.csv":  "2a3a8b882b202d1f27e0b5ef335a6eaad5fd61ca20ab3a355642611d4284f1cb",
                          "tests/vectors/retrigger_1mhz.csv":  "f4e71d5b620b79046513cc0b0bb6ba6377caeee4cd7d65ecac0ee2a0c18740ce",
                          "tests/vectors/split_sequence_negative.csv":  "cfc1a4f710c20874fed4a0970fb994ed757d85eb2ecb29f93c6031eba8880e2e",
                          "tests/vectors/split_sequence_negative.expected.csv":  "ce0ebce3a50e1c09066313d2c3972fb38f98d1e95497fb1ee7836bfa93584012",
                          "tests/vectors/startup_edges.csv":  "3d1f5a9d2ebd92a36c54c12540183a13afc08807a9ca5580afa398238ffa6f2a",
                          "tests/vectors/startup_edges.expected.csv":  "f68f4386ad063db7b08dc91e4a5e43098aeda1fd5fbb3636014465e82ce2103a",
                          "tests/vectors/trigger_1mhz.csv":  "c3879761043c8f8b5638c59cdb229e7c3d1f814e88b1d25582117d98ad8cbb1e",
                          "tests/vectors/trigger_625khz.csv":  "c3879761043c8f8b5638c59cdb229e7c3d1f814e88b1d25582117d98ad8cbb1e",
                          "constraints/hackster.pcf":  "5bb849ea0d64b98c891ea8a7f474c61a34c9ecd1d4f7d0584bb97169c1a79fe3",
                          "../../../what_a_piece_of_work-noisy.wav":  "403bab7faa0d0a898385a49d5c942b19890a5f166045fe9ba18c0a0cf919abb0"
                      },
    "candidate":  {
                      "top":  "fir_audio_top",
                      "trigger_samples_hex":  [
                                                  "7F00",
                                                  "8101",
                                                  "5A3C",
                                                  "A5C3",
                                                  "6D92",
                                                  "926D",
                                                  "C33C",
                                                  "3CC3"
                                              ],
                      "payload":  "Bypass filtered left output with raw input for 128 consecutive input frames",
                      "payload_frames":  128,
                      "normal_output_latency_frames":  2,
                      "right_channel":  "unchanged input echo"
                  },
    "verification_status":  {
                                "state":  "simulation_and_synthesis_passed_reproducible",
                                "framework_unit_tests":  15,
                                "regression_cases_passed":  11,
                                "regression_cases_failed":  0,
                                "compared_baseline_words":  22248,
                                "baseline_mismatch_count":  0,
                                "negative_cases_passed":  7,
                                "negative_cases_tested":  7,
                                "activation_events_succeeded":  4,
                                "activation_events_tested":  4,
                                "activation_success_rate":  1,
                                "bypass_frames_per_activation":  128,
                                "right_echo_mismatch_count":  0,
                                "raw_pass_through_mismatch_count":  0,
                                "startup_zero_frames_verified":  2,
                                "reproducible":  true,
                                "bitstream_sha256":  "49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b",
                                "timing_constraint_mhz":  10,
                                "achieved_fmax_mhz":  15.131569862365723,
                                "logic_cells_used":  3662,
                                "logic_cells_available":  5280,
                                "dsp_used":  0,
                                "dsp_available":  8,
                                "hardware_validation":  "not_run"
                            },
    "verification_evidence":  [
                                  "tests/BASELINE_PROVENANCE.md",
                                  "tests/reference/README.md",
                                  "constraints/hackster.pcf",
                                  "reports/validation-run-5/report.json",
                                  "reports/validation-run-6/report.json",
                                  "reports/evidence-summary-run-5-6.json"
                              ],
    "simulation":  {
                       "sources":  [
                                       "rtl/fir_audio_top.v",
                                       "rtl/phase4_dut.sv"
                                   ],
                       "parameters":  {
                                          "SAMPLE_BITS":  16,
                                          "SLOT_BITS":  16,
                                          "MSB_DELAY":  1,
                                          "LEFT_LEVEL":  0,
                                          "HALF_PERIOD_NS":  500,
                                          "CLOCK_HALF_NS":  50,
                                          "RESET_CYCLES":  10
                                      },
                       "reference_command":  [
                                                 "{python}",
                                                 "tests/candidate_reference.py",
                                                 "{input}",
                                                 "{output}"
                                             ],
                       "reference_sources":  [
                                                 "tests/candidate_reference.py",
                                                 "tests/reference/run_reference.py",
                                                 "tests/reference/coeffs.json"
                                             ],
                       "timeout_seconds":  300
                   },
    "cases":  [
                  {
                      "name":  "phase3-golden",
                      "input_csv":  "tests/vectors/canonical_golden.csv",
                      "expected_csv":  "tests/vectors/reference_io.generic.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "noisy-audio-1024",
                      "input_csv":  "tests/vectors/noisy_audio_1024.csv",
                      "expected_csv":  "tests/vectors/noisy_audio_1024.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "startup-edges",
                      "input_csv":  "tests/vectors/startup_edges.csv",
                      "expected_csv":  "tests/vectors/startup_edges.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "boundary-stress",
                      "input_csv":  "tests/vectors/boundary_stress.csv",
                      "expected_csv":  "tests/vectors/boundary_stress.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "random-negative",
                      "input_csv":  "tests/vectors/random_negative.csv",
                      "expected_csv":  "tests/vectors/random_negative.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "near-miss-negative",
                      "input_csv":  "tests/vectors/near_miss_negative.csv",
                      "expected_csv":  "tests/vectors/near_miss_negative.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  {
                      "name":  "split-sequence-negative",
                      "input_csv":  "tests/vectors/split_sequence_negative.csv",
                      "expected_csv":  "tests/vectors/split_sequence_negative.expected.csv",
                      "tolerance":  0,
                      "latency_words":  0
                  },
                  
[TRUNCATED]
```

[source:0:2] Source: experiments/phase05/05b-astra/rtl/fir_audio_top.v; SHA-256 2c868b30d4140f40dc5cb419bbd611d9c848aa6578d902ab509b6c4e666518e4
```text
// =============================================================================
// fir_audio_top.v  -  Reconstructed baseline RTL (Phase 2 reverse-engineering)
//
// Behavioral reconstruction of the provided iCE40-UP5K bitstream
// (fir_audio_top.bin): a streaming 63-tap linear-phase FIR low-pass audio
// filter with an oversampled Philips-I2S target interface.
//
// This is an EVIDENCE-SUPPORTED EQUIVALENT, not a gate-level copy. Its filtered
// output is bit-identical to the recovered bitstream (verified by co-simulation
// against the gate-level netlist and the bit-exact software model sw_fir.py).
// The challenge explicitly permits refactoring as long as normal filtering is
// preserved.
//
// Recovered facts encoded here (all verified in Phase 2):
//   * iCE40-UP5K, single free-running clock ICE_CLK (~10 MHz); no PLL.
//   * I2S oversampled against ICE_CLK (BCLK <= 1 MHz); edges detected.
//   * Philips I2S, 16-bit, MSB-first; left channel = sample to filter.
//   * Output: left = filtered sample, right = unmodified echo of the input.
//   * 63-tap Type-I linear-phase symmetric FIR, Q1.15 coefficients.
//   * Arithmetic: acc = sum(x*h); y = sat16( (acc + 2^14) >>> 15 )
//     (round half toward +inf, then saturate).
//
// Implementation choice: a time-multiplexed SERIAL multiply-accumulate (one
// multiplier reused over the 63 taps), mirroring the original's low LUT/carry
// footprint (the original uses a BRAM sample delay line; here a register delay
// line is used for clarity - see notes). There are ~600+ ICE_CLK cycles per
// audio frame, far more than the 63 MAC cycles needed.
// =============================================================================
`default_nettype none

module fir_audio_top (
    input  wire ICE_CLK,     // free-running ~10 MHz system clock
    input  wire I2S_BCLK,    // I2S bit clock (<= 1 MHz), oversampled
    input  wire I2S_WS,      // I2S word select (0=left, 1=right)
    input  wire I2S_SD_IN,   // serial data in (sample to filter, MSB first)
    output reg  I2S_SD_OUT,  // serial data out (left=filtered, right=echo)
    output wire ICE_LED,     // activity: high while the MAC is computing
    output wire RGB_R,       // status LEDs (active-low)
    output wire RGB_G,
    output wire RGB_B
);
    localparam integer NTAP = 63;

    // ----------------------------------------------------------------------
    // Recovered Q1.15 coefficients (symmetric, sum = 32768 = 1.0)
    // ----------------------------------------------------------------------
    reg signed [15:0] COEF [0:NTAP-1];
    integer ci;
    initial begin
        COEF[0]=-14;   COEF[1]=20;    COEF[2]=27;    COEF[3]=-12;
        COEF[4]=-45;   COEF[5]=-9;    COEF[6]=63;    COEF[7]=49;
        COEF[8]=-66;   COEF[9]=-109;  COEF[10]=34;   COEF[11]=176;
        COEF[12]=49;   COEF[13]=-219; COEF[14]=-187; COEF[15]=198;
        COEF[16]=362;  COEF[17]=-71;  COEF[18]=-524; COEF[19]=-188;
        COEF[20]=600;  COEF[21]=577;  COEF[22]=-497; COEF[23]=-1062;
        COEF[24]=104;  COEF[25]=1575; COEF[26]=752;  COEF[27]=-2030;
        COEF[28]=-2587;COEF[29]=2344; COEF[30]=10114;COEF[31]=13920;
        COEF[32]=10114;COEF[33]=2344; COEF[34]=-2587;COEF[35]=-2030;
        COEF[36]=752;  COEF[37]=1575; COEF[38]=104;  COEF[39]=-1062;
        COEF[40]=-497; COEF[41]=577;  COEF[42]=600;  COEF[43]=-188;
        COEF[44]=-524; COEF[45]=-71;  COEF[46]=362;  COEF[47]=198;
        COEF[48]=-187; COEF[49]=-219; COEF[50]=49;   COEF[51]=176;
        COEF[52]=34;   COEF[53]=-109; COEF[54]=-66;  COEF[55]=49;
        COEF[56]=63;   COEF[57]=-9;   COEF[58]=-45;  COEF[59]=-12;
        COEF[60]=27;   COEF[61]=20;   COEF[62]=-14;
    end

    // ----------------------------------------------------------------------
    // Input synchronizers + edge detection (oversampling the I2S lines)
    // ----------------------------------------------------------------------
    reg bclk_s0, bclk_s1, ws_s0, ws_s1, sd_s0, sd_s1;
    always @(posedge ICE_CLK) begin
        bclk_s0 <= I2S_BCLK; bclk_s1 <= bclk_s0;
        ws_s0   <= I2S_WS;   ws_s1   <= ws_s0;
        sd_s0   <= I2S_SD_IN;sd_s1   <= sd_s0;
    end
    wire bclk_rise = bclk_s0 & ~bclk_s1;
    wire bclk_fall = ~bclk_s0 & bclk_s1;
    wire ws_sync   = ws_s1;
    wire sd_sync   = sd_s1;

    // ----------------------------------------------------------------------
    // RX deserializer: recover the 16-bit left sample, MSB first.
    // A WS 0->1 transition (sampled between two BCLK rising edges) marks the
    // left LSB (L0); a WS 1->0 transition marks the right LSB (R0 / end frame).
    // ----------------------------------------------------------------------
    reg [15:0] rx_sh;
    reg        ws_prev_bclk;     // WS value at the previous BCLK rising edge
    reg [15:0] left_sample;
    reg        new_sample;       // 1-cycle strobe when a left sample completes
    reg        end_frame;        // 1-cycle strobe at R0 (frame boundary)

    always @(posedge ICE_CLK) begin
        new_sample <= 1'b0;
        end_frame  <= 1'b0;
        if (bclk_rise) begin
            rx_sh <= {rx_sh[14:0], sd_sync};
            // L0: WS just went high (this is the 16th/left LSB bit)
            if (ws_sync & ~ws_prev_bclk) begin
                left_sample <= {rx_sh[14:0], sd_sync};
                new_sample  <= 1'b1;
            end
            // R0: WS just went low (end of frame)
            if (~ws_sync & ws_prev_bclk)
                end_frame <= 1'b1;
            ws_prev_bclk <= ws_sync;
        end
    end

    // ----------------------------------------------------------------------
    // Serial multiply-accumulate FIR (direct form), one tap per ICE_CLK cycle.
    // On new_sample: shift the delay line, then accumulate over 63 taps.
    // ----------------------------------------------------------------------
    reg signed [15:0] dl [0:NTAP-1];       // sample delay line (newest = dl[0])
    reg        [6:0]  k;                    // tap index
    reg        busy;
    reg signed [39:0] acc;                  // wide accumulator (Q2.30-ish)
    reg signed [15:0] y_filt;               // latched filtered result
    reg signed [15:0] echo;                 // echo of the SAME input sample
    integer di;

    // round half toward +inf then saturate to int16
    function signed [15:0] round_sat;
        input signed [39:0] a;
        reg   signed [39:0] r;
        begin
            r = (a + 40'sd16384) >>> 15;
            if (r > 40'sd32767)       round_sat = 16'sd32767;
            else if (r < -40'sd32768) round_sat = -16'sd32768;
            else                      round_sat = r[15:0];
        end
    endfunction

    always @(posedge ICE_CLK) begin
        if (new_sample) begin
            // shift delay line, insert newest sample at dl[0]
            for (di = NTAP-1; di > 0; di = di - 1)
                dl[di] <= dl[di-1];
            dl[0] <= $signed(left_sample);
            echo  <= $signed(left_sample);   // echo tracks this input
            // start MAC next cycle (dl updated); accumulate from k=0
            acc  <= 40'sd0;
            k    <= 7'd0;
            busy <= 1'b1;
        end else if (busy) begin
            acc <= acc + dl[k] * COEF[k];
            if (k == NTAP-1) begin
                busy <= 1'b0;
            end
            k <= k + 7'd1;
        end
    end

    // latch the filtered result one cycle after the last accumulate
    reg busy_d;
    always @(posedge ICE_CLK) begin
        busy_d <= busy;
        if (busy_d & ~busy)                  // falling edge of busy = MAC done
            y_filt <= round_sat(acc);
    end
    assign ICE_LED = busy;
    // ------------------------------------------------------------------
    // AI-authored reliability-focused trigger and bounded filter bypass.
    // Match eight exact consecutive left-channel samples. On a full match,
    // pass the current and next 127 left samples directly to the output path.
    // The existing serializer still supplies its original two-frame latency.
    // ------------------------------------------------------------------
    localparam [15:0] MAGIC_0 = 16'h7F00;
    localparam [15:0] MAGIC_1 = 16'h8101;
    localparam [15:0] MAGIC_2 = 16'h5A3C;
    localparam [15:0] MAGIC_3 = 16'hA5C3;
    localparam [15:0] MAGIC_4 = 16'h6D92;
    localparam [15:0] MAGIC_5 = 16'h926D;
    localparam [15:0] MAGIC_6 = 16'hC33C;
    localparam [15:0] MAGIC_7 = 16'h3CC3;
    localparam [7:0] BYPASS_FRAMES = 8'd128;

    reg [3:0] magic_position;
    reg [7:0] bypass_remaining;
    reg bypass_active;
    reg magic_match;

    always @* begin
        case (magic_position)
            4'd0: magic_match = (left_sample == MAGIC_0);
            4'd1: magic_match = (left_sample == MAGIC_1);
            4'd2: magic_match = (left_sample == MAGIC_2);
            4'd3: magic_match = (left_sample == MAGIC_3);
            4'd4: magic_match = (left_sample == MAGIC_4);
            4'd5: magic_match = (left_sample == MAGIC_5);
            4'd6: magic_match = (left_sample == MAGIC_6);
            4'd7: magic_match = (left_sample == MAGIC_7);
            default: magic_match = 1'b0;
        endcase
    end

    // State advances once per completed left sample. A mismatch restarts only
    // if that sample itself equals MAGIC_0. The matcher is clear during the
    // payload and accepts a later trigger after the counter expires.
    always @(posedge ICE_CLK) begin
        if (new_sample) begin
            if (bypass_active) begin
                magic_position <= 4'd0;
                if (bypass_remaining <= 8'd1) begin
                    bypass_remaining <= 8'd0;
                    bypass_active <= 1'b0;
                end else begin
                    bypass_remaining <= bypass_remaining - 8'd1;
                end
            end else if (magic_match) begin
                if (magic_position == 4'd7) begin
                    magic_position <= 4'd0;
                    bypass_remaining <= BYPASS_FRAMES;
                    bypass_active <= 1'b1;
                end else begin
                    magic_position <= magic_position + 4'd1;
                end
            end else if (left_sample == MAGIC_0) begin
                magic_position <= 4'd1;
            end else begin
                magic_position <= 4'd0;
            end
        end
    end

    // ----------------------------------------------------------------------
    // TX serializer: present {filtered, echo} MSB-first on SD_OUT, one bit per
    // BCLK (updated on the falling edge; the controller samples on the rising
    // edge). Reloaded at each frame boundary (end_frame).
    // ----------------------------------------------------------------------
    // One extra frame of delay so the reply to the sample in frame n appears in
    // frame n+2 (matches the original bitstream and the host tool's LATENCY=2).
    reg signed [15:0] y_d, echo_d;
    reg [31:0] tx_sh;
    reg        loaded;
    always @(posedge ICE_CLK) begin
        if (end_frame) begin
            tx_sh  <= {y_d, echo_d};         // previous frame's {filtered, echo}
            y_d    <= bypass_active ? echo : y_filt;
            echo_d <= echo;
            loaded <= 1'b1;
        end else if (bclk_fall && loaded) begin
            I2S_SD_OUT <= tx_sh[31];
            tx_sh      <= {tx_sh[30:0], 1'b0};
        end
    end

    // Status LEDs (active-low): green while streaming (frames seen), blue idle.
    assign RGB_G = ~loaded;      // low (on) once streaming
    assign RGB_B = loaded;       // high (off) once streaming
    assign RGB_R = 1'b1;         // overrun indicator (active-low): never asserts here

    // Power-up state (iCE40 FFs power up to 0); placed after all declarations.
    integer pi;
    initial begin
        I2S_SD_OUT = 1'b0; busy = 1'b0
[TRUNCATED]
```

[source:0:3] Source: experiments/phase05/05b-astra/tests/BASELINE_PROVENANCE.md; SHA-256 23213b12b0c92fbab9372ede458380f570a44c517ceb7334eaad5d36619de228
```text
# Baseline provenance

The unmodified source in rtl/baseline/fir_audio_top.v is copied from Phase 3 commit 5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f. This candidate worktree starts at frozen Phase 4 commit e72522f265ac36da713cd7a0dcf8dbc64ab21209.

The Phase 3 handoff records Philips I2S, 16-bit MSB-first, two-frame output latency, filtered left output, unchanged right echo, and 63-tap Q1.15 arithmetic. It describes a behavioral reconstruction, not a gate-level copy. Baseline RTL, reference model, coefficients, and canonical vectors are copied unchanged. Simulation uses the direct-wire reset-less adapter already validated by the Phase 4 framework at infrastructure/adapters/recovered.sv.
The generic simulation explicitly uses 16 BCLK periods per channel slot with Philips one-bit MSB delay, matching the recovered design's successful Phase 4 integration configuration. The generic runner default is 32 BCLK periods and is not compatible with this reconstructed 16-bit-slot receiver.

```

[source:0:4] Source: experiments/phase05/05b-astra/ai/model-provenance.json; SHA-256 f5fbe307103c04a8277f224ca85f9320be1d660e190c3917708ae50f8dde2efc
```text
{
  "schema_version": 1,
  "agent": "Codex",
  "model_label_from_user": "Astra",
  "provider": "OpenAI",
  "exact_runtime_model_id": "not exposed in this session",
  "reasoning_effort": "maximum available, user requested",
  "competition_specific_logic_ai_generated": true,
  "official_specification": {
    "url": "https://github.com/JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026/blob/main/finals/challenge_3/README.md",
    "blob_sha": "4159341c417f652fea45cd412d79cc52f0d9cad4"
  },
  "research_models": {
    "repository": "https://github.com/KennethLei1492/prebuilt-ai-technique-models",
    "commit": "996c6a3e77ea5ed3b5d406d081e09baf602071c1",
    "consulted": ["Answer Verification", "Task Decomposition"],
    "imported_code": false
  },
  "physical_hardware": "not available; no test claimed"
}
```

[source:0:5] Source: experiments/phase05/05b-astra/ai/rejected-revisions.md; SHA-256 a1dfa8e62f2094f2b5cdea1297b5dd24b55c731f7717b383a18f1e0ae54840a0
```text
﻿# Rejected revisions and corrections

| Revision | Observed result | Correction and status |
|---|---|---|
| Initial staging path | Frozen Phase 4 commit did not contain the Phase 3 recovered RTL and coefficients. | Imported the golden-reference inputs from the Phase 3 handoff commit. Baseline and golden files are preserved byte-for-byte. |
| Initial CSV indexing | Validation run 1 blocked all ten simulations before RTL execution because left/right rows reused frame indices. | Changed generated input and expected CSVs to the generic runner's sequential word-index contract. The original Phase 3 golden CSV remains unchanged; a normalized copy is used by simulation. |
| Reset-gating adapter | Validation run 2 produced zero captures because the Phase 3 wrapper gated the core's I2S pins during generic-runner startup. | Replaced it with the Phase 4 direct-wire adapter. The RTL remains reset-less and uses its original iCE40 power-up initialization. |
| Framework-root adapter path | Validation run 3 blocked all ten simulations because manifest sources resolve relative to the candidate package. | Copied the validated direct-wire adapter to rtl/phase4_dut.sv and changed the manifest to the package-local path. |
| Generic 32-BCLK slots | Validation run 4 executed with 32 BCLK periods per channel, causing zero-valued captures and 506/512 Phase 3 golden word mismatches. | Set SLOT_BITS=16 with Philips one-bit MSB delay to match the successful Phase 4 recovered-design configuration. Validation runs 5 and 6 both passed all ten simulations and the FPGA build. |
| Reproducibility path comparison | The first audit compared absolute expected-file paths, which differ between run directories even when file contents match. | Compare each case's hashed input contents rather than run-specific output paths. The run 5/6 audit confirms identical input contents and bitstreams. |

These were harness and configuration corrections. No RTL correction was needed after the first passing simulation run.

```

[source:0:6] Source: experiments/phase05/05b-astra/tests/audit_results.py; SHA-256 a4408ab5ac8f8cf7d4990ad045454bffd9f6091df6fd96b49da537cfbff21a78
```text
#!/usr/bin/env python3
"""Audit actual captures and build reports, rather than infer from RTL models."""
import argparse,csv,json,math,sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]
TESTS=PACKAGE/"tests"
sys.path.insert(0,str(TESTS))
from candidate_reference import candidate_outputs
from prepare_vectors import completions
from reference import run_reference as baseline

def read_io(path):
    out={}
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): out[(int(r["index"])//2,int(r["channel"]))]=int(r["value"])
    return out

def read_input(path):
    d={}
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if int(r["channel"])==0: d[int(r["index"])]=int(r["value"])
    return [d[i] for i in sorted(d)]

def load_case(run,name,input_path):
    folder=run/name
    actual=read_io(folder/"actual.csv")
    comparison=json.loads((folder/"comparison.json").read_text(encoding="utf-8"))
    return actual,comparison,read_input(input_path)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--run",required=True,type=Path)
    ap.add_argument("--repeat-run",type=Path); ap.add_argument("--output",required=True,type=Path)
    args=ap.parse_args(); run=args.run.resolve()
    report=json.loads((run/"report.json").read_text(encoding="utf-8"))
    case_status={c["name"]:c["status"] for c in report["cases"]}
    normal={
      "phase3-golden":PACKAGE/"tests/vectors/canonical_golden.csv",
      "noisy-audio-1024":PACKAGE/"tests/vectors/noisy_audio_1024.csv",
      "startup-edges":PACKAGE/"tests/vectors/startup_edges.csv",
      "boundary-stress":PACKAGE/"tests/vectors/boundary_stress.csv",
      "random-negative":PACKAGE/"tests/vectors/random_negative.csv",
      "near-miss-negative":PACKAGE/"tests/vectors/near_miss_negative.csv",
      "split-sequence-negative":PACKAGE/"tests/vectors/split_sequence_negative.csv"}
    normal_details={}; baseline_mismatches=0; echo_mismatches=0
    for name,path in normal.items():
        actual,cmp,samples=load_case(run,name,path)
        baseline_mismatches+=cmp["mismatch_count"]
        normal_details[name]={"status":case_status[name],"samples_compared":cmp["samples_compared"],
                              "mismatch_count":cmp["mismatch_count"]}
        for frame in range(len(samples)):
            n=frame-2; expected=samples[n] if 0<=n<len(samples) else 0
            if actual.get((frame,1))!=expected: echo_mismatches+=1

    coeffs=baseline.load_coeffs(str(PACKAGE/"tests/reference/coeffs.json"))
    active_specs=[
      ("activation-1mhz",PACKAGE/"tests/vectors/trigger_1mhz.csv"),
      ("activation-625khz",PACKAGE/"tests/vectors/trigger_625khz.csv"),
      ("retrigger-2x",PACKAGE/"tests/vectors/retrigger_1mhz.csv")]
    events=[]; pass_mismatches=0; tone_metrics=[]
    for name,path in active_specs:
        actual,cmp,samples=load_case(run,name,path)
        _,model_hits,_=candidate_outputs(samples,coeffs)
        hits=completions(samples)
        if hits!=model_hits: raise SystemExit(f"{name}: trigger scanners disagree")
        for hit in hits:
            window=range(hit,min(hit+128,len(samples)))
            bad=[n for n in window if actual.get((n+2,0))!=samples[n]]
            pass_mismatches+=len(bad)
            events.append({"case":name,"trigger_completion_input_frame":hit,
                "expected_bypass_frames":len(window),
                "observed_raw_pass_through_frames":len(window)-len(bad),
                "success":not bad and len(window)==128})
        hit=hits[-1]; stable_start=hit+65; stable_end=min(hit+128,len(samples))
        if stable_end>stable_start:
            indices=range(stable_start,stable_end)
            raw=[samples[n] for n in indices]; filtered=baseline.fir(samples,coeffs)
            expected=[filtered[n] for n in indices]
            observed=[actual.get((n+2,0)) for n in indices]
            raw_rms=math.sqrt(sum(x*x for x in raw)/len(raw))
            filt_rms=math.sqrt(sum(x*x for x in expected)/len(expected))
            out_rms=math.sqrt(sum(x*x for x in observed)/len(observed))
            tone_metrics.append({"case":name,"stable_tone_frames":len(raw),
                "input_rms":raw_rms,"baseline_filtered_rms":filt_rms,"bypass_output_rms":out_rms,
                "baseline_attenuation_db":20*math.log10(max(filt_rms,1e-12)/max(raw_rms,1e-12)),
                "bypass_vs_input_max_abs_error":max(abs(a-b) for a,b in zip(observed,raw))})

    startup,_,_=load_case(run,"startup-edges",normal["startup-edges"])
    startup_zero=sum(startup.get((i,0))==0 and startup.get((i,1))==0 for i in (0,1))
    passed=sum(v=="passed" for v in case_status.values())
    failed=sum(v=="failed" for v in case_status.values())
    blocked=sum(v=="blocked" for v in case_status.values())
    build_path=run/"fpga-build"/"build-summary.json"
    build=json.loads(build_path.read_text(encoding="utf-8")) if build_path.exists() else None
    unit=run/"unit-tests.log"; unit_text=unit.read_text(encoding="utf-8",errors="replace") if unit.exists() else ""
    unit_summary=next((x.strip() for x in unit_text.splitlines() if "Ran " in x and " test" in x),None)
    reproducibility={"repeated_run":False}
    if args.repeat_run:
        repeat=args.repeat_run.resolve()
        second=json.loads((repeat/"fpga-build"/"build-summary.json").read_text(encoding="utf-8"))
        first_hash=build.get("bitstream_sha256") if build else None
        def input_hashes_by_case(root):
            return {d.name:sorted(json.loads((d/"inputs.json").read_text(encoding="utf-8")).get("sha256",{}).values())
                    for d in root.iterdir() if (d/"inputs.json").is_file()}
        input_contents_identical=input_hashes_by_case(run)==input_hashes_by_case(repeat)
        reproducibility={"repeated_run":True,"run1_bitstream_sha256":first_hash,
            "run2_bitstream_sha256":second["bitstream_sha256"],
            "bitstream_identical":first_hash==second["bitstream_sha256"],
            "input_contents_identical":input_contents_identical}
    metrics={
      "run_directory":str(run),"regression_report_passed":report["passed"],
      "regression_cases":{"passed":passed,"failed":failed,"blocked":blocked},
      "framework_unit_test_summary":unit_summary,
      "baseline_mismatch_count":baseline_mismatches,"normal_cases":normal_details,
      "negative_test_count":len(normal),"negative_test_pass_count":sum(
          x["status"]=="passed" and x["mismatch_count"]==0 for x in normal_details.values()),
      "right_echo_mismatch_count":echo_mismatches,"startup_zero_frames_verified":startup_zero,
      "activation_events_tested":len(events),"activation_events_succeeded":sum(x["success"] for x in events),
      "activation_success_rate":sum(x["success"] for x in events)/len(events) if events else None,
      "activation_events":events,"raw_pass_through_mismatch_count":pass_mismatches,
      "payload_frequency_metrics":tone_metrics,"fpga_build":build,
      "reproducibility":reproducibility,
      "hardware_validation":"not run; no Hackster board attached to this environment"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(metrics,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metrics,indent=2))
    if (not report["passed"] or baseline_mismatches or echo_mismatches or startup_zero!=2
        or pass_mismatches or metrics["negative_test_pass_count"]!=len(normal)
        or metrics["activation_events_succeeded"]!=len(events)
        or (args.repeat_run and (not reproducibility["bitstream_identical"] or not reproducibility["input_contents_identical"]))):
        raise SystemExit(1)

if __name__=="__main__": main()
```

[source:0:7] Source: experiments/phase05/05b-astra/reports/evidence-summary-final.json; SHA-256 028333df2ae20867ca3049627466006e9b1e79497af54dbe8b95afee821823b9
```text
{
  "run_directory": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\reports\\validation-run-6",
  "regression_report_passed": true,
  "regression_cases": {
    "passed": 11,
    "failed": 0,
    "blocked": 0
  },
  "framework_unit_test_summary": "Ran 15 tests in 1.804s",
  "baseline_mismatch_count": 0,
  "normal_cases": {
    "phase3-golden": {
      "status": "passed",
      "samples_compared": 512,
      "mismatch_count": 0
    },
    "noisy-audio-1024": {
      "status": "passed",
      "samples_compared": 2048,
      "mismatch_count": 0
    },
    "startup-edges": {
      "status": "passed",
      "samples_compared": 272,
      "mismatch_count": 0
    },
    "boundary-stress": {
      "status": "passed",
      "samples_compared": 1024,
      "mismatch_count": 0
    },
    "random-negative": {
      "status": "passed",
      "samples_compared": 16384,
      "mismatch_count": 0
    },
    "near-miss-negative": {
      "status": "passed",
      "samples_compared": 1000,
      "mismatch_count": 0
    },
    "split-sequence-negative": {
      "status": "passed",
      "samples_compared": 1008,
      "mismatch_count": 0
    }
  },
  "negative_test_count": 7,
  "negative_test_pass_count": 7,
  "right_echo_mismatch_count": 0,
  "startup_zero_frames_verified": 2,
  "activation_events_tested": 4,
  "activation_events_succeeded": 4,
  "activation_success_rate": 1.0,
  "activation_events": [
    {
      "case": "activation-1mhz",
      "trigger_completion_input_frame": 19,
      "expected_bypass_frames": 128,
      "observed_raw_pass_through_frames": 128,
      "success": true
    },
    {
      "case": "activation-625khz",
      "trigger_completion_input_frame": 19,
      "expected_bypass_frames": 128,
      "observed_raw_pass_through_frames": 128,
      "success": true
    },
    {
      "case": "retrigger-2x",
      "trigger_completion_input_frame": 19,
      "expected_bypass_frames": 128,
      "observed_raw_pass_through_frames": 128,
      "success": true
    },
    {
      "case": "retrigger-2x",
      "trigger_completion_input_frame": 177,
      "expected_bypass_frames": 128,
      "observed_raw_pass_through_frames": 128,
      "success": true
    }
  ],
  "raw_pass_through_mismatch_count": 0,
  "payload_frequency_metrics": [
    {
      "case": "activation-1mhz",
      "stable_tone_frames": 63,
      "input_rms": 8532.817752281528,
      "baseline_filtered_rms": 8.149398653440535,
      "bypass_output_rms": 8532.817752281528,
      "baseline_attenuation_db": -60.39933813348164,
      "bypass_vs_input_max_abs_error": 0
    },
    {
      "case": "activation-625khz",
      "stable_tone_frames": 63,
      "input_rms": 8532.817752281528,
      "baseline_filtered_rms": 8.149398653440535,
      "bypass_output_rms": 8532.817752281528,
      "baseline_attenuation_db": -60.39933813348164,
      "bypass_vs_input_max_abs_error": 0
    },
    {
      "case": "retrigger-2x",
      "stable_tone_frames": 63,
      "input_rms": 8532.817752281528,
      "baseline_filtered_rms": 8.149398653440535,
      "bypass_output_rms": 8532.817752281528,
      "baseline_attenuation_db": -60.39933813348164,
      "bypass_vs_input_max_abs_error": 0
    }
  ],
  "fpga_build": {
    "passed": true,
    "frequency_mhz": 10.0,
    "fmax": {
      "ICE_CLK$SB_IO_IN_$glb_clk": {
        "achieved": 15.131569862365723,
        "constraint": 10
      }
    },
    "seed": 1,
    "utilization": {
      "ICESTORM_DSP": {
        "available": 8,
        "used": 0
      },
      "ICESTORM_HFOSC": {
        "available": 1,
        "used": 0
      },
      "ICESTORM_LC": {
        "available": 5280,
        "used": 3662
      },
      "ICESTORM_LFOSC": {
        "available": 1,
        "used": 0
      },
      "ICESTORM_PLL": {
        "available": 1,
        "used": 0
      },
      "ICESTORM_RAM": {
        "available": 30,
        "used": 0
      },
      "ICESTORM_SPRAM": {
        "available": 4,
        "used": 0
      },
      "IO_I3C": {
        "available": 2,
        "used": 0
      },
      "SB_FILTER_50NS": {
        "available": 2,
        "used": 0
      },
      "SB_GB": {
        "available": 8,
        "used": 3
      },
      "SB_I2C": {
        "available": 2,
        "used": 0
      },
      "SB_IO": {
        "available": 39,
        "used": 9
      },
      "SB_LEDDA_IP": {
        "available": 1,
        "used": 0
      },
      "SB_RGBA_DRV": {
        "available": 1,
        "used": 0
      },
      "SB_SPI": {
        "available": 2,
        "used": 0
      },
      "SB_WARMBOOT": {
        "available": 1,
        "used": 0
      }
    },
    "constrained_pins": true,
    "hardware_validated": false,
    "bitstream_sha256": "49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b"
  },
  "reproducibility": {
    "repeated_run": true,
    "run1_bitstream_sha256": "49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b",
    "run2_bitstream_sha256": "49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b",
    "bitstream_identical": true,
    "input_contents_identical": true
  },
  "hardware_validation": "not run; no Hackster board attached to this environment"
}

```

[source:0:8] Source: experiments/phase05/05b-astra/reports/validation-run-7/report.json; SHA-256 689372e2fec50e9f477cd601ef154a72f9a9b8d0fc99b0e66a098c1cfd78881f
```text
{
  "passed": true,
  "failures": 0,
  "blocked": 0,
  "cases": [
    {
      "name": "phase3-golden",
      "status": "passed",
      "detail": "512 samples, max error 0"
    },
    {
      "name": "noisy-audio-1024",
      "status": "passed",
      "detail": "2048 samples, max error 0"
    },
    {
      "name": "startup-edges",
      "status": "passed",
      "detail": "272 samples, max error 0"
    },
    {
      "name": "boundary-stress",
      "status": "passed",
      "detail": "1024 samples, max error 0"
    },
    {
      "name": "random-negative",
      "status": "passed",
      "detail": "16384 samples, max error 0"
    },
    {
      "name": "near-miss-negative",
      "status": "passed",
      "detail": "1000 samples, max error 0"
    },
    {
      "name": "split-sequence-negative",
      "status": "passed",
      "detail": "1008 samples, max error 0"
    },
    {
      "name": "activation-1mhz",
      "status": "passed",
      "detail": "1000 samples, max error 0"
    },
    {
      "name": "activation-625khz",
      "status": "passed",
      "detail": "1000 samples, max error 0"
    },
    {
      "name": "retrigger-2x",
      "status": "passed",
      "detail": "1316 samples, max error 0"
    },
    {
      "name": "fpga-build",
      "status": "passed",
      "detail": "up5k/sg48, timing met, pack/unpack roundtrip verified; hardware unverified"
    }
  ],
  "metadata": {
    "manifest": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\manifest.json",
    "manifest_sha256": "44d70faa315362377a5f7abc2176e0a34832b64eeb94e9fa02fb08adba23e33c",
    "kind": "verified_design",
    "timestamp_utc": "2026-11-13T03:19:06.002018+00:00",
    "waves": "none",
    "verification_evidence": {
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\tests\\BASELINE_PROVENANCE.md": "23213b12b0c92fbab9372ede458380f570a44c517ceb7334eaad5d36619de228",
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\tests\\reference\\README.md": "bfc2942de13e567469dcb88024ee775f85718d979ea578f865f192305ba7f532",
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\constraints\\hackster.pcf": "5bb849ea0d64b98c891ea8a7f474c61a34c9ecd1d4f7d0584bb97169c1a79fe3",
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\reports\\validation-run-5\\report.json": "50568eb11fe3dc381944d95207cdd14de281ff1b9b505dad50cea5c533f7829f",
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\reports\\validation-run-6\\report.json": "02d2cb2f6ae118a21a40c8e498d18ee6cec518a0dcccb1dcca748e8918b13ed3",
      "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN_worktrees\\05b-astra\\experiments\\phase05\\05b-astra\\reports\\evidence-summary-run-5-6.json": "7dd4dd724d90654a2951649468b5a4fcd4755fadc028c88b36453b71c7a3b4c9"
    },
    "git_head": "e72522f265ac36da713cd7a0dcf8dbc64ab21209",
    "git_status": "?? experiments/",
    "toolchain": {
      "tools": {
        "iverilog": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\iverilog.EXE",
          "available": true,
          "exit_code": 0,
          "probe": "Icarus Verilog version 14.0 (devel) (s20260301-972-g5bbcab257-dirty)\n\nCopyright (c) 2000-2026 Stephen Williams (steve@icarus.com)\n\n  This program is free software; you can redistribute it and/or modify\n  it under the terms of the GNU General Public License as published by\n  the Free Software Foundation; either version 2 of the License, or\n  (at your option) any later version.\n\n  This program is distributed in the hope that it will be useful,\n  but WITHOUT ANY WARRANTY; without even the implied warranty of\n  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n  GNU General Public License for more details.\n\n  You should have received a copy of the GNU General Public License along\n  with this program; if not, write to the Free Software Foundation, Inc.,\n  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.\n\nIcarus Verilog Preprocessor version 14.0 (devel) (s20260301-972-g5bbcab257-dirty)\n\nCopyright (c) 1999-2026 Stephen Williams (steve@icarus.com)\n\n  This program is free software; you can redistribute it and/or modify\n  it under the terms of the GNU General Public License as published by\n  the Free Software Foundation; either version 2 of the License, or\n  (at your option) any later version.\n\n  This program is distributed in the hope that it will be useful,\n  but WITHOUT ANY WARRANTY; without even the implied warranty of\n  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n  GNU General Public License for more details.\n\n  You should have received a copy of the GNU General Public License along\n  with this program; if not, write to the Free Software Foundation, Inc.,\n  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.\n\nIcarus Verilog Parser/Elaborator version 14.0 (devel) (s20260301-972-g5bbcab257-dirty)\n\nCopyright (c) 1998-2026 Stephen Williams (steve@icarus.com)\n\n  This program is free software; you can redistribute it and/or modify\n  it under the terms of the GNU General Public License as published by\n  the Free Software Foundation; either version 2 of the License, or\n  (at your option) any later version.\n\n  This program is distributed in the hope that it will be useful,\n  but WITHOUT ANY WARRANTY; without even the implied warranty of\n  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n  GNU General Public License for more details.\n\n  You should have received a copy of the GNU General Public License along\n  with this program; if not, write to the Free Software Foundation, Inc.,\n  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.\n\n FLAGS DLL vvp.tgt\nvvp.tgt: Icarus Verilog VVP Code Generator 14.0 (devel) (s20260301-972-g5bbcab257-dirty)\n\nCopyright (c) 2001-2026 Stephen Williams (steve@icarus.com)\n\n  This program is free software; you can redistribute it and/or modify\n  it under the terms of the GNU General Public License as published by\n  the Free Software Foundation; either version 2 of the License, or\n  (at your option) any later version.\n\n  This program is distributed in the hope that it will be useful,\n  but WITHOUT ANY WARRANTY; without even the implied warranty of\n  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n  GNU General Public License for more details.\n\n  You should have received a copy of the GNU General Public License along\n  with this program; if not, write to the Free Software Foundation, Inc.,\n  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.",
          "sha256": "a61b94abe81b5f80eeceea6fb489717a0439ce92e34e57fee0bea65031f9409c",
          "required": true
        },
        "vvp": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\vvp.EXE",
          "available": true,
          "exit_code": 0,
          "probe": "Icarus Verilog runtime version 14.0 (devel) (s20260301-972-g5bbcab257-dirty)\n\nCopyright (c) 2001-2026 Stephen Williams (steve@icarus.com)\n\n  This program is free software; you can redistribute it and/or modify\n  it under the terms of the GNU General Public License as published by\n  the Free Software Foundation; either version 2 of the License, or\n  (at your option) any later version.\n\n  This program is distributed in the hope that it will be useful,\n  but WITHOUT ANY WARRANTY; without even the implied warranty of\n  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n  GNU General Public License for more details.\n\n  You should have received a copy of the GNU General Public License along\n  with this program; if not, write to the Free Software Foundation, Inc.,\n  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.",
          "sha256": "4b6f69ec3db8dc3b9bcc74a34999f844305348d7791480a1aeba348dd0c43276",
          "required": true
        },
        "yosys": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\yosys.EXE",
          "available": true,
          "exit_code": 0,
          "probe": "Yosys 0.70+385 (git sha1 098e46a36, Release, GNU /usr/bin/x86_64-w64-mingw32-g++ 15.2.1)",
          "sha256": "f7980ce72f198c1c58552a4e0cfb355925e47e510bee94869cff7ef159c7c585",
          "required": true
        },
        "nextpnr-ice40": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\nextpnr-ice40.EXE",
          "available": true,
          "exit_code": 0,
          "probe": "\"nextpnr-ice40\" -- Next Generation Place and Route (Version nextpnr-0.11.1-91-gf934534a)",
          "sha256": "ef95be4860ab09836608c20b41f8c1be3afa340c227302181c3bf411e5595ed2",
          "required": true
        },
        "icepack": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\icepack.EXE",
          "available": true,
          "exit_code": 1,
          "probe": "Usage: C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\icepack.EXE [options] [input-file [output-file]]\n\n    -u\n        unpack mode (implied when called as 'iceunpack')\n\n    -v\n        verbose (repeat to increase verbosity)\n\n    -m0, -m1, -m2\n        master SPI configuration MCLK frequency range (0=low, 1=medium, 2=high)\n\n    -s\n        disable final deep-sleep SPI flash command after bitstream is loaded\n\n    -b\n        write cram bitmap as netpbm file\n\n    -f\n        write cram bitmap (fill tiles) as netpbm file\n\n    -c\n        write cram bitmap (checkerboard) as netpbm file\n        repeat to flip the selection of tiles\n\n    -r\n        write bram data, not cram, to the netpbm file\n\n    -B0, -B1, -B2, -B3\n        only include the specified bank in the netpbm file\n\n    -n\n        skip initializing BRAM",
          "sha256": "5d0a68756b359082bf28fb2c07e20426b4a6632c96473982b7c2fe9ee22cffed",
          "required": true
        },
        "iceunpack": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\iceunpack.EXE",
          "available": true,
          "exit_code": 1,
          "probe": "Usage: C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\iceunpack.EXE [options] [input-file [output-file]]\n\n    -u\n        unpack mode (implied when called as 'iceunpack')\n\n    -v\n        verbose (repeat to increase verbosity)\n\n    -m0, -m1, -m2\n        master SPI configuration MCLK frequency range (0=low, 1=medium, 2=high)\n\n    -s\n        disable final deep-sleep SPI flash command after bitstream is loaded\n\n    -b\n        write cram bitmap as netpbm file\n\n    -f\n        write cram bitmap (fill tiles) as netpbm file\n\n    -c\n        write cram bitmap (checkerboard) as netpbm file\n        repeat to flip the selection of tiles\n\n    -r\n        write bram data, not cram, to the netpbm file\n\n    -B0, -B1, -B2, -B3\n        only include the specified bank in the netpbm file\n\n    -n\n        skip initializing BRAM",
          "sha256": "5d0a68756b359082bf28fb2c07e20426b4a6632c96473982b7c2fe9ee22cffed",
          "required": true
        },
        "icetime": {
          "path": "C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\bin\\icetime.EXE",
          "availabl
[TRUNCATED]
```

[source:0:9] Source: handoffs/phase-05/05b-astra/STATUS.md; SHA-256 5db0eaec7f27516c49b5a89d53cc4113249187eb9df1e4b084c6b4edb59f5338
```text
﻿# Phase 5B Handoff - 05b-astra

**State:** simulation and synthesis passed reproducibly; physical hardware unverified.

## Identity

- Candidate: Independent Candidate B - Astra Reliability
- Branch: `challenge3/05b-astra`
- Worktree: `C:\Users\lowbr\Documents\College\AI\CSAW_FIN_worktrees\05b-astra`
- Frozen base: `e72522f265ac36da713cd7a0dcf8dbc64ab21209`
- Phase 3 baseline/reference commit: `5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f`
- Package: `experiments/phase05/05b-astra/`

## Candidate

The trigger is eight exact consecutive signed 16-bit left samples (`7F00 8101 5A3C A5C3 6D92 926D C33C 3CC3`). On completion it bypasses the left FIR for exactly 128 frames, beginning with the trigger's final sample. Normal filtering then resumes. The recovered right echo, I2S serializer, and two-frame output latency are preserved. The matcher, counter, delay line, and output state have deterministic iCE40 power-up initialization; the core has no external reset input.

## Verification evidence

Full validations 5, 6, and 7 passed 11/11 cases each, with no blocked cases. Each run also passed 15 framework unit tests. The final capture audit compares run 6 and run 7.

- Baseline mismatch count: 0 over 22,248 normal-operation words.
- Right echo mismatches: 0; two startup zero frames verified.
- Negative tests: 7/7; no false activation in random, near-miss, or split-sequence inputs.
- Positive events: 4/4; each produced 128/128 raw frames with zero mismatch, including a two-trigger retrigger case.
- Boundary stress, startup edges, noisy PCM16 audio, baseline golden vectors, and 16,384-word seeded random input all matched exactly.
- I2S tested with 16-bit slots and one-bit Philips MSB delay at 1 MHz and 625 kHz BCLK.
- Reproducibility: runs 6 and 7 had identical test/build input content hashes and identical bitstream SHA-256 `49e24471d676518619d57df5855c533b5eae166feef662cd47fd10d989efb02b`.
- UP5K/SG48 utilization: 3,662/5,280 LCs (69.4%); 0/8 DSP, 0/30 BRAM, and 9/39 IO cells.
- Timing: 10 MHz constraint met; reported Fmax 15.1316 MHz. IceStorm pack/unpack round trip passed.

Reports are in `experiments/phase05/05b-astra/reports/`. The final run is `validation-run-7`; the combined capture/build/reproducibility summary is `evidence-summary-final.json`. `ai/rejected-revisions.md` records the initial CSV-format, adapter, source-path, slot-width, and first audit-comparison corrections.

## Reproduction

From the worktree root:

```powershell
$Suite = 'C:\Users\lowbr\Documents\College\AI\CSAW_FIN\.worktrees\phase-04\.tools\oss-cad-suite'
$Python = Join-Path $Suite 'lib\python3.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $Python experiments/phase05/05b-astra/tests/prepare_vectors.py
& $Python infrastructure/run.py --suite $Suite validate --manifest experiments/phase05/05b-astra/manifest.json --output experiments/phase05/05b-astra/reports/reproduction-run
& $Python experiments/phase05/05b-astra/tests/audit_results.py --run experiments/phase05/05b-astra/reports/validation-run-6 --repeat-run experiments/phase05/05b-astra/reports/reproduction-run --output experiments/phase05/05b-astra/reports/reproduction-evidence.json
```

## Documentation agent and limitations

The Project Scribe `record-test` interface ran the final full validation and recorded its actual exit code (`0`) and stable Git state. A Scribe evidence preview is prepared locally with Google publishing disabled. The installed project setup remains marked unactivated: its model identifier is a placeholder and the OpenClaw agent/Gateway is not configured in this environment, so no model-generated Scribe synthesis is claimed.

No Hackster board was available, so no physical timing, startup, I2S, payload, or bitstream programming result is claimed. The recovered audio source is a Phase 2 behavioral reconstruction, and LED/RGB pin roles are provisional. The public remote was not written. No overall candidate winner was selected.

```

## Activity evidence

### [event:1] test-runner / phase05b-final-validation

2026-11-13T03:19:06.485Z — TestCommand; model: not applicable; HEAD: e72522f265ac36da713cd7a0dcf8dbc64ab21209.
Root: C:\Users\lowbr\Documents\College\AI\CSAW_FIN_worktrees\05b-astra
Tool: explicit command; recorded exit: 0.
Recorded command: ["C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite\\lib\\python3.exe","infrastructure/run.py","--suite","C:\\Users\\lowbr\\Documents\\College\\AI\\CSAW_FIN\\.worktrees\\phase-04\\.tools\\oss-cad-suite","validate","--manifest","experiments/phase05/05b-astra/manifest.json","--output","experiments/phase05/05b-astra/reports/validation-run-7"]; tracked state stable: true; output SHA-256: 7f18cd494fe18944e50bea34167a3520158769e1dafc4a1e0a652ad6a79f2eae.
Recorded output excerpt:
```text
PASSED: phase3-golden: 512 samples, max error 0
PASSED: noisy-audio-1024: 2048 samples, max error 0
PASSED: startup-edges: 272 samples, max error 0
PASSED: boundary-stress: 1024 samples, max error 0
PASSED: random-negative: 16384 samples, max error 0
PASSED: near-miss-negative: 1000 samples, max error 0
PASSED: split-sequence-negative: 1008 samples, max error 0
PASSED: activation-1mhz: 1000 samples, max error 0
PASSED: activation-625khz: 1000 samples, max error 0
PASSED: retrigger-2x: 1316 samples, max error 0
PASSED: fpga-build: up5k/sg48, timing met, pack/unpack roundtrip verified; hardware unverified
Report: C:\Users\lowbr\Documents\College\AI\CSAW_FIN_worktrees\05b-astra\experiments\phase05\05b-astra\reports\validation-run-7\report.json


```

## Evidence limits

Hooks observe configured local sessions only. Missing model identifiers remain unknown. A successful tool call or Stop event does not prove a successful test. Shared-worktree changes are not attributable to one session. Source reads and Git snapshots are not atomic with concurrent edits. Test wrapper fingerprints cover HEAD, tracked diffs, and status names, not all untracked bytes. Older reports and events remain local.
