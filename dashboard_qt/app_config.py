"""Load fleet + robot configuration for the operator console."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from gpcore.config import get_path, load_config

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CONFIG_DIR = os.path.join(REPO, 'config')


@dataclass
class RobotProfile:
    id: str
    name: str
    host: str
    kind: str                      # 'ros' | 'esp32'
    zmq: Dict[str, int] = field(default_factory=dict)
    legacy_video_port: int = 0
    http: Dict = field(default_factory=dict)
    gas: Dict = field(default_factory=dict)
    footprint: Dict = field(default_factory=dict)

    @property
    def is_esp32(self) -> bool:
        return self.kind == 'esp32'

    @property
    def plan_hard_radius_m(self) -> float | None:
        """Half-width + safety margin → A* hard inflation, or None for the
        planner default when the robot has no measured footprint."""
        hw = self.footprint.get('half_width_m')
        return (hw + 0.05) if hw else None

    @property
    def plan_soft_extra_m(self) -> float:
        """Extra soft-cost reach out to the circumscribed radius so the
        long rear overhang is priced away from walls without hard-blocking
        doorways the body actually fits through."""
        hw = self.footprint.get('half_width_m')
        rear = self.footprint.get('rear_extent_m')
        if not hw or not rear:
            return 0.0
        circumscribed = (hw ** 2 + rear ** 2) ** 0.5
        hard = hw + 0.05
        return max(0.0, circumscribed - hard)


@dataclass
class DashboardPrefs:
    drive_stream_hz: float = 10.0
    speed_min: float = 0.10
    speed_max: float = 0.30
    speed_default: float = 0.15
    turn_rate: float = 0.5
    models_dir: str = os.path.join(REPO, 'models')
    default_model: str = 'fire.pt'
    fire_conf_min: float = 0.25


@dataclass
class AppConfig:
    robots: List[RobotProfile]
    prefs: DashboardPrefs
    default_robot: str

    def profile(self, robot_id: str) -> RobotProfile:
        for r in self.robots:
            if r.id == robot_id:
                return r
        raise KeyError(robot_id)


def load_app_config(fleet_path: str | None = None) -> AppConfig:
    fleet_path = fleet_path or os.path.join(CONFIG_DIR, 'fleet.yaml')
    fleet = load_config(fleet_path)
    cfg_dir = os.path.dirname(os.path.abspath(fleet_path))

    robots: List[RobotProfile] = []
    for entry in get_path(fleet, 'fleet.robots'):
        rc = load_config(os.path.join(cfg_dir, entry['config']))
        robots.append(RobotProfile(
            id=get_path(rc, 'robot.id'),
            name=get_path(rc, 'robot.name'),
            host=get_path(rc, 'robot.host'),
            kind=get_path(rc, 'robot.kind', 'ros'),
            zmq=rc.get('zmq', {}),
            legacy_video_port=get_path(rc, 'camera.legacy_port', 0),
            http=rc.get('http', {}),
            gas=rc.get('gas', {}),
            footprint=rc.get('footprint', {}),
        ))

    d = fleet.get('dashboard', {})
    models_dir = d.get('models_dir', '../models')
    if not os.path.isabs(models_dir):
        models_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), models_dir))
    prefs = DashboardPrefs(
        drive_stream_hz=d.get('drive_stream_hz', 10),
        speed_min=d.get('speed_min_mps', 0.10),
        speed_max=d.get('speed_max_mps', 0.30),
        speed_default=d.get('speed_default_mps', 0.15),
        turn_rate=d.get('turn_rate_rps', 0.5),
        models_dir=models_dir,
        default_model=d.get('default_model', 'fire.pt'),
        fire_conf_min=d.get('fire_conf_min', 0.25),
    )
    return AppConfig(robots=robots, prefs=prefs,
                     default_robot=get_path(fleet, 'fleet.default_robot',
                                            robots[0].id if robots else ''))
