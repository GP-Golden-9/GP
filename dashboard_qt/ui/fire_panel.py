"""FIRE TEST panel — place a fire on the map, send Beta there autonomously.

Deliberately minimal (replaces the old master/slave mission):
  1. PLACE FIRE  → click the map to drop the fire point.
  2. GO TO FIRE  → Beta plans the optimal route over Alpha's shared map and
                   drives there, dodging unmapped obstacles with its
                   ultrasonics (the real autonomous nav stack).
  3. STOP        → halt and disarm at any time.
Status shows IDLE / EN ROUTE / ARRIVED / NO PATH / BLOCKED / STOPPED.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ui import theme
from ui.bottom_panel import LogConsole

_KIND_COLOR = {
    'idle': theme.MUTED, 'muted': theme.MUTED,
    'accent': theme.ACCENT, 'good': theme.GOOD,
    'warn': theme.WARN, 'bad': theme.BAD,
}


class FirePanel(QWidget):
    scanRequested = Signal()           # cover the mapped area + return to base
    placeFireRequested = Signal()      # arm: next map click drops the fire
    goRequested = Signal()             # navigate to fire -> pump 5s -> return
    stopRequested = Signal()           # stop + disarm

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(12)

        title = QLabel('AUTONOMY - BETA')
        title.setStyleSheet('font-size:15px; font-weight:800; letter-spacing:2px;')
        root.addWidget(title)

        sub = QLabel('Two independent autonomous actions over Alpha\'s map. '
                     'Beta follows the suggested path but its ultrasonics let '
                     'it deviate around obstacles and merge back.')
        sub.setWordWrap(True)
        sub.setStyleSheet(f'color:{theme.MUTED}; font-size:11px;')
        root.addWidget(sub)

        # ── SCAN: cover the area + return to base ──
        self.btn_scan = QPushButton('SCAN AREA   (cover map, return to base)')
        self.btn_scan.setFocusPolicy(Qt.NoFocus)
        self.btn_scan.setMinimumHeight(44)
        self.btn_scan.setStyleSheet(
            f'font-weight:800; font-size:13px; background:{theme.ACCENT}; '
            'color:#06210f;')
        self.btn_scan.clicked.connect(self.scanRequested)
        root.addWidget(self.btn_scan)

        sep = QLabel('-  or  -')
        sep.setAlignment(Qt.AlignCenter)
        sep.setStyleSheet(f'color:{theme.MUTED}; font-size:10px;')
        root.addWidget(sep)

        # ── step 1: place fire ──
        self.btn_place = QPushButton('1.  PLACE FIRE   (then click the map)')
        self.btn_place.setCheckable(True)
        self.btn_place.setFocusPolicy(Qt.NoFocus)
        self.btn_place.setMinimumHeight(40)
        self.btn_place.clicked.connect(self.placeFireRequested)
        root.addWidget(self.btn_place)

        self.fire_lbl = QLabel('fire: not placed')
        self.fire_lbl.setStyleSheet(f'font-family:{theme.MONO}; font-size:12px; '
                                    f'color:{theme.MUTED};')
        root.addWidget(self.fire_lbl)

        # ── step 2: go / stop ──
        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.btn_go = QPushButton('2.  GO TO FIRE  ->  PUMP 5s  ->  RETURN')
        self.btn_go.setEnabled(False)
        self.btn_go.setFocusPolicy(Qt.NoFocus)
        self.btn_go.setMinimumHeight(46)
        self.btn_go.setStyleSheet(
            f'font-weight:800; font-size:14px; background:{theme.GOOD}; '
            'color:#06210f;')
        self.btn_go.clicked.connect(self.goRequested)
        self.btn_stop = QPushButton('STOP')
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFocusPolicy(Qt.NoFocus)
        self.btn_stop.setMinimumHeight(46)
        self.btn_stop.setStyleSheet(
            f'font-weight:800; font-size:14px; background:{theme.BAD}; '
            'color:#2a0a0a;')
        self.btn_stop.clicked.connect(self.stopRequested)
        ctl.addWidget(self.btn_go, 2)
        ctl.addWidget(self.btn_stop, 1)
        root.addLayout(ctl)

        # ── status ──
        self.status = QLabel('IDLE')
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setMinimumHeight(34)
        self._paint_status('IDLE', 'idle')
        root.addWidget(self.status)

        cap = QLabel('NAV LOG')
        cap.setStyleSheet(f'color:{theme.MUTED}; font-size:9px; '
                          'font-weight:700; letter-spacing:1px;')
        root.addWidget(cap)
        self.log = LogConsole()
        root.addWidget(self.log, 1)

    # ── API (driven by main_window) ───────────────────────────────────────
    def set_placing(self, on: bool) -> None:
        self.btn_place.setChecked(on)
        self.btn_place.setText('1.  CLICK THE MAP...' if on
                               else '1.  PLACE FIRE   (then click the map)')

    def set_fire(self, x: float, y: float) -> None:
        self.fire_lbl.setText(f'fire: ({x:+.2f}, {y:+.2f}) m')
        self.fire_lbl.setStyleSheet(f'font-family:{theme.MONO}; font-size:12px; '
                                    f'color:{theme.MARKER_FIRE}; font-weight:700;')
        self.btn_go.setEnabled(True)

    def set_running(self, running: bool) -> None:
        self.btn_go.setEnabled(not running and 'not placed'
                               not in self.fire_lbl.text())
        self.btn_stop.setEnabled(running)
        self.btn_place.setEnabled(not running)
        self.btn_scan.setEnabled(not running)

    def set_status(self, text: str, kind: str = 'idle') -> None:
        self._paint_status(text, kind)

    def log_line(self, line: str) -> None:
        self.log.append_line(line, source='local')

    def _paint_status(self, text: str, kind: str) -> None:
        col = _KIND_COLOR.get(kind, theme.TEXT)
        self.status.setText(text)
        self.status.setStyleSheet(
            f'color:{col}; font-family:{theme.MONO}; font-size:15px; '
            f'font-weight:800; letter-spacing:1px; '
            f'border:1px solid {col}; border-radius:8px;')
