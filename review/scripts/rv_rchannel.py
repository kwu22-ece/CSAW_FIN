#!/usr/bin/env python3
"""Subphase-R gap-closer: is the RIGHT input channel truly ignored?

All prior tests (and the real bridge) send L==R. This drives L and R with
DIFFERENT data and checks that (a) output-left == FIR(L) regardless of R, and
(b) output-right == L delayed (echo of LEFT), i.e. right input influences nothing.

gen   <wav> <n> <coeffs.json>   ; check <coeffs.json>
"""
import json, sys, wave
from array import array
def load_h(p): return [int(x) for x in json.load(open(p))["coeffs_q15"]]
def s16(x): x&=0xFFFF; return x-0x10000 if x&0x8000 else x
def sat16(v): return 32767 if v>32767 else (-32768 if v<-32768 else v)
def fir(x,h):
    N=len(h); o=[]
    for n in range(len(x)):
        o.append(sat16((sum((x[n-k] if n-k>=0 else 0)*h[k] for k in range(N))+(1<<14))>>15))
    return o

if __name__=="__main__":
    if sys.argv[1]=="gen":
        wav,n,cj=sys.argv[2],int(sys.argv[3]),sys.argv[4]
        w=wave.open(wav,"rb"); a=array("h"); a.frombytes(w.readframes(w.getnframes()))
        if sys.byteorder=="big": a.byteswap()
        ch=w.getnchannels(); L=list(a)[0::ch][:n]
        # R deliberately DIFFERENT from L: negate + offset (still in range), reversed
        R=[sat16(-v if v!=-32768 else 32767) for v in L][::-1]
        with open("stim_l.hex","w") as f: f.write("\n".join("%04x"%(v&0xFFFF) for v in L)+"\n")
        with open("stim_r.hex","w") as f: f.write("\n".join("%04x"%(v&0xFFFF) for v in R)+"\n")
        json.dump({"n":len(L)},open("rv_rc.json","w"))
        print("gen: n=%d (L and R differ: R=reversed(-L))"%len(L))
    else:
        h=load_h(sys.argv[2]);
        L=[s16(int(x,16)) for x in open("stim_l.hex").read().split()]
        R=[s16(int(x,16)) for x in open("stim_r.hex").read().split()]
        cap=[ln.split() for ln in open("capture.txt").read().split("\n") if ln.strip()]
        SD={}; nf=0
        for f,p,ws,sdin,sdout in cap:
            SD[int(f)*32+int(p)]=int(sdout); nf=max(nf,int(f)+1)
        def word(s): return sum(SD.get(s+i,0)<<(15-i) for i in range(16))
        def oL(f): return s16(word(f*32));
        def oR(f): return s16(word(f*32+16))
        lat=2
        nl=[oL(n+lat) for n in range(len(L)) if n+lat<nf]
        er=[oR(n+lat) for n in range(len(L)) if n+lat<nf]
        Lc=L[:len(nl)]; Rc=R[:len(nl)]
        mdlL=fir(Lc,h)
        mm_filt=sum(1 for n in range(len(nl)) if nl[n]!=mdlL[n])
        mm_echo=sum(1 for n in range(len(er)) if er[n]!=Lc[n])
        # would R matter? compare echo to R and filtered to FIR(R)
        mdlR=fir(Rc,h)
        echo_is_R=sum(1 for n in range(len(er)) if er[n]==Rc[n])
        filt_is_FIRR=sum(1 for n in range(len(nl)) if nl[n]==mdlR[n])
        print("frames=%d"%len(nl))
        print("filtered-left == FIR(LEFT)  : %d/%d mismatch=%d"%(len(nl)-mm_filt,len(nl),mm_filt))
        print("echo-right     == LEFT input: %d/%d mismatch=%d"%(len(er)-mm_echo,len(er),mm_echo))
        print("(control) echo-right == RIGHT input: %d/%d  [expect ~0 since R!=L]"%(echo_is_R,len(er)))
        print("(control) filtered == FIR(RIGHT)    : %d/%d  [expect ~0 since R!=L]"%(filt_is_FIRR,len(nl)))
        print("RESULT:", "RIGHT CHANNEL IGNORED (filtered=FIR(L), echo=L)" if mm_filt==0 and mm_echo==0
              else "RIGHT CHANNEL AFFECTS OUTPUT — investigate")
