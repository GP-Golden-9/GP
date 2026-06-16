"""Live camera panel — native blit, honest telemetry pills, AI state."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

from ui import theme

STALE_BANNER_AFTER_S = 2.5
DETECT_HOLD_S = 1.0          # boxes vanish if inference stops feeding them

_BOX_COLOR = {
    'person': theme.MARKER_HUMAN, 'dog': theme.MARKER_DOG,
    'cat': theme.MARKER_CAT, 'fire': theme.MARKER_FIRE,
    'flame': theme.MARKER_FIRE, 'smoke': theme.MARKER_FIRE,
}


class VideoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 220)
        self._pixmap: QPixmap | None = None
        self._last_frame_local = 0.0
        self._frame_age_s: float | None = None
        self._fps = 0.0
        self._ai_on = False
        self._ai_reason = 'starting…'
        self._robot = ''
        self._detect_text = ''
        self._detect_until = 0.0
        self._detections: list = []        # latest YOLO boxes (normalized)
        self._detections_at = 0.0

        t = QTimer(self)
        t.setInterval(500)
        t.timeout.connect(self.update)
        t.start()

    def set_robot(self, robot_id: str) -> None:
        self._robot = robot_id
        self._pixmap = None
        self._last_frame_local = 0.0
        self._detections = []
        self.update()

    def set_detections(self, detections) -> None:
        """Latest YOLO boxes (normalized cx/cy/w/h), drawn as a vector
        overlay over the live raw frame — decoupled from video latency."""
        self._detections = list(detections or ())
        self._detections_at = time.monotonic()
        self.update()

    def show_jpeg(self, jpeg: bytes, frame_age_s: float | None = None) -> None:
        img = QImage.fromData(jpeg, 'JPEG')
        if img.isNull():
            return
        now = time.monotonic()
        if self._last_frame_local:
            dt = max(1e-3, now - self._last_frame_local)
            inst = 1.0 / dt
            self._fps = 0.9 * self._fps + 0.1 * inst if self._fps else inst
        self._last_frame_local = now
        self._frame_age_s = frame_age_s
        self._pixmap = QPixmap.fromImage(img)
        self.update()

    def set_ai_state(self, on: bool, reason: str = '') -> None:
        self._ai_on = on
        self._ai_reason = reason
        self.update()

    def flash_detection(self, text: str) -> None:
        """Brief on-video note, e.g. 'fire 31% → map (1.4, 0.3)'."""
        self._detect_text = text
        self._detect_until = time.monotonic() + 3.0

    # ── painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#06090f'))

        if self._pixmap is not None:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)
            self._draw_boxes(p, x, y, scaled.width(), scaled.height())

        p.setFont(QFont('Consolas', 8, QFont.Bold))
        since = (time.monotonic() - self._last_frame_local
                 if self._last_frame_local else float('inf'))

        if since > STALE_BANNER_AFTER_S:
            self._pill(p, 8, 8, f'NO SIGNAL · {self._robot}', QColor(theme.BAD))
        else:
            age = (f'{self._frame_age_s * 1000:.0f} ms'
                   if self._frame_age_s is not None else f'{since * 1000:.0f} ms')
            self._pill(p, 8, 8, f'{self._robot} · {self._fps:.1f} FPS · {age}',
                       QColor(theme.GOOD))

        if self._ai_on:
            self._pill_right(p, 8, 'AI ON', QColor(theme.ACCENT))
        else:
            label = 'AI OFF' + (f' — {self._ai_reason}' if self._ai_reason else '')
            self._pill_right(p, 8, label, QColor(theme.WARN))

        if self._detect_text and time.monotonic() < self._detect_until:
            self._pill(p, 8, self.height() - 34, self._detect_text,
                       QColor(theme.MARKER_FIRE))
        p.end()

    def _draw_boxes(self, p, ox, oy, vw, vh) -> None:
        if (not self._detections
                or time.monotonic() - self._detections_at > DETECT_HOLD_S):
            return
        p.save()
        p.setFont(QFont('Consolas', 8, QFont.Bold))
        for d in self._detections:
            try:
                cx, cy, w, h = (float(d['cx']), float(d['cy']),
                                float(d['w']), float(d['h']))
            except (KeyError, TypeError, ValueError):
                continue
            bx = ox + (cx - w / 2) * vw
            by = oy + (cy - h / 2) * vh
            bw, bh = w * vw, h * vh
            label = str(d.get('label', ''))
            col = QColor(_BOX_COLOR.get(label.lower(), theme.GOOD))
            p.setPen(col)
            p.setBrush(Qt.NoBrush)
            p.drawRect(int(bx), int(by), int(bw), int(bh))
            tag = f"{label} {float(d.get('conf', 0.0)) * 100:.0f}%"
            tw = p.fontMetrics().horizontalAdvance(tag) + 8
            p.fillRect(int(bx), int(by) - 16, tw, 15, QColor(8, 11, 18, 210))
            p.setPen(col)
            p.drawText(int(bx) + 4, int(by) - 4, tag)
        p.restore()

    def _pill(self, p, x, y, text, dot: QColor) -> None:
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 34
        h = fm.height() + 10
        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, h / 2, h / 2)
        p.fillPath(path, QColor(8, 11, 18, 210))
        p.setPen(QColor(56, 66, 88, 160))
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(dot)
        p.drawEllipse(x + 10, y + h // 2 - 3, 7, 7)
        p.setPen(QColor(theme.TEXT))
        p.drawText(x + 24, y + h - 8, text)

    def _pill_right(self, p, y, text, dot: QColor) -> None:
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 34
        self._pill(p, self.width() - w - 8, y, text, dot)
