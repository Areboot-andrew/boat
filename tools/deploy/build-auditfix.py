"""Build six-file board-specific upgrades against downloaded live baselines."""
import hashlib,io,json,tarfile,subprocess,sys,difflib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
src=root/'clones/harpoon-03/pilot-beta'
for board in ([int(sys.argv[1])] if len(sys.argv)>1 else (2,3,4)):
 subprocess.run([sys.executable,str(root/'clones/harpoon-02/latest-20261014/build.py'),str(board)],check=True)
 pilot='pilot' if board==2 else 'pilot-beta'
 with tarfile.open(root/f'work/pi0{board}-auditfix-baseline.tar.gz') as a:
  old={m.name:a.extractfile(m).read() for m in a if m.isfile()}
 with tarfile.open(root/f'clones/harpoon-0{board}/latest-20261014/latest-app.tar.gz') as a:
  new={n:a.extractfile(n).read() for n in old if n!='gps-ui/gps_monitor.py'}
 gps=old['gps-ui/gps_monitor.py'].decode()
 anchor="        d['position_age_s'] = round(now-d['position_at'],3) if d['position_at'] else None"
 assert gps.count(anchor)==1 and 'heading_age_s' not in gps
 gps=gps.replace(anchor,anchor+"\n        d['heading_age_s'] = round(now-d['heading_at'],3) if d['heading_at'] else None\n        d['speed_age_s'] = round(now-d['speed_at'],3) if d['speed_at'] else None")
 new['gps-ui/gps_monitor.py']=gps.encode()
 for n,data in new.items():
  if n.endswith('.py'):compile(data,n,'exec')
  print('BOARD',board,n,'changed lines',sum(1 for l in difflib.unified_diff(old[n].decode().splitlines(),data.decode().splitlines()) if l.startswith(('+','-'))))
 manifest=dict(board=board,hostname='harpoon-pi5' if board==1 else f'harpoon-pi5-0{board}',old={n:hashlib.sha256(v).hexdigest() for n,v in old.items()},new={n:hashlib.sha256(v).hexdigest() for n,v in new.items()})
 out=root/f'work/pi0{board}-auditfix.tar.gz'
 with tarfile.open(out,'w:gz') as a:
  for n,data in {**new,'manifest.json':json.dumps(manifest).encode()}.items():
   info=tarfile.TarInfo(n);info.size=len(data);info.mode=0o644;a.addfile(info,io.BytesIO(data))
 (root/f'work/pi0{board}-auditfix-manifest.json').write_text(json.dumps(manifest,indent=2))
 print('BUNDLE',board,hashlib.sha256(out.read_bytes()).hexdigest())
with tarfile.open(root/'work/auditfix-tests.tar.gz','w:gz') as a:
 for p in src.glob('*.py'):
  if p.name in ('control_service.py','control_runner.py','autonav.py','fc_usb.py') or p.name.startswith('test_'):a.add(p,arcname=p.name)
