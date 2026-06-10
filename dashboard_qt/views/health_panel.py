"""Health panel — per-stream freshness LEDs + robot vitals.

Everything here is driven by the health channel and local staleness sweeps;
if this panel is all green, the demo is safe to start."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from gpcore.protocol.channels import Staleness
from views import theme

LED_COLOR = {Staleness.FRESH: theme.GOOD, Staleness.STALE: theme.WARN,
             Staleness.DEAD: theme.BAD}
STREAM_LABELS = (('telemetry', 'Telemetry'), ('video', 'Video'),
                 ('map', 'Map'), ('scan', 'LiDAR'), ('health', 'Health'),
                 ('cmd', 'Commands'))
VALUE_STYLE = f'font-family:{theme.MONO}; font-size:12px;'


class HealthPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        streams_box = QGroupBox('STREAMS')
        grid = QGridLayout(streams_box)
        grid.setVerticalSpacing(7)
        self._leds: dict[str, QLabel] = {}
        for row, (key, label) in enumerate(STREAM_LABELS):
            name = QLabel(label)
            name.setStyleSheet(f'color:{theme.MUTED};')
            grid.addWidget(name, row, 0)
            led = QLabel('●  —')
            led.setAlignment(Qt.AlignRight)
            led.setStyleSheet(VALUE_STYLE + f'color:{theme.BAD};')
            self._leds[key] = led
            grid.addWidget(led, row, 1)
        root.addWidget(streams_box)

        vitals_box = QGroupBox('ROBOT VITALS')
        vgrid = QGridLayout(vitals_box)
        vgrid.setVerticalSpacing(7)
        self._vitals: dict[str, QLabel] = {}
        for row, (key, label) in enumerate((
                ('temp_c', 'Pi temperature'), ('throttled', 'Power flags'),
                ('rssi_dbm', 'WiFi signal'), ('load1', 'CPU load (1m)'),
                ('mem_free_mb', 'Memory free'), ('disk_free_mb', 'Disk free'),
                ('uptime', 'Stack uptime'), ('estop', 'E-stop'))):
            name = QLabel(label)
            name.setStyleSheet(f'color:{theme.MUTED};')
            vgrid.addWidget(name, row, 0)
            val = QLabel('—')
            val.setAlignment(Qt.AlignRight)
            val.setStyleSheet(VALUE_STYLE)
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
            text = f'●  {rate:.1f} Hz' if rate else f'●  {st.value.upper()}'
            led.setText(text)
            led.setStyleSheet(VALUE_STYLE + f'color:{LED_COLOR[st]};')

    def update_health(self, payload: dict) -> None:
        sys = payload.get('sys', {}) or {}

        def put(key, value, fmt='{}', warn=None):
            lbl = self._vitals[key]
            if value is None:
                lbl.setText('—')
                lbl.setStyleSheet(VALUE_STYLE + f'color:{theme.MUTED};')
                return
            lbl.setText(fmt.format(value))
            lbl.setStyleSheet(VALUE_STYLE + (
                f'color:{theme.BAD}; font-weight:700;' if warn
                else f'color:{theme.TEXT};'))

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
