#!/usr/bin/env python3
"""
Robot 2 (Beta) — Local Navigation Fuser
=======================================
The SINGLE /cmd_vel publisher on Beta. Replaces robot2_goto.py +
robot2_autonomous.py (which fought over /cmd_vel). Beta has no lidar and —
since odometry moved to the laptop — no /odom either, so this node carries NO
pose/map math. It is purely reactive and lean (the Pi 3B+ throttles under load):

  * GOAL mode  — the laptop streams a heading bias (/cmd_vel_bias) computed from
                 the map-aware A* plan + the aligned pose. We fuse that
                 attraction with a repulsion field from the two front
                 ultrasonics, so Beta DODGES unmapped obstacles instead of just
                 stopping at them.
  * WANDER mode — no fresh bias: the reactive ultrasonic wander/avoid ladder
                 (ex-robot2_autonomous). Map-blind, always available.
  * REACTIVE fallback — GOAL was expected but the bias went stale (laptop link
                 lost) or Beta was never aligned: we wander rather than drive
                 blind toward a stale goal.

Master arm is /explore_enable (the dashboard AUTONOMOUS button). /emergency_stop
and the bridge's own forward hard-stop + deadman back-stop everything.

Subscribes : /cmd_vel_bias (Twist), /ultrasonic/{left,right} (Range),
             /explore_enable (Bool), /emergency_stop (Bool), /manual_cmd (Twist)
Publishes  : /cmd_vel (Twist), /nav_status (String)

Bands/speeds come from config/robot2.yaml (single source); the constants below
are last-resort fallbacks only.
"""

import math
import os
import sys
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Range
from std_msgs.msg import Bool, String

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # sibling import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'common'))
from gpcore.config import get_path, load_config          # noqa: E402
from local_nav_math import prox, goal_fusion             # noqa: E402

_CFG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'config', 'robot2.yaml')

# Fallbacks — real values live in config/robot2.yaml
STOP_M, CLEAR_M, SLOW_M, MAXR_M = 0.25, 0.40, 0.60, 1.50
MAX_LIN, TURN = 0.15, 0.40
FWD_SPEED, SLOW_SPEED, REV_SPEED = 0.12, 0.07, 0.10
K_REP = 0.40
STEER_DEADBAND = 0.10
TURN_LOCK_S, REV_TIME_S = 1.0, 0.6
BIAS_STALE_S = 0.8
# Global turn-direction sign. All steering uses the ROS convention (+wz = CCW
# = left). If the chassis/bridge mapping is reversed, the robot turns INTO
# obstacles on the bench — flip this to -1 in config (no code change), exactly
# as robot2_autonomous's header anticipated.
TURN_SIGN = 1.0
MANUAL_OVERRIDE_S = 1.0
RATE_HZ = 10.0
# SAFETY: the ultrasonics are Beta's only obstacle sense. If their feed goes
# stale (bridge reconnecting to the Mega, serial hiccup), driving on the last
# range is exactly how it crashes into a wall it can no longer see. After this
# long with no fresh range, STOP rather than trust a frozen reading.
RANGE_STALE_S = 1.0
# Stall escape: after this many bridge /stall events inside the window, give
# up (stop + report STUCK) instead of grinding forever — the laptop's
# replan-on-stuck or the operator then takes over.
STALL_GIVEUP_N = 4
STALL_WINDOW_S = 20.0
GIVEUP_STOP_S = 6.0
# SAFETY: WANDER drives autonomously on the Pi, so if the console vanishes
# (closed, crashed, or WiFi dropped) nothing would stop it. The dashboard
# re-affirms AUTONOMOUS at ~2 Hz; if that heartbeat goes stale, STOP. (GOAL
# mode also has the bias deadman, but this covers WANDER and is the master.)
EXPLORE_TIMEOUT_S = 2.0

try:
    _cfg = load_config(_CFG_PATH)
    STOP_M = float(get_path(_cfg, 'ultrasonic.stop_cm', 25)) / 100.0
    CLEAR_M = float(get_path(_cfg, 'ultrasonic.clear_cm', 40)) / 100.0
    SLOW_M = float(get_path(_cfg, 'ultrasonic.slow_cm', 60)) / 100.0
    MAXR_M = float(get_path(_cfg, 'ultrasonic.max_cm', 150)) / 100.0
    MAX_LIN = float(get_path(_cfg, 'goto.max_linear_mps', MAX_LIN))
    TURN = float(get_path(_cfg, 'goto.max_angular_rps', TURN))
    K_REP = float(get_path(_cfg, 'local_nav.k_rep', TURN))
    STEER_DEADBAND = float(get_path(_cfg, 'local_nav.steer_deadband', STEER_DEADBAND))
    FWD_SPEED = float(get_path(_cfg, 'local_nav.wander_fwd_mps', FWD_SPEED))
    SLOW_SPEED = float(get_path(_cfg, 'local_nav.wander_slow_mps', SLOW_SPEED))
    REV_SPEED = float(get_path(_cfg, 'local_nav.reverse_mps', REV_SPEED))
    TURN_LOCK_S = float(get_path(_cfg, 'local_nav.turn_lock_s', TURN_LOCK_S))
    REV_TIME_S = float(get_path(_cfg, 'local_nav.reverse_time_s', REV_TIME_S))
    BIAS_STALE_S = float(get_path(_cfg, 'local_nav.bias_stale_s', BIAS_STALE_S))
    TURN_SIGN = float(get_path(_cfg, 'local_nav.turn_sign', TURN_SIGN))
    EXPLORE_TIMEOUT_S = float(get_path(_cfg, 'local_nav.explore_timeout_s',
                                       EXPLORE_TIMEOUT_S))
