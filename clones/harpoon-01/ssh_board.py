"""Pi01 only; pinned key plus hostname checked before uploads or scripts."""
import base64,hashlib,os,shlex,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work/backup-ssh-runtime'))
import paramiko
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
class Pin(paramiko.MissingHostKeyPolicy):
 def missing_host_key(self,client,host,key):
  if base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')!='5xYhdtk6hEW8oVZZIQZQUIn90hKLHCf9QZylCgJKunQ':raise RuntimeError('Wrong Pi01 host key')
c=paramiko.SSHClient();c.set_missing_host_key_policy(Pin())
try:
 c.connect('100.82.12.5',username='harpoon',password=os.environ['HARPOON_SSH_PASSWORD'],look_for_keys=False,allow_agent=False,timeout=10)
 _,o,_=c.exec_command('hostname')
 if o.read().decode().strip()!='harpoon-pi5':raise RuntimeError('Wrong Pi01 hostname')
 if sys.argv[1]=='--download':
  with c.open_sftp() as s:s.get(sys.argv[2],sys.argv[3])
  print('Read',sys.argv[2])
 elif sys.argv[1]=='--upload':
  with c.open_sftp() as s:s.put(sys.argv[2],sys.argv[3])
  print('Uploaded',sys.argv[3])
 else:
  cmd=Path(sys.argv[2]).read_text() if sys.argv[1]=='--script' else sys.argv[1]
  i,o,e=c.exec_command('sudo -S -p "" sh -c '+shlex.quote(cmd)+' 2>&1',timeout=900)
  i.write(os.environ['HARPOON_SSH_PASSWORD']+'\n');i.flush()
  for line in o:print(line,end='',flush=True)
  sys.exit(o.channel.recv_exit_status())
finally:c.close()
