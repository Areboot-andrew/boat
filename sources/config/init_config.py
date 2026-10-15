"""One-time import of existing camera URLs. Does not print credentials."""
import json
import shlex
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote
import yaml
from harpoon_config import save, BASE, CONFIG, SECRETS, APPLIED
from config_model import validate

if CONFIG.exists() or SECRETS.exists():
    raise SystemExit('Config already exists; refusing to overwrite')
current = yaml.safe_load((BASE/'pi5-mediamtx.yml').read_text())
tail = subprocess.check_output(['tailscale', 'ip', '-4'], text=True).strip()
c = dict(version=1, boat='harpoon-pi5-02', cameras={}, webrtc_hosts=['192.168.10.50', tail],
         telemetry=dict(bind=tail, port=14551))
secrets = {}
for name in ['cam1', 'cam2']:
    raw = current['paths'][name+'raw']
    url = urlsplit(raw['source'])
    if url.scheme != 'rtsp': raise ValueError('Import expects current RTSP inputs')
    cmd = shlex.split(current['paths'][name+'web']['runOnDemand'])
    fps = int(cmd[cmd.index('-vf')+1].split('=')[1])
    bitrate = int(cmd[cmd.index('-b:v')+1].rstrip('k'))
    c['cameras'][name] = dict(enabled=True,
        source=dict(type='rtsp', host=url.hostname, port=url.port or 554,
                    path=url.path+('?' + url.query if url.query else ''), transport=raw.get('rtspTransport','tcp')),
        web=dict(codec='h264', fps=fps, bitrate_kbps=bitrate, audio='-an' not in cmd),
        qgc=dict(codec='copy', fps=fps, bitrate_kbps=bitrate, audio=False))
    secrets[name] = dict(username=unquote(url.username or ''), password=unquote(url.password or ''))
validate(c, secrets)
save(CONFIG, json.dumps(c, indent=2)+'\n')
save(SECRETS, json.dumps(secrets, indent=2)+'\n', 0o600)
# Baseline copies for subsequent rollback; original media/unit backed up by apply.
save(APPLIED, json.dumps(c, indent=2)+'\n')
save(BASE/'camera-secrets.applied.json', json.dumps(secrets, indent=2)+'\n', 0o600)
print('Imported cam1/cam2; secrets stored separately; no services changed')
