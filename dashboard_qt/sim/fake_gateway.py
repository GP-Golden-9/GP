#!/usr/bin/env python3
"""Fake gateway — full dashboard development with ZERO hardware.

Binds the real protocol ports on localhost and behaves like robot2+robot1
merged: drives, maps, scans, streams video. Reuses the PRODUCTION
GatewayServer and GotoController, so the protocol the console sees is
bit-identical to a real robot.

World: the team's 4×4 m arena, 4 rooms with doorways, 0.05 m grid.
Physics: unicycle model @ 50 Hz, wall collisions, deadman decay (velocity
zeroes 0.6 s after the last drive cmd — same rule as the real gateway).

Fault injection (for the Phase-3 soak gate):
    --drop-video-at 30      video silent for 10 s starting at t=30 s
    --silence-map-at 45     map channel silent for 10 s
    --kill-at 90            hard exit (tests console reconnect + DEAD badges)
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import threading
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, 'common'))

import zmq                                                  # noqa: E402
from gateway.zmq_server import GatewayServer                # noqa: E402
from gpcore.logging_setup import new_run_id, setup_logging  # noqa: E402
from gpcore.nav import GotoController                       # noqa: E402
from gpcore.protocol import channels as ch                  # noqa: E402
from gpcore.protocol import commands as cmds                # noqa: E402
from gpcore.protocol.envelope import make_envelope, pack_with_blob  # noqa: E402

RES = 0.05
GRID_N = 80                       # 80 × 0.05 = 4 m
ORIGIN = -2.0                     # world center at (0,0)
SCAN_RAYS = 240
SCAN_RMAX = 6.0
PHYS_HZ = 50.0
VIDEO_FPS = 15


def build_arena() -> np.ndarray:
    """4×4 m, 4 rooms, doorway gaps — matches the team's test environment."""
    g = np.zeros((GRID_N, GRID_N), dtype=np.int8)
    g[0, :] = 100; g[-1, :] = 100; g[:, 0] = 100; g[:, -1] = 100
    mid = GRID_N // 2
    g[mid, :] = 100                      # horizontal wall
    g[:, mid] = 100                      # vertical wall
    for lo, hi in ((14, 26), (54, 66)):  # doorways
        g[mid, lo:hi] = 0
        g[lo:hi, mid] = 0
    return g


class SimRobot:
    def __init__(self, grid: np.ndarray):
        self.grid = grid
        self.x, self.y, self.th = -1.0, -1.0, 0.0
        self.v = self.w = 0.0
        self.last_drive = 0.0
        self.enc = [0, 0, 0, 0]
        self.pump = False
        self.servo = 90
        self.estop = False
        self.exploring = False
        self.goto = GotoController()

    def occupied(self, x: float, y: float) -> bool:
        i = int((y - ORIGIN) / RES)
        j = int((x - ORIGIN) / RES)
        if not (0 <= i < GRID_N and 0 <= j < GRID_N):
            return True
        return self.grid[i, j] > 50

    def step(self, dt: float) -> None:
        now = time.monotonic()
        if self.estop:
            self.v = self.w = 0.0
        elif now - self.last_drive > cmds.DEADMAN_S:
            # autonomous sources keep their own cadence
            if self.exploring:
                self._explore_step()
            elif self.goto.has_goal:
                cmd = self.goto.step(self.x, self.y, self.th)
                self.v, self.w = cmd.linear, cmd.angular
            else:
                self.v = self.w = 0.0

        nx = self.x + self.v * math.cos(self.th) * dt
        ny = self.y + self.v * math.sin(self.th) * dt
        if not self.occupied(nx + 0.12 * math.cos(self.th),
                             ny + 0.12 * math.sin(self.th)):
            # encoder ticks from wheel kinematics (65 mm wheels, 330 t/rev)
            d = math.hypot(nx - self.x, ny - self.y) * (1 if self.v >= 0 else -1)
            dth_wheel = self.w * dt * 0.23 / 2.0
            mpt = math.pi * 0.065 / 330
            dl = int(round((d - dth_wheel) / mpt))
            dr = int(round((d + dth_wheel) / mpt))
            self.enc[0] += dl; self.enc[1] += dl
            self.enc[2] += dr; self.enc[3] += dr
            self.x, self.y = nx, ny
        self.th = math.atan2(math.sin(self.th + self.w * dt),
                             math.cos(self.th + self.w * dt))

    def _explore_step(self) -> None:
        front = self.raycast(self.th)
        if front < 0.45:
            self.v, self.w = 0.0, 0.5
        else:
            self.v, self.w = 0.12, 0.0

    def raycast(self, angle: float) -> float:
        step = RES / 2
        r = 0.0
        while r < SCAN_RMAX:
            r += step
            if self.occupied(self.x + r * math.cos(angle),
                             self.y + r * math.sin(angle)):
                return r
        return SCAN_RMAX

    def scan(self) -> np.ndarray:
        angles = np.linspace(-math.pi, math.pi, SCAN_RAYS, endpoint=False)
        return np.array([self.raycast(self.th + a) for a in angles],
                        dtype=np.float32), angles[1] - angles[0]


