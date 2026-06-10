"""Parsers for every line format the Arduino Megas emit.

Line formats observed across firmware generations:

  v2  D:ts,e1,e2,e3,e4,ax,ay,az,gx,gy,gz                     (11 fields)
  v4  D:ts,e1,e2,e3,e4,ax,ay,az,gx,gy,gz,mx,my,mz            (14 fields)
  v5  D:…,mx,my,mz,pump,servo,estop                          (17 fields)
  v4  B:ts,pressure_pa,temp_deci_c
  r1  STS:IDLE,SPD:0                  (robot1 firmware '?' reply — text form)
  br  STS:speed,estop,e1,e2,e3,e4    (robot2 bridge synthesized — CSV form)
  any OK:<detail>  /  ERR:<detail>   (command ACKs)

All functions are pure; garbage in → ``None`` out, never an exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class DPacket:
    t_ms: int
    enc: Tuple[int, int, int, int]            # FL, RL, FR, RR
    accel: Tuple[int, int, int]               # raw LSB
    gyro: Tuple[int, int, int]                # raw LSB (bias-corrected by firmware)
    mag: Optional[Tuple[int, int, int]] = None
    pump: Optional[bool] = None               # v5 only
    servo_deg: Optional[int] = None           # v5 only
    estop: Optional[bool] = None              # v5 only


@dataclass(frozen=True)
class BPacket:
    t_ms: int
    pressure_pa: int
    temp_deci_c: int


@dataclass(frozen=True)
class STSPacket:
    text: str                                  # raw payload after 'STS:'
    speed: Optional[int] = None
    estop: Optional[bool] = None
    enc: Optional[Tuple[int, int, int, int]] = None


@dataclass(frozen=True)
class AckLine:
    ok: bool
    detail: str


def parse_line(line: str):
    """Parse one serial line → DPacket | BPacket | STSPacket | AckLine | None."""
    if not line:
        return None
    line = line.strip()
    if line.startswith('D:'):
        return _parse_d(line[2:])
    if line.startswith('B:'):
        return _parse_b(line[2:])
    if line.startswith('STS:'):
        return _parse_sts(line[4:])
    if line.startswith('OK:'):
        return AckLine(ok=True, detail=line[3:])
    if line.startswith('ERR:'):
        return AckLine(ok=False, detail=line[4:])
    return None


def _ints(parts):
    return [int(p) for p in parts]


def _parse_d(body: str) -> Optional[DPacket]:
    parts = body.split(',')
    if len(parts) < 11:
        return None
    try:
        vals = _ints(parts)
    except ValueError:
        return None
    mag = tuple(vals[11:14]) if len(vals) >= 14 else None
    pump = servo = estop = None
    if len(vals) >= 17:
        pump = bool(vals[14])
        servo = vals[15]
        estop = bool(vals[16])
    return DPacket(
        t_ms=vals[0],
        enc=tuple(vals[1:5]),
        accel=tuple(vals[5:8]),
        gyro=tuple(vals[8:11]),
        mag=mag,
        pump=pump,
        servo_deg=servo,
        estop=estop,
    )


def _parse_b(body: str) -> Optional[BPacket]:
    parts = body.split(',')
    if len(parts) != 3:
        return None
    try:
        t, p, temp = _ints(parts)
    except ValueError:
        return None
    return BPacket(t_ms=t, pressure_pa=p, temp_deci_c=temp)


def _parse_sts(body: str) -> STSPacket:
    parts = body.split(',')
    # CSV numeric form from robot2_bridge: speed,estop,e1,e2,e3,e4
    if len(parts) >= 6:
        try:
            vals = _ints(parts[:6])
            return STSPacket(text=body, speed=vals[0], estop=bool(vals[1]),
                             enc=tuple(vals[2:6]))
        except ValueError:
            pass
    # Text form from robot1 firmware: "IDLE,SPD:0" / "MOVING,SPD:180" / "ESTOP,…"
    speed = None
    estop = None
    for p in parts:
        p = p.strip()
        if p.startswith('SPD:'):
            try:
                speed = int(p[4:])
            except ValueError:
                pass
        elif p == 'ESTOP':
            estop = True
    return STSPacket(text=body, speed=speed, estop=estop)
