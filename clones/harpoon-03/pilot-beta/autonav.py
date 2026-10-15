"""Pi03 route follower and persisted settings. No serial access in this module."""
import json,math,os,threading,time
from pathlib import Path
from urllib.request import urlopen

DEFAULTS=dict(cruise=20,max_throttle=50,turn_throttle=25,max_steer=60,radius=4,corridor=15,lookahead=6,turn_distance=15,turn_angle=35,kp=.8,ki=.025,trim_limit=12,steer_rate=30,throttle_rate=5,gps_age=2,heading_offset=0,steer_sign=1)
BOUNDS=dict(cruise=(0,50),max_throttle=(1,50),turn_throttle=(0,25),max_steer=(1,60),radius=(1,10),corridor=(3,40),lookahead=(2,20),turn_distance=(5,50),turn_angle=(15,90),kp=(.1,3),ki=(0,.2),trim_limit=(0,20),steer_rate=(5,90),throttle_rate=(1,20),gps_age=(.5,2.5),heading_offset=(-180,180),steer_sign=(-1,1))
DEFAULTS['turn_radius']=8
BOUNDS['turn_radius']=(2,100)
def clamp(x,a,b):return max(a,min(b,x))
def wrap(x):return (x+180)%360-180
def settings(d):
 if not isinstance(d,dict) or set(d)!=set(DEFAULTS):raise ValueError('Некоректний набір налаштувань')
 for k,(lo,hi) in BOUNDS.items():
  if type(d[k]) not in (int,float) or not math.isfinite(d[k]) or not lo<=d[k]<=hi:raise ValueError('Некоректне поле: '+k)
 if d['steer_sign'] not in (-1,1) or d['cruise']>d['max_throttle'] or d['trim_limit']>d['max_steer'] or d['radius']>=d['corridor']:raise ValueError('Несумісні межі налаштувань')
 return dict(d)
def xy(p,o):return ((p[1]-o[1])*111195*math.cos(math.radians(o[0])),(p[0]-o[0])*111195)
def dist(a,b):return math.hypot(*xy(a,b))
def bearing(a,b):x,y=xy(b,a);return math.degrees(math.atan2(x,y))%360
def valid_route(points,max_points=100):
 if not isinstance(points,list) or not 1<=len(points)<=max_points:raise ValueError('Перевищено кількість точок маршруту')
 for p in points:
  if not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) or abs(p[0])>85 or abs(p[1])>180:raise ValueError('Невірні координати')
 for i,(a,b) in enumerate(zip(points,points[1:])):
  if dist(a,b)<.1:raise ValueError(f'Точки {i+1} і {i+2} збігаються; пересунь або прибери одну')
 return [p[:] for p in points]

def plan_route(c,route):
 """Tangent circular fillets. Radius is never silently reduced to fit a corner.
 Preview and follower consume exactly these samples in the same metric plane.
 Waypoint radius bounds corner cutting, not obstacle clearance.
 """
 c=settings(c);route=valid_route(route)
 if len(route)<2:raise ValueError('Постав щонайменше дві точки')
 o=route[0];pts=[xy(p,o) for p in route];corners={};R=c['turn_radius']
 for i in range(1,len(pts)-1):
  a,b,d=pts[i-1:i+2];l1=math.dist(a,b);l2=math.dist(b,d)
  u=((b[0]-a[0])/l1,(b[1]-a[1])/l1);v=((d[0]-b[0])/l2,(d[1]-b[1])/l2)
  angle=math.acos(clamp(u[0]*v[0]+u[1]*v[1],-1,1))
  if angle<1e-6:continue
  if angle>math.radians(170):raise ValueError(f'Точка {i+1}: розворот надто різкий; додай широку дугу точками')
  cut=R*math.tan(angle/2);miss=R*(1/math.cos(angle/2)-1)
  if miss>c['radius']:raise ValueError(f'Точка {i+1}: дуга не входить у радіус точки ({miss:.1f} м); розсунь точки або збільш допуск')
  sign=1 if u[0]*v[1]-u[1]*v[0]>0 else -1
  entry=(b[0]-u[0]*cut,b[1]-u[1]*cut);end=(b[0]+v[0]*cut,b[1]+v[1]*cut)
  center=(entry[0]-sign*u[1]*R,entry[1]+sign*u[0]*R)
  corners[i]=(cut,entry,end,center,angle,sign)
 for i in range(len(pts)-1):
  used=(corners[i][0] if i in corners else 0)+(corners[i+1][0] if i+1 in corners else 0)
  if used>math.dist(pts[i],pts[i+1])-.1:raise ValueError(f'Між точками {i+1}–{i+2} замало місця для радіуса {R:g} м')
 out=[pts[0]];curved=[False]
 def add_line(end):
  start=out[-1];n=max(1,math.ceil(math.dist(start,end)))
  if len(out)+n>25000:raise ValueError('Маршрут надто довгий: максимум 25 000 відліків траєкторії')
  for j in range(1,n+1):
   p=(start[0]+(end[0]-start[0])*j/n,start[1]+(end[1]-start[1])*j/n)
   if math.dist(out[-1],p)>1e-6:out.append(p);curved.append(False)
 for i in range(1,len(pts)):
  if i not in corners:add_line(pts[i]);continue
  cut,entry,end,center,angle,sign=corners[i];add_line(entry)
  start=math.atan2(entry[1]-center[1],entry[0]-center[0]);n=max(2,math.ceil(R*angle),math.ceil(angle/math.radians(5)))
  if len(out)+n>25000:raise ValueError('Маршрут надто довгий')
  for j in range(1,n+1):
   t=start+sign*angle*j/n;out.append((center[0]+R*math.cos(t),center[1]+R*math.sin(t)));curved.append(True)
 distances=[0.]
 for a,b in zip(out,out[1:]):distances.append(distances[-1]+math.dist(a,b))
 geo=[[o[0]+y/111195,o[1]+x/(111195*math.cos(math.radians(o[0])))] for x,y in out]
 return dict(points=geo,xy=out,curved=curved,distances=distances,length_m=round(distances[-1],1),turn_radius=R)

