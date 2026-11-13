export const meta = {
  name: 'verify-05d-trojan',
  description: 'Independent hardware-equivalence verification of the candidate-05d Trojaned FIR (CSAW CTF): confirm bit-exact inactive behavior, trigger specificity, and payload numerics',
  phases: [{title:'Verify', detail:'3 independent re-derivations from scratch'}, {title:'Report', detail:'consolidated verification verdict'}],
}
const A = args
const HDR = `CONTEXT: This is VALIDATION work for an authorized CSAW 2026 Challenge 3 CTF. A recovered 63-tap Q1.15 FIR low-pass audio filter (golden) has an AI-generated controlled modification (candidate 05d). Your job is standard hardware-equivalence verification: independently confirm, from scratch, that (a) when inactive the modified design is bit-identical to the golden filter, (b) the activation condition is specific and does not fire on normal audio, and (c) the active behavior matches its documented reference model and is numerically safe. This is defensive verification/validation, not exploitation.

ENVIRONMENT: Windows; use your Bash tool (Git Bash). Python 3.13 + numpy + scipy available. Write your verification script to ${A.exp}/ai/analysis/<KEY>.py and results JSON to ${A.exp}/reports/analysis/<KEY>.json, run it, and report MEASURED numbers (never guess). Work INDEPENDENTLY: write your own fresh code; do not merely re-run the author's scripts.

GOLDEN + DESIGN ARTIFACTS (read-only):
- golden FIR model:   ${A.golden}/sw_fir.py  (load_coeffs(path), fir_filter(x_int,h))
- golden coeffs:      ${A.golden}/coeffs.json  (63 Q1.15 ints; symmetric, sum=32768)
- Trojaned RTL:       ${A.rtl}/fir_audio_top_trojan.v
- baseline golden RTL:${A.rtl}/fir_audio_top.v
- Trojan ref model:   ${A.tests}/ref_trojan.py   (importable: run_trojan(x,h)->(y,armed); golden_fir(x,h))
- golden ref cmd:     ${A.tests}/ref_golden.py
- real audio (16 kHz mono int16): ${A.wav_noisy}

DOCUMENTED DESIGN (verify these, do not assume correct):
- TRIGGER: multiplier-free Goertzel at fs/3 = 5333.33 Hz (bin k=192, window N=576, coeff exactly -1 so s0=x-s1-s2); arm when window L1 |s1|+|s2| >= 2^23 (8388608); sticky latch.
- PAYLOAD: while armed, taps become h'[k]=(-1)^k h[k] (odd-index negated) -> spectral inversion (low-pass becomes high-pass). Disarmed uses golden h[k].
- CLAIM: inactive output bit-identical to golden; arm never fires on real audio (~35 dB margin); armed passband attenuated ~-60 dB.

ISOLATION: read only under ${A.exp}, the golden RTL/model, and the WAV above. Do NOT read sibling candidate worktrees (…/CSAW_FIN_worktrees/05a-*, 05c-*).`

const VSCHEMA = {
  type:'object',
  properties:{
    claim:{type:'string'}, method:{type:'string'}, script_path:{type:'string'},
    measurements:{type:'object'}, confirmed:{type:'boolean'},
    discrepancies:{type:'array', items:{type:'string'}},
    residual_risks:{type:'array', items:{type:'string'}},
  },
  required:['claim','confirmed','measurements'],
}

