# Phase 5C — AI Interaction Log (Candidate C, "Architecture-Driven")

Mandatory AI-provenance record. All Trojan trigger/payload RTL and the exploit
reference model in this candidate were AI-authored by **Claude Opus 4.8**
(`claude-opus-4-8`) in Claude Code (Anthropic), using max-effort multi-agent
("ultracode") orchestration. The recovered baseline FIR (`fir_audio_baseline.reference.v`,
`sw_fir.reference.py`, `coeffs.json`) is prior Phase 2/3 work, copied in verbatim
as the host design and not re-authored here.

## Session flow

1. **Orientation (Claude, main loop).** Read project memory and the Phase 2/3/4
   artifacts in the pinned baseline worktree (`challenge3/05c-opus-architecture`
   @ `e72522f`): the recovered RTL, the bit-exact `sw_fir` model, the Phase 4
   simulation/build harness (`infrastructure/`), the recovered-inputs manifest,
   and the PCF. Confirmed the OSS CAD Suite toolchain runs.

2. **Baseline validation (harness sanity).** Ran the recovered-design manifest
   through `infrastructure/run.py validate`: 8/8 simulations bit-exact (max error
   0, incl. 1024 real-audio samples) and a passing UP5K/SG48 build
   (3265 LC, Fmax ~14.4 MHz, critical path = 40-bit accumulator). Captured as the
   equivalence/timing reference.

3. **Candidate design evaluation (Workflow, 7 Opus 4.8 subagents).** A
   deterministic workflow analysed six independent trigger/payload families in
   parallel and a ranking agent selected the best-supported "architecture-driven"
   design. Raw structured output: `candidate-evaluation.workflow.json`; synthesis
   and rationale: `design-research.md`. Selected: **right-slot covert knock →
   filter bypass** (payload insertion point grafted from the `seq-bypass` runner-up
   so the passthrough source is the latency-aligned `echo` register).

4. **RTL authoring (Claude).** Produced `fir_audio_top_trojan.v` by copying the
   recovered baseline verbatim and inserting only the marked `// *** TROJAN`
   lines: a `TROJAN_EN` parameter, the 3-state right-slot sequence detector with
   restart credit, the sticky `armed` flip-flop, and the single 16-bit 2:1
   output mux. A write-only capture register surfaced in the first synthesis as
   dead logic and was removed so RTL, simulation, and synthesis agree; the
   detector reads the right sample inline exactly as the baseline forms
   `left_sample`.

5. **Verification harness (Claude).** Authored a candidate-local adapter
   (`trojan_adapter.sv`), a Trojan-aware reference model (`trojan_ref.py`, reusing
   the authoritative baseline FIR arithmetic and adding only the trigger/payload
   logic), a directed-vector generator (`gen_vectors.py`), and two run manifests
   (inactive-equivalence reusing the 8 recovered vectors vs the *unmodified*
   baseline reference; directed active + near-miss vs the appropriate reference).

6. **Multi-method verification (Claude, via the Phase 4 harness).**
   - Static: contained RTL diff + Yosys hierarchy/mapping checks (build stage).
   - Simulation: 8 inactive + 8 directed Icarus simulations, all max error 0.
   - Math reference: baseline `sw_fir` and independent `trojan_ref`.
   - Directed vectors: 3 active (incl. restart-credit overlap), 5 near-miss.
   - Regression: full recovered 8-vector suite against the Trojan-present RTL.
   - Timing: nextpnr + icetime, both > 14 MHz vs the 10 MHz target.
   - Resources: +41 LUT4 / +3 FF / +27 LC, 0 DSP, 0 BRAM.
   - Repeatability: fixed seed=1, scripted exact commands (see manifest).

## Failures / corrections retained (not hidden)

- First directed run failed "Stimulus value out of range": the magic codes
  (e.g. 0xC0DE) exceed signed-16 and must be written as their signed decimal
  (−16162); the serialized two's-complement bit pattern is identical, so the RTL
  comparator still matches. Fixed in `gen_vectors.py`.
- First Trojan synthesis showed only +3 FF (not the estimated ~19): the
  `right_sample` register was write-only and pruned. Removed it (see step 4).
- Harness requires a fresh `--output` directory each run; superseded run
  directories were discarded.

## Reproduction

See `manifest.json` → `exact_commands`. All commands are argv-executed (no shell)
and need the OSS CAD Suite on `OSS_CAD_SUITE` (or `--suite`).
