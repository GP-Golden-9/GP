"""Throwaway: print robot2 encoder/pose lines whenever they CHANGE."""
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
s.connect('tcp://192.168.1.203:5556')

last = None
t_end = time.monotonic() + 1200
while time.monotonic() < t_end:
    try:
        env = decode(s.recv())
    except zmq.Again:
        print('TELEMETRY GONE (8 s silence)', flush=True)
        continue
    if env.type != 'tele.full':
        continue
    enc = tuple(env.payload.get('enc') or ())
    if enc != last:
        last = enc
        o = env.payload.get('odom') or {}
        print(f"ENC {list(enc)}  x={o.get('x', 0):+.3f} "
              f"y={o.get('y', 0):+.3f} th={o.get('th', 0):+.3f}", flush=True)
