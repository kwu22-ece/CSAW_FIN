#!/usr/bin/env python3
"""Spectral + impulse-response comparison of the payload: golden LPF vs armed HPF.

The payload multiplies the impulse response by (-1)^k (odd-index taps negated),
which is an exact spectral inversion: H'(w) = H(w - pi). We show, with measured
numbers and an SVG figure, that disarmed == the golden low-pass and armed == a
high-pass that is STILL linear-phase (the inverted taps remain symmetric), so the
Trojan is a clean transfer-function attack.
"""
import json, math, os
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.normpath(os.path.join(HERE, "..", ".."))
FS = 16000.0


def load_h():
    with open(os.path.join(EXP, "golden", "coeffs.json")) as fh:
        return [int(v) for v in json.load(fh)["coeffs_q15"]]


def db(x):
    return 20 * math.log10(abs(x) + 1e-30)


def main():
    h = load_h()
    N = len(h)
    hp = [((-1) ** k) * h[k] for k in range(N)]        # armed payload taps (spectral inversion)

    hf = np.array(h) / 32768.0
    hpf = np.array(hp) / 32768.0
    w, Hg = signal.freqz(hf, worN=8192, fs=FS)
    _, Hh = signal.freqz(hpf, worN=8192, fs=FS)
    mg = 20 * np.log10(np.abs(Hg) + 1e-30)
    mh = 20 * np.log10(np.abs(Hh) + 1e-30)

    def gain_at(mag, f):
        i = int(np.argmin(np.abs(w - f)))
        return float(mag[i])

    probes = [250, 500, 1000, 2000, 3000, 4000, 5333.33, 6000, 7000, 7500]
    tbl = [{"f_hz": f, "golden_lpf_dB": round(gain_at(mg, f), 2), "armed_hpf_dB": round(gain_at(mh, f), 2),
            "delta_dB": round(gain_at(mh, f) - gain_at(mg, f), 2)} for f in probes]

    # linear-phase preservation: hp is still symmetric?
    hp_symmetric = all(hp[k] == hp[N - 1 - k] for k in range(N))
    out = {
        "N": N, "sum_h_golden": sum(h), "sum_h_armed": sum(hp),
        "dc_gain_golden_dB": round(db(sum(h) / 32768.0), 3),
        "dc_gain_armed_dB": round(db(sum(hp) / 32768.0), 3),
        "nyquist_gain_golden_dB": round(db(sum(((-1) ** k) * h[k] for k in range(N)) / 32768.0), 3),
        "nyquist_gain_armed_dB": round(db(sum(((-1) ** k) * hp[k] for k in range(N)) / 32768.0), 3),
        "armed_taps_still_symmetric": hp_symmetric,
        "armed_still_linear_phase": hp_symmetric,
        "l1_norm_golden": sum(abs(v) for v in h), "l1_norm_armed": sum(abs(v) for v in hp),
        "accumulator_bound_unchanged": sum(abs(v) for v in h) == sum(abs(v) for v in hp),
        "probe_gain_table": tbl,
        "passband_mean_atten_when_armed_dB": round(float(np.mean([gain_at(mh, f) - gain_at(mg, f)
                                                                  for f in (250, 500, 1000, 2000)])), 2),
    }
    os.makedirs(os.path.join(EXP, "reports", "analysis"), exist_ok=True)
    os.makedirs(os.path.join(EXP, "reports", "figures"), exist_ok=True)
    with open(os.path.join(EXP, "reports", "analysis", "payload_spectral.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    # frequency-response CSV
    with open(os.path.join(EXP, "reports", "analysis", "payload_freqresponse.csv"), "w") as fh:
        fh.write("hz,golden_lpf_db,armed_hpf_db\n")
        for i in range(0, len(w), 8):
            fh.write("%.2f,%.3f,%.3f\n" % (w[i], mg[i], mh[i]))

    # ---- hand-rolled SVG (matplotlib may be absent) ----
    W, H, ML, MB, MT, MR = 760, 420, 64, 50, 48, 20
    pw, ph = W - ML - MR, H - MT - MB
    fmin, fmax = 0.0, 8000.0
    dmin, dmax = -80.0, 8.0

    def X(f): return ML + (f - fmin) / (fmax - fmin) * pw
    def Y(d): return MT + (dmax - max(dmin, min(dmax, d))) / (dmax - dmin) * ph

    def poly(mag, step=4):
        pts = []
        for i in range(0, len(w), step):
            if w[i] > fmax: break
            pts.append("%.1f,%.1f" % (X(w[i]), Y(mag[i])))
        return " ".join(pts)

    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif">')
    s.append(f'<rect width="{W}" height="{H}" fill="#0f1720"/>')
    s.append(f'<text x="{W/2}" y="26" fill="#e6edf3" font-size="17" text-anchor="middle" font-weight="bold">Candidate 05d payload: golden low-pass vs armed high-pass (spectral inversion)</text>')
    # grid + y labels (dB)
    for dbv in range(-80, 9, 8):
        y = Y(dbv)
        s.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML+pw}" y2="{y:.1f}" stroke="#223" stroke-width="1"/>')
        s.append(f'<text x="{ML-8}" y="{y+4:.1f}" fill="#8b98a5" font-size="10" text-anchor="end">{dbv}</text>')
    # x labels (kHz)
    for fk in range(0, 9, 1):
        x = X(fk * 1000)
        s.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT+ph}" stroke="#1b2733" stroke-width="1"/>')
        s.append(f'<text x="{x:.1f}" y="{MT+ph+16}" fill="#8b98a5" font-size="10" text-anchor="middle">{fk}k</text>')
    s.append(f'<text x="{ML+pw/2}" y="{H-6}" fill="#aeb9c4" font-size="11" text-anchor="middle">frequency (Hz, fs=16 kHz)</text>')
    s.append(f'<text x="16" y="{MT+ph/2}" fill="#aeb9c4" font-size="11" text-anchor="middle" transform="rotate(-90 16 {MT+ph/2})">magnitude (dB)</text>')
    # -3 dB and the fs/3 key marker
    s.append(f'<line x1="{X(3296):.1f}" y1="{MT}" x2="{X(3296):.1f}" y2="{MT+ph}" stroke="#394b59" stroke-dasharray="3 3"/>')
    s.append(f'<line x1="{X(5333.33):.1f}" y1="{MT}" x2="{X(5333.33):.1f}" y2="{MT+ph}" stroke="#d98c00" stroke-dasharray="4 3"/>')
    s.append(f'<text x="{X(5333.33)+4:.1f}" y="{MT+14}" fill="#f0a500" font-size="10">key fs/3</text>')
    # curves
    s.append(f'<polyline fill="none" stroke="#3fb950" stroke-width="2.2" points="{poly(mg)}"/>')
    s.append(f'<polyline fill="none" stroke="#f85149" stroke-width="2.2" points="{poly(mh)}"/>')
    # legend
    s.append(f'<rect x="{ML+pw-220}" y="{MT+8}" width="210" height="46" fill="#0b1118" stroke="#223" rx="5"/>')
    s.append(f'<line x1="{ML+pw-208}" y1="{MT+24}" x2="{ML+pw-184}" y2="{MT+24}" stroke="#3fb950" stroke-width="3"/>')
    s.append(f'<text x="{ML+pw-178}" y="{MT+28}" fill="#e6edf3" font-size="11">disarmed = golden LPF (-3 dB 3.3 kHz)</text>')
    s.append(f'<line x1="{ML+pw-208}" y1="{MT+42}" x2="{ML+pw-184}" y2="{MT+42}" stroke="#f85149" stroke-width="3"/>')
    s.append(f'<text x="{ML+pw-178}" y="{MT+46}" fill="#e6edf3" font-size="11">armed = HPF (passband -60 dB)</text>')
    s.append('</svg>')
    svg_path = os.path.join(EXP, "reports", "figures", "payload_spectral.svg")
    with open(svg_path, "w") as fh:
        fh.write("\n".join(s))

    print("sum_h golden=%d armed=%d  | DC golden=%.1f dB armed=%.1f dB | nyquist golden=%.1f armed=%.1f"
          % (out["sum_h_golden"], out["sum_h_armed"], out["dc_gain_golden_dB"], out["dc_gain_armed_dB"],
             out["nyquist_gain_golden_dB"], out["nyquist_gain_armed_dB"]))
    print("armed taps still symmetric (linear phase preserved): %s" % out["armed_taps_still_symmetric"])
    print("accumulator bound unchanged (L1 norm %d == %d): %s" % (out["l1_norm_golden"], out["l1_norm_armed"], out["accumulator_bound_unchanged"]))
    print("passband mean attenuation when armed: %.1f dB" % out["passband_mean_atten_when_armed_dB"])
    print("probe gains (Hz: golden -> armed dB):")
    for r in tbl:
        print("   %7.1f : %7.2f -> %7.2f  (delta %+.2f)" % (r["f_hz"], r["golden_lpf_dB"], r["armed_hpf_dB"], r["delta_dB"]))
    print("SVG: %s" % svg_path)


if __name__ == "__main__":
    main()
