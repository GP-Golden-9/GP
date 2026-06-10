"""Diagnostics panel — fix a broken Pi or ESP32 WITHOUT leaving the console.

Per robot:
  vitals strip (temp / power flags / RSSI / load / mem / disk / uptime)
  remote actions over SSH (key-based auth, `ssh-copy-id pi@robotN.local`
  once per Pi — see docs/runbook_demo_day.md):
      PING            connectivity proof
      STATUS          systemctl list of all gp-* units
      RESTART STACK   sudo systemctl restart gp-robotN
      RESTART CAMERA  (robot2) restart the isolated camera unit
      COLLECT LOGS    runs tools/collect_logs.py for this host
      REBOOT PI       double-confirmed, last resort
  ESP32 robots get PING + OPEN WEB UI (the firmware self-serves a页面)
  plus a hint that power-cycling the node is the hardware reset path.

Every action streams its output into the console below — evidence first,
guesswork never.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

from ui import theme

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SSH = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=accept-new']
UNIT = {'robot1': 'gp-robot1', 'robot2': 'gp-robot2'}


class DiagnosticsPanel(QWidget):
    def __init__(self, robots, parent=None):
        super().__init__(parent)
        self.robots = {p.id: p for p in robots}
        self._proc: QProcess | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        top = QHBoxLayout()
        top.addWidget(QLabel('Robot:'))
        self.combo = QComboBox()
        self.combo.setFocusPolicy(Qt.NoFocus)   # keys belong to teleop
        for p in robots:
            self.combo.addItem(f'{p.name} · {p.id}', p.id)
        self.combo.currentIndexChanged.connect(lambda _i: self._rebuild_actions())
        top.addWidget(self.combo)
        self.vitals = QLabel('vitals —')
        self.vitals.setStyleSheet(f'font-family:{theme.MONO}; font-size:11px; '
                                  f'color:{theme.MUTED};')
        top.addWidget(self.vitals, 1)
        root.addLayout(top)

        self.actions_row = QHBoxLayout()
        self.actions_row.setSpacing(6)
        root.addLayout(self.actions_row)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(800)
        self.console.setStyleSheet(
            f'background:#0c1019; color:#9fb4d0; font-family:{theme.MONO};'
            'font-size:11px; border:none; border-radius:8px; padding:6px;')
        root.addWidget(self.console, 1)

        self._rebuild_actions()

    # ── health feed (called by main window for every robot) ──────────────
    def update_vitals(self, robot_id: str, payload: dict) -> None:
        if robot_id != self.combo.currentData():
            return
        sysv = payload.get('sys', {}) or {}
        thr = sysv.get('throttled') or '—'
        warn = thr not in ('0x0', '0X0', '—')
        parts = [
            f"temp {sysv.get('temp_c', '—')}°C",
            f'power {thr}' + (' ⚠' if warn else ''),
            f"rssi {sysv.get('rssi_dbm', '—')} dBm",
            f"load {sysv.get('load1', '—')}",
            f"mem {sysv.get('mem_free_mb', '—')} MB",
            f"disk {sysv.get('disk_free_mb', '—')} MB",
            f"up {round((payload.get('uptime_s') or 0) / 60)} min",
        ]
        self.vitals.setText('   ·   '.join(str(p) for p in parts))
        self.vitals.setStyleSheet(
            f'font-family:{theme.MONO}; font-size:11px; '
            f'color:{theme.BAD if warn else theme.MUTED};')

    # ── actions ───────────────────────────────────────────────────────────
    def _rebuild_actions(self) -> None:
        while self.actions_row.count():
            item = self.actions_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rid = self.combo.currentData()
        prof = self.robots.get(rid)
        if prof is None:
            return
        host = prof.host
        user_host = f'pi@{host}'

        def btn(text, tip, fn, danger=False):
            b = QPushButton(text)
            b.setFocusPolicy(Qt.NoFocus)
            b.setToolTip(tip)
            if danger:
                b.setStyleSheet(f'color:{theme.BAD}; border-color:{theme.DANGER_D};')
            b.clicked.connect(fn)
            self.actions_row.addWidget(b)
            return b

        btn('PING', 'ICMP reachability',
            lambda: self._run(['ping', '-n', '3', host]))

        if prof.is_esp32:
            btn('OPEN WEB UI', 'ESP32 serves its own control page',
                lambda: (QDesktopServices.openUrl(QUrl(f'http://{host}/')),
                         self._log(f'opened http://{host}/ in the browser')))
            hint = QLabel('ESP32: no SSH — power-cycle the node to hard-reset; '
                          'watchdog stops motors on its own.')
            hint.setStyleSheet(f'color:{theme.MUTED}; font-size:10px;')
            self.actions_row.addWidget(hint)
        else:
            unit = UNIT.get(rid, 'gp-robot1')
            btn('STATUS', 'systemctl status of all gp-* units',
                lambda: self._run(SSH + [user_host,
                                  "systemctl list-units 'gp-*' --no-pager; "
                                  "vcgencmd get_throttled"]))
            btn('RESTART STACK', f'sudo systemctl restart {unit} (≈15 s outage)',
                lambda: self._confirm_run(
                    f'Restart the ROS stack on {host}?',
                    SSH + [user_host, f'sudo systemctl restart {unit} && '
                                      f'echo RESTARTED {unit}']))
            if rid == 'robot2':
                btn('RESTART CAMERA', 'restart gp-camera only (video path)',
                    lambda: self._run(SSH + [user_host,
                                      'sudo systemctl restart gp-camera && '
                                      'echo RESTARTED gp-camera']))
            btn('COLLECT LOGS', 'pull run logs + journal into incidents/',
                lambda: self._run([sys.executable,
                                   os.path.join(REPO, 'tools', 'collect_logs.py'),
                                   host]))
            btn('REBOOT PI', 'last resort — full reboot (~45 s)',
                lambda: self._confirm_run(
                    f'REBOOT the Raspberry Pi at {host}?\n\n'
                    'Only after RESTART STACK failed. The robot will be gone '
                    'for ~45 seconds.',
                    SSH + [user_host, 'sudo reboot']), danger=True)
        self.actions_row.addStretch(1)

    def _confirm_run(self, question: str, cmd: list[str]) -> None:
        if QMessageBox.question(self, 'Confirm action', question,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) == QMessageBox.Yes:
            self._run(cmd)

    def _run(self, cmd: list[str]) -> None:
        if self._proc is not None and self._proc.state() != QProcess.NotRunning:
            self._log('… previous action still running')
            return
        self._log('$ ' + ' '.join(cmd))
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(
            lambda: self._log(bytes(self._proc.readAllStandardOutput())
                              .decode(errors='replace').rstrip()))
        self._proc.finished.connect(
            lambda code, _st: self._log(f'[exit {code}]\n'))
        self._proc.errorOccurred.connect(
            lambda err: self._log(f'[process error: {err.name} — is ssh/ping '
                                  'in PATH? key auth set up?]'))
        self._proc.start(cmd[0], cmd[1:])

    def _log(self, line: str) -> None:
        if line:
            self.console.appendPlainText(line)
