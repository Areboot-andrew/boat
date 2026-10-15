import json
import os
import sys
from config_model import ffmpeg_args

if sys.argv[1] not in ['cam1', 'cam2'] or sys.argv[2] not in ['udp', 'web', 'qgc']:
    raise SystemExit('Invalid worker arguments')
with open('/etc/harpoon/boat.applied.json') as f:
    config = json.load(f)
args = ffmpeg_args(sys.argv[1], sys.argv[2], config)
# Pi04 RTP HEVC: allow non-key-marked packets; await parameter sets across GOP.
if sys.argv[1:3] == ['cam2', 'udp']:
    if '-analyzeduration' in args:
        args[args.index('-analyzeduration') + 1] = '3000000'
    args[args.index('-f'):args.index('-f')] = ['-copyinkf', '-bsf:v', 'dump_extra=freq=all']
os.execv(args[0], args)
