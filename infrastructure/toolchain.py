"""Explicit tool resolution and logged, bounded subprocess execution."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
PROBES = {
    'iverilog': ['-V'], 'vvp': ['-V'], 'yosys': ['-V'],
    'nextpnr-ice40': ['--version'], 'icepack': ['-h'], 'iceunpack': ['-h'],
    'icetime': ['-h'], 'verilator': ['--version'],
}
REQUIRED = {'iverilog', 'vvp', 'yosys', 'nextpnr-ice40', 'icepack', 'iceunpack', 'icetime'}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Toolchain:
    def __init__(self, suite=None):
        self.env = dict(os.environ)
        selected = suite or os.environ.get('OSS_CAD_SUITE')
        self.suite = Path(selected).resolve() if selected else ROOT / '.tools/oss-cad-suite'
        if selected and not (self.suite / 'bin').is_dir():
            raise ValueError(f'Invalid OSS CAD Suite directory: {self.suite}')
        if (self.suite / 'bin').is_dir():
            self.env['OSS_CAD_SUITE'] = str(self.suite)
            paths = [self.suite / 'bin', self.suite / 'lib']
            self.env['PATH'] = os.pathsep.join(map(str, paths)) + os.pathsep + self.env.get('PATH', '')

    def find(self, name):
        path = shutil.which(name, path=self.env['PATH'])
        if not path and name == 'verilator' and os.name == 'nt':
            path = shutil.which('verilator_bin', path=self.env['PATH'])
        if not path:
            raise FileNotFoundError(f'{name} unavailable: run infrastructure/bootstrap.py or set OSS_CAD_SUITE')
        return path

    def run(self, argv, cwd, log, timeout=120):
        argv = [str(a) for a in argv]
        started = time.monotonic()
        record = {'argv': argv, 'cwd': str(cwd), 'timeout_seconds': timeout}
        output = ''
        try:
            result = subprocess.run(argv, cwd=cwd, env=self.env, capture_output=True,
                                    text=True, errors='replace', timeout=timeout, check=False)
            output = result.stdout + result.stderr
            record['exit_code'] = result.returncode
        except subprocess.TimeoutExpired as exc:
            def decode(value):
                return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
            output = decode(exc.stdout) + decode(exc.stderr)
            record.update(exit_code=None, error='timeout')
        except OSError as exc:
            record.update(exit_code=None, error=str(exc))
        record['elapsed_seconds'] = round(time.monotonic() - started, 3)
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(output, encoding='utf-8')
        record['log_sha256'] = sha256(log)
        log.with_suffix(log.suffix + '.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        if record['exit_code'] != 0:
            raise RuntimeError(f'Command failed ({record.get("error", record["exit_code"])}): {argv}; see {log}')
        return output

    def doctor(self):
        report = {}
        for name, flags in PROBES.items():
            try:
                path = self.find(name)
                result = subprocess.run([path, *flags], env=self.env, capture_output=True,
                                        text=True, errors='replace', timeout=20, check=False)
                output = (result.stdout + result.stderr).strip()
                # IceStorm help intentionally returns nonzero on several builds.
                healthy = result.returncode == 0 or (name in {'icepack', 'iceunpack', 'icetime'}
                                                     and 'Usage:' in output and result.returncode == 1)
                report[name] = {'path': path, 'available': healthy, 'exit_code': result.returncode,
                                'probe': output[:4000], 'sha256': sha256(path)}
            except (OSError, subprocess.TimeoutExpired) as exc:
                report[name] = {'available': False, 'error': str(exc)}
            report[name]['required'] = name in REQUIRED
        return {'tools': report, 'passed': all(report[n]['available'] for n in REQUIRED)}
