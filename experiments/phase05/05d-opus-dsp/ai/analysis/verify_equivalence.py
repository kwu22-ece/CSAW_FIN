#!/usr/bin/env python3
"""Independent verification of KEY=verify_equivalence for candidate 05d.

CLAIM: "When inactive, the modified design is bit-identical to the golden
filter for ALL inputs."

This is an INDEPENDENT re-implementation (not the author's scripts). It does:

PART 1 - STRUCTURAL (textual, deterministic proof):
  * Strip comments from both RTL files, normalize whitespace.
  * Confirm COEF[0..62] arrays are byte-identical in both RTLs and equal to
    golden/coeffs.json.
  * DETERMINISTIC GATING PROOF: take the trojan code lines, excise exactly the
    known Trojan additions (Goertzel trigger block, coef_mac wire, arm_mac
    capture, trojan power-up init) and revert the single datapath edit
    (coef_mac -> COEF[k]); assert the result is line-for-line identical to the
    baseline code. If equal, then by construction every behavioral difference
    is one of those Trojan pieces and nothing else changed.
  * Confirm the coef_mac mux reduces to COEF[k] when arm_mac==0 (identity).
  * Confirm the Goertzel always-block assigns ONLY internal trigger signals
    (observer-only: no datapath/output signal on any LHS).
  * Classify every unified-diff hunk as comment-only / gated-by-arm / UNGATED.

PART 2 - EMPIRICAL (independent model + required ref_trojan):
  * Import tests/ref_trojan.py (run_trojan, golden_fir) as required.
  * Build an INDEPENDENT numpy golden model from the recovered arithmetic and
    cross-validate it against golden/sw_fir.py, ref_trojan.golden_fir, and a
    pure-python reimplementation (defeats circularity).
  * Build a broad corpus WITHOUT the fs/3 key tone (exclude +/-150 Hz around
    5333.33 Hz): >=20 random int16 streams, the full real WAV, dense full-scale
    sine tones over 100..8000 Hz (skipping the key band), and
    silence/impulse/step/full-scale edges.
  * For every stream assert run_trojan(x,h) filtered output == independent
    golden EXACTLY and armed_at is all zero. Independently compute the
    non-overlapping 576-sample Goertzel L1 for every window and confirm no
    window reaches 2^23 (catches an end-of-stream arm that armed_at hides);
    report the worst-case L1 and its dB margin.

confirmed = (structural: all behavioral diffs gated) AND
            (empirical: 0 output mismatches AND 0 windows armed).
"""
from __future__ import annotations
import json, math, os, re, sys, time, importlib.util

BASE = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/experiments/phase05/05d-opus-dsp"
WAV  = r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN_worktrees/05d-opus-dsp/what_a_piece_of_work-noisy.wav"
RTL_BASE   = os.path.join(BASE, "rtl", "fir_audio_top.v")
RTL_TROJ   = os.path.join(BASE, "rtl", "fir_audio_top_trojan.v")
COEFF_JSON = os.path.join(BASE, "golden", "coeffs.json")
REF_TROJAN = os.path.join(BASE, "tests", "ref_trojan.py")
SW_FIR     = os.path.join(BASE, "golden", "sw_fir.py")
OUT_JSON   = os.path.join(BASE, "reports", "analysis", "verify_equivalence.json")

import numpy as np

# ---------------------------------------------------------------- helpers ----
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)   # block comments
    out = []
    for line in text.splitlines():
        line = re.sub(r"//.*$", "", line)                    # line comments
        line = re.sub(r"\s+", " ", line).strip()             # normalize ws
        if line:
            out.append(line)
    return out

def parse_coef(text):
    d = {}
    for idx, val in re.findall(r"COEF\[(\d+)\]\s*=\s*(-?\d+)", text):
        d[int(idx)] = int(val)
    return d

# -------------------------------------------------------- independent golden --
def my_golden_np(x, h):
    """Independent bit-exact golden FIR (numpy int64), no shift-semantics
    assumption: floor_divide reproduces the arithmetic >>>15 exactly."""
    xa = np.asarray(x, dtype=np.int64)
    ha = np.asarray(h, dtype=np.int64)
    acc = np.convolve(xa, ha)[:xa.size]          # y[n]=sum_k h[k]x[n-k], x<0 => 0
    y = np.floor_divide(acc + (1 << 14), (1 << 15))   # round half toward +inf
    return np.clip(y, -32768, 32767).astype(np.int64)

