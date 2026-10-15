set -eu
python3 - <<'PY'
import hashlib,json,subprocess,tarfile
from pathlib import Path
from urllib.request import urlopen
host=subprocess.check_output(['hostname'],text=True).strip();board=1 if host=='harpoon-pi5' else int(host[-2:])
with tarfile.open(f'/tmp/pi0{board}-auditfix.tar.gz') as a:m=json.load(a.extractfile('manifest.json'))
for name,sha in m['new'].items():assert hashlib.sha256((Path('/opt/harpoon')/name).read_bytes()).hexdigest()==sha,name
for name in ('live-control.js','pad-config.js'):
 with urlopen('http://127.0.0.1:8090/'+name,timeout=5) as r:data=r.read()
 prefix='pilot' if board==2 else 'pilot-beta'
 assert hashlib.sha256(data).hexdigest()==m['new'][prefix+'/'+name],name
 print(host,name,'HTTP200 and deployed SHA verified')
with urlopen('http://127.0.0.1:8080/telemetry',timeout=5) as r:g=json.load(r)['gps']
assert all(k in g for k in ('position_age_s','heading_age_s','speed_age_s'))
print('GPS source ages:',{k:g.get(k) for k in ('position_age_s','heading_age_s','speed_age_s','link_ok','heading_valid','position_valid')})
if board!=4:
 with urlopen('http://127.0.0.1:8091/status',timeout=3) as r:s=json.load(r)
 print('Controller:',{k:s.get(k) for k in ('connected','armed','mode','state','heartbeat_age_s','lease_active','intent','applied','blocked','network_timeout_s','manual_critical_allowed','autonav_critical_allowed')})
 assert s['connected'] and s['network_timeout_s']==3
else:
 assert subprocess.run(['systemctl','is-active','--quiet','harpoon-web-control']).returncode!=0
 print('Pi04 controller remains disabled/inactive, not commissioned')
PY
journalctl -u harpoon-web-control -u harpoon-gps-monitor --since '-3 min' --no-pager -p err -n 12
