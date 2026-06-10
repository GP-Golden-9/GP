"""Command formatting/validation for the Arduino Mega serial link.

Letter map (v5 firmware — supersets v4; v4 silently ignores U/A/E/X):
  F/B/L/R/S    motion
  P<80..255>   PWM speed
  T<l>,<r>     tank drive (independent side PWM, signed)
  U1 / U0      water pump on/off            (NOT 'W' — that toggles the watchdog!)
  A<deg>       arm servo angle, clamped
  E / X        e-stop engage / release
"""

from __future__ import annotations

MOTION_CMDS = ('F', 'B', 'L', 'R', 'S')

PWM_MIN, PWM_MAX = 80, 255
TANK_MIN, TANK_MAX = -255, 255
SERVO_MIN_DEG, SERVO_MAX_DEG = 10, 170
PUMP_MAX_RUN_MS = 5000      # firmware-enforced auto-off (documented here for UIs)

# Twist→command deadbands — MUST mirror navigation/robot*_bridge.py
LINEAR_DEADBAND = 0.05
ANGULAR_DEADBAND = 0.1


def motion(cmd: str) -> str:
    c = cmd.upper()
    if c not in MOTION_CMDS:
        raise ValueError(f'invalid motion command {cmd!r}')
    return c


def pwm(value: int) -> str:
    return f'P{max(PWM_MIN, min(PWM_MAX, int(value)))}'


def tank(left: int, right: int) -> str:
    l = max(TANK_MIN, min(TANK_MAX, int(left)))
    r = max(TANK_MIN, min(TANK_MAX, int(right)))
    return f'T{l},{r}'


def pump(on: bool) -> str:
    return 'U1' if on else 'U0'


def servo(deg: int) -> str:
    return f'A{max(SERVO_MIN_DEG, min(SERVO_MAX_DEG, int(deg)))}'


def estop(engage: bool) -> str:
    return 'E' if engage else 'X'


def twist_to_motion(linear: float, angular: float) -> str:
    """Mirror of the bridges' Twist→letter logic (single source of truth now)."""
    if abs(linear) < LINEAR_DEADBAND and abs(angular) < ANGULAR_DEADBAND:
        return 'S'
    if abs(linear) > abs(angular):
        return 'F' if linear > 0 else 'B'
    return 'L' if angular > 0 else 'R'


def pwm_from_linear(linear: float, max_linear: float = 0.5) -> int:
    """Mirror of robot2_bridge's speed mapping: |v|∈(0..max] → PWM 80..255."""
    if max_linear <= 0:
        return PWM_MAX
    factor = min(abs(linear) / max_linear, 1.0)
    return int(PWM_MIN + factor * (PWM_MAX - PWM_MIN))
