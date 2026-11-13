# Rejected revisions and corrections

| Revision | Observed result | Correction and status |
|---|---|---|
| Initial staging path | Frozen Phase 4 commit did not contain the Phase 3 recovered RTL and coefficients. | Imported the golden-reference inputs from the Phase 3 handoff commit. Baseline and golden files are preserved byte-for-byte. |
| Initial CSV indexing | Validation run 1 blocked all ten simulations before RTL execution because left/right rows reused frame indices. | Changed generated input and expected CSVs to the generic runner's sequential word-index contract. The original Phase 3 golden CSV remains unchanged; a normalized copy is used by simulation. |
| Reset-gating adapter | Validation run 2 produced zero captures because the Phase 3 wrapper gated the core's I2S pins during generic-runner startup. | Replaced it with the Phase 4 direct-wire adapter. The RTL remains reset-less and uses its original iCE40 power-up initialization. |
| Framework-root adapter path | Validation run 3 blocked all ten simulations because manifest sources resolve relative to the candidate package. | Copied the validated direct-wire adapter to rtl/phase4_dut.sv and changed the manifest to the package-local path. |
| Generic 32-BCLK slots | Validation run 4 executed with 32 BCLK periods per channel, causing zero-valued captures and 506/512 Phase 3 golden word mismatches. | Set SLOT_BITS=16 with Philips one-bit MSB delay to match the successful Phase 4 recovered-design configuration. Validation runs 5 and 6 both passed all ten simulations and the FPGA build. |
| Reproducibility path comparison | The first audit compared absolute expected-file paths, which differ between run directories even when file contents match. | Compare each case's hashed input contents rather than run-specific output paths. The run 5/6 audit confirms identical input contents and bitstreams. |
| Full-audio Scribe timeout | The first Scribe `record-test` full-recording run reached its 300-second default timeout after three of four chunks and recorded `exit_code: null`; no complete report was produced. | Reran the same simulation with `--timeout 900` and a fresh output directory. All four chunks completed, the Scribe event recorded exit 0, and the capture audit passed. |

These were harness and configuration corrections. No RTL correction was needed after the first passing simulation run.
