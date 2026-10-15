"""Pi02 operator control: existing engine, no CRITICAL bench recovery."""
import control_service as engine
import math
import autonav

assert engine.PORT == 'auto:MatekH743:if00'

class BoardControl(engine.Control):
    MAX_THROTTLE = .7
    ALLOW_CRITICAL_AUTONAV = False  # Explicit board-specific owner policy.
    def __init__(self):
        super().__init__()
        self.nav_store=autonav.Store('/var/lib/harpoon-autonav/settings.json')
        self.nav_gps=autonav.GPS();self.mission=None;self.nav_message='Очікування запуску оператором'
        self.nav_step_at=0
    def nav_heartbeat(self,data,now):
        # Browser liveness/replay protection, independent of onboard steering cadence.
        seq=data.get('seq')
        if type(seq)!=int or seq<=self.seq:raise ValueError('Застарілий номер пакета')
        stamp=self.challenge.pop(str(data.get('nonce')),None)
        self.seq=seq
        if stamp is None or now-stamp>self.CHALLENGE_TTL:
            self.pause_network('Auto heartbeat challenge expired')
            return {'network_paused':True,'nonce':None}
        self.deadline=now+self.NETWORK_TIMEOUT
        nonce=engine.secrets.token_urlsafe(12)
        self.challenge={nonce:now}
        return {'network_paused':False,'nonce':nonce}
    def control_step(self,now):
        if not self.mission or not self.owner or self.network_paused:return
        if now-self.nav_step_at<.1:return
        self.nav_step_at=now
        try:
            if self.reason() or not self.armed() or self.hb.get('custom_mode')!=0:raise ValueError('Авто: втрачено ARMED/MANUAL або готовність')
            p,h,s=self.nav_gps.read(self.mission.c)
            values=self.mission.step(p,h,s,now)
            if values is None:
                self.stop('Маршрут завершено');self.command(engine.mav.MAV_CMD_COMPONENT_ARM_DISARM,0,0);return
            steer,throttle=values;cap=self.mission.c['max_throttle']/100
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (steer,throttle,cap)) or not 0<=cap<=.5 or abs(steer)>.6 or not 0<=throttle<=cap:raise ValueError('Авто: недійсна команда навігації')
            self.target(steer,throttle,cap,now)
        except Exception as e:
            self.log('AUTO_ERROR',str(e));self.stop('Авто: '+str(e))
    def stop(self,why):
        if getattr(self,'mission',None):self.nav_message=why
        self.mission=None
        return super().stop(why)
    def pause_network(self,why):
        if self.mission:self.nav_message='Зв’язок втрачено: маршрут призупинено; повторний запуск оператором'
        self.mission=None
        return super().pause_network(why)
    def nav_action(self,data):
        with self.lock:
            a=data.get('action');now=engine.time.monotonic()
            if a=='auto_preview':
                plan=autonav.plan_route(data.get('settings'),data.get('route'))
                return {k:plan[k] for k in ('points','length_m','turn_radius')}
            if a=='auto_save':
                if self.owner or self.armed():raise ValueError('Збереження налаштувань: DISARMED без активної сесії')
                self.nav_store.save(data.get('settings'),data.get('route'));return {'saved':True}
            if a=='emergency_stop':
                self.stop('STOP: автокерування скасовано')
                if self.fd is None or now-self.hb_at>2.5:raise ValueError('STOP: немає USB; фізично вимкни двигун')
                self.command(engine.mav.MAV_CMD_COMPONENT_ARM_DISARM,0,0)
                return {'sent':True,'message':'STOP + DISARM запитано, перевір HEARTBEAT та виходи'}
            if not self.owner or not engine.hmac.compare_digest(str(data.get('lease','')),self.owner):raise ValueError('Немає власної сесії')
            if self.hb.get('system_status') not in ((3,4,5) if self.ALLOW_CRITICAL_AUTONAV else (3,4)):
                if self.mission:self.stop('Авто: критичний стан польотника')
                raise ValueError('Авто: потрібен стан STANDBY/ACTIVE; CRITICAL дозволений лише для ручного керування')
            self.check_network_deadline(now)
            if self.network_paused:return {'network_paused':True,'nonce':None}
            if self.reason() or not self.armed() or self.hb.get('custom_mode')!=0:
                self.stop('Авто: втрачено готовність');raise ValueError('Авто потребує чинної сесії ARMED/MANUAL')
            if a=='auto_start':
                if self.mission:raise ValueError('Маршрут уже активний')
                if data.get('confirm')!='START' or self.nav_store.error:raise ValueError('Підтверди запуск; перевір збережені параметри')
                if any(abs(v)>.001 for v in self.applied) or any(abs(v)>.001 for v in self.intent):raise ValueError('Перед авто відпусти ручне керування до нуля')
                p,h,s=self.nav_gps.read(self.nav_store.config)
                route=self.nav_store.route
                if data.get('return_track'):
                    # Snapshot the recorded track locally; never trust browser gap removal.
                    import json
                    from urllib.request import urlopen
                    with urlopen('http://127.0.0.1:8090/voyage',timeout=.5) as r:v=json.load(r)
                    points=v.get('points',[])
                    if not v.get('fresh') or len(points)<2 or any(x[3] for x in points):raise ValueError('Трек відсутній або має розриви')
                    route=[x[:2] for x in reversed(points)]
                if not route or autonav.dist(p,route[0])>self.nav_store.config['corridor']:raise ValueError('Підійди до першої точки в межах допустимого відхилення')
                follower=autonav.Follower if data.get('return_track') else autonav.SmoothFollower
                prepared=follower(self.nav_store.config,route,p,now)
                result=self.nav_heartbeat(data,engine.time.monotonic())
                if result['network_paused']:return result
                self.mission=prepared;self.nav_step_at=now;self.nav_message='Маршрут запущено оператором; цикл Raspberry 10 Гц';self.log('AUTO',self.nav_message)
                return {**result,'started':True}
            if a=='auto_tick':
                if not self.mission:raise ValueError('Автомаршрут не активний')
                return self.nav_heartbeat(data,now)
    def reason(self, claim_recovery=False):
        if getattr(self,'mission',None):
            if self.hb.get('system_status') not in ((3,4,5) if self.ALLOW_CRITICAL_AUTONAV else (3,4)):return 'Авто: критичний стан польотника'
            try:self.nav_gps.read(self.mission.c)
            except ValueError as e:return str(e)
        return super().reason(claim_recovery=claim_recovery)
    def ingest(self, m):
        super().ingest(m)
        if (m.get_srcSystem(),m.get_srcComponent()) == (1,1) and m.get_type() == 'ATTITUDE':
            if all(math.isfinite(v) for v in (m.roll,m.pitch,m.yaw)):
                self.attitude=dict(roll_deg=math.degrees(m.roll),pitch_deg=math.degrees(m.pitch),yaw_deg=math.degrees(m.yaw)%360)
                self.attitude_at=engine.time.monotonic()
    def log(self, kind, text):
        if kind == 'LEASE':
            text = 'Керування отримане одним браузером'
        super().log(kind, text)
        print(f'[{kind}] {text}', flush=True)

    def action(self, data):
        if data.get('action') == 'arm_request':
            with self.lock:
                now=engine.time.monotonic()
                if data.get('confirm')!='REQUEST_NORMAL_ARM':raise ValueError('Підтверди звичайний запит ARM')
                if self.fd is None or not self.hb or now-self.hb_at>2.5:raise ValueError('Немає свіжого HEARTBEAT')
                if self.hb.get('autopilot')!=3 or self.hb.get('type')!=10:raise ValueError('Неочікуваний польотник')
                if self.armed() or self.owner or self.mission or self.release_at or any(abs(v)>.001 for v in (*self.intent,*self.applied)):
                    raise ValueError('Запит ARM без сесії: потрібен DISARMED без активного керування')
                if now<getattr(self,'arm_request_until',0):raise ValueError('Запит уже надіслано; дочекайся відповіді')
                self.arm_request_until=now+5
                self.log('ARM_REQUEST','Оператор запросив звичайний ARM; рішення польотника, без force і без надання сесії руху')
                self.command(engine.mav.MAV_CMD_COMPONENT_ARM_DISARM,1,0)
                return {'sent':True,'message':'Звичайний ARM запитано. Перевір ACK і HEARTBEAT; доступ до руху цим запитом не надається.'}
        if data.get('action') == 'reboot_fc':
            with self.lock:
                now=engine.time.monotonic()
                if data.get('confirm')!='REBOOT_FC':raise ValueError('Підтверди перезавантаження польотника')
                if self.fd is None or not self.hb or now-self.hb_at>2.5:raise ValueError('Немає свіжого зв’язку: програмне перезавантаження недоступне; потрібне фізичне керування живленням')
                if self.armed() or self.owner or self.mission or any(abs(v)>.001 for v in (*self.intent,*self.applied)):
                    raise ValueError('Спочатку DISARM і завершення керування')
                if self.hb.get('autopilot')!=3 or self.hb.get('type')!=10:raise ValueError('Неочікуваний польотник')
                if now<getattr(self,'reboot_until',0):raise ValueError('Перезавантаження вже запитано; зачекай 30 с')
                self.reboot_until=now+30
                self.log('REBOOT','Оператор підтвердив перезавантаження лише польотника; без зміни параметрів')
                self.command(engine.mav.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,1,0,0,0,0,0,0)
                return {'sent':True,'message':'Запит надіслано. ACK не доводить перезапуск; перевір відновлення HEARTBEAT у логах.'}
        if data.get('action') in ('auto_preview','auto_save','auto_start','auto_tick','emergency_stop'):return self.nav_action(data)
        if data.get('action')=='tick' and data.get('resync') is True:
            with self.lock:
                if not self.owner or not engine.hmac.compare_digest(str(data.get('lease','')),self.owner):raise ValueError('Немає власної сесії')
                self.pause_network('Browser resynchronizing at neutral')
        if self.mission and data.get('action')=='tick':
            with self.lock:self.stop('Ручне перехоплення');raise ValueError('Авто припинено; увімкни ручне керування знову')
        if data.get('action') == 'tick':
            cap = data.get('throttle_cap', .25)
            if data.get('input_source') == 'gamepad' or (type(cap) in (int,float) and cap > .5):
                gate = data.get('pad_gate')
                mode = data.get('pad_mode')
                valid_number = lambda n: type(n) in (int,float) and math.isfinite(n)
                ok = data.get('input_source') == 'gamepad' and isinstance(gate,list) and len(gate)==2 and all(valid_number(n) and .95<=n<=1 for n in gate)
                if not ok or not valid_number(mode) or min(abs(mode-n) for n in (-1,0,1))>.1:
                    with self.lock:
                        if self.owner and data.get('lease') == self.owner:self.stop('TX12 switch permission lost')
                    raise ValueError('Invalid TX12 switch permission')
                maximum = .5 if mode < -.5 else .7 if mode > .5 else .6
                if not valid_number(cap) or not 0<=cap<=maximum:raise ValueError('TX12 mode throttle limit exceeded')
        if data.get('action') == 'read_output_parameters':
            with self.lock:
                if self.fd is None or self.armed() or self.owner:
                    raise ValueError('Parameter inspection requires DISARMED and idle USB')
                names = ['MOT_THR_MIN','MOT_PWM_MIN','MOT_PWM_MAX','MOT_PWM_TYPE',
                         'SERVO1_MIN','SERVO1_TRIM','SERVO1_MAX','SERVO1_REVERSED','ARMING_CHECK']
                for name in names:
                    self.parser.param_request_read_send(1,1,name.encode(),-1)
                self.log('PARAM_READ','Requested motor/output parameters (read only)')
                return {'requested': names}
        if data.get('action') == 'claim':
            if data.get('operator_confirmed') is not True and data.get('bench') is not True:
                raise ValueError('Підтверди ввімкнення керування')
            data = {**data, 'bench': True, 'critical_bench': self.hb.get('system_status') == 5 and not self.ALLOW_CRITICAL_MANUAL}
        return super().action(data)

    def snapshot(self):
        with self.lock:
            result = super().snapshot()
            result['autonav']=dict(active=self.mission is not None,settings=self.nav_store.config,route=self.nav_store.route,error=self.nav_store.error,message=self.nav_message,progress=self.mission.status if self.mission else None)
            age=engine.time.monotonic()-getattr(self,'attitude_at',0)
            result['attitude']=getattr(self,'attitude',None) if result['connected'] and age<2 else None
            result['attitude_age_s']=age if getattr(self,'attitude_at',0) else None
            result['claim_blocked'] = self.reason(claim_recovery=True)
            result['warning'] = 'CRITICAL: попередній DISARMED режим підготовки до 30 с; звичайний ARM без force' if result['state'] == 5 else None
            result['profile'] = 'PILOT: steering +/-60%; keyboard <=50%; TX12 50/60/70%; 300 ms ramp; no reverse'
            result['critical_recovery_enabled'] = True
            result['manual_critical_allowed'] = self.ALLOW_CRITICAL_MANUAL
            result['autonav_critical_allowed'] = self.ALLOW_CRITICAL_AUTONAV
            if self.ALLOW_CRITICAL_MANUAL:
                result['critical_recovery_enabled'] = False
                result['warning'] = 'CRITICAL / EKF: ручне MANUAL дозволено власником; автомісія недоступна' if result['state']==5 else None
                if self.ALLOW_CRITICAL_AUTONAV and result['state']==5:
                    result['warning'] = 'CRITICAL / EKF: ручне та автокерування дозволені власником; помилку EKF не усунуто'
            result['connection_phase'] = 'waiting_usb' if self.fd is None else 'waiting_heartbeat' if not result['connected'] else 'waiting_parameters' if any(k not in self.params for k in engine.PARAMS) else 'blocked' if result['blocked'] else 'ready'
            return result

engine.Control = BoardControl
if __name__ == '__main__':
    original_init=BoardControl.__init__
    def with_gps(self):
        original_init(self)
        engine.threading.Thread(target=self.nav_gps.run,daemon=True).start()
    BoardControl.__init__=with_gps
    engine.main()
