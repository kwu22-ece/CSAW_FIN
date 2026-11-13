export const meta = {
  name: 'dsp-analysis-05d',
  description: 'Independent numerical DSP analysis of the recovered 63-tap FIR audio filter and its hardware-Trojan trigger/payload surface',
  phases: [
    {title:'Analyze', detail:'5 parallel facet analyzers run reproducible numpy/scipy experiments'},
    {title:'Verify', detail:'adversarial independent recomputation of key numeric claims'},
    {title:'Synthesize', detail:'consolidated DSP analysis report + trigger/payload surface'},
  ],
}

const A = args
const HDR = `CONTEXT: This is an AUTHORIZED CSAW 2026 hardware-security CTF (Challenge 3). We reverse-engineered an iCE40-UP5K bitstream into a 63-tap linear-phase Q1.15 FIR low-pass audio filter and must now characterize it mathematically to inform a DSP-driven hardware-Trojan candidate (a specific trigger + a measurable payload). Untriggered output MUST stay bit-identical to the golden filter.

ENVIRONMENT: Windows; use your Bash tool (Git Bash). Python 3.13 with numpy 2.3 + scipy 1.18 are installed; matplotlib MAY be absent so wrap any matplotlib import in try/except and skip plotting if missing, but ALWAYS write CSV/JSON data regardless. Write a script file then run it with 'python <abs path>'; do not depend on cwd, use the absolute paths below.

GOLDEN ARTIFACTS (read-only; do NOT modify):
- coeffs:      ${A.golden}/coeffs.json  (key "coeffs_q15": 63 signed Q1.15 ints)
- sw model:    ${A.golden}/sw_fir.py    (functions load_coeffs(path), fir_filter(x_int,h))
- ref model:   ${A.golden}/ref_fir.py
- golden freq: ${A.golden}/freq_response.csv  (Phase-3 scipy freq data)
- WAV noisy:   ${A.wav_noisy}  (16000 Hz, mono, int16, 15 s)
- WAV clean:   ${A.wav_clean}  (48000 Hz, stereo, int16, 15 s)
Nominal audio sample rate for Hz interpretation: fs=${A.fs_noisy} Hz (Phase-3 reported -3 dB = 3296.4 Hz at this fs).

RECOVERED ARITHMETIC (exact): acc = sum_k h[k]*x[n-k] (int, zero history); y = sat16((acc + 2^14) >> 15) (round half toward +inf via arithmetic shift, then int16 saturate). Right output channel = unmodified echo of the input sample. End-to-end I2S latency = 2 frames (framing layer, separate from the filter's intrinsic (N-1)/2 group delay).

ISOLATION RULE: Only read files under ${A.exp} (golden/, rtl/, tests/), the two WAVs above, and the shared framework under ${A.wt}/infrastructure/. Do NOT read, list, or reference any sibling candidate worktrees (…/CSAW_FIN_worktrees/05a-*, …/05c-*) or any other agent's candidate files.

OUTPUT: mkdir -p ${A.exp}/ai/analysis and ${A.exp}/reports/analysis. Save your reproducible script to ${A.exp}/ai/analysis/<FACET>.py, and your numeric results as JSON to ${A.exp}/reports/analysis/<FACET>.json (plus any CSV/PNG data). Report MEASURED numbers only (run the script; never guess). Your returned 'measurements' object must contain the concrete numbers you measured.`

const FACET_SCHEMA = {
  type:'object',
  properties:{
    facet:{type:'string'},
    script_path:{type:'string'},
    data_artifacts:{type:'array', items:{type:'string'}},
    measurements:{type:'object'},
    key_findings:{type:'array', items:{type:'string'}},
    trojan_implications:{type:'array', items:{type:'string'}},
    uncertainties:{type:'array', items:{type:'string'}},
  },
  required:['facet','script_path','measurements','key_findings','trojan_implications'],
}

