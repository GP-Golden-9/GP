#!/usr/bin/env python3
"""Hold the RPLidar A1 motor OFF while the robot stack is down.

The A1's motor is wired to the USB adapter's DTR line. With no program
holding the port, the adapter's default lets the motor spin forever —
the "lidar runs the moment I plug the robot in" complaint. This script
opens the port, asserts DTR (motor stop), and simply holds it.

Run via gp-lidar-idle.service, which Conflicts= with gp-robot1.service:
systemd stops this holder (freeing the port) right before the real
driver starts, and gp-robot1's ExecStopPost starts it again, so the
motor only ever spins while the stack is actually mapping.
"""

import sys
import time

import serial

PORT = '/dev/rplidar'

try:
    ser = serial.Serial(PORT, 115200, timeout=0.2)
except (serial.SerialException, OSError) as exc:
    # Device absent or busy (driver owns it) — nothing to hold.
    print(f'lidar_idle: cannot open {PORT}: {exc}', flush=True)
    sys.exit(0)

ser.dtr = True          # A1 adapter: DTR asserted = motor STOP
# also request scan stop in case the core was left scanning
try:
    ser.write(b'\xa5\x25')      # RPLIDAR STOP command
except serial.SerialException:
    pass
print('lidar_idle: motor held OFF (DTR asserted) — '
      'stack start releases the port', flush=True)

try:
    while True:
        time.sleep(60)
        ser.dtr = True          # re-assert defensively
except KeyboardInterrupt:
    pass
finally:
    ser.close()
