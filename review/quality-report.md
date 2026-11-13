# Reconstruction Quality Report — Subphase R

**Reviewed:** Phase 2 `1befb30` + Phase 4 `2da1d72` · **Branch:** `challenge3/reconstruction-review`
· **Date:** 2026-11-12. Measurable snapshot per Subphase-R §6.

## Scorecard

| Metric | Value |
|---|---|
| Verified architectural features (§2 components) | **10 / 10** (behavioral) |
| I/O-behavioral claims independently corroborated | **12 / 12** (C1–C12) |
| Independent evidence types brought to bear | **6** (bitstream structure, tool source, integer/DTFT math, gate-level sim, adversarial sim, external reference) |
| Reference-output mismatches (netlist vs model) | **0** (2048/2048 real audio; 1779/1779 adversarial) |
| Known arithmetic discrepancies | **0** (rounding uniquely pinned; accumulator sufficiency proven) |
| Timing / framing discrepancies | **0** (pins, Philips format, 2-frame latency all confirmed vs official bridge + README) |
| Unresolved assumptions affecting I/O behavior | **0** |
| Unresolved items total | **4** (O1 micro-arch *low*, O2 LED roles *low*, O3 hardware *later-phase*, O4 Phase4 handoff *fix proposed*) |
| Defects found in the reconstruction | **0** |
| Actionable integration findings | **1** (R-001, verified fix provided) |
| Review regression experiments passing | **11 / 11** |

## Review regression suite (this branch)

| Experiment | Script | Result |
|---|---|---|
| Provenance / integrity | (bash) iceunpack + sha256 | `.bin` 2547d7a2… matches; `.asc` byte-identical regen |
| Filter math (integer + DTFT) | `rv_filter_math.py` | all exact invariants PASS; −3 dB 3296.3 Hz; lin-phase resid 5.4e-15 |
| Bitstream structure | `rv_bitstream_struct.py` + icebox_vlog | 0 MAC16, 1 zero-init RAM, DSP=position defaults |
| Adversarial arithmetic | `rv_adversarial_arith.py` | round-half-+∞ unique (0 vs 599/528/60/60); rails exact |
| Real-audio bit-exact (noisy WAV) | `rv_realaudio.py` | netlist==indep model==sw_fir.py, 2048/2048 |
| Real-audio bit-exact (clean WAV, 2nd dataset) | `rv_realaudio.py` | 2048/2048 on a different source (48 kHz stereo) |
| Right-channel independence | `rv_rchannel.py` | filtered=FIR(L), echo=L with R≠L, 512/512 |
| Phase 4 golden format (fix) | `rv_make_phase4_golden.py` | passes Phase 4 `read_samples`/`compare` |
| Recon-RTL equivalence + measured latency | workflow agent (sim) | recon==netlist==model 1024/1024; LAT measured=2; 0 DSP/0 BRAM synth |
| Blind coefficient re-derivation | workflow agent (sim) | own gen/decode, never read `coeffs.json` → identical 63 taps (max diff 0) |
| Phase 3 golden cross-check (`5dedf4c`) | `rv_phase3_golden_check.py` | values 254/254 vs my model; format rejected by Phase 4 reader (R-001 residual) |

## Upgrades vs Phase 2 (claims strengthened by independent review)

1. **Rounding mode** — Phase 2: "confirmed round-half-toward-+∞." Review:
   **uniquely discriminated** against floor, truncate, half-even, and half-away on
   the netlist (the 60 tie-cases decide it). Not underdetermined.
2. **Accumulator width** — Phase 2 §9.2 listed it **open**. Review: **closed** —
   the original accumulator provably does not wrap at the ±2.07×10⁹ worst case
   (netlist saturates to the exact rails, matching the bignum model), so
   infinite-precision-then-saturate is exact.
3. **DSP non-use** — Phase 2: "defaults, mirror-symmetric." Review: strengthened to
   "DSP tile config is a pure function of (subtile, y) **mirror-identical across
   both columns**; authoritative `icebox_vlog` extracts **0** MAC16."
4. **"BRAMs: 2"** — Phase 2 asserted a y-normalization artifact. Review:
   **mechanism verified in the `icebox_stat` source** (y=23→22, y=24→24).
5. **Latency / interface** — Phase 2 cross-checked `audio_bridge.py` comments.
   Review: independently re-fetched the official `audio_bridge.py` *and* the
   challenge README's "two frames later" — external ground truth.

## Bottom line

The Phase 2 reconstruction is **accurate and well-supported**: every claim about
the filter's externally observable behavior (interface, framing, latency, taps,
arithmetic, rounding, saturation, output formatting, no-DSP, one-BRAM) is
independently corroborated, and five were strengthened. The only actionable item
is an integration/handoff-format gap (R-001) with a proposed, self-verified fix.
The remaining open items (original micro-architecture, LED roles, on-hardware
confirmation) are correctly scoped as open and do not affect any behavioral
conclusion. **Recommendation: Phase 3 may build the Trojan baseline on this
reconstruction with high confidence in untriggered-output bit-identity.**
