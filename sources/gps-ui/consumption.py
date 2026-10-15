"""Matched fresh GPS/BMS intervals; negative JK current means discharge."""
import math,time,threading,os,logging,json
from logging.handlers import RotatingFileHandler
class Consumption:
    def __init__(self):
        self.lock=threading.RLock();self.bms={};self.bms_at=None;self.previous=None
        self.wh=self.ah=self.matched_wh=self.km=self.valid_seconds=0.0
        self.distance_km=0.0;self.previous_speed=None;self.state_path=None
        self.instant=None;self.ready=False;self.session_id=time.strftime('%Y%m%d-%H%M%S');self.log_error=None
    def restore_boot(self,directory,boot_id):
        self.state_path=os.path.join(directory,'trip-state.json');self.session_id=boot_id
        os.makedirs(directory,exist_ok=True)
        try:
            with open(self.state_path) as f: state=json.load(f)
            if state.get('boot_id')==boot_id:
                for key in ('wh','ah','matched_wh','km','valid_seconds','distance_km'):
                    value=state.get(key,0)
                    if isinstance(value,(int,float)) and math.isfinite(value) and value>=0:setattr(self,key,value)
        except FileNotFoundError:pass
        except (OSError,ValueError) as e:self.log_error='Trip restore: '+str(e)
    def save_boot(self):
        if not self.state_path:return
        with self.lock:
            data={key:getattr(self,key) for key in ('wh','ah','matched_wh','km','valid_seconds','distance_km')}
            data['boot_id']=self.session_id
            with open(self.state_path+'.tmp','w') as f:json.dump(data,f);f.flush();os.fsync(f.fileno())
            os.replace(self.state_path+'.tmp',self.state_path)
    def update(self,**sample):
        with self.lock:
            self.bms.update(sample)
            if sample.get('bms_link_ok'):self.bms_at=time.monotonic()
    def tick(self,gps,now=None):
        now=time.monotonic() if now is None else now
        with self.lock:
            fresh=self.bms.get('bms_link_ok') and self.bms_at is not None and 0<=now-self.bms_at<4
            v=self.bms.get('battery_voltage');a=self.bms.get('battery_current_a')
            valid=fresh and all(isinstance(x,(int,float)) and math.isfinite(x) for x in (v,a)) and v>0
            power=max(0,-v*a) if valid else None;amps=max(0,-a) if valid else None
            speed=gps.get('speed_kmh')
            moving=(speed if speed>=1 else 0) if gps.get('position_valid') and isinstance(speed,(int,float)) and math.isfinite(speed) and 0<=speed<=150 else None
            if self.previous_speed:
                stamp,old_speed=self.previous_speed;dt=now-stamp
                if 0<dt<=2 and moving is not None and old_speed is not None:self.distance_km+=(moving+old_speed)*dt/7200
            self.previous_speed=(now,moving)
            paired=bool(valid and gps.get('position_valid') and isinstance(speed,(int,float)) and math.isfinite(speed) and 0<=speed<=150)
            speed=(speed if speed>=1 else 0) if paired else None
            self.ready=paired;self.instant=power/speed if paired and speed>=1 else None
            if self.previous:
                t,p,amp,s=self.previous;dt=now-t
                if 0<dt<=2 and power is not None and p is not None:
                    energy=(p+power)*0.5*dt/3600
                    self.wh+=energy;self.ah+=(amp+amps)*0.5*dt/3600
                    if speed is not None and s is not None:
                        self.matched_wh+=energy;self.km+=(s+speed)*0.5*dt/3600;self.valid_seconds+=dt
            self.previous=(now,power,amps,speed)
    def snapshot(self):
        with self.lock:
            b=dict(self.bms);fresh=bool(b.get('bms_link_ok') and self.bms_at is not None and time.monotonic()-self.bms_at<4)
            if not fresh:b={k:None for k in b if k!='bms_error'}|{'bms_link_ok':False,'bms_error':self.bms.get('bms_error')}
            avg=self.matched_wh/self.km if self.km>=.1 and self.valid_seconds>=60 else None
            ah=b.get('battery_remaining_ah');v=b.get('battery_voltage')
            remaining=ah*v if fresh and isinstance(ah,(int,float)) and isinstance(v,(int,float)) and ah>=0 and v>0 else None
            estimate=remaining/avg if remaining is not None and avg is not None and avg>0 and self.ready and fresh else None
            return {'bms':b,'energy':{'session_id':self.session_id,'scope':'power-on-trip','consumed_wh':round(self.wh,3),'consumed_ah':round(self.ah,4),'distance_km':round(self.distance_km,4),'instant_wh_km':self.instant if fresh and self.ready else None,'average_wh_km':avg,'range_km':estimate,'remaining_wh_estimate':remaining,'status':'Очікування BMS' if not fresh else 'Очікування GPS' if not self.ready else 'Накопичення: 100 м / 60 с' if avg is None else 'Оцінка без резерву','log_error':self.log_error}}
    def run(self,gps):
        log=None
        try:
            directory=os.environ.get('HARPOON_SESSION_DIR','/var/lib/harpoon-gps');os.makedirs(directory,exist_ok=True)
            log=logging.getLogger('energy-sessions');log.setLevel(logging.INFO)
            log.addHandler(RotatingFileHandler(os.path.join(directory,'consumption.jsonl'),maxBytes=2*1024*1024,backupCount=3))
        except OSError as e:self.log_error=str(e)
        last_log=0
        while True:
            self.tick(gps.snapshot())
            if log and time.monotonic()-last_log>=5:
                log.info(json.dumps({'time':time.time(),**self.snapshot()},ensure_ascii=False));last_log=time.monotonic()
                try:self.save_boot()
                except OSError as e:self.log_error=str(e)
            time.sleep(.5)
