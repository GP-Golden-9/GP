#!/usr/bin/env python3
"""GP Gateway — the only doorway between a robot's ROS island and the network.

Runs on each Pi. ROS topics in/out on one side, the versioned ZMQ protocol
(gpcore.protocol) on the other. With ROS_LOCALHOST_ONLY=1 set by the launch
file, NO DDS traffic crosses the WiFi — only these explicit channels:

    PUB 5556 telemetry   tele.full 20 Hz, tele.scan ≤5 Hz, log.event
    PUB 5557 map         map.grid ≤1 Hz (zlib int8)
    PUB 5559 health      1 Hz (stream freshness + Pi vitals)
    ROUTER 5558 commands cmd.* in, ack out (dedupe + drive deadman)

Usage (normally via the robot launch file):
    python3 gateway_node.py --config /home/pi/GP/config/robot2.yaml
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
import zlib
from array import array

import math

import rclpy
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import Imu, LaserScan
from std_msgs.msg import Bool, Float32, Int32MultiArray, String

from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

# allow running from a source checkout (gateway/ next to common/)
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.abspath(os.path.join(_here, '..', 'common')))

from gpcore.config import load_robot_config
from gpcore.logging_setup import new_run_id, setup_logging
from gpcore.protocol import channels as ch
from gpcore.protocol import commands as cmds
from gpcore.serialproto import mega_commands as mc

from zmq_server import GatewayServer            # noqa: E402
from health_aggregator import HealthAggregator  # noqa: E402

TELE_HZ = 20.0
SCAN_FORWARD_HZ = 5.0
MAP_FORWARD_HZ = 1.0
HEALTH_HZ = 1.0

STREAMS = ('encoders', 'imu', 'odom', 'scan', 'map', 'motor_status')


class GatewayNode(Node):
    def __init__(self, cfg: dict, run_id: str):
        super().__init__('gp_gateway')
        self.cfg = cfg
        robot_id = cfg['robot']['id']
        self.robot_id = robot_id
        self.log = setup_logging('gateway', run_id=run_id)

        endpoints = {
            'telemetry': f"tcp://*:{cfg['zmq']['telemetry']}",
            'map':       f"tcp://*:{cfg['zmq']['map']}",
            'health':    f"tcp://*:{cfg['zmq']['health']}",
            'cmd':       f"tcp://*:{cfg['zmq']['cmd']}",
        }
        self.server = GatewayServer(run_id=run_id, src=robot_id,
                                    endpoints=endpoints)
        self.health = HealthAggregator(streams=STREAMS)

        # ── latest-state cache assembled into tele.full ──
        self.state = {
            'enc': None, 'gyro': None, 'accel': None,
            'odom': None, 'pwm': None,
            'pump': None, 'servo_deg': None, 'estop': False,
            'nav_status': 'IDLE', 'motor_status': '',
            'accessory': '',
        }
        self._last_scan_fwd = 0.0
        self._last_map_fwd = 0.0
        # laser frame yaw vs base_link (pi on robot1: A1 zero axis faces
        # rear). Added to a0 so tele.scan angles are BASE-frame — the
        # console renders scan points at robot pose + angle directly.
        self._laser_yaw = float(
            cfg.get('footprint', {}).get('laser_yaw_rad', 0.0))

        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ── ROS subscriptions (robot-local only) ──
        sub = self.create_subscription
        sub(Int32MultiArray, '/encoders', self._enc_cb, 10)
        sub(Imu, '/imu/data_raw', self._imu_cb, 20)
        sub(Odometry, '/odom', self._odom_cb, 20)
        sub(LaserScan, '/scan', self._scan_cb, 5)
        sub(OccupancyGrid, '/map', self._map_cb, 1)
        sub(String, '/motor_status', self._motor_status_cb, 5)
        sub(String, '/nav_status', self._nav_status_cb, 5)
        sub(String, '/accessory_state', self._accessory_cb, 5)
        sub(String, '/robot_log', self._robot_log_cb, 10)
        # slam_toolbox's pose — odom fallback for robots with no wheel odometry
        sub(PoseWithCovarianceStamped, '/pose', self._pose_cb, 5)

        # ── ROS publishers (commands fan out locally) ──
        self.pub_manual = self.create_publisher(Twist, '/manual_cmd', 10)
        self.pub_estop = self.create_publisher(Bool, '/emergency_stop', 10)
        self.pub_explore = self.create_publisher(Bool, '/explore_enable', 10)
        self.pub_goal = self.create_publisher(PoseStamped, '/goal_pose', 10)
        self.pub_speed = self.create_publisher(Float32, '/set_speed', 10)
        self.pub_accessory = self.create_publisher(String, '/accessory_cmd', 10)

        # ── command handlers ──
        s = self.server.set_handler
        s(cmds.CMD_DRIVE, self._h_drive)
        s(cmds.CMD_ESTOP, self._h_estop)
        s(cmds.CMD_PUMP, self._h_pump)
        s(cmds.CMD_SERVO, self._h_servo)
        s(cmds.CMD_EXPLORE, self._h_explore)
        s(cmds.CMD_GOAL, self._h_goal)
        s(cmds.CMD_SPEED, self._h_speed)
        s(cmds.CMD_RESET_MAP, self._h_reset_map)

        # ── timers ──
        # The command poll gets its OWN callback group: with the default
        # (shared, mutually exclusive) group the MultiThreadedExecutor never
        # actually runs it in parallel, and a slow /map or /scan callback on
        # the Pi 3B+ still starves ACKs. Cross-thread publishes are safe —
        # GatewayServer.publish is locked.
        self._cmd_group = MutuallyExclusiveCallbackGroup()
        self.create_timer(0.02, self._tick_commands,           # 50 Hz cmd poll
                          callback_group=self._cmd_group)
        self.create_timer(1.0 / TELE_HZ, self._tick_telemetry)
        self.create_timer(1.0 / HEALTH_HZ, self._tick_health)

        self.log.info('gateway up', extra={'kv': {
            'robot': robot_id, 'run_id': run_id,
            'ports': cfg['zmq'],
        }})

    # ════════ ROS → cache/ZMQ ════════
    def _enc_cb(self, msg):
        self.state['enc'] = list(msg.data)[:4]
        self.health.touch('encoders')

    def _imu_cb(self, msg: Imu):
        self.state['gyro'] = [msg.angular_velocity.x, msg.angular_velocity.y,
                              msg.angular_velocity.z]
        self.state['accel'] = [msg.linear_acceleration.x,
                               msg.linear_acceleration.y,
                               msg.linear_acceleration.z]
        self.health.touch('imu')

    def _odom_cb(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.state['odom'] = {
            'x': round(p.x, 4), 'y': round(p.y, 4),
            'th': round(math.atan2(siny, cosy), 4),
            'v': round(msg.twist.twist.linear.x, 3),
            'w': round(msg.twist.twist.angular.z, 3),
        }
        self.health.touch('odom')

    def _pose_cb(self, msg: PoseWithCovarianceStamped):
        # Fallback if there is no true /odom publisher (like on Robot 1):
        # take the pose from slam_toolbox to populate the dashboard UI.
        odom = self.state.get('odom')
        if odom and odom.get('v', 0.0) != 0.0:
            return                      # true odometry is flowing — keep it
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.state['odom'] = {
            'x': round(p.x, 4), 'y': round(p.y, 4),
            'th': round(math.atan2(siny, cosy), 4),
            'v': 0.0,
            'w': 0.0,
        }
        self.health.touch('odom')

    def _scan_cb(self, msg: LaserScan):
        self.health.touch('scan')
        now = time.monotonic()
        if now - self._last_scan_fwd < 1.0 / SCAN_FORWARD_HZ:
            return
        self._last_scan_fwd = now
        ranges = array('f', (0.0 if r is None else float(r) for r in msg.ranges))
        self.server.publish('telemetry', ch.TELE_SCAN, {
            'a0': msg.angle_min + self._laser_yaw,   # base-frame angles
            'da': msg.angle_increment,
            'rmin': msg.range_min,
            'rmax': msg.range_max,
            'ranges': ranges.tobytes(),     # float32 LE
        })

    def _map_cb(self, msg: OccupancyGrid):
        self.health.touch('map')
        now = time.monotonic()
        if now - self._last_map_fwd < 1.0 / MAP_FORWARD_HZ:
            return
        self._last_map_fwd = now
        grid = array('b', msg.data).tobytes()
        self.server.publish('map', ch.MAP_GRID, {
            'w': msg.info.width,
            'h': msg.info.height,
            'res': msg.info.resolution,
            'ox': msg.info.origin.position.x,
            'oy': msg.info.origin.position.y,
            'enc': 'zlib',
            'data': zlib.compress(grid, level=3),
        })

    def _motor_status_cb(self, msg: String):
        self.state['motor_status'] = msg.data
        self.health.touch('motor_status')

    def _nav_status_cb(self, msg: String):
        self.state['nav_status'] = msg.data

    def _accessory_cb(self, msg: String):
        # OK:PUMP=ON / OK:SERVO=95 / ERR:PUMP_COOLDOWN … forwarded verbatim;
        # also mirrored into tele.full for stateful UIs.
        self.state['accessory'] = msg.data
        d = msg.data
        if d.startswith('OK:PUMP='):
            self.state['pump'] = d.endswith('ON')
        elif d.startswith('OK:SERVO='):
            try:
                self.state['servo_deg'] = int(d.split('=')[1])
            except (ValueError, IndexError):
                pass
        elif d in ('OK:ESTOP',):
            self.state['estop'] = True
        elif d in ('OK:RELEASED',):
            self.state['estop'] = False

    def _robot_log_cb(self, msg: String):
        self.server.publish('health', ch.LOG_EVENT, {'line': msg.data})

    # ════════ ZMQ commands → ROS ════════
    def _h_drive(self, env):
        vx = float(env.payload.get('vx', 0.0))
        wz = float(env.payload.get('wz', 0.0))
        t = Twist()
        t.linear.x = vx
        t.angular.z = wz
        self.pub_manual.publish(t)
        return True, 'ok'

    def _h_estop(self, env):
        engage = bool(env.payload.get('engage', True))
        self.pub_estop.publish(Bool(data=engage))
        if engage:
            self.pub_manual.publish(Twist())                      # stop now
            self.pub_accessory.publish(String(data=mc.pump(False)))  # pump off
        self.state['estop'] = engage
        self.log.warning('estop', extra={'kv': {'engage': engage}})
        return True, 'engaged' if engage else 'released'

    def _h_pump(self, env):
        if self.server.estop_latched and env.payload.get('on'):
            return False, 'estop latched'
        self.pub_accessory.publish(String(data=mc.pump(bool(env.payload.get('on')))))
        return True, 'forwarded'

    def _h_servo(self, env):
        cmd = mc.servo(int(env.payload.get('deg', 90)))   # clamps 10–170
        self.pub_accessory.publish(String(data=cmd))
        return True, cmd

    def _h_explore(self, env):
        self.pub_explore.publish(Bool(data=bool(env.payload.get('enable'))))
        return True, 'ok'

    def _h_goal(self, env):
        ps = PoseStamped()
        ps.header.frame_id = 'odom'
        ps.header.stamp = self.get_clock().now().to_msg()
        ps.pose.position.x = float(env.payload['x'])
        ps.pose.position.y = float(env.payload['y'])
        ps.pose.orientation.w = 1.0
        self.pub_goal.publish(ps)
        return True, 'ok'

    def _h_speed(self, env):
        self.pub_speed.publish(Float32(data=float(env.payload.get('value', 0.0))))
        return True, 'ok'

    def _h_reset_map(self, env):
        # Restart THIS robot's stack (SLAM included) to start a fresh map.
        # The dashboard routes this to the mapper; the service name must
        # match the robot we run on, not a hardcoded one.
        service = f'gp-{self.robot_id}.service'
        self.log.warning('reset map requested — restarting %s', service)
        # Backgrounded so the ACK leaves before systemd kills us.
        os.system(f'(sleep 0.5; sudo systemctl restart {service}) &')
        return True, f'restarting {service}'

    # ════════ periodic ════════
    def _tick_commands(self):
        self.server.poll_commands(0)   # non-blocking; MultiThreadedExecutor isolates this
        if self.server.deadman_tripped():
            self.pub_manual.publish(Twist())
            self.log.warning('drive deadman tripped — stop sent')
            self.server.publish('health', ch.LOG_EVENT,
                                {'line': 'GATEWAY: drive deadman tripped'})

    def _tick_telemetry(self):
        # On the SLAM robot, map->base_link IS the authoritative pose
        # (drift-corrected). Use it for position whenever it resolves and
        # keep the velocities from /odom (zero if no odom source). Robots
        # without a map frame raise TransformException and keep wheel odom.
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link',
                                                rclpy.time.Time())
            q = t.transform.rotation
            siny = 2.0 * (q.w * q.z + q.x * q.y)
            cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            prev = self.state.get('odom') or {}
            self.state['odom'] = {
                'x': round(t.transform.translation.x, 4),
                'y': round(t.transform.translation.y, 4),
                'th': round(math.atan2(siny, cosy), 4),
                'v': prev.get('v', 0.0),
                'w': prev.get('w', 0.0),
            }
            self.health.touch('odom')
        except TransformException:
            pass

        self.server.publish('telemetry', ch.TELE_FULL, dict(self.state))

    def _tick_health(self):
        snap = self.health.snapshot()
        snap['cmd_stats'] = dict(self.server.stats)
        snap['estop'] = self.server.estop_latched
        self.server.publish('health', ch.HEALTH, snap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    args, ros_args = ap.parse_known_args()

    cfg = load_robot_config(args.config)
    run_id = os.environ.get('GP_RUN_ID') or new_run_id()

    rclpy.init(args=ros_args)
    node = GatewayNode(cfg, run_id)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.server.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
