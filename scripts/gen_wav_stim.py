#!/usr/bin/env python3
"""Generate I2S stimulus from the real noisy WAV (16 kHz mono) for the netlist
co-simulation. left=right=sample (as the bridge does). Leading FLUSH zeros."""
import json, sys, wave
from array import array

WAV = sys.argv[1]
M   = int(sys.argv[2]) if len(sys.argv) > 2 else 2048   # real samples to stream
FLUSH = 128
TAIL  = 8

w = wave.open(WAV, "rb")
assert w.getnchannels()==1 and w.getsampwidth()==2, "need 16-bit mono"
a = array("h"); a.frombytes(w.readframes(M))
if sys.byteorder == "big": a.byteswap()
samples = list(a)[:M]

lw = [0]*FLUSH + [s & 0xFFFF for s in samples] + [0]*TAIL
rw = list(lw)
open("stim_l.hex","w").write("\n".join("%04x"%x for x in lw)+"\n")
open("stim_r.hex","w").write("\n".join("%04x"%x for x in rw)+"\n")
json.dump({"nframes":len(lw),"flush":FLUSH,"tail":TAIL,"M":len(samples),
           "wav":WAV,"samples_int":samples}, open("wav_plan.json","w"))
print("wav=%s  M=%d  FLUSH=%d  nframes=%d" % (WAV, len(samples), FLUSH, len(lw)))
