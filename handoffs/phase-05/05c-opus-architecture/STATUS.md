# Phase 5C handoff — Candidate C (Architecture-Driven)

**Model:** Claude Opus 4.8 (`claude-opus-4-8`), max-effort multi-agent ("ultracode").
**Branch:** `challenge3/05c-opus-architecture` · **Base commit (pinned):** `e72522f`.
**Deliverables root:** `experiments/phase05/05c-opus-architecture/`.
**Scope:** one independent architecture-driven Trojan candidate, as authorized for
the CSAW 2026 Challenge 3 academic CTF. Does **not** select the overall winner;
does **not** merge any other candidate's approach; did not modify another agent's
worktree/branch.

## Design (architecture-driven)

- **Trigger:** the recovered baseline shifts the RIGHT I2S slot into `rx_sh` but
  never captures it — a control channel orthogonal to the audio path. An ordered
  3-frame covert knock `0xC0DE → 0xFACE → 0xBEEF` on the right slot sets a sticky
  `armed` FF (restart credit on `MAGIC0`; per-triple false-match prob 2⁻⁴⁸).
- **Payload:** one 16-bit 2:1 mux at the existing `end_frame` TX load —
  `y_d <= armed ? echo : y_filt` — passing the raw input (filter bypass) once
  armed. The 63-tap MAC datapath is untouched; `echo` is latency-aligned so
  framing/LATENCY=2 are preserved and the accumulator critical path is unaffected.
- **TROJAN_EN** parameter: 1 = Trojan present (default); 0 collapses to baseline.

## Verification (all via the Phase 4 harness; OSS CAD Suite)

| Method | Evidence | Result |
|---|---|---|
| Inactive equivalence (sim) | 8 recovered vectors incl. 1024 real-audio, vs **unmodified** baseline reference | **8/8 max error 0** |
| Directed active (sim) | arm→bypass tone, impulse, restart-credit overlap vs `trojan_ref.py` | **3/3 max error 0** |
| Directed near-miss (sim) | 2-of-3, 1-LSB, interrupted, non-consecutive, wrong-order vs baseline | **5/5 bit-identical (no arm)** |
| Static | `reports/trojan-vs-baseline.diff` + Yosys hierarchy/map checks | contained; 2 functional edits |
| Timing | nextpnr + icetime @10 MHz, seed 1 | baseline 14.44/14.23 → Trojan **14.84/14.47 MHz**, no regression |
| Resources | UP5K/SG48 | **+27 LC, +41 LUT4, +3 FF, 0 DSP, 0 BRAM** (3292/5280 LC) |
| Payload magnitude | impulse response | baseline 63 non-zero taps → armed **1** (single-sample passthrough) |

Machine-readable: `manifest.json`, `reports/verification-summary.json`,
`reports/{inactive-equivalence,directed,fpga-build,baseline-build}/`.
AI provenance (mandatory): `ai/design-research.md`, `ai/interaction-log.md`,
`ai/candidate-evaluation.workflow.json`, `ai/candidate-evaluation.journal.jsonl`.

## Outstanding / pending

- **Physical hardware demonstration is PENDING** — no Hackster board in this
  environment. On-board `sw_filter == hw_filter`, the live triggered demo, and
  power side-channel / `ICE_LED` observation are not done.
- Untriggered **I/O** is bit-identical (sim-proven); the **bitstream** differs
  because the Trojan logic is present (candidate vs baseline SHA in `manifest.json`).
- Equivalence is against the Phase 2/3 behavioural reconstruction, not a
  gate-level copy of the stock bitstream.

## Coordination

Phase 4 infrastructure consumed read-only (`infrastructure/`, `handoffs/phase-04/`);
shared candidate manifest schema followed (mirrors `05a`). No Phase 2/3/4 sources
or other candidates' trees were modified. Not pushed to the public remote
(unreleased competition artifact) — committed locally only, pending authorization.
