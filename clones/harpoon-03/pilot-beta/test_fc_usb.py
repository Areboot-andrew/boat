import tempfile,unittest
from pathlib import Path
from fc_usb import resolve_port

class USBTests(unittest.TestCase):
 def test_discovery_replacement_and_ambiguity(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   for name in ['usb-ArduPilot_MatekH743_OLD-if02','usb-ArduPilot_MatekH743-BL_OLD-if00','usb-FTDI_GPS-if00']:(p/name).touch()
   with self.assertRaises(OSError):resolve_port(d)
   a=p/'usb-ArduPilot_MatekH743_ANY-if00';a.touch()
   self.assertEqual(resolve_port(d),str(a))
   b=p/'usb-ArduPilot_MatekH743_NEW-if00';b.touch()
   with self.assertRaises(OSError):resolve_port(d)
   a.unlink();self.assertEqual(resolve_port(d),str(b))
if __name__=='__main__':unittest.main()
