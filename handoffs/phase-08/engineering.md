# Engineering evidence

The clean audio baseline uses the Phase 2 reconstruction at `1befb30e99a506698c45d4ca9394a3c7ec95c966` and the Phase 4 toolchain and harness at `e72522f265ac36da713cd7a0dcf8dbc64ab21209`. Both revisions are pinned in `reproduction.json`.

| Stage | Entry point or receipt |
|---|---|
| Environment and dependency validation | Phase 4 `infrastructure/run.py doctor` and `infrastructure/toolchain-lock.json` |
| Saved bitstream analysis | Phase 2 `docs/phase2-reverse-engineering-report.md` and `analysis/icebox_stat.txt` |
| Clean reconstruction | Phase 4 `infrastructure/prepare_recovered.py` snapshots the committed Phase 2 inputs and emits a run manifest |
| Regression and synthesis | Phase 4 `infrastructure/run.py validate` runs the framework tests, signed sample comparisons and constrained FPGA build |
| Repeat build | Phase 4 `infrastructure/run.py build` produces an independent clean build; Phase 8 compares both bitstreams and both round-trip results to the Phase 6 hash |
| Candidate collection and evaluation | Phase 5 `handoffs/phase-05/selection.json` at the pinned selection commit |
| Best-candidate review | `handoffs/quality-review/current-best.json` at the pinned quality-review commit |
| Prior clean build signoff | Phase 6 `handoffs/phase-06/STATUS.md` and `artifact-hashes.json` |
| Documentation and packaging | Project Scribe `record-test` and `preview`, and Phase 8 `reproduce.py --package` |

The Phase 8 clean baseline passed 15 framework tests and 8,224 exact sample comparisons. Both UP5K/SG48 builds met the 10 MHz constraint with seed 1. The first build routed at 14.016 MHz and used 3,179 of 5,280 logic cells. Both fresh builds and their pack/unpack/repack comparisons matched SHA-256 `5eba9279b177b8859ceea0bd5c685c9ac442a50414906792711626c1b2a38fda`. The initial restricted run failed four framework tests after Icarus raised access violation 3221225477. The fresh ordinary-process attempt passed and produced `clean-baseline.json`. The source bitstream analysis is historical. Physical hardware checks remain open.

Phase 5 provisionally selected 05B at `9e172a865a543b03e226596689fd6691ffa2b779`. The later quality review records `fd0ca7f6bce1d30bb1b1e6ce43603b4c7d51e5b6` as its best-known revision. Phase 8 verified both manifest blob hashes and the ancestry from the common baseline through the selection and quality revision. The Phase 6 package hash discrepancy concerned the original package. Phase 8 did not rerun candidate tests or determine whether later changes resolved that discrepancy.
