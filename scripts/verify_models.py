"""Verify provisioned model files against the audited Lesson64 model manifest."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--embedding', type=Path, required=True)
    parser.add_argument('--reranker', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    manifest = json.loads((root / 'deploy/models.manifest.json').read_text())
    failed = False
    for kind in ('embedding', 'reranker'):
        directory = getattr(args, kind).expanduser()
        errors = []
        for name, expected in manifest[kind]['files'].items():
            path = directory / name
            if not path.is_file() or path.stat().st_size != expected['bytes']:
                errors.append(name)
                continue
            digest = hashlib.sha256()
            with path.open('rb') as data:
                for block in iter(lambda: data.read(4 * 1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != expected['sha256']:
                errors.append(name)
        failed |= bool(errors)
        print(f"{kind}: {'FAIL' if errors else 'PASS'} ({len(manifest[kind]['files'])} audited files)")
        for name in errors:
            print('  missing or mismatched: ' + name)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
