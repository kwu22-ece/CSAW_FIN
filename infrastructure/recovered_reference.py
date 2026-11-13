"""CSV/framing adapter calling the supplied Phase 2 model without altering it."""
import argparse
import importlib.util
from pathlib import Path
from results import read_samples, write_samples


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--coefficients',type=Path,required=True)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--latency-frames',type=int,default=2)
    args=parser.parse_args()
    rows=read_samples(args.input)
    if len(rows)%2 or any(r['channel'] != i%2 for i,r in enumerate(rows)):
        raise ValueError('Expected complete alternating stereo frames')
    samples=[r['value'] for r in rows[::2]]
    if not 0 <= args.latency_frames < len(samples): raise ValueError('Invalid latency')
    spec=importlib.util.spec_from_file_location('supplied_phase2_model',args.model)
    model=importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
    filtered=model.fir_filter(samples,model.load_coeffs(str(args.coefficients)))
    if len(filtered) != len(samples): raise ValueError('Supplied model output length differs')
    output=[]
    for frame in range(len(samples)):
        n=frame-args.latency_frames
        output.extend([0,0] if n<0 else [filtered[n],samples[n]])
    write_samples(args.output,output)


if __name__=='__main__': main()
