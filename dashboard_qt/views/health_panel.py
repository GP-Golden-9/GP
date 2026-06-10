"""Health panel — per-stream freshness LEDs + robot vitals.

Everything here is driven by the health channel and local staleness sweeps;
if this panel is all green, the demo is safe to start."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from gpcore.protocol.channels import Staleness

LED = {Staleness.FRESH: '🟢', Staleness.STALE: '🟡', Staleness.DEAD: '🔴'}
STREAM_LABELS = (('telemetry', 'Telemetry'), ('video', 'Video'),
                 ('map', 'Map'), ('scan', 'LiDAR'), ('health', 'Health'),
                 ('cmd', 'Commands'))


class HealthPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)

        streams_box = QGroupBox('Streams')
        grid = QGridLayout(streams_box)
        self._leds: dict[str, QLabel] = {}
        for row, (key, label) in enumerate(STREAM_LABELS):
            grid.addWidget(QLabel(label), row, 0)
            led = QLabel('🔴 —')
            led.setAlignment(Qt.AlignRight)
            self._leds[key] = led
            grid.addWidget(led, row, 1)
        root.addWidget(streams_box)

        vitals_box = QGroupBox('Robot vitals')
        vgrid = QGridLayout(vitals_box)
        self._vitals: dict[str, QLabel] = {}
        for row, (key, label) in enumerate((
                ('temp_c', 'Pi temp'), ('throttled', 'Power flags'),
                ('rssi_dbm', 'WiFi RSSI'), ('load1', 'Load (1m)'),
                ('mem_free_mb', 'Mem free'), ('disk_free_mb', 'Disk free'),
                ('uptime', 'Stack uptime'), ('estop', 'E-stop'))):
            vgrid.addWidget(QLabel(label), row, 0)
            val = QLabel('—')
            val.setAlignment(Qt.AlignRight)
            self._vitals[key] = val
            vgrid.addWidget(val, row, 1)
        root.addWidget(vitals_box)
        root.addStretch(1)

    def update_staleness(self, staleness: dict, rates: dict | None = None) -> None:
        for key, led in self._leds.items():
            st = staleness.get(key)
            if st is None:
                continue
            rate = (rates or {}).get(key)
            txt = LED.get(st, '🔴') + (f' {rate:.1f} Hz' if rate else f' {st.value}')
            led.setText(txt)

    def update_health(self, payload: dict) -> None:
        sys = payload.get('sys', {}) or {}

        def put(key, value, fmt='{}', warn=None):
            lbl = self._vitals[key]
            if value is None:
                lbl.setText('—')
                return
            lbl.setText(fmt.format(value))
            lbl.setStyleSheet('color:#f87171;font-weight:bold;' if warn else '')

        temp = sys.get('temp_c')
        put('temp_c', temp, '{:.1f} °C', warn=(temp or 0) > 75)
        thr = sys.get('throttled')
        put('throttled', thr, '{}', warn=bool(thr and thr not in ('0x0', '0X0')))
        put('rssi_dbm', sys.get('rssi_dbm'), '{} dBm',
            warn=(sys.get('rssi_dbm') or 0) < -75)
        put('load1', sys.get('load1'), '{:.2f}')
        put('mem_free_mb', sys.get('mem_free_mb'), '{} MB',
            warn=(sys.get('mem_free_mb') or 9999) < 100)
        put('disk_free_mb', sys.get('disk_free_mb'), '{} MB',
            warn=(sys.get('disk_free_mb') or 99999) < 500)
        up = payload.get('uptime_s')
        put('uptime', f'{up/60:.0f} min' if up is not None else None)
        put('estop', 'ENGAGED' if payload.get('estop') else 'clear',
            warn=bool(payload.get('estop')))
