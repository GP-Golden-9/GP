"""Operator controls: hold-to-drive D-pad, speed, autonomous toggle, E-STOP,
pump (hold-to-run) and servo arm.

Safety semantics implemented HERE (the rest of the chain enforces them again):
  * driving = a 10 Hz cmd.drive stream while a control is held; releasing
    (or this window losing focus/crashing) stops the stream → gateway
    deadman (600 ms) → bridge deadman (0.8 s) → firmware watchdog (1 s)
  * E-STOP is always enabled, latches, and must be released deliberately
  * pump runs only while the button is physically held (max 5 s firmware cap)
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from gpcore.protocol import commands as cmds
from views import theme


class HoldButton(QPushButton):
    """Button that reports pressed/released (auto-repeat handled by caller)."""

    held = Signal(bool)

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.NoFocus)         # keyboard stays with the window
        self.pressed.connect(lambda: self.held.emit(True))
        self.released.connect(lambda: self.held.emit(False))


class ControlPanel(QWidget):
    driveRequested = Signal(float, float)       # vx, wz (one tick of the stream)
    stopRequested = Signal()
    estopToggled = Signal(bool)
    exploreToggled = Signal(bool)
    speedChanged = Signal(float)
    pumpRequested = Signal(bool)
    servoRequested = Signal(int)

    def __init__(self, prefs, accessories_enabled: bool = False, parent=None):
        super().__init__(parent)
        self.prefs = prefs
        self._held_dir: str | None = None
        self._estop = False
        self._speed = prefs.speed_default

        self._stream = QTimer(self)
        self._stream.setInterval(int(1000 / cmds.DRIVE_STREAM_HZ))
        self._stream.timeout.connect(self._stream_tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        # ── action label ──
        self.action_label = QLabel('READY')
        self.action_label.setAlignment(Qt.AlignCenter)
        self.action_label.setStyleSheet(
            f'font-weight:800; font-size:15px; letter-spacing:2px; '
            f'color:{theme.GOOD};')
        root.addWidget(self.action_label)

        # ── D-pad ──
        pad_box = QGroupBox('MANUAL CONTROL · WASD / ARROWS · HOLD TO DRIVE')
        grid = QGridLayout(pad_box)
        self.btn_f = HoldButton('▲'); self.btn_b = HoldButton('▼')
        self.btn_l = HoldButton('◀'); self.btn_r = HoldButton('▶')
        stop_btn = QPushButton('■')
        stop_btn.setObjectName('stopBtn')
        stop_btn.setFocusPolicy(Qt.NoFocus)
        stop_btn.clicked.connect(self._stop_clicked)
        for b in (self.btn_f, self.btn_b, self.btn_l, self.btn_r):
            b.setObjectName('dpadBtn')
        for b in (self.btn_f, self.btn_b, self.btn_l, self.btn_r, stop_btn):
            b.setMinimumSize(56, 46)
            b.setMaximumWidth(80)
        grid.setSpacing(6)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(4, 1)
        grid.addWidget(self.btn_f, 0, 2)
        grid.addWidget(self.btn_l, 1, 1)
        grid.addWidget(stop_btn, 1, 2)
        grid.addWidget(self.btn_r, 1, 3)
        grid.addWidget(self.btn_b, 2, 2)
        self.btn_f.held.connect(lambda on: self._set_held('F', on))
        self.btn_b.held.connect(lambda on: self._set_held('B', on))
        self.btn_l.held.connect(lambda on: self._set_held('L', on))
        self.btn_r.held.connect(lambda on: self._set_held('R', on))
        root.addWidget(pad_box)

        # ── speed ──
        speed_row = QHBoxLayout()
        speed_title = QLabel('SPEED')
        speed_title.setObjectName('sectionTitle')
        speed_row.addWidget(speed_title)
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(int(prefs.speed_min * 100), int(prefs.speed_max * 100))
        self.speed_slider.setValue(int(prefs.speed_default * 100))
        self.speed_slider.valueChanged.connect(self._speed_moved)
        self.speed_label = QLabel(f'{prefs.speed_default:.2f} m/s')
        self.speed_label.setStyleSheet(
            f'color:{theme.ACCENT}; font-family:{theme.MONO}; font-weight:700;')
        self.speed_label.setMinimumWidth(72)
        self.speed_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        root.addLayout(speed_row)

        # ── autonomous ──
        self.explore_btn = QPushButton('AUTONOMOUS · OFF')
        self.explore_btn.setObjectName('exploreBtn')
        self.explore_btn.setCheckable(True)
        self.explore_btn.setMinimumHeight(38)
        self.explore_btn.setFocusPolicy(Qt.NoFocus)
        self.explore_btn.toggled.connect(self._explore_toggled)
        root.addWidget(self.explore_btn)

        # ── accessories (robot2 only) ──
        self.acc_box = QGroupBox('INTERVENTION TOOLS')
        acc = QGridLayout(self.acc_box)
        acc.setSpacing(8)
        self.pump_btn = HoldButton('💧  PUMP — hold to spray (max 5 s)')
        self.pump_btn.setObjectName('pumpBtn')
        self.pump_btn.setMinimumHeight(44)
        self.pump_btn.held.connect(self._pump_held)
        acc.addWidget(self.pump_btn, 0, 0, 1, 3)
        servo_lbl = QLabel('ARM SERVO')
        servo_lbl.setObjectName('sectionTitle')
        acc.addWidget(servo_lbl, 1, 0)
        self.servo_slider = QSlider(Qt.Horizontal)
        self.servo_slider.setRange(10, 170)
        self.servo_slider.setValue(90)
        self.servo_slider.sliderReleased.connect(
            lambda: self.servoRequested.emit(self.servo_slider.value()))
        self.servo_value = QLabel('90°')
        self.servo_value.setStyleSheet(
            f'color:{theme.ACCENT}; font-family:{theme.MONO}; font-weight:700;')
        self.servo_value.setMinimumWidth(44)
        self.servo_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.servo_slider.valueChanged.connect(
            lambda v: self.servo_value.setText(f'{v}°'))
        acc.addWidget(self.servo_slider, 1, 1)
        acc.addWidget(self.servo_value, 1, 2)
        self.acc_box.setVisible(accessories_enabled)
        root.addWidget(self.acc_box)

        # ── E-STOP ──
        self.estop_btn = QPushButton('EMERGENCY STOP  (Esc)')
        self.estop_btn.setFocusPolicy(Qt.NoFocus)
        self.estop_btn.setMinimumHeight(48)
        self._style_estop()
        self.estop_btn.clicked.connect(lambda: self.set_estop(not self._estop))
        root.addWidget(self.estop_btn)
        root.addStretch(1)

    # ── public API (main window / keyboard) ───────────────────────────────
    def keyboard_direction(self, direction: str | None) -> None:
        """direction in {'F','B','L','R'} while held, None on release."""
        if direction is None:
            self._set_held(self._held_dir or 'F', False)
        else:
            self._set_held(direction, True)

    def set_estop(self, engage: bool) -> None:
        if engage == self._estop:
            return
        self._estop = engage
        base = 'font-weight:800; font-size:15px; letter-spacing:2px;'
        if engage:
            self._held_dir = None
            self._stream.stop()
            self.action_label.setText('⛔ EMERGENCY STOP')
            self.action_label.setStyleSheet(base + f'color:{theme.BAD};')
        else:
            self.action_label.setText('READY')
            self.action_label.setStyleSheet(base + f'color:{theme.GOOD};')
        self._style_estop()
        self.estopToggled.emit(engage)

    def set_accessories_enabled(self, on: bool) -> None:
        self.acc_box.setVisible(on)

    def set_servo_feedback(self, deg: int) -> None:
        if not self.servo_slider.isSliderDown():
            self.servo_slider.blockSignals(True)
            self.servo_slider.setValue(deg)
            self.servo_slider.blockSignals(False)
            self.servo_value.setText(f'{deg}°')

    @property
    def estop_engaged(self) -> bool:
        return self._estop

    # ── internals ─────────────────────────────────────────────────────────
    def _style_estop(self) -> None:
        if self._estop:
            self.estop_btn.setText('▲  RELEASE E-STOP')
            self.estop_btn.setStyleSheet(theme.ESTOP_ENGAGED)
        else:
            self.estop_btn.setText('EMERGENCY STOP  ·  Esc')
            self.estop_btn.setStyleSheet(theme.ESTOP_IDLE)

    def _set_held(self, direction: str, on: bool) -> None:
        if self._estop:
            return
        if on:
            self._held_dir = direction
            self._stream.start()
            self._stream_tick()
            self.action_label.setText({'F': 'Forward', 'B': 'Backward',
                                       'L': 'Turn left', 'R': 'Turn right'}[direction])
        elif self._held_dir == direction or direction is None:
            self._held_dir = None
            self._stream.stop()
            self.stopRequested.emit()
            self.action_label.setText('Stopped')

    def _stream_tick(self) -> None:
        if self._held_dir is None or self._estop:
            self._stream.stop()
            return
        v, t = self._speed, self.prefs.turn_rate
        vx, wz = {'F': (v, 0.0), 'B': (-v, 0.0),
                  'L': (0.0, t), 'R': (0.0, -t)}[self._held_dir]
        self.driveRequested.emit(vx, wz)

    def _stop_clicked(self) -> None:
        self._held_dir = None
        self._stream.stop()
        self.stopRequested.emit()
        self.action_label.setText('Stopped')

    def _speed_moved(self, value: int) -> None:
        self._speed = value / 100.0
        self.speed_label.setText(f'{self._speed:.2f} m/s')
        self.speedChanged.emit(self._speed)

    def _explore_toggled(self, on: bool) -> None:
        self.explore_btn.setText(f'AUTONOMOUS · {"ON" if on else "OFF"}')
        self.exploreToggled.emit(on)

    def _pump_held(self, on: bool) -> None:
        if self._estop and on:
            return
        self.pumpRequested.emit(on)
