"""Throwaway, runs ON THE PI: drive the Mega directly over serial.

Bypasses ROS/gateway/bridge entirely: P255 + F for 0.8 s, then S.
Parses the D: stream before and after to report encoder deltas.
"""
import re
import time

import serial

PORT = '/dev/mega'


def read_enc(ser, seconds):
    """Latest encoder 4-tuple seen within the window."""
    enc = None
    deadline = time.time() + seconds
    while time.time() < deadline:
        line = ser.readline().decode(errors='ignore').strip()
        if line.startswith('D:'):
            parts = line[2:].split(',')
            if len(parts) >= 5:
                try:
                    enc = tuple(int(p) for p in parts[1:5])
                except ValueError:
                    pass
    return enc


ser = serial.Serial(PORT, 115200, timeout=0.2)
time.sleep(2.5)                      # Arduino auto-reset on open
ser.reset_input_buffer()

before = read_enc(ser, 1.5)
print('ENC BEFORE :', before, flush=True)

ser.write(b'P255\n')
time.sleep(0.1)
ser.write(b'F\n')
t_end = time.time() + 0.8
while time.time() < t_end:           # feed the watchdog while driving
    ser.write(b'F\n')
    time.sleep(0.2)
ser.write(b'S\n')
ser.write(b'S\n')

after = read_enc(ser, 1.5)
print('ENC AFTER  :', after, flush=True)
if before and after:
    delta = [a - b for a, b in zip(after, before)]
    print('DELTA      :', delta, flush=True)
    moved = sum(abs(d) for d in delta)
    print('VERDICT    :', 'WHEELS TURNED' if moved > 10 else
          'MOTORS DEAD AT FULL PWM — electrical fault at L298N', flush=True)
ser.close()
