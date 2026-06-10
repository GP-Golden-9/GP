"""StateStore — the single writer of application state (UI thread).

Transport threads emit signals; the store consumes them, updates per-stream
freshness, and re-emits compact change signals for views. Views never read
transport objects directly.

Staleness: a 250 ms sweep classifies every stream FRESH/STALE/DEAD from its
arrival age (gpcore.protocol.channels thresholds). Video frame age uses a
per-link clock-offset estimate so the badge shows true capture-to-display
latency, not just arrival age.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from gpcore.protocol.channels import Staleness, classify_age
from gpcore.protocol.envelope import SeqTracker

STREAMS = ('telemetry', 'scan', 'map', 'health', 'video', 'cmd')


@dataclass
class StreamHealth:
    last_arrival_mono: float = 0.0
    tracker: SeqTracker = field(default_factory=SeqTracker)
    rate_ewma_hz: float = 0.0
    staleness: Staleness = Staleness.DEAD

    def touch(self, seq: Optional[int] = None) -> None:
        now = time.monotonic()
        if self.last_arrival_mono:
            dt = max(1e-3, now - self.last_arrival_mono)
            inst = 1.0 / dt
            self.rate_ewma_hz = (0.8 * self.rate_ewma_hz + 0.2 * inst
                                 if self.rate_ewma_hz else inst)
        self.last_arrival_mono = now
        if seq is not None:
            self.tracker.feed(seq)

    def age_s(self) -> float:
        if not self.last_arrival_mono:
            return float('inf')
        return time.monotonic() - self.last_arrival_mono


class RobotState(QObject):
    """Live state of one robot, fed by its link; one instance per robot."""

    telemetryChanged = Signal(dict)            # latest tele.full payload
    scanChanged = Signal(dict)                 # latest tele.scan payload
    mapChanged = Signal(dict)                  # latest map.grid payload
    healthChanged = Signal(dict)               # latest health payload
    logLine = Signal(str)                      # robot-side log.event lines
    stalenessChanged = Signal(dict)            # {stream: Staleness}
    estopChanged = Signal(bool)

    def __init__(self, robot_id: str, parent=None):
        super().__init__(parent)
        self.robot_id = robot_id
        self.streams: Dict[str, StreamHealth] = {s: StreamHealth() for s in STREAMS}
        self.telemetry: dict = {}
        self.scan: dict = {}
        self.map_grid: dict = {}
        self.health: dict = {}
        self.estop = False
        self.run_id_seen = ''
        # capture-clock offset: min(recv_local − cap_t_mono) over recent frames
        self._video_offset: Optional[float] = None

        self._sweep = QTimer(self)
        self._sweep.setInterval(250)
        self._sweep.timeout.connect(self._sweep_staleness)
        self._sweep.start()
        self._last_staleness: dict = {}

    # ── transport feed (queued-connection slots) ──────────────────────────
    def on_telemetry(self, env) -> None:
        self.streams['telemetry'].touch(env.seq)
        self.telemetry = env.payload
        self.run_id_seen = env.run_id
        estop = bool(env.payload.get('estop', False))
        if estop != self.estop:
            self.estop = estop
            self.estopChanged.emit(estop)
        self.telemetryChanged.emit(env.payload)

    def on_scan(self, env) -> None:
        self.streams['scan'].touch(env.seq)
        self.scan = env.payload
        self.scanChanged.emit(env.payload)

    def on_map(self, env) -> None:
        self.streams['map'].touch(env.seq)
        self.map_grid = env.payload
        self.mapChanged.emit(env.payload)

    def on_health(self, env) -> None:
        self.streams['health'].touch()
        if env.type == 'log.event':
            self.logLine.emit(str(env.payload.get('line', '')))
            return
        self.health = env.payload
        self.healthChanged.emit(env.payload)

    def on_video_meta(self, env) -> None:
        st = self.streams['video']
        st.touch(env.seq)
        cap = env.payload.get('cap_t_mono')
        if isinstance(cap, (int, float)):
            offset = time.monotonic() - cap
            if self._video_offset is None:
                self._video_offset = offset
            else:                       # min-tracking with slow decay upward
                self._video_offset = min(self._video_offset * 1.0005, offset)

    def on_cmd_ack(self) -> None:
        self.streams['cmd'].touch()

    # ── queries for views ─────────────────────────────────────────────────
    def video_frame_age_s(self, cap_t_mono: float) -> Optional[float]:
        if self._video_offset is None:
            return None
        return max(0.0, time.monotonic() - (cap_t_mono + self._video_offset))

    def staleness(self, stream: str) -> Staleness:
        return self.streams[stream].staleness

    # ── periodic ──────────────────────────────────────────────────────────
    def _sweep_staleness(self) -> None:
        current = {}
        for name, sh in self.streams.items():
            sh.staleness = classify_age(sh.age_s())
            current[name] = sh.staleness
        if current != self._last_staleness:
            self._last_staleness = dict(current)
            self.stalenessChanged.emit(current)
