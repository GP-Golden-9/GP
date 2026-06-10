"""Incident/log console — robot log.event lines + local console events,
timestamped, bounded, with simple severity coloring."""

from __future__ import annotations

import time

from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit

MAX_BLOCKS = 2000


class LogConsole(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_BLOCKS)
        self.setFrameShape(self.Shape.NoFrame)
        self.setStyleSheet(
            'background:#0d1422; color:#86efac; border:none; border-radius:8px;'
            'font-family:Consolas,monospace; font-size:11px; padding:6px;')

    def append_line(self, line: str, *, source: str = 'robot') -> None:
        stamp = time.strftime('%H:%M:%S')
        text = f'[{stamp}] {line}'
        upper = line.upper()
        fmt = QTextCharFormat()
        if any(k in upper for k in ('ERR', 'FAIL', 'ESTOP', 'EMERGENCY', 'DEADMAN')):
            fmt.setForeground(QColor('#f87171'))
        elif any(k in upper for k in ('WARN', 'STALL', 'RETRY', 'TIMEOUT')):
            fmt.setForeground(QColor('#facc15'))
        elif source == 'local':
            fmt.setForeground(QColor('#93c5fd'))
        else:
            fmt.setForeground(QColor('#86efac'))
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text + '\n', fmt)
        self.setTextCursor(cursor)