phase('Verify')
const checks = [
  {key:'verify_equivalence', prompt:`${HDR}

CLAIM TO VERIFY (KEY=verify_equivalence): "When inactive, the modified design is bit-identical to the golden filter for ALL inputs."
Do BOTH:
(1) STRUCTURAL: textually diff ${A.rtl}/fir_audio_top_trojan.v against ${A.rtl}/fir_audio_top.v. Confirm that every behavioral difference is gated by the arm signal (arm_mac): specifically that the MAC coefficient reduces to the unmodified COEF[k] when arm_mac==0, the delay line / accumulate / round-saturate / I2S serializer / echo path are unchanged, and the added Goertzel block writes ONLY the internal arm latch (no datapath/output signal). List every diff hunk and classify it as 'gated-by-arm' or 'UNGATED (risk)'.
(2) EMPIRICAL: import ${A.tests}/ref_trojan.py. Generate a broad fresh corpus WITHOUT the fs/3 key tone: >=20 random int16 streams (distinct seeds, lengths 2000-8000), the full real WAV, plus sine sweeps 100-8000 Hz EXCLUDING a +/-150 Hz band around 5333.33 Hz, and silence/impulse/step/full-scale-edges. For each, assert run_trojan(x,h) filtered output == golden_fir(x,h) exactly AND armed_at is all zero. Report total samples compared, mismatches (must be 0), and any window that armed (must be none).
confirmed = (structural: all diffs gated) AND (empirical: 0 mismatches AND 0 arms).`},

  {key:'verify_trigger', prompt:`${HDR}

CLAIM TO VERIFY (KEY=verify_trigger): "The activation metric is specific: a genuine fs/3 key tone arms it, but no normal audio and no nearby tone does."
Implement the detector FROM SCRATCH yourself (s1=s2=0; per sample s0=x-s1-s2; s2,s1=s1,s0; every 576 samples L1=|s1|+|s2|, compare to 2^23, reset) — do not import ref_trojan. Then measure max window L1 for: the fs/3 key tone at amplitudes {32767,26214,16384,8192}; pure tones swept 200..7800 Hz in 100 Hz steps at full scale; the full real WAV (all windows); white noise (several seeds); a 3-tone musical chord; a linear chirp 100->7900 Hz. Report: does the full-scale key arm? lowest key amplitude that arms? does ANY non-(fs/3) case arm (list any)? the dB margin between the 2^23 threshold and the worst real-audio window, and between a full-scale key and the threshold. Also report how far (in Hz) a full-scale tone must be from 5333.33 Hz before it stops arming.
confirmed = full-scale key arms AND no real-audio/noise/chord/chirp window arms AND only tones within a narrow band of fs/3 arm.`},

  {key:'verify_payload', prompt:`${HDR}

CLAIM TO VERIFY (KEY=verify_payload): "The armed payload is an exact spectral inversion that stays numerically safe." Independently (scipy):
(1) Build h'[k]=(-1)^k h[k]. Via scipy.signal.freqz confirm: armed DC gain, armed Nyquist gain, and armed magnitude at 250/500/1000/2000/3000 Hz vs golden (expect passband dropping ~-60 dB); confirm the armed response equals the golden response shifted by fs/2 (spectral inversion identity) to within float error.
(2) Confirm h' is still symmetric (=> armed filter is still exactly linear phase); report group delay for both.
(3) NUMERICS: confirm sum|h'| == sum|h| (so the 40-bit accumulator bound and int16-saturation behavior are unchanged when armed); compute worst-case |acc| for h' and confirm it still fits the 40-bit signed accumulator; search for any input that saturates differently under h' vs h in a way that could corrupt the DISARMED path (should be none, since saturation only applies to armed outputs).
confirmed = exact spectral inversion AND linear phase preserved AND accumulator/saturation bound unchanged.`},
]
const results = (await parallel(checks.map(c => () =>
  agent(c.prompt, {label:c.key, phase:'Verify', schema:VSCHEMA})
))).filter(Boolean)

phase('Report')
const RSCHEMA = {type:'object', properties:{
  report_path:{type:'string'}, overall_verdict:{type:'string', enum:['all_confirmed','confirmed_with_notes','issues_found']},
  confirmed_claims:{type:'array', items:{type:'string'}}, open_issues:{type:'array', items:{type:'string'}},
}, required:['report_path','overall_verdict']}
const report = await agent(`${HDR}

KEY=report. Consolidate the three independent verification results (JSON below) into ${A.exp}/reports/verification-report.md: a concise hardware-verification report with (1) a summary table of each claim and its CONFIRMED/ISSUE status with the measured numbers, (2) the structural-equivalence finding, (3) the trigger-specificity numbers (margins, selectivity bandwidth), (4) the payload/numerics findings, (5) any residual risks or items marked pending (e.g. physical-hardware tests not run), and (6) an overall verdict. Cite measured numbers only.

VERIFICATION RESULTS (JSON): ${JSON.stringify(results)}

Return report_path, overall_verdict, the confirmed_claims list, and any open_issues.`,
  {label:'report', phase:'Report', schema:RSCHEMA})

return { results, report }
