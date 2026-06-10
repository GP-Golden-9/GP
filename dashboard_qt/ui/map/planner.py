"""Global path planner over the shared occupancy grid — pure numpy, no Qt.

Why console-side: the SLAM map lives here, and the robots deliberately run
dumb-but-reliable executors (rotate-then-drive). The console plans the
intelligent route; the robot only ever receives short straight legs.

Pipeline:
  1. HARD inflation — obstacles grown by robot radius + margin: anywhere
     the path goes, the whole robot fits.
  2. SOFT cost rings — extra traversal cost near obstacles, so corridors
     and doorways are crossed through their CENTER, not hugging a wall.
  3. A* (8-connected, octile heuristic) on the cost field.
  4. Snap: a goal clicked slightly inside a wall snaps to the nearest free
     cell within SNAP_M.
  5. Line-of-sight simplification — the dense cell path collapses to a few
     straight waypoints the robot's executor can actually follow.

Unknown space (-1) is treated as blocked: the planner never routes a robot
through territory the mapper has not cleared.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

ROBOT_RADIUS_M = 0.16
HARD_MARGIN_M = 0.04
SOFT_RINGS = ((2, 6.0), (2, 2.0))      # (dilation steps, added cost) per ring
SNAP_M = 0.45
OCC_THRESHOLD = 50

SQRT2 = math.sqrt(2.0)


def _dilate(mask: np.ndarray, steps: int) -> np.ndarray:
    m = mask.copy()
    for _ in range(steps):
        p = np.pad(m, 1, constant_values=False)
        m = (p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
             | p[:-2, :-2] | p[:-2, 2:] | p[2:, :-2] | p[2:, 2:] | m)
    return m


def build_costmap(grid: np.ndarray, res: float) -> tuple[np.ndarray, np.ndarray]:
    """→ (blocked bool HxW, soft_cost float HxW)."""
    occ = grid > OCC_THRESHOLD
    unknown = grid < 0
    hard_steps = max(1, math.ceil((ROBOT_RADIUS_M + HARD_MARGIN_M) / res))
    blocked = _dilate(occ, hard_steps) | unknown

    soft = np.zeros(grid.shape, dtype=np.float32)
    ring_mask = blocked.copy()
    for steps, cost in SOFT_RINGS:
        grown = _dilate(ring_mask, steps)
        soft[grown & ~ring_mask] += cost
        ring_mask = grown
    return blocked, soft


def _to_cell(x: float, y: float, ox: float, oy: float, res: float,
             shape) -> tuple[int, int] | None:
    i = int((y - oy) / res)
    j = int((x - ox) / res)
    if 0 <= i < shape[0] and 0 <= j < shape[1]:
        return i, j
    return None


def _to_world(i: int, j: int, ox: float, oy: float, res: float) -> tuple[float, float]:
    return ox + (j + 0.5) * res, oy + (i + 0.5) * res


def _snap_free(blocked: np.ndarray, cell, max_cells: int):
    """BFS to the nearest unblocked cell within max_cells (or None)."""
    if cell is None:
        return None
    if not blocked[cell]:
        return cell
    from collections import deque
    seen = {cell}
    q = deque([(cell, 0)])
    while q:
        (i, j), d = q.popleft()
        if d > max_cells:
            return None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                ni, nj = i + di, j + dj
                if (ni, nj) in seen:
                    continue
                if 0 <= ni < blocked.shape[0] and 0 <= nj < blocked.shape[1]:
                    if not blocked[ni, nj]:
                        return ni, nj
                    seen.add((ni, nj))
                    q.append(((ni, nj), d + 1))
    return None


def _line_free(blocked: np.ndarray, a, b) -> bool:
    """Dense sampling along a→b; every touched cell must be free."""
    (ai, aj), (bi, bj) = a, b
    steps = int(max(abs(bi - ai), abs(bj - aj)) * 2) + 1
    for s in range(steps + 1):
        t = s / steps
        i = int(round(ai + (bi - ai) * t))
        j = int(round(aj + (bj - aj) * t))
        if blocked[i, j]:
            return False
    return True


def _simplify(blocked: np.ndarray, cells: list) -> list:
    if len(cells) <= 2:
        return cells
    out = [cells[0]]
    anchor = 0
    for k in range(2, len(cells)):
        if not _line_free(blocked, cells[anchor], cells[k]):
            out.append(cells[k - 1])
            anchor = k - 1
    out.append(cells[-1])
    return out


def plan_path(grid: np.ndarray, res: float, ox: float, oy: float,
              start_xy: tuple[float, float],
              goal_xy: tuple[float, float]) -> list[tuple[float, float]] | None:
    """A* route start→goal in world meters. None when no safe path exists.

    Returns sparse waypoints (goal included, start excluded). Complexity is
    fine for arena-scale maps (≤ ~200×200 cells in a few tens of ms)."""
    blocked, soft = build_costmap(grid, res)
    snap_cells = max(1, int(SNAP_M / res))
    start = _snap_free(blocked, _to_cell(*start_xy, ox, oy, res, grid.shape),
                       snap_cells)
    goal = _snap_free(blocked, _to_cell(*goal_xy, ox, oy, res, grid.shape),
                      snap_cells)
    if start is None or goal is None:
        return None

    h_, w_ = grid.shape
    g_cost = {start: 0.0}
    parent = {}
    gi, gj = goal

    def heuristic(c):
        di, dj = abs(c[0] - gi), abs(c[1] - gj)
        return (di + dj) + (SQRT2 - 2) * min(di, dj)

    open_q = [(heuristic(start), 0.0, start)]
    closed = set()
    while open_q:
        _f, g, cur = heapq.heappop(open_q)
        if cur == goal:
            cells = [cur]
            while cur in parent:
                cur = parent[cur]
                cells.append(cur)
            cells.reverse()
            sparse = _simplify(blocked, cells)
            return [_to_world(i, j, ox, oy, res) for i, j in sparse[1:]]
        if cur in closed:
            continue
        closed.add(cur)
        ci, cj = cur
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                if di == 0 and dj == 0:
                    continue
                ni, nj = ci + di, cj + dj
                if not (0 <= ni < h_ and 0 <= nj < w_):
                    continue
                nxt = (ni, nj)
                if nxt in closed or blocked[ni, nj]:
                    continue
                # no corner-cutting through diagonal wall gaps
                if di and dj and (blocked[ci, nj] or blocked[ni, cj]):
                    continue
                step = SQRT2 if (di and dj) else 1.0
                ng = g + step * (1.0 + soft[ni, nj])
                if ng < g_cost.get(nxt, float('inf')):
                    g_cost[nxt] = ng
                    parent[nxt] = cur
                    heapq.heappush(open_q, (ng + heuristic(nxt), ng, nxt))
    return None
