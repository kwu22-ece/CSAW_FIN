# AI provenance — Candidate 05d (DSP-driven)

**Competition rule:** For CSAW 2026 Challenge 3 the Trojan RTL and exploit logic
must be **AI-generated**, and **all AI logs are mandatory (missing = disqualification)**.
This directory is the complete, self-contained AI-authorship record for candidate
`05d-opus-dsp`.

## Author model

| Field | Value |
|---|---|
| Model (this session + all workflow subagents) | **Claude Opus 4.8** (`claude-opus-4-8`) |
| Harness | Claude Code (Agent SDK), multi-agent Workflow orchestration ("ultracode") |
| Candidate label | `05d-opus-dsp` (Independent Candidate D, signal-processing-driven) |
| Human role | Operator issued the phase brief; all DSP analysis, design selection, RTL, tests, and reports were AI-generated |

Every Verilog source under `../rtl/`, every reference/test model under `../tests/`,
and every report under `../reports/` was authored by the model above. No RTL was
copied from another candidate; the design was derived independently from the
recovered filter's mathematical properties.

## Contents

| Path | What it is |
|---|---|
| `prompts/` | The exact orchestration prompts given to the AI (workflow scripts: each embeds the full subagent prompts verbatim). |
| `transcripts/` | Raw AI generation logs — per-agent JSONL transcripts and the run journal for every Workflow invocation (copied from the Claude Code session store). |
| `analysis/` | Reproducible numpy/scipy analysis scripts the AI wrote and executed (the numeric evidence behind the DSP report). |
| `decisions/` | AI-authored design-decision records (candidate matrix, scoring, selected design, acceptance criteria). |
| `MODEL-PROVENANCE.md` | Per-artifact model/prompt provenance table (also mirrored into `../manifest.json`). |

## Methodology (how the AI produced this candidate)

1. **DSP analysis workflow** — 5 parallel facet analyzers (coefficients/impulse,
   frequency response, fixed-point numerics, time/latency/echo, trigger surface)
   ran real numerical experiments, an adversarial verifier independently
   recomputed the key numbers, and a synthesis pass produced the DSP report.
2. **Design-exploration workflow** — independent candidate trigger×payload
   designs were generated from different angles, scored by independent judges on
   the competition criteria, and synthesized into one selected design with an
   explicit activation condition and measurable acceptance criteria.
3. **AI implementation** — the selected Trojan RTL was authored as a drop-in
   replacement for the recovered `fir_audio_top`, keeping the datapath/timing and
   I2S protocol identical so untriggered output is bit-identical.
4. **Verification** — the shared Phase-4 harness (iverilog/vvp + yosys/nextpnr/
   icetime) ran bit-exact, impulse, frequency, directed-activation, boundary,
   resource and timing checks; claims were adversarially re-verified.

All logs that substantiate the above are preserved here verbatim.
