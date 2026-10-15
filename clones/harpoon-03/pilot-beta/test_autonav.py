import unittest
from autonav import *
class Tests(unittest.TestCase):
 def test_limits(self):
  for k,v in [('max_throttle',99),('max_steer',100),('turn_throttle',26),('ki',float('nan'))]:
   with self.assertRaises(ValueError):settings({**DEFAULTS,k:v})
 def test_heading_wrap(self):self.assertEqual(wrap(359-1),-2)
 def test_slow_turn_no_acceleration(self):
  c={**DEFAULTS,'cruise':10};f=Follower(c,[[50.0001,30],[50.0001,30.0002]],[50,30],0)
  for n in range(1,20):s,t=f.step([50,30],0,1,n*.15);self.assertLessEqual(t,.1);self.assertLessEqual(abs(s),.6)
  self.assertTrue(f.status['turn_slowdown'])
 def test_no_shortcut_and_end(self):
  f=Follower(DEFAULTS,[[50.0001,30],[50.0001,30.0002]],[50,30],0)
  f.step([50,30],0,1,.1);self.assertEqual(f.i,0)
  f.step([50.00009,30],0,1,1);self.assertEqual(f.i,1)
 def test_gap_and_corridor_stop(self):
  f=Follower(DEFAULTS,[[50.001,30]],[50,30],0)
  with self.assertRaises(ValueError):f.step([51,30],0,1,.1)
 def test_trim_bounded_and_stopped_not_integrating(self):
  f=Follower(DEFAULTS,[[50.001,30]],[50,30],0)
  for n in range(1,100):f.step([50,30],350,0,n*.15)
  self.assertEqual(f.trim,0)
  for n in range(100,200):f.step([50,30],350,1,n*.15)
  self.assertGreater(f.trim,0);self.assertLessEqual(f.trim,DEFAULTS['trim_limit'])
if __name__=='__main__':unittest.main()
