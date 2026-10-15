set -eu
hostname
systemctl is-active harpoon-web-control || true
systemctl is-enabled harpoon-web-control || true
curl -fsS --max-time 3 http://127.0.0.1:8091/status | python3 -c 'import sys,json; s=json.load(sys.stdin); print({k:s.get(k) for k in ("connected","armed","mode","state","lease_active","heartbeat_age_s","intent","applied")})' || true
pilot=pilot-beta
test "$(hostname)" != harpoon-pi5-02 || pilot=pilot
tar -czf /tmp/harpoon-auditfix-baseline.tar.gz -C /opt/harpoon web-control/control_service.py web-control/control_runner.py web-control/autonav.py "$pilot/live-control.js" "$pilot/pad-config.js" gps-ui/gps_monitor.py
chmod 644 /tmp/harpoon-auditfix-baseline.tar.gz
