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
    user: str = 'muc'              # SSH user for diagnostics actions
    zmq: Dict[str, int] = field(default_factory=dict)
    legacy_video_port: int = 0
    http: Dict = field(default_factory=dict)
    gas: Dict = field(default_factory=dict)
    footprint: Dict = field(default_factory=dict)
    drive: Dict = field(default_factory=dict)   # wheel kinematics for laptop odom
    ultrasonic: Dict = field(default_factory=dict)   # front HC-SR04 config
    goto: Dict = field(default_factory=dict)    # goto gains for laptop heading bias
    odom: Dict = field(default_factory=dict)    # encoderless dead-reckoning (Gamma)

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
    # Primary = a CLEAN COCO net for person/dog/cat. fire.pt's COCO classes
    # are wrecked by its fire fine-tune (it scored 0% on a person a clean
    # net got 92% on), so it is demoted to the secondary fire-ONLY model.
    default_model: str = 'yolov8s.pt'
    fire_model: str = 'fire.pt'
    fire_conf_min: float = 0.25
    # Classes the console detects + projects onto the shared map, and the
    # per-class confidence floor for placing a marker. fire.pt is an
    # 81-class model (80 COCO + 'Fire'); we restrict to these so the video
    # and map aren't flooded with chairs/cars. 'fire' covers fire/smoke/flame.
    detect_classes: List[str] = field(
        default_factory=lambda: ['person', 'dog', 'cat', 'fire'])
    detect_conf: Dict[str, float] = field(default_factory=lambda: {
        'person': 0.70, 'dog': 0.60, 'cat': 0.60, 'fire': 0.60})
    # Inference quality knobs. imgsz: the model's internal working
    # resolution — higher resolves small/distant targets that 640 misses
    # (cost grows ~quadratically). augment: test-time augmentation (multi-
    # scale + flip) — a few extra mAP for ~2-3x the latency. Both are
    # laptop-side; dial down if the live feed gets sluggish. 640 benchmarked
    # FASTER and MORE confident than 960 when the subject fills the frame
    # (the common case for a ground robot); raise toward 960 only for small
    # distant targets.
    detect_imgsz: int = 640
    detect_augment: bool = False
    # Classical color/shape detector for a PRINTED/animated flame prop the
    # real-fire net can't see (demo aid). Set false where only genuine fire
    # should alarm.
    detect_fire_prop: bool = True

    @property
    def detect_conf_base(self) -> float:
        """Worker-side floor: lowest per-class threshold, so the annotated
        video shows a box the moment any wanted class crosses ITS floor;
        the stricter per-class gate is applied before a map marker drops."""
        return min(self.detect_conf.values()) if self.detect_conf else 0.25

    @property
    def model_path(self) -> str:
        return os.path.join(self.models_dir, self.default_model)

    @property
    def fire_model_path(self) -> str | None:
        """Full path to the secondary fire model, or None if it's missing
        or detection doesn't want fire at all."""
        if not self.fire_model or 'fire' not in self.detect_classes:
            return None
        p = os.path.join(self.models_dir, self.fire_model)
        return p if os.path.isfile(p) else None


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
            user=get_path(rc, 'robot.user', 'muc'),
            zmq=rc.get('zmq', {}),
            legacy_video_port=get_path(rc, 'camera.legacy_port', 0),
            http=rc.get('http', {}),
            gas=rc.get('gas', {}),
            footprint=rc.get('footprint', {}),
            drive=rc.get('drive', {}),
            ultrasonic=rc.get('ultrasonic', {}),
            goto=rc.get('goto', {}),
            odom=rc.get('odom', {}),
        ))

    d = fleet.get('dashboard', {})
    models_dir = d.get('models_dir', '../models')
    if not os.path.isabs(models_dir):
        models_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), models_dir))
    det = d.get('detect', {}) or {}
    prefs = DashboardPrefs(
        drive_stream_hz=d.get('drive_stream_hz', 10),
        speed_min=d.get('speed_min_mps', 0.10),
        speed_max=d.get('speed_max_mps', 0.30),
        speed_default=d.get('speed_default_mps', 0.15),
        turn_rate=d.get('turn_rate_rps', 0.5),
        models_dir=models_dir,
        default_model=d.get('default_model', 'yolov8s.pt'),
        fire_model=d.get('fire_model', 'fire.pt'),
        fire_conf_min=d.get('fire_conf_min', 0.25),
        detect_classes=det.get('classes', ['person', 'dog', 'cat', 'fire']),
        detect_conf=det.get('conf', {'person': 0.70, 'dog': 0.60,
                                     'cat': 0.60, 'fire': 0.60}),
        detect_imgsz=det.get('imgsz', 640),
        detect_augment=det.get('augment', False),
        detect_fire_prop=det.get('fire_prop_detector', True),
    )
    return AppConfig(robots=robots, prefs=prefs,
                     default_robot=get_path(fleet, 'fleet.default_robot',
                                            robots[0].id if robots else ''))
