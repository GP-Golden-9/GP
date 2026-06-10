"""SLAM map view — QGraphicsView with the scene in METERS (world frame).

Layers (cheap to update independently):
  GridLayer   QPixmap of the occupancy grid, swapped only when a new map
              arrives (≤1 Hz) — never re-rendered per frame
  ScanLayer   laser endpoints as one QPainterPath, rebuilt ≤10 Hz
  RobotItem   pose circle + heading line, moved at telemetry rate
  GoalItem    crosshair + dashed line from robot, on click-to-navigate

Interactions: wheel = zoom (anchored under cursor), right-drag = pan,
left-click = navigation goal → ``goalClicked(x, y)`` in world meters.
"""

from __future__ import annotations

import math
import zlib

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QImage, QPainter, QPainterPath,
                           QPen, QPixmap, qRgb)
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from views import theme

ROBOT_RADIUS_M = 0.115
SCAN_DOT_M = 0.02
SCAN_REBUILD_MIN_S = 0.1


class MapView(QGraphicsView):
    goalClicked = Signal(float, float)          # world meters

    MIN_PX_PER_M = 15
    MAX_PX_PER_M = 800

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor('#0d1422'))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.SmartViewportUpdate)
        # world frame: x right, y UP (Qt default is y-down → flip the view)
        self.scale(120, -120)                   # initial: 120 px per meter

        self._grid_item: QGraphicsPixmapItem | None = None
        scan_color = QColor('#fb7185')          # laser endpoints (rose)
        self._scan_item = QGraphicsPathItem()
        self._scan_item.setPen(QPen(scan_color, 0))
        self._scan_item.setBrush(QBrush(scan_color))
        self._scan_item.setZValue(2)
        self.scene().addItem(self._scan_item)

        self._robot_item = QGraphicsPathItem()
        self._robot_item.setPen(QPen(QColor('#6ee7b7'), 0.02))
        self._robot_item.setBrush(QBrush(QColor(52, 211, 153, 215)))
        self._robot_item.setZValue(3)
        self.scene().addItem(self._robot_item)

        self._goal_line_item = QGraphicsPathItem()
        line_pen = QPen(QColor(theme.WARN), 0.015)
        line_pen.setStyle(Qt.DashLine)
        self._goal_line_item.setPen(line_pen)
        self._goal_line_item.setZValue(4)
        self.scene().addItem(self._goal_line_item)

        self._goal_item = QGraphicsPathItem()
        self._goal_item.setPen(QPen(QColor(theme.BAD), 0.025))
        self._goal_item.setZValue(5)
        self.scene().addItem(self._goal_item)

        self._pose = (0.0, 0.0, 0.0)
        self._goal: tuple[float, float] | None = None
        self._have_grid = False
        self._fitted_once = False
        self._pan_last = None
        self._last_scan_build = 0.0

    # ── data in ───────────────────────────────────────────────────────────
    def update_map(self, payload: dict) -> None:
        """payload: {w,h,res,ox,oy,enc,data} — int8 occupancy, zlib."""
        try:
            w, h, res = payload['w'], payload['h'], payload['res']
            raw = payload['data']
            if payload.get('enc') == 'zlib':
                raw = zlib.decompress(raw)
            grid = np.frombuffer(raw, dtype=np.int8).reshape((h, w))
        except (KeyError, ValueError, zlib.error):
            return

        # Theme palette: unknown deep slate, free light, occupied near-black
        img = np.zeros((h, w), dtype=np.uint8)          # 0 = unknown
        img[grid == 0] = 1                              # 1 = free
        img[grid > 50] = 2                              # 2 = occupied
        # occupancy row 0 is the SOUTH edge; QImage row 0 is the TOP → flip
        img = np.ascontiguousarray(np.flipud(img))

        qimg = QImage(img.data, w, h, w, QImage.Format_Indexed8)
        qimg.setColorTable([qRgb(*theme.MAP_UNKNOWN),
                            qRgb(*theme.MAP_FREE),
                            qRgb(*theme.MAP_OCCUPIED)])
        pixmap = QPixmap.fromImage(qimg.copy())

        if self._grid_item is None:
            self._grid_item = self.scene().addPixmap(pixmap)
            self._grid_item.setZValue(1)
        else:
            self._grid_item.setPixmap(pixmap)
        # place: 1 px = res meters; after flipud the pixmap's top-left is the
        # NW corner of the map → position so south-west lands at (ox, oy)
        self._grid_item.setTransform(
            # scale to meters, then move into place (y-up world)
            # QTransform: translate(ox, oy + h*res) then scale(res, -res)
            _grid_transform(payload['ox'], payload['oy'], res, h))
        self._have_grid = True
        if not self._fitted_once:
            self.fit_map()
            self._fitted_once = True

    def update_pose(self, x: float, y: float, theta: float) -> None:
        self._pose = (x, y, theta)
        path = QPainterPath()
        path.addEllipse(QPointF(x, y), ROBOT_RADIUS_M, ROBOT_RADIUS_M)
        hx = x + (ROBOT_RADIUS_M + 0.10) * math.cos(theta)
        hy = y + (ROBOT_RADIUS_M + 0.10) * math.sin(theta)
        path.moveTo(x, y)
        path.lineTo(hx, hy)
        self._robot_item.setPath(path)
        if self._goal is not None:
            self._draw_goal()

    def update_scan(self, payload: dict, pose: tuple[float, float, float] | None = None) -> None:
        import time
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
        x, y, th = pose or self._pose
        n = len(ranges)
        if n == 0:
            return
        angles = a0 + np.arange(n, dtype=np.float32) * da + th
        valid = np.isfinite(ranges) & (ranges > 0.05) & (ranges < rmax)
        px = x + ranges[valid] * np.cos(angles[valid])
        py = y + ranges[valid] * np.sin(angles[valid])

        path = QPainterPath()
        for i in range(0, len(px), max(1, len(px) // 400)):   # cap dot count
            path.addEllipse(QPointF(float(px[i]), float(py[i])),
                            SCAN_DOT_M, SCAN_DOT_M)
        self._scan_item.setPath(path)

    def set_goal(self, x: float, y: float) -> None:
        self._goal = (x, y)
        self._draw_goal()

    def clear_goal(self) -> None:
        self._goal = None
        self._goal_item.setPath(QPainterPath())
        self._goal_line_item.setPath(QPainterPath())

    def _draw_goal(self) -> None:
        if self._goal is None:
            return
        gx, gy = self._goal
        s = 0.15
        path = QPainterPath()
        path.moveTo(gx - s, gy); path.lineTo(gx + s, gy)
        path.moveTo(gx, gy - s); path.lineTo(gx, gy + s)
        path.addEllipse(QPointF(gx, gy), s * 0.6, s * 0.6)
        self._goal_item.setPath(path)

        rx, ry, _ = self._pose
        line = QPainterPath()
        line.moveTo(rx, ry); line.lineTo(gx, gy)
        self._goal_line_item.setPath(line)

    def fit_map(self) -> None:
        if self._grid_item is not None:
            self.fitInView(self._grid_item, Qt.KeepAspectRatio)

    # ── interactions ──────────────────────────────────────────────────────
    def wheelEvent(self, event) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        # clamp so the user can never zoom into pixel soup or lose the map
        new_scale = abs(self.transform().m11()) * factor
        if self.MIN_PX_PER_M <= new_scale <= self.MAX_PX_PER_M:
            self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._pan_last = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.LeftButton and self._have_grid:
            p = self.mapToScene(event.position().toPoint())
            self.goalClicked.emit(p.x(), p.y())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._pan_last is not None:
            delta = event.position() - self._pan_last
            self._pan_last = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._pan_last = None
            self.setCursor(Qt.ArrowCursor)
            return
        super().mouseReleaseEvent(event)


def _grid_transform(ox: float, oy: float, res: float, h: int):
    """Pixmap(px, y-down, row0=north after flip) → world meters (y-up)."""
    from PySide6.QtGui import QTransform
    t = QTransform()
    t.translate(ox, oy + h * res)
    t.scale(res, -res)
    return t
