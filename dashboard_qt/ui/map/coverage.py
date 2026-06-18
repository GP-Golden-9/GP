"""Area-coverage path generator — the 'suggested' reference path for Beta.

The master (Alpha) maps; the console turns that occupancy grid into a
boustrophedon ('lawnmower') route that covers the free space. Beta follows it
as a GUIDE — its local fuser deviates around unmapped obstacles and merges
back — so this only has to be a reasonable reference, not a perfect plan.

Pure + unit-tested (no Qt, no ROS): grid in, world waypoints out.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

Pt = Tuple[float, float]

# Occupancy: <0 unknown, 0 free, 100 occupied (ROS OccupancyGrid convention).
FREE_MAX = 25            # cells at/below this are treated as drivable


def _free_mask(grid: np.ndarray) -> np.ndarray:
    return (grid >= 0) & (grid <= FREE_MAX)


def coverage_path(grid: np.ndarray, res: float, ox: float, oy: float,
                  lane_m: float = 0.30, margin_m: float = 0.25,
                  start: Optional[Pt] = None) -> List[Pt]:
    """Boustrophedon coverage over the free cells of `grid`.

    grid[r, c] is occupancy; world x = ox + c*res, world y = oy + r*res.
    `lane_m` = spacing between sweep rows (≈ robot width); `margin_m` keeps
    waypoints off the walls. Returns world (x, y) waypoints, ordered, snaking
    rows top→bottom and alternating L→R / R→L. Empty list if nothing is free.
    """
    free = _free_mask(grid)
    if not free.any():
        return []
    rows = np.where(free.any(axis=1))[0]
    r0, r1 = int(rows[0]), int(rows[-1])

    lane_rows = max(1, int(round(lane_m / res)))
    inset = max(0, int(round(margin_m / res)))

    waypoints: List[Pt] = []
    flip = False
    r = r0 + inset
    while r <= r1 - inset:
        cols = np.where(free[r])[0]
        if cols.size:
            c_lo, c_hi = int(cols[0]) + inset, int(cols[-1]) - inset
            if c_hi >= c_lo:
                xa = ox + (c_lo + 0.5) * res
                xb = ox + (c_hi + 0.5) * res
                y = oy + (r + 0.5) * res
                ends = [(xb, y), (xa, y)] if flip else [(xa, y), (xb, y)]
                waypoints.extend(ends)
                flip = not flip
        r += lane_rows

    if start is not None and waypoints:
        # Start the sweep from the end nearest the robot (less initial travel).
        d_first = (waypoints[0][0] - start[0]) ** 2 + (waypoints[0][1] - start[1]) ** 2
        d_last = (waypoints[-1][0] - start[0]) ** 2 + (waypoints[-1][1] - start[1]) ** 2
        if d_last < d_first:
            waypoints.reverse()
    return waypoints
