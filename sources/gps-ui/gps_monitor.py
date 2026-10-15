"""UM982 USB reader. No actuator interface. Standard library only."""
import os, time, threading, select, json, math
from urllib.parse import urlsplit, parse_qs
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from consumption import Consumption
from platform_status import PlatformStatus
from session_log import SessionLog

PORT = os.environ.get('HARPOON_GPS_PORT', '/dev/harpoon-gps-unconfigured')
class GPS:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {'connected': False, 'error': 'Очікування USB GPS', 'latitude': None, 'longitude': None,
                     'speed_kmh': None, 'heading_deg': None, 'satellites': None, 'fix_quality': 0,
                     'course_deg': None, 'heading_status': 'Очікування', 'position_at': 0, 'speed_at': 0, 'heading_at': 0, 'message_at': 0}

    def snapshot(self):
        with self.lock: d = dict(self.data)
        now = time.monotonic()
        d['link_ok'] = d['connected'] and now-d['message_at'] < 4
        d['position_valid'] = d['link_ok'] and d['fix_quality'] > 0 and now-d['position_at'] < 4
        d['heading_valid'] = d['link_ok'] and d['heading_deg'] is not None and now-d['heading_at'] < 4
        if not d['position_valid']: d.update(latitude=None, longitude=None)
        if not d['position_valid'] or now-d['speed_at'] >= 4: d['speed_kmh'] = None
        # UM982 baseline points MASTER (starboard) -> SLAVE (port).
        # Rotate +90 degrees to obtain bow heading; leave RMC course unchanged.
        d['heading_offset_deg'] = -90.0
        d['heading_raw_deg'] = d['heading_deg'] if d['heading_valid'] else None
        d['heading_deg'] = ((d['heading_raw_deg'] + d['heading_offset_deg']) % 360.0
                            if d['heading_valid'] else None)
        d['position_age_s'] = round(now-d['position_at'],3) if d['position_at'] else None
        d['heading_age_s'] = round(now-d['heading_at'],3) if d['heading_at'] else None
        d['speed_age_s'] = round(now-d['speed_at'],3) if d['speed_at'] else None
        if d['speed_kmh'] is None or d['speed_kmh'] < 1: d['course_deg'] = None
        for k in ('position_at','speed_at','heading_at','message_at'): d.pop(k)
        return d

    def parse(self, line):
        line = line.strip()
        if not line or '*' not in line: return
        body, checksum = line[1:].rsplit('*', 1)
        if line[0] == '$':
            check = 0
            for byte in body.encode('ascii'): check ^= byte
            if check != int(checksum, 16): return
        elif line.startswith('#UNIHEADINGA,'):
            check = 0
            for byte in body.encode('ascii'):
                check ^= byte
                for _ in range(8): check = (check >> 1) ^ (0xedb88320 if check & 1 else 0)
            if check != int(checksum,16): return
        else: return
        now = time.monotonic()
        updates = {'message_at': now, 'error': None}
        fields = body.split(',')
        if fields[0].endswith('GGA'):
            q = int(fields[6]); lat = lon = None
            if q and fields[2] and fields[4]:
                def coord(v, hemi):
                    n = float(v); result = int(n/100)+(n%100)/60
                    return -result if hemi in ('S','W') else result
                lat, lon = coord(fields[2],fields[3]), coord(fields[4],fields[5])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180): return
            updates.update(fix_quality=q if lat is not None else 0, latitude=lat, longitude=lon,
                           satellites=int(fields[7]), position_at=now)
        elif fields[0].endswith('RMC'):
            speed = float(fields[7])*1.852 if fields[2]=='A' and fields[7] else None
            if speed is not None and (not math.isfinite(speed) or speed < 0): return
            course = float(fields[8]) if fields[2]=='A' and fields[8] else None
            if course is not None and (not math.isfinite(course) or not 0 <= course <= 360): course = None
            updates.update(speed_kmh=speed, course_deg=course, speed_at=now)
        elif line.startswith('#UNIHEADINGA,'):
            f = body.split(';',1)[1].split(',')
            heading = float(f[3]) if f[0]=='SOL_COMPUTED' and f[1]!='NONE' else None
            if heading is not None and (not math.isfinite(heading) or not 0 <= heading <= 360): return
            updates.update(heading_deg=heading, heading_status=f[0]+'/'+f[1], heading_at=now)
        else: return
        with self.lock: self.data.update(updates)

    def run(self):
        import termios
        while True:
            fd = None
            try:
                fd = os.open(PORT, os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
                attrs = termios.tcgetattr(fd)
                attrs[0]=attrs[1]=attrs[3]=0
                attrs[2]=termios.CS8|termios.CREAD|termios.CLOCAL
                attrs[4]=attrs[5]=termios.B115200
                termios.tcsetattr(fd,termios.TCSANOW,attrs)
                with self.lock: self.data.update(connected=True, error=None)
                # Only COM3 output; no factory reset, other ports untouched. Already saved on receiver.
                os.write(fd,b'GPGGA COM3 1\r\nGPRMC COM3 1\r\nAGRICA COM3 1\r\nUNIHEADINGA COM3 1\r\n')
                buf=b''
                while True:
                    if not select.select([fd],[],[],1)[0]: continue
                    chunk=os.read(fd,4096)
                    if not chunk: raise OSError('GPS disconnected')
                    buf+=chunk
                    while b'\n' in buf:
                        line,buf=buf.split(b'\n',1)
                        try: self.parse(line.decode('ascii'))
                        except (ValueError,IndexError,UnicodeError): pass
                    if len(buf)>16384: buf=b''
            except OSError as e:
                with self.lock: self.data.update(connected=False,error=str(e))
            finally:
                if fd is not None: os.close(fd)
            time.sleep(2)

gps=GPS()
consumption=Consumption()
platform=PlatformStatus()
recorder=None
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(Path(__file__).parent),**kwargs)
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/diagnostics':
            try:
                d=json.loads(Path('/run/harpoon-diagnostics/status.json').read_text())
                uptime=float(Path('/proc/uptime').read_text().split()[0])
                d['stale']=(d.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip() or not 0<=uptime-d.get('uptime_s',-999)<45)
                return self.json_response(d)
            except (OSError,ValueError,TypeError):return self.json_response({'stale':True,'error':'Diagnostics unavailable'},503)
        if path == '/sessions':
            return self.json_response(recorder.status() if recorder else {'error':'Журнал недоступний','sessions':[]},200 if recorder else 503)
        if path in ('/sessions.csv','/track'):
            try:
                params = parse_qs(urlsplit(self.path).query)
                sid = int(params['id'][0])
                if not recorder or not recorder.exists(sid):
                    return self.send_error(404)
                if path == '/track': return self.json_response({'points':recorder.track(sid,int(params.get('after',['-1'])[0]))})
                self.send_response(200)
                self.send_header('Content-Type','text/csv; charset=utf-8')
                self.send_header('Content-Disposition',f'attachment; filename="harpoon-session-{sid}.csv"')
                self.send_header('Cache-Control','no-store');self.end_headers()
                for chunk in recorder.csv_rows(sid): self.wfile.write(chunk.encode('utf-8'))
                return
            except (ValueError,KeyError): return self.send_error(400)
        if self.path in ('/telemetry','/health'):
            payload={'profile':'pi5-gps-monitor','controls_available':False,'gps':gps.snapshot(),'system':platform.snapshot(),**consumption.snapshot()}
            data=json.dumps(payload,allow_nan=False).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        elif self.path.split('?')[0] in ('/','/index.html','/hud.css','/economy.css','/hud.js','/ui-tools.js','/ui-tools.css','/reader.js','/camera-player.js','/leaflet.js','/leaflet.css','/diagnostics.css','/diagnostics.js'):
            super().do_GET()
        else: self.send_error(404)
    def json_response(self,payload,status=200):
        data=json.dumps(payload,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_POST(self):
        if self.path in ('/sessions/start','/sessions/stop','/sessions/delete'):
            # Browser-only same-origin operation; no credentials or control endpoints exposed.
            origin=self.headers.get('Origin')
            if self.headers.get('X-Harpoon-Session')!='1' or (origin and urlsplit(origin).netloc!=self.headers.get('Host')):
                return self.send_error(403)
            if not recorder: return self.json_response({'error':'Журнал недоступний'},503)
            try:
                if self.path.endswith('/delete'):
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=1024: return self.send_error(400)
                    data=json.loads(self.rfile.read(length))
                    if data.get('confirm')!='DELETE': return self.send_error(400)
                    sid=None if data.get('all') is True else int(data['id'])
                    return self.json_response(recorder.delete(sid))
                return self.json_response(recorder.start() if self.path.endswith('/start') else recorder.stop())
            except (ValueError,KeyError) as e: return self.json_response({'error':str(e)},409)
            except Exception as e: return self.json_response({'error':str(e)},503)
        self.send_error(409,'STM migration pending; monitoring only')
    def log_message(self,*args): pass

if __name__=='__main__':
    import signal
    consumption.restore_boot(os.environ.get('HARPOON_SESSION_DIR','/var/lib/harpoon-gps'),Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    def shutdown(*_):
        consumption.save_boot()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown)
    signal.signal(signal.SIGINT,shutdown)
    try:
        recorder=SessionLog(os.environ.get('HARPOON_SESSION_DIR','/var/lib/harpoon-gps'))
        threading.Thread(target=recorder.run,args=(gps,consumption),daemon=True).start()
    except Exception as e: print('Session log unavailable:',e,flush=True)
    try:
        from jk_bms import poll_forever
        threading.Thread(target=poll_forever,args=(os.environ.get('HARPOON_BMS_PORT','/dev/harpoon-gps-unconfigured'),consumption,1,0.5),daemon=True).start()
    except ImportError as e: consumption.update(bms_link_ok=False,bms_error=str(e))
    threading.Thread(target=gps.run,daemon=True).start()
    threading.Thread(target=consumption.run,args=(gps,),daemon=True).start()
    threading.Thread(target=platform.run,args=(gps,consumption),daemon=True).start()
    class Server(ThreadingHTTPServer):
        request_queue_size=128
        daemon_threads=True
    Server(('0.0.0.0',8080),Handler).serve_forever()
