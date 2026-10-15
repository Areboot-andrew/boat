import unittest,time,termios
from unittest.mock import patch,Mock
import control_service as e

class ReconnectTests(unittest.TestCase):
 def test_unplug_cleanup_closes_even_on_termios_error(self):
  with patch.object(e.termios,'tcsetattr',side_effect=termios.error(5,'USB gone')),patch.object(e.fcntl,'ioctl',side_effect=OSError()),patch.object(e.os,'close') as close:
   e.close_serial(17,[1]);close.assert_called_once_with(17)
 def test_bad_fd_does_not_escape(self):
  with patch.object(e.fcntl,'ioctl',side_effect=OSError()),patch.object(e.os,'close',side_effect=OSError()):e.close_serial(17,None)
 def test_worker_failure_exits_for_restart(self):
  for alive,age in [(False,0),(True,21)]:
   c=Mock(loop_at=time.monotonic()-age);worker=Mock();worker.is_alive.return_value=alive
   with patch.object(e.time,'sleep'),patch.object(e.os,'_exit',side_effect=SystemExit) as stop:
    with self.assertRaises(SystemExit):e.supervise_worker(worker,c)
    stop.assert_called_once_with(1)
 def test_retries_after_unplug_without_commands(self):
  c=e.Control();c.stop=Mock()
  with patch.object(e.subprocess,'run',return_value=Mock(returncode=1)),patch.object(e.os,'open',side_effect=OSError('gone')) as op,patch.object(e.time,'sleep',side_effect=[None,SystemExit]):
   with self.assertRaises(SystemExit):c.run()
  self.assertEqual(op.call_count,2);self.assertIsNone(c.owner);self.assertEqual(c.hb,{})
if __name__=='__main__':unittest.main()
