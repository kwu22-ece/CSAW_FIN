# Resource & structure inventory (from the bitstream)

`icebox_stat recovered/fir_audio_top.asc` (saved in `icebox_stat.txt`):

| Resource | Used |
|---|---|
| DFFs | 299 |
| LUTs | 1260 |
| CARRYs | 124 |
| BRAMs | 2 (see note) |
| IOBs | 9 |
| PLLs | 0 |
| GLBs | 6 (global networks) |

## Interpretation

- **Single clock domain.** All 299 FFs and the BRAM are clocked by `ICE_CLK`
  (`io_13_31_0`). No PLL.
- **Fabric MAC, no DSP.** The iCE40-UP5K has 8 hard SB_MAC16 DSP blocks (DSP
  columns x=0 and x=25). **None are used by this design:**
  - x=25 has **zero** routed net-segments; x=0 has only global-clock spine and
    neighbor-op bleed segments — **no functional DSP I/O routing**.
  - DSP tile config bits are present but are nextpnr **defaults**: only 3 distinct
    patterns, **mirror-symmetric** between the two columns (A,B,A,C in both), i.e.
    position-dependent, not function-dependent.
  So the 63-tap multiply-accumulate is realized in the **LUT + carry** fabric
  (1260 LUTs, 124 carry cells), consistent with constant-coefficient arithmetic.
- **Sample delay line in BRAM.** One connected `SB_RAM40_4K` (`ram40_6_23`),
  16-bit words, 6 address bits (≤64 entries), **zero-initialized**. A zero-init
  RAM is a read/write sample buffer, **not** a coefficient ROM — consistent with
  the coefficients living in the fabric, not memory.
  - Note: `icebox_stat` reports **BRAMs: 2**, but `icebox_vlog` emits exactly
    **one** connected RAM and the echo-validated simulation is functionally
    complete with it. The "2" is treated as a tile-counting artifact (ramb+ramt /
    a configured-but-unconnected tile). Tracked as an open item; the simulation
    reproduces the hardware exactly, so no second memory participates in the
    data path.

## IO map (verified; see the Codex handoff for the full table)

9 IOBs, all on the top edge (y=31): ICE_CLK(37), BCLK(36), WS(34), SD_IN(32),
SD_OUT(31), and LED/RGB on 38/39/40/41. BCLK/WS/SD_IN/SD_OUT cross-validated
against `audio_bridge.py` GPIO comments.