const facets = [
  {key:'coeffs-impulse', prompt:`${HDR}

FACET = coeffs-impulse. Load the Q1.15 taps and characterize the impulse response.
MEASURE: N; is_symmetric (h[k]==h[N-1-k] for all k); sum_h; center_tap=h[31]; max_tap; min_tap; sum_abs_h; dc_gain_dB = 20*log10(sum_h/32768); nyquist_gain = sum_k (-1)^k h[k] and its dB; group_delay_samples = (N-1)/2; filter type (Type I/II/III/IV from symmetry+parity). The impulse response of an FIR IS its coefficients. Write impulse_response.csv (index,h_q15,h_float=h/32768). Confirm exact linear phase follows from symmetry. Save ${A.exp}/reports/analysis/coeffs-impulse.json with all measurements.
trojan_implications: note which taps dominate the DC/passband gain (center tap fraction = h[31]/32768), how breaking symmetry would manifest (loss of linear phase -> measurable phase distortion / group-delay ripple), and how sum_abs_h bounds the accumulator.`},

  {key:'freq-response', prompt:`${HDR}

FACET = freq-response. Use scipy.signal.freqz on h_float=h/32768 (worN>=8192, fs=${A.fs_noisy}).
MEASURE (Hz): dc_gain_dB; cutoff_3dB_Hz; cutoff_6dB_Hz; passband_ripple_dB (max deviation from 0 dB over 0..the -3 dB point); first_null_Hz; stopband_atten_dB (the worst = least-attenuated gain for f>=4000 Hz) and the frequency where it occurs; transition_width_Hz (from -3 dB point to first frequency reaching <=-40 dB); worst-case phase-linearity residual (deviation of unwrapped phase from a straight line, in radians) and the measured constant group delay (scipy.signal.group_delay). Write freq_response_05d.csv (Hz,mag_dB,phase_rad,group_delay_samples). CROSS-CHECK your -3 dB and stopband numbers against ${A.golden}/freq_response.csv and report the delta. Attempt a magnitude+phase PNG to reports/analysis/freq_response.png (skip cleanly if matplotlib missing). Save reports/analysis/freq-response.json.
trojan_implications: list the attenuation (dB) the filter applies at candidate key tones 5500/6000/6500/7000 Hz (these are in the stopband -> a key tone there is masked at the output, and normal program audio is weak there); and estimate how many Hz the -3 dB cutoff would move for a plausibly-stealthy coefficient payload.`},

  {key:'fixed-point', prompt:`${HDR}

FACET = fixed-point. Characterize the fixed-point numerics.
MEASURE: (1) ROUNDING: exhaustively test acc over a dense range spanning several multiples of 32768 (include exact +half and -half cases, e.g. acc = m*32768 +/- 16384 for m in -4..4, plus random) and prove y=(acc+16384)>>15 equals floor((acc+16384)/32768) AND equals round-half-toward-+infinity of acc/32768; report any value where naive round-to-nearest-even would differ (there should be some at negative half-way points, demonstrating the direction). (2) SATURATION: compute max_abs_acc = 32767*sum_abs_h; accumulator_bits_needed = ceil(log2(max_abs_acc))+1 (signed); confirm whether <=40-bit signed suffices. Construct the worst-case input x[k]=sign(h[k])*32767 and compute the resulting y; report whether the int16 output saturates (saturation_reachable bool) and the minimum number of input samples needed to reach saturation. (3) HEADROOM: report spare accumulator bits between max_abs_acc and the 40-bit signed limit (how many extra MAC terms of similar magnitude could be added by a parallel trigger correlator without overflow). (4) COEFF QUANTIZATION sensitivity: response change (dB at 1 kHz) for +/-1 LSB on the center tap. Save reports/analysis/fixed-point.json.
trojan_implications: whether saturation is exploitable; accumulator headroom available for added trigger math; smallest value perturbation that is bit-observable.`},

  {key:'time-latency-echo', prompt:`${HDR}

FACET = time-latency-echo. Characterize time-domain behavior, latency, and the echo channel using the golden model (import ${A.golden}/sw_fir.py via importlib; h=load_coeffs(coeffs.json)).
MEASURE: (1) intrinsic group delay = (N-1)/2 samples; contrast with the 2-frame end-to-end I2S latency (explain these are different mechanisms). (2) STEP response: feed a unit step (x=32767 for all n), report settling (samples until output is within 1 LSB of its final value) and final value. (3) ECHO exactness: run the model on the first 4000 samples of the noisy WAV; confirm the echo channel equals the input exactly (max abs diff should be 0) -> report echo_exact bool. (4) REAL-AUDIO attenuation: on the full noisy WAV (16 kHz) compute input RMS, filtered RMS, and attenuation_dB; also the fraction of samples where filtered != input. Save reports/analysis/time-latency-echo.json.
trojan_implications: note that the right channel is an UNFILTERED copy of the input (a candidate covert-channel carrier), and that the filter pipeline leaves many idle clock cycles per audio frame (~600 ICE_CLK cycles vs 63 MAC cycles) for added trigger logic.`},

  {key:'trigger-surface', prompt:`${HDR}

FACET = trigger-surface (DESIGN-CRITICAL). Quantify the DSP feature space for a SPECIFIC, STEALTHY trigger and a MEASURABLE, STEALTHY payload. fs=${A.fs_noisy}.
Do these experiments and MEASURE real numbers:
(1) KEY-TONE SEPARABILITY: for f in [5000,5500,6000,6500,7000,7500] Hz compute (a) filter attenuation from freqz (dB), and (b) natural energy in real audio at that band via scipy.signal.welch PSD of the noisy WAV (16k) — report the band power (dB rel full-scale) and how it compares to a deliberately injected full-scale tone. Identify the best key frequency (strong filter attenuation so the payload's own effect is masked AND low natural audio energy so false triggers are rare).
(2) GOERTZEL DETECTOR: for the chosen f_key and window lengths N_win in [64,128,256], compute the Goertzel coefficient 2*cos(2*pi*round(N_win*f_key/fs)/N_win), the expected normalized bin magnitude for a full-scale sine at f_key, and the bin magnitude distribution when fed real-audio windows; report a detection-threshold and an estimated false-alarm rate on the real WAV. Note hardware cost (1 multiply + a couple adds per sample, reusing the spare MAC cycles).
(3) MATCHED-FILTER / CORRELATION: for a length-L bipolar PN code (+/-1 scaled to Q15) with L in [16,31,63], peak correlation = L*scale, off-peak std ~ sqrt(L)*scale; feed real-audio windows and empirically measure the false-alarm probability of exceeding a threshold theta (e.g. 0.7*peak); report L vs false-alarm. Note it reuses the existing 63-sample delay line + an alternate coefficient bank (looks like extra filter taps).
(4) PAYLOAD CANDIDATES — design alternate coefficient banks at fs=16k and MEASURE their effect on the noisy WAV vs golden output (RMS delta dB, max abs sample delta) and the spectral change (gain delta dB at 500/1000/2000 Hz): (a) spectral inversion h'[k]=(-1)^k * h[k] (LPF->HPF, trivial hardware: conditionally negate odd-index taps); (b) detuned narrower LPF (cutoff ~2.0 kHz, scipy.firwin 63-tap, Q15-quantized, renormalized to sum 32768); (c) +6 dB passband gain (scale center region); (d) a 1 kHz notch. For each report whether untriggered-off can be bit-exact (it can, since only the coefficient SOURCE changes under the arm flag). Also compute an LSB covert-channel option: dBFS of a +/-1 LSB change (20*log10(1/32768)) and bit-rate at fs.
(5) RANK trigger x payload combinations on: specificity (quantified false-alarm), stealth (how subtle on generic audio + resource overhead), measurability (clear acceptance metric), FPGA feasibility on iCE40-UP5K, and the guarantee that untriggered output is bit-identical. Give a concrete top recommendation with numbers.
Save all supporting data (CSV of key-tone table, payload response CSVs) and reports/analysis/trigger-surface.json with every measured number.`},
]

