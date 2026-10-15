import unittest
import math
from bms_mavlink import battery_message, named_messages, mav

class BatteryTests(unittest.TestCase):
    def test_pack(self):
        msg=battery_message({'bms':{'bms_link_ok':True,'battery_voltage':74.263,'battery_current_a':-12.34,'battery_soc':55}},10)
        self.assertEqual(msg.voltages[:2],[65534,8729])
        self.assertEqual(msg.current_battery,1234)
        encoder=mav.MAVLink(None,srcSystem=1,srcComponent=191)
        decoded=mav.MAVLink(None).parse_char(msg.pack(encoder))
        self.assertEqual(decoded.get_srcSystem(),1)
        self.assertEqual(decoded.get_srcComponent(),191)
        self.assertEqual(decoded.id,10)
        self.assertEqual(decoded.battery_remaining,55)
    def test_stale(self):
        msg=battery_message({'bms':{'bms_link_ok':False,'battery_voltage':80,'battery_soc':90}},10)
        self.assertEqual(msg.battery_remaining,-1)
        self.assertEqual(msg.voltages,[65535]*10)
    def test_invalid(self):
        msg=battery_message({'bms':{'bms_link_ok':True,'battery_voltage':float('nan'),'battery_current_a':-999}},10)
        self.assertEqual(msg.current_battery,-1)
        self.assertEqual(msg.temperature,32767)
    def test_named_values(self):
        data={'bms':{'bms_link_ok':True,'battery_power_w':250},'energy':{'instant_wh_km':25,'average_wh_km':30,'range_km':80}}
        encoder=mav.MAVLink(None,srcSystem=1,srcComponent=191)
        messages=named_messages(data,2**32+42)
        self.assertEqual([m.value for m in messages],[250,25,30,80])
        for msg in messages:
            decoded=mav.MAVLink(None).parse_char(msg.pack(encoder))
            self.assertEqual(decoded.time_boot_ms,42)
            self.assertEqual(decoded.get_type(),'NAMED_VALUE_FLOAT')
            self.assertLessEqual(len(decoded.name),10)
    def test_named_stale_and_missing(self):
        self.assertTrue(all(math.isnan(m.value) for m in named_messages({},0)))
        messages=named_messages({'bms':{'bms_link_ok':True,'battery_power_w':0}},0)
        self.assertEqual(messages[0].value,0)
        self.assertTrue(math.isnan(messages[3].value))

if __name__=='__main__': unittest.main()
