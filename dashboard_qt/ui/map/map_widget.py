"""Shared-map widget — the central instrument of the Operations Center.

Layers (independent, individually toggleable):
    occupancy grid · 1 m grid lines · per-robot trails · laser scan ·
    all robots (active highlighted, name tags) · goal · event markers

Interaction modes (toolbar on the canvas):
    NAVIGATE  click → navigation goal for the active robot
    SET POSE  press = position, drag = heading, release = commit — aligns a
              robot's odom frame onto the shared map (RViz "2D Pose Estimate")
    MARKER    click → drop a manual pin

Plus: wheel zoom (clamped, anchored under cursor), right-drag pan, FIT,
FOLLOW (camera tracks the active robot), live cursor coordinates and an
adaptive scale bar.
"""

from __future__ import annotations

import math
import time
import zlib
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, qRgb)
from PySide6.QtWidgets import (QFrame, QGraphicsPathItem, QGraphicsPixmapItem,
                               QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView, QHBoxLayout, QLabel, QMenu,
                               QToolButton, QVBoxLayout, QWidget)

from ui import theme

MODE_NAV, MODE_POSE, MODE_MARK = 'nav', 'pose', 'mark'
MIN_PPM, MAX_PPM = 12, 900
TRAIL_MAX_POINTS = 400
TRAIL_MIN_STEP_M = 0.04
SCAN_REBUILD_MIN_S = 0.1

# One incident = one marker: merge anything of the same kind inside this
# radius and SMOOTH its position instead of spawning a twin. Monocular
# range estimates jitter by tens of centimeters frame to frame — without
# this, a single fire floods the map with a marker cloud.
MARKER_MERGE_M = {'FIRE': 2.0, 'GAS': 2.0, 'PIN': 0.3}
MARKER_POS_BLEND = 0.25            # new estimate weight when merging

MARKER_GLYPH = {'FIRE': '▲', 'GAS': '◆', 'PIN': '●'}
MARKER_COLOR = {'FIRE': theme.MARKER_FIRE, 'GAS': theme.MARKER_GAS,
                'PIN': theme.MARKER_PIN}


@dataclass
class _RobotLayer:
    body: QGraphicsPathItem
    label: QGraphicsSimpleTextItem
    trail: QGraphicsPathItem
    points: list = field(default_factory=list)
    pose: tuple = (0.0, 0.0, 0.0)


@dataclass
class Marker:
    kind: str
    x: float
    y: float
    conf: object
    t_wall: str
    robot: str
    items: list = field(default_factory=list)


