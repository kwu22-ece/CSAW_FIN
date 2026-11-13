# CSAW 2026 — Challenge 3 — Phase 3 Milestone Report
## Original FIR Filter Reconstruction and Verification (Golden Reference)

**Phase:** 3 — establish a reliable, reproducible golden reference for the
*original* audio filter and validate the reconstruction. **No Trojan is designed
and the bitstream is not modified** — that is a later phase. Work stops at the
end of Phase 3.
**Date:** 2026-11-12.
**Branch:** `challenge3/03-baseline` (Git worktree `.worktrees/phase-03`, based
on Phase 2 `1befb30`).
**Target:** `fir_audio_top.bin` — streaming FIR audio filter on a Lattice
iCE40-UP5K (SG48), Hackster board.

Every claim is backed by a reproducible artifact (`baseline/`, `sim/`,
`analysis/`, `build/reports/`). One command regenerates all of it:
`python baseline/regression.py`.

---

## 0. Provenance
- Tooling: Claude Code (Anthropic) in the Claude desktop app; models Claude
  Fable 5.2 then Claude Opus 4.8 (harness switch mid-session).
- Parallel work: Codex owns the Phase 4 reusable sim/synthesis framework
  (`challenge3/04-infrastructure`). Coordination is via `handoffs/` only; no
  Codex-owned files were edited. The Phase 4 framework reported BLOCKED (exit 2)
  for the recovered-design template pending the verified Phase 3 handoff — which
  this phase supplies (`handoffs/phase-03/`).
- Nature of work: independent reference modeling, coefficient re-recovery,
  bit-accurate arithmetic, latency and frequency analysis, HDL co-simulation
  across six input families + real audio, FPGA place-and-route sign-off, and a
  one-command regression. No hardware was programmed.

## 1. Starting point verified
The Phase 2 recovered artifacts were re-derived from scratch: re-simulating the
committed gate-level netlist and decoding the impulse response reproduced
`recovered/coeffs.json` **bit-identically** (63 taps, Σ=32768, symmetric,
center 13920; LAT=2; MSB-first). The reconstructed RTL and current code match
the documented findings.

## 2. Golden reference model [VERIFIED]
`baseline/ref_fir.py` is an independent re-implementation of the fixed-point
filter (not copied from the Phase 2 model). It cross-checks **bit-for-bit**
against `scripts/sw_fir.py` on all six vector families plus 12000 random samples
— 0 mismatches, max |err| 0 (`build/reports/model-crosscheck.json`).

Arithmetic (confirmed to both rails and on crafted values):
`acc = Σ_k h[k]·x[n−k]`, `y = sat16((acc + 2^14) >> 15)` — round half toward
+∞, then saturate to int16. Zero history before index 0 (power-up state). The
right channel echoes the input unmodified. End-to-end latency = 2 frames.

## 3. Numerical verification [VERIFIED]
Independent software + HDL methods; quantitative tables in
`analysis/phase3-verification.md`.

- **HDL battery** (`build/reports/hdl-battery.json`): gate-level netlist ≡
  reconstructed RTL ≡ golden model, **0 mismatches** over impulse / step /
  sinusoid / chirp / random / boundary — 4952 input samples per engine,
  9904 filtered-sample comparisons — with echo-channel match 100% and decoded
  latency 2 on every family.
- **Real audio** (`build/reports/wav-cosim.json`): both engines bit-exact to the
  model on `what_a_piece_of_work-noisy.wav`; canonical dataset emitted and found
  consistent with the Phase 2 reference vectors.
- **Boundary/saturation:** sustained rails and Nyquist-rate full-swing drive the
  output to both int16 limits; all methods agree (saturation, not wraparound).

## 4. Frequency response [VERIFIED — independent method]
`build/reports/freq-metrics.json` (scipy.freqz / group_delay, independent of the
Phase 2 hand DTFT): DC gain **0.000 dB**, **−3 dB = 3296.4 Hz** (Phase 2:
3296.3), stopband **−55.9 dB** above 4 kHz, passband ripple ≤ 0.015 dB, group
delay **31.000 samples**, linear-phase residual ~8e−15. Confirms the speech-band
low-pass with exact linear phase.

## 5. FPGA sign-off [VERIFIED]
`analysis/phase3-fpga-build.md`: reconstructed RTL + Phase 3 PCF
(`handoffs/phase-03/fir_audio_top_hackster.pcf`) place-and-route on UP5K/SG48:
3283/5280 LC, 0 DSP, 0 BRAM, 9 IO; **Fmax 14.49 MHz (nextpnr) / 14.21 MHz
(icetime), PASS at 10 MHz**; all PCF pins valid and routed.

## 6. Handoff to Phase 4 (Codex) [DELIVERED]
`handoffs/phase-03/` closes every item on the Phase 4 `awaiting[]` list:
- `phase4_dut.v` — port adapter for the `phase4_dut(clk,rst,bclk,lrclk,sd_in,
  sd_out)` contract (reset-less core; `rst` = hold-in-idle / power-up align).
- `fir_audio_top_hackster.pcf` — verified SG48 constraints.
- `run_reference.py` — self-contained reference-model entry point (argv contract
  `{python} {input} {output}`; `index,channel,value` output; latency options).
- `reference_io.in.csv` / `reference_io.csv` — canonical input + golden output.
- `INTERFACE.md` — full interface/clock/reset/latency/format spec.

## 7. Verified facts (summary)
1. 63-tap Type-I linear-phase low-pass FIR, Q1.15, Σ=32768 (0 dB DC);
   coefficients identical to Phase 2.
2. Arithmetic: round half toward +∞ then int16 saturate; exercised to both rails.
3. End-to-end latency exactly 2 frames; left=filtered, right=echo; MSB-first,
   bit-offset 0.
4. Gate-level netlist (from the original bitstream), reconstructed RTL, and two
   independent software models are **bit-for-bit identical** on the filtered
   channel across all tested inputs.
5. −3 dB ≈ 3.30 kHz; stopband ≈ 56 dB above 4 kHz; group delay 31 samples;
   exact linear phase.
6. Reconstruction places, routes, and meets timing on UP5K/SG48 at 10 MHz.

## 8. Limitations / open
- **No hardware was programmed this phase**; all results are simulation / P&R.
  On-board `sw_filter == hw_filter` confirmation is the remaining step and is
  what the Phase 4 recovered-design template should now execute.
- **Bitstream-level identity to the original is not claimed.** The reconstruction
  is a behavioral equivalent (register delay line vs the original's BRAM delay
  line); the *filtered-audio* output is bit-identical (demonstrated).
- The original's internal micro-architecture (direct vs transposed, BRAM
  addressing, exact accumulator width) is not reduced to a gate-level structural
  description; its behavior is fully captured by the impulse response + model.
- LED vs R/G/B individual pin roles (38–41) unresolved; not on the audio path.

## 9. Deliverables (this branch)
- Models/datasets: `baseline/ref_fir.py`, `baseline/gen_testvectors.py`,
  `baseline/analyze_response.py`, `baseline/validate_models.py`,
  `baseline/regression.py`.
- HDL validation: `sim/i2s_cosim.py`, `sim/run_battery.py`, `sim/run_wav.py`.
- Analysis: `analysis/phase3-verification.md`, `analysis/phase3-fpga-build.md`.
- Handoff: `handoffs/phase-03/` (adapter, PCF, reference model + dataset,
  interface spec, status).
- Reports (regenerable): `build/reports/*.json`.
