"""GP Operations Center — docking shell and signal router.

Layout philosophy: the MAP is the central widget and absorbs all free
space; everything else is a dock the operator can move, float, resize or
hide (View menu). The arrangement persists across sessions (QSettings).

    ┌────────────────────────────────────────────────────────────┐
    │ command bar: brand · robot pills · model · ALL STOP · exit │
    │ alert banner (hidden when clear)                           │
    ├──────────┬──────────────────────────────────┬──────────────┤
    │ FLEET    │                                  │ OPERATIONS   │
    │ cards    │            SHARED MAP            │ joystick     │
    ├──────────┤      (grid·trails·markers)       │ tools        │
    │ VIDEO    │                                  │ E-STOP       │
    ├──────────┴──────────────────────────────────┴──────────────┤
    │ drawer: INCIDENT LOG · DETECTIONS · DIAGNOSTICS            │
    └────────────────────────────────────────────────────────────┘

Frame model: robot1's SLAM frame IS the shared map frame. Every other
robot carries a FrameOffset (operator-set via the map's SET POSE tool);
poses are transformed in, goals are transformed back out.
"""

from __future__ import annotations

import glob
import os
import time
from functools import partial

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (QApplication, QDockWidget, QLabel, QMainWindow,
                               QMessageBox, QWidget)

from alerts import AlertManager, AlertState
from gpcore.protocol import commands as cmds
from state.store import RobotState
from transport.esp32_link import Esp32Link
from transport.zmq_link import CommandClient, RobotLink
from ui import theme
from ui.alert_banner import AlertBanner
from ui.bottom_panel import BottomPanel
from ui.command_bar import CommandBar
from ui.fleet_panel import FleetPanel
from ui.map.map_widget import MapWidget
from ui.map.projection import (FrameOffset, Pose, apply_offset,
                               detection_to_world, offset_from_alignment,
                               world_point_to_robot)
from ui.ops_panel import OpsPanel
from ui.video_panel import VideoPanel

KEY_VECTORS = {                       # key → (turn, fwd) contribution
    Qt.Key_W: (0, +1), Qt.Key_Up: (0, +1),
    Qt.Key_S: (0, -1), Qt.Key_Down: (0, -1),
    Qt.Key_A: (-1, 0), Qt.Key_Left: (-1, 0),
    Qt.Key_D: (+1, 0), Qt.Key_Right: (+1, 0),
}
FIRE_LABELS = ('fire', 'smoke', 'flame')


