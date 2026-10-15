"""Pi02 PILOT UI with same-origin loopback control and session proxy."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
import json, ipaddress
import control_proxy
import voyage
VOYAGE=None

ROOT = Path(__file__).resolve().parent
ALLOWED = {'/', '/index.html', '/leaflet.css', '/leaflet.js', '/hud.css', '/hud.js',
           '/economy.css', '/ui-tools.css', '/ui-tools.js', '/reader.js', '/camera-player.js',
           '/diagnostics.css', '/diagnostics.js', '/telemetry', '/health', '/diagnostics',
           '/sessions', '/track', '/sessions.csv'}


class Handler(BaseHTTPRequestHandler):
    def json_response(self,obj,status=200):
        self.reply(status,json.dumps(obj).encode(),'application/json')

    def reply(self, status, body, mime):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if control_proxy.handle(self):return
        path = urlsplit(self.path).path
        if path == '/voyage':
            query=parse_qs(urlsplit(self.path).query)
            try:after=max(0,int(query.get('after',['0'])[0]))
            except ValueError:return self.json_response({'error':'Invalid offset'},400)
            return self.json_response(VOYAGE.snapshot(after,query.get('boot',[None])[0]))
        if path in ('/beta.js', '/beta.css', '/live-control.js', '/pad-config.js', '/navigation.js', '/navigation.css', '/auto-ui.js', '/auto-ui.css', '/route-editor.js', '/route-editor.css'):
            mime = 'text/javascript' if path.endswith('.js') else 'text/css'
            return self.reply(200, (ROOT / path[1:]).read_bytes(), mime + '; charset=utf-8')
        if path not in ALLOWED:
            return self.reply(404, b'Not found', 'text/plain')
        try:
            with urlopen('http://127.0.0.1:8080' + self.path, timeout=4) as response:
                body, mime = response.read(), response.headers.get('Content-Type', 'application/octet-stream')
            if path in ('/', '/index.html'):
                body = body.replace(b'</head>', b'<link rel="stylesheet" href="/auto-ui.css"></head>')
                body = body.replace(b'</head>', b'<link rel="stylesheet" href="/beta.css"><link rel="stylesheet" href="/navigation.css"><script src="/pad-config.js" defer></script><script src="/live-control.js" defer></script><script src="/beta.js" defer></script><script src="/navigation.js" defer></script></head>')
                body = body.replace(b'</head>', b'<link rel="stylesheet" href="/route-editor.css"><script src="/route-editor.js" defer></script></head>')
            self.reply(200, body, mime)
        except Exception:
            self.reply(502, b'Pi02 monitoring service unavailable', 'text/plain')

    def do_POST(self):
        if control_proxy.handle(self,post=True):return
        if self.path not in ('/sessions/start','/sessions/stop','/sessions/delete'):
            return self.json_response({'error':'Not found'},404)
        try:
            host=self.headers.get('Host','');origin=urlsplit(self.headers.get('Origin',''))
            peer=ipaddress.ip_address(self.client_address[0])
            if urlsplit('http://'+host).hostname not in control_proxy.HOSTS or origin.scheme not in ('http','https') or origin.netloc!=host or not any(peer in net for net in control_proxy.CONTROL_NETWORKS):
                return self.json_response({'error':'Same-origin trusted network required'},403)
            if self.headers.get('X-Harpoon-Session')!='1':return self.json_response({'error':'Session header required'},403)
            n=int(self.headers.get('Content-Length','0'))
            if not 0<=n<=2048:return self.json_response({'error':'Body size'},400)
            body=self.rfile.read(n)
            req=Request('http://127.0.0.1:8080'+self.path,data=body,method='POST',headers={'X-Harpoon-Session':'1','Content-Type':'application/json'})
            try:
                with urlopen(req,timeout=8) as r:self.reply(r.status,r.read(262144),'application/json')
            except HTTPError as e:self.reply(e.code,e.read(8192),'application/json')
        except (ValueError,TypeError):self.json_response({'error':'Invalid request'},400)
        except OSError:self.json_response({'error':'Session service unavailable'},503)


if __name__ == '__main__':
    VOYAGE=voyage.start()
    ThreadingHTTPServer(('0.0.0.0', 8090), Handler).serve_forever()
