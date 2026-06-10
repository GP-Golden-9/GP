import math

import pytest

from gpcore.nav import GotoController, GotoState


def test_idle_without_goal():
    c = GotoController()
    cmd = c.step(0, 0, 0)
    assert cmd.state == GotoState.IDLE
    assert (cmd.linear, cmd.angular) == (0.0, 0.0)


def test_rotates_first_when_facing_away():
    c = GotoController()
    c.set_goal(0.0, 2.0)              # goal is at +90°
    cmd = c.step(0.0, 0.0, 0.0)       # robot faces +x
    assert cmd.state == GotoState.ROTATING
    assert cmd.linear == 0.0
    assert cmd.angular == pytest.approx(0.4)      # 1.2 * (π/2) clamped to 0.4
    assert cmd.status == 'ROTATING:0.00,2.00'


def test_rotation_direction_sign():
    c = GotoController()
    c.set_goal(0.0, -2.0)
    cmd = c.step(0.0, 0.0, 0.0)
    assert cmd.angular == pytest.approx(-0.4)


def test_drives_when_aligned():
    c = GotoController()
    c.set_goal(1.0, 0.0)
    cmd = c.step(0.0, 0.0, 0.0)
    assert cmd.state == GotoState.DRIVING
    assert cmd.linear == pytest.approx(0.15)      # min(0.15, 0.5*1.0)
    assert cmd.status == 'DRIVING:1.00m'


def test_linear_slows_near_goal():
    c = GotoController()
    c.set_goal(0.2, 0.0)
    cmd = c.step(0.0, 0.0, 0.0)
    assert cmd.linear == pytest.approx(0.5 * 0.2)  # below the clamp now


def test_driving_angular_correction_is_half_clamped():
    c = GotoController()
    c.set_goal(5.0, 0.5)              # slight offset → small angle error
    cmd = c.step(0.0, 0.0, 0.0)
    angle_err = math.atan2(0.5, 5.0)
    assert cmd.state == GotoState.DRIVING
    assert cmd.angular == pytest.approx(min(0.2, 1.2 * 0.5 * angle_err))
    assert abs(cmd.angular) <= 0.2    # half of max_angular


def test_arrival_clears_goal_and_formats_status():
    c = GotoController()
    c.set_goal(0.05, 0.05)
    cmd = c.step(0.0, 0.0, 0.0)       # distance ≈ 0.071 < 0.12
    assert cmd.state == GotoState.ARRIVED
    assert cmd.status == 'ARRIVED:0.05,0.05'
    assert not c.has_goal
    follow_up = c.step(0.0, 0.0, 0.0)
    assert follow_up.status == 'IDLE'


def test_cancel_stops():
    c = GotoController()
    c.set_goal(3.0, 0.0)
    cmd = c.cancel()
    assert cmd.state == GotoState.IDLE
    assert not c.has_goal
