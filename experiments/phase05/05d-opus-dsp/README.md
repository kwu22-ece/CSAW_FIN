# Candidate 05d — Frequency-Domain Hardware Trojan (signal-processing-driven)

**CSAW 2026 Challenge 3** · Independent Candidate **D** · branch
`challenge3/05d-opus-dsp` · baseline `e72522f` · author **Claude Opus 4.8**
(all RTL, models, analysis and reports AI-generated; logs in `ai/`).

## What it is

A drop-in replacement for the recovered 63-tap Q1.15 linear-phase **low-pass**
audio FIR that hides a frequency-domain Trojan:

- **Trigger** — a *multiplier-free* Goertzel single-bin spectral detector listens
  for a secret tone at **fs/3 = 5333.33 Hz** (deep in the filter's stopband). At
  fs/3 the Goertzel coefficient is exactly −1, so detection is just adders; a
  sticky latch arms when a 576-sample window's `|s1|+|s2|` crosses 2²³.
- **Payload** — once armed, the taps become `h′[k]=(−1)ᵏ·h[k]` (odd taps negated):
  an exact **spectral inversion** that turns the low-pass into a **high-pass**, so
  the entire voice passband is attenuated ~**−60 dB**. No extra coefficient ROM.
- **Stealth** — until it hears the key, the output is **bit-for-bit identical** to
  the golden filter; the datapath, I2S timing, 2-frame latency and echo are
  untouched; the armed HPF even stays exactly linear-phase.

See `reports/figures/payload_spectral.svg` for the golden-vs-armed response.

## Results (measured)

| Check | Result |
|---|---|
| Untriggered vs golden (HDL sim, 10 cases) | **bit-identical, 0 error** |
| Near-key 5200/5467 Hz, 500 Hz probe, 15 s real audio | **no false arm** (34.9 dB margin) |
| Triggered vs Trojan model (HDL sim, 3 cases) | **bit-identical, 0 error**; arms @ sample 576 |
| Payload effect (armed) | 500 Hz passband tone **−60.8 dB**; fs/3 key **+72 dB** |
| iCE40-UP5K/SG48 build | **3704/5280 LC, 0 DSP, 0 RAM, Fmax 14.41 MHz** (≥10 MHz ✓) |
| Overhead vs golden | **+439 LC**, +0 DSP/RAM |
| On-board sw==hw | **PENDING** (no board programmed) |

## Layout

```
rtl/     fir_audio_top_trojan.v   the Trojaned FIR (synthesizable, drop-in)
         fir_audio_top.v          preserved golden baseline (for diff/equivalence)
         dut_adapter.sv           Phase-4 port adapter (phase4_dut / phase4_audio_top)
tests/   ref_trojan.py            Trojan reference model (arm + payload); --selftest
         ref_golden.py            golden reference command (harness-native)
         gen_trigger_vectors.py   directed fs/3 activation vectors -> vectors/
         trojan_untriggered.json  sim(vs golden) + FPGA build manifest
         trojan_triggered.json    sim(vs Trojan model) manifest
         baseline.json            golden-RTL sanity manifest
golden/  recovered RTL, coeffs.json, sw_fir.py, ref_fir.py, vectors, INTERFACE.md
reports/ dsp-analysis.md, verification-summary.md, verification-report.md,
         analysis/*.json+csv, figures/payload_spectral.svg, evidence/*.json
ai/      README.md, MODEL-PROVENANCE.md, decisions/, analysis/, prompts/, transcripts/
manifest.json   candidate provenance + verification manifest
```

## Reproduce

Needs OSS CAD Suite (`OSS_CAD_SUITE=C:/Users/lowbr/oss-cad-suite`) and Python 3
with numpy/scipy. From the **worktree root**:

```bash
# reference model self-test (bit-exact-off + arms on fs/3 key)
python experiments/phase05/05d-opus-dsp/tests/ref_trojan.py --selftest --coeffs experiments/phase05/05d-opus-dsp/golden/coeffs.json
# regenerate the directed activation vectors
python experiments/phase05/05d-opus-dsp/tests/gen_trigger_vectors.py
# HDL sims: untriggered (== golden) and triggered (== Trojan model)
OSS_CAD_SUITE=C:/Users/lowbr/oss-cad-suite python infrastructure/run.py sim --manifest experiments/phase05/05d-opus-dsp/tests/trojan_untriggered.json --output build/05d/rerun-untrig
OSS_CAD_SUITE=C:/Users/lowbr/oss-cad-suite python infrastructure/run.py sim --manifest experiments/phase05/05d-opus-dsp/tests/trojan_triggered.json --output build/05d/rerun-trig
# FPGA resource/timing
OSS_CAD_SUITE=C:/Users/lowbr/oss-cad-suite python infrastructure/run.py build --manifest experiments/phase05/05d-opus-dsp/tests/trojan_untriggered.json --output build/05d/rerun-build
# DSP analysis + spectral figure
python experiments/phase05/05d-opus-dsp/ai/analysis/trigger_final_proto.py
python experiments/phase05/05d-opus-dsp/ai/analysis/payload_spectral.py
```

Sim pass criterion: every case `PASSED ... max error 0`. The untriggered battery
compares the Trojaned RTL to the **golden** model (must be bit-identical); the
triggered battery compares it to the **Trojan** model (payload active).

## Design records

`ai/decisions/01-candidate-matrix.md` (research + assessment of trigger×payload
candidates), `ai/decisions/02-selected-design.md` (full spec + acceptance
criteria), `reports/dsp-analysis.md` (filter characterization),
`reports/verification-summary.md` + `reports/verification-report.md` (results).
