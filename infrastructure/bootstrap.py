"""Install a checksum-pinned official OSS CAD Suite, without changing system PATH."""
import argparse
import hashlib
import json
import pathlib
import platform
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=pathlib.Path, default=pathlib.Path('.tools'))
    args = parser.parse_args()
    key = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'darwin'}[platform.system()]
    key += '-arm64' if platform.machine().lower() in ('arm64', 'aarch64') else '-x64'
    lock = json.loads(pathlib.Path(__file__).with_name('toolchain-lock.json').read_text())
    if key not in lock['platforms']:
        parser.error(f'No reviewed archive for {key}; use OSS_CAD_SUITE or add an upstream digest to the lock.')
    entry = lock['platforms'][key]
    dest = args.destination.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / 'oss-cad-suite').exists():
        parser.error('Destination already contains oss-cad-suite; choose a fresh destination.')
    archive = dest / entry['url'].rsplit('/', 1)[-1]
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        print(f'Downloading {entry["url"]}', flush=True)
        urllib.request.urlretrieve(entry['url'], partial)
        partial.replace(archive)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != entry['sha256']:
        raise SystemExit(f'SHA256 mismatch for {archive}: {digest}')
    with tarfile.open(archive) as bundle:
        bundle.extractall(dest, filter='data')
    (dest / 'installation.json').write_text(json.dumps({**entry, 'release': lock['release']}, indent=2))
    print(f'Installed {dest / "oss-cad-suite"}; run python infrastructure/run.py doctor')


if __name__ == '__main__':
    main()
