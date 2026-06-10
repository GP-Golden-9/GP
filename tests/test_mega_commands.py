import pytest

from gpcore.serialproto import mega_commands as mc


def test_motion_validation():
    assert mc.motion('f') == 'F'
    with pytest.raises(ValueError):
        mc.motion('W')          # watchdog toggle must never be used as motion


def test_pwm_clamping():
    assert mc.pwm(10) == 'P80'
    assert mc.pwm(999) == 'P255'
    assert mc.pwm(180) == 'P180'


def test_tank_clamping():
    assert mc.tank(-999, 999) == 'T-255,255'
    assert mc.tank(120, -80) == 'T120,-80'


def test_pump_uses_U_not_W():
    assert mc.pump(True) == 'U1'
    assert mc.pump(False) == 'U0'


def test_servo_clamped_to_safe_range():
    assert mc.servo(999) == 'A170'
    assert mc.servo(-5) == 'A10'
    assert mc.servo(95) == 'A95'


def test_estop_letters_match_firmware():
    assert mc.estop(True) == 'E'
    assert mc.estop(False) == 'X'


@pytest.mark.parametrize('lin,ang,expected', [
    (0.0, 0.0, 'S'),
    (0.04, 0.09, 'S'),          # both inside deadband
    (0.2, 0.0, 'F'),
    (-0.2, 0.0, 'B'),
    (0.0, 0.5, 'L'),
    (0.0, -0.5, 'R'),
    (0.3, 0.2, 'F'),            # |lin| > |ang| → translate wins
    (0.1, -0.4, 'R'),           # |ang| > |lin| → rotation wins
])
def test_twist_to_motion_mirrors_bridge(lin, ang, expected):
    assert mc.twist_to_motion(lin, ang) == expected


def test_pwm_from_linear_mirrors_bridge_formula():
    # robot2_bridge: int(80 + min(|v|/max,1)*175)
    assert mc.pwm_from_linear(0.0) == 80
    assert mc.pwm_from_linear(0.5, max_linear=0.5) == 255
    assert mc.pwm_from_linear(0.25, max_linear=0.5) == int(80 + 0.5 * 175)
    assert mc.pwm_from_linear(9.9, max_linear=0.5) == 255
    assert mc.pwm_from_linear(0.3, max_linear=0) == 255
