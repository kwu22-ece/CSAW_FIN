# Candidate matrix — DSP-driven Trojan trigger × payload (candidate 05d)

AI-authored design-exploration record (Claude Opus 4.8). All numbers are measured
by the reproducible scripts in `../analysis/` and `../../reports/analysis/*.json`
(scipy/numpy on the golden coefficients and the 15 s noisy WAV). This is the
"research multiple candidates → assess → select best-supported" step.

## Design goal

A **signal-processing-driven** hardware Trojan on the recovered 63-tap Q1.15
linear-phase FIR low-pass (fs = 16 kHz). Mandatory properties: untriggered output
**bit-identical** to golden; a **specific** activation condition (no false fire on
normal audio); a **measurable** payload; small, synthesizable on iCE40-UP5K.
Deliberately *different from* a structural/counter/control-oriented Trojan — both
the trigger and the payload live in the frequency domain.

## Trigger candidates (measured)

| Trigger | Mechanism | False-alarm (15 s real audio) | Margin | HW cost | Notes |
|---|---|---|---|---|---|
| **Goertzel single-bin (spectral)** | detect a secret key tone in the stopband | **0 / all windows** | **~35 dB** | adders only at fs/3 (see below) | acoustic delivery (play a tone); classic DSP |
| Matched-PN correlator | correlate delay line vs a secret ±1 code | 0 | 19.9 dB | reuses MAC | needs sample-exact injection (hard to deliver acoustically) |
| Accumulator-saturation | fire on int16 clamp | 0 (never clamps on real audio) | n/a | tiny | needs an adversarial full-scale crafted input; contrived |
| Counter / magic sample value | structural | — | — | tiny | explicitly out of scope (not DSP; the "control-oriented" baseline we avoid) |

**Chosen trigger: Goertzel single-bin spectral detector.** It is the most
DSP-distinctive, has the best measured specificity (0 false alarms, ~35 dB margin
over real audio), and is deliverable acoustically (an attacker simply plays the
key tone). The key frequency sits in the filter stopband so the detector input is
clean and the key itself is inaudible/masked (~−60 dB) in the normal output.

### Resource-driven refinement of the trigger (important)

A first RTL used the key at 7500 Hz with coefficient −1.9616 and an `s1²+s2²`
energy metric. That needs real multipliers; synthesized **without** DSP inference
(the shared Phase-4 `synth_ice40` runs without `-dsp`) it cost **9176/5280 LC
(173 %) — over budget** (`reports/analysis` + build log evidence). 

Fix (pure DSP, zero multipliers): choose the key at **fs/3 = 5333.33 Hz**, an
exact DFT bin (k = 192, window N = 576). At fs/3 the Goertzel coefficient
2·cos(2π/3) = **−1 exactly**, so the recurrence collapses to `s0 = x − s1 − s2`
(adders only). Use the **L1 magnitude `|s1|+|s2|`** as the window metric (abs +
add, no squares). Window 576 restores the detection margin. Result: the detector
is a handful of adders → **+439 LC total** (3704/5280), 0 DSP, timing met.
Measured margins (N = 576, threshold 2²³): threshold is **34.9 dB** above the
worst real-audio window and a full-scale key is **5.8 dB** above threshold;
adjacent full-scale tones (±130 Hz) stay **>20 dB** below threshold.

## Payload candidates (measured; all bit-exact when disarmed)

| Payload | Mechanism | Measured effect | HW cost | Measurability / stealth |
|---|---|---|---|---|
| **Spectral inversion (LPF→HPF)** | h′[k] = (−1)ᵏ·h[k] (negate odd taps) | passband **−60.5 dB**, DC 0→−61 dB, key fs/3 −72→0 dB | **0 extra ROM** (gated negate) | huge, unambiguous; stays linear-phase; same accumulator bound |
| Detuned cutoff (3.3k→2 kHz) | alternate LPF bank | −6 dB @ 2 kHz | +1 coeff ROM | subtle; needs a 2nd 63-tap bank |
| 1 kHz notch | alternate bank | −63 dB @ 1 kHz | +1 coeff ROM | stealthy/targeted; 2nd bank |
| +6 dB gain | scale bank | +6 dB | +1 coeff ROM | crude |
| LSB covert channel | modulate output LSB | −90 dBFS data channel | tiny | stealthiest but minimal effect on filtering behaviour |

**Chosen payload: spectral inversion (LPF→HPF).** Rationale: (1) maximally
measurable — the transfer function is inverted, a clean acceptance metric
(passband −60 dB); (2) the most DSP-intrinsic payload — it attacks H(z) itself;
(3) **zero extra coefficient storage** — `coef = (arm & k odd) ? −COEF[k] :
COEF[k]`, so disarmed is provably identical; (4) it preserves exact linear phase
(the negated taps are still symmetric) and the L1 accumulator bound is unchanged
(sum|h′| = sum|h| = 63248), so no new overflow/saturation. The coefficient-bank
mechanism generalises (the notch/detune banks are drop-in alternatives), but one
crisp payload is committed for rigorous verification.

## Selected combination

**Goertzel spectral trigger @ fs/3 (multiplier-free) → spectral-inversion payload.**
A frequency-domain Trojan: it *listens* for a secret tone and then makes the
filter do the *opposite* of its job, while remaining byte-identical to the golden
filter until it hears the key. See `02-selected-design.md` for the full spec.
