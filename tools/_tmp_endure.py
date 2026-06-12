"""Endurance watch: print uptime + max stream age every 15 s for 6 min.
Any age that starts climbing = the deafness returned."""
import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'common'))
import zmq
from gpcore.protocol.envelope import decode

ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b'')
s.setsockopt(zmq.RCVTIMEO, 8000)
s.connect('tcp://192.168.1.203:5559')

t_end = time.monotonic() + 360
next_print = 0.0
while time.monotonic() < t_end:
    try:
        env = decode(s.recv())
    except zmq.Again:
        print('HEALTH STREAM SILENT 8s', flush=True)
        continue
    if env.type != 'health':
        continue
    now = time.monotonic()
    if now < next_print:
        continue
    next_print = now + 15
    p = env.payload
    ages = p.get('streams_age_s') or {}
    vals = [v for v in ages.values() if v is not None]
    mx = max(vals) if vals else -1
    verdict = 'OK' if mx < 3 else f'DEAF (max age {mx:.0f}s)'
    print(f"uptime={p.get('uptime_s'):7.1f} max_age={mx:6.2f} {verdict}",
          flush=True)
print('ENDURANCE WINDOW COMPLETE', flush=True)
