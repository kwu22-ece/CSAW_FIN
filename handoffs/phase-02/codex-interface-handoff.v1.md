# Phase 2 → Codex Interface Handoff (v1)

**From:** Claude (Phase 2, reverse-engineering) · branch `challenge3/02-reverse-engineering`
**To:** Codex (Phase 4, simulation & synthesis infrastructure)
**Date:** 2026-11-12
**Status of this doc:** EARLY interface handoff. Facts marked **[VERIFIED]** are
established by reproducible evidence (see `recovered/` + `scripts/`). Facts marked
**[PROVISIONAL]** are current best understanding and may change. Consume this file
read-only; do not edit Phase 2 analysis files. A v2 will add reference WAV test
vectors and the reconstructed-RTL equivalence result.

Source bitstream: `fpga/fir_audio_top.bin`
(sha256 `2547d7a23812609cc7fc96bc0234b62bb43458bdfdb49aa03480074bd9c365ee`),
unpacked with `iceunpack` to `recovered/fir_audio_top.asc`, netlist via
`icebox_vlog` → `recovered/netlist/fir_audio_top_icebox.v`.

---

## 1. Top-level ports [VERIFIED]

Device: **Lattice iCE40-UP5K, package sg48**. The design has **9 IOBs**. Port
names below are the raw netlist names (`io_<x>_<y>_<z>`); the pin numbers come
from the icebox sg48 pinloc DB and are **cross-validated** against the GPIO
comments in the challenge `tools/audio_bridge.py`.

| Netlist port | iCE40 pin | Dir | Signal | Notes |
|---|---|---|---|---|
| `io_13_31_0` | 37 | in  | **ICE_CLK** | free-running ~10 MHz; clocks all 299 FFs + the BRAM |
| `io_9_31_1`  | 36 | in  | **I2S_BCLK** | oversampled (not a clock domain) |
| `io_13_31_1` | 34 | in  | **I2S_WS**   | word select; 0=left, 1=right |
| `io_16_31_0` | 32 | in  | **I2S_SD_IN**| serial audio in (MSB first) |
| `io_16_31_1` | 31 | out | **I2S_SD_OUT**| serial audio out (registered) |
| `io_8_31_1`  | 38 | out | ICE_LED (activity/scope trigger) | **[PROVISIONAL]** which of 38/39/40/41 is LED vs R/G/B not yet individually confirmed |
| `io_4_31_0`  | 39 | out | RGB (one of R/G/B) | **[PROVISIONAL]** |
| `io_5_31_0`  | 40 | out | RGB (one of R/G/B) | **[PROVISIONAL]** |
| `io_6_31_0`  | 41 | out | RGB (one of R/G/B) | **[PROVISIONAL]** |

BCLK=36, WS=34, SD_IN=32, SD_OUT=31 match `audio_bridge.py` exactly
(GPIO6→D0→pin36 BCLK, GPIO7→pin34 WS, GPIO8→pin32 SD_IN, GPIO9→pin31 SD_OUT).

**Recommended reconstructed-module interface** (for a clean RTL rewrite; Codex
can target this for testbenches):
```
module fir_audio_top (
  input  ICE_CLK,            // ~10 MHz free-running
  input  I2S_BCLK,           // oversampled
  input  I2S_WS,
  input  I2S_SD_IN,
  output I2S_SD_OUT,
  output ICE_LED,            // high while computing
  output RGB_R, RGB_G, RGB_B // active-low status
);
```

## 2. Clock & reset assumptions [VERIFIED]

- **Single clock domain.** All 299 flip-flops and the BRAM use `posedge ICE_CLK`.
  There is **no PLL** (icebox_stat: PLLs 0) and no second clock.
- BCLK/WS/SD_IN are **oversampled against ICE_CLK** (each has a single
  synchronizer fanout in the netlist) and edge-detected — they are *inputs*, not
  clocks. Keep `BCLK ≤ 1 MHz` (≥10× oversampling at 10 MHz).
- **Reset:** iCE40 global power-on reset; all FFs power up to 0 (the netlist
  declares every FF `reg … = 0`). No external reset pin. Simulation starts in a
  fully defined (all-zero) state.

## 3. I2S frame format [VERIFIED by simulation: 2147/2147 echo matches]

- Standard **Philips I2S**, **16-bit**, **MSB-first**, two channels (left then
  right), **32 BCLK periods per frame**.
- `WS` changes **one bit early** (Philips): WS is low during left bits L15..L1,
  goes high at L0, stays high for right bits R15..R1, goes low at R0. The exact
  controller waveform is reproduced by `scripts/tb_capture.v` (derived from the
  RP2040 PIO program in `audio_bridge.py`).
- Data/WS change on the **falling** edge of BCLK; sampled on the **rising** edge.
- **Controller→FPGA:** the sample to filter is on the **left** channel; the app
  sends the same value on both channels.
- **FPGA→Controller:** left = **filtered** sample, right = **unmodified echo** of
  the input that produced it.
- Samples are **16-bit signed two's complement, interpreted as Q1.15**. Output is
  rounded and saturated back to 16 bits. Rounding is **round-half-toward-+∞**
  (observed from half-LSB cases) [VERIFIED]. Saturation to ±full-scale
  [PROVISIONAL — not yet exercised to the rail].

## 4. Latency / pipeline [VERIFIED]

