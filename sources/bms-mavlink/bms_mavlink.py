"""Transmit-only BMS telemetry. Never opens a flight-controller link or handles commands."""
import json
import math
import os
import socket
import time
import urllib.request
from pymavlink.dialects.v20 import common as mav

def valid(x):
    return isinstance(x, (int, float)) and math.isfinite(x)

def battery_message(data, battery_id):
    b = data.get('bms', {})
    fresh = b.get('bms_link_ok') is True
    v, a, soc = (b.get(k) for k in ('battery_voltage', 'battery_current_a', 'battery_soc'))
    # JK current is negative during discharge; MAVLink uses positive discharge.
    amps = round(-a * 100) if fresh and valid(a) and -327.67 <= -a <= 327.67 else -1
    percent = round(soc) if fresh and valid(soc) and 0 <= soc <= 100 else -1
    # 20 cells exceed BATTERY_STATUS's cell slots. Encode PACK voltage using
    # the documented 65534 mV overflow representation, never truncate the pack.
    volts = [65535] * 10
    if fresh and valid(v) and 0 < v < 655.34:
        remaining = round(v * 1000)
        index = 0
        while remaining > 0:
            volts[index] = min(65534, remaining)
            remaining -= volts[index]
            index += 1
    # Consumption remains unknown for the first stage: don't present a boot
    # counter as consumption since full charge. MOS temperature isn't cell temperature.
    return mav.MAVLink_battery_status_message(
        id=battery_id, battery_function=mav.MAV_BATTERY_FUNCTION_PROPULSION,
        type=mav.MAV_BATTERY_TYPE_UNKNOWN, temperature=32767,
        voltages=volts, current_battery=amps, current_consumed=-1,
        energy_consumed=-1, battery_remaining=percent)

def named_messages(data, stamp):
    b, e = data.get('bms', {}), data.get('energy', {})
    fresh = b.get('bms_link_ok') is True
    fields = (
        (b'HP_PWR_W', b.get('battery_power_w')),
        (b'HP_WH_KM', e.get('instant_wh_km')),
        (b'HP_AVG_WKM', e.get('average_wh_km')),
        (b'HP_RANGEKM', e.get('range_km')),
    )
    return [mav.MAVLink_named_value_float_message(
        stamp & 0xffffffff, name,
        float(value) if fresh and valid(value) and abs(value) < 3.4e38 else float('nan'))
        for name, value in fields]

class DatagramWriter:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.destination = (host, port)
        self.packets = 0
    def write(self, packet):
        self.sock.sendto(packet, self.destination)
        self.packets += 1

def main():
    host = os.environ.get('BMS_QGC_HOST', '172.31.31.7')
    port = int(os.environ.get('BMS_QGC_PORT', '14551'))
    battery_id = int(os.environ.get('BMS_MAV_BATTERY_ID', '10'))
    writer = DatagramWriter(host, port)
    sender = mav.MAVLink(writer, srcSystem=1, srcComponent=191)
    # Ignore proxy environment; telemetry must come from this Pi only.
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_log = 0
    print(f'TX only -> {host}:{port}; system=1 component=191 battery={battery_id}', flush=True)
    while True:
        started = time.monotonic()
        error = None
        try:
            with http.open('http://127.0.0.1:8080/telemetry', timeout=2) as response:
                data = json.load(response)
        except Exception as e:
            data = {}
            error = str(e)
        try:
            fresh = data.get('bms', {}).get('bms_link_ok') is True
            sender.heartbeat_send(mav.MAV_TYPE_ONBOARD_CONTROLLER, mav.MAV_AUTOPILOT_INVALID,
                                  0, 0, mav.MAV_STATE_ACTIVE if fresh else mav.MAV_STATE_CRITICAL)
            sender.send(battery_message(data, battery_id))
            for message in named_messages(data, int(time.monotonic()*1000)):
                sender.send(message)
            if time.monotonic() - last_log >= 30:
                print(json.dumps({'sent_packets':writer.packets,'bms_fresh':fresh,'source_error':error}),flush=True)
                last_log = time.monotonic()
        except OSError as e:
            print('UDP send error: '+str(e),flush=True)
        time.sleep(max(0.05, 1 - (time.monotonic()-started)))

if __name__ == '__main__': main()
