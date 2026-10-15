"""Local 2 Hz session recorder. No control commands; missing readings stay NULL."""
import csv
import io
import math
import os
import shutil
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone

FIELDS = ('seq','utc','elapsed_s','latitude','longitude','speed_kmh','heading_deg',
          'course_deg','gps_valid','gps_age_s','bms_valid','voltage_v','current_a',
          'power_w','remaining_ah','soc_pct','consumed_wh','consumed_ah','distance_km')

class SessionLog:
    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.directory = directory
        self.path = os.path.join(directory, 'sessions.sqlite3')
        self.lock = threading.RLock()
        self.db = sqlite3.connect(os.path.join(directory, 'sessions.sqlite3'), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY, started TEXT NOT NULL, ended TEXT, status TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS samples (
            session_id INTEGER NOT NULL REFERENCES sessions(id), seq INTEGER NOT NULL,
            utc TEXT NOT NULL, elapsed_s REAL NOT NULL, latitude REAL, longitude REAL,
            speed_kmh REAL, heading_deg REAL, course_deg REAL, gps_valid INTEGER,
            gps_age_s REAL, bms_valid INTEGER, voltage_v REAL, current_a REAL, power_w REAL,
            remaining_ah REAL, soc_pct REAL, consumed_wh REAL, consumed_ah REAL, distance_km REAL,
            PRIMARY KEY(session_id,seq));
        ''')
        # A reboot is a recording boundary; retain every committed sample.
        self.db.execute("UPDATE sessions SET status='interrupted', ended=? WHERE status='recording'", (self.utc(),))
        self.db.commit()
        self.active = None
        self.error = None
        self.previous = None
        self.seq = 0
        self.wh = self.ah = self.km = 0.0
        self._totals = self._read_totals()

    def read_rows(self, sql, args=()):
        # Independent WAL reader: disk flushes never hold the telemetry lock.
        with closing(sqlite3.connect(self.path, timeout=2)) as db:
            db.row_factory = sqlite3.Row
            return db.execute(sql,args).fetchall()

    def exists(self, sid):
        return bool(self.read_rows('SELECT id FROM sessions WHERE id=?',(sid,)))

    @staticmethod
    def utc():
        return datetime.now(timezone.utc).isoformat(timespec='milliseconds')

    def start(self):
        with self.lock:
            if self.active is not None: return self.status()
            if shutil.disk_usage(self.directory).free < 20*1024*1024:
                raise OSError('Мало місця для журналу: потрібно понад 20 МБ')
            cursor = self.db.execute("INSERT INTO sessions(started,status) VALUES(?,'recording')", (self.utc(),))
            self.db.commit()
            self.active = cursor.lastrowid
            self.started = time.monotonic()
            self.previous = None
            self.seq = 0
            self.wh = self.ah = self.km = 0.0
            self.error = None
            self._totals = {'consumed_wh':0,'consumed_ah':0,'distance_km':0,'elapsed_s':0}
            return self.status()

    def stop(self):
        with self.lock:
            if self.active is not None:
                self.db.execute("UPDATE sessions SET ended=?,status='saved' WHERE id=?", (self.utc(), self.active))
                self.db.commit()
                self.active = None
            return self.status()

    def status(self):
        rows = self.read_rows('SELECT * FROM sessions ORDER BY id DESC LIMIT 100')
        return {'active_id':self.active, 'error':self.error, 'interval_s':0.5,
                'sessions':[dict(r) for r in rows]}

    def totals(self):
        return dict(self._totals) if self._totals is not None else None

    def _read_totals(self):
        session = self.read_rows('SELECT id FROM sessions ORDER BY id DESC LIMIT 1')
        if not session: return None
        rows = self.read_rows('SELECT consumed_wh,consumed_ah,distance_km,elapsed_s FROM samples WHERE session_id=? ORDER BY seq DESC LIMIT 1',(session[0]['id'],))
        return dict(rows[0]) if rows else {'consumed_wh':0,'consumed_ah':0,'distance_km':0,'elapsed_s':0}

    def delete(self, sid=None):
        with self.lock:
            if self.active is not None: raise ValueError('Спочатку завершіть запис через SAVE')
            with self.db:
                if sid is None:
                    self.db.execute('DELETE FROM samples')
                    self.db.execute('DELETE FROM sessions')
                else:
                    self.db.execute('DELETE FROM samples WHERE session_id=?',(sid,))
                    self.db.execute('DELETE FROM sessions WHERE id=?',(sid,))
            self._totals=self._read_totals()
            return self.status()

    def sample(self, gps, bms, now=None, trip=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if self.active is None: return
            if self.seq % 120 == 0 and shutil.disk_usage(self.directory).free < 20*1024*1024:
                raise OSError('Запис зупинено: на картці менше 20 МБ')
            def num(data, key):
                value = data.get(key)
                return value if isinstance(value, (float,int)) and math.isfinite(value) else None
            valid = bool(gps.get('position_valid'))
            speed = num(gps, 'speed_kmh') if valid else None
            if speed is not None and not 0 <= speed <= 150: speed = None
            bvalid = bool(bms.get('bms_link_ok'))
            b = bms if bvalid else {}
            voltage, current = num(b,'battery_voltage'), num(b,'battery_current_a')
            power = voltage*current if voltage is not None and current is not None else None
            discharge = max(0,-power) if power is not None else None
            amps = max(0,-current) if current is not None else None
            moving = max(0,speed) if speed is not None and speed >= 1 else 0 if speed is not None else None
            if self.previous:
                stamp, p, a, s = self.previous
                dt = now-stamp
                if 0 < dt <= 1.5:
                    if p is not None and discharge is not None:
                        self.wh += (p+discharge)*dt/7200
                        self.ah += (a+amps)*dt/7200
                    if s is not None and moving is not None: self.km += (s+moving)*dt/7200
            values = (self.seq, self.utc(), round(now-self.started,3),
                      num(gps,'latitude') if valid else None, num(gps,'longitude') if valid else None,
                      speed, num(gps,'heading_deg'), num(gps,'course_deg'), int(valid),
                      num(gps,'position_age_s'), int(bvalid), voltage, current, power,
                      num(b,'battery_remaining_ah'), num(b,'battery_soc'),
                      trip['consumed_wh'] if trip else self.wh, trip['consumed_ah'] if trip else self.ah, trip['distance_km'] if trip else self.km)
            self.db.execute('INSERT INTO samples VALUES ('+','.join('?' for _ in range(20))+')', (self.active,)+values)
            self.db.commit()
            self._totals={'consumed_wh':self.wh,'consumed_ah':self.ah,'distance_km':self.km,'elapsed_s':round(now-self.started,3)}
            self.seq += 1
            self.previous = (now,discharge,amps,moving)

    def csv_rows(self, sid):
        # Bounded batches: neither long read transactions nor full-file RAM copies.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(FIELDS)
        yield '\ufeff'+buffer.getvalue()
        last = -1
        ceiling = self.read_rows('SELECT MAX(seq) FROM samples WHERE session_id=?',(sid,))[0][0]
        if ceiling is None: return
        while True:
            rows = self.read_rows('SELECT '+','.join(FIELDS)+' FROM samples WHERE session_id=? AND seq>? AND seq<=? ORDER BY seq LIMIT 256',(sid,last,ceiling))
            if not rows: return
            buffer.seek(0);buffer.truncate(0)
            writer.writerows(rows)
            yield buffer.getvalue()
            last = rows[-1]['seq']

    def track(self, sid, after=-1):
        rows = self.read_rows('SELECT seq,utc,latitude,longitude,speed_kmh,gps_valid FROM samples WHERE session_id=? AND seq>? ORDER BY seq LIMIT 2000',(sid,after))
        return [dict(row) for row in rows]

    def run(self, gps, consumption):
        deadline = time.monotonic()
        while True:
            try:
                snapshot=consumption.snapshot()
                self.sample(gps.snapshot(),snapshot['bms'],trip=snapshot['energy'])
            except (sqlite3.Error,OSError) as e:
                with self.lock:
                    self.db.rollback()
                    self.error = str(e)
                    try: self.stop()
                    except sqlite3.Error: self.active = None
            deadline += 0.5
            time.sleep(max(0,deadline-time.monotonic()))
            if time.monotonic()-deadline > 0.5: deadline = time.monotonic()
