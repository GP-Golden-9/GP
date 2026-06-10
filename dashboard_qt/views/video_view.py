"""Live camera view: native QImage blit (no base64, no browser), with an
honest frame-age badge and an explicit "AI OFF" state instead of silently
showing stale or raw frames."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QWidget

from views import theme

STALE_BANNER_AFTER_S = 2.5


class VideoView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self._pixmap: QPixmap | None = None
        self._last_frame_local = 0.0
        self._frame_age_s: float | None = None
        self._fps = 0.0
        self._ai_on = False
        self._ai_reason = 'starting…'

        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(500)     # keep badges fresh w/o frames
        self._repaint_timer.timeout.connect(self.update)
        self._repaint_timer.start()

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

    # ── painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#05080f'))

        if self._pixmap is not None:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)

        p.setFont(QFont('Consolas', 9, QFont.Bold))

        since_last = (time.monotonic() - self._last_frame_local
                      if self._last_frame_local else float('inf'))

        # top-left pill: LIVE / NO SIGNAL
        if since_last > STALE_BANNER_AFTER_S:
            self._pill(p, 10, 10, 'NO SIGNAL', dot=QColor(theme.BAD))
        else:
            age_txt = (f'{self._frame_age_s*1000:.0f} ms'
                       if self._frame_age_s is not None else f'{since_last*1000:.0f} ms')
            self._pill(p, 10, 10, f'LIVE · {self._fps:.1f} FPS · {age_txt}',
                       dot=QColor(theme.GOOD))

        # top-right pill: AI state
        if self._ai_on:
            self._pill_right(p, 10, 'AI ON', dot=QColor(theme.ACCENT))
        else:
            label = 'RAW · AI OFF' + (f' — {self._ai_reason}' if self._ai_reason else '')
            self._pill_right(p, 10, label, dot=QColor(theme.WARN))
        p.end()

    def _pill(self, p: QPainter, x: int, y: int, text: str,
              dot: QColor | None = None) -> None:
        fm = p.fontMetrics()
        dot_w = 14 if dot is not None else 0
        w = fm.horizontalAdvance(text) + 22 + dot_w
        h = fm.height() + 10
        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, h / 2, h / 2)
        p.fillPath(path, QColor(8, 12, 20, 205))
        p.setPen(QColor(60, 72, 96, 160))
        p.drawPath(path)
        tx = x + 11
        if dot is not None:
            p.setPen(Qt.NoPen)
            p.setBrush(dot)
            p.drawEllipse(x + 10, y + h // 2 - 3, 7, 7)
            tx += dot_w
        p.setPen(QColor(theme.TEXT))
        p.drawText(tx, y + h - 8, text)

    def _pill_right(self, p: QPainter, y: int, text: str,
                    dot: QColor | None = None) -> None:
        fm = p.fontMetrics()
        dot_w = 14 if dot is not None else 0
        w = fm.horizontalAdvance(text) + 22 + dot_w
        self._pill(p, self.width() - w - 10, y, text, dot)
