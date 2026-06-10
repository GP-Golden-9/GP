"""Bottom drawer: INCIDENT LOG · DETECTIONS · DIAGNOSTICS."""

from __future__ import annotations

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (QHeaderView, QPlainTextEdit, QPushButton,
                               QTableWidget, QTableWidgetItem, QTabWidget,
                               QWidget, QVBoxLayout, QHBoxLayout)

from ui import theme
from ui.diagnostics import DiagnosticsPanel

MAX_BLOCKS = 2000


class LogConsole(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(MAX_BLOCKS)
        self.setFrameShape(self.Shape.NoFrame)
        self.setStyleSheet(
            f'background:#0c1019; color:#86efac; border:none;'
            f'font-family:{theme.MONO}; font-size:11px; padding:6px;')

    def append_line(self, line: str, *, source: str = 'robot') -> None:
        stamp = time.strftime('%H:%M:%S')
        upper = line.upper()
        fmt = QTextCharFormat()
        if any(k in upper for k in ('ERR', 'FAIL', 'ESTOP', 'EMERGENCY',
                                    'DEADMAN', 'FIRE', 'GAS', 'ALERT')):
            fmt.setForeground(QColor(theme.BAD))
        elif any(k in upper for k in ('WARN', 'STALL', 'RETRY', 'TIMEOUT', 'DRILL')):
            fmt.setForeground(QColor(theme.WARN))
        elif source == 'local':
            fmt.setForeground(QColor('#93c5fd'))
        else:
            fmt.setForeground(QColor('#86efac'))
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(f'[{stamp}] {line}\n', fmt)
        self.setTextCursor(cursor)


class DetectionsTable(QWidget):
    locateRequested = Signal(float, float)
    clearRequested = Signal()

    COLS = ('TIME', 'KIND', 'ROBOT', 'CONF', 'X (m)', 'Y (m)')

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 6)
        bar = QHBoxLayout()
        bar.addStretch(1)
        locate = QPushButton('LOCATE ON MAP')
        locate.setFocusPolicy(Qt.NoFocus)
        locate.setStyleSheet('font-size:10px; padding:3px 10px;')
        locate.clicked.connect(self._locate_selected)
        clear = QPushButton('CLEAR ALL')
        clear.setFocusPolicy(Qt.NoFocus)
        clear.setStyleSheet('font-size:10px; padding:3px 10px;')
        clear.clicked.connect(self.clearRequested.emit)
        bar.addWidget(locate)
        bar.addWidget(clear)
        lay.addLayout(bar)

        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.doubleClicked.connect(lambda _i: self._locate_selected())
        lay.addWidget(self.table, 1)

    def set_markers(self, markers: list) -> None:
        self.table.setRowCount(len(markers))
        for row, m in enumerate(reversed(markers)):     # newest on top
            conf = f'{m.conf}%' if isinstance(m.conf, int) else '—'
            for col, value in enumerate((m.t_wall or '—', m.kind, m.robot or '—',
                                         conf, f'{m.x:+.2f}', f'{m.y:+.2f}')):
                item = QTableWidgetItem(str(value))
                if col == 1 and m.kind == 'FIRE':
                    item.setForeground(QColor(theme.MARKER_FIRE))
                elif col == 1 and m.kind == 'GAS':
                    item.setForeground(QColor(theme.MARKER_GAS))
                self.table.setItem(row, col, item)

    def _locate_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        try:
            x = float(self.table.item(row, 4).text())
            y = float(self.table.item(row, 5).text())
        except (ValueError, AttributeError):
            return
        self.locateRequested.emit(x, y)


class BottomPanel(QTabWidget):
    def __init__(self, robots, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.log = LogConsole()
        self.detections = DetectionsTable()
        self.diagnostics = DiagnosticsPanel(robots)
        self.addTab(self.log, 'INCIDENT LOG')
        self.addTab(self.detections, 'DETECTIONS')
        self.addTab(self.diagnostics, 'DIAGNOSTICS')
