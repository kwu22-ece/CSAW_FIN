# Subphase Q — cycle 1 engineering record

Phase: Quality review (Q), bounded to at most five investigations.
Agent: Codex, OpenAI. This invocation did not run Claude Code / Opus.
Branch: `challenge3/quality-winner`.
Owned files: 05B RTL/model correction, `experiments/quality/`, and this handoff.
Publication: local commits only; no merge, push, board programming, or Google publication.

## Starting point and independent review

The official selection was read from the Phase 05S worktree at commit
`6d9cacf4e12a7f2357c4f36fa91d9ef87429d046`. Its exact input is retained in
`selection-input.json`, with provenance in `selection-provenance.json`.
Selected candidate: **05B**, package `9e172a865a543b03e226596689fd6691ffa2b779`;
RTL origin `15a8a6525e225ad82d931b3bc75399f744638b2e`;
common baseline `e72522f265ac36da713cd7a0dcf8dbc64ab21209`.
All four original candidate branches remain intact. The quality worktree was
created at the selected package, with no new candidate selection.

The Phase 4 infrastructure is unchanged from the common baseline. The packaged
baseline RTL matches the Phase 3 source at `5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f`
after line-ending normalization. Review isolated the candidate's matcher/counter
and output mux from the unmodified FIR arithmetic, pipeline, serializer and echo.
There is no reset input on this design; each simulation starts from power-up.

`pre-improvement.json` was frozen before any RTL/model change. Fresh evidence:
15 framework tests; 10 standard simulations; two common supplied-vector cases;
7 no-trigger cases with 0/22,248 baseline word errors; four successful existing
activation events; 0/481,082 errors over all 240,000 supplied noisy-WAV frames.
Audio is four reset-isolated chunks with seven-frame overlap, not an uninterrupted
240,000-frame hardware stream. The baseline direct-top build reproduced
3,283 logic cells and 14.9633398056 MHz. Selected 05B reproduced 3,313 cells,
15.4846696854 MHz and bitstream `7fff6e2d74e617354d0d06b4098758137f6f82f5e0ba2d362ec8ab39e5ac47bd`.
Both use UP5K/SG48, nine identical constrained pins, 10 MHz and seed 1.

The initial full-audio Scribe wrapper expired after 300 seconds. Chunks 00–02
completed and passed; the incomplete chunk 03 was rerun in a new output directory
under a 1,200-second wrapper. The frozen report identifies each actual case
directory and hashes its receipts; it does not call the interrupted invocation a
pass. No completed chunk was repeated. Later full-audio wrappers use 1,200 seconds.

## Iteration 1 — first post-bypass sample

Hypothesis: `bypass_active` remains set until the sample after the 128-frame raw
window. The active branch clears the matcher on that sample, so a new eight-word
sequence beginning there is missed. The candidate reference duplicates this
transition, explaining why its existing regression cannot reveal the error.

Experiment: define activation times independently of both FSMs. The first trigger
completes at input frame 15, making raw frames [15,142] inclusive. Put the next
sequence at frame 143 plus offsets -7, -1, 0, 1, and 2. Add all eight single-word
near misses, a right-slot-only sequence and a prefix restart. Test every case at
1 MHz and 625 kHz BCLK, with exact signed comparisons and unchanged latency.
The oracle uses only the original FIR arithmetic and explicit payload intervals.

Before correction, exactly the two offset-zero cases fail: each misses the second
activation and has 128 wrong left words. The other 28 cases pass. The test vectors
and expectations were generated before the fix and reused without modification.
`audit_directed.py` separately checks every captured output against normal FIR
values and the exact expected raw windows; all payload samples are observable
because their raw values differ from the filtered values.

AI correction: on the counter-expiry sample, seed `magic_position` to one when
the sample equals MAGIC_0. Preserve the counter, bypass mux and all FIR logic.
The reference model receives the corresponding correction. This is a three-line
RTL addition, including comments. Focused result: 30/30 directed cases pass, with
exact 128-frame windows, correct return to filtering and unchanged echo. Standard,
framework and common-vector tests pass. Build: 3,240 cells, 15.2716045380 MHz,
zero RAM/DSP, nine IOs; icetime independently passes 10 MHz at 14.87 MHz.
The 73-cell reduction is a measured synthesis result, not a promised optimization.
The 0.2130651474 MHz reduction from the original Fmax is accepted only if full
regression passes, because correctness improves and the 10 MHz requirement holds.

## Iteration 2 — receipt and provenance reproducibility

Hypothesis: the old inventory mixes checkout newline encodings and stale content,
so its verification claims cannot reliably identify the selected source.
Audit all 35 original entries against the exact selected Git blobs and LF/CRLF
variants. Three entries fail every encoding: candidate RTL, BASELINE_PROVENANCE.md,
and prepare_vectors.py. The historical 3,662-cell/49e24471… build is excluded.
Historical receipts remain preserved, with current measurements in the Q handoff.

Two original 05B main-session logs were located and copied byte-for-byte to a
private local archive outside Git. An interaction export preserves user/assistant
messages and tool traffic without internal reasoning. Its index maps source-path
mentions in tool calls to preceding prompts; such mentions alone are not proof
of a successful write. Original runtime metadata records `gpt-6-luna`; the prompts
requested Astra. The previous label is not asserted as verified model identity.
Current-session capture is a snapshot while this session remains open. Final
transcript capture and official provenance sufficiency remain Phase 6 obligations.

## Documentation and limits

Project Scribe's existing controller records test exits in its shared local event
database. A local configuration extends its allowlist to this worktree without
modifying the main checkout's configuration. Its configured model is still
`FILL_PROVIDER/MODEL_ID`, so no model-generated canonical report is claimed.
The final Scribe preview is an evidence record, not model synthesis or publication.

No Hackster/FTDI/USB Serial/iCE40 device was identified by local PnP enumeration.
Physical-board equivalence, host link, trigger demonstration, LED/pin behavior,
and audio capture remain unverified. Enumeration does not prove that no board
exists elsewhere. No implementation integration is authorized by this handoff.

Completion status, acceptance decisions, exact best SHA, evidence paths and
reproduction commands are in `current-best.json` / `current-best.md` at checkpoint.

## Cycle acceptance and stop

Iteration 1 was retained at `f45ad424657f5c85d47cbc4134f88a1326e6a0fd` after full audio and relevant regressions passed. Iteration 2 was retained at `fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6`: a clean Git archive reproduced all 46 simulations, 15 framework tests, both candidate and baseline builds, and the identical candidate bitstream. All standard and full-audio captures were byte-identical to the original. No implementation revision was rejected; the original failing boundary experiment and interrupted wrapper remain recorded.

The bounded cycle stops after these two accepted iterations. No further verified functional defect is known in the exercised scope. Required physical verification is unavailable. Scribe preview succeeded with 96 recorded events after increasing only the local quality configuration evidence cap; no model synthesis or publication occurred. See `documentation-receipt.json`.
