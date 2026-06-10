#!/usr/bin/env python3
"""LiDAR scan watchdog — detects a stalled RPLidar and recovers it.

Failure mode this guards (seen in the field as "LiDAR doesn't spin"):
the driver process is alive but /scan stops, or never starts, because the
motor stalled or the USB link wedged.

Escalation ladder, with grace between rungs:
  1. call /stop_motor then /start_motor (std_srvs/Empty on rplidar driver)
  2. pkill the rplidar driver process — the launch respawn / systemd
     restart brings it back with a fresh USB handle

Every action is logged and announced on /robot_log so it shows in the
dashboard incident feed.
"""

from __future__ import annotations

import subprocess
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from std_srvs.srv import Empty


class ScanWatchdog(Node):
    def __init__(self):
        super().__init__('scan_watchdog')
        self.declare_parameter('min_scan_hz', 3.0)
        self.declare_parameter('stall_grace_s', 8.0)
        # Field incident 2026-06-11: without a startup grace the watchdog
        # measured "0 Hz" one second after arming (DDS discovery of /scan
        # still in progress), stopped a perfectly healthy motor, then
        # escalated to pkill on the same 5 s cadence — faster than the
        # driver's ~5 s respawn-to-scanning time — and kill-looped forever.
        self.declare_parameter('startup_grace_s', 20.0)
        self.declare_parameter('kill_grace_s', 20.0)   # driver respawn + init
        self.declare_parameter('allow_kill', True)

        self._stamps: list[float] = []
        self._armed_at = time.monotonic()
        self._last_action = time.monotonic()
        self._escalation = 0          # 0 = healthy, 1 = motor kicked, 2 = killed
        self._start_timer = None

        self.create_subscription(LaserScan, '/scan', self._scan_cb, 10)
        self.log_pub = self.create_publisher(String, '/robot_log', 10)
        self.stop_cli = self.create_client(Empty, '/stop_motor')
        self.start_cli = self.create_client(Empty, '/start_motor')
        self.create_timer(1.0, self._check)
        self.get_logger().info('scan watchdog armed')

    def _scan_cb(self, _msg):
        now = time.monotonic()
        self._stamps.append(now)
        self._stamps = [t for t in self._stamps if now - t <= 2.0]
        if self._escalation and len(self._stamps) >= 4:
            self._announce('LIDAR: recovered, scans flowing again')
            self._escalation = 0

    def _rate_hz(self) -> float:
        return len(self._stamps) / 2.0

    def _check(self):
        min_hz = self.get_parameter('min_scan_hz').value
        now = time.monotonic()

        # let the driver finish booting and DDS finish discovering /scan
        if now - self._armed_at < self.get_parameter('startup_grace_s').value:
            return
        if self._rate_hz() >= min_hz:
            return
        # after a driver kill, the respawned process needs respawn_delay +
        # init time before scans can possibly flow — wait longer than that
        grace = (self.get_parameter('kill_grace_s').value
                 if self._escalation >= 2
                 else self.get_parameter('stall_grace_s').value)
        if now - self._last_action < grace:
            return
        self._last_action = now

        if self._escalation == 0:
            self._announce(f'LIDAR: scan rate {self._rate_hz():.1f} Hz < {min_hz} Hz '
                           '— cycling motor')
            self._kick_motor()
            self._escalation = 1
        elif self.get_parameter('allow_kill').value:
            self._announce('LIDAR: motor cycle did not help — restarting driver')
            self._kill_driver()
            self._escalation = 2
        else:
            self._announce('LIDAR: still stalled (driver restart disabled)')

    def _kick_motor(self):
        # NEVER time.sleep() here: blocking our executor stalls our own
        # /scan subscription, which made the post-kick rate read low and
        # triggered a bogus escalation.
        if self.stop_cli.service_is_ready():
            self.stop_cli.call_async(Empty.Request())
        else:
            self.get_logger().warn('/stop_motor service not available')

        def _restart_motor():
            self._start_timer.cancel()
            if self.start_cli.service_is_ready():
                self.start_cli.call_async(Empty.Request())
            else:
                self.get_logger().warn('/start_motor service not available')

        if self._start_timer is not None:
            self._start_timer.cancel()
        self._start_timer = self.create_timer(1.5, _restart_motor)

    def _kill_driver(self):
        try:
            subprocess.run(['pkill', '-f', 'rplidar'], timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.get_logger().error(f'pkill failed: {exc}')

    def _announce(self, line: str):
        self.get_logger().warn(line)
        self.log_pub.publish(String(data=line))


def main(args=None):
    rclpy.init(args=args)
    node = ScanWatchdog()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
