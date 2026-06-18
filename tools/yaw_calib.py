#!/usr/bin/env python3
"""Gyro scale-factor calibration for Beta (or any robot that streams 'heading').

The residual yaw drift after the 50 Hz heading fix is the MPU6050's per-unit
scale tolerance (+/-3%), and it's proportional to total rotation. One number
cancels it. This tool reads the robot's integrated heading off the telemetry
channel, unwraps it into a running TOTAL rotation, and tells you the correction
factor to paste into config/robot2.yaml -> drive.gyro_scale_correction.

USAGE
  python tools/yaw_calib.py 192.168.1.203 [known_deg]   # default known_deg=360

PROCEDURE
  1. Put a mark on the floor and a matching mark on the robot.
  2. Start this tool. It zeroes on the first heading sample.
  3. Rotate the robot SLOWLY (well under one turn per ~3 s, so the gyro never
     clips its +/-500 deg/s range) exactly ONE FULL TURN (360 deg) back to the
     mark. Do it a few turns for a better average and pass that as known_deg
     (e.g. 1080 for three turns).
  4. Read the live 'correction' value when you're back on the mark. Paste it.
     Then redeploy:  bundle/scp the config + restart gp-robot2.

It's read-only — it never commands the robot.
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))

import zmq  # noqa: E402
from gpcore.protocol import channels as ch        # noqa: E402
from gpcore.protocol.envelope import decode        # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    host = sys.argv[1]
    known_deg = float(sys.argv[2]) if len(sys.argv) > 2 else 360.0
    port = 5556                                    # telemetry PUB

    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.setsockopt(zmq.SUBSCRIBE, b'')
    sock.setsockopt(zmq.RCVTIMEO, 3000)
    sock.connect(f'tcp://{host}:{port}')
    print(f'connected tcp://{host}:{port} — waiting for heading…  (Ctrl+C to stop)')

    prev = None
    total = 0.0          # unwrapped accumulated rotation, radians
    samples = 0
    try:
        while True:
            try:
                raw = sock.recv()
            except zmq.Again:
                print('  (no telemetry — is the stack up? right IP?)')
                continue
            try:
                env = decode(raw)
            except Exception:
                continue
            if env.type != ch.TELE_FULL:
                continue
            h = env.payload.get('heading')
            if h is None:
                continue
            if prev is not None:
                d = math.atan2(math.sin(h - prev), math.cos(h - prev))
                total += d
            prev = h
            samples += 1
            deg = math.degrees(total)
            corr = (known_deg / abs(deg)) if abs(deg) > 5 else float('nan')
            print(f'\r rotated {deg:+8.1f} deg   '
                  f'target {known_deg:.0f}   '
                  f'correction = {corr:6.4f}   (samples {samples})',
                  end='', flush=True)
            time.sleep(0.01)
    except KeyboardInterrupt:
        deg = math.degrees(total)
        print('\n\n=== RESULT ===')
        print(f'  measured rotation : {deg:+.1f} deg (target {known_deg:.0f})')
        if abs(deg) > 5:
            corr = known_deg / abs(deg)
            print(f'  gyro_scale_correction: {corr:.4f}   '
                  '<- paste into config/robot2.yaml drive:')
            if corr > 1:
                print('  (>1: the gyro UNDER-reads rotation — expected if it drifts back short)')
        else:
            print('  not enough rotation captured — rotate a full turn and retry')
        return 0


if __name__ == '__main__':
    sys.exit(main())
