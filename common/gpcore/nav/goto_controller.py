"""Rotate-then-drive goal controller — pure logic twin of robot2_goto.py.

``step()`` is a pure function of (pose, goal): no clocks, no ROS, fully
unit-testable. The node remains responsible for I/O and timer cadence.

⚠️  Same caveat as the node: NO obstacle avoidance. Robot 2 has no LiDAR.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass


class GotoState(str, enum.Enum):
    IDLE = 'IDLE'
    ROTATING = 'ROTATING'
    DRIVING = 'DRIVING'
    ARRIVED = 'ARRIVED'


@dataclass
class GotoConfig:
    goal_tolerance_m: float = 0.12
    angle_tolerance_rad: float = 0.15
    max_linear_mps: float = 0.15
    max_angular_rps: float = 0.40
    kp_distance: float = 0.5
    kp_angle: float = 1.2


@dataclass(frozen=True)
class GotoCommand:
    linear: float
    angular: float
    state: GotoState
    status: str          # exact /nav_status wire string


def _wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


class GotoController:
    def __init__(self, config: GotoConfig | None = None):
        self.cfg = config or GotoConfig()
        self.goal_x: float | None = None
        self.goal_y: float | None = None
        self.state = GotoState.IDLE

    @property
    def has_goal(self) -> bool:
        return self.goal_x is not None

    def set_goal(self, x: float, y: float) -> None:
        self.goal_x, self.goal_y = x, y
        self.state = GotoState.ROTATING

    def cancel(self) -> GotoCommand:
        self.goal_x = self.goal_y = None
        self.state = GotoState.IDLE
        return GotoCommand(0.0, 0.0, GotoState.IDLE, 'IDLE')

    def step(self, x: float, y: float, theta: float) -> GotoCommand:
        """One control tick. Mirrors robot2_goto._navigate() decisions 1:1."""
        if not self.has_goal:
            return GotoCommand(0.0, 0.0, self.state, 'IDLE')

        dx = self.goal_x - x
        dy = self.goal_y - y
        distance = math.hypot(dx, dy)
        angle_error = _wrap(math.atan2(dy, dx) - theta)
        c = self.cfg

        if distance < c.goal_tolerance_m:
            status = f'ARRIVED:{self.goal_x:.2f},{self.goal_y:.2f}'
            self.state = GotoState.ARRIVED
            self.goal_x = self.goal_y = None
            return GotoCommand(0.0, 0.0, GotoState.ARRIVED, status)

        if abs(angle_error) > c.angle_tolerance_rad:
            self.state = GotoState.ROTATING
            wz = max(-c.max_angular_rps,
                     min(c.max_angular_rps, c.kp_angle * angle_error))
            return GotoCommand(
                0.0, wz, GotoState.ROTATING,
                f'ROTATING:{self.goal_x:.2f},{self.goal_y:.2f}')

        self.state = GotoState.DRIVING
        linear = min(c.max_linear_mps, c.kp_distance * distance)
        half = c.max_angular_rps * 0.5
        angular = max(-half, min(half, c.kp_angle * 0.5 * angle_error))
        return GotoCommand(linear, angular, GotoState.DRIVING,
                           f'DRIVING:{distance:.2f}m')
