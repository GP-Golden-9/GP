#!/usr/bin/env python3
"""
Robot 2 — Dead-Reckoning Odometry Node
=======================================
Fuses encoder ticks + IMU gyroscope to compute (x, y, θ) position.
Publishes nav_msgs/Odometry on /odom at 50 Hz.

Subscribes:
  /encoders      (std_msgs/Int32MultiArray)  — cumulative encoder ticks
  /imu/data_raw  (sensor_msgs/Imu)           — raw IMU readings

Publishes:
  /odom          (nav_msgs/Odometry)          — robot pose in map frame

Kinematics come from config/robot2.yaml `drive:` (single source of truth —
measured 2026-06-11: 85 mm wheels, 0.225 m track). The constants below are
only the last-resort fallback if the config cannot be read.
"""

import math
import os
import sys

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Int32MultiArray
from sensor_msgs.msg import Imu
from geometry_msgs.msg import TransformStamped
import tf2_ros

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))
from gpcore.config import get_path, load_config          # noqa: E402

_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'config', 'robot2.yaml')

# Fallbacks only — real values live in config/robot2.yaml
WHEEL_DIAMETER = 0.085
TICKS_PER_REV = 330
WHEEL_BASE = 0.225
ENCODER_HEADING_WEIGHT = 0.3

try:
    _cfg = load_config(_CFG_PATH)
    WHEEL_DIAMETER = float(get_path(_cfg, 'drive.wheel_diameter_m',
                                    WHEEL_DIAMETER))
    TICKS_PER_REV = int(get_path(_cfg, 'drive.ticks_per_rev', TICKS_PER_REV))
    WHEEL_BASE = float(get_path(_cfg, 'drive.wheel_base_m', WHEEL_BASE))
    ENCODER_HEADING_WEIGHT = float(get_path(
        _cfg, 'drive.encoder_heading_weight', ENCODER_HEADING_WEIGHT))
except Exception:                       # config unreadable → fallbacks
    pass

METERS_PER_TICK = (math.pi * WHEEL_DIAMETER) / TICKS_PER_REV


class Robot2Odom(Node):
    def __init__(self):
        super().__init__('robot2_odom')

        # ── Subscriptions ──
        self.create_subscription(
            Int32MultiArray, '/encoders', self._enc_cb, 10)
        self.create_subscription(
            Imu, '/imu/data_raw', self._imu_cb, 10)

        # ── Publisher ──
        self.odom_pub = self.create_publisher(Odometry, '/odom', 50)

        # ── TF Broadcaster ──
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # ── State ──
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0

        # Encoder tracking
        self.prev_enc = None          # [FL, RL, FR, RR] — previous tick values
        self.last_enc_time = None

        # IMU tracking. A dead/disconnected MPU6050 still produces
        # /imu/data_raw messages — the firmware sends raw ZEROS — so
        # staleness alone can't detect it. A live MPU has a noise floor
        # (raw values always jitter); only a dead chip reads EXACTLY zero
        # on all six axes. After a streak of all-zero messages we fall
        # back to pure encoder heading instead of blending in 70% of
        # nothing (which made every turn register at 30%).
        self.gyro_z = 0.0             # Latest gyro reading (rad/s)
        self._imu_zero_streak = 0
        self._imu_dead = False

        # Timer for publishing at 50 Hz
        self.create_timer(0.02, self._publish_odom)

        self.get_logger().info('═══════════════════════════════════════')
        self.get_logger().info('  Robot 2 Odometry Node Started')
        self.get_logger().info(f'  Wheel ∅ = {WHEEL_DIAMETER*100:.1f} cm')
        self.get_logger().info(f'  Ticks/Rev = {TICKS_PER_REV}')
        self.get_logger().info(f'  Wheel Base = {WHEEL_BASE*100:.1f} cm')
        self.get_logger().info(f'  m/tick = {METERS_PER_TICK:.6f}')
        self.get_logger().info('═══════════════════════════════════════')

    def _imu_cb(self, msg: Imu):
        """Store latest gyroscope Z reading (already in rad/s from bridge)."""
        self.gyro_z = msg.angular_velocity.z
        vals = (msg.angular_velocity.x, msg.angular_velocity.y,
                msg.angular_velocity.z, msg.linear_acceleration.x,
                msg.linear_acceleration.y, msg.linear_acceleration.z)
        if all(abs(v) < 1e-9 for v in vals):
            self._imu_zero_streak = min(self._imu_zero_streak + 1, 1000)
        else:
            self._imu_zero_streak = 0
        dead = self._imu_zero_streak >= 25       # ~1 s of exact zeros
        if dead != self._imu_dead:
            self._imu_dead = dead
            if dead:
                self.get_logger().warn(
                    'IMU reads all-zero (chip dead or unwired) — '
                    'heading from ENCODERS ONLY until it recovers')
            else:
                self.get_logger().info('IMU alive — gyro blending restored')

    def _enc_cb(self, msg: Int32MultiArray):
        """Process encoder data: [Front-Left, Rear-Left, Front-Right, Rear-Right]."""
        if len(msg.data) < 4:
            return

        enc = list(msg.data)  # [FL, RL, FR, RR]
        now = self.get_clock().now()

        if self.prev_enc is None:
            # First reading — initialize, no motion yet
            self.prev_enc = enc
            self.last_enc_time = now
            return

        # ── Compute deltas ──
        d_fl = enc[0] - self.prev_enc[0]
        d_rl = enc[1] - self.prev_enc[1]
        d_fr = enc[2] - self.prev_enc[2]
        d_rr = enc[3] - self.prev_enc[3]

        # Average left and right sides
        d_left  = (d_fl + d_rl) / 2.0
        d_right = (d_fr + d_rr) / 2.0

        # Convert ticks → meters
        d_left_m  = d_left  * METERS_PER_TICK
        d_right_m = d_right * METERS_PER_TICK

        # ── Dead-reckoning ──
        distance = (d_left_m + d_right_m) / 2.0
        d_theta_enc = (d_right_m - d_left_m) / WHEEL_BASE

        # Time delta for IMU integration
        dt_ns = (now - self.last_enc_time).nanoseconds
        dt = dt_ns / 1e9
        if dt <= 0 or dt > 1.0:
            dt = 0.02  # fallback

        # ── Complementary filter: blend encoder heading with IMU gyro ──
        # (pure encoders while the IMU is dead — see _imu_cb)
        if self._imu_dead:
            d_theta = d_theta_enc
        else:
            d_theta_imu = self.gyro_z * dt
            d_theta = (ENCODER_HEADING_WEIGHT * d_theta_enc +
                       (1.0 - ENCODER_HEADING_WEIGHT) * d_theta_imu)

        # ── Update pose ──
        self.theta += d_theta
        # Normalize theta to [-π, π]
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

        self.x += distance * math.cos(self.theta)
        self.y += distance * math.sin(self.theta)

        # Save for next iteration
        self.prev_enc = enc
        self.last_enc_time = now

    def _publish_odom(self):
        """Publish odometry message and TF transform at 50 Hz."""
        now = self.get_clock().now().to_msg()

        # ── Odometry message ──
        odom = Odometry()
        odom.header.stamp = now
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0

        # Quaternion from yaw
        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = math.sin(self.theta / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.theta / 2.0)

        self.odom_pub.publish(odom)

        # ── TF: odom → base_link ──
        t = TransformStamped()
        t.header.stamp = now
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation = odom.pose.pose.orientation
        self.tf_broadcaster.sendTransform(t)


def main(args=None):
    rclpy.init(args=args)
    node = Robot2Odom()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