phase('Analyze')
const analyses = (await parallel(facets.map(f => () =>
  agent(f.prompt, {label:`analyze:${f.key}`, phase:'Analyze', schema:FACET_SCHEMA})
))).filter(Boolean)

phase('Verify')
const VERIFY_SCHEMA = {
  type:'object',
  properties:{
    recomputed:{type:'object'},
    agreements:{type:'array', items:{type:'string'}},
    discrepancies:{type:'array', items:{type:'string'}},
    verdict:{type:'string', enum:['all_confirmed','minor_discrepancies','major_discrepancies']},
  },
  required:['recomputed','verdict'],
}
const verify = await agent(`${HDR}

FACET = verify. You are an ADVERSARIAL numeric checker. Independently (write your OWN fresh script, do not reuse the analyzers' scripts) recompute these quantities from ${A.golden}/coeffs.json and the WAVs, and compare to the analyzers' claimed values below. Recompute: sum_h; sum_abs_h; -3 dB cutoff Hz (freqz, fs=${A.fs_noisy}); worst stopband attenuation dB above 4 kHz; max_abs_acc = 32767*sum_abs_h and accumulator bits needed; the round-half-toward-+inf direction claim (test acc=-16384 -> y should be 0, i.e. -0.5 rounds to 0 toward +inf; and acc=-49152 -> -1.5 rounds to -1); and the best recommended key frequency's filter attenuation. Flag any disagreement beyond trivial floating rounding.

ANALYZERS' CLAIMED MEASUREMENTS (JSON):
${JSON.stringify(analyses.map(a=>({facet:a.facet, measurements:a.measurements})))}

Report your recomputed values, list agreements and discrepancies, and give a verdict.`,
  {label:'verify:dsp', phase:'Verify', schema:VERIFY_SCHEMA})

