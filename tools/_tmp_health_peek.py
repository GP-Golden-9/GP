"""Throwaway: watch robot1's scan freshness over ~10 s."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'common'))

import zmq
from gpcore.protocol.envelope import decode

ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b'')
s.setsockopt(zmq.RCVTIMEO, 8000)
s.connect('tcp://robot.local:5559')

t_end = time.monotonic() + 12
while time.monotonic() < t_end:
    try:
        env = decode(s.recv())
    except zmq.Again:
        print('TIMEOUT: no health traffic')
        break
    if env.type != 'health':
        continue
    ages = env.payload.get('streams_age_s', {})
    print(f"scan_age={ages.get('scan')}  map_age={ages.get('map')}  "
          f"odom_age={ages.get('odom')}  uptime={env.payload.get('uptime_s')}")
