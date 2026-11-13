# Phase 2 → Codex Interface Handoff (v2, final)

**From:** Claude (Phase 2) · branch `challenge3/02-reverse-engineering`
**Supersedes:** v1 (`codex-interface-handoff.v1.md`). v1's port map, clocking,
I2S frame format, filter spec, resource facts, and reproduction steps remain
valid — read it for those. This v2 adds the reconstruction result, reference
test vectors, and resolves several v1 open items.

## What changed since v1

### Reconstructed baseline RTL is available and verified [VERIFIED]
`recovered/rtl/fir_audio_top.v` — a clean, synthesizable I2S-target + 63-tap
serial-MAC FIR. Build it against a Hackster PCF with your Phase 4 flow.
- Module/ports are the recommended interface from v1 §1
  (`ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN, I2S_SD_OUT, ICE_LED, RGB_R/G/B`).
- **Filtered output is bit-identical** to the original bitstream (netlist
  2048/2048 and reconstruction 1024/1024 samples match the software model on
  real noisy audio).
- **Latency is exactly 2 frames** and framing is left=filtered / right=echo, so
  the challenge host tool `stream_audio.py` (hardcodes `LATENCY=2`) drives it
  unmodified and its baseline/echo check passes.
- `yosys synth_ice40` maps cleanly: ~2180 LUT4, ~1179 FF, 73 carry, 0 DSP,
  0 BRAM — fits UP5K with headroom. (Full P&R needs the board PCF; that is your
  Phase 4 step.)
- Sim adapter `scripts/recon_chip_wrap.v` lets one testbench
  (`scripts/tb_capture.v`) drive both the gate-level netlist and this RTL.

### Bit-exact software reference model [VERIFIED]
`scripts/sw_fir.py` implements the exact fixed-point arithmetic
(`y = sat16((sum(x*h) + 2^14) >> 15)`, round half toward +∞). Use it as a golden
model for your testbenches — no hardware required. Confirmed equal to the
gate-level netlist on 2048 real samples, bit-for-bit.

### Reference test vectors [VERIFIED]
`handoffs/phase-02/reference_vectors.csv` — the first 256 samples of
`what_a_piece_of_work-noisy.wav` (16 kHz mono) and their exact filtered outputs
(`n, x_in_int16, y_filtered_int16`). On hardware, `y[n]` appears on output-left
in frame `n+2` (and the right channel echoes `x[n]` with the same 2-frame
delay). Stream the WAV through your build and compare against this, mirroring the
challenge's own `sw_filter == hw_filter` baseline check.

## Resolved v1 open items
1. **Latency** — confirmed exactly 2 frames end-to-end (reconstruction verified
   at LAT=2; host tool expects 2).
2. **Rounding** — confirmed round-half-toward-+∞ then saturate (see sw_fir.py).
3. **"BRAMs: 2" vs one connected RAM** — the behavioral simulation (one RAM) is
   bit-exact to real audio, so no second memory participates in the data path;
   treat the stat count as a tile artifact.

## Still open (do not treat as settled)
- Individual LED vs R/G/B pin roles (pins 38/39/40/41) — not separated; not
  needed for the audio data path.
- Exact internal micro-architecture of the *original* MAC (direct vs transposed,
  BRAM circular-buffer addressing, accumulator width, saturation threshold at the
  rail). The behavior is fully captured by the impulse response + sw model; the
  reconstruction is a behavioral equivalent, not a gate match.
- Full place-and-route / timing closure at the board clock — Phase 4.

## Quick start for your sim/synthesis infra
```
export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite/
export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"   # lib on PATH (vvp DLLs)
# behavioral sim of the reconstruction through the I2S testbench:
iverilog -g2012 -s tb -o recon.vvp scripts/tb_capture.v \
    recovered/rtl/fir_audio_top.v scripts/recon_chip_wrap.v
python scripts/gen_wav_stim.py <noisy.wav> 1024 && vvp recon.vvp +nframes=1160
python scripts/wav_cosim.py          # compares to sw_fir.py (expect all-match)
# synthesis check:
yosys -p "read_verilog -sv recovered/rtl/fir_audio_top.v; synth_ice40 -top fir_audio_top; stat"
```
