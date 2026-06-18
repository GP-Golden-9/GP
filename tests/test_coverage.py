"""Coverage-path generator tests — pure, no Qt/ROS."""

import numpy as np

from dashboard_qt.ui.map.coverage import coverage_path, _free_mask


def _open_room(h=20, w=30):
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


def test_covers_free_space_in_bounds():
    g = _open_room()
    res, ox, oy = 0.05, -0.75, -0.5
    wps = coverage_path(g, res, ox, oy, lane_m=0.15, margin_m=0.05)
    assert len(wps) >= 4
    # every waypoint lands inside the room's world extent
    xs = [p[0] for p in wps]
    ys = [p[1] for p in wps]
    assert min(xs) >= ox and max(xs) <= ox + g.shape[1] * res
    assert min(ys) >= oy and max(ys) <= oy + g.shape[0] * res


def test_boustrophedon_alternates_direction():
    g = _open_room()
    wps = coverage_path(g, 0.05, 0.0, 0.0, lane_m=0.15, margin_m=0.05)
    # rows come in pairs (left-end, right-end); consecutive rows flip, so the
    # x of the FIRST point of row N+1 should be near the LAST of row N (snake).
    assert len(wps) % 2 == 0
    # at least one reversal: not all first-points on the same side
    firsts = [wps[i][0] for i in range(0, len(wps), 2)]
    assert max(firsts) - min(firsts) > 0.1


def test_start_orders_nearest_end_first():
    g = _open_room()
    res, ox, oy = 0.05, 0.0, 0.0
    far = coverage_path(g, res, ox, oy, start=(0.0, 0.0))
    near_top = far[0]
    # starting near the TOP-left should not begin at the bottom of the sweep
    assert near_top[1] <= (oy + g.shape[0] * res) / 2 + 0.3


def test_free_mask_threshold():
    g = np.array([[-1, 0, 25, 26, 100]], dtype=np.int8)
    assert list(_free_mask(g)[0]) == [False, True, True, False, False]
