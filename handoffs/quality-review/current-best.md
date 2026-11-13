# Quality checkpoint — cycle 1

Best verified package: **`fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6`** (05B).
Branch: `challenge3/quality-winner`. RTL fix: `f45ad424657f5c85d47cbc4134f88a1326e6a0fd`.
Original selected package: `9e172a865a543b03e226596689fd6691ffa2b779`. Shared baseline: `e72522f265ac36da713cd7a0dcf8dbc64ab21209`.

Two focused iterations are complete. The first post-bypass input now participates
in trigger matching. Independently scheduled boundary tests improved from 28/30
to 30/30; exact 128-frame bypass windows and unchanged echo were verified.
The second iteration repaired source receipts and preserved private AI logs.

| Check | Result |
| --- | --- |
| Simulations | 46/46: 10 standard, 2 common, 30 directed, 4 full-audio |
| Framework tests | 15/15 |
| Original no-trigger comparison | 0 errors / 22,248 words |
| Full noisy audio | 0 errors / 481,082 words; 240,000 source frames |
| Logic cells | 3,313 → 3,240 (−73); common baseline 3,283 |
| nextpnr Fmax | 15.484670 → 15.271605 MHz; 10 MHz requirement passes |
| DSP / RAM / IO | 0 / 0 / 9 |
| Source inventory | 41/41; deliberate false hash rejected |
| Clean archive reproduction | Full suite passed; identical bitstream |
| Hardware | Not run |

Bitstream SHA-256: `2742912e31ec6c058756e5623d84736285dc2d46695d8ece616494e3152a89b0`.
All standard and full-audio output captures are byte-identical to the original.
Audio chunks reset independently with seven-frame overlap. No uninterrupted
hardware stream, board equivalence, or LED/pin behavior is claimed.

Reproduce from the best package in a checkout containing the Phase 2 commit:

```powershell
& C:/Users/lowbr/oss-cad-suite/lib/python3.exe experiments/quality/run.py --suite C:/Users/lowbr/oss-cad-suite --output build/quality-reproduction-NEW
```

Use a fresh output directory. Full archive preparation commands, source/evidence
hashes, rollback SHA, accepted/rejected revisions and next steps are in
`current-best.json` and `reproduction-evidence.json`. The prior verified revision
`f45ad424657f5c85d47cbc4134f88a1326e6a0fd` and original candidate branches remain available for rollback.

Phase 6 may use the best package for an explicit integration step and hardware
validation. Final transcript capture and provenance review remain required:
the original logs record gpt-6-luna despite an Astra request; this Q session ran
Codex with recorded gpt-6-astra, not the requested Claude/Opus runtime. Original
logs were privately preserved; the current-session copy is a live snapshot.
Scribe recorded local evidence; its model remains unconfigured.

Stopped after two iterations because available priority checks pass and physical
verification needs hardware. No push, merge or external publication occurred.
An external runner must invoke any continuation. Read this checkpoint first.
