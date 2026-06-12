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
s.connect('tcp://robot2.local:5556')
for _ in range(40):
    env = decode(s.recv())
    if env.type == 'tele.full':
        print('motor:', env.payload.get('motor_status'),
              'enc:', env.payload.get('enc'))
        break
