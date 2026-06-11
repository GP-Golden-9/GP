"""Throwaway: one-line robot2 pose+enc snapshot."""
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
s.setsockopt(zmq.RCVTIMEO, 6000)
s.connect('tcp://192.168.1.203:5556')
tag = sys.argv[1] if len(sys.argv) > 1 else 'SNAP'
deadline = time.monotonic() + 6
while time.monotonic() < deadline:
    env = decode(s.recv())
    if env.type == 'tele.full' and env.payload.get('odom'):
        o = env.payload['odom']
        print(f"{tag} x={o['x']:+.3f} y={o['y']:+.3f} th={o['th']:+.3f} "
              f"enc={env.payload.get('enc')}")
        break
