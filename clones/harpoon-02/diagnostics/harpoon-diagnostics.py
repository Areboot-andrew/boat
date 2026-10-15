#!/usr/bin/env python3
"""Read-only diagnostics. Never restarts equipment or changes networking."""
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request

UNITS = ['harpoon-gps-monitor', 'harpoon-pi5-camera', 'harpoon-cam2-qgc-udp',
         'harpoon-bms-mavlink', 'tailscaled', 'NetworkManager']
RUNTIME = Path('/run/harpoon-diagnostics/status.json')
STATE = Path('/var/lib/harpoon-diagnostics/last-state.json')
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
running = True
packet_lock = threading.Lock()
packets = {'count': 0, 'bytes': 0, 'last_at': 0, 'source': None, 'error': None, 'rtp_sequence_discontinuities': 0}

def command(args, timeout=4):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + ('\n'+p.stderr if p.returncode else '')).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, str(exc)

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return ''

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.new')
    with tmp.open('w') as f:
        json.dump(value, f, ensure_ascii=False)
        f.flush()
        if path == STATE:
            os.fsync(f.fileno())
    tmp.replace(path)

def emit(kind, data, warning=False):
    print(('<4>' if warning else '<6>') + json.dumps({
        'event': kind, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'uptime_s': round(float(read('/proc/uptime').split()[0]), 1),
        'boot_id': read('/proc/sys/kernel/random/boot_id'), **data}, ensure_ascii=False), flush=True)

def capture():
    last_flow = last_seq = None
    try:
        with socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800)) as sock:
            sock.bind(('eth0', 0))
            sock.settimeout(1)
            while running:
                try:
                    p = sock.recv(65535)
                except socket.timeout:
                    continue
                if len(p) < 42 or p[12:14] != b'\x08\x00' or p[23] != 17:
                    continue
                u = 14 + (p[14] & 15) * 4
                if len(p) < u + 8 or int.from_bytes(p[u+2:u+4], 'big') != 5600:
                    continue
                with packet_lock:
                    packets['count'] += 1
                    packets['bytes'] += len(p)
                    packets['last_at'] = time.monotonic()
                    packets['source'] = socket.inet_ntoa(p[26:30])
                    rtp = p[u+8:]
                    if len(rtp) >= 12 and rtp[0] >> 6 == 2:
                        flow = (p[26:30], p[u:u+2], rtp[8:12])
                        seq = int.from_bytes(rtp[2:4], 'big')
                        if flow == last_flow and last_seq is not None and seq != (last_seq+1) % 65536:
                            packets['rtp_sequence_discontinuities'] += 1
                        last_flow, last_seq = flow, seq
    except OSError as exc:
        with packet_lock:
            packets['error'] = str(exc)

def network():
    _, routes = command(['ip', '-j', 'route', 'show', 'default'])
    try:
        defaults = json.loads(routes)
    except ValueError:
        defaults = []
    gateway = next((v.get('gateway') for v in defaults if v.get('gateway')), None)
    def tcp(ip):
        started = time.monotonic()
        try:
            with socket.create_connection((ip, 443), timeout=2):
                return True, round((time.monotonic()-started)*1000, 1)
        except OSError:
            return False, None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        a = pool.submit(tcp, '1.1.1.1')
        b = pool.submit(tcp, '8.8.8.8')
        dns = pool.submit(command, ['getent', 'ahostsv4', 'example.com'], 3)
        gw = pool.submit(command, ['ping', '-n', '-c', '1', '-W', '1', gateway], 2) if gateway else None
        av, bv = a.result(), b.result()
        gv = gw.result() if gw else (1, '')
        latency = re.search(r'time[=<]([\d.]+)', gv[1])
        result = {'gateway': gateway, 'gateway_ping': gv[0] == 0 if gw else None,
                  'gateway_ping_ms': float(latency.group(1)) if latency else None,
                  'internet_tcp_443': {'1.1.1.1': av[0], '8.8.8.8': bv[0]},
                  'tcp_connect_ms': {'1.1.1.1': av[1], '8.8.8.8': bv[1]},
                  'checked_uptime_s': float(read('/proc/uptime').split()[0]),
                  'dns_ok': dns.result()[0] == 0}
    code, text = command(['tailscale', 'status', '--json'])
    try:
        ts = json.loads(text) if code == 0 else {}
    except ValueError:
        ts = {}
    result['tailscale'] = {'state': ts.get('BackendState', 'unknown'),
                          'self_online': (ts.get('Self') or {}).get('Online'), 'health': ts.get('Health') or []}
    peer = next((v for v in (ts.get('Peer') or {}).values() if '100.64.139.75' in v.get('TailscaleIPs', [])), {})
    result['groundstation_online'] = peer.get('Online')
    return result

