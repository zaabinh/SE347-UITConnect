"""Export an identifiable Git revision as a candidate, never implicitly approved."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / 'docs/openapi'


def git(*arguments):
    return subprocess.check_output(
        ['git', '-c', f'safe.directory={ROOT}', '-C', str(ROOT), *arguments], stderr=subprocess.PIPE)


def canonical(schema):
    return (json.dumps(schema, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()


def export_revision(revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Use an immutable full 40-character source commit SHA')
    archive = git('archive', '--format=zip', revision, 'backend')
    with TemporaryDirectory(prefix='uitconnect-openapi-') as temporary:
        directory = Path(temporary)
        with ZipFile(BytesIO(archive)) as package:
            package.extractall(directory)
        output = directory / 'openapi.json'
        environment = {**os.environ, 'APP_ENV': 'test',
                       'DATABASE_URL': 'sqlite+pysqlite:///:memory:',
                       'FRONTEND_URL': 'http://localhost:3000',
                       'CORS_ALLOWED_ORIGINS': 'http://localhost:3000'}
        subprocess.run([sys.executable, '-m', 'scripts.check_api_contract', '--export', str(output)],
                       cwd=directory / 'backend', env=environment, check=True)
        return json.loads(output.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', help='Immutable source revision; required when generating')
    parser.add_argument('--verify', action='store_true', help='Re-export candidate source and compare bytes')
    args = parser.parse_args()
    snapshot = SNAPSHOTS / 'candidate-v1.json'
    metadata_path = SNAPSHOTS / 'candidate-v1.metadata.json'
    if args.verify:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata['status'] != 'candidate':
            raise RuntimeError('This command only verifies candidate snapshots')
        generated = canonical(export_revision(metadata['source_commit']))
        if snapshot.read_bytes() != generated or sha256(generated).hexdigest() != metadata['sha256']:
            raise RuntimeError('Candidate differs from its source commit or metadata checksum')
        print('Candidate reproducible; this is provenance verification, not approval.')
        return
    if not args.source:
        parser.error('--source is required')
    generated = canonical(export_revision(args.source))
    from importlib.metadata import version
    metadata = {
        'status': 'candidate', 'source_commit': args.source,
        'sha256': sha256(generated).hexdigest(),
        'generator': 'FastAPI create_app().openapi(), sorted JSON, UTF-8, LF',
        'dependencies': {name: version(name) for name in ('fastapi', 'pydantic')},
        'approval': None,
        'notes': 'No approved PR/tag found. Initial API v1 baseline requires team acceptance separately from breaking changes.',
    }
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(generated)
    metadata_path.write_bytes(canonical(metadata))
    print(f'Generated candidate from {args.source}; NOT APPROVED.')


if __name__ == '__main__':
    main()
