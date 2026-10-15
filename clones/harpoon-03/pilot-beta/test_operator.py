import time, unittest
from unittest.mock import Mock
from control_runner import BoardControl, engine

class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.c = c = BoardControl()
        c.fd = 1
        c.parser = Mock()
        c.hb_at = time.monotonic()
        c.hb = dict(type=10, autopilot=3, base_mode=1, custom_mode=0, system_status=3)
        c.params = {k: 0 for k in engine.PARAMS}
        c.params.update(SERVO1_FUNCTION=70, SERVO3_FUNCTION=26, SERVO1_MIN=1100, SERVO1_TRIM=1100, SERVO3_TRIM=1500, RCMAP_ROLL=1, RCMAP_THROTTLE=3, RC_OVERRIDE_TIME=3, SYSID_MYGCS=255)
        for ch in (1,3):
            for name, value in [('MIN',1100),('TRIM',1500 if ch==1 else 1100),('MAX',1900),('REVERSED',0)]:
                c.params[f'RC{ch}_{name}'] = value

    def test_claim_needs_operator_and_sends_no_arm(self):
        with self.assertRaises(ValueError):
            self.c.action(dict(action='claim'))
        lease=self.c.action(dict(action='claim',operator_confirmed=True))['lease']
        self.assertTrue(lease)
        self.c.parser.command_long_send.assert_not_called()

    def test_previous_disarmed_preparation_restored(self):
        self.c.hb['system_status']=5
        self.assertIsNone(self.c.snapshot()['claim_blocked'])
        self.c.action(dict(action='claim',operator_confirmed=True))
        self.assertIsNone(self.c.reason())
        self.c.parser.command_long_send.assert_not_called()
        self.c.bench_recovery_until=time.monotonic()-1
        self.assertIsNotNone(self.c.reason())
        self.c.bench_recovery_until=time.monotonic()+30
        self.c.hb['base_mode']=129
        self.assertIsNotNone(self.c.reason())

    def test_arm_is_explicit_and_not_forced(self):
        lease=self.c.action(dict(action='claim',operator_confirmed=True))['lease']
        with self.assertRaises(ValueError): self.c.action(dict(action='arm',lease=lease))
        self.c.action(dict(action='arm',lease=lease,confirm='ARM'))
        args=self.c.parser.command_long_send.call_args.args
        self.assertEqual(args[2],400)
        self.assertEqual(args[4:6],(1,0))

    def test_inspect_only_reads_parameters(self):
        self.c.action(dict(action='read_output_parameters'))
        self.assertEqual(self.c.parser.param_request_read_send.call_count,9)
        self.c.parser.command_long_send.assert_not_called()
        self.c.hb['base_mode']=129
        with self.assertRaises(ValueError): self.c.action(dict(action='read_output_parameters'))

    def test_gamepad_caps(self):
        lease=self.c.action(dict(action='claim',operator_confirmed=True))['lease']
        for seq,(mode,cap) in enumerate([(-1,.5),(0,.6),(1,.7)]):
            self.c.action(dict(action='tick',lease=lease,seq=seq,steer=0,throttle=0,throttle_cap=cap,input_source='gamepad',pad_gate=[1,1],pad_mode=mode))
            self.assertEqual(self.c.throttle_cap,cap)
        for mode,cap in [(-1,.6),(0,.7),(1,.71)]:
            with self.assertRaises(ValueError):self.c.action(dict(action='tick',lease=lease,seq=9,steer=0,throttle=0,throttle_cap=cap,input_source='gamepad',pad_gate=[1,1],pad_mode=mode))
        with self.assertRaises(ValueError):self.c.action(dict(action='tick',lease=lease,seq=10,steer=0,throttle=0,throttle_cap=.7))
        self.assertIsNone(self.c.owner)

if __name__=='__main__': unittest.main()
