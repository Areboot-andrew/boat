"""Strict camera configuration model; no shell fragments accepted."""
import ipaddress
import json
import re
from urllib.parse import quote


def keys(obj, expected):
    if not isinstance(obj, dict) or set(obj) != set(expected.split()):
        raise ValueError('Invalid/missing fields: expected ' + expected)


def integer(x, low, high):
    if type(x) is not int or not low <= x <= high:
        raise ValueError(f'Expected integer {low}..{high}')


def host(x):
    if not isinstance(x, str) or not x or len(x) > 253:
        raise ValueError('Invalid hostname/IP')
    try:
        ipaddress.IPv4Address(x)
    except ValueError:
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?', x):
            raise ValueError('Use IPv4 or DNS hostname')


def validate(c, secrets):
    keys(c, 'version boat cameras webrtc_hosts telemetry')
    if c['version'] != 1: raise ValueError('Unsupported version')
    if not re.fullmatch(r'[a-z0-9-]{1,63}', c['boat']): raise ValueError('Invalid boat label')
    if not isinstance(c['webrtc_hosts'], list) or not 1 <= len(c['webrtc_hosts']) <= 8:
        raise ValueError('Need 1..8 WebRTC hosts')
    for h in c['webrtc_hosts']: host(h)
    keys(c['telemetry'], 'bind port')
    ipaddress.IPv4Address(c['telemetry']['bind'])
    integer(c['telemetry']['port'], 1024, 65535)
    if c['telemetry']['port'] in [8080, 8554, 8888, 8889, 8189]: raise ValueError('Port conflict')
    keys(c['cameras'], 'cam1 cam2')
    keys(secrets, 'cam1 cam2')
    ports = set()
    for name, cam in c['cameras'].items():
        keys(cam, 'enabled source web qgc')
        if type(cam['enabled']) is not bool: raise ValueError('enabled must be boolean')
        keys(secrets[name], 'username password')
        for text in secrets[name].values():
            if not isinstance(text, str) or any(ord(ch) < 32 for ch in text):
                raise ValueError('Invalid credentials')
        s = cam['source']
        if s.get('type') == 'rtsp':
            keys(s, 'type host port path transport')
            host(s['host']); integer(s['port'], 1, 65535)
            if not isinstance(s['path'], str) or not s['path'].startswith('/') or any(ord(ch) < 33 for ch in s['path']):
                raise ValueError('RTSP path must start with /, without spaces/control characters')
            if s['transport'] not in ['tcp', 'udp']: raise ValueError('Invalid RTSP transport')
        elif s.get('type') == 'udp':
            keys(s, 'type bind port format codec payload_type fmtp')
            ipaddress.IPv4Address(s['bind']); integer(s['port'], 1024, 65534)
            if s['format'] not in ['mpegts', 'rtp']: raise ValueError('UDP format must be mpegts or rtp')
            if s['codec'] not in ['h264', 'h265']: raise ValueError('Invalid RTP codec')
            integer(s['payload_type'], 96, 127)
            if not isinstance(s['fmtp'], str) or not re.fullmatch(r'[A-Za-z0-9+/=;,. _-]{0,4096}', s['fmtp']):
                raise ValueError('Invalid RTP fmtp')
            used = {s['port']} | ({s['port'] + 1} if s['format'] == 'rtp' else set())
            if cam['enabled']:
                if used & (ports | {8189, 8000, 8001}): raise ValueError('UDP/RTP port conflict')
                ports.update(used)
        else: raise ValueError('source.type must be rtsp or udp')
        for output in ['web', 'qgc']:
            v = cam[output]
            keys(v, 'codec fps bitrate_kbps audio')
            allowed = ['h264'] if output == 'web' else ['copy', 'h264', 'h265']
            if v['codec'] not in allowed: raise ValueError('Invalid output codec')
            integer(v['fps'], 1, 30); integer(v['bitrate_kbps'], 128, 12000)
            if type(v['audio']) is not bool: raise ValueError('audio must be boolean')
            if output == 'qgc' and v['codec'] == 'copy' and v['audio']:
                raise ValueError('QGC copy relays original tracks; audio must be false (no audio conversion)')
    return c


def source_url(source, secret):
    auth = ''
    if secret['username']:
        auth = quote(secret['username'], safe='') + ':' + quote(secret['password'], safe='') + '@'
    return f"rtsp://{auth}{source['host']}:{source['port']}{source['path']}"