def draw_flame(frame, cx: int, cy: int, t: float, rng: np.random.Generator) -> None:
    """Animated flame: layered red→orange→yellow tongues with flicker.

    Realistic enough that fire-trained YOLO models often trigger on it,
    which lets the FULL alert pipeline (camera → inference child →
    detections → alert engine → banner) be exercised with zero hardware.
    """
    import cv2
    layers = (((10, 30, 200), 46), ((20, 90, 235), 34), ((40, 170, 250), 24),
              ((120, 235, 255), 12))
    for (color, base_r) in layers:
        for k in range(5):
            phase = t * (6.5 + k * 1.7) + k * 2.1
            ox = int(math.sin(phase) * base_r * 0.35 + rng.normal(0, 2.0))
            oy = -int(k * base_r * 0.35 + abs(math.sin(phase * 0.7)) * 9)
            r_w = max(4, int(base_r * (1.0 + 0.18 * math.sin(phase * 1.3))))
            r_h = max(6, int(r_w * (1.5 + 0.3 * math.sin(phase))))
            cv2.ellipse(frame, (cx + ox, cy + oy), (r_w, r_h),
                        0, 0, 360, color, -1)


def video_thread(run_id: str, stop: threading.Event, faults: dict,
                 fire_image_path: str = '') -> None:
    import cv2
    ctx = zmq.Context.instance()
    pub = ctx.socket(zmq.PUB); pub.setsockopt(zmq.SNDHWM, 2)
    pub.setsockopt(zmq.LINGER, 0); pub.bind('tcp://*:5560')
    legacy = ctx.socket(zmq.PUB); legacy.setsockopt(zmq.SNDHWM, 1)
    legacy.setsockopt(zmq.LINGER, 0); legacy.bind('tcp://*:5555')

    fire_img = cv2.imread(fire_image_path) if fire_image_path else None
    if fire_img is not None:
        fire_img = cv2.resize(fire_img, (400, 300))

    base = np.zeros((480, 640, 3), np.uint8)
    base[:] = (40, 30, 24)
    for i in range(0, 640, 40):
        cv2.line(base, (i, 0), (i, 480), (60, 50, 40), 1)
    rng = np.random.default_rng(7)
    seq = 0
    t0 = time.monotonic()
    while not stop.is_set():
        t = time.monotonic() - t0
        if faults['drop_video_at'] and faults['drop_video_at'] <= t < faults['drop_video_at'] + 10:
            time.sleep(0.1)
            continue
        frame = base.copy()
        # fire is "burning" on a 12 s cycle: 7 s on, 5 s off — exercises both
        # the alert RAISE and the auto-CLEAR paths of the alert engine
        fire_on = (t % 12.0) < 7.0
        if fire_on:
            if fire_img is not None:
                jitter = int(3 * math.sin(t * 9))
                frame[100:400, 120 + jitter:520 + jitter] = fire_img
            else:
                draw_flame(frame, 320, 300, t, rng)
        cv2.putText(frame, f'SIM CAMERA t={t:6.1f}s frame={seq} '
                           f'fire={"ON" if fire_on else "off"}',
                    (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1)
        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 35])
        if not ok:
            continue
        jpeg = buf.tobytes()
        seq += 1
        meta = make_envelope(ch.VIDEO_META, {
            'w': 640, 'h': 480, 'fmt': 'jpeg',
            'cap_t_mono': time.monotonic(), 'frame_id': seq,
        }, seq=seq, run_id=run_id, src='sim')
        try:
            pub.send(pack_with_blob(meta, jpeg), zmq.NOBLOCK)
            legacy.send(jpeg, zmq.NOBLOCK)
        except zmq.Again:
            pass
        time.sleep(1.0 / VIDEO_FPS)
    pub.close(0); legacy.close(0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--drop-video-at', type=float, default=0)
    ap.add_argument('--silence-map-at', type=float, default=0)
    ap.add_argument('--kill-at', type=float, default=0)
    ap.add_argument('--fire-image', default='',
                    help='photo of real fire to composite into the video '
                         '(more reliable detection than the synthetic flame)')
    args = ap.parse_args()
    faults = {'drop_video_at': args.drop_video_at}

    run_id = os.environ.get('GP_RUN_ID') or new_run_id()
    log = setup_logging('fake_gateway', run_id=run_id)

    grid = build_arena()
    robot = SimRobot(grid)
    server = GatewayServer(run_id=run_id, src='sim-robot2', endpoints={
        'telemetry': 'tcp://*:5556', 'map': 'tcp://*:5557',
        'health': 'tcp://*:5559', 'cmd': 'tcp://*:5558'})

    # ── command handlers drive the sim robot ──
    def h_drive(env):
        robot.v = float(env.payload.get('vx', 0))
        robot.w = float(env.payload.get('wz', 0))
        robot.last_drive = time.monotonic()
        robot.goto.cancel()
        return True, 'ok'

    def h_estop(env):
        robot.estop = bool(env.payload.get('engage', True))
        if robot.estop:
            robot.v = robot.w = 0.0
            robot.pump = False
        return True, 'engaged' if robot.estop else 'released'

    def h_pump(env):
        if robot.estop and env.payload.get('on'):
            return False, 'estop latched'
        robot.pump = bool(env.payload.get('on'))
        return True, f'PUMP={"ON" if robot.pump else "OFF"}'

    def h_servo(env):
        robot.servo = max(10, min(170, int(env.payload.get('deg', 90))))
        return True, f'SERVO={robot.servo}'

    def h_explore(env):
        robot.exploring = bool(env.payload.get('enable'))
        return True, 'ok'

    def h_goal(env):
        robot.goto.set_goal(float(env.payload['x']), float(env.payload['y']))
        return True, 'ok'

    server.set_handler(cmds.CMD_DRIVE, h_drive)
    server.set_handler(cmds.CMD_ESTOP, h_estop)
    server.set_handler(cmds.CMD_PUMP, h_pump)
    server.set_handler(cmds.CMD_SERVO, h_servo)
    server.set_handler(cmds.CMD_EXPLORE, h_explore)
    server.set_handler(cmds.CMD_GOAL, h_goal)
    server.set_handler(cmds.CMD_SPEED, lambda env: (True, 'ok'))

    stop = threading.Event()
    vt = threading.Thread(target=video_thread,
                          args=(run_id, stop, faults, args.fire_image),
                          daemon=True)
    vt.start()

    log.info('fake gateway up', extra={'kv': {
        'ports': '5555-5560', 'arena': '4x4m/4rooms', 'faults': vars(args)}})

    grid_z = zlib.compress(grid.tobytes(), 3)
    t0 = time.monotonic()
    last_tele = last_scan = last_map = last_health = 0.0
    try:
        while True:
            now = time.monotonic()
            t = now - t0
            if args.kill_at and t > args.kill_at:
                log.error('fault injection: hard exit now')
                os._exit(1)

            server.poll_commands(0)
            if server.deadman_tripped():
                robot.v = robot.w = 0.0
            robot.estop = server.estop_latched or robot.estop
            robot.step(1.0 / PHYS_HZ)

            if now - last_tele >= 0.05:
                last_tele = now
                server.publish('telemetry', ch.TELE_FULL, {
                    'enc': list(robot.enc),
                    'gyro': [0.0, 0.0, robot.w], 'accel': [0.0, 0.0, 9.81],
                    'odom': {'x': round(robot.x, 4), 'y': round(robot.y, 4),
                             'th': round(robot.th, 4),
                             'v': round(robot.v, 3), 'w': round(robot.w, 3)},
                    'pump': robot.pump, 'servo_deg': robot.servo,
                    'estop': robot.estop,
                    'nav_status': (robot.goto.state.value
                                   if robot.goto.has_goal else 'IDLE'),
                    'motor_status': 'SIM', 'accessory': '',
                })
            if now - last_scan >= 0.2:
                last_scan = now
                ranges, da = robot.scan()
                server.publish('telemetry', ch.TELE_SCAN, {
                    'a0': -math.pi + robot.th * 0,   # scan is robot-relative
                    'da': float(da), 'rmin': 0.05, 'rmax': SCAN_RMAX,
                    'ranges': ranges.tobytes()})
            map_silent = (args.silence_map_at and
                          args.silence_map_at <= t < args.silence_map_at + 10)
            if now - last_map >= 1.0 and not map_silent:
                last_map = now
                server.publish('map', ch.MAP_GRID, {
                    'w': GRID_N, 'h': GRID_N, 'res': RES,
                    'ox': ORIGIN, 'oy': ORIGIN, 'enc': 'zlib', 'data': grid_z})
            if now - last_health >= 1.0:
                last_health = now
                server.publish('health', ch.HEALTH, {
                    'uptime_s': round(t, 1),
                    'streams_age_s': {'encoders': 0.02, 'imu': 0.02,
                                      'odom': 0.02, 'scan': 0.2, 'map': 1.0,
                                      'motor_status': 0.1},
                    'sys': {'throttled': '0x0', 'temp_c': 47.2,
                            'rssi_dbm': -52, 'load1': 0.7,
                            'mem_free_mb': 5200, 'disk_free_mb': 21000},
                    'cmd_stats': dict(server.stats),
                    'estop': robot.estop})
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
