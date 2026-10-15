"""Pi02 bench-only MAVLink control. No automatic arm, mode or actuator commands."""
import collections, fcntl, hmac, json, math, os, secrets, select, subprocess
import termios, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from pymavlink.dialects.v20 import ardupilotmega as mav

from fc_usb import resolve_port
PORT = 'auto:MatekH743:if00'
PARAMS = ['SERVO1_FUNCTION','SERVO3_FUNCTION','SERVO1_MIN','SERVO1_TRIM','SERVO3_TRIM',
          'RCMAP_ROLL','RCMAP_THROTTLE','RC_OVERRIDE_TIME','RC_OPTIONS','SYSID_MYGCS'] + [
          f'RC{ch}_{suffix}' for ch in (1,3) for suffix in ('MIN','TRIM','MAX','REVERSED')]

def close_serial(fd, old):
    # A removed USB device can raise termios.error (not OSError).
    if fd is None:return
    try:
        if old:termios.tcsetattr(fd,termios.TCSANOW,old)
    except (OSError,termios.error):pass
    try:fcntl.ioctl(fd,termios.TIOCNXCL)
    except OSError:pass
    try:os.close(fd)
    except OSError:pass

def supervise_worker(worker, control):
    while True:
        time.sleep(2)
        if not worker.is_alive() or time.monotonic()-control.loop_at>20:
            print('[WATCHDOG] USB worker dead/stalled; exit for systemd restart; no lease restored',flush=True)
            os._exit(1)

