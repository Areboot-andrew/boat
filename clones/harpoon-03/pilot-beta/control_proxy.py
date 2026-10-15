"""Same-origin proxy to loopback-only control daemon; no raw MAVLink API."""
import json,ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

HOSTS={'100.64.128.45','192.168.10.50','127.0.0.1','localhost','harpoon-pi5-03','harpoon-pi5-03.tail15f590.ts.net'}
CONTROL_NETWORKS=tuple(ipaddress.ip_network(n) for n in ('127.0.0.0/8','192.168.10.0/24','100.64.0.0/10'))
def handle(handler,post=False):
    path=urlsplit(handler.path).path
    if not path.startswith('/control/'):return False
    expected='/control/action' if post else '/control/status'
    if path!=expected:handler.json_response({'error':'Not found'},404);return True
    try:
        host=handler.headers.get('Host','');origin=handler.headers.get('Origin','')
        if urlsplit('http://'+host).hostname not in HOSTS:raise PermissionError('Unknown host')
        headers={};body=None
        if post:
            peer=ipaddress.ip_address(handler.client_address[0])
            if not any(peer in net for net in CONTROL_NETWORKS):raise PermissionError('Керування лише з LAN борта або Tailscale')
            u=urlsplit(origin)
            if u.scheme not in ('http','https') or u.netloc!=host:raise PermissionError('Same-origin required')
            if handler.headers.get('Content-Type','').split(';')[0]!='application/json':raise PermissionError('JSON required')
            # Operator access is now the trusted boat LAN / tailnet boundary.
            # Never expose the daemon's internal secret to browser clients.
            key=Path('/etc/harpoon/web-control.key').read_text().strip()
            n=int(handler.headers.get('Content-Length','0'))
            if not 0<n<=16384:raise ValueError('Body size')
            data=json.loads(handler.rfile.read(n))
            if not isinstance(data,dict):raise ValueError('JSON object required')
            if data.get('critical_bench'):raise PermissionError('CRITICAL recovery unavailable in PILOT')
            if data.get('action')=='claim':
                if data.get('operator_confirmed') is not True:raise PermissionError('Operator confirmation required')
                data.update(bench=True,critical_bench=False)
            body=json.dumps(data).encode();headers={'X-Control-Key':key,'Content-Type':'application/json'}
        req=Request('http://127.0.0.1:8091/'+('action' if post else 'status'),data=body,headers=headers)
        try:
            with urlopen(req,timeout=1.5) as r:result=json.loads(r.read(2097152));status=r.status
        except HTTPError as e:result=json.loads(e.read(8192));status=e.code
        handler.json_response(result,status)
    except PermissionError as e:handler.json_response({'error':str(e)},403)
    except (ValueError,TypeError):handler.json_response({'error':'Invalid request'},400)
    except (OSError,URLError):handler.json_response({'error':'Контролер USB недоступний'},503)
    return True
