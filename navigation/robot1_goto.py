#!/usr/bin/env python3
"""Robot 1 — GoTo navigator with LiDAR collision guard.

Point-to-point controller for the mapper. Unlike robot2's (odometry-only,
no sensor), this one navigates in the MAP frame and refuses to hit things:

  pose    map->base_link TF (slam, drift-corrected) — goals from the
          dashboard arrive in this same frame (robot1 IS the shared frame)
  safety  every /scan is checked against the measured footprint
          (config/robot1.yaml `footprint`/`goto`):
            DRIVING   obstacle inside the forward corridor -> hard stop,
                      resume only when clear past a hysteresis band
            ROTATING  anything inside the rotation circle (the 30 cm rear
                      overhang sweeps 0.34 m!) -> rotation blocked
          blocked longer than `blocked_abort_s` -> goal aborted loudly

Subscribes: /goal_pose /scan /manual_cmd /emergency_stop /explore_enable
Publishes:  /cmd_vel /nav_status

The dashboard's A* mission feeds one waypoint at a time; nav_status uses
the same vocabulary as robot2_goto (IDLE/ROTATING/DRIVING/ARRIVED) plus
BLOCKED:<why> so the operator sees exactly what the guard is doing.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))
from gpcore.config import get_path, load_config          # noqa: E402

ANGLE_TOLERANCE = 0.15        # rad — aligned enough to drive
KP_ANGLE = 1.2
KP_DISTANCE = 0.5
CONTROL_HZ = 20.0

# Self-occlusion learning. Field data 2026-06-11 (tools scan probe): a
# fixture protrudes 0.21-0.24 m at the front-left — present in EVERY scan
# at a constant body-frame position. Anything persistently closer than
# SELF_RADIUS_BOUND is bolted to the robot, and the lidar can never see
# past it anyway, so those beams are masked instead of hand-tuning the
# footprint rectangle forever.
SELF_LEARN_SCANS = 15          # ~2 s at boot
SELF_RADIUS_BOUND = 0.32       # attached fixtures only; walls are farther
SELF_SLACK_M = 0.05            # masked beam ignores returns near profile
SELF_UNMASK_DELTA = 0.20       # return moved this far past profile…
SELF_UNMASK_SCANS = 20         # …this many scans → it was environment

STATE_IDLE = 'IDLE'
STATE_ROTATING = 'ROTATING'
STATE_DRIVING = 'DRIVING'
STATE_ARRIVED = 'ARRIVED'
STATE_BLOCKED = 'BLOCKED'


class Robot1GoTo(Node):
    def __init__(self, cfg: dict):
        super().__init__('robot1_goto')

        self.max_lin = get_path(cfg, 'goto.max_linear_mps', 0.15)
        self.max_ang = get_path(cfg, 'goto.max_angular_rps', 0.40)
        self.goal_tol = get_path(cfg, 'goto.goal_tolerance_m', 0.12)
        self.stop_ahead = get_path(cfg, 'goto.stop_ahead_m', 0.35)
        self.resume_ahead = get_path(cfg, 'goto.resume_ahead_m', 0.45)
        self.corridor_half = get_path(cfg, 'goto.corridor_half_m', 0.21)
        self.rotate_clear = get_path(cfg, 'goto.rotate_clear_m', 0.38)
        self.blocked_abort_s = get_path(cfg, 'goto.blocked_abort_s', 6.0)
        self.laser_yaw = get_path(cfg, 'footprint.laser_yaw_rad', 0.0)
        self.fwd_extent = get_path(cfg, 'footprint.forward_extent_m', 0.10)
        self.rear_extent = get_path(cfg, 'footprint.rear_extent_m', 0.30)
        self.half_width = get_path(cfg, 'footprint.half_width_m', 0.15)

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.create_subscription(PoseStamped, '/goal_pose', self._goal_cb, 10)
        self.create_subscription(LaserScan, '/scan', self._scan_cb, 5)
        self.create_subscription(Twist, '/manual_cmd', self._manual_cb, 10)
        self.create_subscription(Bool, '/emergency_stop', self._estop_cb, 10)
        self.create_subscription(Bool, '/explore_enable', self._explore_cb, 5)

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/nav_status', 10)
        self.log_pub = self.create_publisher(String, '/robot_log', 10)

        self.goal = None              # (x, y) in map frame
        self.estop = False
        self.exploring = False
        self.state = STATE_IDLE
        self._front_blocked = False   # with hysteresis
        self._rear_blocked = False
        self._rot_blocked = False
        self._blocked_since = None
        self._last_status = ''
        self._learn_left = SELF_LEARN_SCANS
        self._profile = None          # per-beam min range while learning
        self._self_mask = None        # bool per beam: attached fixture
        self._unmask_count = None

        self.create_timer(1.0 / CONTROL_HZ, self._navigate)
        self._status(STATE_IDLE)
        self.get_logger().info(
            f'robot1 goto up — stop_ahead={self.stop_ahead} '
            f'corridor=±{self.corridor_half} rotate_clear={self.rotate_clear}')

    # ── pose ─────────────────────────────────────────────────────────────
    def _pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link',
                                                rclpy.time.Time())
        except TransformException:
            return None
        q = t.transform.rotation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return (t.transform.translation.x, t.transform.translation.y,
                math.atan2(siny, cosy))

    # ── callbacks ────────────────────────────────────────────────────────
    def _goal_cb(self, msg: PoseStamped):
        if self.estop:
            return
        self.goal = (msg.pose.position.x, msg.pose.position.y)
        self._blocked_since = None
        self.state = STATE_ROTATING
        self.get_logger().info(f'goal ({self.goal[0]:.2f}, {self.goal[1]:.2f})')

    def _scan_cb(self, msg: LaserScan):
        """Project every return into the BASE frame and test the footprint
        corridors. Runs at scan rate (~7 Hz) — cheap numpy, no copies."""
        n = len(msg.ranges)
        if n == 0:
            return
        r = np.asarray(msg.ranges, dtype=np.float32)

        # ── learn / apply the self-occlusion mask ──
        if self._profile is None or len(self._profile) != n:
            self._profile = np.full(n, np.inf, dtype=np.float32)
            self._learn_left = SELF_LEARN_SCANS
            self._self_mask = None
        finite = np.where(np.isfinite(r) & (r > msg.range_min), r, np.inf)
        if self._learn_left > 0:
            np.minimum(self._profile, finite, out=self._profile)
            self._learn_left -= 1
            if self._learn_left == 0:
                self._self_mask = self._profile < SELF_RADIUS_BOUND
                self._unmask_count = np.zeros(n, dtype=np.int32)
                self.get_logger().info(
                    f'self-occlusion mask: {int(self._self_mask.sum())} '
                    f'beams (attached fixtures < {SELF_RADIUS_BOUND} m)')
            return                       # guard arms after learning

        masked = self._self_mask
        # a masked beam whose return moved well past the learned distance
        # was environment after all (robot drove away from it) → unmask
        moved = masked & (finite > self._profile + SELF_UNMASK_DELTA)
        self._unmask_count[moved] += 1
        self._unmask_count[masked & ~moved] = 0
        release = self._unmask_count >= SELF_UNMASK_SCANS
        if release.any():
            self._self_mask = masked = masked & ~release
            self._unmask_count[release] = 0

        ang = (msg.angle_min + self.laser_yaw
               + np.arange(n, dtype=np.float32) * msg.angle_increment)
        valid = np.isfinite(r) & (r > max(0.05, msg.range_min)) & (r < 8.0)
        valid &= ~(masked & (r < self._profile + SELF_SLACK_M))
        x = r[valid] * np.cos(ang[valid])      # +x = robot forward
        y = r[valid] * np.sin(ang[valid])

        # belt-and-braces: returns inside the body envelope are never
        # obstacles either (chassis itself)
        self_hit = ((x > -(self.rear_extent + 0.03))
                    & (x < self.fwd_extent + 0.03)
                    & (np.abs(y) < self.half_width + 0.03))
        x, y = x[~self_hit], y[~self_hit]

        in_corridor = (np.abs(y) < self.corridor_half) & (x > 0.0)
        ahead = x[in_corridor]
        nearest = float(ahead.min()) if ahead.size else 99.0
        if self._front_blocked:
            self._front_blocked = nearest < self.resume_ahead   # hysteresis
        else:
            self._front_blocked = nearest < self.stop_ahead

        # reverse corridor: distance from the REAR EDGE to the nearest
        # return behind (body extends rear_extent behind base_link)
        in_back = (np.abs(y) < self.corridor_half) & (x < 0.0)
        behind = -x[in_back] - self.rear_extent
        nearest_b = float(behind.min()) if behind.size else 99.0
        if self._rear_blocked:
            self._rear_blocked = nearest_b < 0.25
        else:
            self._rear_blocked = nearest_b < 0.15

        # Rotation sweep, by actual geometry — NOT a naive full circle:
        #   * the front corners only reach hypot(0.10, 0.15) = 0.18 m, so
        #     anything in the front half-plane beyond 0.21 m can never be
        #     touched by rotating (a wall ahead must not veto rotation);
        #   * the REAR corners sweep 0.335 m — points in the rear half
        #     inside rotate_clear genuinely block.
        d = np.hypot(x, y)
        near_any = d < (self.corridor_half)           # grazes the body side
        rear_swing = (x < 0.05) & (d < self.rotate_clear)
        self._rot_blocked = bool(near_any.any() or rear_swing.any())

        # remember the closest return for actionable BLOCKED logs
        if d.size:
            i = int(np.argmin(d))
            self._nearest = (float(x[i]), float(y[i]), float(d[i]))
        else:
            self._nearest = None

    def _manual_cb(self, _msg: Twist):
        if self.goal is not None:
            self._cancel('manual override')

    def _estop_cb(self, msg: Bool):
        self.estop = bool(msg.data)
        if self.estop and self.goal is not None:
            self._cancel('e-stop')

    def _explore_cb(self, msg: Bool):
        self.exploring = bool(msg.data)
        if self.exploring and self.goal is not None:
            self._cancel('explorer enabled')

    # ── control loop ─────────────────────────────────────────────────────
    def _navigate(self):
        if self.goal is None or self.estop or self.exploring:
            return
        pose = self._pose()
        if pose is None:
            self._status('IDLE')      # no TF yet — slam still starting
            return
        px, py, pth = pose
        dx, dy = self.goal[0] - px, self.goal[1] - py
        distance = math.hypot(dx, dy)

        if distance < self.goal_tol:
            self._stop()
            self.state = STATE_ARRIVED
            self._status(f'ARRIVED:{self.goal[0]:.2f},{self.goal[1]:.2f}')
            self.get_logger().info('arrived')
            self.goal = None
            return

        angle_err = math.atan2(dy, dx) - pth
        angle_err = math.atan2(math.sin(angle_err), math.cos(angle_err))
        rotating = abs(angle_err) > ANGLE_TOLERANCE

        # ── collision guard + tight-space maneuvers ──
        # In a corridor narrower than the pivot circle the robot must NOT
        # spin in place (rear corner sweeps 0.335 m). Instead:
        #   goal mostly BEHIND  → REVERSE toward it (lidar covers 360°,
        #                          the rear corridor is guarded too)
        #   goal to a side      → ARC TURN: creep forward while turning;
        #                          the rear tracks inside the front path
        goal_behind = abs(angle_err) > 2.6        # within ~31° of dead aft
        if rotating and self._rot_blocked:
            cmd = Twist()
            if goal_behind and not self._rear_blocked:
                self._blocked_since = None
                self.state = STATE_DRIVING
                back_err = math.atan2(math.sin(angle_err - math.pi),
                                      math.cos(angle_err - math.pi))
                cmd.linear.x = -min(self.max_lin, KP_DISTANCE * distance)
                cmd.angular.z = max(-self.max_ang * 0.5,
                                    min(self.max_ang * 0.5,
                                        KP_ANGLE * 0.5 * back_err))
                self.cmd_pub.publish(cmd)
                self._status(f'REVERSING:{distance:.2f}m')
                return
            if not goal_behind and not self._front_blocked:
                self._blocked_since = None
                self.state = STATE_ROTATING
                cmd.linear.x = 0.06
                cmd.angular.z = max(-self.max_ang * 0.8,
                                    min(self.max_ang * 0.8,
                                        KP_ANGLE * angle_err))
                self.cmd_pub.publish(cmd)
                self._status(f'ROTATING:{self.goal[0]:.2f},{self.goal[1]:.2f}')
                return

        blocked_reason = None
        if rotating and self._rot_blocked:
            blocked_reason = 'ROTATE'
        elif not rotating and self._front_blocked:
            blocked_reason = 'AHEAD'

        if blocked_reason:
            self._stop()
            now = self.get_clock().now().nanoseconds / 1e9
            if self._blocked_since is None:
                self._blocked_since = now
                near = getattr(self, '_nearest', None)
                where = (f' nearest x={near[0]:+.2f} y={near[1]:+.2f} '
                         f'd={near[2]:.2f}m' if near else '')
                self._announce(f'GOTO: path blocked ({blocked_reason}) — '
                               f'holding{where}')
            elif now - self._blocked_since > self.blocked_abort_s:
                self._announce('GOTO: blocked too long — goal aborted')
                self._cancel('blocked')
                return
            self.state = STATE_BLOCKED
            self._status(f'BLOCKED:{blocked_reason}')
            return
        if self._blocked_since is not None:
            self._announce('GOTO: path clear — resuming')
            self._blocked_since = None

        cmd = Twist()
        if rotating:
            self.state = STATE_ROTATING
            cmd.angular.z = max(-self.max_ang,
                                min(self.max_ang, KP_ANGLE * angle_err))
            self._status(f'ROTATING:{self.goal[0]:.2f},{self.goal[1]:.2f}')
        else:
            self.state = STATE_DRIVING
            cmd.linear.x = min(self.max_lin, KP_DISTANCE * distance)
            cmd.angular.z = max(-self.max_ang * 0.5,
                                min(self.max_ang * 0.5,
                                    KP_ANGLE * 0.5 * angle_err))
            self._status(f'DRIVING:{distance:.2f}m')
        self.cmd_pub.publish(cmd)

    # ── helpers ──────────────────────────────────────────────────────────
    def _stop(self):
        self.cmd_pub.publish(Twist())

    def _cancel(self, why: str):
        self.goal = None
        self.state = STATE_IDLE
        self._blocked_since = None
        self._stop()
        self._status(STATE_IDLE)
        self.get_logger().info(f'goal cancelled: {why}')

    def _status(self, text: str):
        if text != self._last_status:
            self._last_status = text
            self.status_pub.publish(String(data=text))

    def _announce(self, line: str):
        self.get_logger().warn(line)
        self.log_pub.publish(String(data=line))


def main(args=None):
    import argparse
    ap = argparse.ArgumentParser()
    default_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               '..', 'config', 'robot1.yaml')
    ap.add_argument('--config', default=default_cfg)
    parsed, ros_args = ap.parse_known_args(args=args)
    cfg = load_config(parsed.config)

    rclpy.init(args=ros_args)
    node = Robot1GoTo(cfg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
