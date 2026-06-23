"""MASTER MISSION panel — the guided Alpha→Beta demo.

Centralized by design: the laptop runs everything; the "robot1 (Alpha) sends an
order to robot2 (Beta)" messages are SIMULATED in this panel's log (no real
robot-to-robot link). One context button walks the operator through the steps:

    START → Alpha maps → (operator: MAPPING DONE) → Alpha asks to send Beta to
    scan → (operator: CONFIRM) → suggested path shown for review/edit →
    (operator: START SCAN) → Beta scans + detects + returns → Alpha moves in to
    the fire → (operator: place fire + CONFIRM) → Alpha drives → pump 10 s →
    returns → done.

ABORT stops everything at any step. The actual driving reuses the AUTONOMY
SCAN/FIRE flows; this panel only orchestrates + narrates.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from ui import theme
from ui.bottom_panel import LogConsole

_KIND = {'accent': theme.ACCENT, 'good': theme.GOOD,
         'warn': theme.WARN, 'bad': theme.BAD, 'idle': theme.MUTED}


class MissionPanel(QWidget):
    actionClicked = Signal()      # the single context button (advances the flow)
    stepDoneClicked = Signal()    # operator force-completes the current step
    abortClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 14)
        root.setSpacing(10)

        title = QLabel('MASTER MISSION - ALPHA -> BETA')
        title.setStyleSheet('font-size:15px; font-weight:800; letter-spacing:2px;')
        root.addWidget(title)

        sub = QLabel("Centralized demo: the laptop runs everything; the "
                     "robot1 -> robot2 orders are simulated in the log below.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f'color:{theme.MUTED}; font-size:11px;')
        root.addWidget(sub)

        # Alpha's current prompt / step instruction
        self.prompt = QLabel('Press START MISSION to begin.')
        self.prompt.setWordWrap(True)
        self.prompt.setMinimumHeight(56)
        self.prompt.setAlignment(Qt.AlignCenter)
        root.addWidget(self.prompt)
        self._paint('Press START MISSION to begin.', 'accent')

        ctl = QHBoxLayout()
        ctl.setSpacing(10)
        self.btn_action = QPushButton('START MISSION')
        self.btn_action.setFocusPolicy(Qt.NoFocus)
        self.btn_action.setMinimumHeight(50)
        self.btn_action.setStyleSheet(
            f'font-weight:800; font-size:14px; background:{theme.GOOD}; '
            'color:#06210f;')
        self.btn_action.clicked.connect(self.actionClicked)
        self.btn_abort = QPushButton('ABORT')
        self.btn_abort.setFocusPolicy(Qt.NoFocus)
        self.btn_abort.setMinimumHeight(50)
        self.btn_abort.setStyleSheet(
            f'font-weight:800; font-size:13px; background:{theme.BAD}; '
            'color:#2a0a0a;')
        self.btn_abort.clicked.connect(self.abortClicked)
        ctl.addWidget(self.btn_action, 2)
        ctl.addWidget(self.btn_abort, 1)
        root.addLayout(ctl)

        # Operator override: mark the current step done and move on. Lets the
        # demo proceed when Beta doesn't perfectly finish (drift / stuck) — or
        # to skip a step entirely.
        self.btn_done = QPushButton('STEP DONE  ->  NEXT')
        self.btn_done.setFocusPolicy(Qt.NoFocus)
        self.btn_done.setMinimumHeight(38)
        self.btn_done.setToolTip('Mark the current step complete and advance '
                                 '(stops the robot if it is driving)')
        self.btn_done.clicked.connect(self.stepDoneClicked)
        root.addWidget(self.btn_done)

        cap = QLabel('MASTER -> SLAVE LOG')
        cap.setStyleSheet(f'color:{theme.MUTED}; font-size:9px; '
                          'font-weight:700; letter-spacing:1px;')
        root.addWidget(cap)
        self.log = LogConsole()
        root.addWidget(self.log, 1)

    # ── API (driven by main_window orchestrator) ──────────────────────────
    def set_step(self, prompt: str, button_label: str, *,
                 enabled: bool = True, kind: str = 'accent') -> None:
        self._paint(prompt, kind)
        self.btn_action.setText(button_label)
        self.btn_action.setEnabled(enabled)

    def log_line(self, line: str) -> None:
        self.log.append_line(line, source='local')

    def _paint(self, text: str, kind: str) -> None:
        col = _KIND.get(kind, theme.TEXT)
        self.prompt.setText(text)
        self.prompt.setStyleSheet(
            f'color:{col}; font-family:{theme.MONO}; font-size:13px; '
            f'font-weight:700; border:1px solid {col}; border-radius:8px; '
            f'padding:8px;')
