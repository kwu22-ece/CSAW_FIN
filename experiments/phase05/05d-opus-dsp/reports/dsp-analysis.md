# Phase 05 DSP Analysis — Recovered 63-tap Q1.15 FIR Low-Pass (candidate 05d-opus-dsp)

**Challenge:** CSAW 2026 Challenge 3 (authorized hardware-security CTF) — iCE40-UP5K bitstream reverse-engineered to a serial-MAC audio FIR.
**Scope:** Pure-DSP mathematical characterization of the golden filter and quantification of a DSP-driven hardware-Trojan surface (trigger × payload). Untriggered behavior must stay **bit-identical** to the golden filter.
**Nominal sample rate:** fs = 16000 Hz.
**Sources consolidated:** `reports/analysis/{coeffs-impulse, freq-response, fixed-point, time-latency-echo, trigger-surface}.json` + independent verifier `verify.json`. Reproducible consolidation: `ai/analysis/synthesize.py` → `reports/analysis/synthesize.json`.
**All numbers below are measured** (scipy/numpy on the golden coefficient vector and the 15 s noisy WAV) or recomputed from the golden coefficients; none are estimated.

---

## 1. Executive summary — verified DSP properties

The recovered core is a **63-tap, Type-I (odd-length, even-symmetric) linear-phase Q1.15 FIR low-pass filter** at fs = 16000 Hz. Every facet and the independent verifier agree on its defining constants; the synthesize pass re-derived them from the golden `coeffs.json` and passed **12 / 12 cross-facet consistency checks**.

| Property | Measured value | Meaning |
|---|---|---|
| Taps `N` | 63 (even order 62) | Type-I linear phase |
| Symmetry | `h[k] == h[62−k]`, 0 defects, max asymmetry 0 LSB | exact linear phase |
| Σh (Q1.15) | 32768 = 2¹⁵ | DC/passband gain = **1.0 = 0.000 dB** exactly |
| Σ\|h\| | 63248 | accumulator L1 bound |
| Center tap h[31] | 13920 (= max tap) | 42.48 % of Σh |
| Min tap | −2587 at index 28 (and 34) | largest negative side-lobe |
| −3 dB cutoff (literal) | **3296.305 Hz** | passband edge |
| −6 dB cutoff | 3399.493 Hz | |
| Worst stopband (f ≥ 4 kHz) | **−55.914 dB @ 4679.76 Hz** | least-attenuated lobe |
| Group delay | **31 samples = 1.9375 ms** | intrinsic (N−1)/2 |
| I2S transport latency | 2 frames = 2 samples = 0.125 ms | separate framing delay |
| Arithmetic | `y = sat16((Σ h[k]·x[n−k] + 2¹⁴) >> 15)` | round half toward +∞, int16 saturate |
| Accumulator | max \|acc\| ≈ 2.072×10⁹ (< 2³¹) → **32 signed bits** | fits int32; 40-bit assumed → 8 spare bits |
| Right channel | **bit-exact unfiltered echo** of the input | key covert-channel surface |

**Verifier verdict:** `minor_discrepancies` — every flagged item is definitional, not a numeric error (detailed and reconciled in §3, §4, §6). The synthesize pass independently reproduces the verifier's agreements and both of its documented notes.

**Top Trojan recommendation (measured, §6):** a **Goertzel single-bin detector at 7500 Hz (window N = 256)** as the trigger, driving a **±1 LSB covert-channel payload on the filtered (left) output**. Measured false-alarm rate = **0.0** over the 15 s corpus (937 windows), trigger margin **38.2 dB**, payload level **−90.309 dBFS** (sub-noise-floor), detector cost ≈ 1 multiply + 2 adds per sample (fits the 562 idle ICE_CLK cycles/frame), and **untriggered output remains bit-identical** because the arm flag only selects the coefficient/accumulator source.

---

## 2. Coefficients, impulse response & linear phase

