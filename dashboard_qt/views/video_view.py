"""Live camera view: native QImage blit (no base64, no browser), with an
honest frame-age badge and an explicit "AI OFF" state instead of silently
showing stale or raw frames."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

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
        p.fillRect(self.rect(), QColor(12, 12, 16))

        if self._pixmap is not None:
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio,
                                         Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            p.drawPixmap(x, y, scaled)

        font = QFont('Consolas', 9)
        p.setFont(font)

        since_last = (time.monotonic() - self._last_frame_local
                      if self._last_frame_local else float('inf'))

        # top-left: LIVE / NO SIGNAL
        if since_last > STALE_BANNER_AFTER_S:
            self._badge(p, 8, 8, '◼ NO SIGNAL', QColor(180, 30, 30))
        else:
            age_txt = (f'{self._frame_age_s*1000:.0f} ms'
                       if self._frame_age_s is not None else f'{since_last*1000:.0f} ms')
            self._badge(p, 8, 8, f'● LIVE  {self._fps:4.1f} fps  age {age_txt}',
                        QColor(30, 120, 40))

        # top-right: AI state
        if self._ai_on:
            self._badge_right(p, 8, 'AI ON', QColor(20, 90, 160))
        else:
            label = 'RAW (AI OFF)' + (f' — {self._ai_reason}' if self._ai_reason else '')
            self._badge_right(p, 8, label, QColor(150, 90, 20))
        p.end()

    def _badge(self, p: QPainter, x: int, y: int, text: str, color: QColor) -> None:
        w = p.fontMetrics().horizontalAdvance(text) + 14
        h = p.fontMetrics().height() + 8
        p.fillRect(x, y, w, h, color)
        p.setPen(Qt.white)
        p.drawText(x + 7, y + h - 7, text)

    def _badge_right(self, p: QPainter, y: int, text: str, color: QColor) -> None:
        w = p.fontMetrics().horizontalAdvance(text) + 14
        self._badge(p, self.width() - w - 8, y, text, color)
