"""Path planner tests — the robots-drive-into-walls regression suite."""

import sys

import numpy as np
import pytest

sys.path.insert(0, 'dashboard_qt')

from ui.map.planner import build_costmap, plan_path

RES = 0.05
N = 80                                   # 4×4 m, like the arena
OX = OY = -2.0


def arena_with_door(door: bool = True) -> np.ndarray:
    """Free 4×4 m room split by a vertical wall at x=0, door at y≈+1."""
    g = np.zeros((N, N), dtype=np.int8)
    g[0, :] = 100; g[-1, :] = 100; g[:, 0] = 100; g[:, -1] = 100
    wall_col = N // 2
    g[:, wall_col] = 100
    if door:
        # door: y from +0.7 to +1.3  → rows 54..66
        g[54:66, wall_col] = 0
    return g


def test_path_goes_through_the_door_not_the_wall():
    g = arena_with_door()
    path = plan_path(g, RES, OX, OY, start_xy=(-1.2, -1.2), goal_xy=(1.2, -1.2))
    assert path is not None and len(path) >= 2
    # the path must rise to the door (y ≈ +0.7..1.3) to cross x=0 —
    # a straight line at y=-1.2 would smash into the wall
    crossing_ys = [y for (x, y) in path if -0.35 < x < 0.35]
    assert crossing_ys, 'path never crosses the wall plane?'
    assert all(y > 0.4 for y in crossing_ys), \
        f'path crossed the wall outside the door: {path}'
    # ends at the goal
    gx, gy = path[-1]
    assert abs(gx - 1.2) < 0.15 and abs(gy + 1.2) < 0.15


def test_no_door_means_no_path():
    g = arena_with_door(door=False)
    assert plan_path(g, RES, OX, OY, (-1.2, -1.2), (1.2, -1.2)) is None


def test_goal_in_wall_snaps_to_nearest_free():
    g = arena_with_door()
    path = plan_path(g, RES, OX, OY, (-1.2, 0.0), (-1.999, 0.0))  # at the border wall
    assert path is not None
    gx, gy = path[-1]
    assert gx > -2.0 + 0.15                 # snapped inside, off the wall


def test_open_space_is_few_waypoints():
    g = np.zeros((N, N), dtype=np.int8)
    g[0, :] = 100; g[-1, :] = 100; g[:, 0] = 100; g[:, -1] = 100
    path = plan_path(g, RES, OX, OY, (-1.2, -1.2), (1.2, 1.2))
    assert path is not None
    assert len(path) <= 4                   # LOS simplification works


def test_unknown_space_is_not_traversable():
    g = arena_with_door()
    g[1:-1, 1:N // 2] = -1                  # left half unexplored
    assert plan_path(g, RES, OX, OY, (-1.2, -1.2), (1.2, 1.2)) is None


def test_inflation_blocks_tight_gaps():
    # 10 cm gap (2 cells) — robot is 32 cm wide: must NOT fit
    g = arena_with_door(door=False)
    g[40:42, N // 2] = 0
    assert plan_path(g, RES, OX, OY, (-1.2, 0.0), (1.2, 0.0)) is None


def test_costmap_shapes():
    g = arena_with_door()
    blocked, soft = build_costmap(g, RES)
    assert blocked.shape == g.shape and soft.shape == g.shape
    assert blocked.any() and (soft > 0).any()
    # door center stays traversable after inflation
    assert not blocked[60, N // 2]
