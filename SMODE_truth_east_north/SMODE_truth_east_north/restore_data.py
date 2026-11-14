"""Reassemble the original NetCDF files without changing any bytes.

First run `git lfs pull` from the repository root, then run this script.
Only Python's standard library is required. Existing originals are verified.
"""
import hashlib
import json
from pathlib import Path


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def restore(root):
    manifest = json.loads((root / 'large-files.json').read_text(encoding='utf-8-sig'))
    for record in manifest['files']:
        names = [record['name']] + [part['name'] for part in record['parts']]
        if any(Path(name).name != name or name in ('.', '..') or '/' in name or '\\' in name for name in names):
            raise ValueError('Manifest contains an invalid filename')
        target = root / record['name']
        if target.exists():
            if target.stat().st_size == record['size'] and digest(target) == record['sha256']:
                print('Already verified:', target.name)
                continue
            raise RuntimeError(f'Existing file differs; refusing to overwrite: {target}')
        # Validate every part before producing an output. LFS pointer files fail here.
        for part in record['parts']:
            path = root / part['name']
            if not path.exists() or path.stat().st_size != part['size'] or digest(path) != part['sha256']:
                raise RuntimeError(f'Missing or damaged part: {path.name}. Run git lfs pull first.')
        temporary = target.with_name(target.name + '.restoring')
        total = hashlib.sha256()
        try:
            with temporary.open('xb') as output:
                for part in record['parts']:
                    with (root / part['name']).open('rb') as stream:
                        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                            output.write(block)
                            total.update(block)
            if temporary.stat().st_size != record['size'] or total.hexdigest() != record['sha256']:
                raise RuntimeError(f'Restored checksum mismatch: {target.name}')
            temporary.rename(target)
        except Exception:
            # Leave incomplete output for inspection; never replace an original.
            raise
        print('Restored and verified:', target.name)


if __name__ == '__main__':
    restore(Path(__file__).resolve().parent)
