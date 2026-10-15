"""Read-only JK/JiKong PB-series BMS telemetry over Modbus RTU."""
import struct
import time

import serial


def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _request(address, register, count):
    body = bytes((address, 3)) + register.to_bytes(2, "big") + count.to_bytes(2, "big")
    checksum = crc16(body)
    return body + bytes((checksum & 255, checksum >> 8))


def _read_registers(port, address, register, count, retries=3):
    for _ in range(retries):
        port.reset_input_buffer()
        port.write(_request(address, register, count))
        port.flush()
        deadline = time.monotonic() + 0.6
        buffer = bytearray()
        while time.monotonic() < deadline:
            buffer.extend(port.read(port.in_waiting or 1))
            while len(buffer) >= 2 and not (buffer[0] == address and buffer[1] in (3, 0x83)):
                del buffer[0]
            if len(buffer) >= 3:
                needed = 5 if buffer[1] == 0x83 else 5 + buffer[2]
                if len(buffer) >= needed:
                    frame = bytes(buffer[:needed])
                    if crc16(frame[:-2]) == (frame[-2] | frame[-1] << 8) and frame[1] == 3:
                        return frame[3:-2]
                    break
        time.sleep(0.12)
    raise RuntimeError("JK BMS did not return a valid frame")


def read_status(port, address=1):
    result = bytearray()
    for block in range(4):
        result.extend(_read_registers(port, address, 0x1200 + block * 0x40, 32))
    return bytes(result)


def parse_status(data):
    u16 = lambda offset: struct.unpack_from(">H", data, offset)[0]
    i16 = lambda offset: struct.unpack_from(">h", data, offset)[0]
    u32 = lambda offset: struct.unpack_from(">I", data, offset)[0]
    i32 = lambda offset: struct.unpack_from(">i", data, offset)[0]
    all_cells = [u16(index * 2) / 1000.0 for index in range(32)]
    cells = [value for value in all_cells if 1.0 <= value <= 5.0]
    if not cells:
        raise RuntimeError("JK BMS returned no active cells")
    voltage = u32(144) / 1000.0
    current = i32(152) / 1000.0
    temperature = lambda raw: None if raw <= -1000 else raw / 10.0
    return {
        "bms_link_ok": True,
        "battery_voltage": voltage,
        "battery_current_a": current,
        "battery_power_w": voltage * current,
        "battery_soc": data[167],
        "battery_remaining_ah": max(0.0, i32(168) / 1000.0),
        "battery_full_ah": u32(172) / 1000.0,
        "bms_alarm_mask": u32(160),
        "bms_balance_current_a": i16(164) / 1000.0,
        "bms_mos_temp_c": temperature(i16(138)),
        "bms_t1_c": temperature(i16(156)),
        "bms_t2_c": temperature(i16(158)),
        "cell_count": len(cells),
        "cell_min_v": min(cells),
        "cell_max_v": max(cells),
        "cell_delta_mv": (max(cells) - min(cells)) * 1000.0,
        "cell_voltages": cells,
    }


def poll_forever(path, state, address=1, interval=0.5, on_sample=None):
    while True:
        try:
            with serial.Serial(path, 115200, timeout=0.025) as port:
                while True:
                    started = time.monotonic()
                    sample=parse_status(read_status(port, address))
                    state.update(**sample,bms_error=None)
                    if on_sample:on_sample(sample)
                    time.sleep(max(0.0, interval - (time.monotonic() - started)))
        except Exception as error:
            state.update(bms_link_ok=False, bms_error=str(error))
            time.sleep(2.0)
