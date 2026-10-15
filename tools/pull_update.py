"""Download and validate this boat's release. NEVER installs/restarts services.

Run on Raspberry: python3 tools/pull_update.py vYYYY.MM.DD.N
Run without sudo in a user-owned directory. Application requires a separate
reviewed installation with backup and fresh DISARMED/idle verification.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import socket
import tarfile
import tempfile
import urllib.parse
import urllib.request

HOSTS = {'harpoon-pi5': 'pi01', **{f'harpoon-pi5-{n:02}': f'pi{n:02}' for n in (2, 3, 4)}}
BASE = 'https://github.com/Areboot-andrew/boat/releases/download/'

def fetch(url, limit):
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Release asset exceeds size limit')
    return data

def validate_archive(data, expected, board):
    pilot = 'pilot/' if board == 'pi02' else 'pilot-beta/'
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        found = {}
        total = 0
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if (not member.isfile() or path.is_absolute() or '..' in path.parts
                    or not member.name.startswith((pilot, 'web-control/'))
                    or member.name in found or member.size > 2_000_000):
                raise ValueError('Invalid package member: ' + member.name)
            total += member.size
            if total > 20_000_000:
                raise ValueError('Expanded package too large')
            found[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        if found != expected:
            raise ValueError('Package file hashes differ from release manifest')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', help='Explicit reviewed release tag; no implicit latest')
    parser.add_argument('--directory', type=Path, default=Path.home() / 'harpoon-updates')
    args = parser.parse_args()
    if not re.fullmatch(r'v[0-9][A-Za-z0-9._-]{0,63}', args.tag):
        raise SystemExit('Invalid release tag')
    hostname = socket.gethostname()
    board = HOSTS.get(hostname)
    if board is None:
        raise SystemExit('Unrecognized hostname; refusing another boat package')
    base = BASE + urllib.parse.quote(args.tag, safe='') + '/'
    raw = fetch(base + 'release.json', 1_000_000)
    manifest = json.loads(raw)
    if manifest.get('schema') != 1 or manifest.get('tag') != args.tag:
        raise SystemExit('Release metadata mismatch')
    item = manifest['boards'][board]
    if item['hostname'] != hostname or item['asset'] != board + '-app.tar.gz':
        raise SystemExit('Board identity mismatch')
    data = fetch(base + item['asset'], 20_000_000)
    if hashlib.sha256(data).hexdigest() != item['sha256']:
        raise SystemExit('Package SHA256 mismatch')
    validate_archive(data, item['files'], board)
    args.directory.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=board + '-' + args.tag + '-', dir=args.directory))
    (folder / item['asset']).write_bytes(data)
    (folder / 'release.json').write_bytes(raw)
    print('VERIFIED / STAGED ONLY:', folder)
    print('No configuration writes, extraction, installation, service restart or FC commands.')

if __name__ == '__main__':
    main()
