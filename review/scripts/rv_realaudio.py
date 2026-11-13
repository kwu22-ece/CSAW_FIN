#!/usr/bin/env python3
"""Subphase-R INDEPENDENT real-audio bit-exact check.

Reproduces the Phase 2 headline claim (netlist filtered output == software model,
bit-for-bit on real audio) with an INDEPENDENT software FIR (not sw_fir.py), and
triangulates against sw_fir.py as a third witness. This mirrors the challenge's
own baseline check: sw_filter == hw_filter.

Modes:
  gen   <wav> <nframes> <coeffs.json>   -> stim_l.hex/stim_r.hex + rv_wav.json
  check <coeffs.json>                   -> compares netlist vs independent model
"""
import json, sys, wave
from array import array

def load_h(p): return [int(x) for x in json.load(open(p))["coeffs_q15"]]
def s16(x):
    x &= 0xFFFF; return x-0x10000 if x & 0x8000 else x
def sat16(v): return 32767 if v>32767 else (-32768 if v<-32768 else v)

def my_fir(x, h):                       # independent impl (own code)
    N=len(h); y=[]
    for n in range(len(x)):
        acc=0
        for k in range(N):
            if n-k>=0: acc += x[n-k]*h[k]
        y.append(sat16((acc + 0x4000) >> 15))   # round half toward +inf, then sat
    return y

if __name__=="__main__":
    mode=sys.argv[1]
    if mode=="gen":
        wav, nf, cj = sys.argv[2], int(sys.argv[3]), sys.argv[4]
        w=wave.open(wav,"rb"); a=array("h"); a.frombytes(w.readframes(w.getnframes()))
        if sys.byteorder=="big": a.byteswap()
        ch=w.getnchannels(); samp=list(a)[0::ch][:nf]        # left channel, nf samples
        with open("stim_l.hex","w") as f: f.write("\n".join("%04x"%(x&0xFFFF) for x in samp)+"\n")
        with open("stim_r.hex","w") as f: f.write("\n".join("%04x"%(x&0xFFFF) for x in samp)+"\n")
        json.dump({"nframes":len(samp),"wav":wav,"rate":w.getframerate(),"ch":ch},
                  open("rv_wav.json","w"))
        print("gen: wav=%s rate=%d ch=%d nframes=%d" % (wav,w.getframerate(),ch,len(samp)))
    elif mode=="check":
        h=load_h(sys.argv[2] if len(sys.argv)>2 else "recovered/coeffs.json")
        plan=json.load(open("rv_wav.json"))
        L=[s16(int(x,16)) for x in open("stim_l.hex").read().split()]
        cap=[ln.split() for ln in open("capture.txt").read().split("\n") if ln.strip()]
        SDOUT={}; nf=0
        for f,p,ws,sdin,sdout in cap:
            g=int(f)*32+int(p); SDOUT[g]=int(sdout); nf=max(nf,int(f)+1)
        def word(d,s,msb=True): return sum((d.get(s+i,0)<<(15-i if msb else i)) for i in range(16))
        def outL(f): return s16(word(SDOUT,f*32+0))
        def outR(f): return s16(word(SDOUT,f*32+16))
        best=None
        for lat in range(0,7):
            m=sum(1 for f in range(lat,min(nf,len(L))) if outR(f)==(L[f-lat] if f-lat>=0 else 0))
            t=min(nf,len(L))-lat
            if best is None or m/t>best[0]: best=(m/t,lat)
        lat=best[1]; print("echo LAT=%d (echo match %.4f)"%(lat,best[0]))
        nl=[outL(n+lat) for n in range(len(L)) if n+lat<nf]
        Lc=L[:len(nl)]
        mine=my_fir(Lc,h)
        # triangulate with sw_fir.py
        import importlib.util, os
        sw_path=os.path.join(os.path.dirname(sys.argv[0]) if os.path.dirname(sys.argv[0]) else ".","..","..","scripts","sw_fir.py")
        swy=None
        try:
            spec=importlib.util.spec_from_file_location("sw_fir", sys.argv[3] if len(sys.argv)>3 else sw_path)
            sw=importlib.util.module_from_spec(spec); spec.loader.exec_module(sw)
            swy=sw.fir_filter(Lc,h)
        except Exception as e:
            print("(sw_fir.py triangulation skipped: %s)"%e)
        mm_nl_mine=[(n,nl[n],mine[n]) for n in range(len(nl)) if nl[n]!=mine[n]]
        print("\n== REAL-AUDIO BIT-EXACT (%d samples) =="%len(nl))
        print("  netlist vs INDEPENDENT model : %d/%d exact (%d mismatch)"
              %(len(nl)-len(mm_nl_mine),len(nl),len(mm_nl_mine)))
        if mm_nl_mine[:3]: print("     e.g.",mm_nl_mine[:3])
        if swy is not None:
            mm2=sum(1 for n in range(len(nl)) if nl[n]!=swy[n])
            mm3=sum(1 for n in range(len(nl)) if mine[n]!=swy[n])
            print("  netlist vs sw_fir.py         : %d/%d exact (%d mismatch)"%(len(nl)-mm2,len(nl),mm2))
            print("  my model vs sw_fir.py        : %d/%d exact (%d mismatch)"%(len(nl)-mm3,len(nl),mm3))
        print("  sample stats: in[min/max]=%d/%d out[min/max]=%d/%d"
              %(min(Lc),max(Lc),min(nl),max(nl)))
        print("\nRESULT:", "BIT-EXACT (netlist==independent model on real audio)"
              if not mm_nl_mine else "MISMATCH FOUND")
