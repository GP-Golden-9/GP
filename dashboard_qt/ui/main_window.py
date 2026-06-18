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
import math
import os
import time
import zlib
from functools import partial

import numpy as np

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox,
                               QDockWidget, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QPlainTextEdit, QTextEdit, QWidget)

from alerts import AlertManager
from speech import Speaker
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
from ui.map.planner import plan_path
from ui.map.projection import (DIST_K, DIST_K_BY_KIND, FrameOffset, Pose,
                               apply_offset, detection_to_world,
                               offset_from_alignment, world_point_to_robot)
from ui.fire_panel import FirePanel
from ui.map.coverage import coverage_path
from ui.mission import MissionExecutor
from ui.ops_panel import OpsPanel
from ui.video_panel import VideoPanel

KEY_VECTORS = {                       # key → (turn, fwd) contribution
    Qt.Key_W: (0, +1), Qt.Key_Up: (0, +1),
    Qt.Key_S: (0, -1), Qt.Key_Down: (0, -1),
    Qt.Key_A: (-1, 0), Qt.Key_Left: (-1, 0),
    Qt.Key_D: (+1, 0), Qt.Key_Right: (+1, 0),
}
FIRE_LABELS = ('fire', 'smoke', 'flame')

# Detection label (lower-case) → map-marker kind, and → the per-class
# confidence key in prefs.detect_conf. fire/smoke/flame all map to the
# single FIRE marker + 'fire' threshold.
DETECT_KIND = {'person': 'HUMAN', 'dog': 'DOG', 'cat': 'CAT',
               'fire': 'FIRE', 'smoke': 'FIRE', 'flame': 'FIRE'}
DETECT_CONF_KEY = {'person': 'person', 'dog': 'dog', 'cat': 'cat',
                   'fire': 'fire', 'smoke': 'fire', 'flame': 'fire'}
