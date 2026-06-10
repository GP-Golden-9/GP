"""Proportional virtual joystick for teleoperation.

Drag the knob: vertical = linear velocity, horizontal = turn rate, both
continuous (not bang-bang like a D-pad). Spring-returns to center on
release → stop. Emits at the protocol's drive-stream rate while engaged so
the deadman chain stays fed.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ui import theme
from gpcore.protocol import commands as cmds

DEADZONE = 0.12


class Joystick(QWidget):
    # normalized (-1..1, -1..1): (turn, forward). Emitted at DRIVE_STREAM_HZ
    # while engaged; one final (0, 0) on release.
    vector = Signal(float, float)
    engagedChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(170, 170)
        self._knob = QPointF(0.0, 0.0)        # normalized
        self._engaged = False
        self._enabled_logic = True

        self._stream = QTimer(self)
        self._stream.setInterval(int(1000 / cmds.DRIVE_STREAM_HZ))
        self._stream.timeout.connect(self._emit_vector)

    def set_enabled_logic(self, on: bool) -> None:
        """Disable driving (e-stop) without greying the widget."""
        self._enabled_logic = on
        if not on:
            self._release()

    # ── geometry ──────────────────────────────────────────────────────────
    def _radius(self) -> float:
        return min(self.width(), self.height()) / 2 - 12

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _to_norm(self, pos: QPointF) -> QPointF:
        r = self._radius()
        v = (pos - self._center()) / r
        length = math.hypot(v.x(), v.y())
        if length > 1.0:
            v /= length
        return v

    # ── mouse ─────────────────────────────────────────────────────────────
    def mousePressEvent(self, e) -> None:
        if not self._enabled_logic:
            return
        self._engaged = True
        self.engagedChanged.emit(True)
        self._knob = self._to_norm(e.position())
        self._stream.start()
        self._emit_vector()
        self.update()

    def mouseMoveEvent(self, e) -> None:
        if self._engaged:
            self._knob = self._to_norm(e.position())
            self.update()

    def mouseReleaseEvent(self, _e) -> None:
        self._release()

    def _release(self) -> None:
        if not self._engaged:
            return
        self._engaged = False
        self._stream.stop()
        self._knob = QPointF(0.0, 0.0)
        self.vector.emit(0.0, 0.0)            # explicit stop
        self.engagedChanged.emit(False)
        self.update()

    def _emit_vector(self) -> None:
        x, y = self._knob.x(), self._knob.y()
        turn = 0.0 if abs(x) < DEADZONE else x
        fwd = 0.0 if abs(y) < DEADZONE else -y      # screen y down → forward up
        self.vector.emit(turn, fwd)

    # ── painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self._center()
        r = self._radius()

        # base well
        grad = QRadialGradient(c, r)
        grad.setColorAt(0.0, QColor(theme.SURFACE_3))
        grad.setColorAt(1.0, QColor(theme.SURFACE))
        p.setBrush(grad)
        p.setPen(QPen(QColor(theme.BORDER), 1.5))
        p.drawEllipse(c, r, r)

        # crosshair + deadzone ring
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawLine(c + QPointF(-r, 0), c + QPointF(r, 0))
        p.drawLine(c + QPointF(0, -r), c + QPointF(0, r))
        p.drawEllipse(c, r * DEADZONE, r * DEADZONE)

        # heading cue
        p.setPen(QPen(QColor(theme.MUTED), 1))
        p.drawText(QRectF(c.x() - 20, c.y() - r + 2, 40, 14),
                   Qt.AlignCenter, 'FWD')

        # knob
        kc = c + QPointF(self._knob.x() * r, self._knob.y() * r)
        color = QColor(theme.ACCENT if self._engaged else theme.MUTED)
        p.setPen(QPen(color.darker(130), 2))
        p.setBrush(color if self._engaged else QColor(theme.SURFACE_3))
        p.drawEllipse(kc, 18, 18)
        p.end()
