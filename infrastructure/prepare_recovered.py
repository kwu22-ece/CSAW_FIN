"""Snapshot committed Phase 2 inputs and prepare a repeatable recovered-design run."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
from toolchain import ROOT, sha256
from vectors import generate, from_wav
from results import write_samples

INPUTS=['recovered/rtl/fir_audio_top.v','recovered/coeffs.json','scripts/sw_fir.py',
        'handoffs/phase-02/codex-interface-handoff.v1.md',
        'handoffs/phase-02/codex-interface-handoff.v2.md',
        'handoffs/phase-02/reference_vectors.csv']


def prepare(source_root,ref,output):
    commit=subprocess.check_output(['git','rev-parse','--verify',ref+'^{commit}'],cwd=source_root,text=True).strip()
    output=output.resolve(); output.mkdir(parents=True,exist_ok=False)
    provenance={}
    for name in INPUTS:
        data=subprocess.check_output(['git','show',commit+':'+name],cwd=source_root)
        dest=output/name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
        provenance[name]=sha256(dest)
    vectors=output/'vectors'; vectors.mkdir()
    cases=[]
    def add(name,samples,expected=None,half_period=500):
        # Two flush frames expose the last two pipeline outputs. Compare every word.
        values=[v for v in samples+[0,0] for _ in range(2)]
        path=vectors/(name+'-input.csv'); write_samples(path,values)
        case={'name':name,'input_csv':str(path),'parameters':{'HALF_PERIOD_NS':half_period}}
        if expected is not None:
            path=vectors/(name+'-expected.csv')
            write_samples(path,[0,0,0,0]+[v for pair in zip(expected,samples) for v in pair])
            case['expected_csv']=str(path)
        cases.append(case)
    with (output/INPUTS[-1]).open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    if [int(r['n']) for r in rows] != list(range(len(rows))): raise ValueError('Non-contiguous supplied vector indices')
    samples=[int(r['x_in_int16']) for r in rows]
    expected=[int(r['y_filtered_int16']) for r in rows]
    add('supplied-vectors-1mhz',samples,expected)
    add('supplied-vectors-625khz',samples,expected,800)
    for kind in ('edges','impulse','random','sine','silence'):
        add('model-'+kind,generate(kind,256,16,2026))
    audio=ROOT/'what_a_piece_of_work-noisy.wav'
    values,_=from_wav(audio,16,1024)
    add('model-provided-audio',values[::2])
    provenance['input_wav_sha256']=sha256(audio)
    own=ROOT/'infrastructure'
    model=output/'scripts/sw_fir.py'; coeffs=output/'recovered/coeffs.json'
    sources=[str(output/'recovered/rtl/fir_audio_top.v'),str(own/'adapters/recovered.sv')]
    config={'schema_version':1,'name':'phase2-recovered-audio','kind':'verified_design','ready':True,
        'verification_evidence':[str(output/p) for p in INPUTS[3:5]]+[str(output/'provenance.json')],
        'simulation':{'sources':sources,'parameters':{'SAMPLE_BITS':16,'SLOT_BITS':16,'MSB_DELAY':1,
            'LEFT_LEVEL':0,'HALF_PERIOD_NS':500,'CLOCK_HALF_NS':50,'RESET_CYCLES':64},
            'reference_command':['{python}',str(own/'recovered_reference.py'),'--model',str(model),
                '--coefficients',str(coeffs),'--input','{input}','--output','{output}'],
            'reference_sources':[str(model),str(coeffs),str(own/'recovered_reference.py')]},
        'cases':cases,
        'build':{'sources':sources,'top':'phase4_audio_top','device':'up5k','package':'sg48',
            'frequency_mhz':10,'seed':1,'pcf':str(own/'constraints/recovered-audio.pcf'),
            'allow_unconstrained':False,'timeout_seconds':300}}
    (output/'manifest.json').write_text(json.dumps(config,indent=2)+'\n')
    (output/'provenance.json').write_text(json.dumps({'source_commit':commit,'sha256':provenance,
        'scope':'Phase 2 reconstruction and model, read-only committed snapshot; audio-only synthesis'},indent=2)+'\n')
    return output/'manifest.json'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--ref',default='HEAD')
    parser.add_argument('--output',type=Path,default=ROOT/'build/recovered-inputs')
    args=parser.parse_args()
    print(prepare(args.source_root,args.ref,args.output))


if __name__=='__main__': main()
