#!/usr/bin/env python3
"""
Robot 2 (Beta) — Reactive autonomous wander/avoid using the TWO FRONT
ultrasonics (front-left + front-right). Beta has no lidar, so these two
HC-SR04s are its only obstacle sense.

Enabled by /explore_enable (the dashboard's AUTONOMOUS button → CMD_EXPLORE),
publishes /cmd_vel, and honors /emergency_stop. The bridge's own forward
ultrasonic guard still back-stops this node, so it's safe by construction.

Behavior:
  both sides clear        → drive forward
  a side in the slow band → creep forward, steering gently away from it
  a side closer than STOP → pivot away from it (turn persists, anti-oscillation)
  BOTH closer than STOP   → reverse briefly, then pivot toward the more open side

Turn direction (ROS convention): angular.z > 0 = turn LEFT (CCW). If the robot
turns the wrong way on the bench, flip the sign of TURN_SPEED.
"""

import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Range
from std_msgs.msg import Bool

# Distance bands (metres) — mirror config/robot2.yaml ultrasonic.*
STOP_M = 0.25       # obstacle this close → turn / reverse
CLEAR_M = 0.40      # (kept for reference; "clear" = above SLOW_M here)
SLOW_M = 0.60       # below this → creep forward + steer away
MAXRANGE_M = 1.50   # firmware echo cap → "nothing in range"

# Motion
FWD_SPEED = 0.12    # m/s forward (open space)
SLOW_SPEED = 0.07   # m/s in the slow band
TURN_SPEED = 0.40   # rad/s pivot
REV_SPEED = 0.10    # m/s reverse when boxed in
TURN_LOCK_S = 1.0   # hold a chosen turn this long (anti-oscillation)
REV_TIME_S = 0.6    # reverse this long when both sides are blocked


class Robot2Autonomous(Node):
    def __init__(self):
        super().__init__('robot2_autonomous')
        self.enabled = False
        self.estop = False
        self.left = MAXRANGE_M
        self.right = MAXRANGE_M
        self.turn_dir = 0           # -1 = right, +1 = left, 0 = none
        self.turn_until = 0.0
        self.rev_until = 0.0
        self._dbg = 0

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Range, '/ultrasonic/left', self._left_cb, 10)
        self.create_subscription(Range, '/ultrasonic/right', self._right_cb, 10)
        self.create_subscription(Bool, '/explore_enable', self._enable_cb, 10)
        self.create_subscription(Bool, '/emergency_stop', self._estop_cb, 10)
        self.create_timer(0.1, self._navigate)      # 10 Hz
        self.get_logger().info('Robot2 autonomous (ultrasonic avoid) ready — '
                               'waiting for /explore_enable')

    # ── inputs ──────────────────────────────────────────────────────────────
    def _left_cb(self, m: Range):
        self.left = m.range if m.range > 0.0 else MAXRANGE_M

    def _right_cb(self, m: Range):
        self.right = m.range if m.range > 0.0 else MAXRANGE_M

    def _estop_cb(self, m: Bool):
        self.estop = bool(m.data)
        if self.estop:
            self._stop()

    def _enable_cb(self, m: Bool):
        self.enabled = bool(m.data)
        self.get_logger().info('AUTONOMOUS ' +
                               ('ENABLED' if self.enabled else 'DISABLED'))
        if not self.enabled:
            self._stop()
            self.turn_dir = 0
            self.turn_until = 0.0
            self.rev_until = 0.0

    # ── output ──────────────────────────────────────────────────────────────
    def _stop(self):
        self.cmd_pub.publish(Twist())

    def _move(self, lin: float, ang: float):
        t = Twist()
        t.linear.x = float(lin)
        t.angular.z = float(ang)
        self.cmd_pub.publish(t)

    # ── control loop ────────────────────────────────────────────────────────
    def _navigate(self):
        if not self.enabled or self.estop:
            return
        now = time.time()
        left, right = self.left, self.right
        nearest = min(left, right)

        self._dbg += 1
        if self._dbg % 20 == 0:
            self.get_logger().info(
                f'L={left:.2f} R={right:.2f} turn={self.turn_dir}')

        # 1. backing out of a corner
        if now < self.rev_until:
            self._move(-REV_SPEED, 0.0)
            return

        # 2. both sides blocked → reverse, then commit to the more open side
        if left < STOP_M and right < STOP_M:
            self.turn_dir = 1 if left > right else -1     # toward more space
            self.rev_until = now + REV_TIME_S
            self.turn_until = now + REV_TIME_S + TURN_LOCK_S
            self._move(-REV_SPEED, 0.0)
            return

        # 3. one side too close → pivot away (latch the direction)
        if nearest < STOP_M:
            if now > self.turn_until:
                self.turn_dir = -1 if left < right else 1  # away from nearer
                self.turn_until = now + TURN_LOCK_S
            self._move(0.0, self.turn_dir * TURN_SPEED)
            return

        # 4. finish an active pivot lock (anti-oscillation)
        if now < self.turn_until and self.turn_dir != 0:
            self._move(0.0, self.turn_dir * TURN_SPEED)
            return
        self.turn_dir = 0

        # 5. slow band → creep forward, steer gently away from the nearer side
        if nearest < SLOW_M:
            steer = TURN_SPEED * 0.4 * (1 if left < right else -1)
            self._move(SLOW_SPEED, steer)
            return

        # 6. all clear → forward
        self._move(FWD_SPEED, 0.0)


def main():
    rclpy.init()
    node = Robot2Autonomous()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node._stop()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
