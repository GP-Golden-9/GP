"""Top command bar: brand · robot pills with live status dots · AI model ·
ALL STOP · link/run chips · clock · exit.

Robot pills replace a combo box: one glance shows every robot's link state,
one click switches the active robot — fleet-console pattern.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QComboBox, QLabel, QPushButton, QSizePolicy,
                               QToolBar, QWidget)

from ui import theme
from ui.theme import chip


def _dot_icon(color: str) -> QIcon:
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(2, 2, 8, 8)
    p.end()
    return QIcon(pm)


class CommandBar(QToolBar):
    robotSelected = Signal(str)
    modelSelected = Signal(str)        # path
    allStop = Signal()
    exitRequested = Signal()

    def __init__(self, robots, models: list[tuple[str, str]],
                 default_model: str, run_id: str, parent=None):
        super().__init__('Command', parent)
        self.setObjectName('commandBar')   # required for saveState/restoreState
        self.setMovable(False)

        title = QLabel('GP <b>OPERATIONS</b> CENTER')
        title.setObjectName('appTitle')
        self.addWidget(title)

        self._pills: dict[str, QPushButton] = {}
        self._link: dict[str, bool | None] = {}
        for prof in robots:
            pill = QPushButton(prof.name)
            pill.setObjectName('robotPill')
            pill.setIcon(_dot_icon(theme.MUTED))
            pill.setCheckable(True)
            pill.setFocusPolicy(Qt.NoFocus)
            pill.setToolTip(f'{prof.id} · {prof.host} · '
                            f'{"ESP32/HTTP" if prof.is_esp32 else "ROS gateway"}')
            pill.clicked.connect(lambda _=False, rid=prof.id: self._pick(rid))
            self.addWidget(pill)
            self._pills[prof.id] = pill
            self._link[prof.id] = None

        spacer1 = QWidget()
        spacer1.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.addWidget(spacer1)

        lbl = QLabel('AI MODEL ')
        lbl.setStyleSheet(f'color:{theme.MUTED}; font-size:10px; '
                          'font-weight:700; letter-spacing:2px;')
        self.addWidget(lbl)
        self.model_combo = QComboBox()
        for name, path in models:
            self.model_combo.addItem(name, path)
        idx = self.model_combo.findText(default_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.currentIndexChanged.connect(
            lambda _i: self.modelSelected.emit(self.model_combo.currentData()))
        self.addWidget(self.model_combo)

        self.link_chip = chip('LINK …')
        self.addWidget(self.link_chip)
        self.addWidget(chip(f'run {run_id}'))
        self.clock = chip('--:--:--')
        self.addWidget(self.clock)
        clock_timer = QTimer(self)
        clock_timer.setInterval(1000)
        clock_timer.timeout.connect(
            lambda: self.clock.setText(time.strftime('%H:%M:%S')))
        clock_timer.start()

        allstop = QPushButton('■ ALL STOP')
        allstop.setObjectName('allStopBtn')
        allstop.setFocusPolicy(Qt.NoFocus)
        allstop.setToolTip('Emergency stop EVERY robot (latched)')
        allstop.clicked.connect(self.allStop.emit)
        self.addWidget(allstop)

        exit_btn = QPushButton('EXIT')
        exit_btn.setObjectName('exitBtn')
        exit_btn.setFocusPolicy(Qt.NoFocus)
        exit_btn.clicked.connect(self.exitRequested.emit)
        self.addWidget(exit_btn)

    # ── state in ──────────────────────────────────────────────────────────
    def set_active(self, robot_id: str) -> None:
        for rid, pill in self._pills.items():
            pill.setChecked(rid == robot_id)

    def set_robot_link(self, robot_id: str, up: bool | None) -> None:
        self._link[robot_id] = up
        pill = self._pills.get(robot_id)
        if pill is None:
            return
        color = theme.MUTED if up is None else (theme.GOOD if up else theme.BAD)
        pill.setIcon(_dot_icon(color))

    def set_active_link_chip(self, up: bool) -> None:
        self.link_chip.setText('●  LINK UP' if up else '●  LINK DOWN')
        self.link_chip.setStyleSheet(
            f'color:{theme.GOOD};' if up else f'color:{theme.BAD};')

    def _pick(self, robot_id: str) -> None:
        self.set_active(robot_id)
        self.robotSelected.emit(robot_id)
