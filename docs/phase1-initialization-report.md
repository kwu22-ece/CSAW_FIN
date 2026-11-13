# CSAW 2026 — Challenge 3 — Phase 1 Milestone Report

**Phase:** 1 — Project Initialization and Research (research/setup only; no Trojan
development or bitstream modification performed).
**Date:** 2026-11-12.
**Project root:** `C:/Users/lowbr/Documents/College/AI/CSAW_FIN`
**Repository:** https://github.com/kwu22-ece/CSAW_FIN (`origin`, public).
**Feature branch:** `phase1/initialization-and-research`.

This report is both the Phase 1 deliverable and the evidence packet handed to the
existing documentation agent (Project Scribe) via its `git.sourceFiles` interface. All
claims below are observations from this machine on the date shown; audio filenames and
agent assertions are not treated as proof of processing results or correctness.

## 0. AI session provenance (model names and interactions)

- Tooling: Claude Code (Anthropic) running in the Claude desktop app.
- Models used this session: **Claude Fable 5.2** (`claude-fable-5-2`) at session start,
  then **Claude Opus 4.8** (`claude-opus-4-8`) for the remainder (model switched
  mid-session by the harness).
- Nature of interaction: directory inspection, documentation-agent code review, Git
  inspection, web research of the challenge and model repositories, dependency install,
  and documentation-agent integration. No RTL was written, synthesized, or programmed.
- Full raw transcripts are intentionally not embedded (privacy + the agent's untrusted-
  input policy). Future coding turns are captured automatically once the installed Claude
  hooks (see §2) are active.

## 1. Local directory inventory

```
CSAW_FIN/
  .git/                                  # git repo, branch main -> origin/main
  .gitignore                             # excludes config.json, state/reports/generated, secrets, node_modules
  README.md                              # project overview
  what_a_piece_of_work.wav               # audio input (~2.8 MiB, tracked in git)
  what_a_piece_of_work-noisy.wav         # audio input (~0.48 MiB, tracked in git)
  docs/phase1-initialization-report.md   # THIS report (added in Phase 1)
  DocumentAgent/openclaw-project-scribe/  # the existing documentation agent (see §2)
    README.md REQUIRED-VALUES.md SOURCES.md VERIFICATION.md SETUP-CSAW_FIN.md
    config.example.json  config.json (gitignored)  config.json.backup* (gitignored)
    package.json  scribe.mjs             # CLI entry point
    lib/core.mjs lib/google.mjs lib/setup.mjs
    scripts/setup.ps1 scripts/setup.sh
    test/scribe.test.mjs                 # 28 tests, all passing on this host
    workspace/AGENTS.md SOUL.md IDENTITY.md PROJECT.md
    workspace/skills/project-documentation/SKILL.md
```

Observation: both `.wav` files are already committed to the public repo (from the prior
`Import CSAW_FINALS project work` commit). They are challenge audio inputs, not build
outputs. History was NOT rewritten and nothing was deleted; flagged here as an open
question (§8) because a public repo now carries a ~2.8 MiB binary.

## 2. Documentation agent integration (Project Scribe)

**Identity:** `DocumentAgent/openclaw-project-scribe/` — "Project Scribe", a local,
dependency-free Node package (Node 24.16+; built-in SQLite) plus a dedicated OpenClaw
synthesis agent. It observes coding-agent sessions, records normalized events in SQLite,
reads Git evidence, asks a tool-denied OpenClaw agent for an evidence-cited JSON digest,
and optionally publishes a managed block into a Google Doc.

**Entry point / interface:** `node --no-warnings scribe.mjs <command> --config <abs config.json>`.
Commands: `setup [--apply]`, `verify`, `hooks`, `capture`, `preview`, `run`, `status`,
`export`, `record-test`, `google-auth`, `google-inspect`, `schedule`.

**Evidence ingestion (how to feed it project records):**
- Milestones / findings / file paths / next steps -> text files allowlisted in
  `config.json > git.sourceFiles` (cited as `source:N:M`, capped at 12,000 chars each).
- Commands / actions / model names / assistant messages -> Claude/Codex hooks captured
  into SQLite for future turns (cited as `event:N`).
- Verification outcomes -> the `record-test` wrapper records a command's exit code, HEAD,
  and tracked-state stability.
- Git state (status/diffstat/commits/source excerpts) -> captured automatically each run.

**Activation state (as found, then updated this phase):**
- Config prepared for project `CSAW_FIN`, agent id `csaw-fin-scribe`; state/reports/
  workspace under `C:/Users/lowbr/AppData/Local/openclaw-project-scribe/CSAW_FIN`.
