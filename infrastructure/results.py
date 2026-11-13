"""Strict signed-sample CSV comparison and machine-readable regression reports."""
import csv
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def read_samples(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['index', 'channel', 'value']:
            raise ValueError(f'{path}: expected index,channel,value header')
        rows = []
        for n, row in enumerate(reader):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'{path}: malformed row {n}')
            item = {k: int(v, 10) for k, v in row.items()}
            if item['index'] != n or item['channel'] not in (0, 1):
                raise ValueError(f'{path}: nonsequential index or invalid channel at {n}')
            rows.append(item)
    if not rows:
        raise ValueError(f'{path}: empty sample capture')
    return rows


def write_samples(path, samples):
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['index', 'channel', 'value'])
        for i, value in enumerate(samples):
            writer.writerow([i, i % 2, value])


def compare(expected, actual, tolerance=0, latency_words=0, sample_bits=16):
    if any(type(v) is not int for v in (tolerance, latency_words, sample_bits)) or tolerance < 0 or latency_words < 0 or not 2 <= sample_bits <= 32:
        raise ValueError('Invalid tolerance, latency_words, or sample_bits')
    ref, got = read_samples(expected), read_samples(actual)
    low, high = -(1 << (sample_bits-1)), (1 << (sample_bits-1))-1
    if any(not low <= row['value'] <= high for row in ref + got):
        raise ValueError(f'Sample outside signed {sample_bits}-bit range')
    if len(got) != len(ref) + latency_words:
        raise ValueError(f'Length mismatch: expected {len(ref)} + latency {latency_words}, got {len(got)}')
    errors, mismatches = [], []
    for i, (a, b) in enumerate(zip(ref, got[latency_words:])):
        error = b['value'] - a['value']
        errors.append(error)
        if a['channel'] != b['channel'] or abs(error) > tolerance:
            if len(mismatches) < 20:
                mismatches.append({'reference_index': i, 'actual_index': i+latency_words,
                                   'expected': a, 'actual': b, 'error': error})
    count = sum(a['channel'] != b['channel'] or abs(b['value']-a['value']) > tolerance
                for a, b in zip(ref, got[latency_words:]))
    return {'passed': count == 0, 'samples_compared': len(ref), 'mismatch_count': count,
            'max_abs_error': max(map(abs, errors)),
            'rmse': math.sqrt(sum(e*e for e in errors)/len(errors)),
            'tolerance': tolerance, 'latency_words': latency_words, 'sample_bits': sample_bits,
            'first_mismatches': mismatches}


def write_report(directory, cases, metadata=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    failures = sum(c['status'] == 'failed' for c in cases)
    blocked = sum(c['status'] == 'blocked' for c in cases)
    report = {'passed': bool(cases) and failures == 0 and blocked == 0,
              'failures': failures, 'blocked': blocked, 'cases': cases, 'metadata': metadata or {}}
    (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    suite = ET.Element('testsuite', name='phase04', tests=str(len(cases)), failures=str(failures),
                       skipped=str(blocked))
    lines = ['# Phase 4 execution report', '', '| Case | Status | Detail |', '|---|---|---|']
    for case in cases:
        node = ET.SubElement(suite, 'testcase', name=case['name'])
        detail = str(case.get('detail', '')).replace('|', '\\|').replace('\n', ' ')
        lines.append(f'| {case["name"]} | {case["status"]} | {detail} |')
        if case['status'] in ('failed', 'blocked'):
            ET.SubElement(node, 'failure' if case['status'] == 'failed' else 'skipped').text = detail
    ET.ElementTree(suite).write(directory / 'junit.xml', encoding='utf-8', xml_declaration=True)
    (directory / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return report
