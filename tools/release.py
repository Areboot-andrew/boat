"""Build board-scoped release assets. No deployment, network or FC access."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def build(tag):
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    release = {'schema': 1, 'tag': tag, 'commit': commit, 'boards': {}}
    for board in range(1, 5):
        subprocess.run([sys.executable, str(ROOT / 'clones/harpoon-02/latest-20261014/build.py'), str(board)], check=True)
        folder = ROOT / f'clones/harpoon-{board:02}/latest-20261014'
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        name = f'pi{board:02}-app.tar.gz'
        shutil.copyfile(folder / 'latest-app.tar.gz', out / name)
        release['boards'][f'pi{board:02}'] = {
            'hostname': manifest['hostname'], 'asset': name,
            'sha256': hashlib.sha256((out / name).read_bytes()).hexdigest(),
            'files': manifest['files'], 'preserve': manifest['preserve'],
            'scope': 'application-only; no live config replacement; not an OS image',
        }
    (out / 'release.json').write_text(json.dumps(release, indent=2) + '\n', encoding='utf-8')

if __name__ == '__main__':
    build(sys.argv[1])