- OpenClaw **Gateway runtime: stopped** (port 18789 held by an unrelated VM process —
  left untouched); model catalog empty; agent `csaw-fin-scribe` **not registered** (only
  `main` exists); `openclaw.model` still a `FILL_PROVIDER/MODEL_ID` placeholder; Google
  publishing disabled. => Full model synthesis (`run`) and publishing are NOT available
  and were NOT forced. The package is "prepared, not activated" (matches SETUP-CSAW_FIN.md).

**Integration performed this phase (no activation, no paid model call, no config overwrite):**
- Backed up `config.json` (timestamped, gitignored), then made two additive edits only:
  (a) added `docs/phase1-initialization-report.md` to `git.sourceFiles`; (b) filled
  `FILL_NODE_EXE` with the verified Node path `C:/Program Files/nodejs/node.exe`. Agent
  identity, model, agentId, paths, and Google settings were left unchanged.
- Installed project-local Claude hooks at `.claude/settings.local.json` (gitignored) so
  future coding turns are captured. (Requires a session restart to take effect; does not
  capture this session retroactively.)
- Recorded a verification outcome through the agent's `record-test` wrapper.
- Ran `scribe.mjs preview` to produce a local, model-free evidence report
  (`preview.md` + `preview-evidence.json` in the reports dir) that incorporates this
  milestone report, the Git snapshot, and the recorded test. This is the Phase 1
  "submit through the agent" deliverable; it advances no checkpoint and calls no model.

## 3. Git repository status

- Branch at start: `main`, up to date with `origin/main`, working tree clean.
- Remote: `origin` = https://github.com/kwu22-ece/CSAW_FIN.git (fetch+push) — matches the
  required remote.
- Commits at start: `9893aed Import CSAW_FINALS project work`, `92876d5 Initial commit`.
- Phase 1 work committed on new branch `phase1/initialization-and-research`.
- `.gitignore` already excludes `config.json`, `config.json.backup*`, `.state/`,
  `reports/`, `generated/`, `*.db*`, `node_modules/`, `.claude/settings.local.json`,
  `*token*.json`, `*credentials*.json`, `*service-account*.json`, `*.pem`, `*.key`. No
  credentials, private transcripts, or build outputs are staged. Only this report is added.

## 4. Research results

### 4.1 Challenge 3 (finals) — target and goal
- Target: a streaming **FIR audio filter** on a **Lattice iCE40-UP5K** FPGA running on a
  physical **Hackster** board. The asset is data-path integrity (pass only in-band audio).
  No key; RTL is **not** provided — teams reverse-engineer the supplied **bitstream**.
- Goal (Phase 2+): use generative AI to design and insert a **stealthy hardware Trojan**
  (hidden trigger + payload), keep normal filtering bit-identical until the trigger fires,
  and **demonstrate on real hardware**.
- Signal path: PC -> RP2040 (I2S controller + USB bridge, MicroPython) -> FPGA (I2S
  target) -> back. `BCLK` <= 1 MHz; FPGA samples on its 10 MHz `ICE_CLK`. Board has
  power side-channel circuitry and an activity LED (`ICE_LED`).
- Provided files (challenge repo `finals/challenge_3/`): `fpga/fir_audio_top.bin`,
  `fpga/Makefile` (+`hackster.mk`, `hackster-fpga-program.py`, programs but does NOT
  synthesize), `tools/stream_audio.py`, `tools/audio_bridge.py`, `tools/requirements.txt`,
  `audio/*.wav` samples, `README.md`, `ice40_audio_filter_IP.md`.
- Deliverable `submission.zip`: `rtl/` (AI-generated synthesizable Verilog), `tb/`
  (exploit testbench + host driver), `demo/` (hardware evidence), `ai/` (**all AI logs —
  missing logs = disqualification**), and a technical brief (README/PDF).
- Scoring: base 100 (Creative GenAI 35, Trojan Quality 25, System Automation 15, Docs/
  Reproducibility 15, HW Demo 10) + Bonus A up to 20 (two extra HW Trojans) + Bonus B up
  to 10 (bit-exact covert channel) = 130 max.
- Constraints: Trojan RTL + exploit logic must be **AI-generated** (humans may use
  non-AI tools for RE/build/program/drive); untriggered output must be **bit-identical**
  to the stock bitstream and pass the link check; must not fire on ordinary speech/music.

### 4.2 Finals context
Three challenges over 24h at CSAW; Challenge 3 is the final one. Finals window: released
12 PM EST 2026-11-12, due 12 PM EST 2026-11-13 (subject to change). Each team presents to
judges on their GenAI use and strategy. Rubric finalized at event start.

