#!/usr/bin/env python3
"""Fake ESP32 inspector — serves robot3's HTTP API on localhost:80 so the
console's Gamma card, gas readouts and GAS alarm path run with zero
hardware. Spawned automatically by main.py --sim.

Behavior: gas idles around 600–900 ADC with noise, spikes above the alarm
threshold (3000) for ~8 s starting at t≈35 s — long enough to exercise the
fleet-wide GAS banner, the map marker and the auto-clear path.
"""

from __future__ import annotations

import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

T0 = time.monotonic()
LAST_CMD = {'t': time.monotonic(), 'dir': 'S'}
# Simulated IMU heading so Gamma's encoderless map dead-reckoning can be tested
# with no hardware: L/R pivot the heading, F/B don't change it (tank drive).
HEADING = {'th': 0.0, 't': time.monotonic()}
SIM_TURN_RATE = 0.6      # rad/s pivot, matches a slow inspector


def _active_dir() -> str:
    """Direction the firmware would currently hold — cleared by its 1.8 s
    command watchdog if the console stops streaming."""
    if time.monotonic() - LAST_CMD['t'] > 1.8:
        return 'S'
    return LAST_CMD['dir']


def telemetry() -> dict:
    t = time.monotonic() - T0
    gas = 750 + 140 * math.sin(t * 0.31) + random.uniform(-40, 40)
    if 35.0 <= t < 43.0:                     # scripted leak event
        gas = 3300 + random.uniform(-80, 80)
    now = time.monotonic()
    dt = now - HEADING['t']
    HEADING['t'] = now
    d = _active_dir()
    if d == 'L':
        HEADING['th'] += SIM_TURN_RATE * dt
    elif d == 'R':
        HEADING['th'] -= SIM_TURN_RATE * dt
    HEADING['th'] = math.atan2(math.sin(HEADING['th']), math.cos(HEADING['th']))
    return {
        'd': round(60 + 35 * math.sin(t * 0.6), 1),
        'g': int(gas),
        'x': round(0.4 * math.sin(t * 0.8), 2),     # tilt, NOT position
        'y': round(0.3 * math.cos(t * 0.7), 2),
        'h': round(HEADING['th'], 4),               # simulated IMU heading (rad)
        'dir': d,                                   # active drive direction
        'a': 1 if gas > 3000 else 0,
        'rssi': int(-48 - 6 * abs(math.sin(t * 0.05))),
        'uptime': int(t),
        'last_cmd_age': int((time.monotonic() - LAST_CMD['t']) * 1000),
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/telemetry':
            body = json.dumps(telemetry()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif url.path == '/control':
            LAST_CMD['t'] = time.monotonic()
            LAST_CMD['dir'] = (parse_qs(url.query).get('dir', ['S'])[0] or 'S')
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            body = b'<html><body><h3>fake ESP32 inspector (sim)</h3></body></html>'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):            # quiet
        pass


def main() -> int:
    try:
        server = ThreadingHTTPServer(('127.0.0.1', 80), Handler)
    except OSError as exc:
        print(f'[fake_esp32] cannot bind port 80 ({exc}) — Gamma stays offline '
              'in sim; everything else works')
        return 0
    print('[fake_esp32] inspector API on http://127.0.0.1/telemetry '
          '(gas leak event at t=35s)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    main()
