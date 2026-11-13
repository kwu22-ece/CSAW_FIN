"""Collect compact evidence from actual reports; verify CSVs and source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import subprocess
from prepare import ROOT, PACKAGE, dump
sys.path.insert(0, str(ROOT / 'infrastructure'))
from results import compare


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(prefix, audio_dirs, source_commit):
    evidence = {}; suites = {}
    for source in [PACKAGE/'rtl/fir_audio_top.v', PACKAGE/'tests/candidate_reference.py']:
        committed = subprocess.check_output(['git', 'show',
            source_commit+':'+source.relative_to(ROOT).as_posix()], cwd=ROOT)
        assert committed.replace(b'\r\n',b'\n') == source.read_bytes().replace(b'\r\n',b'\n'), source
    def receipt(path):
        evidence[str(path.relative_to(ROOT))] = sha(path)
        return json.loads(path.read_text(encoding='utf-8-sig'))
    for name in ['validate', 'common', 'directed']:
        folder = ROOT/'build'/(prefix+'-'+name)
        r = receipt(folder/'report.json')
        suites[name] = {'passed': r['passed'], 'failures': r['failures'],
            'blocked': r['blocked'], 'cases': r['cases']}
        for case in r['cases']:
            if case['name'] == 'fpga-build': continue
            directory = folder/case['name']
            inputs = receipt(directory/'inputs.json')
            # Working-tree file hashes must still agree with the files compiled.
            for source in [PACKAGE/'rtl/fir_audio_top.v', PACKAGE/'rtl/phase4_dut.sv']:
                assert sha(source) == inputs['sha256'][str(source)], source
            comparison = receipt(directory/'comparison.json')
            case['samples_compared'] = comparison['samples_compared']
            case['mismatches'] = comparison['mismatch_count']
    build = receipt(ROOT/'build'/(prefix+'-validate')/'fpga-build/build-summary.json')
    unit_log = ROOT/'build'/(prefix+'-validate')/'unit-tests.log'
    unit_text = unit_log.read_text(encoding='utf-8')
    assert 'Ran 15 tests' in unit_text and unit_text.rstrip().endswith('OK')
    evidence[str(unit_log.relative_to(ROOT))] = sha(unit_log)
    summary = json.loads((PACKAGE/'reports/full-audio-vectors/source-summary.json').read_text())
    audio = []
    for segment in summary['segments']:
        candidates = [d/segment['case'] for d in audio_dirs if (d/segment['case']/'comparison.json').exists()]
        assert len(candidates) == 1, (segment['case'], candidates)
        d = candidates[0]
        c = receipt(d/'comparison.json'); sim = receipt(d/'simulation.log.json')
        inputs = receipt(d/'inputs.json')
        for source in [PACKAGE/'rtl/fir_audio_top.v', PACKAGE/'rtl/phase4_dut.sv']:
            assert sha(source) == inputs['sha256'][str(source)], source
        assert sim['exit_code'] == 0 and c['passed']
        expected = PACKAGE/segment['expected_path']
        assert sha(d/'input.csv') == segment['input_sha256']
        assert sha(expected) == segment['expected_sha256']
        assert compare(expected, d/'actual.csv')['passed']
        audio.append({'case':segment['case'], 'directory':str(d.relative_to(ROOT)),
            'passed':True,'compared_words':c['samples_compared'],'mismatches':c['mismatch_count']})
    return {'schema_version':1,'source_commit_sha':source_commit,
        'framework_tests_passed':15,'suite_results':suites,'build':build,'full_audio':{
            'source_frames':summary['source_frames_covered'],'reset_isolated_chunks':True,
            'trigger_hit_count':len(summary['trigger_completion_frames']),
            'overlap_frames':summary['chunk_overlap_frames'],'source_sha256':summary['source_sha256'],
            'compared_words':sum(x['compared_words'] for x in audio),
            'mismatches':sum(x['mismatches'] for x in audio),'segments':audio},
        'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [
            PACKAGE/'rtl/fir_audio_top.v', PACKAGE/'rtl/baseline/fir_audio_top.v',
            PACKAGE/'tests/candidate_reference.py',PACKAGE/'tests/reference/run_reference.py',
            PACKAGE/'tests/reference/coeffs.json',PACKAGE/'constraints/hackster.pcf']},
        'hardware_verification':'not_run; no matching Hackster/FTDI device found in local PnP enumeration',
        'evidence_sha256':evidence}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prefix',required=True)
    p.add_argument('--audio-dirs',type=Path,nargs='+',required=True)
    p.add_argument('--source-commit',required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists(): raise SystemExit('Refusing to overwrite a frozen evidence snapshot')
    result=collect(a.prefix,[d.resolve() for d in a.audio_dirs],a.source_commit)
    dump(a.output,result)
    print(json.dumps({'output':str(a.output),'full_audio_words':result['full_audio']['compared_words']}))
