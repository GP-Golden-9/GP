"""MISSION tab — the master/slave demo control + command-log view.

Drives MasterMission (a pure simulation) and shows the mocked master→slave
command log, a phase stepper, status pills, and the operator controls
(START / NEXT PHASE / AUTO·MANUAL / ABORT). No real robot is touched.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ui import theme
from ui.bottom_panel import LogConsole
from ui.master_mission import MasterMission

_STATUS_COLOR = {
    'IDLE': theme.MUTED, 'OFFLINE': theme.MUTED, 'OFF': theme.MUTED,
    'ONLINE': theme.GOOD, 'AT BASE': theme.GOOD, 'DONE': theme.GOOD,
    'MAPPING': theme.ACCENT, 'RETURNING': theme.ACCENT,
    'NAVIGATING': theme.ACCENT, 'SCANNED': theme.ACCENT,
    'PUMPING': theme.MARKER_FIRE, 'ON': theme.MARKER_FIRE,
}


class MissionPanel(QWidget):
    startRequested = Signal()
    nextRequested = Signal()
    abortRequested = Signal()
    autoChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel('MASTER / SLAVE  MISSION')
        title.setStyleSheet('font-size:14px; font-weight:800; '
                            'letter-spacing:2px;')
        head.addWidget(title)
        head.addStretch(1)
        self.btn_auto = QPushButton('AUTO')
        self.btn_auto.setCheckable(True)
        self.btn_auto.setChecked(True)
        self.btn_auto.setFocusPolicy(Qt.NoFocus)
        self.btn_auto.setStyleSheet('font-size:11px; padding:4px 14px;')
        self.btn_auto.toggled.connect(self._auto_toggled)
        head.addWidget(self.btn_auto)
        root.addLayout(head)

        # ── phase stepper ──
        self._steps: dict[str, QLabel] = {}
        stepper = QHBoxLayout()
        stepper.setSpacing(6)
        for i, ph in enumerate(MasterMission.PHASES):
            if i:
                arrow = QLabel('>')
                arrow.setStyleSheet(f'color:{theme.MUTED};')
                stepper.addWidget(arrow)
            lbl = QLabel(ph)
            lbl.setAlignment(Qt.AlignCenter)
            self._steps[ph] = lbl
            stepper.addWidget(lbl)
        stepper.addStretch(1)
        root.addLayout(stepper)
        self._set_step('')

        # ── status pills ──
        pills = QHBoxLayout()
        pills.setSpacing(8)
        self._pills: dict[str, QLabel] = {}
        for key, cap in (('alpha', 'ALPHA'), ('beta', 'BETA'),
                         ('link', 'MASTER-SLAVE'), ('pump', 'PUMP')):
            box = QLabel()
            box.setStyleSheet('')
            self._pills[key] = box
            pills.addWidget(self._make_pill_frame(cap, box))
        pills.addStretch(1)
        root.addLayout(pills)
        self.set_status({'alpha': 'IDLE', 'beta': 'IDLE',
                         'link': 'OFFLINE', 'pump': 'OFF'})

        # ── controls ──
        ctl = QHBoxLayout()
        ctl.setSpacing(8)
        self.btn_start = QPushButton('START MISSION')
        self.btn_next = QPushButton('NEXT PHASE >>')
        self.btn_abort = QPushButton('ABORT / OVERRIDE')
        for b in (self.btn_start, self.btn_next, self.btn_abort):
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(34)
        self.btn_start.setStyleSheet(
            f'font-weight:800; background:{theme.GOOD}; color:#06210f;')
        self.btn_abort.setStyleSheet(
            f'font-weight:800; background:{theme.BAD}; color:#2a0a0a;')
        self.btn_start.clicked.connect(self.startRequested)
        self.btn_next.clicked.connect(self.nextRequested)
        self.btn_abort.clicked.connect(self.abortRequested)
        ctl.addWidget(self.btn_start)
        ctl.addWidget(self.btn_next)
        ctl.addWidget(self.btn_abort)
        root.addLayout(ctl)

        # ── master/slave command log ──
        cap = QLabel('MASTER -> SLAVE  COMMAND LOG')
        cap.setStyleSheet(f'color:{theme.MUTED}; font-size:9px; '
                          'font-weight:700; letter-spacing:1px;')
        root.addWidget(cap)
        self.log = LogConsole()
        root.addWidget(self.log, 1)

        self.set_running(False)

    # ── helpers ───────────────────────────────────────────────────────────
    def _make_pill_frame(self, caption: str, value_lbl: QLabel) -> QFrame:
        f = QFrame()
        f.setStyleSheet(f'QFrame{{background:{theme.SURFACE_2}; '
                        f'border:1px solid {theme.BORDER}; border-radius:8px;}} '
                        'QLabel{border:none;}')
        lay = QVBoxLayout(f)
        lay.setContentsMargins(10, 5, 10, 6)
        lay.setSpacing(1)
        c = QLabel(caption)
        c.setStyleSheet(f'color:{theme.MUTED}; font-size:8px; '
                        'font-weight:700; letter-spacing:1px;')
        value_lbl.setStyleSheet(f'font-family:{theme.MONO}; font-size:12px; '
                                'font-weight:800;')
        lay.addWidget(c)
        lay.addWidget(value_lbl)
        return f

    def _auto_toggled(self, on: bool) -> None:
        self.btn_auto.setText('AUTO' if on else 'MANUAL')
        self.btn_next.setEnabled((not on) and self.btn_abort.isEnabled())
        self.autoChanged.emit(on)

    # ── public API (driven by main_window) ────────────────────────────────
    def set_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_abort.setEnabled(running)
        self.btn_next.setEnabled(running and not self.btn_auto.isChecked())
        if not running:
            self._set_step('')

    def log_line(self, line: str) -> None:
        self.log.append_line(line, source='local')

    def set_phase(self, phase: str) -> None:
        self._set_step(phase)

    def _set_step(self, active: str) -> None:
        for ph, lbl in self._steps.items():
            on = (ph == active)
            col = theme.ACCENT if on else theme.MUTED
            weight = '800' if on else '600'
            border = theme.ACCENT if on else theme.BORDER
            lbl.setStyleSheet(
                f'color:{col}; font-size:10px; font-weight:{weight}; '
                f'letter-spacing:1px; padding:3px 9px; '
                f'border:1px solid {border}; border-radius:8px;')

    def set_status(self, st: dict) -> None:
        for key, lbl in self._pills.items():
            val = str(st.get(key, '—'))
            col = _STATUS_COLOR.get(val, theme.TEXT)
            lbl.setText(val)
            lbl.setStyleSheet(f'color:{col}; font-family:{theme.MONO}; '
                              'font-size:12px; font-weight:800;')
