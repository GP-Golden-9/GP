import math

import pytest

from gpcore.kinematics import DiffDriveConfig, DiffDriveOdometry, normalize_angle, \
    quaternion_to_yaw, yaw_to_quaternion

CFG = DiffDriveConfig()  # 65 mm wheels, 330 ticks/rev, 0.23 m base, w=0.3


def make_odo():
    o = DiffDriveOdometry(config=CFG)
    o.update([0, 0, 0, 0], gyro_z=0.0, dt=0.02)  # baseline reading
    return o


def test_meters_per_tick():
    assert CFG.meters_per_tick == pytest.approx(math.pi * 0.065 / 330)


def test_straight_line_one_revolution():
    o = make_odo()
    pose = o.update([330, 330, 330, 330], gyro_z=0.0, dt=0.02)
    assert pose.x == pytest.approx(math.pi * 0.065)   # one wheel circumference
    assert pose.y == pytest.approx(0.0)
    assert pose.theta == pytest.approx(0.0)


def test_in_place_turn_blends_encoder_and_gyro():
    o = make_odo()
    t = 100  # right wheels +100 ticks, left wheels −100 ticks
    gyro_z = 0.5  # rad/s
    dt = 0.02
    pose = o.update([-t, -t, t, t], gyro_z=gyro_z, dt=dt)

    mpt = CFG.meters_per_tick
    d_theta_enc = (t * mpt - (-t * mpt)) / CFG.wheel_base_m
    expected = 0.3 * d_theta_enc + 0.7 * (gyro_z * dt)
    assert pose.theta == pytest.approx(expected)
    assert pose.x == pytest.approx(0.0)               # no translation
    assert pose.y == pytest.approx(0.0)


def test_translation_projected_along_new_heading():
    # Heading update happens BEFORE position integration (matches the node).
    o = make_odo()
    gyro_z = math.pi / 2 / 0.7 / 0.02  # makes blended dθ = π/2 with zero enc dθ...
    # simpler: drive equal wheels with a gyro turn in the same step
    o2 = make_odo()
    pose = o2.update([330, 330, 330, 330], gyro_z=1.0, dt=0.02)
    d_theta = 0.7 * (1.0 * 0.02)          # encoders say straight → only gyro term
    dist = math.pi * 0.065
    assert pose.theta == pytest.approx(d_theta)
    assert pose.x == pytest.approx(dist * math.cos(d_theta))
    assert pose.y == pytest.approx(dist * math.sin(d_theta))


def test_theta_wraps_to_minus_pi_pi():
    o = make_odo()
    # Pure gyro spin in big steps: 0.7 * 1.0 rad per update
    total = 0.0
    enc = [0, 0, 0, 0]
    for _ in range(10):
        pose = o.update(enc, gyro_z=50.0, dt=0.02)  # dθ = 0.7 rad/step
        total += 0.7
    assert -math.pi <= pose.theta <= math.pi
    assert pose.theta == pytest.approx(normalize_angle(total))


def test_dt_clamp_matches_node_fallback():
    o = make_odo()
    # dt of 5 s is nonsense → node clamps to 0.02
    pose = o.update([0, 0, 0, 0], gyro_z=1.0, dt=5.0)
    assert pose.theta == pytest.approx(0.7 * 1.0 * 0.02)


def test_short_encoder_array_ignored():
    o = make_odo()
    before = o.pose
    assert o.update([1, 2, 3], gyro_z=0.0, dt=0.02) == before


def test_quaternion_helpers_roundtrip():
    for theta in (-3.0, -1.0, 0.0, 0.5, 2.9):
        x, y, z, w = yaw_to_quaternion(theta)
        assert quaternion_to_yaw(x, y, z, w) == pytest.approx(theta)


def test_reset():
    o = make_odo()
    o.update([330, 330, 330, 330], gyro_z=0.0, dt=0.02)
    o.reset()
    assert o.pose.x == 0.0 and o.pose.theta == 0.0
