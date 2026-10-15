import json
import os
import sys
from config_model import ffmpeg_args

if sys.argv[1] not in ['cam1', 'cam2'] or sys.argv[2] not in ['udp', 'web', 'qgc']:
    raise SystemExit('Invalid worker arguments')
with open('/etc/harpoon/boat.applied.json') as f:
    config = json.load(f)
args = ffmpeg_args(sys.argv[1], sys.argv[2], config)
os.execv(args[0], args)
