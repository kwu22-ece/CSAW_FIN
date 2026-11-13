"""One-command simulation, comparison, and iCE40 build validation (Python 3.11+)."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

from results import compare, read_samples, write_report
from toolchain import ROOT, Toolchain, sha256
from vectors import generate, from_wav, write_vectors


class Blocked(RuntimeError):
    pass


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', value):
        raise ValueError(f'Invalid HDL identifier: {value!r}')
    return value


def source_path(base, value):
    path = (base / value).resolve()
    if not path.is_file(): raise Blocked(f'Required input missing: {path}')
    return path


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2), encoding='utf-8')


def input_hashes(paths):
    return {str(p): sha256(p) for p in paths}


def stage_runtime_files(base, spec, output):
    evidence = {}
    for name, source in spec.get('runtime_files', {}).items():
        destination = (output/name).resolve()
        if not destination.is_relative_to(output.resolve()) or destination.exists():
            raise ValueError(f'Unsafe or duplicate runtime file destination: {name}')
        path = source_path(base,source)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        evidence.update(input_hashes([path]))
    return evidence


def simulate(tc, base, spec, case, output, waves):
    output.mkdir(parents=True)
    params = {'SAMPLE_BITS': 16, 'SLOT_BITS': 32, 'MSB_DELAY': 1, 'LEFT_LEVEL': 0,
              'HALF_PERIOD_NS': 500, 'CLOCK_HALF_NS': 50, 'RESET_CYCLES': 10}
    overrides = {**spec.get('parameters', {}), **case.get('parameters', {})}
    if set(overrides)-set(params): raise ValueError(f'Unknown parameters: {set(overrides)-set(params)}')
    params.update(overrides)
    if any(type(v) is not int for v in params.values()): raise ValueError('Parameters must be integers')
    bits = params['SAMPLE_BITS']
    if not 2 <= bits <= 32: raise ValueError('SAMPLE_BITS must be 2..32')
    evidence = stage_runtime_files(base,spec,output)
    if 'input_csv' in case:
        path = source_path(base, case['input_csv'])
        rows = read_samples(path)
        if any(r['channel'] != i % 2 for i,r in enumerate(rows)):
            raise ValueError('Input CSV must alternate left/right starting with left')
        values = [r['value'] for r in rows]
        evidence.update(input_hashes([path]))
    elif 'input_wav' in case:
        path = source_path(base, case['input_wav'])
        values, audio = from_wav(path, bits, case.get('frames'))
        evidence.update(input_hashes([path]))
        save_json(output/'audio-input.json', audio)
    else:
        values = generate(case.get('stimulus', 'edges'), case.get('frames', 64), bits, case.get('seed', 1))
    if len(values) > 131072: raise ValueError('Input exceeds MAX_WORDS=131072; split it into cases')
    vector_path, input_csv = write_vectors(output, values, bits)
    if spec.get('fixture_reference') == 'identity':
        reference = input_csv
    elif 'expected_csv' in case:
        reference = source_path(base, case['expected_csv'])
    elif spec.get('reference_command'):
        # argv only, no shell. Explicit contract: model reads {input}, writes {output}.
        reference = output/'expected.csv'
        argv = [str(a).replace('{python}', sys.executable).replace('{input}', str(input_csv))
                .replace('{output}', str(reference)) for a in spec['reference_command']]
        tc.run(argv, base, output/'reference.log', spec.get('timeout_seconds', 120))
        if not reference.is_file(): raise RuntimeError('Reference command did not write expected.csv')
    else:
        raise Blocked('No verified expected_csv or reference_command supplied')
    evidence.update(input_hashes([reference]))
    sources = [ROOT/'infrastructure/hdl'/n for n in ('i2s_driver.sv','i2s_monitor.sv','tb_i2s.sv')]
    sources += [source_path(base, p) for p in spec['sources']]
    evidence.update(input_hashes(sources))
    evidence.update(input_hashes([source_path(base,p) for p in spec.get('reference_sources', [])]))
    save_json(output/'inputs.json', {'sha256': evidence, 'parameters': params, 'case': case})
    binary = output/'simulation.vvp'
    cmd = [tc.find('iverilog'), '-g2012', '-Wall', '-s', 'tb_i2s', '-o', binary]
    for key, value in params.items(): cmd += [f'-Ptb_i2s.{key}={value}']
    for directory in spec.get('include_dirs', []): cmd += ['-I', str((base/directory).resolve())]
    cmd += sources
    tc.run(cmd, output, output/'compile.log', spec.get('timeout_seconds',120))
    cmd = [tc.find('vvp'), binary, f'+VECTORS={vector_path}', f'+CAPTURE={output / "actual.csv"}',
           f'+WORDS={len(values)}']
    if waves != 'none': cmd += [f'+WAVE={output / ("wave."+waves)}']
    if waves == 'fst': cmd += ['-fst']
    log = tc.run(cmd, output, output/'simulation.log', spec.get('timeout_seconds',120))
    if f'PHASE4_SIM_PASS words={len(values)}' not in log: raise RuntimeError('Simulation completion marker missing')
    if waves != 'none' and not (output/('wave.'+waves)).is_file(): raise RuntimeError('Requested waveform missing')
    result = compare(reference, output/'actual.csv', case.get('tolerance',0), case.get('latency_words',0), bits)
    save_json(output/'comparison.json', result)
    if not result['passed']: raise RuntimeError(f'{result["mismatch_count"]} numerical/channel mismatches; see {output / "comparison.json"}')
    return f'{result["samples_compared"]} samples, max error {result["max_abs_error"]}'


def yosys_quote(path):
    value = str(path).replace('\\', '/')
    if any(c in value for c in ['"','\n','\r']): raise ValueError('Unsupported path character')
    return '"'+value+'"'


def build(tc, base, spec, output):
    output.mkdir(parents=True)
    top = identifier(spec['top'])
    device = spec.get('device', 'up5k')
    if device not in ('up5k','u4k','hx1k','hx4k','hx8k','lp1k','lp4k','lp8k'):
        raise ValueError('Unsupported iCE40 device')
    package = spec['package']
    if not re.fullmatch(r'[A-Za-z0-9:_-]+', package): raise ValueError('Invalid package')
    frequency = float(spec.get('frequency_mhz',10))
    if not math.isfinite(frequency) or frequency <= 0: raise ValueError('Invalid clock frequency')
    seed = spec.get('seed',1)
    if type(seed) is not int or seed < 0: raise ValueError('Invalid nextpnr seed')
    sources = [source_path(base,p) for p in spec['sources']]
    pcf = source_path(base,spec['pcf']) if spec.get('pcf') else None
    if not pcf and not spec.get('allow_unconstrained', False):
        raise Blocked('Build requires verified PCF or explicit allow_unconstrained=true for an experimental build')
    runtime_evidence = stage_runtime_files(base,spec,output)
    include_flags = ''.join(' -I'+yosys_quote((base/p).resolve()) for p in spec.get('include_dirs',[]))
    script = 'read_verilog -sv' + include_flags + ' ' + ' '.join(yosys_quote(p) for p in sources) + '\n'
    for key,value in spec.get('parameters',{}).items():
        if type(value) is not int: raise ValueError('Synthesis parameters must be integers')
        script += f'chparam -set {identifier(key)} {value} {top}\n'
    script += f'hierarchy -check -top {top}\nsynth_ice40 -top {top} -json netlist.json\ncheck -assert\ntee -o utilization.json stat -json\n'
    (output/'synthesis.ys').write_text(script,encoding='utf-8')
    save_json(output/'inputs.json', {'sha256': {**input_hashes(sources+([pcf] if pcf else [])),**runtime_evidence}, 'configuration':spec})
    timeout = spec.get('timeout_seconds',300)
    tc.run([tc.find('yosys'),'-s','synthesis.ys'],output,output/'synthesis.log',timeout)
    cmd = [tc.find('nextpnr-ice40'),f'--{device}','--package',package,'--json','netlist.json',
           '--asc','routed.asc','--freq',str(frequency),'--seed',str(seed),'--report','timing.json',
           '--detailed-timing-report']
    if pcf: cmd += ['--pcf',pcf]
    else: cmd += ['--pcf-allow-unconstrained']
    tc.run(cmd,output,output/'place-route.log',timeout)
    timing = json.loads((output/'timing.json').read_text())
    fmax = timing.get('fmax',{})
    if not fmax and spec.get('require_clock',True): raise RuntimeError('No clock timing reported')
    if any(data['achieved'] < data['constraint'] for data in fmax.values()):
        raise RuntimeError('Clock timing constraint not met')
    tc.run([tc.find('icepack'),'routed.asc','bitstream.bin'],output,output/'icepack.log',timeout)
    # Explicit -u avoids dependence on basename detection of uppercase .EXE on Windows.
    tc.run([tc.find('iceunpack'),'-u','bitstream.bin','unpacked.asc'],output,output/'iceunpack.log',timeout)
    tc.run([tc.find('icepack'),'unpacked.asc','roundtrip.bin'],output,output/'roundtrip.log',timeout)
    if sha256(output/'bitstream.bin') != sha256(output/'roundtrip.bin'):
        raise RuntimeError('IceStorm pack/unpack roundtrip differs')
    tc.run([tc.find('icetime'),'-d',device,'-c',str(frequency),'-t','-r','icetime.txt','routed.asc'],
           output,output/'icetime.log',timeout)
    result = {'passed':True, 'frequency_mhz':frequency,'fmax':fmax,'seed':seed,
              'utilization':timing.get('utilization',{}), 'constrained_pins':bool(pcf),
              'hardware_validated':False, 'bitstream_sha256':sha256(output/'bitstream.bin')}
    save_json(output/'build-summary.json',result)
    return f'{device}/{package}, timing met, pack/unpack roundtrip verified; hardware unverified'


def regression(tc, manifest, output, waves='none', mode='all'):
    base = manifest.parent
    config = json.loads(manifest.read_text(encoding='utf-8-sig'))
    cases = []
    if config.get('schema_version') != 1: raise ValueError('Unsupported manifest schema_version')
    if not config.get('ready',False):
        cases.append({'name':config.get('name','design'), 'status':'blocked',
                      'detail':config.get('awaiting','Verified design inputs are not supplied')})
    else:
        if config.get('kind') not in ('infrastructure_fixture','verified_design'):
            raise ValueError('kind must be infrastructure_fixture or verified_design')
        if config['kind'] == 'verified_design':
            if not config.get('verification_evidence'): raise Blocked('Verified design requires verification_evidence paths')
            for p in config['verification_evidence']: source_path(base,p)
            if config.get('simulation',{}).get('fixture_reference'):
                raise ValueError('Identity fixture reference cannot be used for a verified design')
        def execute(name, fn):
            if not re.fullmatch(r'[A-Za-z0-9_-]+',name): raise ValueError('Case names must be simple filenames')
            if any(c['name'] == name for c in cases): raise ValueError(f'Duplicate case name: {name}')
            try: case = {'name':name,'status':'passed','detail':fn()}
            except Blocked as exc: case = {'name':name,'status':'blocked','detail':str(exc)}
            except (OSError,ValueError,RuntimeError,KeyError) as exc: case = {'name':name,'status':'failed','detail':str(exc)}
            print(f'{case["status"].upper()}: {name}: {case["detail"]}',flush=True)
            cases.append(case)
        if mode in ('all','sim'):
            for case in config.get('cases',[]):
                execute(case['name'],lambda case=case: simulate(tc,base,config['simulation'],case,output/case['name'],waves))
        if mode in ('all','build') and config.get('build'):
            execute('fpga-build',lambda: build(tc,base,config['build'],output/'fpga-build'))
    if not cases: raise ValueError('No runnable cases/build selected')
    metadata = {'manifest':str(manifest),'manifest_sha256':sha256(manifest), 'kind':config.get('kind'),
                'timestamp_utc':datetime.now(timezone.utc).isoformat(), 'waves':waves}
    if config.get('ready') and config.get('verification_evidence'):
        metadata['verification_evidence']=input_hashes([source_path(base,p) for p in config['verification_evidence']])
    try:
        metadata['git_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        metadata['git_status']=subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError): pass
    metadata['toolchain']=tc.doctor()
    report = write_report(output,cases,metadata)
    print(f'Report: {output / "report.json"}',flush=True)
    return 1 if report['failures'] else 2 if report['blocked'] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',type=Path,help='OSS CAD Suite root (or OSS_CAD_SUITE env var)')
    sub = parser.add_subparsers(dest='command',required=True)
    doc = sub.add_parser('doctor',help='Probe dependencies and capture versions/executable hashes')
    doc.add_argument('--output',type=Path)
    for name in ('sim','build','regress','validate'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--manifest',type=Path,default=ROOT/'infrastructure/configs/smoke.json')
        cmd.add_argument('--output',type=Path,help='New run directory; existing paths are refused')
        cmd.add_argument('--waves',choices=('none','vcd','fst'),default='none')
    cmp = sub.add_parser('compare')
    cmp.add_argument('expected',type=Path); cmp.add_argument('actual',type=Path)
    cmp.add_argument('--tolerance',type=int,default=0); cmp.add_argument('--latency-words',type=int,default=0)
    cmp.add_argument('--sample-bits',type=int,default=16)
    args = parser.parse_args()
    tc = Toolchain(args.suite)
    try:
        if args.command == 'doctor':
            result = tc.doctor()
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True); save_json(args.output,result)
            print(json.dumps(result,indent=2)); return 0 if result['passed'] else 1
        if args.command == 'compare':
            result = compare(args.expected,args.actual,args.tolerance,args.latency_words,args.sample_bits)
            print(json.dumps(result,indent=2)); return 0 if result['passed'] else 1
        output = (args.output or ROOT/'build'/('phase04-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])).resolve()
        output.mkdir(parents=True,exist_ok=False)
        if args.command == 'validate':
            tc.run([sys.executable,'-m','unittest','discover','-s','infrastructure/tests','-v'],ROOT,output/'unit-tests.log')
        return regression(tc,args.manifest.resolve(),output,args.waves,{'sim':'sim','build':'build'}.get(args.command,'all'))
    except Blocked as exc:
        print(f'BLOCKED: {exc}',file=sys.stderr); return 2
    except (OSError,ValueError,RuntimeError,KeyError) as exc:
        print(f'FAILED: {exc}',file=sys.stderr); return 1


if __name__ == '__main__':
    sys.exit(main())
