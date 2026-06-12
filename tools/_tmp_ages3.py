import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'common'))
import zmq
from gpcore.protocol.envelope import decode
ctx = zmq.Context()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b'')
s.setsockopt(zmq.RCVTIMEO, 6000)
s.connect('tcp://192.168.1.203:5559')
for _ in range(20):
    env = decode(s.recv())
    if env.type == 'health':
        print('uptime:', env.payload.get('uptime_s'),
              'ages:', env.payload.get('streams_age_s'))
        break
