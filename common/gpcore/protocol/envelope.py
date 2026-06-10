"""Versioned msgpack message envelope used on every ZMQ channel.

Wire format (msgpack map):
    {v, seq, t_mono, t_wall, run_id, src, type, payload}

* ``seq``     — per-channel monotonically increasing counter (gap detection)
* ``t_mono``  — sender's ``time.monotonic()`` at send (latency/staleness math)
* ``t_wall``  — sender's epoch seconds (human correlation across machines)
* ``run_id``  — launch-session id, identical across all nodes of one launch
* ``src``     — sender id, e.g. ``robot2`` or ``dashboard``
* ``type``    — payload type, e.g. ``tele.full``, ``map.grid``, ``cmd.drive``
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict

import msgpack

PROTOCOL_VERSION = 1

_REQUIRED_FIELDS = ('v', 'seq', 't_mono', 't_wall', 'run_id', 'src', 'type', 'payload')


class ProtocolError(Exception):
    """Raised when a message cannot be decoded or has the wrong version."""


@dataclass
class Envelope:
    v: int
    seq: int
    t_mono: float
    t_wall: float
    run_id: str
    src: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def age_s(self, now_mono: float | None = None) -> float:
        """Age relative to the *local* monotonic clock.

        Only meaningful for envelopes produced on this machine, or when the
        consumer tracks a per-link clock offset (see dashboard StateStore).
        """
        return (now_mono if now_mono is not None else time.monotonic()) - self.t_mono


def make_envelope(msg_type: str, payload: Dict[str, Any], *, seq: int, run_id: str,
                  src: str, t_mono: float | None = None,
                  t_wall: float | None = None) -> Envelope:
    return Envelope(
        v=PROTOCOL_VERSION,
        seq=seq,
        t_mono=time.monotonic() if t_mono is None else t_mono,
        t_wall=time.time() if t_wall is None else t_wall,
        run_id=run_id,
        src=src,
        type=msg_type,
        payload=payload,
    )


def encode(env: Envelope) -> bytes:
    return msgpack.packb({
        'v': env.v, 'seq': env.seq, 't_mono': env.t_mono, 't_wall': env.t_wall,
        'run_id': env.run_id, 'src': env.src, 'type': env.type,
        'payload': env.payload,
    }, use_bin_type=True)


def decode(raw: bytes) -> Envelope:
    try:
        obj = msgpack.unpackb(raw, raw=False)
    except Exception as exc:  # malformed bytes, truncation, wrong codec…
        raise ProtocolError(f'undecodable message: {exc}') from exc
    if not isinstance(obj, dict):
        raise ProtocolError(f'expected map, got {type(obj).__name__}')
    missing = [k for k in _REQUIRED_FIELDS if k not in obj]
    if missing:
        raise ProtocolError(f'missing fields: {missing}')
    if obj['v'] != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {obj['v']} "
                            f'(speaking {PROTOCOL_VERSION})')
    return Envelope(**{k: obj[k] for k in _REQUIRED_FIELDS})


class SeqTracker:
    """Detects gaps/duplicates in a per-channel sequence stream."""

    def __init__(self):
        self.last_seq: int | None = None
        self.received = 0
        self.gaps = 0          # number of gap EVENTS
        self.lost = 0          # total messages missing
        self.duplicates = 0

    def feed(self, seq: int) -> int:
        """Record one arrival. Returns messages lost since the previous one."""
        self.received += 1
        if self.last_seq is None:
            self.last_seq = seq
            return 0
        delta = seq - self.last_seq
        lost = 0
        if delta == 1:
            pass
        elif delta > 1:
            lost = delta - 1
            self.gaps += 1
            self.lost += lost
        else:  # restart of the sender (seq reset) or duplicate
            if delta == 0:
                self.duplicates += 1
            # seq went backwards → treat as sender restart, not loss
        self.last_seq = seq
        return lost

    def loss_ratio(self) -> float:
        total = self.received + self.lost
        return (self.lost / total) if total else 0.0
