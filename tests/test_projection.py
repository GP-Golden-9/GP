"""Shared-map geometry tests: frame alignment + detection projection."""

import math
import sys

import pytest

sys.path.insert(0, 'dashboard_qt')

from ui.map.projection import (FrameOffset, Pose, apply_offset,
                               detection_bearing, detection_distance,
                               detection_to_world, offset_from_alignment,
                               world_point_to_robot)


def test_identity_offset_is_noop():
    p = Pose(1.2, -0.7, 0.5)
    out = apply_offset(p, FrameOffset())
    assert (out.x, out.y, out.th) == pytest.approx((1.2, -0.7, 0.5))


def test_alignment_roundtrip():
    # operator drops the robot at `desired` while odometry says `raw` —
    # afterwards apply_offset(raw) must equal desired exactly
    raw = Pose(2.0, 1.0, 0.3)
    desired = Pose(-1.5, 0.8, 2.1)
    off = offset_from_alignment(raw, desired)
    out = apply_offset(raw, off)
    assert out.x == pytest.approx(desired.x)
    assert out.y == pytest.approx(desired.y)
    assert out.th == pytest.approx(desired.th)


def test_alignment_tracks_future_motion():
    # after alignment, robot motion in its own frame maps consistently
    raw0 = Pose(0.0, 0.0, 0.0)
    desired = Pose(1.0, 1.0, math.pi / 2)      # placed facing +y on the map
    off = offset_from_alignment(raw0, desired)
    raw1 = Pose(0.5, 0.0, 0.0)                  # drove 0.5 m "forward"
    out = apply_offset(raw1, off)
    assert out.x == pytest.approx(1.0)          # forward in robot frame = +y map
    assert out.y == pytest.approx(1.5)


def test_goal_click_inverse_transform():
    off = offset_from_alignment(Pose(0, 0, 0), Pose(1.0, 1.0, math.pi / 2))
    # operator clicks (1.0, 2.0) on the shared map → 1 m ahead of the robot
    rx, ry = world_point_to_robot(1.0, 2.0, off)
    assert rx == pytest.approx(1.0)
    assert ry == pytest.approx(0.0, abs=1e-9)


def test_bearing_signs():
    assert detection_bearing(0.5, 62) == pytest.approx(0.0)
    assert detection_bearing(1.0, 62) < 0      # right of center → clockwise
    assert detection_bearing(0.0, 62) > 0
    assert abs(detection_bearing(1.0, 62)) == pytest.approx(math.radians(31))


def test_distance_model_clamped():
    assert detection_distance(1.0) == pytest.approx(0.9)   # full-frame flame
    assert detection_distance(0.001) == 4.0                # tiny → clamp far
    # h is normalized (≤1); out-of-range input saturates to the nearest value
    assert detection_distance(5.0) == pytest.approx(0.9)
    assert detection_distance(0.5) == pytest.approx(1.8)   # half frame ≈ 1.8 m


def test_detection_lands_ahead_of_robot():
    pose = Pose(0.0, 0.0, 0.0)                  # facing +x
    x, y = detection_to_world(pose, cx_norm=0.5, bbox_h_norm=0.9, hfov_deg=62)
    assert y == pytest.approx(0.0, abs=1e-9)
    assert 0.4 <= x <= 4.0

    # box on the LEFT edge of the image → marker left of heading (+y)
    x2, y2 = detection_to_world(pose, cx_norm=0.0, bbox_h_norm=0.9, hfov_deg=62)
    assert y2 > 0
