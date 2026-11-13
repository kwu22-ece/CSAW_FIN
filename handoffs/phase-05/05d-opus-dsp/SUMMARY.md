# Phase 05 handoff — Candidate 05d (DSP-driven, Claude Opus 4.8)

**Branch:** `challenge3/05d-opus-dsp` · **baseline:** `e72522f` (Phase-4 infra) ·
**worktree:** `CSAW_FIN_worktrees/05d-opus-dsp` · **candidate tree:**
`experiments/phase05/05d-opus-dsp/`.

This is **Independent Candidate D** — a signal-processing-driven hardware-Trojan
candidate developed independently from the recovered filter's mathematics. No
other candidate's work was inspected or used. All RTL/exploit logic and analysis
are AI-generated (logs in `experiments/phase05/05d-opus-dsp/ai/`).

## Approach (frequency-domain Trojan)

- **Trigger:** a **multiplier-free Goertzel** single-bin spectral detector tuned
  to **fs/3 = 5333.33 Hz** (exact DFT bin, window N=576). At fs/3 the Goertzel
  coefficient is exactly −1, so the per-sample recurrence is `s0 = x − s1 − s2`
  (adders only) and the arm metric is the L1 magnitude `|s1|+|s2|` vs a 2²³
  threshold. fs/3 sits ~−60 dB down in the filter stopband, so the key tone is
  masked in normal output and normal audio carries little energy there.
- **Payload:** once armed, the taps become `h′[k] = (−1)ᵏ·h[k]` (odd taps negated)
  — an exact **spectral inversion** turning the low-pass into a high-pass (voice
  passband attenuated ~−60 dB). Implemented as a gated conditional negate on the
  coefficient feeding the existing serial MAC: **zero extra coefficient ROM**, and
  the armed filter stays exactly linear-phase with the same accumulator bound.
- **Stealth:** when disarmed the modified design is **byte-identical** to the
  golden filter (arm gates the only change); datapath, I2S timing, 2-frame
  latency, echo and LEDs are untouched; arm is not exposed on any pin.

The design deliberately differs from structural/counter/control triggers — both
trigger and payload live in the frequency domain. An earlier 7500 Hz / energy
variant was rejected because its multipliers synthesized to 173 % of the UP5K LC
budget; the fs/3 / coefficient-−1 / L1 redesign is multiplier-free (+439 LC).

## Test evidence (executed)

Shared Phase-4 harness (iverilog/vvp, yosys/nextpnr/icetime) + numpy/scipy.

- **Untriggered (vs golden model): 10/10 HDL cases bit-identical, max error 0** —
  edges, impulse, random, sine, silence, real WAV (256 & 2048 frames), near-key
  5200/5467 Hz, 500 Hz probe. (normal-operation equivalence + trigger selectivity)
- **Triggered (vs Trojan model): 3/3 HDL cases bit-identical** — full-scale and
  80 %-scale fs/3 keys arm at sample 576; key-then-low-probe.
- **Trigger specificity:** 0 false arms over 15 s of real audio; threshold 34.9 dB
  above worst real-audio window; adjacent full-scale tones (±130 Hz) stay >20 dB
  below threshold.
- **Payload effect:** armed, a 500 Hz passband tone is attenuated **−60.8 dB**
  (RMS 14178→13); the fs/3 key rises **+72 dB** (blocked→passed). Golden-vs-armed
  frequency response in `reports/figures/payload_spectral.svg`.
- **FPGA (iCE40-UP5K/SG48):** 3704/5280 LC, 0 DSP, 0 RAM, **Fmax 14.41 MHz** at the
  10 MHz board clock (timing met, pack/unpack roundtrip verified). Golden baseline
  3265 LC → +439 LC overhead.
- **Numerics:** round-half-toward-+∞ proven (0/567715 mismatch); armed L1 norm =
  golden L1 norm (63248) ⇒ no new overflow/saturation.
- Independent re-derivation of the equivalence/trigger/payload claims:
  `reports/verification-report.md`.

Evidence files: `experiments/phase05/05d-opus-dsp/reports/` (and `reports/evidence/`
for compact copies of the gitignored harness run outputs).

## Results

A complete, synthesizable, AI-authored candidate that is **bit-exact to the golden
filter until it hears a secret fs/3 tone**, then measurably inverts the filter
response, at ~8 % logic-cell overhead and full timing closure — verified in
simulation and place-and-route.

## Outstanding limitations

- **On-board `sw == hw` is PENDING** — no iCE40 board was programmed; all results
  are bit-exact simulation + P&R/timing.
- Bitstream-level identity to the original is not claimed (behavioural
  reconstruction, inherited from Phase 2/3).
- Arm latch persists until power cycle (reset-less core); no disarm key (out of
  scope, documented).

## Documentation agent

Fed to **Project Scribe** via `record-test` (verification exit) and a model-free
`preview` evidence report (the agent's model is a placeholder / not activated, so
no model synthesis or Google publishing was performed). See
`documentation-agent-handoff.md`.

Full detail: `experiments/phase05/05d-opus-dsp/README.md`, `.../manifest.json`,
`.../ai/decisions/`, `.../reports/`.
