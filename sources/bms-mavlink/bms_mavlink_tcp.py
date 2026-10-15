"""Read-only MAVLink telemetry server bound to the Pi's Tailscale address.

Incoming client bytes are discarded, never forwarded to a flight controller.
Slow clients are disconnected so they cannot stall other readers indefinitely.
"""
import io
import json
import os
import select
import socket
import time
import urllib.request
from bms_mavlink import mav, battery_message, named_messages


def main():
    address = (os.environ.get('BMS_TCP_BIND', '100.82.12.5'),
               int(os.environ.get('BMS_TCP_PORT', '14551')))
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(address)
    listener.listen(4)
    listener.setblocking(False)
    clients = []
    buf = io.BytesIO()
    sender = mav.MAVLink(buf, srcSystem=1, srcComponent=191)
    http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_log = 0
    batches = 0
    print(f'TCP read-only telemetry on {address[0]}:{address[1]}', flush=True)
    while True:
        started = time.monotonic()
        for _ in range(8):
            try:
                client, peer = listener.accept()
            except BlockingIOError:
                break
            if len(clients) >= 4:
                client.close()
                continue
            client.settimeout(0.1)
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            clients.append(client)
            print(f'Client connected: {peer[0]}', flush=True)
        error = None
        try:
            with http.open('http://127.0.0.1:8080/telemetry', timeout=2) as response:
                data = json.load(response)
        except Exception as exc:
            data, error = {}, str(exc)
        fresh = data.get('bms', {}).get('bms_link_ok') is True
        buf.seek(0)
        buf.truncate()
        sender.heartbeat_send(mav.MAV_TYPE_ONBOARD_CONTROLLER, mav.MAV_AUTOPILOT_INVALID,
                              0, 0, mav.MAV_STATE_ACTIVE if fresh else mav.MAV_STATE_CRITICAL)
        sender.send(battery_message(data, 10))
        for message in named_messages(data, int(time.monotonic() * 1000)):
            sender.send(message)
        payload = buf.getvalue()
        for client in clients[:]:
            try:
                if select.select([client], [], [], 0)[0]:
                    if not client.recv(4096):
                        raise ConnectionError('Client closed')
                client.sendall(payload)
                batches += 1
            except OSError:
                clients.remove(client)
                client.close()
        if time.monotonic() - last_log >= 30:
            print(json.dumps({'clients': len(clients), 'sent_batches': batches,
                              'bms_fresh': fresh, 'source_error': error}), flush=True)
            last_log = time.monotonic()
        time.sleep(max(0.05, 1 - (time.monotonic() - started)))


if __name__ == '__main__':
    main()
