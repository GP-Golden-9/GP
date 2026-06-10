#!/usr/bin/env python3
"""
Robot 1 (Alpha) — Motor Bridge for ROS 2
=========================================
Pairs with the standard motor controller on Robot 1.
Handles the STS: protocol for basic status and encoders.
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String, Int32MultiArray, Bool
import serial
import time
import threading


class Robot1Bridge(Node):
    def __init__(self):
        super().__init__('robot1_bridge')
        
        # /dev/mega is a udev symlink (systemd/99-gp-serial.rules) so the
        # Arduino can never be confused with the RPLidar (both are ttyUSB*).
        self.declare_parameter('serial_port', '/dev/mega')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('manual_timeout', 0.5)
        # Firmware stops motors after 2 s of serial silence; keepalive re-sends
        # the active command while fresh Twists arrive, deadman stops otherwise.
        self.declare_parameter('keepalive_period', 0.3)
        self.declare_parameter('deadman_timeout', 0.8)

        self.arduino = None
        self._serial_lock = threading.Lock()
        self.connect_arduino()

        # Manual override state
        self.manual_mode = False
        self.manual_last_time = time.time()
        self.emergency_stop = False
        self.last_twist_time = 0.0
        
        # Subscribers
        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_callback, 10)
        self.create_subscription(Twist, '/manual_cmd', self.manual_cmd_callback, 10)
        self.create_subscription(Bool, '/emergency_stop', self.estop_callback, 10)
        
        # Publishers
        self.status_pub = self.create_publisher(String, '/motor_status', 10)
        self.encoder_pub = self.create_publisher(Int32MultiArray, '/encoders', 10)
        
        self.last_cmd = 'S'
        
        # Timers
        self.create_timer(0.1, self.check_manual_timeout)
        self.create_timer(self.get_parameter('keepalive_period').value, self.keepalive)
        
        # Status polling thread
        self.thread = threading.Thread(target=self.poll_status, daemon=True)
        self.thread.start()
        
        self.get_logger().info('Robot 1 Bridge started')

    def connect_arduino(self):
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        ports = list(dict.fromkeys([port, '/dev/mega', '/dev/ttyUSB0', '/dev/ttyACM0']))
        
        for p in ports:
            try:
                self.arduino = serial.Serial(p, baud, timeout=1)
                time.sleep(2)
                self.get_logger().info(f'Connected to Arduino on {p}')
                return
            except:
                pass
        self.get_logger().error('Could not connect to Robot 1 Arduino')

    def _twist_to_cmd(self, msg: Twist) -> str:
        """Convert a Twist message to an Arduino direction command."""
        linear = msg.linear.x
        angular = msg.angular.z
        if abs(linear) < 0.05 and abs(angular) < 0.1:
            return 'S'
        if abs(linear) > abs(angular):
            return 'F' if linear > 0 else 'B'
        else:
            return 'L' if angular > 0 else 'R'

    def _send(self, cmd: str, force: bool = False):
        """Send a command to the Arduino if it differs from the last one (thread-safe)."""
        if not self.arduino:
            return
        if force or cmd != self.last_cmd or cmd == 'S':
            try:
                with self._serial_lock:
                    self.arduino.write(f'{cmd}\n'.encode())
                self.last_cmd = cmd
            except Exception as e:
                self.get_logger().error(f'Serial write error: {e}')

    def keepalive(self):
        """Re-send the active motion command while the commander is alive.

        The firmware stops after 2 s of silence (its watchdog); this keeps a
        legitimate continuous drive alive, and the deadman branch stops the
        robot if the commander (dashboard/explorer) goes silent mid-drive.
        """
        if self.emergency_stop or self.last_cmd not in ('F', 'B', 'L', 'R'):
            return
        deadman = self.get_parameter('deadman_timeout').value
        if time.monotonic() - self.last_twist_time <= deadman:
            self._send(self.last_cmd, force=True)
        else:
            self.get_logger().warn('Deadman: commander silent — stopping')
            self._send('S')

    def cmd_vel_callback(self, msg: Twist):
        """Autonomous command — only processed when not in manual mode."""
        if self.emergency_stop or self.manual_mode:
            return
        self.last_twist_time = time.monotonic()
        self._send(self._twist_to_cmd(msg))

    def manual_cmd_callback(self, msg: Twist):
        """Manual command from dashboard — takes priority over autonomous."""
        if self.emergency_stop:
            return
        self.manual_mode = True
        self.manual_last_time = time.time()
        self.last_twist_time = time.monotonic()
        self._send(self._twist_to_cmd(msg))

    def estop_callback(self, msg: Bool):
        """Emergency stop — highest priority."""
        if msg.data:
            self.emergency_stop = True
            self._send('S')
            self.get_logger().warn('EMERGENCY STOP ACTIVATED')
        else:
            self.emergency_stop = False
            self.get_logger().info('Emergency stop released')

    def check_manual_timeout(self):
        """Return to autonomous mode after manual timeout."""
        if self.manual_mode:
            timeout = self.get_parameter('manual_timeout').value
            if time.time() - self.manual_last_time > timeout:
                self.manual_mode = False

    def poll_status(self):
        # 1 Hz (was 5 Hz): every command — including '?' — feeds the firmware
        # watchdog, so aggressive polling would defeat its safety timeout.
        while rclpy.ok():
            if self.arduino:
                try:
                    with self._serial_lock:
                        self.arduino.write(b'?\n') # Request status
                    line = self.arduino.readline().decode().strip()
                    if line.startswith('STS:'):
                        # Publish raw status for dashboard
                        self.status_pub.publish(String(data=line))
                        
                        # Parse encoders for ROS
                        parts = line.split(',')
                        if len(parts) >= 6:
                            enc_msg = Int32MultiArray()
                            enc_msg.data = [int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])]
                            self.encoder_pub.publish(enc_msg)
                except:
                    pass
            time.sleep(1.0)

def main(args=None):
    rclpy.init(args=args)
    node = Robot1Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