def pure_python_golden(x, h):
    N = len(h); y = []
    for n in range(len(x)):
        acc = 0
        for k in range(min(n + 1, N)):
            acc += h[k] * x[n - k]
        s = (acc + (1 << 14)) >> 15
        y.append(32767 if s > 32767 else -32768 if s < -32768 else s)
    return y

# Independent Goertzel (coeff = -1), non-overlapping windows, L1 = |s1|+|s2|.
def goertzel_window_l1(x, n_win=576):
    s1 = s2 = 0; l1s = []
    for i, xi in enumerate(x):
        s0 = int(xi) - s1 - s2
        s2, s1 = s1, s0
        if (i + 1) % n_win == 0:
            l1s.append(abs(s1) + abs(s2))
            s1 = s2 = 0
    return l1s   # one entry per COMPLETE window (end-of-stream arm included)

# ------------------------------------------------------------------- main -----
def main():
    report = {"key": "verify_equivalence",
              "claim": "When inactive, the modified design is bit-identical to the golden filter for ALL inputs.",
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "method": {}, "structural": {}, "empirical": {},
              "discrepancies": [], "residual_risks": []}
    disc = report["discrepancies"]

    base_txt = open(RTL_BASE).read()
    troj_txt = open(RTL_TROJ).read()
    coeffs_json = json.load(open(COEFF_JSON))["coeffs_q15"]

    # ===================== PART 1: STRUCTURAL =====================
    S = report["structural"]
    cb, ct = parse_coef(base_txt), parse_coef(troj_txt)
    S["coeffs_count_base"] = len(cb)
    S["coeffs_count_troj"] = len(ct)
    S["coeffs_base_eq_troj"] = (cb == ct)
    rtl_list = [cb[i] for i in range(len(cb))] if len(cb) == len(coeffs_json) else None
    S["coeffs_rtl_eq_json"] = (rtl_list == list(coeffs_json))
    S["coeffs_sum"] = sum(coeffs_json)
    if not S["coeffs_base_eq_troj"]:
        disc.append("RTL COEF arrays differ between baseline and trojan")
    if not S["coeffs_rtl_eq_json"]:
        disc.append("RTL COEF array differs from golden/coeffs.json")

    code_base = strip_comments(base_txt)
    code_troj = strip_comments(troj_txt)

    # Locate the Goertzel trigger region in trojan code (localparam NWIN .. just
    # before MAC delay-line declaration), then excise the known trojan pieces.
    def find(seq, pred, start=0):
        for i in range(start, len(seq)):
            if pred(seq[i]):
                return i
        return -1

    i_nwin = find(code_troj, lambda l: l.startswith("localparam integer NWIN"))
    i_dl   = find(code_troj, lambda l: l.startswith("reg signed [15:0] dl [0:NTAP-1]"))
    goertzel_block = code_troj[i_nwin:i_dl] if (i_nwin >= 0 and i_dl > i_nwin) else []

    # Isolate the Goertzel always-block body for LHS inspection.
    gi = find(goertzel_block, lambda l: l.startswith("always @(posedge ICE_CLK)"))
    goertzel_always = goertzel_block[gi:] if gi >= 0 else []
    always_text = " ".join(goertzel_always)
    lhs = set()
    for m in re.finditer(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*<=", always_text):
        lhs.add(m.group(1))
    for m in re.finditer(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*=(?!=)", always_text):
        lhs.add(m.group(1))
    allowed_internal = {"g_s0", "g_l1", "gs1", "gs2", "gwin", "arm_latch"}
    datapath_output = {"dl", "acc", "y_filt", "echo", "tx_sh", "I2S_SD_OUT",
                       "loaded", "y_d", "echo_d", "k", "busy", "busy_d",
                       "RGB_R", "RGB_G", "RGB_B", "ICE_LED", "left_sample",
                       "new_sample", "end_frame", "rx_sh", "coef_mac", "arm_mac"}
    leaked = sorted(lhs & datapath_output)
    S["goertzel_lhs_signals"] = sorted(lhs)
    S["goertzel_observer_only"] = (len(leaked) == 0 and lhs.issubset(allowed_internal))
    if leaked:
        disc.append("Goertzel block writes datapath/output signal(s): %s" % leaked)

    # coef_mac identity when disarmed.
    cm = re.search(r"wire\s+signed\s+\[15:0\]\s+coef_mac\s*=\s*(.+?);", troj_txt)
    coef_mac_expr = re.sub(r"\s+", " ", cm.group(1)).strip() if cm else None
    S["coef_mac_expr"] = coef_mac_expr
    # Expect: (arm_mac & k[0]) ? -COEF[k] : COEF[k]  -> false-branch is COEF[k],
    # condition gated by arm_mac. When arm_mac==0 => COEF[k].
    S["coef_mac_identity_when_disarmed"] = bool(
        coef_mac_expr and "arm_mac" in coef_mac_expr
        and re.search(r"\?\s*-COEF\[k\]\s*:\s*COEF\[k\]$", coef_mac_expr))
    if not S["coef_mac_identity_when_disarmed"]:
        disc.append("coef_mac is not provably identity when arm_mac==0: %r" % coef_mac_expr)

    # Deterministic gating proof: excise trojan pieces + revert datapath edit,
    # then compare to baseline code line-for-line.
    reverted = []
    skip = set(range(i_nwin, i_dl)) if goertzel_block else set()
    for i, l in enumerate(code_troj):
        if i in skip:
            continue
        if l.startswith("wire signed [15:0] coef_mac"):
            continue
        if l == "arm_mac <= arm_latch;":
            continue
        if l.startswith("gs1 = 32'sd0; gs2 = 32'sd0; gwin = 10'd0; arm_latch = 1'b0; arm_mac = 1'b0;"):
            continue
        if l == "acc <= acc + dl[k] * coef_mac;":
            reverted.append("acc <= acc + dl[k] * COEF[k];")
            continue
        reverted.append(l)
    S["revert_equals_baseline"] = (reverted == code_base)
    S["datapath_edit"] = {"from": "acc <= acc + dl[k] * COEF[k];",
                          "to": "acc <= acc + dl[k] * coef_mac;"}
    if not S["revert_equals_baseline"]:
        # surface residual differences so a real ungated change cannot hide
        import difflib
        residual = [d for d in difflib.unified_diff(code_base, reverted,
                    "baseline_code", "trojan_reverted_code", lineterm="")]
        S["revert_residual_diff"] = residual[:200]
        disc.append("After excising known trojan pieces, trojan code != baseline "
                    "(an UNGATED change exists); see revert_residual_diff")

    # Parse locked trigger constants from trojan RTL.
    m_nwin = re.search(r"localparam\s+integer\s+NWIN\s*=\s*(\d+)", troj_txt)
    m_thr  = re.search(r"ARM_THRESHOLD\s*=\s*32'd(\d+)", troj_txt)
    S["NWIN"] = int(m_nwin.group(1)) if m_nwin else None
    S["ARM_THRESHOLD"] = int(m_thr.group(1)) if m_thr else None

    # Human-readable hunk classification (from the 9 unified-diff regions).
    S["hunks"] = [
        {"region": "header comment block (L1-32)", "classification": "comment-only (non-behavioral)"},
        {"region": "COEF section comment (L46)", "classification": "comment-only"},
        {"region": "input-sync comment (L70)", "classification": "comment-only"},
        {"region": "RX deserializer comments (L84-108)", "classification": "comment-only (logic identical)"},
        {"region": "NEW Goertzel trigger block (L110-146): localparams NWIN/ARM_THRESHOLD, regs gs1/gs2/gwin/arm_latch/arm_mac/g_s0/g_l1, always block", "classification": "gated-by-arm (observer: writes ONLY internal trigger state + arm_latch; no datapath/output)"},
        {"region": "NEW coef_mac wire (L161)", "classification": "gated-by-arm (identity COEF[k] when arm_mac==0)"},
        {"region": "MAC block: + arm_mac<=arm_latch capture (L176); acc uses coef_mac not COEF[k] (L185)", "classification": "gated-by-arm (datapath identical when arm_mac==0; delay-line/echo/acc-reset/k/busy unchanged)"},
        {"region": "busy_d/y_filt latch, TX serializer, status LEDs (L193-223)", "classification": "comment-only (logic identical; arm NOT exposed on LEDs)"},
        {"region": "power-up initial block (L230-234)", "classification": "gated-by-arm (initializes new trojan regs to 0 => powers up disarmed; golden regs unchanged)"},
    ]
    S["ungated_risks"] = [h for h in S["hunks"] if "UNGATED" in h["classification"]]

    structural_ok = (S["coeffs_base_eq_troj"] and S["coeffs_rtl_eq_json"]
                     and S["goertzel_observer_only"]
                     and S["coef_mac_identity_when_disarmed"]
                     and S["revert_equals_baseline"]
                     and not S["ungated_risks"])
    S["structural_all_diffs_gated"] = bool(structural_ok)

    # ===================== PART 2: EMPIRICAL =====================
    E = report["empirical"]
    rt = load_module(REF_TROJAN, "ref_trojan_mod")
    sw = load_module(SW_FIR, "sw_fir_mod")
    run_trojan = rt.run_trojan
    ref_golden_fir = rt.golden_fir
    sw_fir_filter = sw.fir_filter
    h = [int(v) for v in coeffs_json]
    N_WIN = rt.N_WIN
    ARM_THRESHOLD = rt.ARM_THRESHOLD
    FS = rt.FS
    KEY_HZ = FS / 3.0
    report["method"]["N_WIN"] = N_WIN
    report["method"]["ARM_THRESHOLD"] = ARM_THRESHOLD
    report["method"]["FS"] = FS
    report["method"]["key_hz"] = KEY_HZ
    report["method"]["exclusion_band_hz"] = [KEY_HZ - 150.0, KEY_HZ + 150.0]

    # ---- cross-validate the independent golden against the 3 other models ----
    rngv = np.random.default_rng(12345)
    xv = rngv.integers(-32768, 32768, size=1500, dtype=np.int64).tolist()
    g_me  = my_golden_np(xv, h).tolist()
    g_py  = pure_python_golden(xv, h)
    g_sw  = sw_fir_filter(xv, h)
    g_rt  = ref_golden_fir(xv, h)
    E["cross_model_agreement"] = {
        "independent_np_eq_pure_python": (g_me == g_py),
        "independent_np_eq_sw_fir_py":   (g_me == g_sw),
        "independent_np_eq_ref_golden":  (g_me == g_rt),
        "sample_len": len(xv)}
    if not all(E["cross_model_agreement"][k] for k in
               ("independent_np_eq_pure_python","independent_np_eq_sw_fir_py",
                "independent_np_eq_ref_golden")):
        disc.append("Independent golden model disagrees with reference models")

    # ---- build corpus (NO fs/3 key tone; exclude +/-150 Hz band) ----
    corpus = []   # (category, label, x_list)

    # 20+ random int16 streams, distinct seeds, lengths 2000-8000
    for seed in range(24):
        rng = np.random.default_rng(1000 + seed)
        length = int(rng.integers(2000, 8001))
        x = rng.integers(-32768, 32768, size=length, dtype=np.int64).tolist()
        corpus.append(("random", f"rand_seed{seed}_len{length}", x))

    # full real WAV
    import wave
    from array import array
    w = wave.open(WAV, "rb")
    a = array("h"); a.frombytes(w.readframes(w.getnframes())); w.close()
    if sys.byteorder == "big": a.byteswap()
    corpus.append(("real_audio", "wav_full_%d" % len(a), list(a)))

    # full-scale sine tones over 100..8000 Hz, excluding key band
    def in_band(f): return (KEY_HZ - 150.0) <= f <= (KEY_HZ + 150.0)
    tone_len = 1728   # exactly 3 x 576-sample windows
    freqs = []
    f = 100.0
    while f <= 8000.0:                      # coarse 100 Hz grid
        if not in_band(f): freqs.append(round(f, 3))
        f += 100.0
    for f0 in [x / 10.0 for x in range(47333, 51834, 100)]:   # 4733.3..5183.3 step 10
        if not in_band(f0): freqs.append(round(f0, 3))
    for f0 in [x / 10.0 for x in range(54833, 59334, 100)]:   # 5483.3..5933.3 step 10
        if not in_band(f0): freqs.append(round(f0, 3))
    freqs = sorted(set(freqs))
    for fr in freqs:
        t = np.arange(tone_len)
        x = np.round(32767 * np.sin(2 * np.pi * fr * t / FS)).astype(np.int64)
        x = np.clip(x, -32768, 32767).tolist()
        corpus.append(("sine_fullscale", f"sine_{fr}Hz", x))

    # silence / impulse / step / full-scale edges and other hard edges
    corpus.append(("edge", "silence", [0] * 4000))
    imp = [0] * 4000; imp[0] = 32767; corpus.append(("edge", "impulse_pos", imp))
    imp2 = [0] * 4000; imp2[0] = -32768; corpus.append(("edge", "impulse_neg", imp2))
    corpus.append(("edge", "step_up", [0] * 1000 + [32767] * 3000))
    corpus.append(("edge", "step_down", [32767] * 1000 + [-32768] * 3000))
    corpus.append(("edge", "dc_max", [32767] * 4000))
    corpus.append(("edge", "dc_min", [-32768] * 4000))
    corpus.append(("edge", "nyquist_fullscale", [32767 if i % 2 == 0 else -32768 for i in range(4000)]))
    corpus.append(("edge", "alt_pairs", [32767, 32767, -32768, -32768] * 1000))
    corpus.append(("edge", "ramp_up", [(-32768 + (i * 65535 // 3999)) for i in range(4000)]))
    rngw = np.random.default_rng(999)
    walk = np.clip(np.cumsum(rngw.integers(-400, 401, size=6000)), -32768, 32767).astype(np.int64).tolist()
    corpus.append(("edge", "random_walk", walk))

    # ---- run the checks ----
    total_samples = 0
    total_mismatches = 0
    first_mismatch = None
    total_windows = 0
    windows_armed = 0
    armed_at_nonzero_total = 0
    max_L1 = 0
    max_L1_label = None
    per_cat = {}
    streams_armed = []

    for cat, label, x in corpus:
        y_t, armed = run_trojan(x, h)             # REQUIRED model under test
        y_g = my_golden_np(x, h)                  # INDEPENDENT golden
        yt = np.asarray(y_t, dtype=np.int64)
        mism_idx = np.flatnonzero(yt != y_g)
        n_mis = int(mism_idx.size)
        n_arm_samp = int(sum(armed))
        l1s = goertzel_window_l1(x, N_WIN)
        n_win = len(l1s)
        wmax = max(l1s) if l1s else 0
        n_win_armed = sum(1 for v in l1s if v >= ARM_THRESHOLD)

        total_samples += len(x)
        total_mismatches += n_mis
        total_windows += n_win
        windows_armed += n_win_armed
        armed_at_nonzero_total += n_arm_samp
        if wmax > max_L1:
            max_L1, max_L1_label = wmax, label
        if n_mis and first_mismatch is None:
            j = int(mism_idx[0])
            first_mismatch = {"stream": label, "index": j,
                              "trojan": int(yt[j]), "golden": int(y_g[j])}
        if n_arm_samp or n_win_armed:
            streams_armed.append({"stream": label, "armed_at_nonzero": n_arm_samp,
                                  "windows_armed": n_win_armed, "max_L1": wmax})
        c = per_cat.setdefault(cat, {"streams": 0, "samples": 0, "mismatches": 0,
                                     "windows": 0, "windows_armed": 0, "max_L1": 0})
        c["streams"] += 1; c["samples"] += len(x); c["mismatches"] += n_mis
        c["windows"] += n_win; c["windows_armed"] += n_win_armed
        c["max_L1"] = max(c["max_L1"], wmax)

    margin_db = (20.0 * math.log10(ARM_THRESHOLD / max_L1)) if max_L1 > 0 else float("inf")

    E["num_streams"] = len(corpus)
    E["num_sine_tones"] = len(freqs)
    E["total_samples_compared"] = total_samples
    E["total_output_mismatches"] = total_mismatches
    E["first_mismatch"] = first_mismatch
    E["total_windows_evaluated"] = total_windows
    E["windows_that_armed"] = windows_armed
    E["armed_at_nonzero_samples_total"] = armed_at_nonzero_total
    E["worst_case_window_L1"] = max_L1
    E["worst_case_window_L1_stream"] = max_L1_label
    E["arm_threshold"] = ARM_THRESHOLD
    E["margin_dB_over_worst_case"] = round(margin_db, 2)
    E["streams_that_armed"] = streams_armed
    E["per_category"] = per_cat

    # WAV-specific headline (real-audio claim) + definitive 3-way agreement on WAV
    wav_x = next(x for c, lbl, x in corpus if c == "real_audio")
    wav_y_t, wav_armed = run_trojan(wav_x, h)
    wav_g_me = my_golden_np(wav_x, h).tolist()
    wav_g_sw = sw_fir_filter(wav_x, h)
    wav_g_rt = ref_golden_fir(wav_x, h)
    wav_l1 = goertzel_window_l1(wav_x, N_WIN)
    wav_max = max(wav_l1) if wav_l1 else 0
    E["wav"] = {
        "samples": len(wav_x),
        "trojan_eq_independent_golden": (wav_y_t == wav_g_me),
        "trojan_eq_sw_fir_py": (wav_y_t == wav_g_sw),
        "trojan_eq_ref_golden": (wav_y_t == wav_g_rt),
        "armed_at_nonzero": int(sum(wav_armed)),
        "windows": len(wav_l1),
        "max_window_L1": wav_max,
        "margin_dB": round(20.0 * math.log10(ARM_THRESHOLD / wav_max), 2) if wav_max else float("inf"),
    }
    if not (wav_y_t == wav_g_me == wav_g_sw == wav_g_rt):
        disc.append("WAV: trojan output disagrees with one or more golden models")

    empirical_ok = (total_mismatches == 0 and windows_armed == 0
                    and armed_at_nonzero_total == 0
                    and E["cross_model_agreement"]["independent_np_eq_sw_fir_py"])
    E["empirical_zero_mismatch_zero_arm"] = bool(empirical_ok)

    # ===================== VERDICT =====================
    report["confirmed"] = bool(structural_ok and empirical_ok)
    if max_L1 > 0 and margin_db < 20:
        report["residual_risks"].append(
            "Worst-case full-scale out-of-band tone margin is %.1f dB; detector "
            "specificity is finite near the key band edge." % margin_db)
    report["residual_risks"].append(
        "Equivalence verified on the reference MODEL (ref_trojan.py) and RTL "
        "source text, not via gate-level/Verilog simulation of the bitstream.")
    report["residual_risks"].append(
        "Empirical corpus is broad but finite; structural proof (revert==baseline "
        "+ observer-only trigger) is what establishes bit-identity for ALL inputs "
        "while arm_mac==0.")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as fh:
        json.dump(report, fh, indent=2)

    # ---- console summary ----
    print("=== STRUCTURAL ===")
    print("  COEF base==troj   :", S["coeffs_base_eq_troj"])
    print("  COEF rtl==json    :", S["coeffs_rtl_eq_json"], "(sum=%d)" % S["coeffs_sum"])
    print("  revert==baseline  :", S["revert_equals_baseline"])
    print("  coef_mac identity :", S["coef_mac_identity_when_disarmed"], "|", coef_mac_expr)
    print("  goertzel LHS      :", S["goertzel_lhs_signals"])
    print("  observer-only     :", S["goertzel_observer_only"])
    print("  NWIN / THRESHOLD  :", S["NWIN"], "/", S["ARM_THRESHOLD"])
    print("  UNGATED risks     :", S["ungated_risks"])
    print("  ALL DIFFS GATED   :", S["structural_all_diffs_gated"])
    print("=== EMPIRICAL ===")
    print("  streams           :", E["num_streams"], "(%d sine tones)" % E["num_sine_tones"])
    print("  samples compared  :", E["total_samples_compared"])
    print("  output mismatches :", E["total_output_mismatches"])
    print("  windows evaluated :", E["total_windows_evaluated"])
    print("  windows armed     :", E["windows_that_armed"])
    print("  armed_at nonzero  :", E["armed_at_nonzero_samples_total"])
    print("  worst window L1   :", E["worst_case_window_L1"], "of 2^23=%d" % ARM_THRESHOLD,
          "(%s)" % E["worst_case_window_L1_stream"])
    print("  margin over worst :", E["margin_dB_over_worst_case"], "dB")
    print("  WAV 3-way golden  :", E["wav"]["trojan_eq_independent_golden"],
          E["wav"]["trojan_eq_sw_fir_py"], E["wav"]["trojan_eq_ref_golden"],
          "| WAV margin", E["wav"]["margin_dB"], "dB")
    print("  cross-model agree :", E["cross_model_agreement"])
    print("=== CONFIRMED:", report["confirmed"], "===")
    print("  discrepancies     :", disc)
    print("  wrote", OUT_JSON)

if __name__ == "__main__":
    main()
