#!/usr/bin/env python3
"""Compare the netlist I2S capture (real WAV in) against the software FIR model,
bit-for-bit. Calibrates decode via the echo channel."""
import json, sys
sys.path.insert(0, r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN/.worktrees/phase-02/scripts")
from sw_fir import load_coeffs, fir_filter

plan = json.load(open("wav_plan.json"))
FLUSH = plan["flush"]; M = plan["M"]; samples = plan["samples_int"]
cap = open("capture.txt").read().split("\n")
SDOUT={};
stl=[int(x,16) for x in open("stim_l.hex").read().split()]
for line in cap:
    line=line.strip()
    if not line: continue
    f,p,ws,sdin,sdout=line.split()
    SDOUT[int(f)*32+int(p)]=int(sdout)
NF=len(stl)
def word(start,msb=True):
    v=0
    for i in range(16):
        b=SDOUT.get(start+i,0)
        v|= b<<(15-i) if msb else b<<i
    return v
def s16(x):
    x&=0xFFFF; return x-0x10000 if x&0x8000 else x

# calibrate via echo (output-right == input-left delayed LAT)
best=None
for msb in (True,False):
  for boff in range(-2,3):
    for lat in range(0,7):
      m=t=0
      for f in range(lat,NF):
        t+=1
        if s16(word(f*32+16+boff,msb))==s16(stl[f-lat]): m+=1
      if best is None or m/t>best[0]: best=(m/t,msb,boff,lat,m,t)
score,msb,boff,lat,m,t=best
print("echo calib: msb=%s boff=%d LAT=%d  %d/%d (%.4f)"%(msb,boff,lat,m,t,score))

# hardware filtered output for the real samples
hw=[s16(word((FLUSH+n+lat)*32+0+boff,msb)) for n in range(M)]
# software model on the SAME stream (flush zeros + real samples), aligned
h=load_coeffs(r"C:/Users/lowbr/Documents/College/AI/CSAW_FIN/.worktrees/phase-02/recovered/coeffs.json")
x=[0]*FLUSH+samples
y_full=fir_filter(x,h)
sw=y_full[FLUSH:FLUSH+M]

mism=[(n,hw[n],sw[n]) for n in range(M) if hw[n]!=sw[n]]
print("samples compared: %d" % M)
print("bit-exact matches: %d/%d" % (M-len(mism), M))
if mism:
    print("first mismatches (n, hw, sw):", mism[:10])
else:
    print("RESULT: netlist hardware output == software FIR model, BIT-FOR-BIT.")
print("hw first10:", hw[:10])
print("sw first10:", sw[:10])
# stats
import statistics
print("input range: [%d, %d]" % (min(samples), max(samples)))
print("output range: [%d, %d]" % (min(hw), max(hw)))
