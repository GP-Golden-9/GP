import pytest

from gpcore.config import ConfigError, get_path, load_config, load_robot_config

VALID_ROBOT_YAML = """
robot: {id: robot2, name: Beta, host: robot2.local}
zmq: {telemetry: 5556, map: 5557, cmd: 5558, health: 5559, video: 5560}
drive:
  wheel_diameter_m: 0.065
  ticks_per_rev: 330
"""


def test_load_valid(tmp_path):
    p = tmp_path / 'robot2.yaml'
    p.write_text(VALID_ROBOT_YAML)
    cfg = load_robot_config(str(p))
    assert cfg['robot']['id'] == 'robot2'
    assert get_path(cfg, 'drive.wheel_diameter_m') == 0.065


def test_missing_file():
    with pytest.raises(ConfigError, match='not found'):
        load_config('definitely/not/here.yaml')


def test_invalid_yaml(tmp_path):
    p = tmp_path / 'bad.yaml'
    p.write_text('robot: {id: [unclosed')
    with pytest.raises(ConfigError, match='invalid YAML'):
        load_config(str(p))


def test_non_mapping_top_level(tmp_path):
    p = tmp_path / 'list.yaml'
    p.write_text('- just\n- a list\n')
    with pytest.raises(ConfigError, match='mapping'):
        load_config(str(p))


def test_missing_required_key_named_in_error(tmp_path):
    p = tmp_path / 'robot2.yaml'
    p.write_text("robot: {id: robot2, name: Beta, host: x}\nzmq: {telemetry: 1}\n")
    with pytest.raises(ConfigError, match='zmq.map'):
        load_robot_config(str(p))


def test_get_path_default_and_error():
    cfg = {'a': {'b': 1}}
    assert get_path(cfg, 'a.b') == 1
    assert get_path(cfg, 'a.zz', default=7) == 7
    with pytest.raises(ConfigError, match="a.zz"):
        get_path(cfg, 'a.zz')
