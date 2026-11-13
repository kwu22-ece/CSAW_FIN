# CSAW 2026 — Challenge 3 — Phase 2 Milestone Report
## FPGA Bitstream Analysis and Architecture Reconstruction

**Phase:** 2 — reverse-engineering only. No Trojan was designed and the bitstream
was not modified. Work stops at the end of Phase 2.
**Date:** 2026-11-12.
**Branch:** `challenge3/02-reverse-engineering` (Git worktree `.worktrees/phase-02`).
**Target:** `fir_audio_top.bin` — a streaming FIR audio filter on a Lattice
iCE40-UP5K (sg48), Hackster board.

Every claim below is backed by a reproducible artifact in this branch
(`recovered/`, `scripts/`, `analysis/`). Facts are separated from hypotheses in
§8–§9.

---

## 0. AI session provenance
- Tooling: Claude Code (Anthropic) in the Claude desktop app.
- Models this session: Claude Fable 5.1, then Claude Opus 4.8 (harness switch
  mid-session).
- A separate Codex instance is preparing Phase 4 (sim/synthesis infrastructure)
  in parallel; coordination is via `handoffs/phase-02/` (read-only for Codex).
- Nature of work: unpack/analyze the bitstream, gate-level simulation, filter
  analysis, clean-RTL reconstruction, and multi-method verification. No RTL from
  the bitstream was executed on hardware this phase.

## 1. Method overview
1. **Unpack** the bitstream with IceStorm (`iceunpack`) → `recovered/fir_audio_top.asc`.
2. **Netlist** with `icebox_vlog` → a gate-level Verilog (`recovered/netlist/`).
   Because the design uses no DSP blocks (§3), this netlist is *functionally
   complete* and directly simulatable.
3. **Inventory** resources (`icebox_stat`), decode tile usage, and map I/O.
4. **Simulate** the netlist through a faithful I2S controller testbench; recover
   the impulse response (= coefficients) exactly, using the echo channel as an
   alignment oracle.
5. **Characterize** the filter (frequency response, linear phase, gain).
6. **Reconstruct** a clean, synthesizable baseline RTL and prove its filtered
   output is bit-identical to the bitstream.
7. **Cross-verify** every major conclusion by independent methods (§7).

## 2. Interface and I/O map [VERIFIED]
9 IOBs, all on the top edge. Pin numbers from the icebox sg48 pinloc DB,
**cross-validated** against the GPIO comments in the challenge's
`tools/audio_bridge.py`:

| Netlist port | Pin | Dir | Signal |
|---|---|---|---|
| `io_13_31_0` | 37 | in | **ICE_CLK** (~10 MHz; clocks all 299 FFs + the BRAM) |
| `io_9_31_1` | 36 | in | **I2S_BCLK** (oversampled) |
| `io_13_31_1` | 34 | in | **I2S_WS** |
| `io_16_31_0` | 32 | in | **I2S_SD_IN** |
| `io_16_31_1` | 31 | out | **I2S_SD_OUT** (registered) |
| `io_8_31_1` / `io_4_31_0` / `io_5_31_0` / `io_6_31_0` | 38/39/40/41 | out | ICE_LED + RGB (roles not individually separated) |

BCLK=36, WS=34, SD_IN=32, SD_OUT=31 match the bridge firmware exactly.

**Clocking:** single clock domain (all 299 FFs + the BRAM on `ICE_CLK`); no PLL.
BCLK/WS/SD_IN are oversampled and edge-detected (each has one synchronizer
fanout), so BCLK is data, not a clock.

**I2S framing (verified by 2147/2147 echo matches):** standard Philips, 16-bit,
MSB-first, L then R, 32 BCLK/frame; WS changes one bit early. Left carries the
sample to filter; output left = filtered, output right = unmodified echo.
Samples are 16-bit signed, treated as Q1.15. **End-to-end latency = 2 frames.**

## 3. Implementation structure [VERIFIED]
`icebox_stat`: DFFs 299, LUTs 1260, CARRYs 124, BRAMs 2 (see note), IOBs 9,
PLLs 0, GLBs 6.

- **No DSP/MAC16 blocks are used.** The UP5K's 8 hard DSP blocks sit in columns
  x=0 and x=25. Column 25 has **zero** routed net-segments; column 0 carries only
  global-clock-spine and neighbor-op bleed segments — no functional DSP I/O. The
  DSP tiles' config bits are nextpnr defaults (only 3 distinct, position-dependent
  patterns, mirror-symmetric across the two columns). The 63-tap multiply-
  accumulate is therefore realized in the **LUT + carry fabric**.
