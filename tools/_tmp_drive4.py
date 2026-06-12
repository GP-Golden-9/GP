import os
import sys
import time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'common'))
import zmq
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import decode, encode

HOST = '192.168.1.203'
ctx = zmq.Context()
tele = ctx.socket(zmq.SUB)
tele.setsockopt(zmq.SUBSCRIBE, b'')
tele.setsockopt(zmq.RCVTIMEO, 6000)
tele.connect(f'tcp://{HOST}:5556')
d = ctx.socket(zmq.DEALER)
d.setsockopt(zmq.RCVTIMEO, 1000)
d.connect(f'tcp://{HOST}:5558')
seq = 0


def enc():
    t_end = time.monotonic() + 6
    while time.monotonic() < t_end:
        env = decode(tele.recv())
        if env.type == 'tele.full' and env.payload.get('enc') is not None:
            return env.payload['enc'], env.payload.get('motor_status')
    return None, None


def send(t, p):
    global seq
    seq += 1
    d.send(encode(cmds.make_command(t, p, seq=seq, run_id='chk', src='chk')))


before, s0 = enc()
print('BEFORE:', before, s0)
t_end = time.monotonic() + 0.9
while time.monotonic() < t_end:
    send(cmds.CMD_DRIVE, {'vx': 0.30, 'wz': 0.0})
    time.sleep(0.1)
send(cmds.CMD_DRIVE, {'vx': 0.0, 'wz': 0.0})
time.sleep(1.2)
after, s1 = enc()
print('AFTER :', after, s1)
if before and after:
    delta = [a - b for a, b in zip(after, before)]
    moved = sum(abs(x) for x in delta) > 10
    print('DELTA :', delta, '=> WHEELS TURNED' if moved
          else '=> wheels did NOT turn')
