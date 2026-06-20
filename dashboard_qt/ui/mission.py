"""Mission executor — walks a robot through planned waypoints.

The planner produces a safe route in the SHARED frame; the robot only has a
dumb straight-line goto. This executor closes the loop: send waypoint N,
watch the robot's aligned pose, advance when close enough, abort loudly on
timeout. Cancel on anything that changes the operator's intent (new goal,
robot switch, e-stop, mode change).
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QTimer, Signal

WP_TOLERANCE_M = 0.30          # intermediate waypoints; final = robot's own 0.12
WP_TIMEOUT_S = 25.0            # no progress to the active waypoint → abort
TICK_MS = 100                  # 10 Hz — also the heading-bias stream rate
MAX_SKIPS = 4                  # consecutive unreachable waypoints → give up
TURN_COMMIT_RAD = 1.40         # heading error past which we commit to spinning
                               # round (≈80°) — keeps a turn-around decisive

# Default goto gains (mirror config/robot2.yaml goto.*); overridden per robot
# via start(..., gains=...).
_DEFAULT_GAINS = {
    'kp_distance': 0.5, 'kp_angle': 1.2,
    'max_linear_mps': 0.15, 'max_angular_rps': 0.40,
    'angle_tolerance_rad': 0.15,
}


class MissionExecutor(QObject):
    waypointActive = Signal(int, int, float, float)   # idx, total, x, y (world)
    missionFinished = Signal(str)                     # 'arrived' | reason
    progress = Signal(str)                            # human line for the log
    biasComputed = Signal(float, float)               # vx, wz toward active wp

    def __init__(self, send_goal_world, parent=None):
        """``send_goal_world(x, y)`` — callback that transforms into the
        robot frame and transmits (main window owns the transform)."""
        super().__init__(parent)
        self._send = send_goal_world
        self.robot_id: str | None = None
        self._wps: list[tuple[float, float]] = []
        self._idx = -1
        self._wp_started = 0.0
        self._pose: tuple[float, float, float] | None = None   # x, y, th (world)
        self._gains = dict(_DEFAULT_GAINS)
        self._skip_stuck = False
        self._timeout = WP_TIMEOUT_S
        self._tol = WP_TOLERANCE_M
        self._skips = 0
        self._best_dist = float('inf')
        self._best_ang = float('inf')
        self._wp_progress_t = 0.0
        self._paused = False
        self._turn_commit = 0          # decisive turn-around direction (+1/-1/0)
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    @property
    def paused(self) -> bool:
        return self._paused

    # ── manual ASSIST: nudge the robot mid-run without aborting ────────────
    def pause(self) -> None:
        """Suspend bias streaming + the no-progress clock so the operator can
        hand-drive the robot (e.g. past a tricky spot) WITHOUT cancelling the
        run. The waypoint list/index are kept; resume() picks up from the
        robot's new pose."""
        self._paused = True

    def resume(self) -> None:
        """Re-arm the active waypoint from wherever the robot is NOW — the
        operator's nudge counts as progress, so the run doesn't instantly
        time out."""
        if not self.active or not self._paused:
            return
        self._paused = False
        now = time.monotonic()
        self._wp_started = now
        self._best_dist = float('inf')
        self._best_ang = float('inf')
        self._wp_progress_t = now

    # ── lifecycle ─────────────────────────────────────────────────────────
    def start(self, robot_id: str, waypoints: list[tuple[float, float]],
              gains: dict | None = None, *, skip_stuck: bool = False,
              wp_timeout: float = WP_TIMEOUT_S,
              tol: float = WP_TOLERANCE_M) -> None:
        """``skip_stuck`` = follow the path LOOSELY: a waypoint that can't be
        reached in ``wp_timeout`` is SKIPPED (move to the next) instead of
        aborting the whole run — so a dead-end waypoint never traps a coverage
        scan. ``tol`` widens 'close enough' so it isn't rigid about exact points.
        Gives up only after MAX_SKIPS consecutive unreachable waypoints."""
        self.cancel(silent=True)
        if not waypoints:
            return
        self.robot_id = robot_id
        self._wps = list(waypoints)
        self._idx = -1
        self._pose = None
        self._gains = {**_DEFAULT_GAINS, **(gains or {})}
        self._skip_stuck = skip_stuck
        self._timeout = wp_timeout
        self._tol = tol
        self._skips = 0
        self._paused = False
        self._timer.start()
        self.progress.emit(f'mission: {len(waypoints)} waypoint(s) → {robot_id}')
        self._advance()

    def cancel(self, reason: str = 'cancelled', silent: bool = False) -> None:
        if not self.active:
            return
        self._timer.stop()
        self._wps = []
        self._paused = False
        if not silent:
            self.missionFinished.emit(reason)
            self.progress.emit(f'mission {reason}')

    def update_pose(self, robot_id: str, x: float, y: float,
                    th: float = 0.0) -> None:
        if self.active and robot_id == self.robot_id:
            self._pose = (x, y, th)

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
        self._best_dist = float('inf')          # progress tracking (see _tick)
        self._best_ang = float('inf')
        self._turn_commit = 0
        self._wp_progress_t = self._wp_started
        self._send(x, y)
        self.waypointActive.emit(self._idx + 1, len(self._wps), x, y)

    def _tick(self) -> None:
        if self._paused:                 # operator is hand-driving — hold
            return
        if self._pose is None:
            if time.monotonic() - self._wp_started > self._timeout:
                self._timer.stop()
                self.missionFinished.emit('timeout (no odometry)')
                self.progress.emit('mission ABORTED — no odometry from robot')
            return
        x, y = self._wps[self._idx]
        px, py, pth = self._pose
        dist = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
        final = (self._idx == len(self._wps) - 1)
        tol = 0.15 if (final and not self._skip_stuck) else self._tol
        if dist <= tol:
            self._skips = 0
            self._advance()
            return
        # PROGRESS-based stuck detection. A far waypoint is fine as long as Beta
        # is still working toward it — either CLOSING DISTANCE or TURNING TO FACE
        # it. The follower is rotate-then-drive: during the turn phase vx=0 so the
        # distance doesn't shrink, but that's legitimate progress, not a stall.
        # Counting only distance falsely flagged "stuck" mid-turn under the gentle
        # autonomy gains (slow kp_angle) — so we also reset the clock while the
        # heading error to the waypoint keeps shrinking. Only when BOTH stall
        # (can't get closer AND can't turn toward it) is it genuinely blocked.
        now = time.monotonic()
        ang_err = abs(math.atan2(math.sin(math.atan2(y - py, x - px) - pth),
                                 math.cos(math.atan2(y - py, x - px) - pth)))
        if dist < self._best_dist - 0.05:        # closing in → reset the clock
            self._best_dist = dist
            self._wp_progress_t = now
        if ang_err < self._best_ang - 0.05:      # turning to face it → also progress
            self._best_ang = ang_err
            self._wp_progress_t = now
        if now - self._wp_progress_t > self._timeout:
            if self._skip_stuck:
                # flexible: don't abort — skip this waypoint and keep going,
                # unless several in a row are unreachable (genuinely trapped).
                self._skips += 1
                self.progress.emit(
                    f'waypoint {self._idx + 1} unreachable — skipping '
                    f'({self._skips}/{MAX_SKIPS}); target ({x:+.2f},{y:+.2f}) '
                    f'robot ({px:+.2f},{py:+.2f}) closest={self._best_dist:.2f}m '
                    f'tol={tol:.2f}m')
                if self._skips >= MAX_SKIPS:
                    self._timer.stop()
                    self.missionFinished.emit('stuck')
                    return
                self._advance()
                return
            self._timer.stop()
            self.missionFinished.emit('timeout')
            self.progress.emit(
                f'mission ABORTED — waypoint {self._idx + 1} not reached in '
                f'{self._timeout:.0f}s (robot stuck?)')
            return
        self._emit_bias(px, py, pth, x, y, dist)

    def _emit_bias(self, px, py, pth, gx, gy, dist) -> None:
        """Stream a heading bias toward the active waypoint (rotate-then-drive,
        same gains as the Pi goto used to run). The Pi fuses this attraction
        with ultrasonic repulsion — see robot2_local_nav.py."""
        g = self._gains
        tol = g['angle_tolerance_rad']
        ang_err = math.atan2(gy - py, gx - px) - pth
        ang_err = math.atan2(math.sin(ang_err), math.cos(ang_err))
        # Decisive TURN-AROUND: when the next waypoint is well behind, commit to
        # ONE turn direction and hold it (full rate, no driving) until roughly
        # facing the goal. Without this, a ~180° target sits near the +pi/-pi
        # wrap and tiny pose noise flips the sign, so the robot rocks / inches
        # back and forth instead of just spinning round to face it.
        if self._turn_commit == 0:
            if abs(ang_err) > TURN_COMMIT_RAD:
                self._turn_commit = 1 if ang_err > 0.0 else -1
        elif abs(ang_err) <= tol:
            self._turn_commit = 0
        max_w = g['max_angular_rps']
        if self._turn_commit != 0:
            self.biasComputed.emit(0.0, self._turn_commit * max_w)
            return
        wz = max(-max_w, min(max_w, g['kp_angle'] * ang_err))
        if abs(ang_err) > tol:
            vx = 0.0                       # face the waypoint before driving
        else:
            vx = min(g['max_linear_mps'], g['kp_distance'] * dist)
        self.biasComputed.emit(vx, wz)
