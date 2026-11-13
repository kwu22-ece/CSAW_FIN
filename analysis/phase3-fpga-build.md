# Phase 3 — FPGA build validation (reconstructed RTL + Phase 3 PCF)

Independent place-and-route of the reconstructed baseline RTL
(`recovered/rtl/fir_audio_top.v`) with the Phase 3 pin constraints
(`handoffs/phase-03/fir_audio_top_hackster.pcf`), proving the recovered design
maps onto the real target device and closes timing at the board clock.

**Toolchain:** OSS CAD Suite at `C:/Users/lowbr/oss-cad-suite`
(`yosys` 0.69+24, `nextpnr-ice40` 0.11.x, `icetime`, `icepack`).
**Device:** iCE40-UP5K, package SG48 (Hackster board). **Constraint:** 10 MHz.

Reproduce:
```
cd build/fpga
yosys -q -p "read_verilog -sv ../../recovered/rtl/fir_audio_top.v; \
             synth_ice40 -top fir_audio_top -json fir.json"
nextpnr-ice40 --up5k --package sg48 --json fir.json \
    --pcf ../../handoffs/phase-03/fir_audio_top_hackster.pcf \
    --asc fir.asc --freq 10
icetime -d up5k -t fir.asc
icepack fir.asc fir_recon.bin
```

## Results [VERIFIED]

| Metric | Value |
|---|---|
| ICESTORM_LC | 3283 / 5280 (62%) |
| ICESTORM_RAM (BRAM) | 0 / 30 |
| ICESTORM_DSP | 0 / 8 |
| SB_IO | 9 / 39 |
| nextpnr Fmax | 14.49 MHz (**PASS** at 10.00 MHz) |
| icetime (independent) | 70.39 ns critical path = 14.21 MHz (**PASS** at 10 MHz) |
| Critical path | 32 logic levels through the 40-bit FIR accumulator |
| PCF pins | all 9 (`ICE_CLK, I2S_BCLK, I2S_WS, I2S_SD_IN, I2S_SD_OUT, ICE_LED, RGB_R/G/B`) valid for SG48 and routed |

- The PCF's five audio data-path pins (31/32/34/36/37) are the Phase 2 verified
  map; the four LED/RGB pins (38–41) are the known set, roles unseparated.
- **Logic-cell count (3283 LC) is higher than the original.** The reconstruction
  uses a register-based delay line and a serial MAC for clarity; the original
  stores its sample delay line in **one BRAM** (0 BRAM here). Both fit the UP5K
  with large headroom. This is an implementation choice, permitted by the
  challenge — it does **not** change the filtered output (bit-exact; see
  `analysis/phase3-verification.md`).
- `icepack` produces a 104090-byte reconstruction bitstream. Its SHA-256 is
  **not** equal to the original `fir_audio_top.bin` and is **not expected to be**:
  this is a behavioral reconstruction, not a gate-level copy. Bitstream-level
  identity is explicitly **not claimed**; filtered-audio identity **is**
  (demonstrated bit-for-bit).
- No hardware was programmed this phase; these are simulation/P&R sign-off
  numbers. On-board confirmation remains a later step.
