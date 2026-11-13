"""Reproduce the complete quality suite with fresh outputs and exact commands."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    commands = []

    def run(*args):
        argv = [sys.executable, *map(str, args)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        log = out / ('command-%02d.log' % len(commands))
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
        commands.append({'argv': argv, 'exit_code': result.returncode, 'log': log.name})
        (out/'commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
        print(f'{result.returncode}: {args[0]}', flush=True)
        if result.returncode: raise SystemExit(result.returncode)

    package = 'experiments/phase05/05b-astra'
    run('experiments/quality/verify_inventory.py', '--manifest', ROOT/package/'manifest.json',
        '--output', out/'inventory-audit.json')
    run('infrastructure/prepare_recovered.py', '--source-root', ROOT,
        '--ref', '1befb30e99a506698c45d4ca9394a3c7ec95c966', '--output', out/'recovered')
    run('experiments/quality/prepare.py', '--output', out/'vectors', '--recovered', out/'recovered')
    for mode, manifest, target in [
        ('validate', ROOT/package/'manifest.json', 'standard'),
        ('sim', out/'vectors/common.json', 'common'),
        ('sim', out/'vectors/directed.json', 'directed'),
        ('build', out/'vectors/baseline-build.json', 'baseline-build')]:
        run('infrastructure/run.py', '--suite', a.suite, mode, '--manifest', manifest, '--output', out/target)
    run('experiments/quality/audit_directed.py', '--run', out/'directed',
        '--specs', out/'vectors/directed-specs.json', '--output', out/'directed-audit.json')
    run(package+'/tests/audit_results.py', '--run', out/'standard', '--output', out/'standard-audit.json')
    run(package+'/tests/prepare_full_audio.py')
    run('infrastructure/run.py', '--suite', a.suite, 'sim', '--manifest',
        ROOT/package/'tests/full_audio_manifest.json', '--output', out/'full-audio')
    run(package+'/tests/audit_full_audio.py', '--run', out/'full-audio', '--summary',
        ROOT/package/'reports/full-audio-vectors/source-summary.json', '--output', out/'audio-audit.json')


if __name__ == '__main__':
    main()
