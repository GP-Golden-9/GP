"""Command channel semantics: types, ids, ACKs, dedupe, deadman.

Laptop (DEALER) → robot (ROUTER):  envelope with type ``cmd.*`` whose payload
always carries a ``cmd_id``. Robot replies with type ``ack`` echoing the id.

Retry rule: ACK timeout 300 ms, ×2 retries with the SAME cmd_id — the robot
dedupes by id, so pump/servo commands are exactly-once even under retry.
Drive commands are a 10 Hz keepalive stream; the gateway's deadman stops the
robot when the stream goes silent for DEADMAN_S while velocity ≠ 0.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Any, Dict

from .envelope import Envelope, make_envelope

CMD_DRIVE   = 'cmd.drive'    # {vx: float, wz: float}
CMD_ESTOP   = 'cmd.estop'    # {engage: bool}
CMD_PUMP    = 'cmd.pump'     # {on: bool}
CMD_SERVO   = 'cmd.servo'    # {deg: int}
CMD_EXPLORE = 'cmd.explore'  # {enable: bool}
CMD_GOAL    = 'cmd.goal'     # {x: float, y: float}
CMD_SPEED   = 'cmd.speed'    # {value: float 0..1}
CMD_PING    = 'cmd.ping'     # {} — link liveness check

ALL_COMMANDS = frozenset({
    CMD_DRIVE, CMD_ESTOP, CMD_PUMP, CMD_SERVO, CMD_EXPLORE, CMD_GOAL,
    CMD_SPEED, CMD_PING,
})

# Commands that must execute exactly once (retries must be deduped):
EXACTLY_ONCE = frozenset({CMD_PUMP, CMD_SERVO, CMD_GOAL})

ACK_TIMEOUT_S = 0.30
ACK_RETRIES = 2
DEADMAN_S = 0.60
DRIVE_STREAM_HZ = 10.0
ESTOP_BURST = 5            # e-stop is sent this many times, 50 ms apart
ESTOP_BURST_SPACING_S = 0.05


class CommandError(Exception):
    pass


def new_cmd_id() -> str:
    return uuid.uuid4().hex[:12]


def make_command(cmd_type: str, payload: Dict[str, Any], *, seq: int, run_id: str,
                 src: str, cmd_id: str | None = None) -> Envelope:
    if cmd_type not in ALL_COMMANDS:
        raise CommandError(f'unknown command type {cmd_type!r}')
    body = dict(payload)
    body['cmd_id'] = cmd_id or new_cmd_id()
    return make_envelope(cmd_type, body, seq=seq, run_id=run_id, src=src)


def make_ack(cmd_env: Envelope, *, ok: bool, detail: str = '', seq: int,
             run_id: str, src: str) -> Envelope:
    return make_envelope('ack', {
        'cmd_id': cmd_env.payload.get('cmd_id', ''),
        'cmd_type': cmd_env.type,
        'ok': ok,
        'detail': detail,
    }, seq=seq, run_id=run_id, src=src)


def validate_command(env: Envelope) -> str:
    """Returns the cmd_id; raises CommandError when the envelope is not a
    well-formed command."""
    if env.type not in ALL_COMMANDS:
        raise CommandError(f'unknown command type {env.type!r}')
    cmd_id = env.payload.get('cmd_id')
    if not cmd_id or not isinstance(cmd_id, str):
        raise CommandError(f'{env.type}: missing cmd_id')
    return cmd_id


class CommandDeduper:
    """LRU set of recently executed cmd_ids (robot side).

    A retried command (same cmd_id) is acknowledged but not re-executed.
    """

    def __init__(self, capacity: int = 64):
        self.capacity = capacity
        self._seen: OrderedDict[str, None] = OrderedDict()

    def seen_before(self, cmd_id: str) -> bool:
        if cmd_id in self._seen:
            self._seen.move_to_end(cmd_id)
            return True
        self._seen[cmd_id] = None
        if len(self._seen) > self.capacity:
            self._seen.popitem(last=False)
        return False


class DriveDeadman:
    """Stops the robot when the drive stream goes silent mid-motion.

    Feed it every accepted drive command; ``should_stop(now)`` is polled by
    the gateway loop and returns True exactly once per silence event.
    """

    def __init__(self, timeout_s: float = DEADMAN_S):
        self.timeout_s = timeout_s
        self._last_cmd_mono: float | None = None
        self._moving = False
        self._tripped = False

    def feed(self, vx: float, wz: float, now_mono: float) -> None:
        self._last_cmd_mono = now_mono
        self._moving = (abs(vx) > 1e-6 or abs(wz) > 1e-6)
        self._tripped = False

    def should_stop(self, now_mono: float) -> bool:
        if (self._moving and not self._tripped and self._last_cmd_mono is not None
                and now_mono - self._last_cmd_mono > self.timeout_s):
            self._tripped = True
            self._moving = False
            return True
        return False
