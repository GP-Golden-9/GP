"""Alert engine — turns raw signals (YOLO detections, gas flags) into
operator-grade alarms with debounce, latch, acknowledge and drill support.

Lifecycle per alert kind (FIRE, GAS):

    CLEAR ──(raise condition met)──▶ ACTIVE ──(operator ACK)──▶ ACKED
      ▲                                │                          │
      └────────(no positive signal for CLEAR_AFTER_S)─────────────┘

Raise conditions are deliberately debounced — one noisy frame must never
fire the alarm, and one missed frame must never silence a real fire:

    FIRE  ≥ RAISE_HITS detections above CONF_MIN within RAISE_WINDOW_S
    GAS   ≥ GAS_RAISE_HITS consecutive alarm-flagged telemetry polls

A *drill* raises a clearly-labeled synthetic alert (F9 in the console) so
the team can rehearse the response — standard practice for alarm systems.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from PySide6.QtCore import QObject, QTimer, Signal


class AlertKind(str, Enum):
    FIRE = 'FIRE'
    GAS = 'GAS'


class AlertState(str, Enum):
    CLEAR = 'CLEAR'
    ACTIVE = 'ACTIVE'
    ACKED = 'ACKED'


# ── Tuning ────────────────────────────────────────────────────────────────
FIRE_LABELS = ('fire', 'smoke', 'flame')
FIRE_CONF_MIN = 0.50
FIRE_RAISE_HITS = 3
FIRE_RAISE_WINDOW_S = 2.0
GAS_RAISE_HITS = 2
CLEAR_AFTER_S = 5.0
SWEEP_PERIOD_MS = 500


@dataclass
class _KindTracker:
    state: AlertState = AlertState.CLEAR
    hits: deque = field(default_factory=lambda: deque(maxlen=32))
    consecutive: int = 0
    last_positive: float = 0.0
    info: dict = field(default_factory=dict)


class AlertManager(QObject):
    """Single source of truth for alarm state. Views render it; they never
    decide it."""

    alertRaised = Signal(str, dict)     # kind, info{robot, label, confidence, drill, t_wall}
    alertAcked = Signal(str)            # kind
    alertCleared = Signal(str)          # kind
    logEvent = Signal(str)              # human line for the incident log

    def __init__(self, parent=None):
        super().__init__(parent)
        self._k: dict[AlertKind, _KindTracker] = {k: _KindTracker() for k in AlertKind}
        self._sweep = QTimer(self)
        self._sweep.setInterval(SWEEP_PERIOD_MS)
        self._sweep.timeout.connect(self._sweep_clears)
        self._sweep.start()

    # ── inputs ────────────────────────────────────────────────────────────
    def process_fire_detections(self, robot_id: str,
                                detections: list[tuple[str, float]]) -> None:
        """Feed every annotated frame's (label, confidence) list."""
        best = None
        for label, conf in detections or ():
            if conf >= FIRE_CONF_MIN and any(t in label.lower() for t in FIRE_LABELS):
                if best is None or conf > best[1]:
                    best = (label, conf)
        if best is None:
            return
        now = time.monotonic()
        tr = self._k[AlertKind.FIRE]
        tr.last_positive = now
        tr.hits.append(now)
        recent = sum(1 for t in tr.hits if now - t <= FIRE_RAISE_WINDOW_S)
        if tr.state is AlertState.CLEAR and recent >= FIRE_RAISE_HITS:
            self._raise(AlertKind.FIRE, {
                'robot': robot_id, 'label': best[0],
                'confidence': round(best[1] * 100), 'drill': False,
            })
        elif tr.state is not AlertState.CLEAR:
            tr.info['confidence'] = max(tr.info.get('confidence', 0),
                                        round(best[1] * 100))

    def process_gas(self, robot_id: str, alarm_flag: bool, value=None) -> None:
        """Feed every robot3 telemetry poll's alarm flag."""
        tr = self._k[AlertKind.GAS]
        if not alarm_flag:
            tr.consecutive = 0
            return
        now = time.monotonic()
        tr.last_positive = now
        tr.consecutive += 1
        if tr.state is AlertState.CLEAR and tr.consecutive >= GAS_RAISE_HITS:
            self._raise(AlertKind.GAS, {
                'robot': robot_id, 'label': 'gas leak',
                'confidence': value, 'drill': False,
            })

    # ── operator actions ──────────────────────────────────────────────────
    def acknowledge(self, kind: str) -> None:
        tr = self._k[AlertKind(kind)]
        if tr.state is AlertState.ACTIVE:
            tr.state = AlertState.ACKED
            self.alertAcked.emit(kind)
            self.logEvent.emit(f'ALERT acknowledged: {kind}')

    def drill(self, kind: str = 'FIRE') -> None:
        """Synthetic, clearly-labeled alert for response rehearsal (F9)."""
        tr = self._k[AlertKind(kind)]
        tr.last_positive = time.monotonic()
        if tr.state is AlertState.CLEAR:
            self._raise(AlertKind(kind), {
                'robot': 'drill', 'label': f'{kind.lower()} drill',
                'confidence': 100, 'drill': True,
            })

    def state(self, kind: str) -> AlertState:
        return self._k[AlertKind(kind)].state

    # ── internals ─────────────────────────────────────────────────────────
    def _raise(self, kind: AlertKind, info: dict) -> None:
        tr = self._k[kind]
        tr.state = AlertState.ACTIVE
        info['t_wall'] = time.strftime('%H:%M:%S')
        tr.info = info
        self.alertRaised.emit(kind.value, info)
        tag = ' [DRILL]' if info.get('drill') else ''
        conf = info.get('confidence')
        conf_txt = f' conf {conf}%' if isinstance(conf, int) else ''
        self.logEvent.emit(
            f'ALERT {kind.value}{tag}: {info.get("label")} on '
            f'{info.get("robot")}{conf_txt}')

    def _sweep_clears(self) -> None:
        now = time.monotonic()
        for kind, tr in self._k.items():
            if (tr.state is not AlertState.CLEAR
                    and now - tr.last_positive > CLEAR_AFTER_S):
                tr.state = AlertState.CLEAR
                tr.hits.clear()
                tr.consecutive = 0
                self.alertCleared.emit(kind.value)
                self.logEvent.emit(f'ALERT cleared: {kind.value}')
