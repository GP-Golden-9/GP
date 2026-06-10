"""YAML config loading that fails loudly and early.

A typo'd key on a robot must abort launch with a precise message — not
surface as a mystery default three subsystems later.
"""

from __future__ import annotations

from typing import Any, Iterable

import yaml


class ConfigError(Exception):
    pass


# Keys every config/robotN.yaml must provide (dotted paths):
ROBOT_REQUIRED_KEYS = (
    'robot.id',
    'robot.name',
    'robot.host',
    'zmq.telemetry',
    'zmq.map',
    'zmq.cmd',
    'zmq.health',
    'zmq.video',
)


def load_config(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f'config file not found: {path}')
    except yaml.YAMLError as exc:
        raise ConfigError(f'invalid YAML in {path}: {exc}')
    if not isinstance(data, dict):
        raise ConfigError(f'{path}: top level must be a mapping, got '
                          f'{type(data).__name__}')
    return data


def get_path(cfg: dict, dotted: str, default: Any = ..., *, source: str = 'config'):
    """``get_path(cfg, 'drive.wheel_diameter_m')`` with a precise error."""
    node: Any = cfg
    for part in dotted.split('.'):
        if not isinstance(node, dict) or part not in node:
            if default is not ...:
                return default
            raise ConfigError(f'{source}: missing required key {dotted!r}')
        node = node[part]
    return node


def require_keys(cfg: dict, keys: Iterable[str], *, source: str = 'config') -> None:
    missing = []
    for key in keys:
        try:
            get_path(cfg, key, source=source)
        except ConfigError:
            missing.append(key)
    if missing:
        raise ConfigError(f'{source}: missing required keys: {missing}')


def load_robot_config(path: str) -> dict:
    cfg = load_config(path)
    require_keys(cfg, ROBOT_REQUIRED_KEYS, source=path)
    return cfg
