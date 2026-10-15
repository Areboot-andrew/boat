set -eu
/opt/harpoon/mavlink-venv/bin/python - <<'PY'
import socket,time,collections
from pymavlink.dialects.v20 import common as mav
with socket.create_connection(('100.64.128.45',14551),timeout=5) as s:
 s.settimeout(3);p=mav.MAVLink(None);counts=collections.Counter();battery=None;end=time.monotonic()+3
 while time.monotonic()<end:
  for m in p.parse_buffer(s.recv(8192)) or []:
   counts[(m.get_srcSystem(),m.get_srcComponent(),m.get_type())]+=1
   if m.get_type()=='BATTERY_STATUS':battery=(m.id,m.battery_remaining)
 assert battery and battery[0]==10,(counts,battery)
 print('Decoded:',dict(counts),'Battery ID / percent:',battery)
PY