class MainWindow(QMainWindow):
    def __init__(self, app_cfg, yolo_manager=None, run_id: str = 'dash'):
        super().__init__()
        self.app_cfg = app_cfg
        self.yolo = yolo_manager
        self.run_id = run_id
        self.active_id = app_cfg.default_robot
        self._frame_caps: dict[int, float] = {}
        self._offsets: dict[str, FrameOffset] = {}
        self._aligned: dict[str, bool] = {}
        self._link_state: dict[str, bool | None] = {}
        self._keys: set[int] = set()
        self._last_sb = 0.0
        self._last_fire_marker = 0.0
        self._hfov = 62.0      # camera horizontal FOV for detection projection

        self.setWindowTitle('GP Operations Center')
        self.resize(1560, 920)

        self._build_transport()
        self._build_ui()
        self._build_menu()
        self._wire_alerts()
        self._wire_inference()
        self._wire_keyboard_stream()
        self._restore_layout()
        self._start()

    # ══════════════════════════════════════════════════════════════════════
    # Construction
    # ══════════════════════════════════════════════════════════════════════
    def _build_transport(self) -> None:
        self.links: dict[str, object] = {}
        self.cmd: dict[str, object] = {}
        self.state: dict[str, RobotState] = {}
        for prof in self.app_cfg.robots:
            st = RobotState(prof.id, parent=self)
            self.state[prof.id] = st
            self._offsets[prof.id] = FrameOffset()
            # robot1's SLAM frame IS the shared frame — aligned by definition
            self._aligned[prof.id] = (prof.id == 'robot1')
            self._link_state[prof.id] = None

            if prof.is_esp32:
                link = Esp32Link(prof.host,
                                 poll_hz=prof.http.get('poll_hz', 2),
                                 timeout_s=prof.http.get('timeout_s', 1.0),
                                 run_id=self.run_id, parent=self)
                link.telemetryReceived.connect(st.on_telemetry)
                link.ackReceived.connect(partial(self._on_ack, prof.id))
                link.linkUp.connect(partial(self._on_link_state, prof.id))
                self.links[prof.id] = link
                self.cmd[prof.id] = link
            else:
                link = RobotLink(prof.host, prof.zmq,
                                 legacy_video_port=prof.legacy_video_port,
                                 parent=self)
                link.telemetryReceived.connect(st.on_telemetry)
                link.scanReceived.connect(st.on_scan)
                link.mapReceived.connect(st.on_map)
                link.healthReceived.connect(st.on_health)
                link.videoFrameReceived.connect(partial(self._on_video, prof.id))
                link.legacyFrameReceived.connect(
                    partial(self._on_legacy_video, prof.id))
                client = CommandClient(prof.host, prof.zmq.get('cmd', 5558),
                                       run_id=self.run_id, parent=self)
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

    def _build_ui(self) -> None:
        # command bar + alert banner stacked as toolbars area substitute
        models = [(os.path.basename(p), p) for p in sorted(
            glob.glob(os.path.join(self.app_cfg.prefs.models_dir, '*.pt')))]
        self.command_bar = CommandBar(self.app_cfg.robots, models,
                                      self.app_cfg.prefs.default_model,
                                      self.run_id, self)
        self.addToolBar(self.command_bar)
        self.command_bar.robotSelected.connect(self._switch_robot)
        self.command_bar.modelSelected.connect(self._switch_model)
        self.command_bar.allStop.connect(self._all_stop)
        self.command_bar.exitRequested.connect(self._confirm_exit)
        self.command_bar.set_active(self.active_id)

        # central: alert banner above the map
        central = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.alert_banner = AlertBanner()
        self.map = MapWidget()
        lay.addWidget(self.alert_banner)
        lay.addWidget(self.map, 1)
        self.setCentralWidget(central)
        self.map.set_active_robot(self.active_id)
        self.map.goalRequested.connect(self._goal_clicked)
        self.map.posePicked.connect(self._pose_picked)
        self.map.markerPlaced.connect(
            lambda x, y: self.map.add_marker('PIN', x, y, robot='operator',
                                             t_wall=time.strftime('%H:%M:%S')))

        # docks
        self.fleet = FleetPanel(self.app_cfg.robots)
        self.fleet.activateClicked.connect(self._switch_robot)
        self.fleet.locateClicked.connect(self._locate_robot)
        self._dock_fleet = self._dock('FLEET', self.fleet,
                                      Qt.LeftDockWidgetArea, 'dockFleet')

        self.video = VideoPanel()
        self.video.set_robot(self.active_id)
        self._dock_video = self._dock('LIVE FEED', self.video,
                                      Qt.LeftDockWidgetArea, 'dockVideo')

        self.ops = OpsPanel(self.app_cfg.prefs)
        self._dock_ops = self._dock('OPERATIONS', self.ops,
                                    Qt.RightDockWidgetArea, 'dockOps')
        self.ops.driveRequested.connect(self._drive)
        self.ops.stopRequested.connect(self._stop)
        self.ops.estopToggled.connect(self._estop)
        self.ops.modeChanged.connect(self._mode_changed)
        self.ops.speedChanged.connect(self._speed_changed)
        self.ops.pumpRequested.connect(self._pump)
        self.ops.servoRequested.connect(self._servo)
        self._update_ops_target()

        self.drawer = BottomPanel(self.app_cfg.robots)
        self._dock_drawer = self._dock('OPERATIONS LOG', self.drawer,
                                       Qt.BottomDockWidgetArea, 'dockDrawer')
        self.drawer.detections.locateRequested.connect(self.map.center_on)
        self.drawer.detections.clearRequested.connect(self.map.clear_markers)
        self.map.markersChanged.connect(self.drawer.detections.set_markers)

        self.resizeDocks([self._dock_fleet, self._dock_video], [300, 330],
                         Qt.Horizontal)
        self.resizeDocks([self._dock_fleet, self._dock_video], [380, 330],
                         Qt.Vertical)
        self.resizeDocks([self._dock_ops], [330], Qt.Horizontal)
        self.resizeDocks([self._dock_drawer], [200], Qt.Vertical)

        sb = self.statusBar()
        self.sb_nav = QLabel('nav —')
        self.sb_enc = QLabel('enc —')
        self.sb_acc = QLabel('')
        for w in (self.sb_nav, self.sb_enc, self.sb_acc):
            sb.addWidget(w)
        sb.addPermanentWidget(QLabel(
            'Esc e-stop · Space stop · WASD drive · F9 alert drill'))

    def _dock(self, title: str, widget, area, name: str) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetMovable
                         | QDockWidget.DockWidgetFloatable
                         | QDockWidget.DockWidgetClosable)
        self.addDockWidget(area, dock)
        return dock

    def _build_menu(self) -> None:
        view = self.menuBar().addMenu('&View')
        for dock in (self._dock_fleet, self._dock_video, self._dock_ops,
                     self._dock_drawer):
            view.addAction(dock.toggleViewAction())
        view.addSeparator()
        fit = QAction('Fit map', self)
        fit.triggered.connect(self.map.fit_map)
        view.addAction(fit)
        reset = QAction('Reset layout', self)
        reset.triggered.connect(self._reset_layout)
        view.addAction(reset)

        tools = self.menuBar().addMenu('&Tools')
        drill = QAction('Fire alert drill\tF9', self)
        drill.triggered.connect(lambda: self.alerts.drill('FIRE'))
        tools.addAction(drill)
        clear = QAction('Clear map markers', self)
        clear.triggered.connect(self.map.clear_markers)
        tools.addAction(clear)

    def _wire_alerts(self) -> None:
        self.alerts = AlertManager(
            parent=self, fire_conf_min=self.app_cfg.prefs.fire_conf_min)
        self.alerts.alertRaised.connect(self._on_alert_raised)
        self.alerts.alertAcked.connect(self.alert_banner.on_acked)
        self.alerts.alertCleared.connect(self.alert_banner.on_cleared)
        self.alerts.logEvent.connect(
            lambda line: self.drawer.log.append_line(line, source='local'))
        self.alert_banner.ackClicked.connect(self.alerts.acknowledge)
        self.alert_banner.locateClicked.connect(self._locate_alert)

    def _wire_inference(self) -> None:
        if self.yolo is None:
            self.video.set_ai_state(False, 'inference disabled')
            return
        self.yolo.annotatedFrame.connect(self._on_annotated)
        self.yolo.availabilityChanged.connect(self._on_ai_state)
        self.yolo.modelChanged.connect(
            lambda p: self._log(f'AI model active: {os.path.basename(p)}'))

    def _wire_keyboard_stream(self) -> None:
        # keyboard drives the same 10 Hz stream as the joystick
        self._key_timer = QTimer(self)
        self._key_timer.setInterval(int(1000 / cmds.DRIVE_STREAM_HZ))
        self._key_timer.timeout.connect(self._keyboard_tick)

    def _start(self) -> None:
        for link in self.links.values():
            link.start()
        for client in self.cmd.values():
            if client not in self.links.values():
                client.start()
        self._log(f'operations center up — run {self.run_id}, '
                  f'active {self.active_id}')

    # ══════════════════════════════════════════════════════════════════════
    # Frame helpers
    # ══════════════════════════════════════════════════════════════════════
    def _aligned_pose(self, robot_id: str) -> Pose | None:
        odom = self.state[robot_id].telemetry.get('odom')
        if not odom:
            return None
        return apply_offset(Pose(odom['x'], odom['y'], odom['th']),
                            self._offsets[robot_id])

    # ══════════════════════════════════════════════════════════════════════
    # Operator actions
    # ══════════════════════════════════════════════════════════════════════
    def _client(self):
        return self.cmd[self.active_id]

    def _drive(self, vx: float, wz: float) -> None:
        self._client().drive(vx, wz)

    def _stop(self) -> None:
        self._client().drive(0.0, 0.0)

    def _estop(self, engage: bool) -> None:
        self._client().estop(engage)
        self._log(f'E-STOP {"ENGAGED" if engage else "released"} → {self.active_id}')

    def _all_stop(self) -> None:
        for rid, client in self.cmd.items():
            client.estop(True)
        self.ops.set_estop(True)
        self._log('ALL STOP — every robot e-stopped (release per robot)')

    def _mode_changed(self, mode: str) -> None:
        enable = (mode == 'auto')
        self._client().send(cmds.CMD_EXPLORE, {'enable': enable})
        if not enable:
            self._stop()
        self._log(f'{self.active_id} drive mode → {mode.upper()}')

    def _speed_changed(self, value: float) -> None:
        prefs = self.app_cfg.prefs
        span = max(1e-6, prefs.speed_max - prefs.speed_min)
        self._client().send(cmds.CMD_SPEED,
                            {'value': (value - prefs.speed_min) / span})

    def _pump(self, on: bool) -> None:
        self._client().send(cmds.CMD_PUMP, {'on': on})
        self._log(f'pump {"ON" if on else "OFF"} requested')

    def _servo(self, deg: int) -> None:
        self._client().send(cmds.CMD_SERVO, {'deg': deg})

    def _goal_clicked(self, x: float, y: float) -> None:
        # click is in the SHARED frame; the robot executes in ITS frame
        rx, ry = world_point_to_robot(x, y, self._offsets[self.active_id])
        self._client().send(cmds.CMD_GOAL, {'x': round(rx, 3), 'y': round(ry, 3)})
        self.map.set_goal(x, y)
        self._log(f'goal → shared ({x:.2f}, {y:.2f}) = '
                  f'{self.active_id} frame ({rx:.2f}, {ry:.2f})')

    def _pose_picked(self, x: float, y: float, th: float) -> None:
        odom = self.state[self.active_id].telemetry.get('odom') or \
            {'x': 0.0, 'y': 0.0, 'th': 0.0}
        raw = Pose(odom['x'], odom['y'], odom['th'])
        self._offsets[self.active_id] = offset_from_alignment(
            raw, Pose(x, y, th))
        self._aligned[self.active_id] = True
        self.map.reset_mode()
        self._log(f'{self.active_id} aligned to map at '
                  f'({x:.2f}, {y:.2f}, {th:.2f} rad)')

    def _switch_robot(self, robot_id: str) -> None:
        if robot_id == self.active_id:
            self.command_bar.set_active(robot_id)
            return
        self.ops.set_estop(False)                 # latch belongs to old robot
        self.active_id = robot_id
        self.command_bar.set_active(robot_id)
        self.fleet.set_active(robot_id)
        self.map.set_active_robot(robot_id)
        self.map.clear_goal()
        self.video.set_robot(robot_id)
        self._update_ops_target()
        up = self._link_state.get(robot_id)
        if up is not None:
            self.command_bar.set_active_link_chip(up)
        self._log(f'active robot → {robot_id}')

    def _update_ops_target(self) -> None:
        prof = self.app_cfg.profile(self.active_id)
        self.ops.set_target(prof.name, prof.id,
                            has_tools=(prof.id == 'robot2'))

    def _switch_model(self, path: str) -> None:
        if self.yolo is not None:
            self.yolo.set_model(path)

    def _locate_robot(self, robot_id: str) -> None:
        pose = self.map.robot_pose(robot_id)
        if pose:
            self.map.center_on(pose[0], pose[1])

    def _locate_alert(self, kind: str) -> None:
        for m in reversed(self.map._markers):
            if m.kind == kind:
                self.map.center_on(m.x, m.y)
                return

    # ══════════════════════════════════════════════════════════════════════
    # Robot state → UI (multi-robot; video/scan/goal follow the active one)
    # ══════════════════════════════════════════════════════════════════════
    def _on_telemetry(self, robot_id: str, payload: dict) -> None:
        esp = payload.get('esp32')
        if isinstance(esp, dict):                 # gas alarms are fleet-wide
            self.alerts.process_gas(robot_id, bool(esp.get('a')), esp.get('g'))

        pose = self._aligned_pose(robot_id)
        if pose is not None:
            self.map.update_robot(robot_id, pose.x, pose.y, pose.th)
            card = self.fleet.cards.get(robot_id)
            if card:
                import math
                card.set_pose(pose.x, pose.y, math.degrees(pose.th),
                              self._aligned[robot_id])

        if not robot_id == self.active_id:
            return
        nav = payload.get('nav_status', '')
        if nav.startswith('ARRIVED'):
            self.map.clear_goal()
        servo = payload.get('servo_deg')
        if servo is not None:
            self.ops.set_servo_feedback(int(servo))

        now = time.monotonic()
        if now - self._last_sb >= 0.25:
            self._last_sb = now
            state = (nav or 'IDLE').split(':')[0]
            color = {'DRIVING': theme.ACCENT, 'ROTATING': theme.WARN,
                     'ARRIVED': theme.GOOD}.get(state, theme.MUTED)
            self.sb_nav.setText(f'{robot_id} · nav {nav or "IDLE"}')
            self.sb_nav.setStyleSheet(f'color:{color};')
            enc = payload.get('enc')
            self.sb_enc.setText(f'enc {enc}' if enc else 'enc —')
            acc = payload.get('accessory')
            self.sb_acc.setText(f'acc {acc}' if acc else '')

    def _on_scan(self, robot_id: str, payload: dict) -> None:
        pose = self._aligned_pose(robot_id)
        if pose is not None:
            self.map.update_scan(payload, (pose.x, pose.y, pose.th))

    def _on_map(self, robot_id: str, payload: dict) -> None:
        self.map.update_map(payload)              # robot1 is the map source

    def _on_health(self, robot_id: str, payload: dict) -> None:
        self.drawer.diagnostics.update_vitals(robot_id, payload)
        card = self.fleet.cards.get(robot_id)
        if card:
            sysv = payload.get('sys', {}) or {}
            thr = sysv.get('throttled')
            warn = bool(thr and thr not in ('0x0', '0X0'))
            card.set_vitals(
                f"{sysv.get('temp_c', '—')}°C · {sysv.get('rssi_dbm', '—')}dBm"
                + (' ⚠' if warn else ''), warn)

    def _on_staleness(self, robot_id: str, staleness: dict) -> None:
        card = self.fleet.cards.get(robot_id)
        if card:
            card.set_staleness(staleness)

    def _on_robot_log(self, robot_id: str, line: str) -> None:
        self.drawer.log.append_line(f'{robot_id}: {line}')

    def _on_robot_estop(self, robot_id: str, engaged: bool) -> None:
        if robot_id == self.active_id:
            self.ops.set_estop(engaged)

    def _on_link_state(self, robot_id: str, up: bool) -> None:
        self._link_state[robot_id] = up
        self.command_bar.set_robot_link(robot_id, up)
        if robot_id == self.active_id:
            self.command_bar.set_active_link_chip(up)
        self._log(f'{robot_id} command link {"up" if up else "DOWN"}')

    def _on_ack(self, robot_id: str, cmd_id: str, cmd_type: str, ok: bool,
                detail: str) -> None:
        self.state[robot_id].on_cmd_ack()
        if not ok:
            self._log(f'{robot_id} REJECTED {cmd_type}: {detail}')

    def _on_cmd_failed(self, robot_id: str, cmd_id: str, cmd_type: str,
                       reason: str) -> None:
        self._log(f'{robot_id} {cmd_type} FAILED: {reason}')

    # ══════════════════════════════════════════════════════════════════════
    # Video, inference, detection → map projection
    # ══════════════════════════════════════════════════════════════════════
    def _on_video(self, robot_id: str, meta, jpeg: bytes) -> None:
        if robot_id != self.active_id:
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
            self.video.show_jpeg(jpeg, st.video_frame_age_s(cap))

    def _on_legacy_video(self, robot_id: str, jpeg: bytes) -> None:
        if robot_id != self.active_id:
            return
        if self.state[robot_id].streams['video'].age_s() < 2.0:
            return
        if self.yolo is not None and self.yolo.available:
            self.yolo.submit_frame(0, jpeg)
        else:
            self.video.show_jpeg(jpeg, None)

    def _on_annotated(self, frame_id: int, jpeg: bytes, detections) -> None:
        st = self.state.get(self.active_id)
        cap = self._frame_caps.get(frame_id)
        age = st.video_frame_age_s(cap) if (st and cap) else None
        self.video.show_jpeg(jpeg, age)

        pairs = [(d.get('label', ''), float(d.get('conf', 0.0)))
                 for d in detections or ()]
        self.alerts.process_fire_detections(self.active_id, pairs)

        # Project fire onto the shared map — ONLY while the (debounced) FIRE
        # alert is live, at most 2×/s, best detection of the frame. One fire
        # event = one marker; the map merges + smooths repeats.
        if self.alerts.state('FIRE') is AlertState.CLEAR:
            return
        now = time.monotonic()
        if now - self._last_fire_marker < 0.5:
            return
        pose = self._aligned_pose(self.active_id)
        if pose is None:
            return
        best = None
        for d in detections or ():
            label = str(d.get('label', '')).strip().lower()
            conf = float(d.get('conf', 0.0))
            if label in FIRE_LABELS and conf >= self.app_cfg.prefs.fire_conf_min:
                if best is None or conf > best[1]:
                    best = (d, conf)
        if best is None:
            return
        self._last_fire_marker = now
        d, conf = best
        x, y = detection_to_world(pose, float(d.get('cx', 0.5)),
                                  float(d.get('h', 0.3)), self._hfov)
        self.map.add_marker('FIRE', x, y, conf=round(conf * 100),
                            robot=self.active_id,
                            t_wall=time.strftime('%H:%M:%S'))
        self.video.flash_detection(
            f'fire {conf * 100:.0f}% → map ({x:+.1f}, {y:+.1f})')

    def _on_ai_state(self, on: bool, reason: str) -> None:
        self.video.set_ai_state(on, reason)
        if not on and reason:
            self._log(f'AI OFF: {reason}')

    # ══════════════════════════════════════════════════════════════════════
    # Alerts
    # ══════════════════════════════════════════════════════════════════════
    def _on_alert_raised(self, kind: str, info: dict) -> None:
        self.alert_banner.on_raised(kind, info)
        QApplication.beep()
        if kind == 'GAS':                          # mark the reporting robot's spot
            pose = self._aligned_pose(info.get('robot', '')) or Pose(0, 0, 0)
            self.map.add_marker('GAS', pose.x, pose.y,
                                conf=None, robot=info.get('robot', ''),
                                t_wall=info.get('t_wall', ''))

    # ══════════════════════════════════════════════════════════════════════
    # Keyboard (same 10 Hz stream as the joystick)
    # ══════════════════════════════════════════════════════════════════════
    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.isAutoRepeat():
            return
        if e.key() == Qt.Key_Escape:
            self.ops.set_estop(True)
            return
        if e.key() == Qt.Key_F9:
            self.alerts.drill('FIRE')
            return
        if e.key() == Qt.Key_Space:
            self._keys.clear()
            self._key_timer.stop()
            self.ops.keyboard_vector(0.0, 0.0)
            return
        if e.key() in KEY_VECTORS:
            self._keys.add(e.key())
            if not self._key_timer.isActive():
                self._key_timer.start()
                self._keyboard_tick()
            return
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QKeyEvent) -> None:
        if e.isAutoRepeat():
            return
        if e.key() in KEY_VECTORS:
            self._keys.discard(e.key())
            if not self._keys:
                self._key_timer.stop()
                self.ops.keyboard_vector(0.0, 0.0)
            return
        super().keyReleaseEvent(e)

    def _keyboard_tick(self) -> None:
        turn = max(-1, min(1, sum(KEY_VECTORS[k][0] for k in self._keys)))
        fwd = max(-1, min(1, sum(KEY_VECTORS[k][1] for k in self._keys)))
        self.ops.keyboard_vector(turn, fwd)

    # ══════════════════════════════════════════════════════════════════════
    # Layout persistence & lifecycle
    # ══════════════════════════════════════════════════════════════════════
    def _settings(self) -> QSettings:
        return QSettings('GP', 'OperationsCenter')

    def _restore_layout(self) -> None:
        self._default_state = self.saveState()
        s = self._settings()
        geo = s.value('geometry')
        state = s.value('windowState')
        if geo is not None:
            self.restoreGeometry(geo)
        if state is not None:
            self.restoreState(state)

    def _reset_layout(self) -> None:
        self.restoreState(self._default_state)
        for dock in (self._dock_fleet, self._dock_video, self._dock_ops,
                     self._dock_drawer):
            dock.show()

    def _confirm_exit(self) -> None:
        if QMessageBox.question(
                self, 'Exit console',
                'Close the operations center?\n\nRobots stop automatically '
                'via the deadman chain; a latched e-stop stays latched.',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) == QMessageBox.Yes:
            self.close()

    def _log(self, line: str) -> None:
        self.drawer.log.append_line(line, source='local')

    def closeEvent(self, event) -> None:
        s = self._settings()
        s.setValue('geometry', self.saveGeometry())
        s.setValue('windowState', self.saveState())
        for client in set(self.cmd.values()) | set(self.links.values()):
            try:
                client.stop()
            except Exception:
                pass
        if self.yolo is not None:
            self.yolo.stop()
        event.accept()
