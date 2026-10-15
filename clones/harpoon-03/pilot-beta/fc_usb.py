"""Select one MatekH743 main USB interface, independent of serial and socket."""
from pathlib import Path

def resolve_port(root='/dev/serial/by-id'):
    ports={str(p.resolve()):str(p) for p in Path(root).glob('usb-ArduPilot_MatekH743_*-if00') if p.exists()}
    if not ports:raise OSError('USB: MatekH743 не знайдено; повторний пошук через 3 с')
    if len(ports)!=1:raise OSError('USB: знайдено кілька MatekH743; залиш один польотник підключеним')
    return next(iter(ports.values()))
