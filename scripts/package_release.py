"""Create a local release ZIP from the reviewed file allowlist."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / 'RELEASE_FILES.json'


def members() -> list[tuple[str, Path]]:
    names = json.loads(ALLOWLIST.read_text(encoding='utf-8'))
    if not isinstance(names, list) or len(names) != len(set(names)):
        raise ValueError('Release allowlist must be a list of unique relative paths')
    results = []
    forbidden = {'.git', '.deployment', 'data', 'backups', 'models', 'archive', '__pycache__', 'deployment_logs', 'test-results'}
    for name in sorted(names):
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or forbidden.intersection(relative.parts):
            raise ValueError(f'Unsafe allowlist path: {name}')
        if relative.suffix not in {'.py', '.sh', '.md', '.txt', '.json', '.yml', '.conf'} and name not in {
            'Dockerfile', 'LICENSE', '.gitignore', '.dockerignore', '.env.example', '.env.docker.example'
        }:
            raise ValueError(f'Unexpected release file type: {name}')
        source = ROOT / relative
        if source.resolve() != source or not source.is_file():
            raise ValueError(f'Listed file is absent or uses a symlink: {name}')
        results.append((name, source))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'agentops-rca.zip')
    output = parser.parse_args().output.resolve()
    if output.suffix != '.zip':
        parser.error('--output must end in .zip')
    selected = members()
    with ZipFile(output, 'x', compression=ZIP_DEFLATED) as archive:
        for name, source in selected:
            entry = ZipInfo(f'agentops-rca/{name}')
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith('.sh') else 0o100644) << 16
            archive.writestr(entry, source.read_bytes())
    with ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('ZIP integrity verification failed')
    print(f'Created {output.name} ({len(selected)} files)')
    print(f'SHA-256 {hashlib.sha256(output.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()