except Exception:                        # config unreadable → fallbacks
    pass


class Robot2LocalNav(Node):
    def __init__(self):
        super().__init__('robot2_local_nav')
        self.enabled = False
        self.estop = False
        self.explore_t = 0.0           # last AUTONOMOUS heartbeat (safety)
        self.left = MAXR_M
        self.right = MAXR_M
        self.range_t = 0.0             # last fresh ultrasonic update (safety)

        # streamed attraction bias from the laptop
        self.bias_vx = 0.0
        self.bias_wz = 0.0
        self.bias_t = 0.0

        # anti-oscillation / recovery latches (ex-autonomous)
        self.turn_dir = 0
        self.turn_until = 0.0
        self.rev_until = 0.0
        self._manual_until = 0.0
        self._dbg = 0
        self._last_status = ''
        # Stall escape: the bridge publishes /stall when the wheels are frozen
        # under a drive command (physically wedged, or low obstacle the tilted
        # sensors miss). We back off + reorient to the more-open side. Repeated
        # stalls in a short window → give up so we don't grind forever (the
        # laptop's replan-on-stuck / the operator then takes over).
        self._stall_escapes = 0
        self._stall_first_t = 0.0
        self._giveup_until = 0.0

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/nav_status', 10)
        self.create_subscription(Twist, '/cmd_vel_bias', self._bias_cb, 10)
        self.create_subscription(Range, '/ultrasonic/left', self._left_cb, 10)
        self.create_subscription(Range, '/ultrasonic/right', self._right_cb, 10)
        self.create_subscription(Bool, '/explore_enable', self._enable_cb, 10)
        self.create_subscription(Bool, '/emergency_stop', self._estop_cb, 10)
        self.create_subscription(Twist, '/manual_cmd', self._manual_cb, 10)
        self.create_subscription(Bool, '/stall', self._stall_cb, 10)
        self.create_timer(1.0 / RATE_HZ, self._navigate)

        self.get_logger().info('═══════════════════════════════════════')
        self.get_logger().info('  Robot 2 Local Nav (fuser) started')
        self.get_logger().info(f'  bands  stop={STOP_M:.2f} slow={SLOW_M:.2f} m')
        self.get_logger().info(f'  speeds lin<={MAX_LIN:.2f} turn<={TURN:.2f}')
        self.get_logger().info('  waiting for /explore_enable')
        self.get_logger().info('═══════════════════════════════════════')

    # ── inputs ───────────────────────────────────────────────────────────
    def _bias_cb(self, m: Twist):
        self.bias_vx = m.linear.x
        self.bias_wz = m.angular.z
        self.bias_t = time.monotonic()

    def _left_cb(self, m: Range):
        self.left = m.range if m.range > 0.0 else MAXR_M
        self.range_t = time.monotonic()

    def _right_cb(self, m: Range):
        self.right = m.range if m.range > 0.0 else MAXR_M
        self.range_t = time.monotonic()

    def _enable_cb(self, m: Bool):
        en = bool(m.data)
        if en:
            self.explore_t = time.monotonic()      # heartbeat (streamed ~2 Hz)
        if en != self.enabled:                     # log only on state change
            self.get_logger().info('AUTONOMOUS ' +
                                   ('ENABLED' if en else 'DISABLED'))
        self.enabled = en
        if not en:
            self._reset_latches()
            self._stop()

    def _estop_cb(self, m: Bool):
        self.estop = bool(m.data)
        if self.estop:
            self._stop()

    def _manual_cb(self, m: Twist):
        # A live manual command takes priority — yield the /cmd_vel channel so
        # we never fight the operator (belt-and-suspenders; AUTONOMOUS off also
        # disables us). The bridge gives /manual_cmd its own path.
        if abs(m.linear.x) > 1e-6 or abs(m.angular.z) > 1e-6:
            self._manual_until = time.monotonic() + MANUAL_OVERRIDE_S

    def _stall_cb(self, m: Bool):
        """Bridge says the wheels are frozen under a drive command → ESCAPE:
        back off, then commit to the more-open side for a longer reorient.
        Triggers even when the ultrasonics read clear (a low obstacle the
        tilted sensors miss, or high-centred)."""
        if not (m.data and self.enabled and not self.estop):
            return
        now = time.monotonic()
        if now < self.rev_until:                 # already escaping — ignore dup
            return
        if self._stall_escapes == 0 or now - self._stall_first_t > STALL_WINDOW_S:
            self._stall_escapes = 0
            self._stall_first_t = now
        self._stall_escapes += 1
        self.rev_until = now + REV_TIME_S
        self.turn_dir = 1 if self.left > self.right else -1
        self.turn_until = self.rev_until + TURN_LOCK_S * 1.5   # bigger reorient
        side = 'left' if self.turn_dir > 0 else 'right'
        self.get_logger().warn(
            f'STALL -> escape #{self._stall_escapes}: back off + reorient {side}')
        if self._stall_escapes >= STALL_GIVEUP_N:
            self._giveup_until = now + GIVEUP_STOP_S
            self._stall_escapes = 0
            self.get_logger().error(
                f'STALL x{STALL_GIVEUP_N} in {STALL_WINDOW_S:.0f}s — GIVING UP, '
                'stopping (needs replan / operator)')

    # ── outputs ──────────────────────────────────────────────────────────
    def _stop(self):
        self.cmd_pub.publish(Twist())

    def _move(self, lin: float, ang: float):
        t = Twist()
        t.linear.x = float(max(-MAX_LIN, min(MAX_LIN, lin)))
        # TURN_SIGN is the single global steering-direction calibration.
        t.angular.z = float(max(-TURN, min(TURN, TURN_SIGN * ang)))
        self.cmd_pub.publish(t)

    def _status(self, text: str):
        if text != self._last_status:
            self._last_status = text
            self.status_pub.publish(String(data=text))

    def _reset_latches(self):
        self.turn_dir = 0
        self.turn_until = 0.0
        self.rev_until = 0.0

    # ── control loop (10 Hz) ─────────────────────────────────────────────
    def _navigate(self):
        if not self.enabled or self.estop:
            return
        now = time.monotonic()
        # SAFETY: the console must keep re-affirming AUTONOMOUS. If that
        # heartbeat goes stale (console closed/crashed, WiFi dropped), STOP —
        # never keep wandering with no operator. Latches reset so it resumes
        # cleanly when the heartbeat returns.
        if now - self.explore_t > EXPLORE_TIMEOUT_S:
            self._reset_latches()
            self._stop()
            self._status('LINK LOST — stopped')
            return
        if now < self._manual_until:        # operator override active
            self._status('MANUAL')
            return

        # Gave up after repeated stalls — hold and report, then auto-resume.
        if now < self._giveup_until:
            self._reset_latches()
            self._stop()
            self._status('STUCK — gave up (replan / operator needed)')
            return

        # SAFETY: never drive on a frozen obstacle reading. If the ultrasonic
        # feed stalled (bridge reconnecting), stop until it's live again.
        if self.range_t == 0.0 or now - self.range_t > RANGE_STALE_S:
            self._reset_latches()
            self._stop()
            self._status('NO RANGE — stopped')
            return

        left, right = self.left, self.right
        nearest = min(left, right)

        self._dbg += 1
        if self._dbg % 20 == 0:
            self.get_logger().info(
                f'L={left:.2f} R={right:.2f} turn={self.turn_dir} '
                f'bias=({self.bias_vx:+.2f},{self.bias_wz:+.2f})')

        # ── hard overrides (recovery) — evaluated FIRST (ex-autonomous) ──
        # 1. backing out of a corner
        if now < self.rev_until:
            self._move(-REV_SPEED, 0.0)
            self._status('STUCK')
            return
        # 2. both sides blocked → reverse, then commit to the more open side
        if left < STOP_M and right < STOP_M:
            self.turn_dir = 1 if left > right else -1
            self.rev_until = now + REV_TIME_S
            self.turn_until = now + REV_TIME_S + TURN_LOCK_S
            self._move(-REV_SPEED, 0.0)
            self._status('STUCK')
            return
        # 3. one side too close → latched pivot away
        if nearest < STOP_M:
            if now > self.turn_until:
                self.turn_dir = -1 if left < right else 1
                self.turn_until = now + TURN_LOCK_S
            self._move(0.0, self.turn_dir * TURN)
            self._status('BLOCKED')
            return
        # 4. finish an active pivot lock (anti-oscillation)
        if now < self.turn_until and self.turn_dir != 0:
            self._move(0.0, self.turn_dir * TURN)
            return
        self.turn_dir = 0

        # ── clear band: GOAL fusion if the bias is fresh, else WANDER ──
        if now - self.bias_t <= BIAS_STALE_S:
            vx, wz, blocked = goal_fusion(
                self.bias_vx, self.bias_wz, left, right,
                stop=STOP_M, slow=SLOW_M, max_lin=MAX_LIN, turn=TURN,
                k_rep=K_REP, deadband=STEER_DEADBAND)
            self._move(vx, wz)
            self._status('BLOCKED' if blocked else 'GOAL')
            return

        # WANDER (reactive, ex-autonomous slow-band + forward)
        if nearest < SLOW_M:
            # steer AWAY from the nearer side (obstacle on left → turn right)
            steer = TURN * 0.4 * (-1 if left < right else 1)
            self._move(SLOW_SPEED, steer)
        else:
            self._move(FWD_SPEED, 0.0)
        self._status('WANDER')


def main(args=None):
    rclpy.init(args=args)
    node = Robot2LocalNav()
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
