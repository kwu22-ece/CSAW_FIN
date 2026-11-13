"""Generate independent scheduled-window tests using the shared Phase 4 harness.

The expected activation frames are specified by each experiment, not obtained
from the candidate FSM/reference. FIR arithmetic is the unchanged Phase 3 model.
Run from the repository root after infrastructure/prepare_recovered.py.
"""
import argparse
import csv
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'experiments/phase05/05b-astra'
sys.path.insert(0, str(PACKAGE / 'tests'))
from reference import run_reference as baseline

MAGIC = [32512, -32511, 23100, -23101, 28050, -28051, -15556, 15555]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def write_csv(path, pairs):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['index', 'channel', 'value'])
        for n, pair in enumerate(pairs):
            for ch, value in enumerate(pair):
                writer.writerow([2*n+ch, ch, value])


def prepare(output, recovered):
    output.mkdir(parents=True, exist_ok=False)
    native = json.loads((PACKAGE / 'manifest.json').read_text(encoding='utf-8-sig'))
    sources = [str(PACKAGE / p) for p in native['simulation']['sources']]
    parameters = dict(native['simulation']['parameters'], RESET_CYCLES=64)
    common = {
        'schema_version': 1, 'name': 'quality-common', 'kind': 'verified_design',
        'ready': True, 'verification_evidence': [str(recovered / 'provenance.json')],
        'simulation': {'sources': sources, 'parameters': parameters}, 'cases': []}
    for rate in ['1mhz', '625khz']:
        name = 'supplied-vectors-' + rate
        common['cases'].append({'name': name,
            'input_csv': str(recovered / 'vectors' / (name+'-input.csv')),
            'expected_csv': str(recovered / 'vectors' / (name+'-expected.csv')),
            'parameters': {'HALF_PERIOD_NS': 500 if rate == '1mhz' else 800},
            'tolerance': 0, 'latency_words': 0})
    dump(output / 'common.json', common)
    build = dict(native['build'])
    build['sources'] = [str(PACKAGE / 'rtl/baseline/fir_audio_top.v')]
    build['pcf'] = str(PACKAGE / build['pcf'])
    dump(output / 'baseline-build.json', {**common, 'build': build, 'cases': []})

    coeffs = baseline.load_coeffs(str(PACKAGE / 'tests/reference/coeffs.json'))
    rng = random.Random(20261113)
    noise = [rng.randrange(-30000, 30001) for _ in range(500)]
    cases, specs = [], []

    def add(name, left, hits, right=None):
        right = right if right is not None else [-x for x in left]
        active = set(n for hit in hits for n in range(hit, hit+128))
        assert len(active) == 128*len(hits) and max(active, default=0)+2 < len(left)
        filtered = baseline.fir(left, coeffs)
        # Each raw/filtered distinction must be observable at every payload frame.
        assert all(left[n] != filtered[n] for n in active)
        expected = [(0, 0)] * 2 + [
            (x if n in active else filtered[n], x) for n, x in enumerate(left[:-2])]
        write_csv(output / (name+'.csv'), zip(left, right))
        write_csv(output / (name+'.expected.csv'), expected)
        for half, rate in [(500, '1mhz'), (800, '625khz')]:
            cases.append({'name': name+'-'+rate, 'input_csv': str(output/(name+'.csv')),
                'expected_csv': str(output/(name+'.expected.csv')),
                'parameters': {'HALF_PERIOD_NS': half}, 'tolerance': 0, 'latency_words': 0})
            specs.append({'name': name+'-'+rate, 'completion_input_frames': hits,
                'payload_frames': 128, 'latency_frames': 2,
                'expected_changed_left_words': len(active), 'expected_changed_right_words': 0})

    # First trigger completes at 15; bypass covers [15,142]. Detection must
    # resume at 143. Sequences starting inside the window must be ignored.
    for offset in [-7, -1, 0, 1, 2]:
        left = noise.copy(); left[8:16] = MAGIC
        start = 143+offset; left[start:start+8] = MAGIC
        add('retrigger-offset-'+str(offset), left, [15, start+7] if offset >= 0 else [15])
    for broken in range(8):
        left = noise.copy(); left[8:16] = MAGIC; left[8+broken] ^= 1
        add('near-miss-word-'+str(broken), left, [])
    left = noise.copy(); right = noise.copy(); right[8:16] = MAGIC
    add('right-slot-only', left, [], right)
    left = noise.copy(); left[8:12] = MAGIC[:4]; left[12:20] = MAGIC
    add('prefix-restart', left, [19])
    dump(output / 'directed.json', {**common, 'name': 'quality-boundary', 'cases': cases})
    dump(output / 'directed-specs.json', specs)
    print(json.dumps({'directed_cases': len(cases), 'common_cases': 2, 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovered', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.output.resolve(), args.recovered.resolve())