class _Canvas(QGraphicsView):
    cursorMoved = Signal(float, float)
    zoomChanged = Signal(float)                # px per meter
    clicked = Signal(float, float)             # NAV / MARK click
    posePicked = Signal(float, float, float)   # SET POSE commit
    userNavigated = Signal()                   # manual zoom/pan → stop auto-fit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(theme.MAP_BG))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        self.setMouseTracking(True)
        # No scrollbars, and the scene rect is LOCKED to the map bounds in
        # update_map(): otherwise items outside the arena (laser rays
        # escaping through doors reach 6 m out) silently grow the auto
        # scene rect and DRIFT the whole view off-center.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.NoFocus)    # arrow keys must reach MainWindow
        self.scale(120, -120)                  # world: x right, y UP

        self.mode = MODE_NAV
        self._pan_last = None
        self._pose_press: QPointF | None = None
        self._pose_preview = QGraphicsPathItem()
        self._pose_preview.setPen(QPen(QColor(theme.ACCENT), 0.03))
        self._pose_preview.setZValue(40)
        self.scene().addItem(self._pose_preview)

    def ppm(self) -> float:
        return abs(self.transform().m11())

    # ── interactions ──────────────────────────────────────────────────────
    def wheelEvent(self, e) -> None:
        factor = 1.22 if e.angleDelta().y() > 0 else 0.82
        if MIN_PPM <= self.ppm() * factor <= MAX_PPM:
            self.scale(factor, factor)
            self.zoomChanged.emit(self.ppm())
            self.userNavigated.emit()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.RightButton:
            self._pan_last = e.position()
            self.setCursor(Qt.ClosedHandCursor)
            self.userNavigated.emit()
            return
        if e.button() == Qt.LeftButton:
            p = self.mapToScene(e.position().toPoint())
            if self.mode == MODE_POSE:
                self._pose_press = p
                self._draw_pose_preview(p, p)
                return
            self.clicked.emit(p.x(), p.y())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._pan_last is not None:
            d = e.position() - self._pan_last
            self._pan_last = e.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(d.y()))
            return
        p = self.mapToScene(e.position().toPoint())
        self.cursorMoved.emit(p.x(), p.y())
        if self._pose_press is not None:
            self._draw_pose_preview(self._pose_press, p)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.RightButton:
            self._pan_last = None
            self.setCursor(Qt.ArrowCursor)
            return
        if e.button() == Qt.LeftButton and self._pose_press is not None:
            start = self._pose_press
            end = self.mapToScene(e.position().toPoint())
            self._pose_press = None
            self._pose_preview.setPath(QPainterPath())
            dx, dy = end.x() - start.x(), end.y() - start.y()
            th = math.atan2(dy, dx) if math.hypot(dx, dy) > 0.05 else 0.0
            self.posePicked.emit(start.x(), start.y(), th)
            return
        super().mouseReleaseEvent(e)

    def _draw_pose_preview(self, a: QPointF, b: QPointF) -> None:
        path = QPainterPath()
        path.addEllipse(a, 0.14, 0.14)
        dx, dy = b.x() - a.x(), b.y() - a.y()
        if math.hypot(dx, dy) > 0.05:
            ang = math.atan2(dy, dx)
            tip = QPointF(a.x() + 0.45 * math.cos(ang), a.y() + 0.45 * math.sin(ang))
            path.moveTo(a)
            path.lineTo(tip)
            for side in (-1, 1):
                wing = ang + side * 2.6
                path.lineTo(QPointF(tip.x() + 0.12 * math.cos(wing),
                                    tip.y() + 0.12 * math.sin(wing)))
                path.moveTo(tip)
        self._pose_preview.setPath(path)


class _ScaleBar(QWidget):
    """Adaptive metric scale bar painted bottom-left of the canvas."""

    NICE = (0.25, 0.5, 1, 2, 5, 10)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ppm = 120.0
        self.setFixedHeight(22)
        self.setFixedWidth(190)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_ppm(self, ppm: float) -> None:
        self._ppm = max(1e-3, ppm)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        length_m = next((L for L in self.NICE if 55 <= L * self._ppm <= 165),
                        self.NICE[-1])
        px = min(self.width() - 50, length_m * self._ppm)
        y = self.height() - 7
        pen = QPen(QColor(theme.TEXT), 2)
        p.setPen(pen)
        p.drawLine(2, y, 2 + px, y)
        p.drawLine(2, y - 5, 2, y + 1)
        p.drawLine(2 + px, y - 5, 2 + px, y + 1)
        p.setFont(QFont('Consolas', 8))
        label = f'{length_m:g} m'
        p.setPen(QColor(theme.TEXT))
        p.drawText(int(px) + 8, y + 3, label)
        p.end()


