# Phase 4 reusable simulation and build infrastructure

This framework validates configurable RTL, compares signed audio samples, captures
waveforms, and runs repeatable iCE40 synthesis/place-and-route. Its bundled loopback
and counter are **infrastructure fixtures only**. They do not implement the recovered
filter, establish bitstream equivalence, or verify hardware pins. The recovered
design template starts blocked; no unavailable design result is replaced by a mock.

## Run

Python 3.11+ is required; there are no pip dependencies. Install the checksum-pinned
[official OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build) with:

```text
python infrastructure/bootstrap.py
```

The lock records the upstream release URL and GitHub asset SHA-256. Installation is
local to `.tools/`; it does not change system PATH or install drivers. The bootstrap
currently pins Windows x64. Other platforms can use an existing suite through
`OSS_CAD_SUITE=/absolute/oss-cad-suite` or `--suite /absolute/oss-cad-suite`.
Do not use unreviewed download hashes. Existing installation directories are refused.

Native Windows (also avoids an inaccessible Windows Store Python alias):

```powershell
infrastructure/run.ps1 doctor --output build/dependencies.json
infrastructure/run.ps1 validate --waves vcd
infrastructure/run.ps1 sim --waves fst
infrastructure/run.ps1 build
infrastructure/run.ps1 regress --manifest infrastructure/configs/recovered.template.json
```

Portable Python entry point:

```text
python infrastructure/run.py --suite /absolute/oss-cad-suite validate --waves vcd
python infrastructure/run.py compare expected.csv actual.csv --sample-bits 16
```

`validate` executes the Python/HDL failure-path tests, all configured simulations,
and the selected FPGA build. `regress` runs configured simulations/build without
the framework tests; `sim` and `build` select a single stage. `--output` must name a
new directory, preventing stale outputs from passing a later run. Default output
names contain UTC time and a random suffix. Wave capture is `none`, `vcd`, or `fst`.
Exit codes: **0 passed, 1 failed, 2 blocked by missing design inputs**.

`doctor` probes versions/help and hashes executables. Its availability result alone
does not prove compilation, simulation, or synthesis; `validate` supplies those
checks. Verilator is discovered as an optional lint tool; execution uses Icarus/vvp.
The native Windows binary is `verilator_bin.exe`. No Verilator simulation backend
is claimed. Icarus on this host crashed under the Codex restricted sandbox even on
a minimal counter, but passed with approved ordinary process execution. This is
recorded as an environment limitation, not silently treated as a test pass.

## Connect a verified design

Copy `configs/recovered.template.json` to a new manifest and supply the actual
handoff paths. All input paths resolve relative to the manifest. The template's
widths, polarity, clocks, reset duration, package, and latency are placeholders,
not verified findings. Set `ready: true` only after filling the verified inputs;
`verification_evidence` names the handoff files, whose hashes are recorded. This is
provenance supplied by the design owner, not an independent certification of it.

The generic harness instantiates this simulation adapter:

```verilog
module phase4_dut(input wire clk, rst, bclk, lrclk, sd_in,
                 output wire sd_out);
    // Instantiate the supplied recovered module and map verified ports here.
    // rst is active high at this boundary; translate polarity if necessary.
endmodule
```

Put adapters under `infrastructure/adapters/` and list the adapter and all supplied
RTL files in `simulation.sources`. Do not modify the recovered logic or its model.
The harness assumes an external BCLK/LRCLK controller and shared input/output
framing; designs with output clocks or different edges need an explicit extension.

| Simulation parameter | Meaning |
|---|---|
| `SAMPLE_BITS` | Signed sample width, 2–32 bits |
| `SLOT_BITS` | BCLK periods per channel, at least sample width, at most 256 |
| `MSB_DELAY` | 1 for I2S one-bit delay, 0 for left-justified |
| `LEFT_LEVEL` | LRCLK level corresponding to channel 0 |
| `HALF_PERIOD_NS` | Integer BCLK half-period; data/LR change at falling edges |
| `CLOCK_HALF_NS` | Integer internal clock half-period |
| `RESET_CYCLES` | Initial internal clock cycles with active reset |

The monitor samples on rising BCLK edges. It handles packed slots where the final
bit arrives at the next LRCLK transition, checks slot lengths, and rejects X/Z
serial data. A literal four-bit wire-sequence test independently exercises the
driver and monitor; loopback alone is not the protocol oracle. Maximum input is
131072 words per case. The watchdog and wall-clock subprocess timeout bound runs.

Each case uses one of `input_csv`, `input_wav`, or generated `stimulus` (`edges`,
`random`, `impulse`, `sine`, `silence`) plus `frames` and optional `seed`.
CSV uses exactly `index,channel,value`: contiguous zero-based index, channel 0/1,
signed decimal samples. Inputs alternate left/right beginning with left.
WAV import accepts uncompressed PCM16/24/32 mono/stereo at the configured width;
mono duplicates into both channels. It does **not** resample, normalize, or imply
that the serial frame rate matches the WAV sample rate. Audio metadata is retained.
The two supplied WAV smoke cases use the first 256 frames as transport stimuli,
not as golden filtered outputs.

