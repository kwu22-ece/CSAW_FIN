# Phase 5C — AI Design Research (Candidate C, "Architecture-Driven")

**Model:** Claude Opus 4.8 (`claude-opus-4-8`), Claude Code (Anthropic), max-effort
multi-agent ("ultracode") orchestration.
**Authorized context:** NYU CSAW 2026 AI Hardware Attack Challenge, finals
Challenge 3 — an academic CTF. All work is a benign, sandboxed hardware-security
demonstration on the competitor's own iCE40-UP5K board. Untriggered behaviour is
bit-identical to the recovered baseline; the trigger cannot fire on ordinary
speech/music.

This document, together with `candidate-evaluation.workflow.json` (the raw
structured output of the candidate-evaluation workflow) and `interaction-log.md`,
is the mandatory AI-provenance record for this candidate.

## 1. Method

A deterministic Workflow (7 subagents, all Opus 4.8) was run:

- **Analyze (6 agents, parallel):** each independently read the recovered baseline
  RTL and rigorously assessed ONE trigger/payload family against seven criteria
  (specificity, stealth, baseline-equivalence, payload-impact, FPGA-feasibility,
  testability, evidence-quality), scoring 1–5 each with quantitative
  false-trigger and resource estimates.
- **Rank (1 agent):** synthesized the six assessments, selected the single
  best-supported design for the "architecture-driven" remit (favouring
  control/interface-structure exploitation and clean verifiability), and was
  permitted to graft the best idea from a runner-up.

## 2. Candidate families evaluated (scored totals /35)

| Family | Trigger | Payload | Total |
|---|---|---|---|
| seq-bypass | magic-knock on LEFT sample sequence | filter bypass (passthrough) | 34 |
| **right-slot-covert** | **magic knock on the unused RIGHT I2S slot** | **filter bypass (grafted)** | **selected** |
| seq-coefswap | magic-knock on left | spectral-inversion coefficient swap | — |
| amplitude-saturate | N consecutive full-scale samples | mute / gain | — |
| interface-timing | illegal WS/BCLK framing | (various) | — |
| seq-covert-lsb | magic-knock on left | bit-exact LSB covert channel (Bonus B) | — |

(Full per-family JSON with scores, risks, and resource estimates is in
`candidate-evaluation.workflow.json`.)

## 3. Selected design and rationale

**Winner: `right-slot-covert`** with the payload insertion point grafted from
`seq-bypass`.

**Why architecture-driven (the deciding factor).** The recovered baseline
deserialiser shifts the RIGHT I2S channel bits into `rx_sh` but *never captures
them* — it latches only the left sample at L0 and strobes `end_frame` at R0,
discarding the right contents. The right slot is therefore a control channel
**structurally orthogonal to the audio datapath**: no speech or music, however
pathological, ever exercises it (in normal operation the right slot carries
silence or a left-copy that the design ignores). This buys maximal **specificity**
and **stealth** simultaneously, which no signal-path trigger (left-sample knock,
amplitude pattern, coefficient swap) achieves — those must argue
"band-limited-impossibility" against live audio.

**Trigger.** Capture `right_sample` at the existing R0 event; match an ordered
3-frame knock `0xC0DE → 0xFACE → 0xBEEF` on consecutive frames. `seq_idx` advances
on exact match and resets on mismatch, with a one-step restart credit when the
mismatching value equals `MAGIC0` (so partial self-overlap cannot be gamed and the
FSM cannot lock up). A sticky `armed` flip-flop latches on the 3rd match. Per-frame
false-match probability of the ordered triple = 2⁻⁴⁸ ≈ 3.6×10⁻¹⁵.

**Payload.** A single 16-bit 2:1 mux at the documented output-load point inside
`if (end_frame)`: `y_d <= armed ? echo : y_filt`. The 63-tap MAC datapath is left
byte-for-byte untouched, so `y_filt` is always the exact baseline FIR result. When
armed, the left ("filtered") slot is loaded from the latency-aligned `echo`
register (raw input), passing all out-of-band energy at full gain — defeating the
"pass only in-band audio" asset. Because `echo` is latched from the same
`new_sample` as `y_filt`, framing and the host LATENCY=2 are preserved with zero
skew, and the mux sits at the low-rate frame boundary, far off the serial-MAC
accumulate carry chain (the real critical path), guaranteeing no Fmax regression.

**Rejected alternatives (key reasons).** `seq-coefswap` scored payload-impact 5
but places a mux in the multiplier input path, eroding the ~4 MHz Fmax slack (a
timing-regression risk the remit penalises); `amplitude-saturate` risks false
triggers on loud/clipped music; the left-sample knocks sit in the audio path and
rely on improbability rather than structural orthogonality.

## 4. Chosen activation condition, behavioural change, acceptance criteria

- **Activation:** `armed` 0→1 at the 3rd consecutive right-slot match
  `{0xC0DE,0xFACE,0xBEEF}`; sticky until power-on (matches the baseline's
  reset-less design).
- **Behavioural change:** untriggered → output identical to baseline; after the
  knock → left output = raw input passthrough (filter bypassed), so left output
  equals the right/echo output.
- **Acceptance — inactive (bit-identity):** Trojan-present RTL vs the *unmodified*
  baseline reference on the 8 recovered vectors (incl. 1024 real-audio samples)
  and all directed near-miss vectors → **zero** differing samples; `armed`
  stays 0.
- **Acceptance — active (payload):** vs the triggered reference model, after the
  knock the left output bit-exactly equals the raw input (LATENCY=2) and the
  impulse response collapses from 63 non-zero taps to a single sample.
- **Acceptance — resources/timing:** UP5K/SG48 synthesis passes with a small
  resource delta and no timing regression at the 10 MHz board clock.
- **Hardware:** on-board demonstration marked **pending** (no physical Hackster
  board available in this environment).
