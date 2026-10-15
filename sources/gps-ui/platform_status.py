"""One sampler for every viewer; eth0 rates, temperature and atomic video OSD."""
import math
import os
import threading
import time
from pathlib import Path

def number(value, digits=0):
    return f'{value:.{digits}f}' if isinstance(value, (int, float)) and math.isfinite(value) else '—'

def osd_text(g, sample):
    b = sample.get('bms', {}) if sample.get('bms', {}).get('bms_link_ok') else {}
    e = sample.get('energy', {})
    h = g.get('heading_deg') if g.get('heading_valid') else g.get('course_deg') if g.get('position_valid') and (g.get('speed_kmh') or 0) >= 1 else None
    label = 'КУРС' if g.get('heading_valid') else 'ШЛЯХ'
    return (f'{label} {number(h)}°   |   {number(b.get("battery_power_w"))} Вт   |   АКБ {number(b.get("battery_soc"))}%\n'
            f'ВИТРАТА {number(e.get("instant_wh_km"), 1)} Вт·год/км   |   ЗАПАС ≈ {number(e.get("range_km"), 1)} км')

class PlatformStatus:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}

    def snapshot(self):
        with self.lock:
            return dict(self.data)

    def run(self, gps, consumption):
        previous = None
        path = Path(os.environ.get('HARPOON_SESSION_DIR', '/var/lib/harpoon-gps')) / 'video-osd.txt'
        while True:
            now = time.monotonic()
            data = {'interface': 'eth0', 'rx_mbps': None, 'tx_mbps': None, 'temperature_c': None}
            try:
                base = Path('/sys/class/net/eth0')
                rx = int((base / 'statistics/rx_bytes').read_text())
                tx = int((base / 'statistics/tx_bytes').read_text())
                data['link_up'] = (base / 'carrier').read_text().strip() == '1'
                if previous and now > previous[0] and rx >= previous[1] and tx >= previous[2]:
                    data.update(rx_mbps=(rx-previous[1])*8/(now-previous[0])/1e6, tx_mbps=(tx-previous[2])*8/(now-previous[0])/1e6)
                previous = (now, rx, tx)
            except (OSError, ValueError):
                previous = None
            try:
                data['temperature_c'] = int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000
            except (OSError, ValueError):
                pass
            try:
                temp = path.with_suffix('.tmp')
                temp.write_text(osd_text(gps.snapshot(), consumption.snapshot()), encoding='utf-8')
                temp.replace(path)
            except OSError as error:
                data['osd_error'] = str(error)
            with self.lock:
                self.data = data
            time.sleep(1)
