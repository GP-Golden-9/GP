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
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

ROBOT_RADIUS_M = 0.115
SCAN_DOT_M = 0.02
SCAN_REBUILD_MIN_S = 0.1


class MapView(QGraphicsView):
    goalClicked = Signal(float, float)          # world meters

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor(40, 40, 46))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        # world frame: x right, y UP (Qt default is y-down → flip the view)
        self.scale(120, -120)                   # initial: 120 px per meter

        self._grid_item: QGraphicsPixmapItem | None = None
        self._scan_item = QGraphicsPathItem()
        self._scan_item.setPen(QPen(QColor(235, 64, 52), 0))
        self._scan_item.setBrush(QBrush(QColor(235, 64, 52)))
        self._scan_item.setZValue(2)
        self.scene().addItem(self._scan_item)

        self._robot_item = QGraphicsPathItem()
        self._robot_item.setPen(QPen(QColor(0, 255, 120), 0))
        self._robot_item.setBrush(QBrush(QColor(0, 180, 80, 200)))
        self._robot_item.setZValue(3)
        self.scene().addItem(self._robot_item)

        self._goal_item = QGraphicsPathItem()
        pen = QPen(QColor(255, 70, 70), 0)
        self._goal_item.setPen(pen)
        self._goal_item.setZValue(4)
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

        # RViz palette: unknown gray, free near-white, occupied black
        img = np.full((h, w), 205, dtype=np.uint8)
        img[grid == 0] = 254
        img[grid > 50] = 0
        # occupancy row 0 is the SOUTH edge; QImage row 0 is the TOP → flip
        img = np.ascontiguousarray(np.flipud(img))

        qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8).copy()
        pixmap = QPixmap.fromImage(qimg)

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

    def _draw_goal(self) -> None:
        if self._goal is None:
            return
        gx, gy = self._goal
        s = 0.15
        path = QPainterPath()
        path.moveTo(gx - s, gy); path.lineTo(gx + s, gy)
        path.moveTo(gx, gy - s); path.lineTo(gx, gy + s)
        path.addEllipse(QPointF(gx, gy), s * 0.6, s * 0.6)
        rx, ry, _ = self._pose
        path.moveTo(rx, ry); path.lineTo(gx, gy)
        self._goal_item.setPath(path)

    def fit_map(self) -> None:
        if self._grid_item is not None:
            self.fitInView(self._grid_item, Qt.KeepAspectRatio)

    # ── interactions ──────────────────────────────────────────────────────
    def wheelEvent(self, event) -> None:
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
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
