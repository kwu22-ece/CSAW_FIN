# Phase 3 status — original-filter golden reference (baseline)

Branch: `challenge3/03-baseline` (based on Phase 2 `1befb30`).
Worktree: `C:/Users/lowbr/Documents/College/AI/CSAW_FIN/.worktrees/phase-03`.
Owner: Claude. Scope: mathematical reference, baseline datasets, FIR
reconstruction validation, numerical comparison — **no Trojan, no bitstream
modification** (that is a later phase). Work stops at the end of Phase 3.

## Done and verified
- Independent golden software model (`baseline/ref_fir.py`), cross-checked
  bit-for-bit against the Phase 2 model on all vector families + 12000 random
  samples.
- FIR coefficients independently re-recovered from the gate-level netlist
  (identical to `recovered/coeffs.json`): 63-tap, Q1.15, symmetric, Σ=32768.
- Bit-accurate fixed-point confirmed: round half toward +∞ then int16 saturate;
  exercised to both rails; `−1.0` impulse identity (`out = −h[n]`).
- 2-frame latency re-confirmed (echo-channel oracle, 100% match) on every vector
  and on real audio.
- Frequency response (independent scipy method): DC 0.000 dB, −3 dB 3296.4 Hz,
  stopband −55.9 dB above 4 kHz, group delay 31.000 samples, linear phase.
- HDL validation: gate-level netlist ≡ reconstructed RTL ≡ golden model,
  **bit-for-bit, 0 mismatches**, across impulse/step/sine/chirp/random/boundary
  (9904 sample-comparisons) and real audio.
- FPGA sign-off: reconstructed RTL + Phase 3 PCF place-and-route on UP5K/SG48,
  Fmax ≈ 14.5 MHz, PASS at 10 MHz.

## Delivered to Phase 4 (this directory)
- `phase4_dut.v` — port adapter matching the Phase 4 contract.
- `fir_audio_top_hackster.pcf` — verified SG48 pin constraints.
- `run_reference.py` — reference-model entry point (argv contract).
- `reference_io.in.csv` / `reference_io.csv` — canonical input + golden output
  (`index,channel,value`).
- `INTERFACE.md` — full interface/clock/reset/latency/format spec; closes every
  item on the Phase 4 `awaiting[]` list.

## Limitations
- No hardware programmed this phase; all results are simulation / P&R.
- Bitstream-level identity to the original is **not** claimed (behavioral
  reconstruction; the original uses a BRAM delay line, the reconstruction a
  register delay line). Filtered-audio identity **is** demonstrated.
- LED/RGB individual pin roles (38–41) unresolved; not on the audio data path.

## Reproduce everything
```
export YOSYSHQ_ROOT=/c/Users/lowbr/oss-cad-suite
export PATH="$YOSYSHQ_ROOT/bin:$YOSYSHQ_ROOT/lib:$PATH"
python baseline/regression.py          # software + HDL, one command
```
Reports land in `build/reports/` (git-ignored, regenerable).
