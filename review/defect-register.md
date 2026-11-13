# Reconstruction Review — Prioritized Defect & Uncertainty Register

**Subphase R — Independent FPGA Reconstruction Review**
**Reviewed snapshot:** Phase 2 `challenge3/02-reverse-engineering` @ `1befb30`
(netlist/RTL/coeffs) and Phase 4 `challenge3/04-infrastructure` @ `2da1d72`
(test harness). **Review branch:** `challenge3/reconstruction-review`.
**Date:** 2026-11-12. All items below are backed by a reproducible experiment in
`review/scripts/` with its log in `review/logs/`.

Categories: **VERIFIED** (independent evidence confirms) · **SUPPORTED/INCOMPLETE**
(consistent, but some aspect not independently closed) · **UNVERIFIED** · **CONTRADICTED**.

## Component assessment (Phase 2 §2 checklist)

| # | Component | Category | Independent evidence (method) |
|---|---|---|---|
| 1 | I2S signal interpretation | **VERIFIED** | official `audio_bridge.py` pins/format + gate-sim echo 1.0000 |
| 2 | Framing & clock behavior | **VERIFIED** | Philips 16b MSB-first L/R, WS 1-bit-early, single 10 MHz clk, no PLL — matches bridge + `icebox_stat` PLLs:0 |
| 3 | Internal state & registers | **VERIFIED (behavioral)** | zero-init confirmed (`.ram_data` all-zero + FF power-up 0); exact original register topology = open **O1** |
| 4 | FIR architecture | **VERIFIED (behavioral)** | 63-tap direct-form MAC, no DSP (icebox_vlog=0 MAC16), 1 BRAM delay line; original direct-vs-transposed form = **O1** |
| 5 | Filter coefficients | **VERIFIED (exact)** | integer+DTFT audit; gate-sim re-derivation identical; RTL `COEF[]`==`coeffs.json` |
| 6 | Pipeline latency | **VERIFIED** | README "two frames later" + host LATENCY=2 + measured echo LAT=2 (twice) |
| 7 | Fixed-point arithmetic | **VERIFIED** | netlist == infinite-precision accumulate on 1779+2048 frames, 0 mismatch |
| 8 | Rounding & saturation | **VERIFIED (uniquely pinned)** | round-half-+inf uniquely beats floor/trunc/half-even/half-away on netlist; both rails reached & exact |
| 9 | Output formatting | **VERIFIED** | left=filtered / right=echo-of-left, 2-frame delay — echo oracle 1.0000 |
| 10 | Reset & startup | **VERIFIED (sim)** | zero-history startup transient matches model from sample 0; on-hardware = open **O3** |

**No CONTRADICTED items. No defects found in any I/O-behavioral claim.** Several
claims were *strengthened* beyond Phase 2 (see quality report §"Upgrades").

## Prioritized issue queue (highest-impact first)

### P1 — Interface interpretation / timing
- **CLOSED-CONFIRMED.** Pins (36/34/32/31), Philips 16-bit MSB-first L/R, WS one
  bit early, 2-frame latency — all independently confirmed vs the official
  `tools/audio_bridge.py` and the challenge README ("two frames later").
  Evidence: `review/logs/` (WebFetch cross-check), echo LAT=2 in every sim.

### P2 — FIR coefficients / arithmetic / architecture
- **CLOSED-CONFIRMED (coeffs).** 63 taps exact; Σ=32768; symmetric; center 13920.
  Methods: `rv_filter_math.py` (integer+DTFT), canonical gate-sim re-derivation
  (identical), adversarial random-stimulus joint match (0/1779), **and a fully
  blind independent re-derivation** (separate agent, own stimulus+decoder, never
  opened `coeffs.json`; both +32767 and −32768 impulses) → identical 63 taps,
  **max elementwise diff 0**.
- **CLOSED-CONFIRMED (rounding).** `sat16((acc+2^14)>>15)` = round-half-toward-+∞,
  **uniquely discriminated** vs 4 alternative conventions (`rv_adversarial_arith.py`:
  0 vs 599/528/60/60 mismatches on the netlist).