class MapWidget(QWidget):
    goalRequested = Signal(float, float)
    posePicked = Signal(float, float, float)   # for the ACTIVE robot
    markerPlaced = Signal(float, float)
    markersChanged = Signal(list)              # list[Marker]
    resetMapRequested = Signal()               # operator asked to clear the map

    def __init__(self, parent=None):
        super().__init__(parent)
        self.canvas = _Canvas(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)

        sc = self.canvas.scene()
        self._grid_item: QGraphicsPixmapItem | None = None
        self._gridlines = QGraphicsPathItem()
        self._gridlines.setPen(QPen(QColor(*theme.MAP_GRIDLINE), 0))
        self._gridlines.setZValue(1.5)
        sc.addItem(self._gridlines)

        self._scan = QGraphicsPathItem()
        self._scan.setPen(QPen(QColor(theme.SCAN_COLOR), 0))
        self._scan.setBrush(QBrush(QColor(theme.SCAN_COLOR)))
        self._scan.setZValue(3)
        sc.addItem(self._scan)
        self._last_scan_build = 0.0

        self._goal_line = QGraphicsPathItem()
        pen = QPen(QColor(theme.GOAL_LINE), 0.015)
        pen.setStyle(Qt.DashLine)
        self._goal_line.setPen(pen)
        self._goal_line.setZValue(4)
        sc.addItem(self._goal_line)

        # planned route (A* output): line + waypoint dots
        self._path_item = QGraphicsPathItem()
        ppen = QPen(QColor(theme.ACCENT), 0.035)
        ppen.setCapStyle(Qt.RoundCap)
        self._path_item.setPen(ppen)
        self._path_item.setZValue(4.5)
        sc.addItem(self._path_item)
        self._path_dots = QGraphicsPathItem()
        self._path_dots.setPen(QPen(QColor(theme.ACCENT), 0))
        self._path_dots.setBrush(QBrush(QColor(theme.ACCENT)))
        self._path_dots.setZValue(4.6)
        sc.addItem(self._path_dots)
        self._goal_mark = QGraphicsPathItem()
        self._goal_mark.setPen(QPen(QColor(theme.GOAL_COLOR), 0.025))
        self._goal_mark.setZValue(5)
        sc.addItem(self._goal_mark)
        self._goal: tuple[float, float] | None = None

        self._robots: dict[str, _RobotLayer] = {}
        self._active_id = ''
        self._markers: list[Marker] = []
        self._have_grid = False
        self._follow = False
        # auto-fit keeps the whole map filling the canvas (first map, dock
        # resizes, map growth) until the operator zooms/pans manually
        self._user_nav = False

        self._build_overlay()
        self.canvas.cursorMoved.connect(self._on_cursor)
        self.canvas.zoomChanged.connect(self._scalebar.set_ppm)
        self.canvas.clicked.connect(self._on_click)
        self.canvas.posePicked.connect(self.posePicked)
        self.canvas.userNavigated.connect(
            lambda: setattr(self, '_user_nav', True))

    # ════════ overlay (toolbar / chips on the canvas) ════════
    def _build_overlay(self) -> None:
        self._toolbar = QFrame(self.canvas)
        self._toolbar.setObjectName('mapToolbar')
        bar = QHBoxLayout(self._toolbar)
        bar.setContentsMargins(7, 5, 7, 5)
        bar.setSpacing(5)

        def tool(text, tip, checkable=True):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFocusPolicy(Qt.NoFocus)
            bar.addWidget(b)
            return b

        self.btn_nav = tool('⊕ NAVIGATE', 'Click the map to send the active robot there')
        self.btn_pose = tool('⌖ SET POSE', 'Place the active robot on the map: '
                                           'click = position, drag = heading')
        self.btn_mark = tool('◈ MARKER', 'Click to drop a manual marker')
        self.btn_nav.setChecked(True)
        for b, mode in ((self.btn_nav, MODE_NAV), (self.btn_pose, MODE_POSE),
                        (self.btn_mark, MODE_MARK)):
            b.clicked.connect(lambda _=False, b=b, m=mode: self._set_mode(b, m))

        sep = QLabel('│')
        sep.setStyleSheet(f'color:{theme.BORDER};')
        bar.addWidget(sep)

        fit = tool('FIT', 'Fit the whole map in view (re-enables auto-fit)',
                   checkable=False)
        fit.clicked.connect(lambda: self.fit_map(from_button=True))
        self.btn_follow = tool('FOLLOW', 'Keep the active robot centered')
        self.btn_follow.toggled.connect(lambda on: setattr(self, '_follow', on))

        sep2 = QLabel('│')
        sep2.setStyleSheet(f'color:{theme.BORDER};')
        bar.addWidget(sep2)

        reset = tool('⟳ RESET MAP', 'Restart SLAM to clear the map completely',
                     checkable=False)
        reset.setStyleSheet(f'color:{theme.ACCENT};')
        reset.clicked.connect(self.resetMapRequested.emit)

        layers_btn = QToolButton()
        layers_btn.setText('LAYERS ▾')
        layers_btn.setFocusPolicy(Qt.NoFocus)
        layers_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(layers_btn)
        self._layer_actions = {}
        for key, label in (('scan', 'Laser scan'), ('trails', 'Trails'),
                           ('grid', 'Grid lines'), ('markers', 'Markers')):
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(lambda on, k=key: self._toggle_layer(k, on))
            self._layer_actions[key] = act
        clear = menu.addAction('Clear markers')
        clear.triggered.connect(self.clear_markers)
        layers_btn.setMenu(menu)
        bar.addWidget(layers_btn)

        self._coords = QLabel('x —  y —')
        self._coords.setObjectName('mapChip')
        self._coords.setParent(self.canvas)
        self._scalebar = _ScaleBar(self.canvas)
        self._scalebar.set_ppm(self.canvas.ppm())
        self._mode_hint = QLabel('')
        self._mode_hint.setObjectName('mapChip')
        self._mode_hint.setParent(self.canvas)
        self._mode_hint.hide()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self._have_grid and not self._user_nav:
            self.fit_map()
        self._toolbar.move(10, 10)
        self._toolbar.adjustSize()
        self._scalebar.move(12, self.canvas.height() - 30)
        self._coords.adjustSize()
        self._coords.move(self.canvas.width() - self._coords.width() - 12,
                          self.canvas.height() - 32)
        self._mode_hint.move(10, 10 + self._toolbar.height() + 6)

    def _set_mode(self, btn, mode: str) -> None:
        for b in (self.btn_nav, self.btn_pose, self.btn_mark):
            b.setChecked(b is btn)
        self.canvas.mode = mode
        hints = {MODE_NAV: '',
                 MODE_POSE: 'SET POSE: click = position, drag = heading, release = commit',
                 MODE_MARK: 'MARKER: click to drop a pin'}
        text = hints[mode]
        self._mode_hint.setText(text)
        self._mode_hint.setVisible(bool(text))
        self._mode_hint.adjustSize()

    def reset_mode(self) -> None:
        self._set_mode(self.btn_nav, MODE_NAV)

    def _toggle_layer(self, key: str, on: bool) -> None:
        if key == 'scan':
            self._scan.setVisible(on)
        elif key == 'grid':
            self._gridlines.setVisible(on)
        elif key == 'trails':
            for r in self._robots.values():
                r.trail.setVisible(on)
        elif key == 'markers':
            for m in self._markers:
                for it in m.items:
                    it.setVisible(on)

    def _on_cursor(self, x: float, y: float) -> None:
        self._coords.setText(f'x {x:+.2f}  y {y:+.2f} m')
        self._coords.adjustSize()
        self._coords.move(self.canvas.width() - self._coords.width() - 12,
                          self.canvas.height() - 32)

    def _on_click(self, x: float, y: float) -> None:
        if self.canvas.mode == MODE_NAV:
            if self._have_grid:
                self.goalRequested.emit(x, y)
        elif self.canvas.mode == MODE_MARK:
            self.markerPlaced.emit(x, y)

    # ════════ occupancy grid ════════
    def update_map(self, payload: dict) -> None:
        try:
            w, h, res = payload['w'], payload['h'], payload['res']
            raw = payload['data']
            if payload.get('enc') == 'zlib':
                raw = zlib.decompress(raw)
            grid = np.frombuffer(raw, dtype=np.int8).reshape((h, w))
        except (KeyError, ValueError, zlib.error):
            return

        img = np.zeros((h, w), dtype=np.uint8)
        img[grid == 0] = 1
        img[grid > 50] = 2
        img = np.ascontiguousarray(np.flipud(img))
        qimg = QImage(img.data, w, h, w, QImage.Format_Indexed8)
        qimg.setColorTable([qRgb(*theme.MAP_UNKNOWN), qRgb(*theme.MAP_FREE),
                            qRgb(*theme.MAP_OCCUPIED)])
        pixmap = QPixmap.fromImage(qimg.copy())

        ox, oy = payload['ox'], payload['oy']
        if self._grid_item is None:
            self._grid_item = self.canvas.scene().addPixmap(pixmap)
            self._grid_item.setZValue(1)
        else:
            self._grid_item.setPixmap(pixmap)
        from PySide6.QtGui import QTransform
        t = QTransform()
        t.translate(ox, oy + h * res)
        t.scale(res, -res)
        self._grid_item.setTransform(t)
        self._have_grid = True

        self._rebuild_gridlines(ox, oy, w * res, h * res)
        # lock the scene to the map (+ pan margin) — see _Canvas.__init__
        rect = self._grid_item.mapRectToScene(self._grid_item.boundingRect())
        self.canvas.scene().setSceneRect(rect.adjusted(-3, -3, 3, 3))
        if not self._user_nav:
            self.fit_map()

    def _rebuild_gridlines(self, ox: float, oy: float, w_m: float, h_m: float) -> None:
        path = QPainterPath()
        x = math.ceil(ox)
        while x <= ox + w_m:
            path.moveTo(x, oy); path.lineTo(x, oy + h_m)
            x += 1.0
        y = math.ceil(oy)
        while y <= oy + h_m:
            path.moveTo(ox, y); path.lineTo(ox + w_m, y)
            y += 1.0
        self._gridlines.setPath(path)

    # ════════ robots ════════
    def _layer(self, robot_id: str) -> _RobotLayer:
        if robot_id not in self._robots:
            sc = self.canvas.scene()
            body = QGraphicsPathItem(); body.setZValue(6)
            trail = QGraphicsPathItem(); trail.setZValue(2)
            label = QGraphicsSimpleTextItem(robot_id)
            label.setFlag(label.GraphicsItemFlag.ItemIgnoresTransformations)
            label.setZValue(7)
            label.setFont(QFont('Segoe UI', 8, QFont.Bold))
            for it in (body, trail, label):
                sc.addItem(it)
            self._robots[robot_id] = _RobotLayer(body=body, label=label, trail=trail)
        return self._robots[robot_id]

    def set_active_robot(self, robot_id: str) -> None:
        self._active_id = robot_id
        for rid, layer in self._robots.items():
            self._style_robot(rid, layer)

    def _style_robot(self, rid: str, layer: _RobotLayer) -> None:
        active = (rid == self._active_id)
        color = QColor(theme.ROBOT_ACTIVE if active else theme.ROBOT_OTHER)
        fill = QColor(color); fill.setAlpha(210 if active else 150)
        layer.body.setPen(QPen(color.lighter(125), 0.02))
        layer.body.setBrush(QBrush(fill))
        layer.label.setBrush(QBrush(color.lighter(135)))
        trail_rgba = theme.TRAIL_ACTIVE if active else theme.TRAIL_OTHER
        layer.trail.setPen(QPen(QColor(*trail_rgba), 0.03))

    def update_robot(self, robot_id: str, x: float, y: float, th: float) -> None:
        layer = self._layer(robot_id)
        if layer.pose == (0.0, 0.0, 0.0) and not layer.points:
            self._style_robot(robot_id, layer)
        layer.pose = (x, y, th)

        r = 0.115
        path = QPainterPath()
        path.addEllipse(QPointF(x, y), r, r)
        tip = QPointF(x + (r + 0.13) * math.cos(th), y + (r + 0.13) * math.sin(th))
        path.moveTo(x, y); path.lineTo(tip)
        for side in (-1, 1):
            wing = th + side * 2.7
            path.lineTo(QPointF(tip.x() + 0.07 * math.cos(wing),
                                tip.y() + 0.07 * math.sin(wing)))
            path.moveTo(tip)
        layer.body.setPath(path)
        layer.label.setPos(x + 0.16, y + 0.16)

        if (not layer.points or
                math.hypot(x - layer.points[-1][0], y - layer.points[-1][1])
                >= TRAIL_MIN_STEP_M):
            layer.points.append((x, y))
            if len(layer.points) > TRAIL_MAX_POINTS:
                layer.points = layer.points[-TRAIL_MAX_POINTS:]
            tp = QPainterPath()
            tp.moveTo(*layer.points[0])
            for px, py in layer.points[1:]:
                tp.lineTo(px, py)
            layer.trail.setPath(tp)

        if self._goal is not None and robot_id == self._active_id:
            self._draw_goal()
        if self._follow and robot_id == self._active_id:
            self.canvas.centerOn(x, y)

    def robot_pose(self, robot_id: str):
        layer = self._robots.get(robot_id)
        return layer.pose if layer else None

    # ════════ scan ════════
    def update_scan(self, payload: dict, pose: tuple[float, float, float]) -> None:
        now = time.monotonic()
        if now - self._last_scan_build < SCAN_REBUILD_MIN_S:
            return
        self._last_scan_build = now
        try:
            ranges = np.frombuffer(payload['ranges'], dtype=np.float32)
            a0, da = payload['a0'], payload['da']
            rmax = payload.get('rmax', 12.0)
        except (KeyError, ValueError):
            return
        x, y, th = pose
        n = len(ranges)
        if n == 0:
            return
        angles = a0 + np.arange(n, dtype=np.float32) * da + th
        valid = np.isfinite(ranges) & (ranges > 0.05) & (ranges < rmax)
        px = x + ranges[valid] * np.cos(angles[valid])
        py = y + ranges[valid] * np.sin(angles[valid])
        path = QPainterPath()
        step = max(1, len(px) // 360)
        for i in range(0, len(px), step):
            path.addEllipse(QPointF(float(px[i]), float(py[i])), 0.02, 0.02)
        self._scan.setPath(path)

    # ════════ goal ════════
    def set_goal(self, x: float, y: float) -> None:
        self._goal = (x, y)
        self._draw_goal()

    def clear_goal(self) -> None:
        self._goal = None
        self._goal_mark.setPath(QPainterPath())
        self._goal_line.setPath(QPainterPath())

    def set_path(self, start: tuple[float, float],
                 waypoints: list[tuple[float, float]]) -> None:
        """Planned route from the robot through every waypoint."""
        if not waypoints:
            self.clear_path()
            return
        line = QPainterPath()
        line.moveTo(*start)
        dots = QPainterPath()
        for (x, y) in waypoints:
            line.lineTo(x, y)
            dots.addEllipse(QPointF(x, y), 0.05, 0.05)
        self._path_item.setPath(line)
        self._path_dots.setPath(dots)

    def clear_path(self) -> None:
        self._path_item.setPath(QPainterPath())
        self._path_dots.setPath(QPainterPath())

    def _draw_goal(self) -> None:
        if self._goal is None:
            return
        gx, gy = self._goal
        s = 0.15
        path = QPainterPath()
        path.moveTo(gx - s, gy); path.lineTo(gx + s, gy)
        path.moveTo(gx, gy - s); path.lineTo(gx, gy + s)
        path.addEllipse(QPointF(gx, gy), s * 0.6, s * 0.6)
        self._goal_mark.setPath(path)
        pose = self._robots.get(self._active_id)
        if pose is not None:
            line = QPainterPath()
            line.moveTo(pose.pose[0], pose.pose[1])
            line.lineTo(gx, gy)
            self._goal_line.setPath(line)

    # ════════ markers ════════
    def add_marker(self, kind: str, x: float, y: float, conf=None,
                   robot: str = '', t_wall: str = '') -> None:
        kind = kind.upper()
        merge_r = MARKER_MERGE_M.get(kind, 0.6)
        for m in self._markers:
            if m.kind == kind and math.hypot(m.x - x, m.y - y) < merge_r:
                # same incident: smooth position, keep highest confidence
                m.x += MARKER_POS_BLEND * (x - m.x)
                m.y += MARKER_POS_BLEND * (y - m.y)
                if isinstance(conf, int):
                    m.conf = max(m.conf, conf) if isinstance(m.conf, int) else conf
                m.t_wall = t_wall or m.t_wall
                m.robot = robot or m.robot
                self._draw_marker_items(m)
                self.markersChanged.emit(list(self._markers))
                return
        m = Marker(kind=kind, x=x, y=y, conf=conf, t_wall=t_wall, robot=robot)
        self._markers.append(m)
        self._draw_marker_items(m)
        self.markersChanged.emit(list(self._markers))

    def _draw_marker_items(self, m: Marker) -> None:
        sc = self.canvas.scene()
        for it in m.items:
            sc.removeItem(it)
        m.items.clear()
        color = QColor(MARKER_COLOR.get(m.kind, theme.MARKER_PIN))
        ring = QGraphicsPathItem()
        rp = QPainterPath()
        rp.addEllipse(QPointF(m.x, m.y), 0.22, 0.22)
        rp.addEllipse(QPointF(m.x, m.y), 0.05, 0.05)
        ring.setPath(rp)
        ring.setPen(QPen(color, 0.03))
        ring.setZValue(8)
        glyph = QGraphicsSimpleTextItem(MARKER_GLYPH.get(m.kind, '●'))
        glyph.setFlag(glyph.GraphicsItemFlag.ItemIgnoresTransformations)
        glyph.setFont(QFont('Segoe UI', 10, QFont.Bold))
        glyph.setBrush(QBrush(color))
        glyph.setPos(m.x + 0.06, m.y + 0.28)
        glyph.setZValue(9)
        label = QGraphicsSimpleTextItem(
            f'{m.kind}' + (f' {m.conf}%' if isinstance(m.conf, int) else ''))
        label.setFlag(label.GraphicsItemFlag.ItemIgnoresTransformations)
        label.setFont(QFont('Consolas', 7, QFont.Bold))
        label.setBrush(QBrush(color.lighter(125)))
        label.setPos(m.x + 0.06, m.y - 0.06)
        label.setZValue(9)
        for it in (ring, glyph, label):
            sc.addItem(it)
        m.items = [ring, glyph, label]

    def clear_markers(self) -> None:
        for m in self._markers:
            for it in m.items:
                self.canvas.scene().removeItem(it)
        self._markers.clear()
        self.markersChanged.emit([])

    def center_on(self, x: float, y: float) -> None:
        self.canvas.centerOn(x, y)

    def fit_map(self, *, from_button: bool = False) -> None:
        if from_button:
            self._user_nav = False         # FIT re-engages auto-fit
        if self._grid_item is not None:
            rect = self._grid_item.mapRectToScene(
                self._grid_item.boundingRect()).adjusted(-0.25, -0.25, 0.25, 0.25)
            self.canvas.fitInView(rect, Qt.KeepAspectRatio)
            if self.canvas.ppm() > MAX_PPM:
                f = MAX_PPM / self.canvas.ppm()
                self.canvas.scale(f, f)
            self._scalebar.set_ppm(self.canvas.ppm())
