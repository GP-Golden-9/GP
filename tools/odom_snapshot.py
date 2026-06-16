#!/usr/bin/env python3
"""One-shot odometry snapshot for wheel-scale calibration.

Connects to a robot's gateway telemetry (ZMQ), waits for one tele.full
frame, and prints the cumulative encoder ticks [FL,RL,FR,RR] and the
reported odom pose (x, y, theta). Use it before and after driving a
measured straight distance to recover the true metres-per-tick.

Usage:
    python tools/odom_snapshot.py 192.168.1.203 5556
"""
import sys
import os

import zmq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))
from gpcore.protocol import channels as ch          # noqa: E402
from gpcore.protocol.envelope import decode, ProtocolError  # noqa: E402


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else '192.168.1.203'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5556
    ctx = zmq.Context()
    s = ctx.socket(zmq.SUB)
    s.setsockopt(zmq.SUBSCRIBE, b'')
    s.setsockopt(zmq.RCVTIMEO, 5000)
    s.connect(f'tcp://{host}:{port}')
    deadline = 25
    got = 0
    while got < deadline:
        try:
            env = decode(s.recv())
        except (zmq.Again, ProtocolError):
            got += 1
            continue
        if env.type != ch.TELE_FULL:
            continue
        p = env.payload
        enc = p.get('enc')
        odom = p.get('odom')
        print(f"ENC={enc}  ODOM={odom}")
        return 0
    print("no tele.full received (timeout)")
    return 1


if __name__ == '__main__':
    sys.exit(main())