- **CLOSED-CONFIRMED (accumulator width / saturation).** Resolves Phase 2 §9.2
  open item: at worst-case acc ≈ ±2.07×10⁹ the netlist saturates to the exact
  int16 rails and matches infinite-precision-then-saturate; no premature
  saturation (0/1779). So the original accumulator is wide enough (≥32-bit
  effective) and the bignum sw model is exact.
- **OPEN O1 (low impact).** The *original's* internal micro-architecture (direct
  vs transposed serial/parallel MAC, BRAM circular-buffer addressing, exact
  accumulator bit width) is not reduced to a gate-level structure. Behavior is
  fully captured by the impulse response + bit-exact model; affects no I/O
  conclusion. Correctly scoped as open by Phase 2.

### P3 — Pipeline / buffering / state
- **CLOSED-CONFIRMED (BRAM).** Exactly one zero-init SB_RAM40_4K (`ram40_6_23`),
  16-bit words, ≤64 entries — a sample delay line, not a coeff ROM. icebox_vlog
  (authoritative) = 1 RAM; `.ram_data` all-zero. The `icebox_stat` "BRAMs: 2" is a
  y-normalization artifact (one block's ramb y=23→key 22 and ramt y=24→key 24),
  **mechanism verified in `icebox_stat` source** — Phase 2 explanation correct.
- **CLOSED-CONFIRMED (DSP non-use).** icebox_vlog extracts 0 MAC16; DSP tile config
  is a pure function of (subtile, y) **mirror-identical across both columns** →
  position-dependent default, not a used MAC. (`rv_bitstream_struct.py`.)

- **CLOSED-CONFIRMED (recon-RTL equivalence, C12).** Independent sim: the
  reconstructed RTL == gate-level netlist == independent fixed-point model,
  **1024/1024** bit-exact on real audio; latency **measured** (echo sweep, unique
  peak) = 2 frames; `yosys synth_ice40` maps it with 0 DSP / 0 BRAM (behavioral
  equivalent via register delay line — a functional, not structural, copy).
- **CLOSED-CONFIRMED (right channel ignored).** With R≠L (reversed/negated),
  filtered-left == FIR(LEFT) and echo-right == LEFT input, 512/512; right input is
  neither filtered nor echoed (`rv_rchannel.py`). Confirms output formatting.

### P4 — Boundary-case & reset verification
- **CLOSED-CONFIRMED (saturation rails).** Both +32767 and −32768 reached and exact.
- **VERIFIED (sim) / OPEN O3 (hardware).** Zero-history startup matches in sim;
  on-board confirmation is a later step (no hardware used this phase).

### P5 — Maintainability / integration
- **R-001 (ACTIONABLE, revised vs Phase 3 `5dedf4c`).** Originally (at 1befb30): no
  `phase4_dut` adapter and the only reference CSV was unreadable by Phase 4. Phase 3
  `5dedf4c` has since added the adapter + an `index,channel,value` reference whose
  **values are independently validated** (254/254 filtered & echo vs my model, at
  2-frame latency — `rv_phase3_golden_check.py`). **Residual bug:** Phase 3's
  `reference_io.csv` `index` column is frame-index (`0,0,1,1,…`) where Phase 4
  `results.read_samples()` requires per-row word index (`0,1,2,3,…`) — Phase 4
  **rejects it** ("nonsequential index … at 1"). Fix is trivial (emit running
  index; `rv_make_phase4_golden.py` shows the passing pattern +
  `latency_words` convention). Handoff/format gap, not a reconstruction defect. Owner: Phase 3.

## Open uncertainties (carried forward)
- **O1** original MAC micro-architecture (behavior-irrelevant). *low*
- **O2** individual LED vs R/G/B pin roles (38–41), not on the audio path. *low*
- **O3** no on-hardware run yet; all evidence is bitstream + gate-level sim. *medium (later phase)*
- **O4 → R-001 (revised)** Phase 3 `5dedf4c` adapter + reference landed; values
  validated; residual index-convention bug still fails Phase 4's reader. *medium, owner Phase 3*
