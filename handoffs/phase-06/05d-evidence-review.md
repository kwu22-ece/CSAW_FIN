# Phase 6 follow-up for 05D

Reviewed November 13, 2026 on `codex/challenge3-phase-06-validation`. The 05D branch tip is `51c223336f3d4d23854907bdee87dfd5ac1f2e98`. The manifest was introduced in `629c7d4a1dd158ff1b6585e0e84e9aff74f8810f`. The later commit supplies the previously missing verification report and adds analysis and documentation evidence. The RTL, golden inputs, manifest, and saved build receipts are byte-identical between the two commits.

## Verified from files

- All 11 files under `golden/` and the clean `rtl/fir_audio_top.v` match Git blobs from the Phase 3 baseline at `5dedf4c4ed10f47fbe9ec138c7db2019446cdb7f`.
- Direct comparison of retained expected and actual CSVs yielded zero mismatches over 1,568 words from six baseline runs and 11,808 words from ten 05D normal-operation runs. Indices, stereo channel order, signed 16-bit range, and recorded compile and simulation exits also checked out. The archived simulation reports were recorded at the Phase 4 base with the experiment files untracked. These results describe the retained captures.
- Both local UP5K/SG48 build summaries equal their committed receipts. The saved bitstreams and their respective pack/unpack/repack outputs match the recorded hashes. The RTL and adapter hashes in both build-input receipts match raw commit blobs. The constraint file hash matches the committed Phase 4 PCF after CRLF conversion. The checked-in manifest has no complete source hash inventory or literal candidate SHA.

| Saved build at 10 MHz, seed 1 | Logic cells | nextpnr maximum clock |
|---|---:|---:|
| 05D clean control | 3,265 / 5,280 | 14.445 MHz |
| 05D candidate | 3,704 / 5,280 | 14.409 MHz |

The saved 05D build uses 439 more logic cells than its paired control and meets the recorded clock constraint. A saved pack/unpack round trip verifies artifact consistency. Fresh synthesis, a second independent build, activation tests, and board checks were not executed in this review. No hardware validation receipt was found. Candidate signoff remains open.

## Selection

Subphase Q has since committed `handoffs/quality-review/current-best.json` on `challenge3/quality-winner`. It records 05B revision `fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6` as the current selection. That commit exists and is an ancestor of the quality branch. The committed inventory receipt reports 41 checks and zero failures, and the reproduction receipt names the same SHA. The 05D package completion does not change that recorded selection.

Evidence was read from the immutable 05D commit, the retained local `build/05d/` receipts and captures, and the committed Subphase Q handoff. Candidate files and branches were preserved. This review contains no candidate bitstream, activation procedure, or private transcripts. The handoff is local to the validation branch.
