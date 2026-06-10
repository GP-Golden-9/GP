"""Robot 3 (ESP32) transport — HTTP polling presented through the same
signal surface as RobotLink/CommandClient so the rest of the console
doesn't care which kind of robot it is talking to."""

from __future__ import annotations

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
                 run_id: str = 'esp32', parent=None):
        super().__init__(parent)
        self.host = host
        self.poll_period = 1.0 / max(0.5, poll_hz)
        self.timeout_s = timeout_s
        self.run_id = run_id
        self._session = requests.Session()
        self._stop = threading.Event()
        self._cmd_lock = threading.Lock()
        self._pending_dir: str | None = None
        self._seq = 0
        self._up: bool | None = None
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
        elif cmd_type == cmds.CMD_ESTOP:
            with self._cmd_lock:
                self._pending_dir = 'S'
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

    # ── worker ────────────────────────────────────────────────────────────
    def _loop(self) -> None:
        next_poll = 0.0
        while not self._stop.is_set():
            now = time.monotonic()

            with self._cmd_lock:
                d, self._pending_dir = self._pending_dir, None
            if d is not None:
                try:
                    self._session.get(f'http://{self.host}/control',
                                      params={'dir': d}, timeout=self.timeout_s)
                except requests.RequestException:
                    pass

            if now >= next_poll:
                next_poll = now + self.poll_period
                up = False
                try:
                    r = self._session.get(f'http://{self.host}/telemetry',
                                          timeout=self.timeout_s)
                    data = r.json()
                    up = True
                    self._seq += 1
                    # NOTE: the ESP32 has no odometry — its telemetry x/y are
                    # accelerometer TILT, never feed them into the pose
                    # pipeline. Pose stays at the frame origin so the operator
                    # places Gamma manually with the map's SET POSE tool.
                    self.telemetryReceived.emit(make_envelope(ch.TELE_FULL, {
                        'esp32': data,
                        'gas': data.get('g'),
                        'odom': {'x': 0.0, 'y': 0.0, 'th': 0.0, 'v': 0, 'w': 0},
                    }, seq=self._seq, run_id=self.run_id, src=self.host))
                except (requests.RequestException, ValueError):
                    pass
                if up != self._up:
                    self._up = up
                    self.linkUp.emit(up)
            time.sleep(0.05)
