"""Channel/port map and staleness model — one scheme for every robot."""

from __future__ import annotations

import enum

# ── ZMQ ports (identical on every robot host) ─────────────────────────────
PORT_VIDEO_LEGACY = 5555   # raw JPEG PUB (tcp_rasp_zmq.py) — retired after Qt parity
PORT_TELEMETRY    = 5556   # PUB: tele.full @ 20 Hz, tele.scan @ scan rate
PORT_MAP          = 5557   # PUB: map.grid @ ~1 Hz (zlib int8 grid)
PORT_COMMAND      = 5558   # ROUTER (robot) ↔ DEALER (laptop), ACKed commands
PORT_HEALTH       = 5559   # PUB: health @ 1 Hz
PORT_VIDEO        = 5560   # PUB multipart: [envelope(video.meta), jpeg bytes]

# ── Other well-known ports ────────────────────────────────────────────────
PORT_ROSBRIDGE = 9090      # legacy dashboard path (fallback during migration)
PORT_DASHBOARD = 8080      # NiceGUI legacy dashboard

# ── Message types ─────────────────────────────────────────────────────────
TELE_FULL  = 'tele.full'
TELE_SCAN  = 'tele.scan'
MAP_GRID   = 'map.grid'
HEALTH     = 'health'
VIDEO_META = 'video.meta'
LOG_EVENT  = 'log.event'
ACK        = 'ack'

# ── Staleness model (consumer side) ───────────────────────────────────────
FRESH_BELOW_S = 2.5
STALE_BELOW_S = 5.0


class Staleness(enum.Enum):
    FRESH = 'fresh'
    STALE = 'stale'
    DEAD = 'dead'


def classify_age(age_s: float) -> Staleness:
    if age_s < FRESH_BELOW_S:
        return Staleness.FRESH
    if age_s < STALE_BELOW_S:
        return Staleness.STALE
    return Staleness.DEAD
