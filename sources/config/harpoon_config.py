#!/usr/bin/python3
"""Root-only staged configuration apply, validation, and rollback."""
import argparse
import copy
import fcntl
import grp
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from config_model import validate, render, source_url, sdp

BASE = Path('/etc/harpoon')
CONFIG = BASE / 'boat.json'
APPLIED = BASE / 'boat.applied.json'
SECRETS = BASE / 'camera-secrets.json'
MEDIA = BASE / 'pi5-mediamtx.yml'
DROP = Path('/etc/systemd/system/harpoon-bms-mavlink.service.d/30-boat.conf')
SERVICES = ['harpoon-pi5-camera', 'harpoon-bms-mavlink']
FILES = [MEDIA, APPLIED, DROP, BASE/'cam1.sdp', BASE/'cam2.sdp']
BACKUPS = Path('/var/backups/harpoon-config')


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=45, **kwargs)


def save(path, data, mode=0o640):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.harpoon-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.chmod(name, mode)
        os.chown(name, 0, grp.getgrnam('harpoon').gr_gid if mode == 0o640 else 0)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def load():
    c, secrets = json.loads(CONFIG.read_text()), json.loads(SECRETS.read_text())
    validate(c, secrets)
    return c, secrets


def installed_ips():
    result = json.loads(run(['ip', '-j', '-4', 'addr']).stdout)
    return {a['local'] for link in result for a in link.get('addr_info', [])}


def check_media(data):
    """Start parser/server with ephemeral localhost ports and NO source hooks."""
    c = copy.deepcopy(data)
    c.update(rtspAddress='127.0.0.1:0', rtspTransports=['tcp'], hls=False, webrtc=False)
    for p in c['paths'].values():
        for key in list(p):
            if key.startswith('runOn'): del p[key]
    with tempfile.TemporaryDirectory(prefix='harpoon-check-') as tmp:
        path = Path(tmp)/'mediamtx.json'
        path.write_text(json.dumps(c)); path.chmod(0o600)
        with (Path(tmp)/'output').open('w+') as log:
            proc = subprocess.Popen(['/usr/local/bin/mediamtx', str(path)], stdout=log, stderr=log)
            try:
                time.sleep(1.5)
                if proc.poll() is not None: raise ValueError('MediaMTX rejected candidate; current config unchanged')
            finally:
                if proc.poll() is None: proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()


def probe(c, secrets):
    for name, cam in c['cameras'].items():
        if not cam['enabled']: continue
        s = cam['source']
        cmd = ['/usr/bin/ffprobe', '-v', 'error']
        if s['type'] == 'rtsp':
            cmd += ['-rtsp_transport', s['transport'], '-rw_timeout', '5000000', source_url(s, secrets[name])]
        else:
            raise ValueError(name+': UDP preflight requires dedicated receive test; use --allow-offline only for intentional staging')
        cmd += ['-select_streams', 'v:0', '-show_entries', 'stream=codec_name', '-of', 'json']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            streams = json.loads(result.stdout).get('streams', []) if result.returncode == 0 else []
            if not streams: raise ValueError()
        except (subprocess.TimeoutExpired, ValueError):
            raise ValueError(name+': video source test failed; current config unchanged') from None


def backup():
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    dest = BACKUPS / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S-%f')
    dest.mkdir(mode=0o700)
    entries = []
    for index, path in enumerate(FILES):
        entries.append({'path': str(path), 'exists': path.exists(), 'file': str(index)})
        if path.exists(): shutil.copy2(path, dest/str(index))
    # Preserve last successfully applied draft and credentials for rollback.
    if APPLIED.exists(): shutil.copy2(APPLIED, dest/'boat.json')
    if (BASE/'camera-secrets.applied.json').exists():
        shutil.copy2(BASE/'camera-secrets.applied.json', dest/'secrets.json')
    (dest/'manifest.json').write_text(json.dumps(entries))
    return dest


def restore(dest):
    entries = json.loads((dest/'manifest.json').read_text())
    if {x['path'] for x in entries} != {str(p) for p in FILES}: raise ValueError('Invalid backup manifest')
    for entry in entries:
        p = Path(entry['path'])
        if entry['exists']: save(p, (dest/entry['file']).read_text(), 0o644 if p == DROP else 0o640)
        elif p.exists(): p.unlink()
    if (dest/'boat.json').exists(): save(CONFIG, (dest/'boat.json').read_text())
    if (dest/'secrets.json').exists():
        save(SECRETS, (dest/'secrets.json').read_text(), 0o600)
        save(BASE/'camera-secrets.applied.json', (dest/'secrets.json').read_text(), 0o600)


def restart():
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'restart', *SERVICES])
    time.sleep(2)
    for unit in SERVICES:
        if run(['systemctl', 'is-active', unit]).stdout.strip() != 'active':
            raise ValueError('Service did not start: '+unit)


def apply(allow_offline):
    c, secrets = load()
    if c['telemetry']['bind'] not in installed_ips(): raise ValueError('Telemetry bind IP not assigned to this board')
    for cam in c['cameras'].values():
        s = cam['source']
        if cam['enabled'] and s['type'] == 'udp' and s['bind'] not in installed_ips() | {'0.0.0.0'}:
            raise ValueError('UDP bind IP not assigned to this board')
    media = render(c, secrets)
    check_media(media)
    if not allow_offline: probe(c, secrets)
    dest = backup()
    try:
        save(APPLIED, json.dumps(c, indent=2)+'\n')
        for name, cam in c['cameras'].items():
            if cam['source']['type'] == 'udp' and cam['source']['format'] == 'rtp':
                save(BASE/(name+'.sdp'), sdp(cam['source']))
        save(MEDIA, json.dumps(media, indent=2)+'\n')
        save(DROP, '[Service]\nEnvironment=BMS_TCP_BIND='+c['telemetry']['bind']+'\nEnvironment=BMS_TCP_PORT='+str(c['telemetry']['port'])+'\n', 0o644)
        restart()
        with socket.create_connection((c['telemetry']['bind'], c['telemetry']['port']), timeout=4) as s:
            s.settimeout(4)
            if s.recv(1) != b'\xfd': raise ValueError('MAVLink health check failed')
        save(BASE/'camera-secrets.applied.json', json.dumps(secrets, indent=2)+'\n', 0o600)
    except Exception:
        restore(dest); restart()
        raise ValueError('Apply failed; previous generated files restored. Backup: '+str(dest)) from None
    print('APPLIED; backup:', dest)
    if allow_offline: print('Sources NOT verified: offline staging explicitly allowed')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['validate', 'apply', 'export', 'rollback'])
    p.add_argument('--allow-offline', action='store_true')
    p.add_argument('--backup')
    a = p.parse_args()
    if os.geteuid() != 0: raise ValueError('Run with sudo')
    with open('/run/lock/harpoon-config.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if a.command == 'validate':
            c, s = load(); check_media(render(c, s)); print('VALID; live sources not checked')
        elif a.command == 'export':
            c, _ = load(); print(json.dumps(c, indent=2))
        elif a.command == 'apply': apply(a.allow_offline)
        else:
            if not a.backup: raise ValueError('Specify --backup NAME')
            path = (BACKUPS/a.backup).resolve()
            if path.parent != BACKUPS.resolve(): raise ValueError('Invalid backup path')
            restore(path); restart(); print('ROLLED BACK:', path)


if __name__ == '__main__':
    try: main()
    except Exception as e:
        # Never echo subprocess stderr: camera URLs can contain credentials.
        print('ERROR:', 'System command failed (details suppressed for credential safety)' if isinstance(e, subprocess.SubprocessError) else str(e))
        raise SystemExit(1)
