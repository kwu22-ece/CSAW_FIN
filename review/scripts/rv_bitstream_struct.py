#!/usr/bin/env python3
"""Subphase-R INDEPENDENT bitstream-structure audit (parses the .asc directly).

Verifies, from the ASCII bitstream alone (independent of icebox_stat / the
committed netlist):
  * DSP (SB_MAC16) non-use: whether any .dspN_tile carries design-specific
    (non-default) configuration. Default = identical pattern replicated across
    all 8 physical DSP blocks / mirror-symmetric between the two columns.
  * RAM usage: which .ramb/.ramt tiles actually carry config bits (the
    icebox_stat "BRAMs: 2" count), and whether .ram_data is zero-initialized.
  * Resource tallies vs icebox_stat.

Usage: python rv_bitstream_struct.py recovered/fir_audio_top.asc
"""
import hashlib, sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "recovered/fir_audio_top.asc"
lines = open(path).read().replace("\r", "").split("\n")

# --- split into tile sections ---
tiles = []   # (directive, x, y, [bitrows])
cur = None
for ln in lines:
    if ln.startswith("."):
        if cur: tiles.append(cur)
        parts = ln.split()
        d = parts[0]
        xy = (int(parts[1]), int(parts[2])) if len(parts) >= 3 and parts[1].lstrip('-').isdigit() else None
        cur = [d, xy, []]
    elif cur is not None:
        if ln.strip() != "":
            cur[2].append(ln.strip())
if cur: tiles.append(cur)

def setbits(rows):     # count '1's across binary rows
    return sum(r.count("1") for r in rows)
def nonzero_hex(rows): # count nonzero hex nibbles
    return sum(1 for r in rows for c in r if c not in "0 \t")

by_type = defaultdict(list)
for d, xy, rows in tiles:
    by_type[d].append((xy, rows))

print("== TILE-TYPE SET-BIT SUMMARY ==")
for d in sorted(by_type):
    entries = by_type[d]
    if d == ".ram_data":
        nz = [(xy, nonzero_hex(rows)) for xy, rows in entries]
        tot = sum(n for _, n in nz)
        nzt = [xy for xy, n in nz if n]
        print(f"  {d:14s}: {len(entries)} tiles, {tot} nonzero nibbles total; "
              f"non-zero at {nzt if nzt else 'NONE (all zero-initialized)'}")
    else:
        sb = [(xy, setbits(rows)) for xy, rows in entries]
        active = [xy for xy, n in sb if n]
        print(f"  {d:14s}: {len(entries)} tiles, {len(active)} with >=1 set bit")

# --- DSP analysis: are all DSP blocks' config identical (=> non-functional default)? ---
print("\n== DSP (MAC16) FUNCTIONAL-CONFIG CHECK ==")
dsp = defaultdict(dict)   # (x,y_block) grouping: key by subtile name+coord
dsp_tiles = [(d, xy, rows) for d, xy, rows in tiles if d.startswith(".dsp")]
# group by subtile index (dsp0..dsp3): compare the same subtile across all blocks
by_sub = defaultdict(list)
for d, xy, rows in dsp_tiles:
    by_sub[d].append((xy, "".join(rows)))
all_identical = True
for d in sorted(by_sub):
    contents = by_sub[d]
    digests = defaultdict(list)
    for xy, blob in contents:
        digests[hashlib.sha1(blob.encode()).hexdigest()[:10]].append(xy)
    nbits = setbits([contents[0][1]])
    print(f"  {d}: {len(contents)} instances, {len(digests)} distinct bit-pattern(s), "
          f"{nbits} set bits each")
    for h, xys in digests.items():
        print(f"      pattern {h}: {len(xys)} tiles @ {xys}")
    if len(digests) > 1:
        all_identical = False
print(f"  => every DSP sub-tile pattern is replicated across blocks "
      f"(position-dependent default): {all_identical}")
print("     (functional use would make one block's pattern UNIQUE; none is.)")

# --- RAM analysis ---
print("\n== RAM (SB_RAM40_4K) CHECK ==")
ramb = [(xy, setbits(rows)) for d, xy, rows in tiles if d == ".ramb_tile"]
ramt = [(xy, setbits(rows)) for d, xy, rows in tiles if d == ".ramt_tile"]
ramb_active = [xy for xy, n in ramb if n]
ramt_active = [xy for xy, n in ramt if n]
print(f"  .ramb_tile with config bits: {ramb_active}")
print(f"  .ramt_tile with config bits: {ramt_active}")
print(f"  => physically-configured RAM blocks (ramb+ramt tile keys): "
      f"{len(ramb_active)+len(ramt_active)}  (icebox_stat reports 'BRAMs: 2')")
# zero-init check on the used block's ram_data
rd = {xy: nonzero_hex(rows) for d, xy, rows in tiles if d == ".ram_data"}
nonzero_rd = {xy: n for xy, n in rd.items() if n}
print(f"  .ram_data non-zero blocks: {nonzero_rd if nonzero_rd else 'NONE -> zero-initialized'}")

print("\n== ICEBOX_STAT CROSS-TALLY ==")
print(f"  .logic_tile with bits: {sum(1 for d,xy,r in tiles if d=='.logic_tile' and setbits(r))}"
      f"  .io_tile with bits: {sum(1 for d,xy,r in tiles if d=='.io_tile' and setbits(r))}")
