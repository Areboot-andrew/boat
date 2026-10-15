import time,unittest
from unittest.mock import Mock
from control_runner import BoardControl

class RebootTests(unittest.TestCase):
    def setUp(self):
        self.c=BoardControl();self.c.fd=1;self.c.parser=Mock()
        self.c.hb_at=time.monotonic()
        self.c.hb=dict(type=10,autopilot=3,base_mode=1,custom_mode=16,system_status=2)
    def request(self):return self.c.action(dict(action='reboot_fc',confirm='REBOOT_FC'))
    def test_config_error_can_reboot_without_ready_gate(self):
        self.assertTrue(self.request()['sent'])
        a=self.c.parser.command_long_send.call_args.args
        self.assertEqual(a[2],246);self.assertEqual(a[4:],(1,0,0,0,0,0,0))
        self.assertEqual(self.c.parser.command_long_send.call_count,1)
        self.c.parser.param_set_send.assert_not_called()
        with self.assertRaises(ValueError):self.request()
        self.assertEqual(self.c.parser.command_long_send.call_count,1)
    def test_confirmation_required(self):
        with self.assertRaises(ValueError):self.c.action(dict(action='reboot_fc'))
        self.c.parser.command_long_send.assert_not_called()
    def test_no_reboot_while_armed_owned_moving_or_offline(self):
        for key,value in [('hb_at',time.monotonic()-10),('fd',None),('owner','other'),('intent',(0,.1)),('applied',(.1,0)),('mission',object())]:
            old=getattr(self.c,key);setattr(self.c,key,value)
            with self.assertRaises(ValueError):self.request()
            setattr(self.c,key,old)
        self.c.hb['base_mode']=129
        with self.assertRaises(ValueError):self.request()
        self.c.parser.command_long_send.assert_not_called()

if __name__=='__main__':unittest.main()
