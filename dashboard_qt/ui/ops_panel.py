"""Operations panel — teleop for the ACTIVE robot, organized top-down the
way an operator reaches for it:

    drive mode → joystick (proportional) → speed presets → intervention
    tools → E-STOP (always at the bottom, always reachable)

The joystick emits the protocol's 10 Hz drive stream while engaged; the
keyboard path (WASD in the main window) feeds the same stream.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from ui import theme
from ui.joystick import Joystick


class OpsPanel(QWidget):
    driveRequested = Signal(float, float)      # vx (m/s), wz (rad/s)
    stopRequested = Signal()
    estopToggled = Signal(bool)
    modeChanged = Signal(str)                  # 'manual' | 'auto'
    speedChanged = Signal(float)               # m/s
    pumpRequested = Signal(bool)
    servoRequested = Signal(int)

    def __init__(self, prefs, parent=None):
        super().__init__(parent)
        self.prefs = prefs
        self._speed = prefs.speed_default
        self._estop = False

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(9)

        # ── target + state line ──
        head = QHBoxLayout()
        self.target_lbl = QLabel('—')
        self.target_lbl.setStyleSheet('font-size:13px; font-weight:800; '
                                      'letter-spacing:1px;')
        head.addWidget(self.target_lbl)
        head.addStretch(1)
        self.state_lbl = QLabel('READY')
        self.state_lbl.setStyleSheet(f'color:{theme.GOOD}; font-weight:800; '
                                     'font-size:11px; letter-spacing:2px;')
        head.addWidget(self.state_lbl)
        root.addLayout(head)

        # ── drive mode ──
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.btn_manual = QPushButton('MANUAL')
        self.btn_auto = QPushButton('AUTONOMOUS')
        for b in (self.btn_manual, self.btn_auto):
            b.setCheckable(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setMinimumHeight(32)
            mode_row.addWidget(b)
        self.btn_manual.setChecked(True)
        self.btn_manual.clicked.connect(lambda: self._set_mode('manual'))
        self.btn_auto.clicked.connect(lambda: self._set_mode('auto'))
        root.addLayout(mode_row)

        # ── joystick ──
        joy_box = QGroupBox('TELEOP · DRAG = PROPORTIONAL · WASD / ARROWS')
        jl = QVBoxLayout(joy_box)
        self.joystick = Joystick()
        jl.addWidget(self.joystick, alignment=Qt.AlignHCenter)
        self.joystick.vector.connect(self._joy_vector)
        root.addWidget(joy_box)

        # ── speed ──
        speed_box = QGroupBox('SPEED LIMIT')
        sl = QVBoxLayout(speed_box)
        row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(int(prefs.speed_min * 100),
                                   int(prefs.speed_max * 100))
        self.speed_slider.setValue(int(prefs.speed_default * 100))
        self.speed_slider.valueChanged.connect(self._speed_moved)
        self.speed_lbl = QLabel(f'{prefs.speed_default:.2f} m/s')
        self.speed_lbl.setStyleSheet(f'color:{theme.ACCENT}; '
                                     f'font-family:{theme.MONO}; font-weight:700;')
        self.speed_lbl.setMinimumWidth(70)
        self.speed_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(self.speed_slider, 1)
        row.addWidget(self.speed_lbl)
        sl.addLayout(row)
        presets = QHBoxLayout()
        presets.setSpacing(5)
        for pct in (25, 50, 75, 100):
            b = QPushButton(f'{pct}%')
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet('font-size:10px; padding:3px 0;')
            b.clicked.connect(lambda _=False, p=pct: self._preset(p))
            presets.addWidget(b)
        sl.addLayout(presets)
        root.addWidget(speed_box)

        # ── intervention tools (robot2) ──
        self.tools_box = QGroupBox('INTERVENTION TOOLS')
        tl = QGridLayout(self.tools_box)
        tl.setSpacing(7)
        self.pump_btn = QPushButton('PUMP — HOLD TO SPRAY · MAX 5 s')
        self.pump_btn.setFocusPolicy(Qt.NoFocus)
        self.pump_btn.setMinimumHeight(40)
        self.pump_btn.setStyleSheet(
            f'background:#0c3349; border:1px solid #155e85; color:#7dd3fc; '
            'font-weight:700; border-radius:8px;')
        self.pump_btn.pressed.connect(lambda: self._pump(True))
        self.pump_btn.released.connect(lambda: self._pump(False))
        tl.addWidget(self.pump_btn, 0, 0, 1, 3)
        cap = QLabel('ARM')
        cap.setStyleSheet(f'color:{theme.MUTED}; font-size:9px; font-weight:700;')
        tl.addWidget(cap, 1, 0)
        self.servo_slider = QSlider(Qt.Horizontal)
        self.servo_slider.setRange(10, 170)
        self.servo_slider.setValue(90)
        self.servo_slider.sliderReleased.connect(
            lambda: self.servoRequested.emit(self.servo_slider.value()))
        self.servo_lbl = QLabel('90°')
        self.servo_lbl.setStyleSheet(f'color:{theme.ACCENT}; '
                                     f'font-family:{theme.MONO}; font-weight:700;')
        self.servo_slider.valueChanged.connect(
            lambda v: self.servo_lbl.setText(f'{v}°'))
        tl.addWidget(self.servo_slider, 1, 1)
        tl.addWidget(self.servo_lbl, 1, 2)
        root.addWidget(self.tools_box)

        root.addStretch(1)

        # ── E-STOP ──
        self.estop_btn = QPushButton('EMERGENCY STOP · Esc')
        self.estop_btn.setFocusPolicy(Qt.NoFocus)
        self.estop_btn.setMinimumHeight(46)
        self.estop_btn.setStyleSheet(theme.ESTOP_IDLE)
        self.estop_btn.clicked.connect(lambda: self.set_estop(not self._estop))
        root.addWidget(self.estop_btn)

    # ── public API ────────────────────────────────────────────────────────
    def set_target(self, name: str, robot_id: str, has_tools: bool) -> None:
        self.target_lbl.setText(f'{name} · {robot_id}')
        self.tools_box.setVisible(has_tools)

    def set_estop(self, engage: bool) -> None:
        if engage == self._estop:
            return
        self._estop = engage
        self.joystick.set_enabled_logic(not engage)
        if engage:
            self.state_lbl.setText('⛔ E-STOP')
            self.state_lbl.setStyleSheet(f'color:{theme.BAD}; font-weight:800;'
                                         'font-size:11px; letter-spacing:2px;')
            self.estop_btn.setText('RELEASE E-STOP')
            self.estop_btn.setStyleSheet(theme.ESTOP_ENGAGED)
        else:
            self.state_lbl.setText('READY')
            self.state_lbl.setStyleSheet(f'color:{theme.GOOD}; font-weight:800;'
                                         'font-size:11px; letter-spacing:2px;')
            self.estop_btn.setText('EMERGENCY STOP · Esc')
            self.estop_btn.setStyleSheet(theme.ESTOP_IDLE)
        self.estopToggled.emit(engage)

    @property
    def estop_engaged(self) -> bool:
        return self._estop

    def set_mode_display(self, mode: str) -> None:
        self.btn_manual.setChecked(mode == 'manual')
        self.btn_auto.setChecked(mode == 'auto')

    def set_servo_feedback(self, deg: int) -> None:
        if not self.servo_slider.isSliderDown():
            self.servo_slider.blockSignals(True)
            self.servo_slider.setValue(deg)
            self.servo_slider.blockSignals(False)
            self.servo_lbl.setText(f'{deg}°')

    def keyboard_vector(self, turn: float, fwd: float) -> None:
        """Keyboard drive path (held keys) — same stream as the joystick."""
        if self._estop:
            return
        if turn == 0.0 and fwd == 0.0:
            self.stopRequested.emit()
        else:
            self.driveRequested.emit(fwd * self._speed,
                                     turn * -self.prefs.turn_rate)

    def current_speed(self) -> float:
        return self._speed

    # ── internals ─────────────────────────────────────────────────────────
    def _joy_vector(self, turn: float, fwd: float) -> None:
        if self._estop:
            return
        if turn == 0.0 and fwd == 0.0:
            self.stopRequested.emit()
            if not self._estop:
                self.state_lbl.setText('READY')
        else:
            self.state_lbl.setText('DRIVING')
            self.driveRequested.emit(fwd * self._speed,
                                     turn * -self.prefs.turn_rate)

    def _set_mode(self, mode: str) -> None:
        self.set_mode_display(mode)
        self.modeChanged.emit(mode)

    def _speed_moved(self, value: int) -> None:
        self._speed = value / 100.0
        self.speed_lbl.setText(f'{self._speed:.2f} m/s')
        self.speedChanged.emit(self._speed)

    def _preset(self, pct: int) -> None:
        span = self.prefs.speed_max - self.prefs.speed_min
        self.speed_slider.setValue(
            int((self.prefs.speed_min + span * pct / 100) * 100))

    def _pump(self, on: bool) -> None:
        if self._estop and on:
            return
        self.pumpRequested.emit(on)
