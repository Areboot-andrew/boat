set -eu
test "$(hostname)" = harpoon-pi5-03
test "$(tailscale ip -4)" = 100.64.128.45
target=/etc/systemd/system/harpoon-bms-mavlink.service.d/60-tail-telemetry.conf
test ! -e "$target"
backup=$(mktemp -d /var/backups/harpoon-pi03-tail-telemetry-20261014.XXXXXX)
chmod 700 "$backup"
cp -a /etc/systemd/system/harpoon-bms-mavlink.service.d "$backup/"
systemctl cat harpoon-bms-mavlink > "$backup/unit-before.txt"
install -m 644 /tmp/pi03-tail-telemetry.conf "$target"
systemctl daemon-reload
systemctl restart harpoon-bms-mavlink
systemctl is-active harpoon-bms-mavlink
printf 'Backup: %s\n' "$backup"
/opt/harpoon/mavlink-venv/bin/python - <<'PY'
import socket,time,collections
from pymavlink.dialects.v20 import common as mav
s=socket.create_connection(('100.64.128.45',14551),timeout=5);s.settimeout(2)
p=mav.MAVLink(None);counts=collections.Counter();battery=None
end=time.monotonic()+4
while time.monotonic()<end:
 for m in p.parse_buffer(s.recv(8192)) or []:
  counts[(m.get_srcSystem(),m.get_srcComponent(),m.get_type())]+=1
  if m.get_type()=='BATTERY_STATUS':battery=(m.id,m.battery_remaining)
s.close()
assert battery and battery[0]==10,(counts,battery)
print('Received TCP MAVLink:',dict(counts),'Battery ID / percent:',battery)
PY
systemctl is-active harpoon-qgc-telemetry-udp
