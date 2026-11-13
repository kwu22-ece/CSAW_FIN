#!/usr/bin/env python3
"""Generate directed I2S input vectors for candidate-05d activation tests.

Writes harness-format CSVs (index,channel,value; sequential word index, channels
alternating 0/1; left channel = the sample to filter, right = mono echo copy).
These exercise the Goertzel trigger (7500 Hz key tone) and the near-key
selectivity cases. Deterministic (no RNG) -> reproducible.
"""
import csv, math, os

FS = 16000
HERE = os.path.dirname(os.path.abspath(__file__))
VDIR = os.path.join(HERE, "vectors")
os.makedirs(VDIR, exist_ok=True)


def tone(freq, amp, n, phase=0.0):
    return [int(round(amp * math.sin(2 * math.pi * freq * i / FS + phase))) for i in range(n)]


def write_vec(name, left):
    """left: list of int16 left-channel samples; right channel mirrors left."""
    path = os.path.join(VDIR, name)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "channel", "value"])
        wi = 0
        for s in left:
            s = max(-32768, min(32767, int(s)))
            w.writerow([wi, 0, s]); wi += 1
            w.writerow([wi, 1, s]); wi += 1
    return path, len(left)


FKEY = FS / 3.0            # 5333.33 Hz exact-bin key frequency (N_WIN=576, coeff=-1)


def main():
    made = []
    # 1) Full-scale fs/3 key tone, 1152 samples (2 windows): arms at n=576.
    made.append(write_vec("key_fullscale.csv", tone(FKEY, 32767, 1152)))
    # 2) 80%-scale fs/3 key tone, 1152 samples: still arms (L1 ~1.3e7 > 2^23=8.39e6).
    made.append(write_vec("key_partialscale.csv", tone(FKEY, 26214, 1152)))
    # 3) Key then low probe: 1152 samples fs/3 (arm at 576), then 576 samples 500 Hz.
    #    Demonstrates the armed HPF BLOCKING a 500 Hz tone the golden LPF would pass.
    made.append(write_vec("key_then_lowprobe.csv", tone(FKEY, 32767, 1152) + tone(500, 20000, 576)))
    # 4) Near-key 5467 Hz full scale, 1152 samples: must NOT arm (selectivity, +134 Hz).
    made.append(write_vec("nearkey_5467.csv", tone(5467, 32767, 1152)))
    # 5) Near-key 5200 Hz full scale, 1152 samples: must NOT arm (selectivity, -133 Hz).
    made.append(write_vec("nearkey_5200.csv", tone(5200, 32767, 1152)))
    # 6) 500 Hz passband tone alone, 768 samples: golden passes it; no arm (control).
    made.append(write_vec("probe_500.csv", tone(500, 20000, 768)))
    for p, n in made:
        print("wrote %-22s  %d left samples (%d words)" % (os.path.basename(p), n, 2 * n))


if __name__ == "__main__":
    main()