- The filtered reply (and the echo) to the sample sent in frame *n* appears in
  frame *n+2* — a **2-frame** I/O latency. (Independent of the filter's internal
  31-sample group delay.)

## 5. Filter specification [VERIFIED — exact]

- **63-tap, Type-I linear-phase (symmetric) FIR low-pass.** Coefficients are
  fixed in the bitstream.
- Coefficients are **Q1.15 signed integers**, recovered exactly (see §7 method)
  in `recovered/coeffs.json`. Center tap h[31]=13920. **Σh = 32768 = exactly 1.0**
  (0 dB DC gain). Symmetry h[i]=h[62−i] holds exactly.
- Frequency response (fs=16 kHz): flat passband to ~3 kHz, **−3 dB ≈ 3.3 kHz**,
  −60 dB by 4 kHz, stopband ≥ ~56 dB above 4 kHz. Group delay 31 samples
  (1.94 ms). Full table in `analysis/` / `scripts/analyze_filter.py`.

Coefficient vector (Q1.15, index 0..62):
```
-14, 20, 27, -12, -45, -9, 63, 49, -66, -109, 34, 176, 49, -219, -187, 198, 362,
-71, -524, -188, 600, 577, -497, -1062, 104, 1575, 752, -2030, -2587, 2344, 10114,
13920, 10114, 2344, -2587, -2030, 752, 1575, 104, -1062, -497, 577, 600, -188,
-524, -71, 362, 198, -187, -219, 49, 176, 34, -109, -66, 49, 63, -9, -45, -12, 27,
20, -14
```

## 6. Resource / implementation facts [VERIFIED]

- icebox_stat: **DFFs 299, LUTs 1260, CARRYs 124, BRAMs used (connected) 1,
  IOBs 9, PLLs 0, GLBs 6**.
- **No DSP/MAC16 blocks are used** [VERIFIED]: DSP columns x=0 and x=25 carry no
  functional routing (x=25 has zero routed net-segments; x=0 has only global-clock
  and neighbor-bleed segments). The multiply-accumulate is implemented in the
  LUT/carry fabric. DSP tile config bits are nextpnr defaults (mirror-symmetric
  across the two columns; only 3 distinct position-dependent patterns).
- **One** connected `SB_RAM40_4K` (`ram40_6_23`), 16-bit words, 6 address bits
  (≤64 entries), **zero-initialized** → it is the **sample delay line**, not a
  coefficient ROM. (icebox_stat prints "BRAMs: 2"; this is a tile-count artifact —
  only one RAM is connected in the netlist and the echo-validated simulation is
  functionally complete with it. Tracked as an open item.)

## 7. Simulator requirements & how to reproduce [VERIFIED working]

Toolchain present at `C:/Users/lowbr/oss-cad-suite` (OSS CAD Suite 20260913):
`iceunpack`, `icebox_stat`, `icebox_vlog`, `iverilog` 14.0, `vvp`, `icetime`.

**Windows DLL note (important):** `vvp.exe` needs **both** `oss-cad-suite/bin`
**and** `oss-cad-suite/lib` on PATH (set `YOSYSHQ_ROOT` too), else it fails with
`libvvp-1.dll: cannot open shared object file`.

Simulate the recovered netlist (gate-level, functionally complete — no DSP gap):
```
export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite/
export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"
iverilog -g2012 -s tb -o sim.vvp scripts/tb_capture.v \
    recovered/netlist/fir_audio_top_sim.v \
    $YOSYSHQ_ROOT/share/yosys/ice40/cells_sim.v
python scripts/gen_stim.py          # writes stim_l.hex, stim_r.hex, stim_plan.json
vvp sim.vvp +nframes=<N>
python scripts/decode.py            # self-calibrates via echo, extracts h[n]
```
- `fir_audio_top_sim.v` = the icebox_vlog netlist with **two cosmetic edits only**
  (`output io_16_31_1` → `output reg`; drop the duplicate `reg` decl, keep POR=0)
  so iverilog `-g2012` accepts it. Semantics unchanged.
- `tb_capture.v` drives the exact I2S waveform and logs per-BCLK-edge bits;
  `decode.py` calibrates alignment against the echo channel (an exact oracle).

## 8. Test vectors for your testbenches

- **Impulse response = coefficients** [VERIFIED]: send one frame with
  value **−32768 (0x8000)** on both channels surrounded by zeros; the output-left
  sequence 2 frames later is **−h[n]** exactly (−32768 = −1.0 in Q1.15, no
  rounding). Amplitudes +32767, ±16384, +8192 reproduce h[n]/scale and confirm
  linearity.
- **Echo self-check**: output-right[n] == input-left[n−2] for every frame.
- **[PROVISIONAL / coming in v2]** A bit-exact reference pair
  (`what_a_piece_of_work-noisy.wav` subset in → filtered out) and a pure-software
  FIR reference model, so your sim can be checked against the real audio path
  without hardware. This mirrors the challenge's own `sw_filter == hw_filter`
  baseline check.

## 9. Open items (do not treat as settled)

1. LED vs R/G/B individual pin assignment (pins 38/39/40/41) — functional role
   not yet separated.
2. Internal MAC micro-architecture (direct vs transposed form; serial vs parallel;
   accumulator width; exact saturation threshold) — behavior is fully captured by
   the impulse response, but the structural form is still being recovered.
3. Saturation behavior at the rail not yet exercised.
4. The icebox_stat "BRAMs: 2" vs one connected RAM discrepancy (see §6).
