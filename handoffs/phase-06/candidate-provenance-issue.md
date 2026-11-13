# 05B package hash mismatch

- Owner — Subphase Q, candidate package provenance.
- Status — open and independently verified in Phase 6. Candidate signoff is blocked.
- Source — 05B package `9e172a865a543b03e226596689fd6691ffa2b779`, RTL origin `15a8a6525e225ad82d931b3bc75399f744638b2e`.
- Expected — all tracked sources in the package reproduce the hashes declared by its manifest and source inventory under the documented checkout convention.
- Observed — 9/35 raw blob hashes match and 23/35 additional hashes match after CRLF conversion. The manifest digest also matches after CRLF conversion. These three entries still differ.

| Manifest-relative path | Recorded SHA-256 | Raw Git blob SHA-256 |
|---|---|---|
| `rtl/fir_audio_top.v` | `2c868b30d4140f40dc5cb419bbd611d9c848aa6578d902ab509b6c4e666518e4` | `683fb8dda4c1105d2c0cf74caeefbb732890d8e5a390558c3c18dc99927f67d9` |
| `tests/BASELINE_PROVENANCE.md` | `23213b12b0c92fbab9372ede458380f570a44c517ceb7334eaad5d36619de228` | `f4aba11088ed74dc8e2aa6f33d617cf6bf2b9550e252f482ec71dd07320eec2a` |
| `tests/prepare_vectors.py` | `0214f9ae31b0e164eb163f9f5922a04581cf5e50c6b8a1abb3a0ffd081ad5443` | `b4977dad1522527c4dbe8f7f969f81cae8d80609453a49f15eb2de84ad7c0ebe` |

Read file bytes directly with `git show <SHA>:<path>` using a binary subprocess pipe, then compute SHA-256 on those bytes. For the CRLF check, replace CRLF with LF and replace LF with CRLF before hashing. The full result is retained in `build/phase06-provenance.json`. Phase 5S also recorded a user-reported boundary defect. Its reproduction status remains as recorded in the Phase 5S handoff.

Close this provenance issue with a corrected immutable inventory tied to the exact package SHA and a stated newline convention. Preserve the historical receipts for comparison.
