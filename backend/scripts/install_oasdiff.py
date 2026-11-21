"""Install a pinned, checksum-verified oasdiff binary without a package manager."""

from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import platform
import tarfile
from tempfile import gettempdir
from urllib.request import urlopen

VERSION = '1.39.0'
ARCHIVES = {
    ('Linux', 'x86_64'): ('linux_amd64', '71a85930728f367a2086077b7ae1411319421549d18473a3e8258b6451520433'),
    ('Linux', 'aarch64'): ('linux_arm64', '481db7d891d916f13df277b2ef8bbb95477702827710e49fe22cef69c359c780'),
    ('Windows', 'AMD64'): ('windows_amd64', '956a73df88e03efdf3fcc5f327446cc176fefe4adcea1978b0fef464a1ee8901'),
    ('Windows', 'ARM64'): ('windows_arm64', '5699ac9dc74b432f78990cd369ff2bec3a79302c58e923c1ec823e47a86ddb82'),
    ('Darwin', 'arm64'): ('darwin_all', 'fe88d9950324d3b0ebeaf8e0d3a210b64cb099a0f55fce5ee5a22b276df0eac4'),
    ('Darwin', 'x86_64'): ('darwin_all', 'fe88d9950324d3b0ebeaf8e0d3a210b64cb099a0f55fce5ee5a22b276df0eac4'),
}
TOOLS = Path(os.environ.get('RUNNER_TEMP', gettempdir())) / 'uitconnect-tools'
BINARY = TOOLS / ('oasdiff.exe' if platform.system() == 'Windows' else 'oasdiff')


def main():
    target, checksum = ARCHIVES[(platform.system(), platform.machine())]
    name = f'oasdiff_{VERSION}_{target}.tar.gz'
    url = f'https://github.com/oasdiff/oasdiff/releases/download/v{VERSION}/{name}'
    with urlopen(url, timeout=60) as response:
        archive = response.read()
    if sha256(archive).hexdigest() != checksum:
        raise RuntimeError('oasdiff archive checksum mismatch; refusing to install')
    with tarfile.open(fileobj=BytesIO(archive), mode='r:gz') as package:
        members = [member for member in package.getmembers()
                   if member.isfile() and Path(member.name).name == BINARY.name]
        if len(members) != 1:
            raise RuntimeError('Expected exactly one oasdiff binary')
        TOOLS.mkdir(parents=True, exist_ok=True)
        BINARY.write_bytes(package.extractfile(members[0]).read())
    BINARY.chmod(0o755)
    print(f'Installed oasdiff {VERSION}: {BINARY}')


if __name__ == '__main__':
    main()
