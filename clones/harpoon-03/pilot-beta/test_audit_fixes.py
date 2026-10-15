"""No hardware: onboard cadence, delayed start, source ages and network bounds."""
import time,unittest
from unittest.mock import Mock,patch
from test_manual_critical import Tests
from autonav import GPS,DEFAULTS

class AuditTests(Tests):
 def test_onboard_steps_without_browser_requests(self):
  c,l=self.start_critical_mission();start=time.monotonic()
  c.mission.step=Mock(return_value=(.1,.2));deadline=c.deadline
  for i in range(1,11):c.control_step(start+i*.101)
  self.assertEqual(c.mission.step.call_count,10);self.assertEqual(c.intent,(.1,.2))
  self.assertEqual(c.deadline,deadline,'onboard loop never renews browser deadline')
  c.check_network_deadline(deadline+.01);c.control_step(deadline+.02)
  self.assertIsNone(c.mission);self.assertEqual(c.intent,(0,0));self.assertEqual(c.owner,l)
  c.parser.command_long_send.assert_not_called()
 def test_auto_pulse_only_renews_liveness(self):
  c,l=self.start_critical_mission();c.mission.step=Mock(return_value=(.1,.2))
  c.action(dict(action='auto_tick',lease=l,seq=2,nonce=c.test_nonce))
  c.mission.step.assert_not_called()
 def test_lost_start_ack_resync_keeps_owner(self):
  c,l=self.start_critical_mission()
  c.action(dict(action='tick',lease=l,seq=2,steer=0,throttle=0,resync=True))
  self.assertIsNone(c.mission);self.assertEqual(c.owner,l)
  with self.assertRaises(ValueError):c.action(dict(action='auto_start',lease=l,seq=1,nonce=c.test_nonce,confirm='START'))
  self.assertIsNone(c.mission);c.parser.command_long_send.assert_not_called()
 def test_local_invalid_output_stops(self):
  c,l=self.start_critical_mission();c.mission.step=Mock(return_value=(float('nan'),.1))
  c.control_step(time.monotonic()+.2)
  self.assertIsNone(c.mission);self.assertEqual(c.intent,(0,0))

class Ages(unittest.TestCase):
 def test_combined_independent_ages(self):
  g=GPS();g.at=100;g.value=dict(link_ok=True,position_valid=True,heading_valid=True,latitude=50,longitude=30,heading_deg=90,speed_kmh=4,position_age_s=.2,heading_age_s=.2,speed_age_s=.2)
  with patch('autonav.time.monotonic',return_value=101):
   self.assertEqual(g.read(DEFAULTS)[1],90)
   for field in ('position_age_s','heading_age_s','speed_age_s'):
    g.value[field]=1.2
    with self.assertRaises(ValueError):g.read(DEFAULTS)
    g.value[field]=.2
   del g.value['heading_age_s']
   with self.assertRaises(ValueError):g.read(DEFAULTS)

if __name__=='__main__':unittest.main()
