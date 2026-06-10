"""Pure geometry for the shared map — no Qt, fully unit-tested.

Two responsibilities:

1. FRAME ALIGNMENT — each robot dead-reckons in its OWN odom frame; the
   operator aligns it to the shared (robot1 SLAM) map once with the
   Set-Pose tool. We keep a rigid 2-D transform per robot:

       world = R(off.th) · raw + off.xy        heading: th_w = raw.th + off.th

2. DETECTION PROJECTION — a camera detection becomes a world point by
   casting a ray from the robot's aligned pose:
       bearing  from the bounding-box center x and the camera's horizontal
                FOV (box right of center → ray right of heading)
       distance from the bounding-box height (pinhole model: a flame of
                roughly constant real height appears smaller with distance),
                clamped to a sane range — monocular range is an ESTIMATE
                and the marker is labeled as such.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    th: float


@dataclass(frozen=True)
class FrameOffset:
    x: float = 0.0
    y: float = 0.0
    th: float = 0.0


def wrap(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def apply_offset(raw: Pose, off: FrameOffset) -> Pose:
    """Robot-frame pose → shared-map pose."""
    c, s = math.cos(off.th), math.sin(off.th)
    return Pose(
        x=off.x + c * raw.x - s * raw.y,
        y=off.y + s * raw.x + c * raw.y,
        th=wrap(raw.th + off.th),
    )


def offset_from_alignment(raw: Pose, desired: Pose) -> FrameOffset:
    """Solve the offset so that apply_offset(raw, off) == desired.

    This is what the Set-Pose tool computes when the operator drops the
    robot onto its true map position."""
    th = wrap(desired.th - raw.th)
    c, s = math.cos(th), math.sin(th)
    return FrameOffset(
        x=desired.x - (c * raw.x - s * raw.y),
        y=desired.y - (s * raw.x + c * raw.y),
        th=th,
    )


# ── Detection → world ─────────────────────────────────────────────────────
DIST_K = 0.9          # meters at bbox height = full frame (tuned for flames)
DIST_MIN = 0.4
DIST_MAX = 4.0


def detection_bearing(cx_norm: float, hfov_deg: float) -> float:
    """Bearing relative to the camera axis. Image x grows to the RIGHT;
    a target right of center lies clockwise from heading → negative yaw."""
    return -(cx_norm - 0.5) * math.radians(hfov_deg)


def detection_distance(bbox_h_norm: float) -> float:
    h = max(0.02, min(1.0, bbox_h_norm))
    return max(DIST_MIN, min(DIST_MAX, DIST_K / h))


def detection_to_world(pose: Pose, cx_norm: float, bbox_h_norm: float,
                       hfov_deg: float) -> tuple[float, float]:
    """``pose`` must already be in the shared map frame (offset applied)."""
    ang = pose.th + detection_bearing(cx_norm, hfov_deg)
    d = detection_distance(bbox_h_norm)
    return pose.x + d * math.cos(ang), pose.y + d * math.sin(ang)


def world_point_to_robot(x: float, y: float, off: FrameOffset) -> tuple[float, float]:
    """Shared-map point → robot odom frame (inverse of apply_offset).

    Navigation goals are clicked on the SHARED map but executed by the
    robot in ITS OWN frame — this is the transform that keeps a goal click
    honest after the operator aligned the robot with Set-Pose."""
    dx, dy = x - off.x, y - off.y
    c, s = math.cos(-off.th), math.sin(-off.th)
    return c * dx - s * dy, s * dx + c * dy
