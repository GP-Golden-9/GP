"""Fleet rail — one live card per robot: role, stream LEDs, pose, vitals
summary, quick actions. The whole fleet at a glance, always visible."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from gpcore.protocol.channels import Staleness
from ui import theme

ROLE = {'robot1': 'MAPPER', 'robot2': 'INTERVENER', 'robot3': 'INSPECTOR'}
LED = {Staleness.FRESH: theme.GOOD, Staleness.STALE: theme.WARN,
       Staleness.DEAD: theme.BAD}


class RobotCard(QFrame):
    activateClicked = Signal(str)
    locateClicked = Signal(str)

    def __init__(self, prof, parent=None):
        super().__init__(parent)
        self.prof = prof
        self.setStyleSheet(
            f'QFrame{{background:{theme.SURFACE_2}; border:1px solid {theme.BORDER};'
            'border-radius:10px;}} QLabel{border:none;}')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 9)
        lay.setSpacing(5)

        head = QHBoxLayout()
        self.name_lbl = QLabel(f'<b>{prof.name}</b>')
        self.name_lbl.setStyleSheet('font-size:13px;')
        head.addWidget(self.name_lbl)
        role = QLabel(ROLE.get(prof.id, prof.kind.upper()))
        role.setStyleSheet(f'color:{theme.MUTED}; font-size:9px; '
                           'font-weight:700; letter-spacing:1px;')
        head.addWidget(role)
        head.addStretch(1)
        self.active_tag = QLabel('ACTIVE')
        self.active_tag.setStyleSheet(
            f'color:{theme.ACCENT}; font-size:9px; font-weight:800; '
            f'letter-spacing:1px; border:1px solid {theme.ACCENT}; '
            'border-radius:6px; padding:1px 6px;')
        self.active_tag.hide()
        head.addWidget(self.active_tag)
        lay.addLayout(head)

        host = QLabel(prof.host)
        host.setStyleSheet(f'color:{theme.MUTED}; font-family:{theme.MONO}; '
                           'font-size:10px;')
        lay.addWidget(host)

        leds = QHBoxLayout()
        leds.setSpacing(8)
        self._leds: dict[str, QLabel] = {}
        for key, label in (('cmd', 'LINK'), ('telemetry', 'TELE'),
                           ('video', 'VID'), ('map', 'MAP'), ('scan', 'LIDAR')):
            lbl = QLabel(f'<span style="color:{theme.BAD}">●</span> {label}')
            lbl.setStyleSheet('font-size:9px; font-weight:700; '
                              f'color:{theme.MUTED}; letter-spacing:1px;')
            self._leds[key] = lbl
            leds.addWidget(lbl)
        leds.addStretch(1)
        lay.addLayout(leds)

        grid = QGridLayout()
        grid.setVerticalSpacing(2)
        grid.setHorizontalSpacing(10)
        self._fields: dict[str, QLabel] = {}
        for col, (key, label) in enumerate((('pose', 'POSE'), ('vital', 'VITALS'))):
            cap = QLabel(label)
            cap.setStyleSheet(f'color:{theme.MUTED}; font-size:8px; '
                              'font-weight:700; letter-spacing:1px;')
            val = QLabel('—')
            val.setStyleSheet(f'font-family:{theme.MONO}; font-size:10px;')
            grid.addWidget(cap, 0, col)
            grid.addWidget(val, 1, col)
            self._fields[key] = val
        lay.addLayout(grid)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        take = QPushButton('CONTROL')
        take.setFocusPolicy(Qt.NoFocus)
        take.setStyleSheet('font-size:10px; padding:3px 10px;')
        take.clicked.connect(lambda: self.activateClicked.emit(prof.id))
        locate = QPushButton('LOCATE')
        locate.setFocusPolicy(Qt.NoFocus)
        locate.setStyleSheet('font-size:10px; padding:3px 10px;')
        locate.clicked.connect(lambda: self.locateClicked.emit(prof.id))
        actions.addWidget(take)
        actions.addWidget(locate)
        actions.addStretch(1)
        self.align_lbl = QLabel('')
        self.align_lbl.setStyleSheet(f'color:{theme.WARN}; font-size:9px; '
                                     'font-weight:700;')
        actions.addWidget(self.align_lbl)
        lay.addLayout(actions)

    # ── updates ───────────────────────────────────────────────────────────
    def set_active(self, active: bool) -> None:
        self.active_tag.setVisible(active)
        border = theme.ACCENT if active else theme.BORDER
        self.setStyleSheet(
            f'QFrame{{background:{theme.SURFACE_2}; border:1px solid {border};'
            'border-radius:10px;}} QLabel{border:none;}')

    def set_staleness(self, staleness: dict) -> None:
        for key, lbl in self._leds.items():
            st = staleness.get(key)
            if st is None:
                continue
            color = LED.get(st, theme.BAD)
            label = lbl.text().split('</span> ', 1)[-1]
            lbl.setText(f'<span style="color:{color}">●</span> {label}')

    def set_pose(self, x: float, y: float, th_deg: float, aligned: bool) -> None:
        self._fields['pose'].setText(f'{x:+.2f}, {y:+.2f} · {th_deg:+.0f}°')
        self.align_lbl.setText('' if aligned else '⌖ NOT ALIGNED')

    def set_vitals(self, text: str, warn: bool) -> None:
        self._fields['vital'].setText(text)
        self._fields['vital'].setStyleSheet(
            f'font-family:{theme.MONO}; font-size:10px; '
            f'color:{theme.BAD if warn else theme.TEXT};')


class FleetPanel(QWidget):
    activateClicked = Signal(str)
    locateClicked = Signal(str)

    def __init__(self, robots, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.cards: dict[str, RobotCard] = {}
        for prof in robots:
            card = RobotCard(prof)
            card.activateClicked.connect(self.activateClicked)
            card.locateClicked.connect(self.locateClicked)
            self.cards[prof.id] = card
            lay.addWidget(card)
        lay.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def set_active(self, robot_id: str) -> None:
        for rid, card in self.cards.items():
            card.set_active(rid == robot_id)
