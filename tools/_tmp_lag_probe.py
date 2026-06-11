"""Throwaway: measure robot2 telemetry rate, end-to-end delay, odom motion."""
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
s.connect('tcp://robot2.local:5556')

n = 0
delays = []
seqs = []
poses = []
t_end = time.monotonic() + 12
while time.monotonic() < t_end:
    try:
        env = decode(s.recv())
    except zmq.Again:
        print('TIMEOUT: no telemetry for 6 s')
        break
    if env.type != 'tele.full':
        continue
    n += 1
    delays.append(time.time() - env.t_wall)   # end-to-end (clock-sync caveat)
    seqs.append(env.seq)
    o = env.payload.get('odom') or {}
    poses.append((o.get('x'), o.get('y'), o.get('th')))

if n:
    delays.sort()
    print(f'tele.full msgs in 12 s : {n}  (rate {n/12:.1f} Hz, expect 20)')
    print(f'delay p50/p95/max (s)  : {delays[len(delays)//2]:.2f} / '
          f'{delays[int(len(delays)*0.95)]:.2f} / {delays[-1]:.2f}')
    print(f'seq first..last        : {seqs[0]} .. {seqs[-1]} '
          f'(gaps: {seqs[-1]-seqs[0]+1-n})')
    print(f'pose first             : {poses[0]}')
    print(f'pose last              : {poses[-1]}')
    moved = max(abs((a or 0)-(b or 0)) for a, b in zip(poses[0], poses[-1]))
    print(f'pose changed?          : {"YES" if moved > 0.01 else "NO (frozen)"}')
