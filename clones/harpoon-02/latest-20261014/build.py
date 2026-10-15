"""Prepare current Pi02 app sources; does not connect or install anything."""
import hashlib,io,json,re,tarfile,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[3]
source=repo/'clones/harpoon-03/pilot-beta'
out=Path(__file__).parent
board=int(sys.argv[1]) if len(sys.argv)>1 else 2
assert board in (1,2,3,4)
label=f'Pi{board:02}';hostname='harpoon-pi5' if board==1 else f'harpoon-pi5-{board:02}';tail={1:'100.82.12.5',2:'100.93.62.62',3:'100.64.128.45',4:'192.168.10.50'}[board]
if board==1:out=repo/'clones/harpoon-01/latest-20261014';out.mkdir(parents=True,exist_ok=True)
if board==3:out=repo/'clones/harpoon-03/latest-20261014';out.mkdir(parents=True,exist_ok=True)
if board==4:out=repo/'clones/harpoon-04/latest-20261014';out.mkdir(parents=True,exist_ok=True)
files={}
for asset in (repo/'sources/monitor-assets').iterdir():
 if asset.is_file() and asset.suffix in ('.html','.js','.css'):
  files['pilot/monitor-assets/'+asset.name]=asset.read_bytes()
pilot_names=('server.py','control_proxy.py','beta.js','beta.css','live-control.js','pad-config.js','navigation.js','navigation.css','voyage.py','auto-ui.css','route-editor.js','route-editor.css')
for name in pilot_names:files['pilot/'+name]=(source/name).read_bytes()
for name in ('control_service.py','control_runner.py','fc_usb.py','autonav.py'):files['web-control/'+name]=(source/name).read_bytes()
for key,data in list(files.items()):
 text=data.decode().replace('harpoon-pi5-03',hostname).replace('Pi03',label).replace('PILOT ОІ / 03',f'PILOT ОІ / {board:02}').replace('harpoon.pi03.',f'harpoon.pi{board:02}.').replace('100.64.128.45',tail)
 if key=='pilot/control_proxy.py':
  text=re.sub(r'HOSTS=\{[^\n]+\}',f"HOSTS={{'{tail}','192.168.10.50','127.0.0.1','localhost','{hostname}','{hostname}.tail15f590.ts.net'}}",text)
 if key=='web-control/control_runner.py' and board in (1,2,3):
  assert text.count('    MAX_THROTTLE = .7')==1
  text=text.replace('    MAX_THROTTLE = .7',f'    MAX_THROTTLE = .7\n    ALLOW_CRITICAL_MANUAL = True  # Explicit {label} owner request, 14.10.2026')
  text=text.replace('    ALLOW_CRITICAL_AUTONAV = False','    ALLOW_CRITICAL_AUTONAV = True')
 files[key]=text.encode()
 if key.endswith('.py'):compile(text,key,'exec')
key='pilot/server.py';text=files[key].decode()
anchor='        if path not in ALLOWED:'
assert text.count(anchor)==1
text=text.replace(anchor,"""        if path == '/diagnostics':
            try:
                d=json.loads(Path('/run/harpoon-diagnostics/status.json').read_text())
                uptime=float(Path('/proc/uptime').read_text().split()[0])
                d['stale']=(d.get('boot_id')!=Path('/proc/sys/kernel/random/boot_id').read_text().strip() or not 0<=uptime-d.get('uptime_s',-999)<90)
                return self.json_response(d)
            except (OSError,ValueError,TypeError):return self.json_response({'stale':True,'error':'Diagnostics unavailable'},503)
"""+anchor)
old="""            with urlopen('http://127.0.0.1:8080' + self.path, timeout=4) as response:
                body, mime = response.read(), response.headers.get('Content-Type', 'application/octet-stream')"""
new="""            asset=ROOT/'monitor-assets'/('index.html' if path=='/' else path[1:])
            if path in ('/','/index.html') or path.endswith(('.js','.css')):
                import mimetypes
                body=asset.read_bytes();mime=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream'
            else:
                with urlopen('http://127.0.0.1:8080' + self.path, timeout=4) as response:
                    body, mime = response.read(), response.headers.get('Content-Type', 'application/octet-stream')"""
assert old in text;text=text.replace(old,new);compile(text,key,'exec');files[key]=text.encode()
if board in (1,3,4):files={k.replace('pilot/','pilot-beta/',1) if k.startswith('pilot/') else k:v for k,v in files.items()}
with tarfile.open(out/'latest-app.tar.gz','w:gz') as archive:
 for name,data in sorted(files.items()):
  info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;archive.addfile(info,io.BytesIO(data))
manifest={'board':label,'target':tail,'hostname':hostname,'status':'PREPARED_NOT_DEPLOYED','sha256':hashlib.sha256((out/'latest-app.tar.gz').read_bytes()).hexdigest(),'files':{k:hashlib.sha256(v).hexdigest() for k,v in sorted(files.items())},'preserve':['camera/GPS/BMS configs','Tail identity and keys','internal control key','sessions','voyage database','autonav settings and routes','flight-controller parameters'],'required_before_install':['pinned SSH identity','live file/service comparison','DISARMED/no lease/zero intent and applied before controller restart','backup']}
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared',label,len(files),'current application files:',manifest['sha256'])
