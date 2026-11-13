# Recovered artifacts — provenance & reproduction

Phase 2 reverse-engineering of the Challenge 3 bitstream. All artifacts here are
derived deterministically from the provided bitstream with the OSS CAD Suite.

## Source

- **Bitstream:** `fir_audio_top.bin`
  - sha256 `2547d7a23812609cc7fc96bc0234b62bb43458bdfdb49aa03480074bd9c365ee`
  - from the official challenge repo `finals/challenge_3/fpga/fir_audio_top.bin`
    (JBlocklove/CSAW-AI-Hardware-Attack-Challenge-2026, commit `dcb0cec`).
  - A local copy is kept at `bitstream/fir_audio_top.bin` (git-ignored — it is the
    challenge's binary; recover it from the challenge repo or any board readback).
- Toolchain: OSS CAD Suite `20260913` at `C:/Users/lowbr/oss-cad-suite`
  (`iceunpack`, `icebox_stat`, `icebox_vlog`, `iverilog` 14.0, `vvp`, `icetime`).

## Files

| File | How produced |
|---|---|
| `fir_audio_top.asc` | `iceunpack bitstream/fir_audio_top.bin recovered/fir_audio_top.asc` |
| `netlist/fir_audio_top_icebox.v` | `icebox_vlog recovered/fir_audio_top.asc > …` (raw) |
| `netlist/fir_audio_top_sim.v` | the above + 2 cosmetic edits for `iverilog -g2012` (see below) |
| `netlist/icebox_vlog.err` | stderr from icebox_vlog (empty = clean) |
| `coeffs.json` | FIR taps (Q1.15) recovered by simulation — `scripts/decode.py` |

### The two cosmetic edits in `fir_audio_top_sim.v`

icebox_vlog declares the registered output `io_16_31_1` (SD_OUT) as an ANSI
output **and** a separate `reg`, which `iverilog -g2012` rejects. The sim copy:
1. `output io_16_31_1,` → `output reg io_16_31_1,`
2. `reg io_16_31_1 = 0;` → `initial io_16_31_1 = 1'b0;` (preserves power-on 0)

No logic changes. Regenerate with:
```
sed -e 's/output io_16_31_1,/output reg io_16_31_1,/' \
    -e "s/^reg io_16_31_1 = 0;/initial io_16_31_1 = 1'b0;/" \
    netlist/fir_audio_top_icebox.v > netlist/fir_audio_top_sim.v
```

## Reproduce the coefficient recovery

```
export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite/
export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"   # lib on PATH: vvp DLLs
iverilog -g2012 -s tb -o sim.vvp ../scripts/tb_capture.v \
    netlist/fir_audio_top_sim.v $YOSYSHQ_ROOT/share/yosys/ice40/cells_sim.v
python ../scripts/gen_stim.py
vvp sim.vvp +nframes=2149
python ../scripts/decode.py            # -> coeffs.json
python ../scripts/analyze_filter.py coeffs.json 16000
```

The recovery is self-validating: the decoder calibrates alignment against the
I2S **echo channel** (output-right == input delayed by 2 frames, matched
2147/2147), and recovers identical coefficients from 5 independent impulse
amplitudes. The amplitude **−32768 = −1.0** in Q1.15 yields the taps exactly
(output = −h[n], no rounding).