### 4.3 Prebuilt AI technique models (KennethLei1492/prebuilt-ai-technique-models)
A Python package of six composable "pipeline models" sharing one `TaskRequest`/`TaskResult`
contract: **Hybrid Retrieval**, **Task Decomposition**, **Answer Verification**,
**Parallelization**, **Caching**, and **Pipeline RAG**. Built on the Claude API (default
`claude-opus-5-5`, via `ANTHROPIC_API_KEY` or `ant auth login`; `PIPELINE_MODEL`/
`PIPELINE_EFFORT` configurable); a deterministic `MockLLM` runs offline with no key.
Install: `pip install -e ".[dev,retrieval]"`, test `python -m pytest -q`, quality gate
`python tools/quality_gate.py`, offline demo `python -m pipeline_rag --offline ...`.
Relevance: scaffolding for the "Creative Use of GenAI" / "System Automation" scoring and
for producing the mandatory `ai/` logs; offline mock validates flow/shape, not answer
quality. Not yet cloned/installed (investigation only; see §7).

## 5. Dependency inventory and tool versions

Installed and verified on this host (2026-11-12):

| Tool | Version | Source | Status |
|---|---|---|---|
| Node.js | v24.16.0 | C:/Program Files/nodejs | present (meets Scribe >=24.16) |
| Git | 2.54.0.windows.1 | C:/Program Files/Git | present |
| OpenClaw CLI | 2026.11.3 (847611d) | npm global | present; Gateway stopped, no model |
| Python | 3.13.14 | Windows Store build | present |
| pyserial | 3.5 | PyPI (pip --user) | **installed this phase** |
| mpremote | 1.29.0 | PyPI (pip --user) | **installed this phase** (+ platformdirs 4.14.5) |

Missing (needed in later phases; reproducible install procedures documented for §7):

| Tool | Needed for | Install (reproducible) |
|---|---|---|
| OSS CAD Suite (Yosys, nextpnr-ice40, icepack/iceprog/icetime) | synthesizing/ packing the AI-generated iCE40 RTL | download YosysHQ/oss-cad-suite-build Windows release, extract, add `bin/` to PATH |
| Icarus Verilog or Verilator | `tb/` exploit simulation | winget/choco `iverilog`; Verilator via OSS CAD Suite or MSYS2 |
| ffmpeg | convert audio to 16 kHz/16-bit mono PCM | `winget install Gyan.FFmpeg` |

Notes: user pip Scripts dir
`C:/Users/lowbr/AppData/Local/Packages/PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0/LocalCache/local-packages/Python313/Scripts`
is not on PATH — use `python -m mpremote` or add it. Package managers available: winget,
choco (choco installs typically need an elevated shell). The challenge `tools/
requirements.txt` pins `mpremote>=1.20.0` and `pyserial>=3.5` (both satisfied).

## 6. Verification outcomes

- Project Scribe test suite: **28 passed / 0 failed / 0 skipped** (Node built-in runner,
  ~24 s), confirming the documentation agent functions on native Windows. Recorded through
  the agent's `record-test` wrapper (an `event` in its SQLite DB).
- `pyserial` and `mpremote` import/CLI verified (`import serial` -> 3.5; `mpremote --help`).
- `scribe.mjs preview` produced a report with no model/Google call.

## 7. Next-phase instructions (Phase 2+)

1. Install the FPGA build + simulation toolchains (OSS CAD Suite, iverilog/verilator,
   ffmpeg) per §5 and record versions.
2. Clone the challenge repo and the prebuilt-ai-technique-models repo **outside** this
   project tree (untrusted-data hygiene); set `ANTHROPIC_API_KEY` or use `--offline`.
   Do not commit cloned third-party trees into this public repo.
3. Reverse-engineer `fir_audio_top.bin` (icestorm/`icetime`, side-channel + `ICE_LED`),
   and reconstruct an equivalent synthesizable FIR in `rtl/`.
4. Only then begin Trojan design (trigger + payload) with AI assistance, preserving
   bit-identical untriggered output; keep all AI logs in `ai/` (missing = DQ).
5. To activate full Scribe synthesis/publishing: start the OpenClaw Gateway, set
   `openclaw.model` to a real provider/model, run `scribe.mjs setup --config config.json`
   then `--apply` to register `csaw-fin-scribe`, `verify`, a manual `run`, then
   `schedule --apply`. Configure Google only when a destination Doc + credentials exist.

## 8. Failures, errors, and unresolved questions

- OpenClaw Gateway is stopped and TCP 18789 is held by an unrelated VM process; a real
  model and agent registration are still required before `run`/`schedule` can work.
  Resolving these (and choosing a possibly paid model) is deferred to the operator.
- No coding-agent events existed at Phase 1 (hooks not previously installed); this
  session is therefore not in the event DB. Hooks installed now apply to future turns only.
- Open question: should the tracked `.wav` inputs remain in the public repo, or be removed
  going forward (history rewrite intentionally not performed in Phase 1)?
- `ice40_audio_filter_IP.md` interface doc and the exact `fpga/Makefile` targets were
  noted from the challenge README but not yet fetched in full; review at the start of Phase 2.
