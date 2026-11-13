#!/usr/bin/env python3
"""Generate I2S frame stimulus for the netlist testbench.

Writes stim_l.hex / stim_r.hex (one 16-bit word per frame, hex, for $readmemh)
and stim_plan.json describing the frames (so the decoder knows what was sent).

Frame plan for impulse-response recovery:
  - FLUSH zero frames (clear the <=64-deep delay line and pipeline)
  - one impulse frame carrying value A on BOTH channels (bridge sends same on L/R)
  - TAIL zero frames (read out the full impulse response)
repeated for several amplitudes A.
"""
import json, sys

FLUSH = 256      # zero frames before each impulse (delay line <=64 deep)
TAIL  = 160      # zero frames after impulse (read out response; N<=64 taps)
AMPS  = [-32768, 32767, 16384, -16384, 8192]  # Q1.15 impulse amplitudes

def u16(x):
    return x & 0xFFFF

lwords = []
rwords = []
plan = []  # list of dicts: {kind, amp, frame_index}

# Lead-in idle so the core powers up / resets cleanly
LEADIN = 64
for _ in range(LEADIN):
    lwords.append(0); rwords.append(0)

for A in AMPS:
    seg_start = len(lwords)
    for _ in range(FLUSH):
        lwords.append(0); rwords.append(0)
    impulse_frame = len(lwords)
    lwords.append(u16(A)); rwords.append(u16(A))
    for _ in range(TAIL):
        lwords.append(0); rwords.append(0)
    plan.append({"amp": A, "seg_start": seg_start,
                 "impulse_frame": impulse_frame,
                 "flush": FLUSH, "tail": TAIL})

nframes = len(lwords)
with open("stim_l.hex", "w") as f:
    f.write("\n".join("%04x" % w for w in lwords) + "\n")
with open("stim_r.hex", "w") as f:
    f.write("\n".join("%04x" % w for w in rwords) + "\n")
with open("stim_plan.json", "w") as f:
    json.dump({"nframes": nframes, "leadin": LEADIN, "segments": plan,
               "amps": AMPS, "flush": FLUSH, "tail": TAIL}, f, indent=1)

print("nframes =", nframes)
print("segments:", len(plan), "amps:", AMPS)
print("frames/segment:", FLUSH + 1 + TAIL)
