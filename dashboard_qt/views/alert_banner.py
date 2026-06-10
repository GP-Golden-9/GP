"""Full-width alert banner under the toolbar.

Hidden when all clear. While an alert is ACTIVE it pulses and offers an
ACKNOWLEDGE button; acknowledged alerts hold steady gray until the engine
clears them. FIRE outranks GAS when both are live. Pure view — all alarm
logic lives in alerts.AlertManager.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from views import theme

ICON = {'FIRE': '🔥', 'GAS': '☣'}
PULSE = {'FIRE': (theme.BANNER_FIRE_A, theme.BANNER_FIRE_B),
         'GAS': (theme.BANNER_GAS_A, theme.BANNER_GAS_B)}
PRIORITY = ('FIRE', 'GAS')
PULSE_MS = 550


class AlertBanner(QFrame):
    ackClicked = Signal(str)            # kind

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('alertBanner')
        self.hide()

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 10, 8)
        self.text = QLabel('')
        self.text.setObjectName('alertText')
        lay.addWidget(self.text, 1)
        self.ack_btn = QPushButton('ACKNOWLEDGE')
        self.ack_btn.setObjectName('ackBtn')
        self.ack_btn.setFocusPolicy(Qt.NoFocus)
        self.ack_btn.clicked.connect(self._ack)
        lay.addWidget(self.ack_btn)

        # kind → {'info': dict, 'acked': bool}
        self._alerts: dict[str, dict] = {}
        self._pulse_on = False
        self._pulse = QTimer(self)
        self._pulse.setInterval(PULSE_MS)
        self._pulse.timeout.connect(self._tick)

    # ── driven by AlertManager signals ────────────────────────────────────
    def on_raised(self, kind: str, info: dict) -> None:
        self._alerts[kind] = {'info': info, 'acked': False}
        self._render()

    def on_acked(self, kind: str) -> None:
        if kind in self._alerts:
            self._alerts[kind]['acked'] = True
            self._render()

    def on_cleared(self, kind: str) -> None:
        self._alerts.pop(kind, None)
        self._render()

    # ── internals ─────────────────────────────────────────────────────────
    def _top(self) -> str | None:
        for kind in PRIORITY:
            if kind in self._alerts:
                return kind
        return None

    def _render(self) -> None:
        kind = self._top()
        if kind is None:
            self._pulse.stop()
            self.hide()
            return

        entry = self._alerts[kind]
        info, acked = entry['info'], entry['acked']
        drill = ' · DRILL' if info.get('drill') else ''
        conf = info.get('confidence')
        conf_txt = f' · confidence {conf}%' if isinstance(conf, int) else ''
        others = len(self._alerts) - 1
        more = f'   (+{others} more)' if others else ''
        self.text.setText(
            f'{ICON.get(kind, "⚠")}  {kind} DETECTED{drill}  ·  '
            f'{info.get("robot", "?")}{conf_txt}  ·  {info.get("t_wall", "")}'
            f'{more}')
        self.ack_btn.setVisible(not acked)

        if acked:
            self._pulse.stop()
            self.setStyleSheet(theme.BANNER_ACKED)
        else:
            if not self._pulse.isActive():
                self._pulse_on = True
                self._pulse.start()
            self._apply_pulse(kind)
        self.show()

    def _tick(self) -> None:
        self._pulse_on = not self._pulse_on
        kind = self._top()
        if kind:
            self._apply_pulse(kind)

    def _apply_pulse(self, kind: str) -> None:
        a, b = PULSE.get(kind, PULSE['FIRE'])
        self.setStyleSheet(a if self._pulse_on else b)

    def _ack(self) -> None:
        kind = self._top()
        if kind:
            self.ackClicked.emit(kind)
