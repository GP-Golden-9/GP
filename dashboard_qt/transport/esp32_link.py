"""Robot 3 (ESP32) transport — HTTP polling presented through the same
signal surface as RobotLink/CommandClient so the rest of the console
doesn't care which kind of robot it is talking to."""

from __future__ import annotations

import math
import threading
import time

import requests
from PySide6.QtCore import QObject, Signal

from gpcore.protocol import channels as ch
from gpcore.protocol import commands as cmds
from gpcore.protocol.envelope import make_envelope


class Esp32Link(QObject):
    telemetryReceived = Signal(object)   # Envelope-shaped (tele.full)
    healthReceived = Signal(object)
    linkUp = Signal(bool)
    ackReceived = Signal(str, str, bool, str)
    commandFailed = Signal(str, str, str)

    def __init__(self, host: str, *, poll_hz: float = 2.0, timeout_s: float = 1.0,
                 fwd_speed_mps: float = 0.15, reverse_speed_mps: float | None = None,
                 run_id: str = 'esp32', parent=None):
        super().__init__(parent)
        self.host = host
        self.poll_period = 1.0 / max(0.5, poll_hz)
        self.timeout_s = timeout_s
        self.run_id = run_id
        # Encoderless dead-reckoning: heading from the IMU (telemetry 'h'),
        # position from a fixed drive speed x time while moving F/B.
        self.fwd_speed = float(fwd_speed_mps)
        self.rev_speed = float(reverse_speed_mps if reverse_speed_mps is not None
                               else fwd_speed_mps)
        self._od_x = self._od_y = self._od_th = 0.0
        self._od_last: float | None = None
        # Dead-reckoning uses the COMMANDED direction (what the console sent),
        # not the device's telemetry 'dir' echo — the ESP reports motion direction
        # unreliably, but the laptop always knows what it asked for. Held with a
        # timeout matching the firmware's command watchdog so a dropped stream
        # stops advancing the pose too.
        self._held_dir = 'S'
        self._held_t = 0.0
        self.cmd_hold_s = 2.0
        self._pending_speed: float | None = None    # 0..1 to push to /speed
        self._speed_frac = 1.0                       # latest commanded speed (0..1)
        self._session = requests.Session()
        self._stop = threading.Event()
        self._cmd_lock = threading.Lock()
        self._pending_dir: str | None = None
        self._seq = 0
        self._up: bool | None = None
        self._fails = 0                  # consecutive telemetry failures
        self._thread: threading.Thread | None = None

    # same surface as CommandClient (subset that applies) ──────────────────
    def send(self, cmd_type: str, payload: dict) -> str:
        cmd_id = cmds.new_cmd_id()
        if cmd_type == cmds.CMD_DRIVE:
            vx = float(payload.get('vx', 0)); wz = float(payload.get('wz', 0))
            if abs(vx) < 0.01 and abs(wz) < 0.01:
                d = 'S'
            elif abs(vx) >= abs(wz):
                d = 'F' if vx > 0 else 'B'
            else:
                d = 'L' if wz > 0 else 'R'
            with self._cmd_lock:
                self._pending_dir = d            # latest-wins, sent by worker
                self._held_dir = d               # for pose dead-reckoning
                self._held_t = time.monotonic()
        elif cmd_type == cmds.CMD_ESTOP:
            with self._cmd_lock:
                self._pending_dir = 'S'
                self._held_dir = 'S'
                self._held_t = time.monotonic()
        elif cmd_type == cmds.CMD_SPEED:
            v = max(0.0, min(1.0, float(payload.get('value', 0.5))))
            with self._cmd_lock:
                self._pending_speed = v
                self._speed_frac = v
        else:
            self.commandFailed.emit(cmd_id, cmd_type, 'unsupported on ESP32')
        return cmd_id

    def drive(self, vx: float, wz: float) -> str:
        return self.send(cmds.CMD_DRIVE, {'vx': vx, 'wz': wz})

    def estop(self, engage: bool) -> None:
        self.send(cmds.CMD_ESTOP, {'engage': engage})

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name=f'esp32-{self.host}')
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    # ── encoderless dead-reckoning ────────────────────────────────────────
    def _dead_reckon(self, data: dict, now: float) -> dict:
        """Pose with no encoders: HEADING from the IMU (telemetry 'h', radians,
        integrated on the ESP32), POSITION advanced by a fixed drive speed x
        elapsed time while the reported direction is F/B. Turns are pivot-in-
        place (heading only, no translation). This is the robot's own frame;
        the main window applies the operator's SET POSE offset to map it."""
        try:
            th = float(data.get('h', self._od_th))
        except (TypeError, ValueError):
            th = self._od_th
        # Use the COMMANDED direction (held with a watchdog), not telemetry 'dir'.
        with self._cmd_lock:
            d = self._held_dir if (now - self._held_t) < self.cmd_hold_s else 'S'
            frac = self._speed_frac
        # Scale the calibrated speed by the slider: the Arduino PWMs 90..255, so
        # the actual speed ranges ~0.35x (slider min) to 1.0x (slider max).
        scale = 0.35 + 0.65 * frac
        fwd = self.fwd_speed * scale
        rev = self.rev_speed * scale
        if self._od_last is not None:
            dt = min(now - self._od_last, 1.0)        # clamp a stalled poll
            if dt > 0:
                if d == 'F':
                    self._od_x += fwd * math.cos(th) * dt
                    self._od_y += fwd * math.sin(th) * dt
                elif d == 'B':
                    self._od_x -= rev * math.cos(th) * dt
                    self._od_y -= rev * math.sin(th) * dt
                # L / R / S: pivot-in-place or stopped → no translation
        self._od_last = now
        self._od_th = th
        v = fwd if d == 'F' else (-rev if d == 'B' else 0.0)
        return {'x': round(self._od_x, 4), 'y': round(self._od_y, 4),
                'th': round(th, 4), 'v': round(v, 3), 'w': 0.0}

    # ── worker ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        next_poll = 0.0
        while not self._stop.is_set():
            now = time.monotonic()

            with self._cmd_lock:
                d, self._pending_dir = self._pending_dir, None
                sp, self._pending_speed = self._pending_speed, None
            if d is not None:
                # Drive gets a SHORT timeout so a momentary stall can't block
                # the control stream (the cause of the control lag).
                try:
                    self._session.get(f'http://{self.host}/control',
                                      params={'dir': d}, timeout=0.4)
                except requests.RequestException:
                    pass
            if sp is not None:
                try:
                    self._session.get(f'http://{self.host}/speed',
                                      params={'v': round(sp, 3)}, timeout=0.4)
                except requests.RequestException:
                    pass

            if now >= next_poll:
                next_poll = now + self.poll_period
                try:
                    r = self._session.get(f'http://{self.host}/telemetry',
                                          timeout=min(self.timeout_s, 0.6))
                    data = r.json()
                    self._fails = 0
                    self._seq += 1
                    odom = self._dead_reckon(data, now)
                    self.telemetryReceived.emit(make_envelope(ch.TELE_FULL, {
                        'esp32': data,
                        'gas': data.get('g'),
                        'odom': odom,
                    }, seq=self._seq, run_id=self.run_id, src=self.host))
                except (requests.RequestException, ValueError):
                    self._fails += 1
                # Debounce: 'up' on any good poll, 'down' only after 3 misses
                # in a row, so a single dropped poll no longer flaps the link.
                up = self._fails < 3
                if up != self._up:
                    self._up = up
                    self.linkUp.emit(up)
            time.sleep(0.03)