class Control:
    NETWORK_TIMEOUT = 3.0
    CHALLENGE_TTL = 3.0
    ALLOW_CRITICAL_MANUAL = False  # Board-specific explicit operator policy; not an FC parameter.
    def __init__(self):
        self.lock=threading.RLock();self.fd=None;self.parser=None;self.params={};self.hb={}
        self.hb_at=0;self.outputs={};self.output_at=0;self.rc={};self.events=collections.deque(maxlen=250)
        self.event_id=0;self.error='USB not connected';self.owner=None;self.deadline=0
        self.seq=-1;self.intent=(0,0);self.last_tx=0;self.pending={};self.challenge={}
        self.release_at=0;self.bench_recovery_until=0
        self.applied=(0,0);self.ramp_from=(0,0);self.ramp_at=0;self.throttle_cap=.25
        self.loop_at=time.monotonic()
        self.network_paused=False
    def pause_network(self,why):
        # Keep ownership and MANUAL; an expired command must not persist as thrust.
        if not self.network_paused:self.log('LINK_PAUSE',why+'; zero output, session retained; return controls to neutral')
        self.network_paused=True;self.challenge={};self.reset_ramp()
    def check_network_deadline(self,now):
        if self.owner and now>self.deadline:self.pause_network('No fresh command for %.1f s'%self.NETWORK_TIMEOUT)
    def control_step(self,now):
        """Optional onboard controller hook; called under the USB/output lock."""
        pass
    def ramp_value(self,now):
        fraction=max(0,min(1,(now-self.ramp_at)/.3))
        values=tuple(start+(end-start)*fraction for start,end in zip(self.ramp_from,self.intent))
        return (values[0],min(values[1],self.throttle_cap))
    def target(self,steer,throttle,cap,now):
        current=self.ramp_value(now)
        self.throttle_cap=cap
        current=(current[0],min(current[1],cap))
        desired=(steer,min(throttle,cap))
        if desired!=self.intent:
            self.ramp_from=current;self.ramp_at=now;self.intent=desired
        self.applied=current
    def reset_ramp(self):
        self.intent=self.applied=self.ramp_from=(0,0);self.ramp_at=time.monotonic();self.throttle_cap=.25
    def log(self,kind,text):
        self.event_id+=1;self.events.append(dict(id=self.event_id,time=time.time(),kind=kind,text=text))
    def write(self,b):
        n=os.write(self.fd,b)
        if n!=len(b):raise OSError('Partial MAVLink write')
        return n
    def reason(self,claim_recovery=False):
        if self.fd is None or time.monotonic()-self.hb_at>2.5:return 'Немає свіжого HEARTBEAT USB'
        if self.hb.get('autopilot')!=3 or self.hb.get('type')!=10:return 'Неочікуваний тип польотника'
        state=self.hb.get('system_status')
        recovery=(claim_recovery or time.monotonic()<self.bench_recovery_until) and not self.armed() and self.hb.get('custom_mode') in (0,4)
        manual_critical=self.ALLOW_CRITICAL_MANUAL and state==5 and self.hb.get('custom_mode') in (0,4)
        if state not in (3,4) and not (state==5 and recovery) and not manual_critical:return 'Польотник не готовий: MAV_STATE='+str(state)
        if any(k not in self.params for k in PARAMS):return 'Очікування параметрів RC / серво'
        p=self.params
        if any(p[k]!=v for k,v in {'SERVO1_FUNCTION':70,'SERVO3_FUNCTION':26,'RCMAP_ROLL':1,'RCMAP_THROTTLE':3,'SYSID_MYGCS':255,'SERVO1_TRIM':1100,'SERVO3_TRIM':1500}.items()):return 'Призначення виходів не відповідає стендовому профілю'
        if not .1<=p['RC_OVERRIDE_TIME']<=3:return 'Потрібен перевірений RC timeout 0.1–3 s'
        if int(p['RC_OPTIONS'])&2:return 'Польотник ігнорує RC override'
        for ch in (1,3):
            lo,mid,hi=[p[f'RC{ch}_{k}'] for k in ('MIN','TRIM','MAX')]
            valid=(900<=lo<mid<hi<=2100) if ch==1 else (900<=lo<=mid<hi<=2100)
            if not valid:return 'Неперевірена RC-калібровка'
            if p[f'RC{ch}_REVERSED'] not in (0,1):return 'Неперевірений напрям RC'
        return None
    def armed(self):return bool(self.hb.get('base_mode',0)&128)
    def command(self,cmd,*args):
        self.parser.command_long_send(1,1,cmd,0,*(list(args)+[0]*(7-len(args))))
        self.pending[cmd]=time.monotonic();self.log('TX',f'COMMAND_LONG {cmd}, args={args}; очікування ACK')
    def override(self,steer,throttle,release=False):
        p=self.params
        if release:values=[0,65535,0,65535,65535,65535,65535,65535]
        else:
            def pwm(ch,x):
                if p[f'RC{ch}_REVERSED']:x=-x
                mid=p[f'RC{ch}_TRIM'];edge=p[f'RC{ch}_MAX' if x>=0 else f'RC{ch}_MIN']
                return round(mid+abs(x)*(edge-mid))
            values=[pwm(1,steer),65535,pwm(3,throttle),65535,65535,65535,65535,65535]
        self.parser.rc_channels_override_send(1,1,*values)
    def stop(self,why):
        was_active=self.owner is not None
        self.owner=None;self.challenge={};self.intent=(0,0);self.deadline=0;self.bench_recovery_until=0
        self.reset_ramp()
        self.network_paused=False
        if was_active and self.fd is not None:
            try:
                self.override(0,0)
                self.command(mav.MAV_CMD_DO_SET_MODE,1,4) # HOLD, never ARM
                self.release_at=time.monotonic()+.5
            except OSError as e:self.log('ERROR',f'Stop send failed: {e}')
        if was_active:self.log('STOP',why+'; neutral + HOLD requested, not proof of physical stop')
    def snapshot(self):
        with self.lock:
            return dict(connected=self.fd is not None and time.monotonic()-self.hb_at<2.5,
                armed=self.armed(),mode=self.hb.get('custom_mode'),state=self.hb.get('system_status'),
                heartbeat_age_s=round(time.monotonic()-self.hb_at,2) if self.hb_at else None,
                blocked=self.reason(),claim_blocked=self.reason(claim_recovery=True),
                warning='CRITICAL: стендовий запуск DISARMED до 30 с; якщо стан не нормалізується — STOP' if self.hb.get('system_status')==5 else None,
                error=self.error,lease_active=self.owner is not None,
                network_paused=self.network_paused,network_timeout_s=self.NETWORK_TIMEOUT,
                intent=self.intent,outputs=self.outputs,output_age_s=round(time.monotonic()-self.output_at,2) if self.output_at else None,
                applied=self.applied,throttle_cap=self.throttle_cap,ramp_ms=300,
                rc=self.rc,parameters=self.params,events=list(self.events),pending=list(self.pending),
                profile='BENCH: steering ±60%, forward ≤50%, cap per operator, 300 ms ramp; cruise requires live browser; no reverse')
    def action(self,d):
        with self.lock:
            a=d.get('action');now=time.monotonic()
            if a=='claim':
                if d.get('bench') is not True:raise ValueError('Підтверди безпечні умови стенду і фізичне відключення живлення за потреби')
                recovery=d.get('critical_bench') is True
                if self.reason(claim_recovery=recovery):raise ValueError(self.reason(claim_recovery=recovery))
                if self.armed():raise ValueError('Захоплення тільки DISARMED')
                if self.owner or self.release_at:raise ValueError('Керування вже зайняте або зупиняється')
                self.owner=secrets.token_urlsafe(24);self.deadline=now+self.NETWORK_TIMEOUT;self.seq=-1;self.intent=(0,0);self.network_paused=False
                self.reset_ramp()
                if recovery and self.hb.get('system_status')==5:
                    self.bench_recovery_until=now+30
                    self.log('WARNING','Explicit DISARMED bench recovery, 30 s. Normal ARM checks unchanged; CRITICAL while armed stops control.')
                self.log('LEASE','Стендове керування отримане одним браузером')
                return {'lease':self.owner}
            if a in ('check','disarm'):
                if self.fd is None or now-self.hb_at>2.5:raise ValueError('USB offline')
                if a=='check':self.command(mav.MAV_CMD_RUN_PREARM_CHECKS)
                else:
                    self.stop('DISARM button');self.command(mav.MAV_CMD_COMPONENT_ARM_DISARM,0,0)
                return {'sent':True}
            if not self.owner or not hmac.compare_digest(str(d.get('lease','')),self.owner):raise ValueError('Немає чинної сесії керування')
            if a=='stop':self.stop('Browser STOP: '+str(d.get('reason','operator request'))[:180]);return {'stopped':True}
            self.check_network_deadline(now)
            if self.reason():self.stop(self.reason());raise ValueError('Керування заблоковано')
            if a=='tick':
                seq=d.get('seq');steer=d.get('steer');throttle=d.get('throttle')
                cap=d.get('throttle_cap',.25)
                if type(seq)!=int or seq<=self.seq:raise ValueError('Застарілий номер пакета')
                if any(type(x) not in (int,float) or not math.isfinite(x) for x in (steer,throttle)):raise ValueError('Некоректна команда')
                if type(cap) not in (int,float) or not math.isfinite(cap) or not 0<=cap<=getattr(self,'MAX_THROTTLE',.5):raise ValueError('Некоректний ліміт тяги')
                if abs(steer)>.6 or not 0<=throttle<=cap:raise ValueError('Перевищення стендової межі')
                # Short-lived server challenge prevents queued delayed motion requests reviving control.
                nonce=d.get('nonce')
                if steer or throttle:
                    stamp=self.challenge.pop(str(nonce),None)
                    if stamp is None or now-stamp>self.CHALLENGE_TTL:self.pause_network('Motion challenge expired; resynchronizing')
                    if self.hb.get('custom_mode')!=0:raise ValueError('Спочатку MANUAL, підтверджений HEARTBEAT')
                    if throttle and not self.armed():raise ValueError('Тяга тільки після ARM')
                self.seq=seq
                if self.network_paused and (steer or throttle):
                    return {'nonce':None,'intent':self.intent,'network_paused':True}
                if self.network_paused:
                    self.network_paused=False;self.log('LINK_RECOVER','Neutral command received; session ready')
                self.deadline=now+self.NETWORK_TIMEOUT;self.target(steer,throttle,cap,now)
                self.challenge={k:v for k,v in self.challenge.items() if now-v<self.CHALLENGE_TTL}
                nonce=secrets.token_urlsafe(12);self.challenge[nonce]=now
                return {'nonce':nonce,'intent':self.intent,'network_paused':False}
            if a in ('manual','arm'):
                if self.intent!=(0,0) or any(abs(v)>1e-6 for v in self.ramp_value(now)):raise ValueError('Відпусти клавіші та дочекайся нуля перед зміною стану')
                if a=='manual':
                    if self.armed():raise ValueError('Зміна режиму тільки DISARMED')
                    self.command(mav.MAV_CMD_DO_SET_MODE,1,0)
                else:
                    if d.get('confirm')!='ARM':raise ValueError('Потрібне явне підтвердження ARM')
                    if self.hb.get('custom_mode')!=0 or self.armed():raise ValueError('ARM тільки з DISARMED MANUAL')
                    self.command(mav.MAV_CMD_COMPONENT_ARM_DISARM,1,0) # normal checks, never force
                return {'sent':True}
            raise ValueError('Невідома дія')
    def ingest(self,m):
        if (m.get_srcSystem(),m.get_srcComponent())!=(1,1):return
        t=m.get_type();d=m.to_dict()
        if t=='HEARTBEAT':
            if any(self.hb.get(k)!=d.get(k) for k in ('base_mode','custom_mode','system_status')):
                self.log('STATE',f"mode={d['custom_mode']} state={d['system_status']} armed={bool(d['base_mode']&128)}")
            self.hb=d;self.hb_at=time.monotonic()
            if d.get('system_status') in (3,4):self.bench_recovery_until=0
        elif t=='PARAM_VALUE':self.params[str(m.param_id).rstrip('\x00')]=float(m.param_value)
        elif t=='STATUSTEXT':self.log('FC',f'{m.severity}: {m.text}')
        elif t=='COMMAND_ACK':
            if getattr(m,'target_system',0) not in (0,255) or getattr(m,'target_component',0) not in (0,190):return
            result=mav.enums['MAV_RESULT'].get(m.result);self.log('ACK',f'{m.command}: {result.name if result else m.result}')
            if m.result!=5:self.pending.pop(m.command,None)
        elif t=='SERVO_OUTPUT_RAW' and m.port==0:self.outputs={'steer_pwm':m.servo3_raw,'throttle_pwm':m.servo1_raw};self.output_at=time.monotonic()
        elif t=='RC_CHANNELS':self.rc={'count':m.chancount,'rc1':m.chan1_raw,'rc3':m.chan3_raw}
    def run(self):
        while True:
            self.loop_at=time.monotonic()
            fd=None;old=None
            try:
                # Do not compete with another serial owner or silently steal the port.
                port=resolve_port()
                if subprocess.run(['fuser',port],capture_output=True,timeout=2).returncode==0:raise OSError('USB already owned by another process')
                fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
                fcntl.ioctl(fd,termios.TIOCEXCL)
                old=termios.tcgetattr(fd);a=termios.tcgetattr(fd);a[0]=a[1]=a[3]=0
                a[2]=termios.CS8|termios.CREAD|termios.CLOCAL;a[4]=a[5]=termios.B115200;a[6][termios.VMIN]=0;a[6][termios.VTIME]=0
                termios.tcsetattr(fd,termios.TCSANOW,a)
                with self.lock:
                    self.fd=fd;self.params={};self.hb={};self.hb_at=0;self.error=None
                    self.parser=mav.MAVLink(self,srcSystem=255,srcComponent=190);self.parser.robust_parsing=True
                    self.log('USB','Auto-detected '+port+'; no control until operator claims')
                index=0;next_param=0;opened_at=time.monotonic()
                while True:
                    self.loop_at=time.monotonic()
                    ready=select.select([fd],[],[],.02)[0]
                    data=os.read(fd,8192) if ready else None
                    if data==b'':raise OSError('USB EOF')
                    with self.lock:
                        if data:
                            for m in self.parser.parse_buffer(data) or []:self.ingest(m)
                        now=time.monotonic()
                        if now-(self.hb_at or opened_at)>10:raise OSError('HEARTBEAT timeout >10 s; reconnect USB')
                        if self.hb_at and now>=next_param:
                            self.parser.param_request_read_send(1,1,PARAMS[index].encode(),-1)
                            index=(index+1)%len(PARAMS);next_param=now+(.2 if len(self.params)<len(PARAMS) else 1)
                        if self.owner and self.reason():self.stop(self.reason())
                        self.check_network_deadline(now)
                        self.control_step(now)
                        if self.owner and now-self.last_tx>=.02:
                            if self.hb.get('custom_mode') not in (0,4):self.stop('Неочікуваний режим')
                            else:
                                self.applied=self.ramp_value(now)
                                steer,thr=self.applied
                                if self.hb.get('custom_mode')!=0 or not self.armed():
                                    # A disarm/HOLD must never leave a latent throttle target.
                                    if thr or self.intent[1]:self.target(steer,0,self.throttle_cap,now);self.applied=(steer,0)
                                self.override(steer if self.hb.get('custom_mode')==0 else 0,thr if self.armed() and self.hb.get('custom_mode')==0 else 0)
                                self.last_tx=now
                        if self.release_at and now>=self.release_at:
                            self.override(0,0,release=True);self.release_at=0;self.log('RELEASE','RC1/RC3 override released')
                        for cmd,stamp in list(self.pending.items()):
                            if now-stamp>4:self.log('TIMEOUT',f'Немає ACK для {cmd}; перевір фактичний стан');self.pending.pop(cmd)
            except Exception as e:
                with self.lock:
                    try:self.stop('USB error')
                    finally:
                        self.owner=None;self.reset_ramp();self.fd=None;self.hb={};self.hb_at=0;self.params={};self.release_at=0
                        self.outputs={};self.output_at=0;self.rc={};self.pending={};self.error=str(e);self.log('ERROR',str(e))
            finally:
                close_serial(fd,old)
            time.sleep(3)