- **Sample delay line in BRAM.** One connected `SB_RAM40_4K` (`ram40_6_23`),
  16-bit words, 6 address bits (≤64 entries), **zero-initialized** — a read/write
  sample buffer, not a coefficient ROM (coefficients are in the fabric).
  `icebox_stat` prints "BRAMs: 2", but independent decode (§7) shows only one
  physical block has its PowerUp bit set; the "2" is an x,y-normalization artifact
  that maps that block's `ramb` and `ramt` tiles to two location keys.

## 4. The filter [VERIFIED — exact]
- **63-tap, Type-I linear-phase (symmetric) FIR low-pass.** Coefficients are
  fixed Q1.15 integers, recovered exactly (§5 method) and stored in
  `recovered/coeffs.json`.
- Symmetry `h[i] = h[62−i]` holds exactly. Center tap `h[31] = 13920`.
  **Σh = 32768 = exactly 1.0** → 0 dB DC gain.
- Frequency response (fs = 16 kHz, `scripts/analyze_filter.py`,
  `analysis/freq_response.csv`): flat passband (ripple < 0.02 dB) to ~3 kHz,
  **−3 dB ≈ 3.3 kHz** (3296.3 Hz), −10.5 dB at 3.5 kHz, −59.7 dB at 4 kHz,
  stopband ≈ **56 dB** (−55.9 dB worst case) above 4 kHz. Group delay 31 samples
  (1.94 ms).
- This is the documented "passes the speech band, strongly attenuates above it"
  low-pass; the 3.3 kHz edge is the classic speech/telephony band.

Coefficients (Q1.15, index 0..62):
```
-14, 20, 27, -12, -45, -9, 63, 49, -66, -109, 34, 176, 49, -219, -187, 198, 362,
-71, -524, -188, 600, 577, -497, -1062, 104, 1575, 752, -2030, -2587, 2344, 10114,
13920, 10114, 2344, -2587, -2030, 752, 1575, 104, -1062, -497, 577, 600, -188,
-524, -71, 362, 198, -187, -219, 49, 176, 34, -109, -66, 49, 63, -9, -45, -12, 27,
20, -14
```

**Fixed-point arithmetic (verified):** products summed in a wide accumulator,
then `y = saturate16( (acc + 2^14) >> 15 )` — round half toward +∞, then saturate.
Software model: `scripts/sw_fir.py`.

## 5. How the coefficients were recovered (exactly)
The netlist is simulated through `scripts/tb_capture.v`, which reproduces the
exact RP2040 I2S waveform (derived from the PIO program in `audio_bridge.py`),
oversampled against a 10 MHz `ICE_CLK`. `scripts/decode.py` parses the capture
and **self-calibrates using the echo channel**: output-right must equal the input
delayed by the (unknown) latency; the unique alignment that makes this hold for
every frame (found: MSB-first, latency 2) also fixes the filtered-channel decode.

An impulse of value **−32768 (0x8000) = exactly −1.0 in Q1.15** makes the single
active product `h[k]·(−1)` exact (no rounding), so the output-left sequence is
**−h[n]** directly. Impulses at +32767, ±16384, +8192 reproduce `h[n]` scaled and
confirm linearity and the rounding mode. Input decode matched the stimulus
2149/2149 and the echo matched 2147/2147.

## 6. Reconstructed baseline RTL [VERIFIED]
`recovered/rtl/fir_audio_top.v` — a clean I2S-target + 63-tap serial-MAC FIR.
Through the same testbench it reproduces the filtered output **bit-for-bit**:
netlist 2048/2048 and reconstruction 1024/1024 real samples match the software
model (`analysis/reconstruction-verification.md`). Same 2-frame latency and
left=filtered/right=echo framing, so the host tool drives it unmodified.
`yosys synth_ice40` maps it cleanly (~2180 LUT4, ~1179 FF, 73 carry, 0 DSP,
0 BRAM) — fits the UP5K with large headroom for later phases.

## 7. Independent cross-verification
Primary recovery is empirical (gate-level simulation) and already multiply-checked
within itself: the **echo channel** (2147/2147), **five impulse amplitudes**
agreeing, exact **linear-phase symmetry**, **Σh = 1.0**, and a **bit-exact
real-audio** match of the netlist to the software model (2048/2048) — the same
check the challenge uses (`sw_filter == hw_filter`).

In addition, three independent agents re-checked the major conclusions with
**different methods, adversarially** (each instructed to try to refute). All
agreed with the published results; none could refute them.

