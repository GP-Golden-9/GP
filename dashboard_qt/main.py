#!/usr/bin/env python3
"""GP Fleet Console — PySide6 operator dashboard.

    python dashboard_qt/main.py                # real robots (config/fleet.yaml)
    python dashboard_qt/main.py --sim          # zero-hardware: spawns the fake
                                               # gateway and targets localhost
    python dashboard_qt/main.py --no-ai        # skip YOLO even if installed

"""

from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)                      # views/, transport/, state/, …
sys.path.insert(0, os.path.join(REPO, 'common'))  # gpcore without install

from PySide6.QtWidgets import QApplication    # noqa: E402

from app_config import load_app_config        # noqa: E402
from gpcore.logging_setup import new_run_id, setup_logging  # noqa: E402


SIM_ROBOT2_PORT_OFFSET = 10     # robot2's sim shares localhost with robot1's


def start_sim() -> None:
    """THREE independent simulated robots, like the real fleet:

        robot1  mapper — publishes map+scan, wanders autonomously
        robot2  rover  — camera (+ fire imagery), executes goals/teleop
        robot3  ESP32  — HTTP inspector with gas readings + leak event
    """
    gateway = os.path.join(HERE, 'sim', 'fake_gateway.py')

    def spawn(cmd):
        proc = subprocess.Popen(cmd, cwd=REPO)
        atexit.register(lambda: proc.poll() is None and proc.terminate())

    spawn([sys.executable, gateway, '--robot-id', 'robot1', '--role', 'mapper',
           '--start-x', '-1.3', '--start-y', '1.3'])

    rover = [sys.executable, gateway, '--robot-id', 'robot2', '--role', 'rover',
             '--port-offset', str(SIM_ROBOT2_PORT_OFFSET),
             '--start-x', '-1.0', '--start-y', '-1.0']
    # real fire photo (gitignored test asset) → genuine detections in sim
    fire_asset = os.path.join(HERE, 'sim', 'assets', 'fire_crop.jpg')
    if os.path.isfile(fire_asset):
        rover += ['--fire-image', fire_asset]
    spawn(rover)

    spawn([sys.executable, os.path.join(HERE, 'sim', 'fake_esp32.py')])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--sim', action='store_true',
                    help='spawn sim/fake_gateway.py and target localhost')
    ap.add_argument('--config', default=None, help='fleet.yaml path')
    ap.add_argument('--no-ai', action='store_true', help='disable YOLO worker')
    ap.add_argument('--exit-after', type=float, default=0,
                    help='quit after N seconds (smoke tests / soak automation)')
    ap.add_argument('--drill-after', type=float, default=0,
                    help='trigger a FIRE alert drill after N seconds '
                         '(same as pressing F9 — for rehearsals and tests)')
    args = ap.parse_args()

    run_id = os.environ.get('GP_RUN_ID') or new_run_id()
    log = setup_logging('dashboard', run_id=run_id)

    cfg = load_app_config(args.config)
    if args.sim:
        start_sim()
        for prof in cfg.robots:
            prof.host = '127.0.0.1'
            if prof.id == 'robot2':       # rover lives on offset ports in sim
                prof.zmq = {k: (v + SIM_ROBOT2_PORT_OFFSET if v else 0)
                            for k, v in prof.zmq.items()}
        cfg.default_robot = 'robot2'
        log.info('sim mode: 3 independent robots on 127.0.0.1')

    yolo = None
    if not args.no_ai:
        model_path = os.path.join(cfg.prefs.models_dir, cfg.prefs.default_model)
        if os.path.isfile(model_path):
            from inference.yolo_worker import YoloManager
            yolo = YoloManager(model_path)
            yolo.start()
        else:
            log.warning('default model missing — AI OFF',
                        extra={'kv': {'path': model_path}})

    app = QApplication(sys.argv)
    app.setStyle('Fusion')                 # respects stylesheets consistently
    from ui import theme
    app.setStyleSheet(theme.QSS)

    from ui.main_window import MainWindow
    win = MainWindow(cfg, yolo_manager=yolo, run_id=run_id)
    theme.enable_dark_titlebar(win)
    win.showMaximized()
    from PySide6.QtCore import QTimer
    if args.exit_after:
        QTimer.singleShot(int(args.exit_after * 1000), app.quit)
    if args.drill_after:
        QTimer.singleShot(int(args.drill_after * 1000),
                          lambda: win.alerts.drill('FIRE'))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
