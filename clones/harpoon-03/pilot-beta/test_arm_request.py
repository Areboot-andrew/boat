import time,unittest
from unittest.mock import Mock
from control_runner import BoardControl

class ArmRequestTests(unittest.TestCase):
    def setUp(self):
        self.c=BoardControl();self.c.fd=1;self.c.parser=Mock();self.c.hb_at=time.monotonic()
        self.c.hb=dict(type=10,autopilot=3,base_mode=1,custom_mode=16,system_status=2)
    def request(self):return self.c.action(dict(action='arm_request',confirm='REQUEST_NORMAL_ARM'))
    def test_normal_request_does_not_grant_control_or_change_params(self):
        self.assertTrue(self.request()['sent'])
        a=self.c.parser.command_long_send.call_args.args
        self.assertEqual(a[2],400);self.assertEqual(a[4:6],(1,0))
        self.assertIsNone(self.c.owner);self.assertIsNotNone(self.c.reason())
        self.c.parser.param_set_send.assert_not_called()
        with self.assertRaises(ValueError):self.request()
        self.assertEqual(self.c.parser.command_long_send.call_count,1)
    def test_no_confirmation_no_request(self):
        with self.assertRaises(ValueError):self.c.action(dict(action='arm_request'))
        self.c.parser.command_long_send.assert_not_called()
    def test_stale_busy_or_armed_rejected(self):
        for key,value in [('hb_at',0),('fd',None),('owner','other'),('mission',object()),('intent',(0,.1)),('release_at',1)]:
            old=getattr(self.c,key);setattr(self.c,key,value)
            with self.assertRaises(ValueError):self.request()
            setattr(self.c,key,old)
        self.c.hb['base_mode']=129
        with self.assertRaises(ValueError):self.request()
        self.c.parser.command_long_send.assert_not_called()
if __name__=='__main__':unittest.main()
