import base64, hashlib, os, shlex, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'work/backup-ssh-runtime'))
import paramiko
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

class Pin(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, host, key):
        fingerprint = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        if fingerprint != 'WjW3tyvjOYz0w+YHnuiowDd7xE/jGknd+RVFlnTf0nY':
            raise RuntimeError('Not the verified second board')

client = paramiko.SSHClient()
client.set_missing_host_key_policy(Pin())
try:
    client.connect(os.environ.get('HARPOON_SSH_HOST', '192.168.10.50'), username='harpoon', password=os.environ['HARPOON_SSH_PASSWORD'], look_for_keys=False, allow_agent=False, timeout=10)
    _, out, _ = client.exec_command('hostname')
    if out.read().decode().strip() != 'harpoon-pi5-02':
        raise RuntimeError('Wrong hostname')
    if sys.argv[1] == '--download':
        with client.open_sftp() as sftp:
            sftp.get(sys.argv[2], sys.argv[3])
        print('Downloaded', sys.argv[3])
    elif sys.argv[1] == '--upload':
        with client.open_sftp() as sftp:
            sftp.put(sys.argv[2], sys.argv[3])
        print('Uploaded', sys.argv[3])
    else:
        command = Path(sys.argv[2]).read_text(encoding='utf-8') if sys.argv[1] == '--script' else sys.argv[1]
        stdin, out, err = client.exec_command('sudo -S -p "" sh -c ' + shlex.quote(command) + ' 2>&1', timeout=900)
        stdin.write(os.environ['HARPOON_SSH_PASSWORD'] + '\n'); stdin.flush()
        for line in out:
            print(line, end='', flush=True)
        sys.exit(out.channel.recv_exit_status())
finally:
    client.close()
