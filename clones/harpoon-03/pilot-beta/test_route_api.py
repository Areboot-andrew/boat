import unittest, tempfile, json
from pathlib import Path
from unittest.mock import Mock
from control_runner import BoardControl
from autonav import Store, DEFAULTS, plan_route
from test_smooth import geo
class RouteAPI(unittest.TestCase):
 def test_preview_read_only(self):
  c=BoardControl();c.parser=Mock();before=(c.owner,c.mission,c.intent)
  r=[geo(0,0),geo(40,0),geo(40,40)]
  p=c.action(dict(action='auto_preview',settings=DEFAULTS,route=r))
  self.assertEqual(p['points'],plan_route(DEFAULTS,r)['points']);self.assertEqual(before,(c.owner,c.mission,c.intent));self.assertEqual(c.parser.mock_calls,[])
 def test_legacy_config_and_atomic_save(self):
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'settings.json';old={k:v for k,v in DEFAULTS.items() if k!='turn_radius'}
   path.write_text(json.dumps(dict(settings=old,route=[])));s=Store(path)
   self.assertIsNone(s.error);self.assertEqual(s.config['turn_radius'],8)
   r=[geo(0,0),geo(40,0),geo(40,40)];s.save(s.config,r);before=path.read_text()
   with self.assertRaises(ValueError):s.save(s.config,[geo(0,0),geo(3,0),geo(3,3)])
   self.assertEqual(path.read_text(),before);self.assertEqual(Store(path).route,r)
if __name__=='__main__':unittest.main()
