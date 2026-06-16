"""Laptop-side wheel + gyro odometry (moved OFF the Pi, 2026-06-16).

`navigation/robot2_odom.py` fused encoders + IMU into a pose at 50 Hz and
burned ~80 % of a Pi 3B+ core doing it, starving the bridge/gateway so the
map pose trailed live movement (while the standalone camera stayed smooth).
The gateway already streams the raw `enc` + `gyro` in every telemetry frame,
so the powerful laptop reconstructs the pose here for free. Same kinematics,
slip gate, gyro-bias auto-cal and IMU-dead fallback as the Pi node — just run
at the ~20 Hz telemetry rate instead of 50 Hz (the integration is identical,
the timestep is simply larger).

Stateful: one instance per robot. `update(enc, gyro)` returns the same
`{'x','y','th','v','w'}` dict the gateway used to put in `telemetry['odom']`,
so nothing downstream changes.
"""

from __future__ import annotations

import math
import time
from typing import Optional, Sequence


class LocalOdom:
    def __init__(self, drive: dict):
        wheel_d = float(drive.get('wheel_diameter_m', 0.085))
        ticks = int(drive.get('ticks_per_rev', 408))
        self.wheel_base = float(drive.get('wheel_base_m', 0.225))
        self.enc_w = float(drive.get('encoder_heading_weight', 0.3))
        self.slip_gate = float(drive.get('slip_gate_rad_s', 0.6))
        self.m_per_tick = (math.pi * wheel_d) / ticks

        self.x = self.y = self.theta = 0.0
        self.v = self.w = 0.0
        self.prev_enc: Optional[list] = None
        self.last_t: Optional[float] = None

        # gyro zero-rate bias auto-cal (learned while the wheels are stopped)
        self.gyro_bias = 0.0
        self._bias_locked = False
        self._bias_n = 0
        self._still = 0
        # dead-IMU detection (firmware streams exact zeros when the chip is
        # dead/unwired — a live MPU always jitters)
        self._imu_zero = 0
        self._imu_dead = False

    def reset(self) -> None:
        """Zero the pose — called when the robot restarts (run_id changes),
        mirroring the Pi node coming up at the origin."""
        self.x = self.y = self.theta = 0.0
        self.v = self.w = 0.0
        self.prev_enc = None
        self.last_t = None

    def update(self, enc: Sequence, gyro: Optional[Sequence],
               heading: Optional[float] = None) -> Optional[dict]:
        if not enc or len(enc) < 4:
            return None
        now = time.monotonic()
        if self.prev_enc is None or self.last_t is None:
            self.prev_enc = list(enc)
            self.last_t = now
            return {'x': 0.0, 'y': 0.0, 'th': round(self.theta, 4),
                    'v': 0.0, 'w': 0.0}

        dt = now - self.last_t
        if dt <= 0 or dt > 1.0:
            dt = 0.05                       # ~telemetry period fallback

        d_fl = enc[0] - self.prev_enc[0]
        d_rl = enc[1] - self.prev_enc[1]
        d_fr = enc[2] - self.prev_enc[2]
        d_rr = enc[3] - self.prev_enc[3]

        gz_raw = float(gyro[2]) if (gyro and len(gyro) >= 3) else 0.0
        if gyro and all(abs(float(g)) < 1e-9 for g in gyro):
            self._imu_zero = min(self._imu_zero + 1, 1000)
        else:
            self._imu_zero = 0
        self._imu_dead = self._imu_zero >= 12      # ~0.6 s of exact zeros

        ticks_total = abs(d_fl) + abs(d_rl) + abs(d_fr) + abs(d_rr)
        if ticks_total == 0:                       # robot still → learn bias
            self._still += 1
            window = 0.06 if self._bias_locked else 0.5
            if (self._still >= 10 and not self._imu_dead
                    and abs(gz_raw - self.gyro_bias) < window):
                self.gyro_bias += 0.02 * (gz_raw - self.gyro_bias)
                self._bias_n += 1
                if not self._bias_locked and self._bias_n >= 60:
                    self._bias_locked = True
        else:
            self._still = 0

        d_left = (d_fl + d_rl) / 2.0
        d_right = (d_fr + d_rr) / 2.0
        distance = (d_left + d_right) / 2.0 * self.m_per_tick
        d_theta_enc = ((d_right - d_left) * self.m_per_tick) / self.wheel_base

        if heading is not None:
            # The robot integrated the heading at 50 Hz — far better than our
            # 20 Hz gyro integration. Use it directly; only discount distance
            # when the wheels claim a lot more rotation than the body actually
            # turned (carpet scrub).
            new_theta = math.atan2(math.sin(heading), math.cos(heading))
            d_theta = math.atan2(math.sin(new_theta - self.theta),
                                 math.cos(new_theta - self.theta))
            w_enc = d_theta_enc / dt if dt > 0 else 0.0
            w_body = d_theta / dt if dt > 0 else 0.0
            if ticks_total > 0 and abs(w_enc - w_body) > self.slip_gate:
                distance *= min(1.0, (abs(w_body) + 0.05) / (abs(w_enc) + 0.05))
            self.theta = new_theta
            self.x += distance * math.cos(self.theta)
            self.y += distance * math.sin(self.theta)
            self.v = distance / dt if dt > 0 else 0.0
            self.w = d_theta / dt if dt > 0 else 0.0
            self.prev_enc = list(enc)
            self.last_t = now
            return {'x': round(self.x, 4), 'y': round(self.y, 4),
                    'th': round(self.theta, 4),
                    'v': round(self.v, 3), 'w': round(self.w, 3)}

        if self._imu_dead:
            d_theta = d_theta_enc
        else:
            gz = gz_raw - self.gyro_bias
            d_theta_imu = gz * dt
            w_enc = d_theta_enc / dt if dt > 0 else 0.0
            if ticks_total == 0 and abs(gz) < 0.03:
                d_theta = 0.0                      # parked: freeze heading
            elif abs(w_enc - gz) > self.slip_gate:
                # carpet slip: gyro owns heading, discount the slipped distance
                d_theta = d_theta_imu
                distance *= min(1.0, (abs(gz) + 0.05) / (abs(w_enc) + 0.05))
            else:
                d_theta = (self.enc_w * d_theta_enc
                           + (1.0 - self.enc_w) * d_theta_imu)

        self.theta = math.atan2(math.sin(self.theta + d_theta),
                                math.cos(self.theta + d_theta))
        self.x += distance * math.cos(self.theta)
        self.y += distance * math.sin(self.theta)
        self.v = distance / dt if dt > 0 else 0.0
        self.w = d_theta / dt if dt > 0 else 0.0

        self.prev_enc = list(enc)
        self.last_t = now
        return {'x': round(self.x, 4), 'y': round(self.y, 4),
                'th': round(self.theta, 4),
                'v': round(self.v, 3), 'w': round(self.w, 3)}
