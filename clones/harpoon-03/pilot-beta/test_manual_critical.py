"""Isolated fake MAVLink only: no serial open, threads or live API."""
import time,unittest
from unittest.mock import Mock,patch
from types import SimpleNamespace
from control_runner import BoardControl,engine
class Tests(unittest.TestCase):
 def setUp(self):
  with patch('control_runner.autonav.Store',return_value=SimpleNamespace(config={},route=[],error=None)):
   self.c=c=BoardControl()
  c.ALLOW_CRITICAL_MANUAL=True;c.ALLOW_CRITICAL_AUTONAV=False;c.fd=1;c.parser=Mock();c.hb_at=time.monotonic()
  c.hb=dict(type=10,autopilot=3,base_mode=1,custom_mode=0,system_status=5)
  c.params={k:0 for k in engine.PARAMS}
  c.params.update(SERVO1_FUNCTION=70,SERVO3_FUNCTION=26,SERVO1_TRIM=1100,SERVO3_TRIM=1500,RCMAP_ROLL=1,RCMAP_THROTTLE=3,RC_OVERRIDE_TIME=3,SYSID_MYGCS=255)
  for ch in (1,3):
   c.params.update({f'RC{ch}_MIN':1100,f'RC{ch}_TRIM':1500 if ch==1 else 1100,f'RC{ch}_MAX':1900,f'RC{ch}_REVERSED':0})
 def test_manual_armed_tick_not_stopped(self):
  c=self.c;lease=c.action(dict(action='claim',operator_confirmed=True))['lease'];c.hb['base_mode']=129
  self.assertIsNone(c.reason());r=c.action(dict(action='tick',lease=lease,seq=0,steer=0,throttle=0))
  c.action(dict(action='tick',lease=lease,seq=1,nonce=r['nonce'],steer=.1,throttle=.1))
  self.assertEqual(c.intent,(.1,.1));self.assertEqual(c.owner,lease);c.parser.command_long_send.assert_not_called()
 def test_claim_still_disarmed(self):
  self.c.hb['base_mode']=129
  with self.assertRaisesRegex(ValueError,'DISARMED'):self.c.action(dict(action='claim',operator_confirmed=True))
 def test_stale_and_bad_states_block(self):
  c=self.c
  for state in (0,1,2,6,7,8):
   c.hb['system_status']=state;self.assertIsNotNone(c.reason())
  c.hb['system_status']=5;c.hb_at=time.monotonic()-3;self.assertIn('HEARTBEAT',c.reason())
 def test_other_modes_block(self):
  self.c.hb['custom_mode']=16;self.assertIsNotNone(self.c.reason())
 def test_autonomy_not_allowed(self):
  c=self.c;lease=c.action(dict(action='claim',operator_confirmed=True))['lease'];c.hb['base_mode']=129
  with self.assertRaisesRegex(ValueError,'лише для ручного'):c.action(dict(action='auto_start',lease=lease,confirm='START'))
  c.parser.command_long_send.assert_not_called()
 def test_default_other_boards_unchanged(self):
  c=self.c;c.ALLOW_CRITICAL_MANUAL=False;c.hb['base_mode']=129;self.assertIsNotNone(c.reason())
 def test_status_warning_not_block(self):
  s=self.c.snapshot();self.assertIsNone(s['blocked']);self.assertTrue(s['manual_critical_allowed']);self.assertIn('CRITICAL',s['warning'])
 def start_critical_mission(self):
  from autonav import DEFAULTS
  c=self.c;c.ALLOW_CRITICAL_AUTONAV=True
  c.nav_store.config=dict(DEFAULTS);c.nav_store.route=[[50,30],[50.0001,30]]
  c.nav_gps.read=Mock(return_value=([50,30],0,0))
  lease=c.action(dict(action='claim',operator_confirmed=True))['lease'];c.hb['base_mode']=129
  c.test_nonce=c.action(dict(action='tick',lease=lease,seq=0,steer=0,throttle=0))['nonce']
  r=c.action(dict(action='auto_start',lease=lease,confirm='START',seq=1,nonce=c.test_nonce))
  self.assertTrue(r['started']);c.test_nonce=r['nonce']
  c.parser.command_long_send.assert_not_called()
  return c,lease
 def test_explicit_critical_autonav_start_and_tick(self):
  c,lease=self.start_critical_mission();self.assertIsNone(c.reason())
  c.action(dict(action='auto_tick',lease=lease,seq=2,nonce=c.test_nonce))
  self.assertIsNotNone(c.mission);self.assertTrue(c.snapshot()['autonav_critical_allowed'])
 def test_critical_autonav_still_needs_gps(self):
  c,lease=self.start_critical_mission();c.nav_gps.read.side_effect=ValueError('GPS stale')
  self.assertIn('GPS',c.reason())
  with self.assertRaises(ValueError):c.action(dict(action='auto_tick',lease=lease,seq=0))
  self.assertIsNone(c.mission)
 def test_critical_autonav_still_blocks_emergency(self):
  c,lease=self.start_critical_mission();c.hb['system_status']=6
  self.assertIsNotNone(c.reason())
  with self.assertRaises(ValueError):c.action(dict(action='auto_tick',lease=lease,seq=0))
  self.assertIsNone(c.mission)
if __name__=='__main__':unittest.main()