- **Length / type.** `N = 63`, even order 62 → **Type-I** FIR. The impulse response equals the coefficient vector (FIR), listed in `impulse_response.csv`.
- **Symmetry (exact).** `h[k] = h[62−k]` holds for all k with **0 symmetry defects** and **max \|h[k]−h[62−k]\| = 0 LSB**. Head/tail confirm it: `h[0]=h[62]=−14`, `h[1]=h[61]=20`. The vector is symmetric, not antisymmetric.
- **Gain budget.** Σh = **32768** (exactly 1.0 in Q1.15) ⇒ DC gain **0.000 dB**. Σ\|h\| = **63248**. Decomposing by sign: Σ(h>0) = **48008**, Σ\|h<0\| = **15240**, and 48008 − 15240 = **32768 = Σh** (independent cross-check of both the gain and the L1 norm).
- **Dominant center tap.** `h[31] = 13920` is the global maximum and alone carries **42.48 %** of Σh (13920/32768 = 0.4248) and 22.01 % of Σ\|h\|. The largest negative tap is **−2587** (indices 28 & 34).
- **Nyquist.** `Σ(−1)^k h[k] = −28` (int) = −0.000854 linear = **−61.366 dB** at fs/2 = 8000 Hz — a small residual, not a true null.
- **Linear-phase proof.** Symmetry gives `H(e^{jω}) = A(ω)·e^{−jω·31}` with `A(ω)` real, so the phase is exactly `−31ω` and the **group delay is a constant 31 = (N−1)/2 samples** at every frequency (confirmed empirically in §5: the full-scale impulse peaks at index 31 with a bit-exact symmetric response, residual 0 LSB).

**Trojan leverage.** The center tap is the highest-gain-per-LSB lever but also the most conspicuous to a magnitude/`Σh` check. Any break of symmetry (`h[k] ≠ h[62−k]`) destroys the flat 31-sample group delay and is detectable by a phase/group-delay probe even when the magnitude response barely moves — so a stealthy payload must be trigger-gated, never a static coefficient edit (which `Σh ≠ 32768` or a symmetry diff would catch immediately).

---

## 3. Frequency response (passband / cutoff / stopband / transition / phase)

Measured with `scipy.signal.freqz` on `h/32768`, worN = 16384, fs = 16000, brentq root-finding.