def sdp(s):
    codec = 'H264' if s['codec'] == 'h264' else 'H265'
    lines = ['v=0', 'o=- 0 0 IN IP4 127.0.0.1', 's=HARPOON', f"c=IN IP4 {s['bind']}", 't=0 0',
             f"m=video {s['port']} RTP/AVP {s['payload_type']}", f"a=rtpmap:{s['payload_type']} {codec}/90000"]
    if s['fmtp']: lines.append(f"a=fmtp:{s['payload_type']} {s['fmtp']}")
    return '\n'.join(lines + ['a=recvonly', ''])


def input_args(name, source):
    if source['format'] == 'rtp':
        return ['-protocol_whitelist', 'file,udp,rtp', '-analyzeduration', '1000000', '-probesize', '1000000', '-max_delay', '200000', '-reorder_queue_size', '64', '-i', f'/etc/harpoon/{name}.sdp']
    return ['-f', 'mpegts', '-i', f"udp://{source['bind']}:{source['port']}?fifo_size=65536&overrun_nonfatal=1"]


def ffmpeg_args(name, mode, c):
    cam = c['cameras'][name]
    cmd = ['/usr/bin/ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'warning']
    if mode == 'udp':
        cmd += input_args(name, cam['source']) + ['-map', '0:v:0', '-an', '-c:v', 'copy']
        target = name + 'raw'
    else:
        v = cam[mode]
        cmd += ['-rtsp_transport', 'tcp', '-i', f'rtsp://127.0.0.1:8554/{name}raw', '-map', '0:v:0']
        cmd += ['-map', '0:a:0?'] if v['audio'] else ['-an']
        bitrate = v['bitrate_kbps']
        cmd += ['-vf', f"fps={v['fps']}", '-c:v', 'libx264' if v['codec'] == 'h264' else 'libx265',
                '-threads', '2', '-preset', 'ultrafast', '-tune', 'zerolatency', '-pix_fmt', 'yuv420p',
                '-b:v', f'{bitrate}k', '-maxrate', f'{round(bitrate * 1.2)}k', '-bufsize', f'{round(bitrate * .6)}k',
                '-g', str(v['fps']), '-bf', '0']
        if v['codec'] == 'h264': cmd += ['-profile:v', 'baseline']
        else: cmd += ['-x265-params', 'pools=2:frame-threads=1:bframes=0:rc-lookahead=0']
        if v['audio']: cmd += ['-af', 'aresample=async=1:first_pts=0', '-c:a', 'libopus', '-ar', '48000', '-ac', '1', '-b:a', '32k']
        target = name + ('web' if mode == 'web' else '')
    return cmd + ['-f', 'rtsp', '-rtsp_transport', 'tcp', f'rtsp://127.0.0.1:8554/{target}']


def render(c, secrets):
    validate(c, secrets)
    out = dict(logLevel='warn', rtsp=True, rtspAddress=':8554', rtmp=False,
               hls=True, hlsAddress=':8888', hlsVariant='mpegts', webrtc=True,
               webrtcAddress=':8889', webrtcAdditionalHosts=c['webrtc_hosts'],
               webrtcLocalTCPAddress=':8189', srt=False, paths={})
    for name, cam in c['cameras'].items():
        if not cam['enabled']: continue
        s = cam['source']
        worker = '/usr/bin/python3 /opt/harpoon/config/camera_worker.py ' + name
        if s['type'] == 'rtsp':
            raw = dict(source=source_url(s, secrets[name]), rtspTransport=s['transport'], sourceOnDemand=True,
                       sourceOnDemandStartTimeout='30s', sourceOnDemandCloseAfter='10s')
        else:
            raw = dict(source='publisher', runOnInit=worker+' udp', runOnInitRestart=True)
        out['paths'][name+'raw'] = raw
        for mode, path in [('web', name+'web'), ('qgc', name)]:
            if mode == 'qgc' and cam[mode]['codec'] == 'copy':
                out['paths'][path] = dict(source=f'rtsp://127.0.0.1:8554/{name}raw', rtspTransport='tcp',
                                         sourceOnDemand=True, sourceOnDemandStartTimeout='30s', sourceOnDemandCloseAfter='10s')
            else:
                out['paths'][path] = dict(source='publisher', runOnDemand=worker+' '+mode,
                                         runOnDemandRestart=True, runOnDemandStartTimeout='30s', runOnDemandCloseAfter='15s')
    return out