Provide `expected_csv` for each design case, or configure a model command:

```json
{
  "reference_command": ["{python}", "../../models/verified_model.py", "--input", "{input}", "--output", "{output}"],
  "reference_sources": ["../../models/verified_model.py"]
}
```

The command runs from the manifest directory with argument-vector execution, no
shell. `{input}` is the generated CSV and `{output}` is the expected CSV destination.
Add every model dependency to `reference_sources` to retain hashes. A nonzero model
exit, missing output, malformed/empty CSV, out-of-range value, length difference,
channel swap, or numerical mismatch fails the case. There is no implicit alignment
search, truncation, rounding, or clipping. `tolerance` defaults to zero integer LSBs.
`latency_words` explicitly discards that many leading actual words and requires
`actual length = expected length + latency_words`; supply sufficient input flush
frames and the corresponding shorter reference. Use even latency to preserve stereo
channel pairing unless the actual verified interface explicitly requires otherwise.

`fixture_reference: "identity"` is permitted only in `infrastructure_fixture`
manifests and must never be used to assert FIR correctness.

## Synthesis and artifacts

Configure `build.sources`, `top`, optional integer `parameters`, `device`, `package`,
`pcf`, `frequency_mhz`, and deterministic `seed`. Both simulation and build accept
`include_dirs` and `runtime_files`, a destination-to-source mapping for memory files:

```json
{"runtime_files":{"coefficients.hex":"../../handoffs/phase-03/coefficients.hex"}}
```

Runtime files are copied into the fresh run directory and hashed. Paths cannot
escape that directory. The default smoke build explicitly uses unconstrained
UP5K/SG48 IOs; those pin assignments are **not suitable for board programming**.
Normal builds require a PCF. `allow_unconstrained: true` is an explicit experimental
opt-in and remains visible in `build-summary.json`. No programming command is provided.
Global clock frequency is supported; multi-clock designs needing distinct clock
constraints require an extension before claiming complete timing signoff.

Yosys checks hierarchy and mapped design consistency, then writes `netlist.json`,
`utilization.json`, and its log. nextpnr writes routed ASC, detailed `timing.json`,
and utilization; missing clocks or failed timing fail by default. `require_clock:
false` supports intentionally combinational builds. IceStorm packs, unpacks, and
re-packs the bitstream, requiring identical hashes; `icetime` independently checks
the requested frequency. It uses explicit unpack mode to avoid Windows basename
detection differences. Tool outputs remain available even after a failed stage.

Per-case results include input/reference/source hashes, exact argv, command exit,
wall time, output hash, CSV captures, mismatch examples, RMSE and maximum error.
The top-level report includes Git HEAD/status, manifest hash, tool versions/hashes,
case statuses, and links by directory layout. JSON, Markdown, and JUnit XML are
emitted. Blocked cases are skipped in JUnit and yield exit 2, never a successful
regression. Generated build products/tool archives are ignored by Git.

## Coordination

### Recovered Phase 2 integration

The Phase 2 v2 handoff is now supported by `prepare_recovered.py`. It reads a
specific Git commit with `git show`, snapshots the supplied RTL/model/coefficients
and handoffs byte-for-byte into a fresh ignored directory, and records hashes and
the full commit ID. It never reads in-progress Phase 3 model edits or modifies
Claude's sources. In a checkout with the Phase 2 commit available:

```text
python infrastructure/prepare_recovered.py --source-root . --ref 1befb30e99a506698c45d4ca9394a3c7ec95c966 --output build/recovered-inputs
python infrastructure/run.py validate --manifest build/recovered-inputs/manifest.json --output build/recovered-validation
```

On Windows, use `.tools/oss-cad-suite/lib/python3.exe` for the first command and
`infrastructure/run.ps1` for the second. Choose new output directories on repeats.

Eight simulations compare all output words, including zero startup frames and
the last two delayed outputs flushed by two zero input frames. Two use the supplied
256-frame golden vector at BCLK 1 MHz and 625 kHz. Six call the unchanged supplied
`sw_fir.py` through a CSV/framing adapter (edge values, impulse, seeded random,
sine, silence, and 1,024 provided audio frames). Arithmetic remains in the supplied
model; the adapter only selects left input and maps filtered-left/echo-right with
the handoff's two-frame latency. No automatic latency fitting is performed.

`adapters/recovered.sv` also exposes an **audio-only** synthesis top. The five
clock/audio pins in `constraints/recovered-audio.pcf` come from the verified Phase 2
port table. The LED/RGB outputs are omitted because their individual board roles
remain provisional. Accordingly this is not a full-board replacement image or
hardware validation. The default generic recovered template remains blocked;
use the explicitly generated manifest for this verified input revision. A later
Phase 3 handoff requires its own integration run and is not implicitly covered.

Read `handoffs/phase-02/` and `handoffs/phase-03/`; report infrastructure facts through
`handoffs/phase-04/`. See `handoffs/phase-04/STATUS.md` for execution evidence and
remaining dependencies. Project Scribe in the main checkout receives this status,
test-wrapper events and Git evidence through its existing configuration. Its local
`preview` works without a model service; no model-generated report or remote
publication should be inferred from a preview.