class SmoothFollower:
 """Progress-local pure pursuit on the same sampled curve shown by the map.
 No jumping to remote crossing segments. Existing controller output path remains.
 """
 def __init__(self,c,route,pos,now):
  self.c=dict(c);self.plan=plan_route(c,route);self.origin=route[0];self.previous=pos[:];self.previous_at=now
  if dist(pos,route[0])>c['radius']:raise ValueError('Для плавного маршруту підійди до першої точки в її радіус')
  self.progress=0.;self.trim=0.;self.steer=0.;self.throttle=0.;self.status={};self.at=now
 def step(self,pos,heading,speed,now):
  import bisect
  c=self.c;elapsed=now-self.previous_at;dt=clamp(now-self.at,.01,.3);self.at=now
  if dist(pos,self.previous)>max(10,elapsed*28):raise ValueError('Стрибок координат: маршрут припинено')
  self.previous=pos[:];self.previous_at=now
  p=xy(pos,self.origin);pts=self.plan['xy'];ss=self.plan['distances'];curves=self.plan['curved']
  lo=max(0,bisect.bisect_right(ss,max(0,self.progress-2))-1)
  hi=min(len(pts)-1,bisect.bisect_right(ss,self.progress+max(5,speed*max(elapsed,.1)*3+2)))
  best=None
  for i in range(lo,hi):
   a,b=pts[i:i+2];dx,dy=b[0]-a[0],b[1]-a[1];t=clamp(((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy),0,1)
   cross=math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);s=ss[i]+t*(ss[i+1]-ss[i])
   if best is None or cross<best[0]:best=(cross,s,i)
  if best is None:raise ValueError('Не визначено положення на маршруті')
  cross,s,index=best
  if cross>c['corridor']:raise ValueError('Перевищено допустиме відхилення від маршруту')
  self.progress=max(self.progress,s);remaining=ss[-1]-self.progress
  if remaining<=c['radius'] and dist(pos,self.plan['points'][-1])<=c['radius']:return None
  ahead=min(ss[-1],self.progress+c['turn_distance']+speed*2)
  approaching=any(curves[index+1:bisect.bisect_right(ss,ahead)+1])
  look=max(c['lookahead'],speed*2)
  if approaching:look=min(look,max(1,c['turn_radius']*.35))
  target=min(ss[-1],self.progress+look);j=min(len(pts)-2,max(0,bisect.bisect_right(ss,target)-1));f=(target-ss[j])/(ss[j+1]-ss[j])
  aim=(pts[j][0]+(pts[j+1][0]-pts[j][0])*f,pts[j][1]+(pts[j+1][1]-pts[j][1])*f)
  err=wrap(math.degrees(math.atan2(aim[0]-p[0],aim[1]-p[1]))-heading)
  slow=approaching or abs(err)>c['turn_angle'] or cross>c['corridor']*.5 or remaining<c['turn_distance']
  wanted=min(c['cruise'],c['max_throttle'],c['turn_throttle'] if slow else c['max_throttle'])
  if abs(err)>70:wanted=min(wanted,10)
  if speed>.5 and abs(err)<25 and abs(c['kp']*err+self.trim)<c['max_steer']:
   self.trim=clamp(self.trim+c['ki']*err*dt,-c['trim_limit'],c['trim_limit'])
  steer=clamp(c['steer_sign']*(c['kp']*err+self.trim),-c['max_steer'],c['max_steer'])
  self.steer+=clamp(steer-self.steer,-c['steer_rate']*dt,c['steer_rate']*dt);self.throttle=min(wanted,self.throttle+c['throttle_rate']*dt)
  self.status=dict(point=index+1,total=len(pts),distance_m=round(remaining,1),cross_track_m=round(cross,1),azimuth_error_deg=round(err,1),trim_pct=round(self.trim,2),turn_slowdown=slow,smooth=True)
  return self.steer/100,self.throttle/100

