"""Read-only GPS trip recorder. No MAVLink commands or actuator access."""
import json, math, sqlite3, threading, time
from pathlib import Path
from urllib.request import urlopen

def distance(a,b):
    p,q=map(math.radians,(a[0],b[0]));d=math.radians(b[0]-a[0]);l=math.radians(b[1]-a[1])
    return 6371000*2*math.asin(min(1,math.sqrt(math.sin(d/2)**2+math.cos(p)*math.cos(q)*math.sin(l/2)**2)))

class Voyage:
    def __init__(self,path,boot):
        self.lock=threading.RLock();self.db=sqlite3.connect(path,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS trips (boot TEXT PRIMARY KEY, data TEXT)')
        self.boot=boot;row=self.db.execute('SELECT data FROM trips WHERE boot=?',(boot,)).fetchone()
        self.data=json.loads(row[0]) if row else dict(points=[],distance_m=0,started=None,gaps=0)
        self.last=None;self.candidate=None;self.moving=0;self.segment=bool(self.data['points']);self.error=None;self.gps={};self.sample_at=0;self.saved=0
    def update(self,g,now):
        with self.lock:
            self.gps=g;self.sample_at=now
            valid=g.get('position_valid') and g.get('link_ok') and isinstance(g.get('position_age_s'),(int,float)) and 0<=g['position_age_s']<3
            coords=(g.get('latitude'),g.get('longitude'))
            valid=valid and all(type(v) in (int,float) and math.isfinite(v) for v in coords)
            valid=valid and abs(coords[0])<=90 and abs(coords[1])<=180
            if not valid:
                self.last=None;self.candidate=None;self.moving=0;self.segment=bool(self.data['points']);return
            point=[*coords,now,False]
            speed=g.get('speed_kmh');moving=type(speed) in (int,float) and math.isfinite(speed) and 1<=speed<=100
            if self.last and (now-self.last[2]>5 or distance(self.last,point)>max(15,(now-self.last[2])*28)):
                self.segment=True;self.last=None;self.moving=0;self.candidate=None
            self.last=point
            if not self.data['points']:
                self.data['points'].append(point) # First reliable fix = home.
            if not moving:self.moving=0;self.candidate=None;return
            if self.candidate is None:self.candidate=point
            self.moving+=1
            if self.moving<3 or distance(self.candidate,point)<2:return
            if self.data['started'] is None:self.data['started']=self.candidate[2]
            previous=self.data['points'][-1];delta=distance(previous,point)
            if delta<2:return
            if len(self.data['points'])>=50000:self.error='Ліміт треку: запис зупинено';return
            point[3]=self.segment
            if self.segment:self.data['gaps']+=1
            else:self.data['distance_m']+=delta
            self.segment=False;self.data['points'].append(point)
    def save(self):
        with self.lock:
            self.db.execute('INSERT OR REPLACE INTO trips VALUES (?,?)',(self.boot,json.dumps(self.data)));self.db.commit()
    def snapshot(self,after=0,boot=None):
        with self.lock:
            now=time.monotonic();fresh=now-self.sample_at<3
            state={**self.data,'points':self.data['points'][after if boot==self.boot else 0:]}
            return dict(**state,boot=self.boot,elapsed_s=max(0,now-self.data['started']) if self.data['started'] is not None else 0,
                        gps=self.gps if fresh else {},fresh=fresh,error=self.error)
    def run(self):
        while True:
            try:
                with urlopen('http://127.0.0.1:8080/telemetry',timeout=2) as r:g=json.load(r).get('gps',{})
                self.update(g,time.monotonic())
                if time.monotonic()-self.saved>=5:self.save();self.saved=time.monotonic()
            except Exception as e:
                self.update({},time.monotonic());self.error=str(e)
            time.sleep(1)

def start():
    v=Voyage('/var/lib/harpoon-pilot-nav/voyage.sqlite3',Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    threading.Thread(target=v.run,daemon=True).start();return v