def collect(net):
    _, power = command(['vcgencmd', 'get_throttled'])
    match = re.search(r'0x[0-9a-fA-F]+', power)
    flags = int(match.group(), 16) if match else None
    temp = read('/sys/class/thermal/thermal_zone0/temp')
    memory = {}
    for line in read('/proc/meminfo').splitlines():
        k, value = line.split(':', 1)
        if k in ('MemTotal', 'MemAvailable', 'SwapTotal', 'SwapFree'):
            memory[k] = int(value.split()[0])
    services = {}
    for unit in UNITS:
        _, text = command(['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'NRestarts', '-p', 'Result'])
        services[unit] = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    try:
        with HTTP.open('http://127.0.0.1:8080/telemetry', timeout=2) as response:
            data = json.load(response)
        gps = {k: data.get('gps', {}).get(k) for k in ['link_ok', 'position_valid', 'heading_valid', 'satellites', 'fix_quality', 'error']}
        bms = {'link_ok': data.get('bms', {}).get('bms_link_ok')}
        api_error = None
    except Exception as exc:
        gps, bms, api_error = {}, {}, str(exc)
    disk = shutil.disk_usage('/')
    # PID 1 mount table: our own namespace is deliberately read-only (ProtectSystem).
    root_ro = any(line.split()[1] == '/' and 'ro' in line.split()[3].split(',') for line in read('/proc/1/mounts').splitlines())
    interfaces = {}
    for name in ('eth0', 'tailscale0'):
        base = Path('/sys/class/net') / name
        interfaces[name] = {k: read(base / 'statistics' / k) for k in ['rx_bytes','tx_bytes','rx_errors','tx_errors','rx_dropped','tx_dropped']}
        interfaces[name]['carrier'] = read(base / 'carrier')
        interfaces[name]['link_mbps'] = read(base / 'speed')
    with packet_lock:
        incoming = dict(packets)
    incoming['age_s'] = round(time.monotonic() - incoming.pop('last_at'), 1) if incoming['last_at'] else None
    return {'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'boot_id': read('/proc/sys/kernel/random/boot_id'), 'uptime_s': float(read('/proc/uptime').split()[0]),
            'power_flags': hex(flags) if flags is not None else power,
            'undervoltage_now': bool(flags & 1) if flags is not None else None,
            'throttled_now': bool(flags & 4) if flags is not None else None,
            'temperature_c': float(temp)/1000 if temp else None, 'load': os.getloadavg(), 'memory_kib': memory,
            'disk_free_mib': disk.free//1048576, 'root_readonly': root_ro,
            'pressure': {k: read('/proc/pressure/'+k) for k in ['cpu','memory','io']},
            'usb_devices': sorted(p.name for p in Path('/dev/serial/by-id').glob('*')),
            'network': net, 'interfaces': interfaces, 'camera2_udp': incoming,
            'services': services, 'gps': gps, 'bms': bms, 'telemetry_error': api_error}

def problems(s):
    out = []
    if s['undervoltage_now']: out.append('POWER_UNDERVOLTAGE')
    if s['throttled_now']: out.append('CPU_THROTTLED')
    if (s['temperature_c'] or 0) >= 80: out.append('TEMPERATURE_HIGH')
    m = s['memory_kib']
    if m.get('MemAvailable', 9999999) < max(100*1024, m.get('MemTotal',0)*0.1): out.append('MEMORY_LOW')
    if s['disk_free_mib'] < 1024: out.append('DISK_LOW')
    if s['root_readonly']: out.append('ROOT_READONLY')
    if s['interfaces']['eth0']['carrier'] != '1': out.append('ETHERNET_NO_CARRIER')
    net = s['network']
    if not net.get('gateway'): out.append('NO_DEFAULT_GATEWAY')
    if not any(net.get('internet_tcp_443', {}).values()): out.append('INTERNET_PROBES_FAILED')
    if not net.get('dns_ok'): out.append('DNS_FAILED')
    if net.get('tailscale',{}).get('state') != 'Running': out.append('TAILSCALE_NOT_RUNNING')
    if net.get('tailscale',{}).get('self_online') is False: out.append('TAILSCALE_OFFLINE')
    if net.get('groundstation_online') is False: out.append('GROUNDSTATION_OFFLINE')
    if s['camera2_udp']['age_s'] is None or s['camera2_udp']['age_s'] > 5: out.append('CAMERA2_NO_UDP')
    if s['camera2_udp']['error']: out.append('UDP_OBSERVER_ERROR')
    if s['telemetry_error']: out.append('WEB_TELEMETRY_UNAVAILABLE')
    if s['gps'].get('link_ok') is False: out.append('GPS_LINK_DOWN')
    elif s['gps'].get('position_valid') is False: out.append('GPS_NO_FIX')
    if s['bms'].get('link_ok') is False: out.append('BMS_LINK_DOWN')
    for unit, data in s['services'].items():
        if data.get('ActiveState') != 'active': out.append('SERVICE_NOT_ACTIVE:'+unit)
    return out

def main():
    global running
    def stop(*_):
        global running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        previous = json.loads(STATE.read_text())
    except (OSError, ValueError):
        previous = None
    emit('monitor_start', {'previous_monitor_state': previous,
                          'note': 'Missing clean_stop indicates abrupt loss or killed monitor, not proven power failure.'})
    threading.Thread(target=capture, daemon=True).start()
    last_net = last_snapshot = 0
    net, prev = {}, None
    while running:
        started = time.monotonic()
        try:
            if started-last_net >= 30:
                net, last_net = network(), started
            s = collect(net)
            if prev:
                dt = s['uptime_s'] - prev['uptime_s']
                for name, values in s['interfaces'].items():
                    for direction in ('rx', 'tx'):
                        try:
                            delta = int(values[direction+'_bytes']) - int(prev['interfaces'][name][direction+'_bytes'])
                            values[direction+'_mbps'] = round(delta*8/dt/1000000, 3) if dt > 0 and delta >= 0 else None
                        except (ValueError, KeyError):
                            values[direction+'_mbps'] = None
            s['problems'] = problems(s)
            if prev is None or s['problems'] != prev['problems']:
                emit('health_change', {'active': s['problems'],
                     'cleared': sorted(set(prev['problems'] if prev else [])-set(s['problems']))}, bool(s['problems']))
            if prev:
                state_keys = ('gateway','gateway_ping','internet_tcp_443','dns_ok','tailscale','groundstation_online')
                if any(s['network'].get(k) != prev['network'].get(k) for k in state_keys):
                    emit('network_change', {'before':prev['network'], 'after':s['network']})
                gaps = s['camera2_udp']['rtp_sequence_discontinuities'] - prev['camera2_udp']['rtp_sequence_discontinuities']
                if gaps > 0:
                    emit('camera2_rtp_sequence_discontinuity', {'count':gaps,'note':'May indicate loss, reordering or duplicate packets; observer drops also possible.'},True)
                if s['usb_devices'] != prev['usb_devices']:
                    emit('usb_change', {'before':prev['usb_devices'], 'after':s['usb_devices']}, True)
                for unit, value in s['services'].items():
                    if value != prev['services'].get(unit): emit('service_change', {'unit':unit,'state':value}, True)
                delta = (datetime.datetime.fromisoformat(s['utc'])-datetime.datetime.fromisoformat(prev['utc'])).total_seconds()-(s['uptime_s']-prev['uptime_s'])
                if abs(delta)>5: emit('clock_jump', {'seconds': round(delta,1)}, True)
            atomic(RUNTIME,s)
            if started-last_snapshot >= 60:
                emit('snapshot',s)
                atomic(STATE,{'boot_id':s['boot_id'],'utc':s['utc'],'uptime_s':s['uptime_s'],'clean_stop':False,'problems':s['problems']})
                last_snapshot = started
            prev = s
        except Exception as exc:
            emit('monitor_error', {'error':str(exc)}, True)
        while running and time.monotonic()-started<10: time.sleep(0.2)
    emit('monitor_stop', {'clean_stop':True})
    atomic(STATE,{'boot_id':read('/proc/sys/kernel/random/boot_id'),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'clean_stop':True})

if __name__ == '__main__':
    if '--monitor' in sys.argv:
        main()
    elif '--probe-cameras' in sys.argv:
        for name in ('cam1','cam2','cam2web'):
            code, result = command(['ffprobe','-v','error','-rtsp_transport','tcp','-read_intervals','%+2','-count_frames','-show_entries','stream=codec_name,width,height,nb_read_frames','-of','json','rtsp://127.0.0.1:8554/'+name],15)
            print(name, 'exit', code, result)
    else:
        print(RUNTIME.read_text() if RUNTIME.exists() else 'No status snapshot yet')
        print('\nRECENT HEALTH EVENTS:')
        subprocess.run(['journalctl','-u','harpoon-diagnostics','-n','20','--no-pager','-o','short-iso'])
