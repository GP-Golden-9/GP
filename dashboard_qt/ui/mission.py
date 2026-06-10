"""Mission executor — walks a robot through planned waypoints.

The planner produces a safe route in the SHARED frame; the robot only has a
dumb straight-line goto. This executor closes the loop: send waypoint N,
watch the robot's aligned pose, advance when close enough, abort loudly on
timeout. Cancel on anything that changes the operator's intent (new goal,
robot switch, e-stop, mode change).
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, QTimer, Signal

WP_TOLERANCE_M = 0.30          # intermediate waypoints; final = robot's own 0.12
WP_TIMEOUT_S = 25.0            # no progress to the active waypoint → abort
TICK_MS = 200


class MissionExecutor(QObject):
    waypointActive = Signal(int, int, float, float)   # idx, total, x, y (world)
    missionFinished = Signal(str)                     # 'arrived' | reason
    progress = Signal(str)                            # human line for the log

    def __init__(self, send_goal_world, parent=None):
        """``send_goal_world(x, y)`` — callback that transforms into the
        robot frame and transmits (main window owns the transform)."""
        super().__init__(parent)
        self._send = send_goal_world
        self.robot_id: str | None = None
        self._wps: list[tuple[float, float]] = []
        self._idx = -1
        self._wp_started = 0.0
        self._pose: tuple[float, float] | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self, robot_id: str, waypoints: list[tuple[float, float]]) -> None:
        self.cancel(silent=True)
        if not waypoints:
            return
        self.robot_id = robot_id
        self._wps = list(waypoints)
        self._idx = -1
        self._pose = None
        self._timer.start()
        self.progress.emit(f'mission: {len(waypoints)} waypoint(s) → {robot_id}')
        self._advance()

    def cancel(self, reason: str = 'cancelled', silent: bool = False) -> None:
        if not self.active:
            return
        self._timer.stop()
        self._wps = []
        if not silent:
            self.missionFinished.emit(reason)
            self.progress.emit(f'mission {reason}')

    def update_pose(self, robot_id: str, x: float, y: float) -> None:
        if self.active and robot_id == self.robot_id:
            self._pose = (x, y)

    def remaining(self) -> list[tuple[float, float]]:
        return self._wps[self._idx:] if self.active and self._idx >= 0 else []

    # ── internals ─────────────────────────────────────────────────────────
    def _advance(self) -> None:
        self._idx += 1
        if self._idx >= len(self._wps):
            self._timer.stop()
            self.missionFinished.emit('arrived')
            self.progress.emit('mission complete — arrived')
            return
        x, y = self._wps[self._idx]
        self._wp_started = time.monotonic()
        self._send(x, y)
        self.waypointActive.emit(self._idx + 1, len(self._wps), x, y)

    def _tick(self) -> None:
        if self._pose is None:
            if time.monotonic() - self._wp_started > WP_TIMEOUT_S:
                self._timer.stop()
                self.missionFinished.emit('timeout (no odometry)')
                self.progress.emit('mission ABORTED — no odometry from robot')
            return
        x, y = self._wps[self._idx]
        px, py = self._pose
        dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
        final = (self._idx == len(self._wps) - 1)
        tol = 0.15 if final else WP_TOLERANCE_M
        if dist <= tol:
            self._advance()
        elif time.monotonic() - self._wp_started > WP_TIMEOUT_S:
            self._timer.stop()
            self.missionFinished.emit('timeout')
            self.progress.emit(
                f'mission ABORTED — waypoint {self._idx + 1} not reached in '
                f'{WP_TIMEOUT_S:.0f}s (robot stuck?)')
