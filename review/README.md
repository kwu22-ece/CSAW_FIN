# Subphase R — Independent Reconstruction Review (working directory)

Independent technical review of the Phase 2 FPGA reverse-engineering result.
Read-only review of committed snapshots; **no Phase 2/3/4 files are modified**.
All artifacts here are additive, on branch `challenge3/reconstruction-review`.

- **Reviewed source commits:** Phase 2 `1befb30`, Phase 4 `2da1d72`.
- **Findings:** `defect-register.md` (prioritized), `quality-report.md` (measurable).
- **Handoffs:** `../handoffs/reconstruction-review/`.
- **Experiment logs:** `logs/`. **Scripts (independent of `scripts/`):** `scripts/`.

## Reproduce (OSS CAD Suite + Python; Git Bash on Windows)

```bash
export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite
export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"   # lib on PATH => vvp DLLs
CELLS="$YOSYSHQ_ROOT/share/yosys/ice40/cells_sim.v"
WT=<this worktree root>

# 1. Provenance: regenerate the .asc from the .bin and diff
iceunpack bitstream/fir_audio_top.bin /tmp/my.asc && diff /tmp/my.asc recovered/fir_audio_top.asc

# 2. Filter math (integer invariants + independent DTFT)
python review/scripts/rv_filter_math.py recovered/coeffs.json recovered/rtl/fir_audio_top.v 16000

# 3. Bitstream structure (DSP non-use, one zero-init RAM); + authoritative icebox_vlog
python review/scripts/rv_bitstream_struct.py recovered/fir_audio_top.asc
icebox_vlog recovered/fir_audio_top.asc | grep -c SB_MAC16   # => 0

# build the gate-level netlist sim once, then run each stimulus through it:
iverilog -g2012 -s tb -o /tmp/nl.vvp scripts/tb_capture.v recovered/netlist/fir_audio_top_sim.v "$CELLS"

# 4. Adversarial arithmetic (rounding-mode discrimination + saturation/accumulator)
(cd /tmp && python $WT/review/scripts/rv_adversarial_arith.py gen $WT/recovered/coeffs.json \
   && vvp nl.vvp +nframes=1783 && python $WT/review/scripts/rv_adversarial_arith.py check $WT/recovered/coeffs.json)

# 5. Real-audio bit-exact (netlist vs independent model vs sw_fir.py)
(cd /tmp && python $WT/review/scripts/rv_realaudio.py gen $WT/what_a_piece_of_work-noisy.wav 2048 $WT/recovered/coeffs.json \
   && vvp nl.vvp +nframes=2052 && python $WT/review/scripts/rv_realaudio.py check $WT/recovered/coeffs.json $WT/scripts/sw_fir.py)

# 6. Phase 4 golden-format fix (self-validates against Phase 4 results.read_samples)
python review/scripts/rv_make_phase4_golden.py what_a_piece_of_work-noisy.wav 256 recovered/coeffs.json handoffs/reconstruction-review/phase4-golden
```

## Coordination
- Independent reviewer; does not merge into the engineering branch or force-push.
- Proposed changes/patches go in `../handoffs/reconstruction-review/` for the
  responsible agent (Phase 3) to inspect and integrate.
- Phase 3 (`challenge3/03-baseline`) was active at review time with no new commits
  beyond `1befb30`; its uncommitted work-in-progress was not read.