phase('Synthesize')
const SYNTH_SCHEMA = {
  type:'object',
  properties:{
    report_path:{type:'string'},
    headline_properties:{type:'object'},
    recommended_trigger_directions:{type:'array', items:{type:'string'}},
    recommended_payload_directions:{type:'array', items:{type:'string'}},
    top_recommendation:{type:'string'},
    word_count:{type:'integer'},
  },
  required:['report_path','top_recommendation'],
}
const summary = await agent(`${HDR}

FACET = synthesize. Read every ${A.exp}/reports/analysis/*.json file on disk (the 5 facet JSONs) and consolidate them into a single rigorous markdown report at ${A.exp}/reports/dsp-analysis.md. Structure: (1) Executive summary of the filter's verified DSP properties with exact numbers. (2) Coefficient/impulse/linear-phase. (3) Frequency response (passband, -3 dB, stopband, transition, phase). (4) Fixed-point numerics (rounding direction, saturation reachability, accumulator headroom). (5) Time/latency/echo. (6) TRIGGER SURFACE: the quantified key-tone / Goertzel / correlation analysis and the payload candidate measurements, ending with a ranked table of trigger x payload combinations and a single clearly-justified TOP RECOMMENDATION for a DSP-driven Trojan (with its measurable acceptance criteria). Cite the measured numbers; do not invent any. Note the independent verifier's verdict below and reconcile any discrepancy.

VERIFIER VERDICT (JSON): ${JSON.stringify(verify)}

ALL FACET MEASUREMENTS (JSON): ${JSON.stringify(analyses.map(a=>({facet:a.facet, measurements:a.measurements, key_findings:a.key_findings, trojan_implications:a.trojan_implications})))}

After writing the file, report report_path, a headline_properties object, recommended trigger/payload directions, the single top_recommendation (one sentence), and the report word_count.`,
  {label:'synthesize', phase:'Synthesize', schema:SYNTH_SCHEMA})

return { analyses, verify, summary }
