"""Guarded Raspberry-only six-file update. Never sends FC commands."""
import hashlib,json,os,shutil,subprocess,sys,tarfile,tempfile,time
from pathlib import Path
from urllib.request import urlopen
board=int(sys.argv[1]);expected=sys.argv[2]
assert board in (1,2,3,4)
assert subprocess.check_output(['hostname'],text=True).strip()==('harpoon-pi5' if board==1 else f'harpoon-pi5-0{board}')
root=Path('/opt/harpoon');pilot='pilot' if board==2 else 'pilot-beta'
bundle=Path(f'/tmp/pi0{board}-auditfix.tar.gz')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(bundle)==expected,'Wrong package'
names={'web-control/control_service.py','web-control/control_runner.py','web-control/autonav.py',f'{pilot}/live-control.js',f'{pilot}/pad-config.js','gps-ui/gps_monitor.py'}
with tarfile.open(bundle) as a:
 manifest=json.load(a.extractfile('manifest.json'))
 assert set(manifest['new'])==names and manifest['board']==board
 files={n:a.extractfile(n).read() for n in names}
for n,data in files.items():
 assert hashlib.sha256(data).hexdigest()==manifest['new'][n]
 assert sha(root/n)==manifest['old'][n],n+' differs from audited baseline'
 if n.endswith('.py'):compile(data,n,'exec')
active=lambda unit:subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0
controller='harpoon-web-control';monitor='harpoon-gps-monitor'
was_control=active(controller);was_monitor=active(monitor)
def guard():
 assert active(controller)==was_control,'Controller state changed'
 if not was_control:
  assert subprocess.run(['systemctl','is-enabled',controller],text=True,capture_output=True).stdout.strip()=='disabled'
  return
 with urlopen('http://127.0.0.1:8091/status',timeout=3) as r:s=json.load(r)
 assert s['connected'] and s['heartbeat_age_s']<2 and not s['armed'] and not s['lease_active'],'Require fresh DISARMED, no lease'
 assert all(abs(v)<.001 for v in s['intent']+s['applied']),'Non-neutral controller'
def preserved():
 return {str(p):sha(p) for p in [*Path('/etc/harpoon').rglob('*'),root/pilot/'control_proxy.py'] if p.is_file()}
guard();before=preserved()
backup=Path(tempfile.mkdtemp(prefix=f'harpoon-pi0{board}-auditfix-20261014.',dir='/var/backups'));backup.chmod(0o700)
for n in names:
 p=backup/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/n,p)
(backup/'manifest.json').write_text(json.dumps(manifest,indent=2))
guard()
if was_control:subprocess.run(['systemctl','stop',controller],check=True)
try:
 if was_monitor:subprocess.run(['systemctl','stop',monitor],check=True)
 for n,data in files.items():
  p=root/n;st=p.stat();tmp=p.with_name(p.name+'.auditfix-new')
  with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.chown(tmp,st.st_uid,st.st_gid);tmp.chmod(st.st_mode&0o777);os.replace(tmp,p)
 if was_monitor:subprocess.run(['systemctl','start',monitor],check=True)
 if was_control:subprocess.run(['systemctl','start',controller],check=True)
 time.sleep(2)
 assert active(controller)==was_control and active(monitor)==was_monitor,'Service state mismatch'
 assert before==preserved(),'Unrelated configuration changed'
 assert all(sha(root/n)==manifest['new'][n] for n in names)
except Exception:
 if was_control:subprocess.run(['systemctl','stop',controller],check=False)
 if was_monitor:subprocess.run(['systemctl','stop',monitor],check=False)
 for n in names:shutil.copy2(backup/n,root/n)
 if was_monitor:subprocess.run(['systemctl','start',monitor],check=False)
 if was_control:subprocess.run(['systemctl','start',controller],check=False)
 print('ROLLED BACK',backup,flush=True);raise
print('INSTALLED',board,'BACKUP',backup,'controller_active',was_control,'monitor_active',was_monitor,flush=True)
print('All six hashes verified; /etc/harpoon and proxy unchanged',flush=True)
