"""Main window — assembles views, owns per-robot links/state, routes signals.

Design rules:
  * transport threads → RobotState (single writer) → views; views never
    touch sockets
  * ALL robots stay connected (cheap; ZMQ reconnects in the background);
    the ACTIVE robot drives video/map/controls, others still log + health
  * keyboard always works: WASD/arrows hold-to-drive, Space stop, Esc e-stop
"""

from __future__ import annotations

import glob
import os
import time
from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (QComboBox, QLabel, QMainWindow, QPushButton,
                               QSizePolicy, QSplitter, QTabWidget, QToolBar,
                               QVBoxLayout, QWidget)

from gpcore.protocol import commands as cmds
from state.store import RobotState
from transport.esp32_link import Esp32Link
from transport.zmq_link import CommandClient, RobotLink
from views import theme
from views.control_panel import ControlPanel
from views.health_panel import HealthPanel
from views.log_console import LogConsole
from views.map_view import MapView
from views.theme import Card, chip
from views.video_view import VideoView

KEY_DIRS = {
    Qt.Key_W: 'F', Qt.Key_Up: 'F',
    Qt.Key_S: 'B', Qt.Key_Down: 'B',
    Qt.Key_A: 'L', Qt.Key_Left: 'L',
    Qt.Key_D: 'R', Qt.Key_Right: 'R',
}