- **Passband.** Flat-band ripple = **0.01547 dB** max deviation (**0.02768 dB** peak-to-peak) out to the passband-edge onset at **≈ 2881.84 Hz** (passband max +0.01547 dB, min −0.01222 dB). *Note:* the literal "max deviation over 0…the −3 dB point" evaluates to 2.99 dB, but that is dominated by the roll-off shoulder — it is **not** ripple; the meaningful in-band ripple is 0.0155 dB.
- **Cutoff.** **−3 dB (literal −3.0 dB) = 3296.305 Hz**; −6 dB = 3399.493 Hz. (Verifier half-power point −3.0103 dB = 3296.763 Hz, ≈ 0.46 Hz higher — the "−3 dB" label here is the literal −3.0 dB convention, consistent with Phase-3's 3296.4 Hz.)
- **First null / stopband.** First spectral null at **3855.84 Hz**. Worst-case (least-attenuated) stopband gain for f ≥ 4000 Hz = **−55.914 dB @ 4679.76 Hz**.
- **Transition.** −3 dB → −40 dB spans **488.45 Hz** (−40 dB reached at 3784.75 Hz).
- **Phase.** Deviation of the unwrapped phase from a straight line = **2.6×10⁻¹² rad** over [0, first null] and **7.1×10⁻¹⁵ rad** across the passband — linear to floating-point precision. **Group delay = 31.0 samples**, std ≈ 1.1×10⁻¹⁴ (i.e. 0), and the fitted phase slope implies 31.000 samples.

**Cross-checks / reconciliation.** Against the golden Phase-3 `freq_response.csv` (coarse 15.625 Hz grid): −3 dB agrees to **0.05 Hz** (3296.305 vs golden-interp 3296.25 vs Phase-3 3296.4) and worst stopband to **0.029 dB** (−55.914 @ 4680 vs golden −55.943 @ 4673). These sub-tolerance deltas are pure CSV-grid interpolation noise (worN 512 vs 16384) — the verifier reached the same conclusion. The DSP path itself reproduces the golden magnitude to **8.38×10⁻⁷** absolute error (§4).

---

## 4. Fixed-point numerics (rounding, saturation, headroom)

**Arithmetic (recovered, exact):** `acc = Σ_k h[k]·x[n−k]` (int, zero history); `y = sat16((acc + 2¹⁴) >> 15)` — round half toward +∞ via arithmetic shift, then int16 saturate.

### Rounding direction — proven
Over **567,715** accumulator values (dense [−163840, +163840] + explicit m·32768 ± 16384 + 240k random spanning the full ±2.07×10⁹ range), the hardware form `(acc+16384)>>15` equals `floor((acc+16384)/32768)` equals `round-half-toward-+∞(acc/32768)` with **0 mismatches** (the round-half-up reference was computed independently via exact `Fraction`, so this is a real cross-check, not a tautology). The verifier's independent 400k-value sweep likewise found **0 mismatches**.

The rule differs from round-half-to-**even** exactly at the exact-half points `acc mod 65536 == 16384`, where the hardware is always **+1 above** round-half-even — a deterministic positive bias on negative exact-halves:

| acc | acc/D | hardware (toward +∞) | round-half-even |
|---|---|---|---|
| −114688 | −3.5 | **−3** | −4 |
| −49152 | −1.5 | **−1** | −2 |
| +16384 | +0.5 | **+1** | 0 |

### Accumulator width & the one documented facet discrepancy
Three self-consistent definitions of the worst-case magnitude exist; the synthesize pass recomputed all three from the coefficients:

| Definition | Value | Basis |
|---|---|---|
| Task formula / fixed-point | **2,072,447,216** | 32767 × Σ\|h\| |
| True asymmetric worst case | **2,072,495,224** | 32767·Σ\|h\| + max(Σpos, Σ\|neg\|) = +48008 for the negative input extreme |
| coeffs-impulse (safe over-estimate) | **2,072,510,464** | 32768 × Σ\|h\| using \|min int16\| = 32768 |

All three are ≈ 2³⁰·⁹⁵ and all three are **< 2³¹ = 2,147,483,648**, so the accumulator needs **exactly 32 signed bits** regardless of convention. This is the sole "discrepancy" the verifier flagged (`minor_discrepancies`): it is **purely definitional** — a spread of 63,248 LSB (≈ 3×10⁻⁵ relative) — with **no engineering impact**. A 40-bit signed accumulator (as assumed by the core) leaves **8 spare bits** (spare magnitude 5.48×10¹¹), room for ≈ **510** extra full-scale Q15×Q15 MAC terms or **264** additional 63-tap worst-case FIRs.

### Saturation — reachable only adversarially
Clamp thresholds (recomputed, exactly matching the fixed-point facet): **positive clamp when acc ≥ 1,073,725,440; negative clamp when acc ≤ −1,073,758,209.** Saturation **is reachable** with the adversarial full-scale pattern `x[k] = sign(h[k])·32767`: this drives acc to the peak 2,072,447,216 at output n = 62 (unclamped y = 63246 → clamped 32767). The earliest output index that can clamp is **n = 31** — exactly when the large center tap enters the window — and a minimum of **32 input samples** is required. On the **real 15 s noisy WAV the peak \|acc\| is only 975,867,864** (well under the 1.07×10⁹ threshold) ⇒ **0 saturations**. Ordinary audio never approaches the clamp, which makes the saturation/near-saturation state a clean, rare, attacker-forceable condition.

### Sensitivity floor
A ±1 LSB change on the center tap shifts the 1 kHz magnitude by only **±2.651×10⁻⁴ dB** (nominal \|H(1k)\| = 0.99996) and DC gain by +2.651×10⁻⁴ dB; the DSP model reproduces the golden CSV to **8.38×10⁻⁷** absolute magnitude error. The smallest output-observable perturbation is **1 accumulator LSB**, which flips `y` by 1 exactly when `acc ≡ 16384 (mod 32768)` (a rounding boundary); one Q1.15 coefficient LSB (3.052×10⁻⁵) can perturb acc by up to ±32767, so it is output-observable at boundary inputs despite a sub-millidB spectral footprint.

---

## 5. Time domain, latency & echo channel

- **Group delay vs. latency are different mechanisms.** The **31-sample group delay** (1.9375 ms) is intrinsic to the symmetric FIR (energy centroid at the center tap), carried inside the sample values; it is verified empirically (impulse peak at index 31, symmetry residual 0 LSB). The **2-frame I2S latency** (2 samples = 0.125 ms) is a separate framing/pipeline transport delay applied equally to **both** the filtered and echo channels, independent of the filter arithmetic.
- **Step response** (x[n] = 32767): final value 32767 (DC gain 1.0), **settles to within 1 LSB at n = 61** (identical to exact settle), fully filled at n = N−1 = 62. The transient rings (undershoots ~114 LSB below final near n = 50) because of the windowed-sinc negative side-lobes.
- **Echo channel is bit-exact.** Over the first 4000 noisy-WAV samples the modeled right channel equals the input with **max abs diff = 0** (`echo_exact = True`), while the filtered left channel differs on **100 %** of samples — the echo path applies no filtering.
- **Real audio (full 15 s / 240000-sample noisy WAV).** Input RMS 2832.07 → filtered RMS 2577.61 ⇒ **−0.8177 dB** attenuation; peak 32440 → 29781; **99.98 %** of samples modified (239961/240000); **0** output saturations. The modest −0.82 dB indicates most energy is in-band while the LPF trims high-frequency noise.
- **Idle-cycle budget.** At ICE_CLK ≈ 10 MHz and a 16 kHz frame rate there are **625** ICE_CLK cycles per audio frame; the serial MAC uses only **63**, leaving **562 idle cycles/frame (89.92 %)** for added trigger logic with no impact on the audio datapath. (The facet further notes a place-and-route Fmax of 14.49 MHz > 10 MHz, i.e. timing headroom for extra logic.)

---

## 6. Trigger surface & payload candidates (the Trojan design space)

All numbers measured by `ai/analysis/trigger-surface.py` on the golden filter and the 15 s noisy WAV (240000 samples, mono, 16 kHz).

### 6.1 Key-tone separability — where to put the trigger carrier
Every candidate stopband tone is attenuated ≈ −60 dB by the filter, so the discriminator is **how little natural audio energy** sits in that band (a Welch estimate over the real WAV). The **separability score** = filter attenuation + the tone's margin over natural band power (full-scale tone referenced to 0 dBFS, ±250 Hz band).

| Key (Hz) | Filter atten (dB) | Natural band power (dBFS) | Tone margin (dB) | Separability score |
|---|---|---|---|---|
| 5000 | −60.096 | −37.017 | 37.017 | 97.113 |
| 5500 | −60.196 | −38.002 | 38.002 | 98.198 |
| 6000 | −60.396 | **−29.285** | 29.285 | 89.681 |
| 6500 | −59.827 | −38.741 | 38.741 | 98.568 |
| 7000 | −60.658 | −39.214 | 39.214 | 99.873 |
| **7500** | **−60.718** | **−39.573** | **39.573** | **100.291** |

**Best carrier = 7500 Hz** (deepest attenuation **−60.718 dB**, least in-band audio energy **−39.573 dBFS**). 6000 Hz is the worst choice despite good attenuation because real audio carries much more energy there (−29.285 dBFS).

**Reconciliation with the verifier.** The verifier reported the best key as **7000 Hz (−60.658 dB)** — but it ranked only the subset {5500, 6000, 6500, 7000} by *deepest attenuation alone*. The trigger-surface facet ranks the fuller set {5000…7500} by the combined *separability* metric. These are **not in conflict**: on the common subset both place 7000 Hz above 6000/6500 Hz; 7500 Hz (absent from the verifier's set) is marginally deeper **and** the cleanest band, so it wins. 7000 Hz is an essentially-equivalent runner-up (score 99.873 vs 100.291); either is an excellent carrier. The payload is masked ≈ 60 dB at the filtered **left** output, but the carrier survives at full amplitude on the **bit-exact right echo channel** — so a trigger detector must tap the input/echo path, not the filtered output.

### 6.2 Goertzel single-bin detector @ 7500 Hz
7500 Hz lands exactly on a DFT bin for power-of-two windows (no scalloping): k = 30/60/120 for N = 64/128/256, `actual_bin_hz = 7500.0`, Goertzel coefficient `2cos = −1.961571`. A full-scale tone gives normalized magnitude **1.0**; cost is **1 real multiply + 2 adds per input sample** (easily inside the 562 idle cycles/frame).

| N_win | k_bin | real-audio max mag | threshold | false-alarm rate | tone→audio-max margin |
|---|---|---|---|---|---|
| 64 | 30 | 0.030595 | 0.5 | **0.0** | 30.287 dB |
| 128 | 60 | 0.018521 | 0.5 | **0.0** | 34.647 dB |
| **256** | 120 | **0.012286** | 0.5 | **0.0** | **38.212 dB** |

Longer windows integrate more → cleaner separation; **N = 256 gives 0 false alarms over 937 windows with a 38.2 dB margin.**

### 6.3 Matched-filter / PN-correlation detector (alternative trigger)
A length-L ±1 PN code correlated against the input, normalized so the aligned peak = 1.0, threshold θ = 0.7. Reuses the existing 63-sample delay line (the PN code looks like an alternate tap bank).

| L | empirical off-peak σ | max \|corr\| (real audio) | false-alarm rate | peak→audio margin |
|---|---|---|---|---|
| 16 | 0.012157 | 0.116632 | **0.0** | 18.664 dB |
| 31 | 0.017817 | 0.186999 | **0.0** | 14.563 dB |
| **63** | 0.008872 | 0.100921 | **0.0** | **19.92 dB** |

Zero false alarms at all lengths; L = 63 gives the best margin (19.9 dB) but a smaller margin than the Goertzel trigger and needs a full MAC pass over the delay line per window.

### 6.4 Payload candidate coefficient banks (triggered behavior)
Each bank is a drop-in alternate coefficient set; the arm flag selects the coefficient **source**, so the **untriggered path stays bit-identical** (golden ROM bank). Deltas measured against the golden output on the noisy WAV.

| Payload | DC gain | RMS Δ (dBFS) | max \|Δ\| (LSB) | key gain Δ | character |
|---|---|---|---|---|---|
| spectral_inversion_hpf | −0.000854 | −18.435 | 30090 | −60.658 dB @ 1 kHz (LPF→HPF) | loud, unambiguous PoC |
| gain_plus6db | 2.0 | −19.237 | 16375 | +6.021 dB all freqs | obvious level shift |
| notch_1k | 1.0 | −27.771 | 16843 | −63.063 dB @ 1 kHz | surgical notch |
| narrow_lpf_2k | 1.0 | −33.851 | 8937 | −6.013 dB @ 2 kHz | subtle timbre detune |
| **LSB covert channel** | 1.0 | **−90.309 (±1 LSB)** | 1 | — | sub-noise-floor data exfil, ≤16000 bps (62.5 bps @ 1 bit/256-frame) |

### 6.5 Ranked trigger × payload combinations

| Rank | Trigger | Payload | False-alarm rate | Trigger margin | Payload measurability | Untriggered |
|---|---|---|---|---|---|---|
| **1** | Goertzel @ 7500 Hz, N=256 | ±1 LSB left-channel covert channel | **0.0** | 38.212 dB | left-LSB bitstream, ≤16000 bps, clean BER metric | **bit-exact** |
| 2 | Goertzel @ 7500 Hz, N=256 | spectral_inversion_hpf (LPF→HPF) | 0.0 | 38.212 dB | −60.7 dB gain flip at probe freqs; RMS Δ −18.435 dBFS | bit-exact |
| 3 | Matched PN, L=63 | narrow_lpf_2k (cutoff → 2 kHz) | 0.0 | 19.92 dB | −6.013 dB @ 2 kHz; RMS Δ −33.851 dBFS | bit-exact |

### 6.6 TOP RECOMMENDATION

> **Trigger:** Goertzel single-bin detector at **7500 Hz** with window **N = 256** (tapping the input / right-echo path).
> **Payload:** a **±1 LSB covert channel on the filtered left output** (arm flag switches the coefficient/accumulator source only).

**Why this one.** It is the measured optimum on every axis: **lowest false-alarm rate (0.0** over 937 real-audio windows), **largest trigger margin (38.2 dB** between the full-scale-tone magnitude 1.0 and the real-audio max 0.012286), the carrier sits deepest in the stopband (**−60.718 dB**) and in the quietest natural band (**−39.573 dBFS**) so the detector input is clean and the tone is masked ~60 dB at the audible output, the detector is **≈ 1 multiply + 2 adds per sample** (fits the 562 idle ICE_CLK cycles/frame, 89.92 % slack; Fmax headroom confirmed), and the payload at **−90.309 dBFS** sits below the 16-bit noise floor (inaudible on speech/music) yet is **exactly decodable as a bit stream**. Crucially, **untriggered output is bit-identical to the golden filter**, satisfying the hard constraint.

**Measurable acceptance criteria.**
1. **Untriggered equivalence:** with the arm flag deasserted, the left channel is **bit-identical** to golden `sw_fir` over the full 15 s noisy WAV (0 differing samples) and over the adversarial worst-case saturation vector; the right channel stays a bit-exact echo (max \|Δ\| = 0).
2. **Trigger specificity:** **0 false alarms** on the 15 s real-audio corpus at Goertzel threshold 0.5 (measured real-audio max magnitude 0.012286 ≪ 0.5; k_bin = 120, N = 256).
3. **Trigger sensitivity:** a full-scale 7500 Hz tone yields normalized Goertzel magnitude ≈ 1.0 ≥ 0.5, asserting within one window (256 samples = 16 ms).
4. **Payload measurability:** when armed, the left-channel LSB sequence decodes the injected bit stream with BER ≈ 0 at the chosen rate (≤ 16000 bps; 62.5 bps at 1 bit / 256-frame block), with per-sample perturbation ≤ 1 LSB (−90.309 dBFS), below the audible/spectral noise floor.

*(If a visibly dramatic proof-of-concept is preferred over stealth, Rank 2 — same Goertzel trigger with the spectral_inversion_hpf payload — flips the LPF to an HPF, a −60.7 dB gain change at the probe frequencies, while keeping the untriggered path bit-exact.)*

---

### Appendix — provenance & verification
- Golden coefficients independently re-summed: Σh = 32768, Σ\|h\| = 63248, Σpos = 48008, Σ\|neg\| = 15240 (48008 − 15240 = 32768 ✓).
- Cross-facet consistency: **12 / 12 checks pass** (`synthesize.json`), covering Σh, Σ\|h\|, N, center tap, group delay, −3 dB cutoff, worst stopband, accumulator width, rounding direction, saturation thresholds, key-tone attenuation, and the real-audio crosscheck.
- Independent verifier verdict: `minor_discrepancies`; all flagged items (accumulator-magnitude convention §4; "−3 dB" = literal vs half-power §3; golden-CSV grid deltas §3; best-key subset vs separability §6.1) are definitional and reconciled above with no change to any engineering conclusion.
- Scripts: `ai/analysis/{coeffs-impulse, freq-response, fixed-point, time-latency-echo, trigger-surface, synthesize}.py`. Data: `reports/analysis/*.json`, `*.csv`.
