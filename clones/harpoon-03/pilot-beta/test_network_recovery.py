"""Mock-only tests; never open a serial port or start the service."""
import time
from unittest.mock import patch
from test_manual_critical import Tests

class NetworkTests(Tests):
 def active(self):
  c=self.c;lease=c.action(dict(action='claim',operator_confirmed=True))['lease']
  c.hb['base_mode']=129
  r=c.action(dict(action='tick',lease=lease,seq=0,steer=0,throttle=0))
  return c,lease,r['nonce']
 def test_delayed_valid_command(self):
  c,l,n=self.active();now=time.monotonic()
  with patch('control_service.time.monotonic',return_value=now+1.2):
   r=c.action(dict(action='tick',lease=l,seq=1,nonce=n,steer=.1,throttle=.2))
  self.assertFalse(r['network_paused']);self.assertEqual(c.intent,(.1,.2));self.assertEqual(c.owner,l)
  c.parser.command_long_send.assert_not_called()
 def test_timeout_neutral_retains_session_no_mode_command(self):
  c,l,n=self.active();c.intent=c.applied=(.2,.25)
  c.check_network_deadline(c.deadline+.1)
  self.assertEqual(c.owner,l);self.assertEqual(c.intent,(0,0));self.assertEqual(c.applied,(0,0));self.assertTrue(c.network_paused)
  c.parser.command_long_send.assert_not_called()
  r=c.action(dict(action='tick',lease=l,seq=1,nonce=n,steer=.1,throttle=.2))
  self.assertTrue(r['network_paused']);self.assertEqual(c.intent,(0,0))
  r=c.action(dict(action='tick',lease=l,seq=2,steer=0,throttle=0,resync=True))
  self.assertFalse(r['network_paused']);self.assertEqual(c.owner,l)
  c.action(dict(action='tick',lease=l,seq=3,nonce=r['nonce'],steer=.1,throttle=.2))
  self.assertEqual(c.intent,(.1,.2))
 def test_lost_reply_resync_rejects_delayed_old_motion(self):
  c,l,n=self.active()
  c.action(dict(action='tick',lease=l,seq=1,nonce=n,steer=.1,throttle=.2))
  r=c.action(dict(action='tick',lease=l,seq=2,steer=0,throttle=0,resync=True))
  with self.assertRaisesRegex(ValueError,'Застарілий'):
   c.action(dict(action='tick',lease=l,seq=1,nonce=n,steer=.1,throttle=.2))
  self.assertEqual(c.intent,(0,0));self.assertEqual(c.owner,l)
  c.parser.command_long_send.assert_not_called()
 def test_mission_resync_keeps_manual_session(self):
  c,l=self.start_critical_mission()
  c.action(dict(action='tick',lease=l,seq=2,steer=0,throttle=0,resync=True))
  self.assertIsNone(c.mission);self.assertEqual(c.owner,l);self.assertEqual(c.intent,(0,0))
  c.parser.command_long_send.assert_not_called()
 def test_wrong_owner_cannot_pause(self):
  c,l,n=self.active();c.intent=(.1,.2)
  with self.assertRaises(ValueError):c.action(dict(action='tick',lease='wrong',resync=True,seq=1,steer=0,throttle=0))
  self.assertEqual(c.intent,(.1,.2));self.assertEqual(c.owner,l)
