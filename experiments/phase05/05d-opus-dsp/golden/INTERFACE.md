# Phase 3 → Phase 4 (Codex) interface handoff

**From:** Claude (Phase 3) · branch `challenge3/03-baseline`
**Consumes:** `handoffs/phase-04/STATUS.md` (adapter contract, "Pending from
Claude Phase 2/3", `awaiting[]` in `validation.json`).
**Supplies:** everything on that pending list — verified RTL + port adapter,
verified interface/clocks/reset/latency, verified filter vectors + reference
model, and the verified board package + PCF. All claims here are backed by
reproducible artifacts in this branch and cross-checked against the gate-level
netlist unpacked from the original bitstream.

This supersedes nothing in `handoffs/phase-02/` — it adds the Phase 4-shaped
interface. Read `handoffs/phase-02/codex-interface-handoff.v2.md` for the
narrative recovery; this file is the integration contract.

---

## 1. RTL + port adapter  [closes "verified RTL and port adapter"]

- **Core (board top):** `recovered/rtl/fir_audio_top.v`, module `fir_audio_top`.
  Clean, synthesizable; filtered output is bit-identical to the original
  bitstream (demonstrated, §4). Ports:
  `ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN, I2S_SD_OUT, ICE_LED, RGB_R, RGB_G, RGB_B`.
- **Phase 4 adapter:** `handoffs/phase-03/phase4_dut.v`, module `phase4_dut`,
  matching your contract exactly:
  `module phase4_dut(input clk, rst, bclk, lrclk, sd_in, output sd_out)`.
  Compile it **together with** `recovered/rtl/fir_audio_top.v`.
  Mapping: `clk→ICE_CLK, bclk→I2S_BCLK, lrclk→I2S_WS, sd_in→I2S_SD_IN,
  sd_out→I2S_SD_OUT`.

## 2. Interface / clocks / reset / latency  [closes "verified interface…"]

- **Port directions:** `clk,bclk,lrclk,sd_in` inputs; `sd_out` output
  (registered). Verified against the icebox SG48 pinloc DB + bridge GPIO
  comments (Phase 2 §2).
- **Clock:** single free-running `ICE_CLK` (~10 MHz); no PLL. `bclk`/`lrclk` are
  **oversampled data**, edge-detected against `ICE_CLK` — not clock domains.
  Your controller owning BCLK/LRCLK and changing SD on falling edges, monitor
  sampling on rising edges, is exactly what the design expects.
- **I2S format:** Philips, **16-bit, MSB-first**, 32 BCLK/frame, left then
  right; WS changes one bit early. **bit_offset = 0.** Left slot carries the
  sample to filter; right slot = echo.
  Channel polarity: **left = filtered, right = echo** (`channel 0`/`1` in the
  reference CSV).
- **Reset:** the recovered design is **reset-less** (power-up state only: all
  iCE40 FFs + the sample BRAM power up to 0). `phase4_dut` accepts active-high
  `rst` for boundary compatibility and uses it as *hold-in-idle* (power-up
  alignment): **assert `rst` while the I2S lines are idle, deassert before the
  first frame.** `sd_out` is 0 during reset and at power-up. The core is not
  re-initialized mid-stream (the original has no such capability).
- **Latency:** end-to-end = **exactly 2 frames** (verified: echo channel matched
  100% at LAT=2 on every vector family and on real audio; the host tool
  `stream_audio.py` hardcodes `LATENCY=2`). Output frame *m* carries
  `left=filtered(x[m-2])`, `right=echo(x[m-2])`; frames *m<2* are 0.

## 3. Reference model + vectors  [closes "verified filter vectors and model"]

- **Reference-model entry point** (your `reference_command` argv contract;
  substitutes `{python} {input} {output}`, no shell):
  ```
  {python} handoffs/phase-03/run_reference.py {input} {output}
  ```
  Self-contained (no project imports); loads `recovered/coeffs.json`
  automatically. Options: `--latency N` (default 2), `--aligned` (emit logical
  `y[n]`/`x[n]` with no frame shift), `--coeffs PATH`.
- **Input format** (auto-detected): `index,value` (mono int16, the sample to
  filter) **or** `index,channel,value` (channel 0 / left is taken as the input).
- **Reference CSV output format:** exactly your spec — `index,channel,value`,
  contiguous zero-based word index, channel `0`=left=filtered / `1`=right=echo,
  signed decimal int16. By default the 2-frame framing is already applied, so it
  equals a raw capture of `sd_out`. If your monitor removes latency itself, call
  with `--aligned` and set your latency to 0, or keep default and set latency 2.
- **Canonical dataset (committed):**
  - `handoffs/phase-03/reference_io.in.csv` — 256 real input frames
    (`what_a_piece_of_work-noisy.wav`, 16 kHz mono).
  - `handoffs/phase-03/reference_io.csv` — the golden framed output for it.
  - Verified: `run_reference.py` regenerates `reference_io.csv` from
    `reference_io.in.csv` byte-identically, and the gate-level netlist reproduces
    it bit-for-bit (`build/reports/wav-cosim.json`).
- **Regenerate any vector family** (impulse/step/sine/chirp/random/boundary):
  `python baseline/gen_testvectors.py` → `build/vectors/<name>.csv` (`index,value`),
  then pipe through `run_reference.py`.
- **Coefficients / arithmetic:** 63-tap Q1.15, symmetric, Σ=32768; per sample
  `acc=Σ h[k]·x[n−k]`, `y=sat16((acc+2^14)>>15)` (round half toward +∞, then
  int16 saturate). Accumulator ≥ 40-bit signed is sufficient and non-saturating
  until the final shift.

## 4. Board package + PCF  [closes "verified board package and PCF"]

- **Device:** iCE40-UP5K, package **SG48** (Hackster board).
- **Constraints:** `handoffs/phase-03/fir_audio_top_hackster.pcf` (top =
  `fir_audio_top`). Data-path pins verified:
  `ICE_CLK=37, I2S_BCLK=36, I2S_WS=34, I2S_SD_IN=32, I2S_SD_OUT=31`.
  LED/RGB pins `38–41` are the known set (roles unseparated; not on the audio
  path — any assignment within the set is harmless).
- **Build proven** (see `analysis/phase3-fpga-build.md`):
  `yosys synth_ice40` → `nextpnr-ice40 --up5k --package sg48` → `icetime`:
  3283/5280 LC, 0 DSP, 0 BRAM, 9 IO; **Fmax 14.49 MHz (nextpnr) / 14.21 MHz
  (icetime), PASS at 10 MHz**. All PCF pins valid and routed.

## 5. Evidence of bit-exactness (this phase)

`build/reports/` (regenerate with `python baseline/regression.py`):
- `model-crosscheck.json` — two independent software models agree on all vector
  families + 12000 random samples; −1.0 impulse identity; both saturation rails;
  round-half-toward-+∞.
- `hdl-battery.json` — netlist vs recon vs model: **0 mismatches** over 6
  families (9904 sample-comparisons), latency=2 and echo exact everywhere.
- `wav-cosim.json` — real audio, both engines bit-exact, canonical dataset.
- `freq-metrics.json` — DC 0.000 dB, −3 dB = 3296.4 Hz, stopband −55.9 dB >4 kHz,
  group delay 31.000 samples, linear-phase residual ~8e-15.

## 6. Still open (do not treat as settled)

- Individual LED-vs-R/G/B pin role among 38–41 (not on the audio path).
- The *original's* internal micro-architecture (direct vs transposed form, BRAM
  circular-buffer addressing, exact accumulator width/rail threshold). Behavior
  is fully captured by the impulse response + bit-exact model; the reconstruction
  is a behavioral equivalent, not a gate match — **bitstream-level identity is
  not claimed**.
- **No hardware was programmed this phase.** All results are simulation / P&R.
  On-board `sw_filter == hw_filter` confirmation is the remaining step and is
  what Phase 4's recovered-design template should execute once wired to this
  adapter + reference model.

## 7. Request to Codex

- Point the recovered-design template at `phase4_dut` (+ `fir_audio_top.v`) and
  `run_reference.py`; it should move from BLOCKED (exit 2) to a real pass.
- If your monitor needs a different latency convention than framed-LAT=2, use the
  `run_reference.py` flags in §3 rather than editing the model.
- If you need additional vector families or a longer real-audio slice, say so in
  `handoffs/phase-03/` (I own the models/vectors); I will not edit Codex-owned
  framework files.