class MainWindow(QMainWindow):
    def __init__(self, app_cfg, yolo_manager=None, run_id: str = 'dash'):
        super().__init__()
        self.app_cfg = app_cfg
        self.yolo = yolo_manager
        self.run_id = run_id
        self.active_id = app_cfg.default_robot
        self._frame_caps: dict[int, float] = {}      # frame_id → cap_t_mono

        self.setWindowTitle('GP Fleet Console')
        self.resize(1480, 880)
        self._last_sb_update = 0.0

        # ── per-robot transport + state ──
        self.links: dict[str, object] = {}
        self.cmd: dict[str, object] = {}
        self.state: dict[str, RobotState] = {}
        for prof in app_cfg.robots:
            st = RobotState(prof.id, parent=self)
            self.state[prof.id] = st
            if prof.is_esp32:
                link = Esp32Link(prof.host,
                                 poll_hz=prof.http.get('poll_hz', 2),
                                 timeout_s=prof.http.get('timeout_s', 1.0),
                                 run_id=run_id, parent=self)
                link.telemetryReceived.connect(st.on_telemetry)
                link.ackReceived.connect(
                    partial(self._on_ack, prof.id))
                self.links[prof.id] = link
                self.cmd[prof.id] = link              # same object serves both
            else:
                link = RobotLink(prof.host, prof.zmq,
                                 legacy_video_port=prof.legacy_video_port,
                                 parent=self)
                link.telemetryReceived.connect(st.on_telemetry)
                link.scanReceived.connect(st.on_scan)
                link.mapReceived.connect(st.on_map)
                link.healthReceived.connect(st.on_health)
                link.videoFrameReceived.connect(
                    partial(self._on_video, prof.id))
                link.legacyFrameReceived.connect(
                    partial(self._on_legacy_video, prof.id))
                client = CommandClient(prof.host, prof.zmq.get('cmd', 5558),
                                       run_id=run_id, parent=self)
                client.ackReceived.connect(partial(self._on_ack, prof.id))
                client.commandFailed.connect(partial(self._on_cmd_failed, prof.id))
                client.linkUp.connect(partial(self._on_link_state, prof.id))
                self.links[prof.id] = link
                self.cmd[prof.id] = client

            st.telemetryChanged.connect(partial(self._on_telemetry, prof.id))
            st.scanChanged.connect(partial(self._on_scan, prof.id))
            st.mapChanged.connect(partial(self._on_map, prof.id))
            st.healthChanged.connect(partial(self._on_health, prof.id))
            st.stalenessChanged.connect(partial(self._on_staleness, prof.id))
            st.logLine.connect(partial(self._on_robot_log, prof.id))
            st.estopChanged.connect(partial(self._on_robot_estop, prof.id))

        # ── toolbar ──
        tb = QToolBar('Fleet')
        tb.setMovable(False)
        self.addToolBar(tb)

        title = QLabel('GP <b>FLEET</b> CONSOLE')
        title.setObjectName('appTitle')
        tb.addWidget(title)

        robot_lbl = QLabel('ROBOT')
        robot_lbl.setObjectName('sectionTitle')
        tb.addWidget(robot_lbl)
        self.robot_combo = QComboBox()
        for prof in app_cfg.robots:
            self.robot_combo.addItem(f'{prof.name}  ·  {prof.id}', prof.id)
        self.robot_combo.setCurrentIndex(
            max(0, [p.id for p in app_cfg.robots].index(self.active_id)))
        self.robot_combo.currentIndexChanged.connect(self._robot_switched)
        tb.addWidget(self.robot_combo)

        model_lbl = QLabel('AI MODEL')
        model_lbl.setObjectName('sectionTitle')
        tb.addWidget(model_lbl)
        self.model_combo = QComboBox()
        for p in sorted(glob.glob(os.path.join(app_cfg.prefs.models_dir, '*.pt'))):
            self.model_combo.addItem(os.path.basename(p), p)
        idx = self.model_combo.findText(app_cfg.prefs.default_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.currentIndexChanged.connect(self._model_switched)
        tb.addWidget(self.model_combo)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.link_chip = chip('LINK …')
        tb.addWidget(self.link_chip)
        self.runid_chip = chip(f'run {run_id}')
        tb.addWidget(self.runid_chip)

        # ── central layout (cards inside splitters) ──
        self.video_view = VideoView()
        self.log_console = LogConsole()
        self.map_view = MapView()
        self.map_view.goalClicked.connect(self._goal_clicked)

        video_card = Card('LIVE FEED')
        video_card.body.addWidget(self.video_view)
        log_card = Card('INCIDENT LOG')
        log_card.body.addWidget(self.log_console)

        map_card = Card('SLAM MAP  ·  click to set goal')
        fit_btn = QPushButton('FIT VIEW')
        fit_btn.setObjectName('fitBtn')
        fit_btn.setFocusPolicy(Qt.NoFocus)
        fit_btn.clicked.connect(self.map_view.fit_map)
        map_card.header.addWidget(fit_btn)
        map_card.body.addWidget(self.map_view)

        tabs = QTabWidget()
        tabs.setFocusPolicy(Qt.NoFocus)
        self.control_panel = ControlPanel(
            app_cfg.prefs, accessories_enabled=(self.active_id == 'robot2'))
        self.health_panel = HealthPanel()
        tabs.addTab(self.control_panel, 'CONTROL')
        tabs.addTab(self.health_panel, 'HEALTH')
        panel_card = Card(padding=8)
        panel_card.body.addWidget(tabs)

        left = QSplitter(Qt.Vertical)
        left.addWidget(video_card)
        left.addWidget(log_card)
        left.setSizes([580, 240])

        right = QSplitter(Qt.Vertical)
        right.addWidget(map_card)
        right.addWidget(panel_card)
        right.setSizes([420, 420])

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([860, 600])

        wrapper = QWidget()
        outer = QVBoxLayout(wrapper)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(split)
        self.setCentralWidget(wrapper)

        # status bar: structured fields, updated at most 4×/s
        sb = self.statusBar()
        self.sb_nav = QLabel('nav —')
        self.sb_enc = QLabel('enc —')
        self.sb_acc = QLabel('acc —')
        for w in (self.sb_nav, self.sb_enc, self.sb_acc):
            sb.addWidget(w)

        # ── control panel → active robot ──
        cp = self.control_panel
        cp.driveRequested.connect(self._drive)
        cp.stopRequested.connect(self._stop)
        cp.estopToggled.connect(self._estop)
        cp.exploreToggled.connect(self._explore)
        cp.speedChanged.connect(self._speed)
        cp.pumpRequested.connect(self._pump)
        cp.servoRequested.connect(self._servo)

        # ── inference ──
        if self.yolo is not None:
            self.yolo.annotatedFrame.connect(self._on_annotated)
            self.yolo.availabilityChanged.connect(self._on_ai_state)
            self.yolo.modelChanged.connect(
                lambda p: self._local_log(f'AI model active: {os.path.basename(p)}'))
        else:
            self.video_view.set_ai_state(False, 'inference disabled')

        for link in self.links.values():
            link.start()
        for client in self.cmd.values():
            if client not in self.links.values():
                client.start()
        self._local_log(f'console up — run {run_id}, active robot {self.active_id}')

    # ════════ active-robot helpers ════════
    def _client(self):
        return self.cmd[self.active_id]

    def _is_active(self, robot_id: str) -> bool:
        return robot_id == self.active_id

    # ════════ controls → commands ════════
    def _drive(self, vx: float, wz: float) -> None:
        self._client().drive(vx, wz)

    def _stop(self) -> None:
        self._client().drive(0.0, 0.0)

    def _estop(self, engage: bool) -> None:
        self._client().estop(engage)
        self._local_log(f'E-STOP {"ENGAGED" if engage else "released"} '
                        f'→ {self.active_id}')

    def _explore(self, enable: bool) -> None:
        self._client().send(cmds.CMD_EXPLORE, {'enable': enable})

    def _speed(self, value: float) -> None:
        prefs = self.app_cfg.prefs
        span = max(1e-6, prefs.speed_max - prefs.speed_min)
        norm = (value - prefs.speed_min) / span
        self._client().send(cmds.CMD_SPEED, {'value': norm})

    def _pump(self, on: bool) -> None:
        self._client().send(cmds.CMD_PUMP, {'on': on})
        self._local_log(f'pump {"ON" if on else "OFF"} requested')

    def _servo(self, deg: int) -> None:
        self._client().send(cmds.CMD_SERVO, {'deg': deg})

    def _goal_clicked(self, x: float, y: float) -> None:
        self._client().send(cmds.CMD_GOAL, {'x': round(x, 3), 'y': round(y, 3)})
        self.map_view.set_goal(x, y)
        self._local_log(f'goal → ({x:.2f}, {y:.2f})')

    # ════════ state → views (active robot filter) ════════
    def _on_telemetry(self, robot_id: str, payload: dict) -> None:
        if not self._is_active(robot_id):
            return
        odom = payload.get('odom')
        if odom:
            self.map_view.update_pose(odom['x'], odom['y'], odom['th'])
        nav = payload.get('nav_status', '')
        if nav.startswith('ARRIVED'):
            self.map_view.clear_goal()
        servo = payload.get('servo_deg')
        if servo is not None:
            self.control_panel.set_servo_feedback(int(servo))

        # status bar at 4 Hz max — repainting labels at telemetry rate (20 Hz)
        # is wasted work and makes the text flicker
        now = time.monotonic()
        if now - self._last_sb_update >= 0.25:
            self._last_sb_update = now
            state = (nav or 'IDLE').split(':')[0]
            color = {'DRIVING': theme.ACCENT, 'ROTATING': theme.WARN,
                     'ARRIVED': theme.GOOD}.get(state, theme.MUTED)
            self.sb_nav.setText(f'{robot_id}  ·  nav {nav or "IDLE"}')
            self.sb_nav.setStyleSheet(f'color:{color};')
            enc = payload.get('enc')
            self.sb_enc.setText(f'enc {enc}' if enc else 'enc —')
            acc = payload.get('accessory')
            self.sb_acc.setText(f'acc {acc}' if acc else '')

    def _on_scan(self, robot_id: str, payload: dict) -> None:
        if self._is_active(robot_id):
            self.map_view.update_scan(payload)

    def _on_map(self, robot_id: str, payload: dict) -> None:
        if self._is_active(robot_id):
            self.map_view.update_map(payload)

    def _on_health(self, robot_id: str, payload: dict) -> None:
        if self._is_active(robot_id):
            self.health_panel.update_health(payload)

    def _on_staleness(self, robot_id: str, staleness: dict) -> None:
        if not self._is_active(robot_id):
            return
        st = self.state[robot_id]
        rates = {k: v.rate_ewma_hz for k, v in st.streams.items()
                 if v.staleness.value == 'fresh'}
        self.health_panel.update_staleness(staleness, rates)

    def _on_robot_log(self, robot_id: str, line: str) -> None:
        self.log_console.append_line(f'{robot_id}: {line}')

    def _on_robot_estop(self, robot_id: str, engaged: bool) -> None:
        if self._is_active(robot_id):
            self.control_panel.set_estop(engaged)

    def _on_link_state(self, robot_id: str, up: bool) -> None:
        if self._is_active(robot_id):
            self.link_chip.setText('●  LINK UP' if up else '●  LINK DOWN')
            self.link_chip.setStyleSheet(
                f'color:{theme.GOOD};' if up else f'color:{theme.BAD};')
        self._local_log(f'{robot_id} command link {"up" if up else "DOWN"}')

    def _on_ack(self, robot_id: str, cmd_id: str, cmd_type: str, ok: bool,
                detail: str) -> None:
        self.state[robot_id].on_cmd_ack()
        if not ok:
            self._local_log(f'{robot_id} REJECTED {cmd_type}: {detail}')

    def _on_cmd_failed(self, robot_id: str, cmd_id: str, cmd_type: str,
                       reason: str) -> None:
        self._local_log(f'{robot_id} {cmd_type} FAILED: {reason}')

    # ════════ video path ════════
    def _on_video(self, robot_id: str, meta, jpeg: bytes) -> None:
        if not self._is_active(robot_id):
            return
        st = self.state[robot_id]
        st.on_video_meta(meta)
        cap = meta.payload.get('cap_t_mono', 0.0)
        fid = int(meta.payload.get('frame_id', 0))
        self._frame_caps[fid] = cap
        if len(self._frame_caps) > 64:
            for k in sorted(self._frame_caps)[:-32]:
                self._frame_caps.pop(k, None)
        if self.yolo is not None and self.yolo.available:
            self.yolo.submit_frame(fid, jpeg)
        else:
            self.video_view.show_jpeg(jpeg, st.video_frame_age_s(cap))

    def _on_legacy_video(self, robot_id: str, jpeg: bytes) -> None:
        # only used when the framed channel is silent (old camera script)
        if not self._is_active(robot_id):
            return
        if self.state[robot_id].streams['video'].age_s() < 2.0:
            return
        if self.yolo is not None and self.yolo.available:
            self.yolo.submit_frame(0, jpeg)
        else:
            self.video_view.show_jpeg(jpeg, None)

    def _on_annotated(self, frame_id: int, jpeg: bytes) -> None:
        st = self.state.get(self.active_id)
        cap = self._frame_caps.get(frame_id)
        age = st.video_frame_age_s(cap) if (st and cap) else None
        self.video_view.show_jpeg(jpeg, age)

    def _on_ai_state(self, on: bool, reason: str) -> None:
        self.video_view.set_ai_state(on, reason)
        if not on and reason:
            self._local_log(f'AI OFF: {reason}')

    # ════════ switching ════════
    def _robot_switched(self, _index: int) -> None:
        new_id = self.robot_combo.currentData()
        if new_id == self.active_id:
            return
        self.control_panel.set_estop(False)      # latch belongs to old robot
        self.active_id = new_id
        self.control_panel.set_accessories_enabled(new_id == 'robot2')
        self.map_view.clear_goal()
        self._local_log(f'active robot → {new_id}')

    def _model_switched(self, _index: int) -> None:
        if self.yolo is not None:
            self.yolo.set_model(self.model_combo.currentData())

    # ════════ keyboard ════════
    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.isAutoRepeat():
            return
        if e.key() == Qt.Key_Escape:
            self.control_panel.set_estop(True)
            return
        if e.key() == Qt.Key_Space:
            self.control_panel.keyboard_direction(None)
            return
        d = KEY_DIRS.get(e.key())
        if d:
            self.control_panel.keyboard_direction(d)
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent) -> None:
        if e.isAutoRepeat():
            return
        if e.key() in KEY_DIRS:
            self.control_panel.keyboard_direction(None)
            return
        super().keyReleaseEvent(e)

    # ════════ misc ════════
    def _local_log(self, line: str) -> None:
        self.log_console.append_line(line, source='local')

    def closeEvent(self, event) -> None:
        for client in set(self.cmd.values()) | set(self.links.values()):
            try:
                client.stop()
            except Exception:
                pass
        if self.yolo is not None:
            self.yolo.stop()
        event.accept()