- **Coefficient re-derivation (independent sim + decoder).** A fresh stimulus and
  a separately-written decoder recovered the **63 taps bit-for-bit identical** to
  `coeffs.json` (Σ = 32768, symmetric). Cross-validated on a second 412-frame
  random + crafted stimulus (including saturating probes): a convolution model
  with the recovered taps and the round/saturate rule matched the hardware on all
  412 frames, 0 mismatches. Scanned the full output tail — exactly 63 contiguous
  nonzero taps, no hidden/extra taps.
- **DSP non-use + BRAM count (CBIT decode + routing).** Decoding every MAC16
  functional config bit on all 8 DSP blocks found **all functional CBITs = 0**
  (the set bits are position-dependent Cascade/ColBuf/LC defaults, identical
  between the two columns); routing analysis found **0 DSP operand/output
  segments on any net**. Independently confirmed **exactly one physical RAM**
  (PowerUp set on block (6,23)); the `icebox_stat` "BRAMs: 2" is an
  **x,y-normalization artifact** that maps the single block's `ramb`(y=23) and
  `ramt`(y=24) tiles to two location keys — their ports combine into one 64×16
  RAM40. Re-confirmed 299 DFFs / 1260 LUTs / 124 CARRYs / 9 IOBs / 0 PLLs.
- **Frequency + real-audio (independent FFT + new segments + full-scale).** DC
  gain 0.000 dB, **−3 dB = 3296.3 Hz**, linear phase (group delay 31.000 samples,
  residual imaginary part ~1.4e-10), worst-case stopband **−55.9 dB** above 4 kHz
  (−59.7 dB at exactly 4 kHz). Netlist vs software model matched **2816/2816**
  samples across two new audio offsets (120000 and the loudest region) **plus a
  full-scale square wave that drove the output to both rails** — independently
  confirming the round-half-toward-+∞ and int16-saturation rule.

A fourth agent (independent gate-level *structural* reconstruction of the MAC
form) was still running when Phase 2 was finalized and did not return; its target
(direct-vs-transposed serial-MAC form) is the internal micro-architecture already
listed as open (§9.2) and affects no major conclusion.

## 8. Verified facts (summary)
1. iCE40-UP5K sg48; single `ICE_CLK` domain; no PLL; 9 IOBs; I/O map in §2.
2. No DSP blocks used; one BRAM used as a ≤64×16 zero-init sample delay line; MAC
   in LUT/carry fabric.
3. Philips I2S, 16-bit MSB-first; left=filtered, right=echo; 2-frame latency.
4. 63-tap Type-I linear-phase low-pass FIR, Q1.15; Σh = 1.0; −3 dB ≈ 3.3 kHz;
   stopband ≈ 56 dB above 4 kHz; group delay 31 samples. Exact coefficients in
   `recovered/coeffs.json`.
5. Arithmetic: round half toward +∞, then saturate to int16.
6. A reconstruction reproduces the filtered output bit-for-bit and synthesizes for
   the UP5K.

## 9. Open questions / unresolved
1. Individual LED vs R/G/B pin roles (38/39/40/41) are not separated (not needed
   for the audio data path).
2. The *original's* internal micro-architecture (direct vs transposed form, the
   BRAM circular-buffer addressing, accumulator width) is not reduced to a
   gate-level structural description; its behavior is fully captured by the
   impulse response and the bit-exact software model, and the reconstruction is a
   behavioral equivalent. (The independent structural-RE agent for this was still
   running at finalize and did not return.)
3. **Resolved:** the "BRAMs: 2" print is an `icebox_stat` x,y-normalization
   artifact (one physical RAM; §3, §7), not a second memory.
4. **Resolved:** the round-half-toward-+∞ + int16-saturation rule is confirmed to
   both rails by an independent full-scale test (§7), not just modeled.
5. No hardware was used this phase; all results are from the bitstream + the
   recovered netlist in simulation. On-board confirmation is a later step.

## 10. Deliverables (this branch)
- Recovered: `recovered/fir_audio_top.asc`, `recovered/netlist/*.v`,
  `recovered/coeffs.json`, `recovered/rtl/fir_audio_top.v`, `recovered/README.md`.
- Scripts: `scripts/` (sim harness `tb_capture.v`/`gen_stim.py`/`decode.py`,
  `analyze_filter.py`, `sw_fir.py`, WAV co-sim, `recon_chip_wrap.v`).
- Analysis: `analysis/` (resource inventory, frequency response, reconstruction
  verification, synth log).
- Handoffs: `handoffs/phase-02/` (Codex interface v1+v2, reference vectors).
