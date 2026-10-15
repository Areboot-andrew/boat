import unittest,tempfile,os
from voyage import Voyage
class Tests(unittest.TestCase):
 def setUp(self):self.v=Voyage(':memory:','boot')
 def gps(self,x,speed=8):return dict(link_ok=True,position_valid=True,position_age_s=.1,latitude=50,longitude=30+x,speed_kmh=speed)
 def test_stationary_does_not_start(self):
  for n in range(20):self.v.update(self.gps(n*.000001,0),n)
  self.assertIsNone(self.v.data['started']);self.assertEqual(self.v.data['distance_m'],0)
 def test_motion_and_gap(self):
  for n in range(5):self.v.update(self.gps(n*.00004),n+100)
  self.assertIsNotNone(self.v.data['started']);d=self.v.data['distance_m'];self.assertGreater(d,0)
  self.v.update({},106)
  for n in range(5):self.v.update(self.gps(.001+n*.00004),n+107)
  self.assertTrue(any(p[3] for p in self.v.data['points']));self.assertLess(self.v.data['distance_m']-d,30)
 def test_same_boot_persists_new_boot_resets(self):
  with tempfile.TemporaryDirectory() as t:
   p=os.path.join(t,'v.db');v=Voyage(p,'a')
   for n in range(5):v.update(self.gps(n*.00004),n+100)
   v.save();w=Voyage(p,'a');self.assertEqual(v.data,w.data)
   z=Voyage(p,'b');self.assertEqual(z.data['points'],[])
   for x in (v,w,z):x.db.close()
 def test_bad_fix_and_jump_not_counted(self):
  for n in range(5):self.v.update(self.gps(n*.00004),n+100)
  d=self.v.data['distance_m'];self.v.update(self.gps(1),106)
  self.assertEqual(d,self.v.data['distance_m'])
  bad=self.gps(1);bad['latitude']=float('nan');self.v.update(bad,107)
  self.assertEqual(d,self.v.data['distance_m'])
if __name__=='__main__':unittest.main()