# Spoken phrase per marker kind (Windows SAPI). HUMAN reads as "human".
DETECT_SPEECH = {'HUMAN': 'human detected', 'FIRE': 'fire detected',
                 'DOG': 'dog detected', 'CAT': 'cat detected'}


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
        self._last_marker: dict[str, float] = {}   # kind -> last projection t
        # Spoken detection announcements (Windows SAPI; no-op if unavailable).
        # 4 s per-kind cooldown so a target in view isn't announced every frame.
        self.speaker = Speaker(cooldown_s=4.0)
        self._hfov = 62.0      # camera horizontal FOV for detection projection
        self._grid: np.ndarray | None = None      # latest occupancy (for A*)
        self._grid_meta: tuple | None = None      # (res, ox, oy)
        self._map_source_id: str | None = None    # who publishes the map (SLAM)

        self.setWindowTitle('GP Operations Center')
        self.resize(1560, 920)

        self._build_transport()
        self._build_ui()
        self._build_menu()
        self._wire_alerts()
        self._wire_inference()
        self._wire_keyboard_stream()
        QApplication.instance().installEventFilter(self)
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
            # Wheel-encoder robots (Beta) compute their pose on the LAPTOP from
            # the raw enc+gyro in telemetry — odom was moved off the Pi to free
            # a core so the map tracks live. SLAM robots (Alpha, no encoders)
            # keep their map-frame pose from the gateway.
            if prof.drive.get('ticks_per_rev'):
                from state.local_odom import LocalOdom
                st.local_odom = LocalOdom(prof.drive)
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

            # NOTE: telemetry is NOT rendered per-frame (that backed up the UI
            # thread and lagged the map + readouts). _render_telemetry runs the
            # heavy update on a 30 Hz timer using the LATEST frame — see below.
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

        # central: alert banner (always visible) above a TAB WIDGET. The
        # OPERATIONS LOG used to be a bottom dock that overlapped the map and
        # controls when the window was maximized — it now lives in its own tab
        # beside the map, so nothing overlaps.
        from PySide6.QtWidgets import QVBoxLayout, QTabWidget
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.alert_banner = AlertBanner()
        outer.addWidget(self.alert_banner)

        self.center_tabs = QTabWidget()
        self.center_tabs.setDocumentMode(True)
        self.center_tabs.setFocusPolicy(Qt.NoFocus)   # never swallow WASD
        map_page = QWidget()
        lay = QVBoxLayout(map_page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.map = MapWidget()
        lay.addWidget(self.map, 1)
        self.center_tabs.addTab(map_page, 'MAP')
        outer.addWidget(self.center_tabs, 1)
        self.setCentralWidget(central)
        self.map.set_active_robot(self.active_id)
        self.map.goalRequested.connect(self._goal_clicked)
        self.map.posePicked.connect(self._pose_picked)
        self.map.resetMapRequested.connect(self._reset_map_clicked)
        for prof in self.app_cfg.robots:          # true-scale body outlines
            if prof.footprint:
                self.map.set_footprint(prof.id, prof.footprint)

        # planner output is executed waypoint-by-waypoint by the mission
        self.mission = MissionExecutor(self._send_goal_world, parent=self)
        self.mission.progress.connect(self._log)
        self.mission.waypointActive.connect(self._on_waypoint_active)
        self.mission.missionFinished.connect(self._on_mission_finished)
        self.mission.biasComputed.connect(self._on_mission_bias)
        self._nav_goal: tuple[str, float, float] | None = None   # for replan
        self._nav_replans = 0
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
        # The LIVE FEED follows the active robot IF it has a camera; otherwise
        # it falls back to a camera robot (Beta) — so selecting Alpha (no
        # camera) still shows Beta's view. _cam_robots is learned at runtime
        # from which robots actually deliver frames.
        self._cam_robots: set[str] = set()
        self._video_robot = self.active_id
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
        self.center_tabs.addTab(self.drawer, 'OPERATIONS LOG')
        self.drawer.detections.locateRequested.connect(self.map.center_on)
        self.drawer.detections.clearRequested.connect(self.map.clear_markers)
        self.map.markersChanged.connect(self.drawer.detections.set_markers)

        # ── Master/Slave mission demo (pure dashboard simulation) ──
        # FIRE TEST: place a fire on the map, send Beta to navigate to it
        # autonomously (reuses the real A* + mission executor + ultrasonic
        # avoidance). Replaces the old master/slave simulation.
        self._fire_xy: tuple[float, float] | None = None
        self._placing_fire = False
        # Autonomous sequence state machine (SCAN and FIRE are independent
        # multi-leg sequences sharing the mission executor): None | scan_cover
        # | scan_return | fire_go | fire_pump | fire_return. _seq_home is the
        # base pose captured at the start of a sequence to return to.
        self._seq: str | None = None
        self._seq_home: tuple[float, float] | None = None
        self._seq_phase_label = ''        # steady-phase status (re-shown after a dodge)
        self._pump_timer = QTimer(self)
        self._pump_timer.setSingleShot(True)
        self._pump_timer.timeout.connect(self._pump_done)
        self.fire_panel = FirePanel()
        # AUTONOMY is a DOCK, not a center tab, so the MAP stays visible while
        # the operator runs the autonomy flow (tabbed with OPERATIONS on the
        # right; flip between the joystick and the autonomy panel, map always up).
        self._dock_autonomy = self._dock('AUTONOMY', self.fire_panel,
                                         Qt.RightDockWidgetArea, 'dockAutonomy')
        self.tabifyDockWidget(self._dock_ops, self._dock_autonomy)
        self._dock_autonomy.raise_()
        self.fire_panel.scanRequested.connect(self._scan_area)
        self.fire_panel.placeFireRequested.connect(self._arm_place_fire)
        self.fire_panel.goRequested.connect(self._fire_go)
        self.fire_panel.stopRequested.connect(self._fire_stop)

        self.resizeDocks([self._dock_fleet, self._dock_video], [300, 330],
                         Qt.Horizontal)
        self.resizeDocks([self._dock_fleet, self._dock_video], [380, 330],
                         Qt.Vertical)
        self.resizeDocks([self._dock_ops], [330], Qt.Horizontal)

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
                     self._dock_autonomy):
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
        tools.addSeparator()
        muted = self._settings().value('mute_voice', False, type=bool)
        self.act_mute = QAction('Mute voice announcements', self)
        self.act_mute.setCheckable(True)
        self.act_mute.setShortcut('Ctrl+M')
        self.act_mute.setChecked(muted)
        self.speaker.set_muted(muted)
        self.act_mute.toggled.connect(self._on_mute_toggled)
        tools.addAction(self.act_mute)

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

        # Render telemetry (map pose, fleet cards, ultrasonic readout, mission)
        # off the LATEST frame at a fixed 30 Hz, decoupled from arrival. Heavy
        # per-frame rendering used to run inside the telemetry callback and
        # back up the UI thread, so the map and readouts trailed real motion.
        self._tele_render_rev: dict[str, int] = {}
        self._tele_timer = QTimer(self)
        self._tele_timer.setInterval(33)            # ~30 Hz
        self._tele_timer.timeout.connect(self._render_telemetry)
        self._tele_timer.start()

        # AUTONOMOUS safety heartbeat: while armed, re-affirm at 2 Hz so the
        # robot's local nav stops if this console disappears.
        self._auto_robot: str | None = None
        self._auto_hb = QTimer(self)
        self._auto_hb.setInterval(500)              # 2 Hz
        self._auto_hb.timeout.connect(self._autonomy_heartbeat)
        self._auto_hb.start()

    def _render_telemetry(self) -> None:
        for rid, st in self.state.items():
            if not st.telemetry:
                continue
            rev = st._tele_rev
            if self._tele_render_rev.get(rid) == rev:
                continue                            # no new frame → skip
            self._tele_render_rev[rid] = rev
            self._on_telemetry(rid, st.telemetry)

    def _start(self) -> None:
        for link in self.links.values():
            link.start()
        for client in self.cmd.values():
            if client not in self.links.values():
                client.start()
        # host-level reachability → amber "ON NETWORK, stack stopped" pills
        from transport.reachability import ReachabilityProber
        targets = {p.id: (p.host, 80 if p.is_esp32 else 22)
                   for p in self.app_cfg.robots}
        self._prober = ReachabilityProber(targets, parent=self)
        self._prober.reachableChanged.connect(self.command_bar.set_robot_net)
        self._prober.start()
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
        if (vx or wz) and self.mission.active:    # operator takes over
            self.mission.cancel('cancelled by manual drive')
            self.map.clear_path()
        self._client().drive(vx, wz)

    def _stop(self) -> None:
        self._client().drive(0.0, 0.0)

    def _estop(self, engage: bool) -> None:
        if engage:
            self.mission.cancel('cancelled by e-stop')
        self._client().estop(engage)
        self._log(f'E-STOP {"ENGAGED" if engage else "released"} → {self.active_id}')

    def _all_stop(self) -> None:
        self._fire_stop()
        self.mission.cancel('cancelled by ALL STOP')
        for rid, client in self.cmd.items():
            client.estop(True)
        self.ops.set_estop(True)
        self._log('ALL STOP — every robot e-stopped (release per robot)')

    def _mode_changed(self, mode: str) -> None:
        self.mission.cancel('cancelled by mode change')
        enable = (mode == 'auto')
        self._client().send(cmds.CMD_EXPLORE, {'enable': enable})
        # Track the armed robot so the heartbeat keeps re-affirming AUTONOMOUS.
        # If this console goes away, the heartbeat stops and the robot's local
        # nav times out and STOPS (it won't keep wandering unattended).
        self._auto_robot = self.active_id if enable else None
        if not enable:
            self._stop()
        self._log(f'{self.active_id} drive mode → {mode.upper()}')

    def _autonomy_heartbeat(self) -> None:
        """Re-affirm AUTONOMOUS ~2 Hz while armed. The robot's local nav stops
        if this stream stops (console closed/crashed/WiFi lost) — safety."""
        rid = self._auto_robot
        if rid and rid in self.cmd:
            self.cmd[rid].send(cmds.CMD_EXPLORE, {'enable': True})

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
        """NAVIGATE click: A* over the occupancy grid → waypoint mission.

        The console plans the safe route around MAPPED obstacles (through
        doors, away from walls) and drives it leg by leg; Beta's local fuser
        additionally dodges UNMAPPED obstacles with its ultrasonics. Beta has
        no lidar, so map-aware nav needs it ALIGNED to the map (SET POSE)."""
        if self._placing_fire:                 # FIRE TEST: this click drops the fire
            self._place_fire(x, y)
            return
        rid = self.active_id
        if rid == 'robot2' and not self._aligned.get(rid, False):
            msg = 'Align Beta with SET POSE for map-aware navigation'
            self.statusBar().showMessage(msg, 5000)
            self._log(msg + ' — meanwhile AUTONOMOUS runs reactive avoidance')
            return
        status = self._plan_and_run(x, y)
        if status == 'no_map':
            if rid == 'robot2':
                self.statusBar().showMessage(
                    'No map yet — Beta runs reactive avoidance only', 5000)
                self._log('no map — start Alpha mapping for Beta go-to-goal')
                return
            self._send_goal_world(x, y)            # Alpha: short direct goal
            self.map.set_goal(x, y)
            self._log(f'goal (direct, no map yet) → ({x:.2f}, {y:.2f})')
            return
        if status == 'no_path':
            self.statusBar().showMessage(
                'NO PATH — target unreachable (blocked or unexplored)', 4000)
            self._log(f'NO PATH to ({x:.2f}, {y:.2f}) — blocked or unexplored')
            return
        self._nav_goal = (rid, x, y)               # remember for replan-on-stuck
        self._nav_replans = 0

    def _plan_and_run(self, gx: float, gy: float) -> str:
        """A* from the active robot's current aligned pose → (gx,gy) and run
        the mission. Returns 'ok' | 'no_path' | 'no_map'. Reused by goal
        clicks and replan-on-stuck so a stuck robot re-routes from where it is."""
        pose = self._aligned_pose(self.active_id)
        if self._grid is None or pose is None:
            return 'no_map'
        res, ox, oy = self._grid_meta
        prof = self.app_cfg.profile(self.active_id)
        t0 = time.monotonic()
        path = plan_path(self._grid, res, ox, oy, (pose.x, pose.y), (gx, gy),
                         hard_radius_m=prof.plan_hard_radius_m,
                         soft_extra_m=prof.plan_soft_extra_m)
        dt_ms = (time.monotonic() - t0) * 1000
        if path is None:
            return 'no_path'
        self.map.set_goal(*path[-1])
        self.map.set_path((pose.x, pose.y), path)
        self._log(f'route planned: {len(path)} leg(s), {dt_ms:.0f} ms')
        self.mission.start(self.active_id, path, gains=prof.goto)
        return 'ok'

    def _on_mission_bias(self, vx: float, wz: float) -> None:
        """Stream the mission's heading bias to a local-fuser robot (Beta).
        Alpha drives from CMD_GOAL instead, so it ignores this."""
        rid = self.mission.robot_id
        if rid == 'robot2' and rid in self.cmd:
            self.cmd[rid].send(cmds.CMD_NAV_BIAS,
                               {'vx': round(vx, 3), 'wz': round(wz, 3)})

    def _send_goal_world(self, x: float, y: float) -> None:
        # shared frame → the executing robot's own odom frame
        rx, ry = world_point_to_robot(x, y, self._offsets[self.active_id])
        self._client().send(cmds.CMD_GOAL, {'x': round(rx, 3), 'y': round(ry, 3)})

    # ══════════════════════════════════════════════════════════════════════
    # FIRE TEST — place a fire on the map, send Beta to navigate to it
    # ══════════════════════════════════════════════════════════════════════
    def _arm_place_fire(self) -> None:
        """Arm fire placement: the next map click drops the fire point."""
        self._placing_fire = True
        self.map.reset_mode()                  # NAV mode → click reaches _goal_clicked
        self.fire_panel.set_placing(True)
        self.fire_panel.log_line('click the map where the fire is...')
        self.statusBar().showMessage('Click the map to place the FIRE', 6000)

    def _place_fire(self, x: float, y: float) -> None:
        self._placing_fire = False
        self._fire_xy = (x, y)
        self.fire_panel.set_placing(False)
        self.map.add_marker('FIRE', x, y, conf=None, robot='operator',
                            t_wall=time.strftime('%H:%M:%S'))
        self.fire_panel.set_fire(x, y)
        self.fire_panel.log_line(f'fire placed at ({x:+.2f}, {y:+.2f}) m')

    # ── shared sequence helpers ───────────────────────────────────────────
    def _seq_ready(self):
        """Common preflight for an autonomous sequence. Returns Beta's aligned
        pose, or None (with a panel reason) if the map/alignment isn't ready."""
        pose = self._aligned_pose('robot2')
        if self._grid is None:
            self.fire_panel.set_status('NO MAP - start Alpha mapping', 'bad')
            return None
        if pose is None or not self._aligned.get('robot2'):
            self.fire_panel.set_status('SET POSE Beta on the map first', 'bad')
            self.fire_panel.log_line('Beta must be aligned (SET POSE) for map nav')
            return None
        if self.active_id != 'robot2':
            self._switch_robot('robot2')
        return self._aligned_pose('robot2')

    def _seq_arm(self) -> None:
        self._auto_robot = 'robot2'                 # arm autonomy + heartbeat
        self.cmd['robot2'].send(cmds.CMD_EXPLORE, {'enable': True})

    def _seq_disarm(self) -> None:
        self._auto_robot = None
        self._nav_goal = None
        if 'robot2' in self.cmd:
            self.cmd['robot2'].send(cmds.CMD_EXPLORE, {'enable': False})
            self.cmd['robot2'].send(cmds.CMD_NAV_BIAS, {'vx': 0.0, 'wz': 0.0})

    def _seq_drive_to(self, x: float, y: float) -> bool:
        """Plan + run a single-goal leg; arms replan-on-stuck. False on no path."""
        if self._plan_and_run(x, y) != 'ok':
            return False
        self._nav_goal = ('robot2', x, y)
        self._nav_replans = 0
        return True

    def _seq_finish(self, label: str, kind: str = 'good') -> None:
        self._seq = None
        self._seq_phase_label = ''
        self._seq_disarm()
        self.map.clear_path()
        self.map.clear_reference_path()
        self.fire_panel.set_running(False)
        self.fire_panel.set_status(label, kind)
        self.fire_panel.log_line(label)

    def _seq_phase(self, label: str) -> None:
        """Set a steady running-phase status (re-shown after a dodge clears)."""
        self._seq_phase_label = label
        self.fire_panel.set_status(label, 'accent')

    # ── SCAN: cover the mapped area, then return to base ──────────────────
    def _scan_area(self) -> None:
        pose = self._seq_ready()
        if pose is None:
            return
        self._seq_home = (pose.x, pose.y)
        res, ox, oy = self._grid_meta
        prof = self.app_cfg.profile('robot2')
        half = (prof.footprint or {}).get('half_width_m', 0.10)
        path = coverage_path(self._grid, res, ox, oy,
                             lane_m=0.6,                # coarse sweeps (simple path)
                             clearance_m=half + 0.12,   # keep waypoints off walls
                             max_waypoints=14,          # cap complexity
                             start=(pose.x, pose.y))
        if not path:
            self.fire_panel.set_status('no free area to scan', 'warn')
            return
        self._seq_arm()
        self._seq = 'scan_cover'
        self.map.set_reference_path(path)           # persistent reference viz
        # Follow the coverage path LOOSELY: skip a waypoint it can't reach in
        # 12 s (don't get trapped in a dead end), and accept 'close enough'.
        self.mission.start('robot2', path, gains=prof.goto,
                           skip_stuck=True, wp_timeout=12.0, tol=0.45)
        self.fire_panel.set_running(True)
        self._seq_phase(f'SCANNING — {len(path)} waypoints')
        self.fire_panel.log_line(f'SCAN: covering the area ({len(path)} waypoints)')

    # ── FIRE: navigate to the fire → pump 5 s → return to start ───────────
    def _fire_go(self) -> None:
        if self._fire_xy is None:
            self.fire_panel.set_status('place a fire first', 'warn')
            return
        pose = self._seq_ready()
        if pose is None:
            return
        self._seq_home = (pose.x, pose.y)
        self._seq_arm()
        fx, fy = self._fire_xy
        if self._seq_drive_to(fx, fy):
            self._seq = 'fire_go'
            self.map.set_reference_path([(pose.x, pose.y), (fx, fy)])
            self.fire_panel.set_running(True)
            self._seq_phase('EN ROUTE to fire')
            self.fire_panel.log_line('FIRE: navigating to the fire (A* + ultrasonic dodge)')
        else:
            self._seq_disarm()
            self.fire_panel.set_status('NO PATH to the fire', 'bad')
            self.fire_panel.log_line('no safe route - blocked or unexplored area')

    def _fire_stop(self) -> None:
        self._pump_timer.stop()
        self.mission.cancel('stopped by operator', silent=True)
        self._seq = None
        self._seq_phase_label = ''
        self._seq_disarm()
        if 'robot2' in self.cmd:
            self.cmd['robot2'].send(cmds.CMD_PUMP, {'on': False})
        self.map.clear_path()
        self.map.clear_reference_path()
        self.fire_panel.set_running(False)
        self.fire_panel.set_status('STOPPED', 'muted')

    def _pump_done(self) -> None:
        if self._seq != 'fire_pump':
            return
        if 'robot2' in self.cmd:
            self.cmd['robot2'].send(cmds.CMD_PUMP, {'on': False})
        self.fire_panel.log_line('FIRE: pump OFF - returning to start')
        self._seq = 'fire_return'
        self._seq_arm()                             # re-arm for the return drive
        hx, hy = self._seq_home
        self.fire_panel.set_running(True)
        self._seq_phase('RETURNING to start')
        if not self._seq_drive_to(hx, hy):
            self._seq_finish('FIRE done (no path back)', 'warn')

    def _on_waypoint_active(self, idx: int, total: int, x: float, y: float) -> None:
        pose = self._aligned_pose(self.active_id)
        if pose is not None:
            self.map.set_path((pose.x, pose.y), self.mission.remaining())
        if self._seq:
            self.statusBar().showMessage(
                f'{self._seq}: waypoint {idx}/{total}', 3000)

    def _on_mission_finished(self, reason: str) -> None:
        self.map.clear_path()
        self._on_mission_bias(0.0, 0.0)            # stop streaming bias
        if reason == 'arrived':
            self.map.clear_goal()
        # A no-progress TIMEOUT triggers a bounded replan from the current pose.
        if (reason.startswith('timeout') and self._nav_goal
                and self._nav_replans < 3
                and self._nav_goal[0] == self.active_id):
            _, gx, gy = self._nav_goal
            self._nav_replans += 1
            self._log(f'nav {reason} — replanning from current pose '
                      f'({self._nav_replans}/3)')
            if self._plan_and_run(gx, gy) == 'ok':
                return
        self._nav_goal = None

        # Advance the autonomous sequence.
        if self._seq is None:
            return
        if reason != 'arrived':
            self._seq_finish(f'STOPPED ({reason})', 'warn')
            return
        if self._seq == 'scan_cover':
            self.fire_panel.log_line('SCAN: area covered - returning to base')
            self._seq = 'scan_return'
            self._seq_phase('RETURNING to base')
            if not self._seq_drive_to(*self._seq_home):
                self._seq_finish('SCAN done (no path back)', 'warn')
        elif self._seq == 'scan_return':
            self._seq_finish('SCAN COMPLETE — back at base', 'good')
        elif self._seq == 'fire_go':
            self._seq = 'fire_pump'
            self._seq_disarm()                      # HOLD at the fire (no wander)
            self.fire_panel.set_status('PUMP ON - 5 s', 'good')
            self.fire_panel.log_line('FIRE: arrived - pump ON for 5 s')
            if 'robot2' in self.cmd:
                self.cmd['robot2'].send(cmds.CMD_PUMP, {'on': True})
            self._pump_timer.start(5000)            # firmware also hard-caps 5 s
        elif self._seq == 'fire_return':
            self._seq_finish('FIRE DONE — back at start', 'good')

    def _pose_picked(self, x: float, y: float, th: float) -> None:
        odom = self.state[self.active_id].telemetry.get('odom') or \
            {'x': 0.0, 'y': 0.0, 'th': 0.0}
        raw = Pose(odom['x'], odom['y'], odom['th'])
        if math.isnan(th):          # plain click: reposition, keep heading
            th = apply_offset(raw, self._offsets[self.active_id]).th
        self._offsets[self.active_id] = offset_from_alignment(
            raw, Pose(x, y, th))
        self._aligned[self.active_id] = True
        self.map.reset_mode()
        self._log(f'{self.active_id} aligned to map at '
                  f'({x:.2f}, {y:.2f}, {th:.2f} rad)')

    def _reset_map_clicked(self) -> None:
        # SLAM runs on the robot that publishes the map (the mapper) — route
        # there regardless of which robot is active.
        target = self._map_source_id or self.active_id
        client = self.cmd.get(target)
        if client is None:
            self._log(f'RESET MAP: no command link to {target}')
            return
        if QMessageBox.question(
                self, 'Reset map',
                f'Restart SLAM on {target}?\n\nThe current map is discarded '
                'and the robot stack restarts (~10 s offline).',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        client.send(cmds.CMD_RESET_MAP, {})
        self._log(f'{target} SLAM reset requested — map will rebuild')
        self.mission.cancel('cancelled by map reset')
        self.map.clear_markers()
        self.map.clear_path()
        self.map.clear_goal()

    def _switch_robot(self, robot_id: str) -> None:
        if robot_id == self.active_id:
            self.command_bar.set_active(robot_id)
            return
        self.mission.cancel('cancelled by robot switch')
        self.map.clear_path()
        self.ops.set_estop(False)                 # latch belongs to old robot
        self.active_id = robot_id
        self.command_bar.set_active(robot_id)
        self.fleet.set_active(robot_id)
        self.map.set_active_robot(robot_id)
        self.map.clear_goal()
        self._video_robot = self._pick_video_robot()   # keep Beta's feed if active has none
        self.video.set_robot(self._video_robot)
        self._update_ops_target()
        up = self._link_state.get(robot_id)
        if up is not None:
            self.command_bar.set_active_link_chip(up)
        self._log(f'active robot → {robot_id}')

    def _update_ops_target(self) -> None:
        prof = self.app_cfg.profile(self.active_id)
        self.ops.set_target(prof.name, prof.id,
                            has_tools=(prof.id == 'robot2'),
                            has_gas=prof.is_esp32,
                            has_ultra=bool(prof.ultrasonic.get('enabled')))

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
            self._update_esp32_readouts(robot_id, esp)

        pose = self._aligned_pose(robot_id)
        if pose is not None:
            self.map.update_robot(robot_id, pose.x, pose.y, pose.th)
            self.mission.update_pose(robot_id, pose.x, pose.y, pose.th)
            card = self.fleet.cards.get(robot_id)
            if card:
                import math
                card.set_pose(pose.x, pose.y, math.degrees(pose.th),
                              self._aligned[robot_id])

        if not robot_id == self.active_id:
            return
        nav = payload.get('nav_status', '')
        # Deviation indicator during an autonomous sequence: Beta's fuser
        # reports BLOCKED while it dodges an unmapped obstacle off the
        # reference path. Surfacing it is the visible proof of reactive
        # autonomy (the map already shows it leaving + rejoining the dashed
        # reference line).
        if self._seq and robot_id == 'robot2':
            if nav.startswith('BLOCKED') or nav.startswith('STUCK'):
                self.fire_panel.set_status('DEVIATING - dodging obstacle', 'warn')
            elif self._seq_phase_label:
                self.fire_panel.set_status(self._seq_phase_label, 'accent')
        if nav.startswith('ARRIVED') and not self.mission.active:
            self.map.clear_goal()       # mission mode clears its own goal
        servo = payload.get('servo_deg')
        if servo is not None:
            self.ops.set_servo_feedback(int(servo))
        if 'us' in payload:                       # front ultrasonics (Beta)
            uc = self.app_cfg.profile(robot_id).ultrasonic
            self.ops.set_ultrasonic(payload.get('us'),
                                    stop_cm=uc.get('stop_cm', 25),
                                    slow_cm=uc.get('slow_cm', 60))

        now = time.monotonic()
        if now - self._last_sb >= 0.25:
            self._last_sb = now
            if isinstance(esp, dict):             # inspector: env readouts
                gas = esp.get('g', '—')
                alarm = bool(esp.get('a'))
                self.sb_nav.setText(f'{robot_id} · gas {gas}'
                                    + (' · ALARM' if alarm else ''))
                self.sb_nav.setStyleSheet(
                    f'color:{theme.BAD if alarm else theme.MUTED};')
                self.sb_enc.setText(f"dist {esp.get('d', '—')} cm")
                rssi = esp.get('rssi')
                self.sb_acc.setText(f'rssi {rssi} dBm' if rssi is not None else '')
            else:
                state = (nav or 'IDLE').split(':')[0]
                color = {'DRIVING': theme.ACCENT, 'ROTATING': theme.WARN,
                         'ARRIVED': theme.GOOD}.get(state, theme.MUTED)
                self.sb_nav.setText(f'{robot_id} · nav {nav or "IDLE"}')
                self.sb_nav.setStyleSheet(f'color:{color};')
                enc = payload.get('enc')
                self.sb_enc.setText(f'enc {enc}' if enc else 'enc —')
                acc = payload.get('accessory')
                self.sb_acc.setText(f'acc {acc}' if acc else '')

    def _update_esp32_readouts(self, robot_id: str, esp: dict) -> None:
        """Gas level lives on the FLEET CARD (always visible) and in the
        diagnostics vitals — the inspector's reading must never require
        switching robots to see."""
        gas = esp.get('g')
        alarm = bool(esp.get('a'))
        profile = self.app_cfg.profile(robot_id)
        warn_at = (profile.gas or {}).get('clear_threshold', 2000)
        card = self.fleet.cards.get(robot_id)
        if card and gas is not None:
            rssi = esp.get('rssi')
            text = f'gas {gas}' + (' ALARM' if alarm else '') + \
                   (f' · {rssi} dBm' if rssi is not None else '')
            card.set_vitals(text, warn=alarm or (gas >= warn_at))
        # live gas gauge in the ops panel when this inspector is active
        if robot_id == self.active_id and gas is not None:
            alarm_at = (profile.gas or {}).get('alarm_threshold', 3000)
            self.ops.set_gas(int(gas), alarm, warn_at, alarm_at)
        # mirror into the diagnostics vitals strip (health-channel shape)
        self.drawer.diagnostics.update_vitals(robot_id, {
            'sys': {'rssi_dbm': esp.get('rssi'), 'temp_c': None,
                    'throttled': None, 'load1': None,
                    'mem_free_mb': None, 'disk_free_mb': None},
            'uptime_s': esp.get('uptime'),
        })

    def _on_scan(self, robot_id: str, payload: dict) -> None:
        pose = self._aligned_pose(robot_id)
        if pose is not None:
            self.map.update_scan(payload, (pose.x, pose.y, pose.th))

    def _on_map(self, robot_id: str, payload: dict) -> None:
        self._map_source_id = robot_id            # whoever maps owns SLAM
        self.map.update_map(payload)
        try:                                      # keep a copy for the planner
            raw = payload['data']
            if payload.get('enc') == 'zlib':
                raw = zlib.decompress(raw)
            self._grid = np.frombuffer(raw, dtype=np.int8).reshape(
                (payload['h'], payload['w']))
            self._grid_meta = (payload['res'], payload['ox'], payload['oy'])
        except (KeyError, ValueError, zlib.error):
            pass

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
    def _pick_video_robot(self) -> str:
        """Which robot's feed to show: the active one if it has a camera, else
        a camera robot (prefer Beta) — so viewing Alpha still shows Beta."""
        if self.active_id in self._cam_robots:
            return self.active_id
        if 'robot2' in self._cam_robots:
            return 'robot2'
        return next(iter(self._cam_robots), self.active_id)

    def _refresh_video_robot(self) -> None:
        target = self._pick_video_robot()
        if target != self._video_robot:
            self._video_robot = target
            self.video.set_robot(target)

    def _on_video(self, robot_id: str, meta, jpeg: bytes) -> None:
        self._cam_robots.add(robot_id)
        self._refresh_video_robot()
        if robot_id != self._video_robot:
            return
        st = self.state[robot_id]
        st.on_video_meta(meta)
        cap = meta.payload.get('cap_t_mono', 0.0)
        fid = int(meta.payload.get('frame_id', 0))
        self._frame_caps[fid] = cap
        if len(self._frame_caps) > 64:
            for k in sorted(self._frame_caps)[:-32]:
                self._frame_caps.pop(k, None)
        # Show the RAW frame immediately (network-latency only). When AI is
        # up we ALSO submit it for detection; the boxes arrive a beat later
        # as a vector overlay (_on_annotated) and never gate the video.
        self.video.show_jpeg(jpeg, st.video_frame_age_s(cap))
        if self.yolo is not None and self.yolo.available:
            self.yolo.submit_frame(fid, jpeg)

    def _on_legacy_video(self, robot_id: str, jpeg: bytes) -> None:
        self._cam_robots.add(robot_id)
        self._refresh_video_robot()
        if robot_id != self._video_robot:
            return
        if self.state[robot_id].streams['video'].age_s() < 2.0:
            return
        if self.yolo is not None and self.yolo.available:
            self.yolo.submit_frame(0, jpeg)
        else:
            self.video.show_jpeg(jpeg, None)

    def _on_annotated(self, frame_id: int, jpeg: bytes, detections) -> None:
        # jpeg is intentionally empty now — the raw frame is already on screen
        # (see _on_video). We only push the detection boxes as an overlay, so
        # inference latency never delays the video itself.
        self.video.set_detections(detections)

        pairs = [(d.get('label', ''), float(d.get('conf', 0.0)))
                 for d in detections or ()]
        # FIRE still drives the audible/banner alarm on its own (debounced)
        # threshold — independent of the map-marker floor below.
        self.alerts.process_fire_detections(self.active_id, pairs)

        # Project wanted detections (person/dog/cat/fire) onto the shared
        # map: best-of-frame per kind, each gated by its per-class confidence
        # floor and rate-limited to 2x/s so one sighting = one marker (the
        # map merges + smooths repeats within MARKER_MERGE_M).
        pose = self._aligned_pose(self.active_id)
        if pose is None:
            return
        now = time.monotonic()
        best: dict[str, tuple] = {}            # kind -> (conf, cx, h)
        for d in detections or ():
            label = str(d.get('label', '')).strip().lower()
            kind = DETECT_KIND.get(label)
            if kind is None:
                continue
            conf = float(d.get('conf', 0.0))
            if conf < self._detect_conf_for(label):
                continue
            if kind not in best or conf > best[kind][0]:
                best[kind] = (conf, float(d.get('cx', 0.5)),
                              float(d.get('h', 0.3)))
        for kind, (conf, cx, h) in best.items():
            if now - self._last_marker.get(kind, 0.0) < 0.5:
                continue
            self._last_marker[kind] = now
            x, y = detection_to_world(pose, cx, h, self._hfov,
                                      DIST_K_BY_KIND.get(kind, DIST_K))
            self.map.add_marker(kind, x, y, conf=round(conf * 100),
                                robot=self.active_id,
                                t_wall=time.strftime('%H:%M:%S'))
            self.video.flash_detection(
                f'{kind.lower()} {conf * 100:.0f}% -> map ({x:+.1f}, {y:+.1f})')
            phrase = DETECT_SPEECH.get(kind)
            if phrase:
                self.speaker.announce(kind, phrase)

    def _detect_conf_for(self, label: str) -> float:
        """Per-class map-marker confidence floor from prefs.detect_conf."""
        key = DETECT_CONF_KEY.get(label, label)
        return float(self.app_cfg.prefs.detect_conf.get(key, 0.5))

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
    def eventFilter(self, obj, e) -> bool:
        """App-wide: drive keys reach the teleop stream even when a dock,
        the map or a slider holds focus. Two carve-outs:

        * Escape (E-STOP) is ALWAYS intercepted — operator panic key.
        * Other keys pass through while a widget that legitimately consumes
          keystrokes (combo box, line edit, spin box, editable text) has
          focus, so typing never drives the robot.
        """
        # If the window loses focus while a drive key is held, its KeyRelease
        # is delivered elsewhere and the key stays "stuck" in self._keys — the
        # robot keeps driving and the keyboard then feels dead/erratic until a
        # full reset. Release everything on deactivation (also a safety stop).
        if e.type() == e.Type.WindowDeactivate and self._keys:
            self._keys.clear()
            self._key_timer.stop()
            self.ops.keyboard_vector(0.0, 0.0)
        if e.type() == e.Type.KeyPress and e.key() == Qt.Key_Escape:
            self.keyPressEvent(e)
            return True
        # Only widgets that take TEXT keep their keystrokes. A plain combo
        # box does NOT qualify — exempting it routed WASD into the model
        # selector for the entire session (field regression 2026-06-11:
        # the combo grabbed initial focus and teleop went dead).
        fw = QApplication.focusWidget()
        if isinstance(fw, (QLineEdit, QAbstractSpinBox)) or \
                (isinstance(fw, QComboBox) and fw.isEditable()) or \
                (isinstance(fw, (QPlainTextEdit, QTextEdit))
                 and not fw.isReadOnly()):
            return super().eventFilter(obj, e)
        if e.type() == e.Type.KeyPress:
            if e.key() in KEY_VECTORS or e.key() in (Qt.Key_F9, Qt.Key_Space):
                self.keyPressEvent(e)
                return True
        elif e.type() == e.Type.KeyRelease:
            if e.key() in KEY_VECTORS:
                self.keyReleaseEvent(e)
                return True
        return super().eventFilter(obj, e)

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
    def _on_mute_toggled(self, checked: bool) -> None:
        self.speaker.set_muted(checked)
        self._settings().setValue('mute_voice', checked)
        self._log('voice announcements ' + ('MUTED' if checked else 'on'))

    # Bump when the default dock layout changes so stale saved arrangements
    # (e.g. a previous session that squeezed the OPS dock to a sliver) are
    # discarded instead of restored over the new default.
    LAYOUT_VERSION = 3      # bumped: AUTONOMY moved from a center tab to a dock

    def _settings(self) -> QSettings:
        return QSettings('GP', 'OperationsCenter')

    def _restore_layout(self) -> None:
        self._default_state = self.saveState()
        s = self._settings()
        if s.value('layout_version', 0, type=int) != self.LAYOUT_VERSION:
            return                      # schema changed → keep the fresh default
        geo = s.value('geometry')
        state = s.value('windowState')
        if geo is not None:
            self.restoreGeometry(geo)
        if state is not None:
            self.restoreState(state)

    def _reset_layout(self) -> None:
        self.restoreState(self._default_state)
        for dock in (self._dock_fleet, self._dock_video, self._dock_ops):
            dock.show()
        self._apply_dock_sizes()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # resizeDocks in __init__ runs BEFORE showMaximized, so the maximize
        # redistributes the width and collapses the right OPS dock to a sliver.
        # Enforce the column widths once, AFTER the window is actually shown.
        if not getattr(self, '_docks_sized', False):
            self._docks_sized = True
            QTimer.singleShot(0, self._apply_dock_sizes)

    def _apply_dock_sizes(self) -> None:
        # Clamp the DOCK widths directly (a min on the inner panel doesn't
        # propagate to the dock area reliably), then resize. The OPS dock kept
        # collapsing to a sliver otherwise.
        self._dock_fleet.setMinimumWidth(286)
        self._dock_ops.setMinimumWidth(320)
        self.resizeDocks([self._dock_fleet], [300], Qt.Horizontal)
        self.resizeDocks([self._dock_ops], [340], Qt.Horizontal)
        QTimer.singleShot(0, self._relax_dock_limits)

    def _relax_dock_limits(self) -> None:
        # Let the operator resize them afterwards, but never below a usable
        # floor (keeps the joystick + proximity readout legible).
        self._dock_fleet.setMinimumWidth(250)
        self._dock_ops.setMinimumWidth(312)

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
        s.setValue('layout_version', self.LAYOUT_VERSION)
        # SAFETY: disarm autonomy + stop every robot BEFORE tearing down the
        # links, so closing the console never leaves a robot wandering. The
        # robot-side heartbeat timeout is the backstop if this doesn't land.
        self._auto_robot = None
        for rid, client in self.cmd.items():
            try:
                client.send(cmds.CMD_EXPLORE, {'enable': False})
                client.drive(0.0, 0.0)
            except Exception:
                pass
        time.sleep(0.25)                    # let the stop/disarm flush
        for client in set(self.cmd.values()) | set(self.links.values()):
            try:
                client.stop()
            except Exception:
                pass
        if self.yolo is not None:
            self.yolo.stop()
        self.speaker.stop()
        event.accept()
