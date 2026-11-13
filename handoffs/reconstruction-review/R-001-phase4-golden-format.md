# R-001 — Phase 3 golden reference: values validated, but index convention still fails Phase 4

- **Source commits:** found at Phase 2 `1befb30` / Phase 4 `2da1d72`; **re-checked
  against Phase 3 `challenge3/03-baseline` 5dedf4c** (committed after this review began).
- **Severity:** medium — blocks automated Phase 4 ingestion; trivial fix.
- **Owner to integrate:** Phase 3.
- **Confidence:** very high (ran Phase 4's own reader + an independent value cross-check).

## History / current state
- **Original (at 1befb30):** no `phase4_dut` adapter and the only reference CSV
  (`handoffs/phase-02/reference_vectors.csv`, header `n,x_in_int16,y_filtered_int16`)
  was unreadable by Phase 4 and lacked the echo channel.
- **Phase 3 `5dedf4c` has since addressed most of this** (`handoffs/phase-03/`):
  `phase4_dut.v` adapter ✓, `run_reference.py` ✓, `reference_io.csv` with an
  `index,channel,value` header and correct channel semantics (0=filtered, 1=echo) ✓,
  `INTERFACE.md` + SG48 `.pcf` ✓.
- **Independent value check — PASS.** Phase 3's golden filtered and echo values
  match this reviewer's independent fixed-point model **bit-for-bit (254/254 each)**
  once the 2-frame latency baked into the stream is accounted for
  (`Phase3[n] == model[n−2]`). Phase 3's golden is numerically correct.

## Residual defect (still blocks Phase 4)
Phase 3's `reference_io.csv` puts a **frame index** in the `index` column,
duplicated across the two channels: `0,0 / 0,1 / 1,0 / 1,1 / 2,0 …`. Phase 4's
`infrastructure/results.py::read_samples()` requires the `index` column to equal
the **per-row (word) index** `0,1,2,3,…`:
```python
for n, row in enumerate(reader):
    if item['index'] != n or item['channel'] not in (0,1):
        raise ValueError('nonsequential index or invalid channel at %d' % n)
```
So Phase 4 rejects the file at the 2nd row.

## Decisive reproduction
```bash
git show origin/challenge3/03-baseline:handoffs/phase-03/reference_io.in.csv > p3_in.csv
git show origin/challenge3/03-baseline:handoffs/phase-03/reference_io.csv    > p3_io.csv
python review/scripts/rv_phase3_golden_check.py p3_in.csv p3_io.csv recovered/coeffs.json \
    ../phase-04/infrastructure/results.py
```
Result (log `review/logs/rv_phase3_golden_check.log`):
```
(A) best shift=2: filtered 254/254, echo 254/254  (values CORRECT; latency baked in)
(B) REJECTED: ValueError - nonsequential index or invalid channel at 1
    first 6 index values: [0, 0, 1, 1, 2, 2]  (Phase4 requires 0,1,2,3,4,5)
```

## Proposed correction (trivial; pattern already provided)
Emit the `index` column as the **running row/word index**, not the frame index:
```
index,channel,value
0,0,<filtered[0]>
1,1,<echo[0]>
2,0,<filtered[1]>
3,1,<echo[1]>
...
```
i.e. for audio frame n write rows `(2n,0,filtered[n])` and `(2n+1,1,echo[n])`.
`review/scripts/rv_make_phase4_golden.py` already does exactly this and its output
passes Phase 4 `read_samples()`/`compare()` (see `handoffs/reconstruction-review/phase4-golden/`).
Point `run_reference.py`'s writer at the running counter and the file will ingest.

## Latency note
Phase 3 bakes the 2-frame latency into the stream (output[0..1]=startup zeros),
so compare with **`latency_words = 0`** against a same-latency actual capture.
(A latency-*aligned* golden like this reviewer's `phase4-golden/golden_output.csv`
instead uses `latency_words = 4` = 2 frames × 2 channels.) Pick one convention and
keep expected and actual consistent.

## Regression status
Additive review artifacts only; no Phase 2/3/4 files modified. The checks import
Phase 4's `results.py` read-only.
