"""Area-coverage path generator — the 'suggested' reference path for Beta.

The master (Alpha) maps; the console turns that occupancy grid into a
boustrophedon ('lawnmower') route that covers the free space. Beta follows it
as a GUIDE — its local fuser deviates around unmapped obstacles and merges
back — so this only has to be a reasonable reference, not a perfect plan.

Robust to rough maps: the free space is ERODED by the robot's clearance so no
waypoint lands against a wall/obstacle, and each row uses its LARGEST open run
so a lane never routes across a gap. Pure + unit-tested (no Qt, no ROS).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

Pt = Tuple[float, float]

# Occupancy: <0 unknown, 0 free, 100 occupied (ROS OccupancyGrid convention).
FREE_MAX = 25            # cells at/below this (and >= 0) are drivable


def _free_mask(grid: np.ndarray) -> np.ndarray:
    return (grid >= 0) & (grid <= FREE_MAX)


def _dilate(mask: np.ndarray, n: int) -> np.ndarray:
    """Grow a boolean mask by n cells (4-connectivity), numpy-only."""
    out = mask.copy()
    for _ in range(n):
        g = out.copy()
        g[1:, :] |= out[:-1, :]
        g[:-1, :] |= out[1:, :]
        g[:, 1:] |= out[:, :-1]
        g[:, :-1] |= out[:, 1:]
        out = g
    return out


def _largest_run(row: np.ndarray) -> Optional[Tuple[int, int]]:
    """(lo, hi) inclusive of the longest contiguous True run, or None."""
    best = None
    best_len = 0
    i, n = 0, row.shape[0]
    while i < n:
        if row[i]:
            j = i
            while j < n and row[j]:
                j += 1
            if j - i > best_len:
                best_len = j - i
                best = (i, j - 1)
            i = j
        else:
            i += 1
    return best


def coverage_path(grid: np.ndarray, res: float, ox: float, oy: float,
                  lane_m: float = 0.55, clearance_m: float = 0.22,
                  max_waypoints: int = 16,
                  start: Optional[Pt] = None) -> List[Pt]:
    """Boustrophedon coverage over the CLEARED free cells of `grid`.

    grid[r, c] is occupancy; world x = ox + c*res, world y = oy + r*res.
    `lane_m` spaces the sweep rows (≈ robot width); `clearance_m` keeps every
    waypoint that far from any wall/obstacle/unknown cell. `max_waypoints`
    CAPS the path complexity — on a big/irregular map the lane spacing is
    auto-widened so the robot gets a simple handful of sweeps, not dozens of
    full-width passes it can't reliably follow. Empty if nothing has clearance.
    """
    # Non-drivable = occupied OR unknown (never aim Beta into unmapped space).
    occ = ~_free_mask(grid)
    if occ.all():
        return []
    inset = max(1, int(round(clearance_m / res)))
    clear = ~_dilate(occ, inset)              # free cells with full clearance
    if not clear.any():
        return []

    rows = np.where(clear.any(axis=1))[0]
    r0, r1 = int(rows[0]), int(rows[-1])
    lane_rows = max(1, int(round(lane_m / res)))
    # Auto-coarsen so the path stays under max_waypoints (~2 per sweep row).
    max_rows = max(2, max_waypoints // 2)
    lane_rows = max(lane_rows, int(np.ceil((r1 - r0 + 1) / max_rows)))

    waypoints: List[Pt] = []
    flip = False
    r = r0
    while r <= r1:
        run = _largest_run(clear[r])
        if run is not None and run[1] > run[0]:
            c_lo, c_hi = run
            xa = ox + (c_lo + 0.5) * res
            xb = ox + (c_hi + 0.5) * res
            y = oy + (r + 0.5) * res
            ends = [(xb, y), (xa, y)] if flip else [(xa, y), (xb, y)]
            waypoints.extend(ends)
            flip = not flip
        r += lane_rows

    if start is not None and waypoints:
        d_first = (waypoints[0][0] - start[0]) ** 2 + (waypoints[0][1] - start[1]) ** 2
        d_last = (waypoints[-1][0] - start[0]) ** 2 + (waypoints[-1][1] - start[1]) ** 2
        if d_last < d_first:
            waypoints.reverse()
    return waypoints
