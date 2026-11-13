# Reconstructed RTL — equivalence evidence

`recovered/rtl/fir_audio_top.v` is a clean, synthesizable reconstruction of the
bitstream's behavior (I2S target + 63-tap serial-MAC FIR). It is an
**evidence-supported equivalent**, not a gate-level copy.

## Equivalence (bit-exact filtered output)

Verified by co-simulation through the identical I2S testbench (`tb_capture.v`)
used on the gate-level netlist, with the echo channel as an exact alignment
oracle (see `scripts/recon_chip_wrap.v` for the sim-only port adapter).

| Design under test | Echo match | Filtered output vs software model |
|---|---|---|
| Gate-level netlist (`fir_audio_top_sim.v`) | 2182/2182 @ LAT=2 | **2048/2048 bit-exact** |
| Reconstructed RTL (`rtl/fir_audio_top.v`)  | 1158/1158 @ LAT=2 | **1024/1024 bit-exact** |

Both equal the bit-exact software reference (`scripts/sw_fir.py`) on real noisy
audio (`what_a_piece_of_work-noisy.wav`). By transitivity the reconstruction's
filtered output is bit-identical to the original bitstream's, at the same
**2-frame latency** and with the same left=filtered / right=echo framing — so the
challenge host tool `stream_audio.py` (which hardcodes `LATENCY=2`) drives it
unmodified and its baseline check passes.

## Synthesizability (iCE40-UP5K)

`yosys synth_ice40` maps cleanly (no errors, no inferred latches). Resource use
(`analysis/recon_synth.log`):

| Cell | Count | UP5K budget |
|---|---|---|
| SB_LUT4 | 2180 | 5280 (~41%) |
| DFFs (all SB_DFF*) | ~1179 | 5280 (~22%) |
| SB_CARRY | 73 | — |
| SB_MAC16 (DSP) | 0 | 8 |
| SB_RAM40_4K | 0 | 30 |

Fits with large headroom for later phases. Notes on fidelity vs the original:
- The original realizes the sample history in **one BRAM** (≤64×16) and a tighter
  fabric MAC (orig: 1260 LUTs / 299 FFs / 1 BRAM). This reconstruction uses a
  register delay line (hence more FFs, no BRAM) and a straightforward fabric
  multiplier (hence more LUTs). A BRAM-backed circular buffer would reproduce the
  original's footprint more closely; it is an optimization, not required for a
  correct baseline.
- Full place-and-route needs a Hackster PCF (pin constraints). Mapping success +
  cell counts well under device limits establish synthesizability; the final
  P&R/bitstream build is Phase 4 (Codex) infrastructure.
