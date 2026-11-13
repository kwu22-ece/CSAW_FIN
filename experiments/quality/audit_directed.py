"""Independently verify exact raw/filtered windows in serial-output captures."""
import argparse
import json
import sys
from pathlib import Path
from prepare import ROOT, PACKAGE, baseline, dump
sys.path.insert(0, str(ROOT / 'infrastructure'))
from results import read_samples


def audit(run, specs_path):
    coeffs = baseline.load_coeffs(str(PACKAGE / 'tests/reference/coeffs.json'))
    results = []
    for spec in json.loads(specs_path.read_text()):
        directory = run / spec['name']
        raw = read_samples(directory / 'input.csv')
        actual = read_samples(directory / 'actual.csv')
        assert len(raw) == len(actual) and len(raw) % 2 == 0
        assert all(r['channel'] == i % 2 for i, r in enumerate(actual))
        samples = [r['value'] for r in raw[::2]]
        filtered = baseline.fir(samples, coeffs)
        active = set(n for h in spec['completion_input_frames'] for n in range(h, h+128))
        mismatches = []; changed = []; right_bad = 0
        for frame in range(len(samples)):
            n = frame - 2
            normal = filtered[n] if n >= 0 else 0
            echo = samples[n] if n >= 0 else 0
            expected = echo if n in active else normal
            if actual[2*frame]['value'] != expected: mismatches.append(frame)
            if actual[2*frame]['value'] != normal: changed.append(n)
            right_bad += actual[2*frame+1]['value'] != echo
        exact_window = set(changed) == active
        results.append({**spec, 'passed': not mismatches and not right_bad and exact_window,
            'left_mismatches': len(mismatches), 'right_mismatches': right_bad,
            'changed_left_words': len(changed), 'exact_windows_verified': exact_window})
    return {'passed': all(c['passed'] for c in results), 'cases': results,
            'passed_cases': sum(c['passed'] for c in results), 'total_cases': len(results)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--specs', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.run, args.specs)
    dump(args.output, result)
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}))
    raise SystemExit(0 if result['passed'] else 1)