class Store:
 def __init__(self,path):
  self.path=Path(path);self.config=dict(DEFAULTS);self.route=[];self.error=None
  try:
   if self.path.exists():
    d=json.loads(self.path.read_text());self.config=settings({'turn_radius':8,**d['settings']});self.route=valid_route(d['route']) if d['route'] else []
  except Exception as e:self.error='Налаштування не прочитані: '+str(e)
 def save(self,c,r):
  c=settings(c);r=valid_route(r) if r else []
  if r:plan_route(c,r)
  temp=self.path.with_suffix('.tmp')
  with temp.open('w') as f:json.dump(dict(settings=c,route=r),f);f.flush();os.fsync(f.fileno())
  os.replace(temp,self.path);self.config=c;self.route=r;self.error=None

class GPS:
 def __init__(self):self.value={};self.at=0;self.lock=threading.Lock()
 def run(self):
  while True:
   try:
    requested=time.monotonic()
    with urlopen('http://127.0.0.1:8080/telemetry',timeout=1) as r:g=json.load(r)['gps']
    with self.lock:self.value=g;self.at=requested
   except Exception:
    with self.lock:self.value={};self.at=0
   time.sleep(.25)
 def read(self,c):
  with self.lock:g=self.value;age=time.monotonic()-self.at
  if age>c['gps_age'] or not g.get('link_ok') or not g.get('position_valid') or not g.get('heading_valid'):raise ValueError('Авто: немає свіжого GPS / курсу носа')
  vals=[g.get(k) for k in ('latitude','longitude','heading_deg','position_age_s','speed_kmh')]
  if any(type(v) not in (int,float) or not math.isfinite(v) for v in vals) or not 0<=vals[3]<=c['gps_age'] or not -85<=vals[0]<=85 or not -180<=vals[1]<=180 or not 0<=vals[4]<=100:raise ValueError('Авто: недостовірні дані GPS')
  for key in ('position_age_s','heading_age_s','speed_age_s'):
   source_age=g.get(key)
   if type(source_age) not in (int,float) or not math.isfinite(source_age) or source_age<0 or source_age+age>c['gps_age']:raise ValueError('Авто: застарілі дані '+key)
  return [vals[0],vals[1]],(vals[2]+c['heading_offset'])%360,vals[4]/3.6

class Follower:
 def __init__(self,c,route,pos,now):
  self.c=dict(c);self.route=valid_route(route,50000);self.origin=pos[:];self.i=0;self.trim=0;self.steer=0;self.throttle=0;self.at=now;self.previous=pos[:];self.previous_at=now;self.status={}
 def step(self,pos,heading,speed,now):
  c=self.c;dt=clamp(now-self.at,.01,.3);self.at=now
  if dist(pos,self.previous)>max(10,(now-self.previous_at)*28):raise ValueError('Стрибок координат: маршрут припинено')
  self.previous=pos[:];self.previous_at=now
  if self.i>=len(self.route):return None
  target=self.route[self.i];d=dist(pos,target)
  if d<=c['radius']:
   self.origin=target;self.i+=1
   if self.i==len(self.route):return None
   target=self.route[self.i];d=dist(pos,target);self.trim=0
  bx,by=xy(target,self.origin);px,py=xy(pos,self.origin);length=math.hypot(bx,by)
  t=clamp((px*bx+py*by)/(length*length or 1),0,1);cross=math.hypot(px-t*bx,py-t*by)
  if cross>c['corridor']:raise ValueError('Перевищено допустиме відхилення від маршруту')
  # Look ahead on the current segment only: never cut across the next corner.
  aim_t=clamp(t+max(c['lookahead'],speed*2)/(length or 1),0,1)
  aim=[self.origin[0]+(target[0]-self.origin[0])*aim_t,self.origin[1]+(target[1]-self.origin[1])*aim_t]
  err=wrap(bearing(pos,aim)-heading)
  turn=abs(wrap(bearing(target,self.route[self.i+1])-bearing(self.origin,target))) if self.i+1<len(self.route) else 0
  slow=abs(err)>c['turn_angle'] or cross>c['corridor']*.5 or (d<c['turn_distance']+speed*2 and turn>c['turn_angle']) or (self.i==len(self.route)-1 and d<c['turn_distance'])
  wanted=min(c['cruise'],c['max_throttle'],c['turn_throttle'] if slow else c['max_throttle'])
  if abs(err)>70:wanted=min(wanted,10)
  # Bounded integral trim only while moving and approximately aligned; no windup at saturation.
  if speed>.5 and abs(err)<25 and abs(c['kp']*err+self.trim)<c['max_steer']:
   self.trim=clamp(self.trim+c['ki']*err*dt,-c['trim_limit'],c['trim_limit'])
  steer=clamp(c['steer_sign']*(c['kp']*err+self.trim),-c['max_steer'],c['max_steer'])
  self.steer+=clamp(steer-self.steer,-c['steer_rate']*dt,c['steer_rate']*dt)
  self.throttle=min(wanted,self.throttle+c['throttle_rate']*dt)
  self.status=dict(point=self.i+1,total=len(self.route),distance_m=round(d,1),cross_track_m=round(cross,1),azimuth_error_deg=round(err,1),trim_pct=round(self.trim,2),turn_slowdown=slow)
  return self.steer/100,self.throttle/100
