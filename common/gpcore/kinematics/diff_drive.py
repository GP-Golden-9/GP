"""Dead-reckoning math extracted verbatim from navigation/robot2_odom.py.

The node keeps doing ROS I/O; the pose integration lives here so it can be
unit-tested (straight line, in-place turn, gyro/encoder blend, θ wrap)
without ROS installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple


def normalize_angle(a: float) -> float:
    """Wrap to [-π, π] exactly the way robot2_odom does."""
    return math.atan2(math.sin(a), math.cos(a))


def yaw_to_quaternion(theta: float) -> Tuple[float, float, float, float]:
    """(x, y, z, w) for a pure yaw rotation."""
    return (0.0, 0.0, math.sin(theta / 2.0), math.cos(theta / 2.0))


def quaternion_to_yaw(x: float, y: float, z: float, w: float) -> float:
    siny = 2.0 * (w * z + x * y)
    cosy = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny, cosy)


@dataclass
class DiffDriveConfig:
    wheel_diameter_m: float = 0.065
    ticks_per_rev: int = 330
    wheel_base_m: float = 0.23
    # Complementary filter: 0.0 = pure gyro, 1.0 = pure encoders
    encoder_heading_weight: float = 0.3

    @property
    def meters_per_tick(self) -> float:
        return (math.pi * self.wheel_diameter_m) / self.ticks_per_rev


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0


@dataclass
class DiffDriveOdometry:
    """Feed cumulative encoder ticks + gyro-z; get an integrated pose.

    Encoder order is [FL, RL, FR, RR] — matching the firmware's D: packet
    and robot2_bridge's /encoders message.
    """

    config: DiffDriveConfig = field(default_factory=DiffDriveConfig)
    pose: Pose = field(default_factory=Pose)
    _prev_enc: Optional[Tuple[int, int, int, int]] = None

    def reset(self) -> None:
        self.pose = Pose()
        self._prev_enc = None

    def update(self, enc: Sequence[int], gyro_z: float, dt: float) -> Pose:
        """One integration step.

        ``enc``     cumulative ticks [FL, RL, FR, RR]
        ``gyro_z``  rad/s (already scaled by the bridge)
        ``dt``      seconds since previous update (clamped like the node does)
        """
        if len(enc) < 4:
            return self.pose
        enc4 = (int(enc[0]), int(enc[1]), int(enc[2]), int(enc[3]))

        if self._prev_enc is None:
            self._prev_enc = enc4
            return self.pose

        if dt <= 0 or dt > 1.0:
            dt = 0.02  # node's fallback for nonsense clock deltas

        d_fl = enc4[0] - self._prev_enc[0]
        d_rl = enc4[1] - self._prev_enc[1]
        d_fr = enc4[2] - self._prev_enc[2]
        d_rr = enc4[3] - self._prev_enc[3]

        mpt = self.config.meters_per_tick
        d_left_m = ((d_fl + d_rl) / 2.0) * mpt
        d_right_m = ((d_fr + d_rr) / 2.0) * mpt

        distance = (d_left_m + d_right_m) / 2.0
        d_theta_enc = (d_right_m - d_left_m) / self.config.wheel_base_m
        d_theta_imu = gyro_z * dt

        w = self.config.encoder_heading_weight
        d_theta = w * d_theta_enc + (1.0 - w) * d_theta_imu

        # NOTE: matches the node exactly — heading is updated FIRST and the
        # translation is projected along the NEW heading.
        theta = normalize_angle(self.pose.theta + d_theta)
        self.pose = Pose(
            x=self.pose.x + distance * math.cos(theta),
            y=self.pose.y + distance * math.sin(theta),
            theta=theta,
        )
        self._prev_enc = enc4
        return self.pose