def main():
    control=Control();key=Path('/etc/harpoon/web-control.key').read_text().strip()
    class Handler(BaseHTTPRequestHandler):
        def answer(self,status,obj):
            data=json.dumps(obj,allow_nan=False).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass # Lost reply is handled by neutral resync, not an actuator command.
        def do_GET(self):
            if self.path!='/status':return self.answer(404,{'error':'Not found'})
            self.answer(200,control.snapshot())
        def do_POST(self):
            if self.path!='/action':return self.answer(404,{'error':'Not found'})
            if not hmac.compare_digest(self.headers.get('X-Control-Key',''),key):return self.answer(403,{'error':'Невірний ключ керування'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=16384:raise ValueError('Invalid body size')
                d=json.loads(self.rfile.read(n))
                if not isinstance(d,dict):raise ValueError('Expected object')
                self.answer(200,control.action(d))
            except (ValueError,TypeError) as e:self.answer(409,{'error':str(e)})
            except Exception as e:
                with control.lock:control.stop('API exception');control.log('ERROR',str(e))
                self.answer(503,{'error':'Control unavailable'})
        def log_message(self,*a):pass
    import signal
    def shutdown(*_):
        with control.lock:control.stop('Service stopping')
        time.sleep(.65)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    worker=threading.Thread(target=control.run,daemon=True);worker.start()
    threading.Thread(target=supervise_worker,args=(worker,control),daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',8091),Handler).serve_forever()

if __name__=='__main__':main()
