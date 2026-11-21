"""Compare old -> new OpenAPI with pinned oasdiff; never trust a PR's own baseline."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from scripts.api_baseline import git
from scripts.install_oasdiff import BINARY, VERSION


def read_trusted_baseline(revision):
    if not re.fullmatch('[0-9a-f]{40}', revision or ''):
        raise ValueError('API_CONTRACT_BASELINE_COMMIT must identify an approved immutable commit (40-character SHA). '
                         'Initial candidate is not approved; accept it separately before enabling the release gate.')
    try:
        data = git('show', f'{revision}:docs/openapi/approved-v1.json')
        metadata = json.loads(git('show', f'{revision}:docs/openapi/approved-v1.metadata.json'))
    except subprocess.CalledProcessError as exc:
        raise ValueError('Trusted revision has no approved-v1 snapshot/metadata; candidate files cannot satisfy this gate.') from exc
    if metadata.get('status') != 'approved' or not re.fullmatch('[0-9a-f]{40}', metadata.get('source_commit', '')):
        raise ValueError('Trusted baseline metadata must declare approved status and an immutable source_commit')
    if sha256(data).hexdigest() != metadata.get('sha256'):
        raise ValueError('Trusted baseline SHA-256 differs from its metadata')
    return data


def compare(baseline, current, *, binary=BINARY):
    if not Path(binary).is_file():
        raise RuntimeError('Install the pinned checker first: python -m scripts.install_oasdiff')
    version = subprocess.run([str(binary), '--version'], capture_output=True, text=True, check=True)
    if not re.search(rf'(?<![\d.])v?{re.escape(VERSION)}(?![\d.])', version.stdout + version.stderr):
        raise RuntimeError(f'Expected oasdiff {VERSION}, got {version.stdout.strip()} {version.stderr.strip()}')
    # Old requests must still be accepted; new responses must satisfy old consumers.
    return subprocess.run([str(binary), 'breaking', str(baseline), str(current), '--fail-on', 'WARN', '--format', 'text'],
                          capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--trusted-ref', help='Externally configured approved commit, not PR-controlled snapshot files')
    source.add_argument('--candidate', type=Path, help='Local exploratory comparison only; not a release approval')
    parser.add_argument('--current', type=Path, required=True)
    args = parser.parse_args()
    with TemporaryDirectory(prefix='uitconnect-trusted-baseline-') as directory:
        if args.trusted_ref is not None:
            baseline = Path(directory) / 'approved.json'
            baseline.write_bytes(read_trusted_baseline(args.trusted_ref))
        else:
            baseline = args.candidate
            print('CANDIDATE comparison only: approved-baseline release readiness remains Pending.')
        result = compare(baseline, args.current)
        print(result.stdout or 'No incompatible OpenAPI changes detected.')
        if result.stderr:
            print(result.stderr)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
