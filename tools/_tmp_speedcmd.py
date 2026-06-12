import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'common'))
import zmq
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import decode, encode

ctx = zmq.Context()
d = ctx.socket(zmq.DEALER)
d.setsockopt(zmq.RCVTIMEO, 3000)
d.connect('tcp://robot2.local:5558')
env = cmds.make_command(cmds.CMD_SPEED, {'value': 0.9}, seq=1,
                        run_id='probe', src='probe')
d.send(encode(env))
ack = decode(d.recv())
print('ACK:', ack.payload)

s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b'')
s.setsockopt(zmq.RCVTIMEO, 6000)
s.connect('tcp://robot2.local:5556')
time.sleep(1.0)
for _ in range(40):
    e2 = decode(s.recv())
    if e2.type == 'tele.full':
        print('motor:', e2.payload.get('motor_status'))
        break
