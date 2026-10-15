import unittest, math
from autonav import DEFAULTS, plan_route, SmoothFollower, xy
def geo(x,y):return [50+y/111195,30+x/(111195*math.cos(math.radians(50)))]
class SmoothTests(unittest.TestCase):
 def test_long_and_short_straight_segments(self):
  for length in (1,3000):
   p=plan_route(DEFAULTS,[geo(0,0),geo(length,0)])
   self.assertAlmostEqual(p['length_m'],length,1)
 def test_duplicate_points(self):
  with self.assertRaisesRegex(ValueError,'збігаються'):plan_route(DEFAULTS,[geo(0,0),geo(0,0)])
 def setUp(self):self.c=dict(DEFAULTS);self.r=[geo(0,0),geo(40,0),geo(40,40)]
 def test_tangent_arc(self):
  p=plan_route(self.c,self.r);self.assertEqual(p['points'][0],self.r[0]);self.assertAlmostEqual(p['length_m'],80-16+4*math.pi,1)
  for point,curve in zip(p['xy'],p['curved']):
   if curve:self.assertAlmostEqual(math.dist(point,(32,8)),8,places=5)
  vec=[(b[0]-a[0],b[1]-a[1]) for a,b in zip(p['xy'],p['xy'][1:])]
  for a,b in zip(vec,vec[1:]):
   angle=math.acos(max(-1,min(1,(a[0]*b[0]+a[1]*b[1])/(math.hypot(*a)*math.hypot(*b)))))
   self.assertLess(angle,math.radians(5.1))
 def test_too_tight_rejected(self):
  for r in ([geo(0,0),geo(4,0),geo(4,4)], [geo(0,0),geo(40,0),geo(0,1)]):
   with self.assertRaises(ValueError):plan_route(self.c,r)
 def test_tolerance_rejected(self):
  with self.assertRaises(ValueError):plan_route({**self.c,'radius':1},self.r)
 def test_same_preview_path(self):
  f=SmoothFollower(self.c,self.r,self.r[0],0);self.assertEqual(f.plan,plan_route(self.c,self.r))
 def test_follow_sampled_path_no_actuators(self):
  f=SmoothFollower({**self.c,'cruise':40},self.r,self.r[0],0);p=f.plan['points'];slow=False
  for i,point in enumerate(p[:-1]):
   x,y=xy(p[i+1],point);result=f.step(point,math.degrees(math.atan2(x,y)),2,i*.5+.1)
   if result is None:break
   self.assertLessEqual(abs(result[0]),.6);self.assertLessEqual(result[1],.5)
   if f.status['turn_slowdown']:slow=True;self.assertLessEqual(result[1],.25)
  self.assertTrue(slow);self.assertIsNone(f.step(p[-1],0,0,len(p)*.5))
 def test_start_near_first(self):
  with self.assertRaises(ValueError):SmoothFollower(self.c,self.r,geo(20,0),0)
 def test_stale_jump_corridor(self):
  f=SmoothFollower(self.c,self.r,self.r[0],0)
  with self.assertRaises(ValueError):f.step(geo(100,100),0,1,.1)
 def test_collinear(self):self.assertAlmostEqual(plan_route(self.c,[geo(0,0),geo(30,0),geo(60,0)])['length_m'],60,1)
 def test_left_turn(self):
  p=plan_route(self.c,[geo(0,0),geo(0,40),geo(-40,40)])
  self.assertAlmostEqual(p['length_m'],80-16+4*math.pi,1)
if __name__=='__main__':unittest.main()
