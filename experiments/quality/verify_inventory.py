"""Verify the manifest's portable source inventory, independent of checkout EOLs."""
import argparse
import hashlib
import json
from pathlib import Path

TEXT_SUFFIXES = {'.v', '.sv', '.py', '.md', '.json', '.csv', '.pcf'}
POLICY = 'SHA-256; listed text extensions normalize CRLF to LF; binary bytes unchanged'


def digest(path):
    raw = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        raw = raw.replace(b'\r\n', b'\n')
    return hashlib.sha256(raw).hexdigest()


def verify(manifest):
    m = json.loads(manifest.read_text(encoding='utf-8-sig'))
    if m.get('source_sha256_encoding') != POLICY:
        raise ValueError('Manifest does not specify the quality inventory encoding')
    rows = []
    for relative, expected in m['source_sha256'].items():
        actual = digest(manifest.parent/relative)
        rows.append({'path':relative,'expected':expected,'actual':actual,'passed':actual==expected})
    return {'passed':bool(rows) and all(r['passed'] for r in rows),
        'encoding':POLICY,'entries':len(rows),'failures':sum(not r['passed'] for r in rows),'results':rows}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(); r=verify(a.manifest)
    a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in r.items() if k!='results'}))
    raise SystemExit(0 if r['passed'] else 1)
