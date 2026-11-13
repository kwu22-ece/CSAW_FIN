#!/usr/bin/env python3
"""Characterize the recovered 63-tap FIR: frequency response, passband edge,
stopband attenuation, group delay. Reads coeffs.json (Q1.15 integer taps).

Usage: python analyze_filter.py <coeffs.json> [fs_hz]
"""
import json, sys
import numpy as np

coeffs_path = sys.argv[1] if len(sys.argv) > 1 else "coeffs.json"
FS = float(sys.argv[2]) if len(sys.argv) > 2 else 16000.0

d = json.load(open(coeffs_path))
hq = d["coeffs_q15"]
N = len(hq)
h = np.array(hq, dtype=np.float64) / 32768.0   # Q1.15 -> float

print("N taps           :", N)
print("sum (DC gain)    : %d / 32768 = %.6f (%.3f dB)" %
      (sum(hq), sum(hq)/32768.0, 20*np.log10(abs(sum(hq)/32768.0))))
print("symmetric        :", all(hq[i] == hq[N-1-i] for i in range(N)))
print("group delay      : %.1f samples = %.3f ms @ %g Hz" %
      ((N-1)/2, (N-1)/2/FS*1000, FS))
print("max |tap|        : %d (%.5f)" % (max(abs(x) for x in hq), max(abs(x) for x in hq)/32768.0))

# Frequency response via DTFT on a dense grid
W = np.linspace(0, np.pi, 4096)
H = np.array([np.sum(h * np.exp(-1j*w*np.arange(N))) for w in W])
mag = np.abs(H)
magdb = 20*np.log10(np.maximum(mag, 1e-12))
f = W/np.pi*(FS/2)

def edge(thresh_db):
    # first frequency where magnitude drops below thresh (from DC)
    below = np.where(magdb < thresh_db)[0]
    return f[below[0]] if len(below) else None

print("\n-- Response landmarks (fs=%g Hz) --" % FS)
for t in (-1, -3, -6):
    e = edge(t)
    print("  %+d dB point   : %s Hz" % (t, ("%.0f" % e) if e else "n/a"))

# passband ripple: max deviation from 1.0 up to the -3 dB edge
e3 = edge(-3)
if e3:
    pb = mag[f <= e3]
    print("  passband ripple (to -3dB): +%.3f / %.3f dB" %
          (20*np.log10(pb.max()), 20*np.log10(pb.min())))

# stopband: min attenuation above various edges
for fe in (3000, 4000, 5000, 6000):
    if fe < FS/2:
        sb = magdb[f >= fe]
        print("  max gain above %4d Hz : %.1f dB" % (fe, sb.max()))

# first null
dmag = np.diff(np.sign(np.diff(mag)))
# print coarse response table
print("\n-- Magnitude vs frequency --")
for ff in [0,500,1000,1500,2000,2500,3000,3500,4000,5000,6000,7000,8000]:
    if ff <= FS/2:
        idx = np.argmin(np.abs(f-ff))
        print("  %5d Hz : %7.2f dB  (%.4f)" % (ff, magdb[idx], mag[idx]))

# save a CSV of the response for the report
import csv
with open("freq_response.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["freq_hz","mag","mag_db"])
    for i in range(0,len(f),8):
        w.writerow(["%.2f"%f[i],"%.6f"%mag[i],"%.3f"%magdb[i]])
print("\nsaved freq_response.csv")

# normalized float coeffs for reference
print("\n-- float coeffs (h[n]) --")
print(np.array2string(h, precision=6, max_line_width=100, separator=", "))
