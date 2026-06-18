"""Coverage-path generator tests — pure, no Qt/ROS."""

import numpy as np

from dashboard_qt.ui.map.coverage import (coverage_path, _free_mask,
                                          _dilate, _largest_run)


def _open_room(h=24, w=36):
    """Free interior (0), occupied 1-cell border (100)."""
    g = np.zeros((h, w), dtype=np.int8)
    g[0, :] = 100
    g[-1, :] = 100
    g[:, 0] = 100
    g[:, -1] = 100
    return g


def test_empty_when_nothing_free():
    g = np.full((10, 10), 100, dtype=np.int8)
    assert coverage_path(g, 0.05, 0.0, 0.0) == []


def test_unknown_is_not_drivable():
    g = np.full((10, 10), -1, dtype=np.int8)      # all unknown
    assert coverage_path(g, 0.05, 0.0, 0.0) == []


def test_covers_free_space_with_clearance():
    g = _open_room()
    res, ox, oy = 0.05, -0.9, -0.6
    wps = coverage_path(g, res, ox, oy, lane_m=0.15, clearance_m=0.05)
    assert len(wps) >= 4
    # every waypoint is inside the room AND clear of the walls (eroded)
    xs = [p[0] for p in wps]
    ys = [p[1] for p in wps]
    assert min(xs) > ox and max(xs) < ox + g.shape[1] * res
    assert min(ys) > oy and max(ys) < oy + g.shape[0] * res


def test_clearance_keeps_off_walls():
    g = _open_room()
    res, ox, oy = 0.05, 0.0, 0.0
    # big clearance -> waypoints well inside (>= ~clearance from the border)
    wps = coverage_path(g, res, ox, oy, lane_m=0.2, clearance_m=0.15)
    for (x, y) in wps:
        assert x >= ox + 0.12 and x <= ox + g.shape[1] * res - 0.12
        assert y >= oy + 0.12 and y <= oy + g.shape[0] * res - 0.12


def test_clearance_too_big_yields_empty():
    g = _open_room(h=12, w=12)
    assert coverage_path(g, 0.05, 0.0, 0.0, clearance_m=1.0) == []


def test_largest_run_picks_biggest_segment():
    row = np.array([1, 1, 0, 1, 1, 1, 1, 0, 1], dtype=bool)
    assert _largest_run(row) == (3, 6)
    assert _largest_run(np.zeros(5, dtype=bool)) is None


def test_dilate_grows_mask():
    m = np.zeros((5, 5), dtype=bool)
    m[2, 2] = True
    d = _dilate(m, 1)
    assert d[2, 1] and d[1, 2] and d[2, 3] and d[3, 2] and d[2, 2]
    assert not d[0, 0]


def test_free_mask_threshold():
    g = np.array([[-1, 0, 25, 26, 100]], dtype=np.int8)
    assert list(_free_mask(g)[0]) == [False, True, True, False, False]
