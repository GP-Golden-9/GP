# GP — Swarm Emergency Robotics (Graduation Project)

Three specialized robots + one operator console for emergency
exploration, intervention and inspection:

| Robot | Role | Brain | Senses / acts |
|---|---|---|---|
| **Robot 1 "Alpha"** — Mapper | explores & builds the shared map | Pi 4 (8 GB) + Arduino Mega | RPLidar A1 → SLAM (slam_toolbox), autonomous wall-follow explorer |
| **Robot 2 "Beta"** — Intervener | teleoperated intervention | Pi 3B+ + Arduino Mega | USB camera (fire detection on the laptop), encoders + GY-87 IMU odometry, click-to-navigate, **water pump + arm servo** (firmware v5) |
| **Robot 3 "Gamma"** — Inspector | gas monitoring | ESP32 | MQ-5 gas + ultrasonic + MPU6050, latched buzzer alarm, HTTP API |

Operator side: **`dashboard_qt/` (PySide6 console)** — live video with YOLO
fire detection (crash-isolated child process), RViz-style map with
click-to-goal, hold-to-drive controls, pump/servo cluster, latched E-stop,
per-stream freshness badges, health vitals, incident log.

## Architecture (one paragraph)

Each Pi is a self-contained ROS 2 Humble island (`ROS_LOCALHOST_ONLY=1`,
distinct `ROS_DOMAIN_ID`) — **no DDS over WiFi**. A per-robot *gateway*
(`gateway/gateway_node.py`) is the only network doorway, speaking a
versioned msgpack/ZMQ protocol (`docs/protocol.md`): telemetry 5556, map
5557, ACKed commands 5558, health 5559, video 5560. Safety is layered:
10 Hz drive stream from the console → gateway deadman (0.6 s) → bridge
deadman (0.8 s) → firmware watchdog (1 s), plus an end-to-end latched
e-stop down to the firmware (`E`/`X`).

## Repository map

```
common/gpcore/      shared ROS-free core: protocol, Mega serial parsers,
                    diff-drive kinematics, goto controller, config, logging
gateway/            robot-side ZMQ gateway (+ ROS-free zmq_server, testable)
robots/robot{1,2}/  launch files (respawn, run_id), preflight, scan_watchdog,
                    camera_pub (ROS-free video unit)
dashboard_qt/       PySide6 operator console  ·  --sim = zero-hardware mode
dashboard/          LEGACY NiceGUI dashboard (kept runnable during migration)
navigation/         robot bridges, odometry, goto, explorer (ROS 2 nodes)
mapping/            slam_toolbox launch + tuned mapper.yaml
firmware/           robot2 v5 (pump/servo/e-stop) · robot3 v2 (watchdog/reconnect)
arduino/            original firmware generations (v4 = rollback for robot2)
classification/     tcp_rasp_zmq.py — legacy camera streamer still used by tmux path
rasp_cmd/           tmux fallback launchers (DDS-isolated, restart loops)
systemd/            units + udev serial rules + installer
config/             ALL ports/hosts/calibration in one place (fleet + per robot)
tools/              baseline_probe, soak_test (KPI gates), collect_logs
tests/              68 pytest tests — run on Windows and the Pis
docs/               protocol spec, demo runbook, bench checklist, baselines
attic/              dead experiments, kept for reference
```

## Quick start

**Operator console (Windows laptop):**
```bash
pip install -r dashboard_qt/requirements.txt
pip install -e common
python dashboard_qt/main.py            # real robots
python dashboard_qt/main.py --sim      # zero hardware: simulated arena+video
```
(Optional AI overlay: `pip install ultralytics torch`; without them the
console runs with an explicit "RAW (AI OFF)" badge.)

**Robots (each Pi, one-time):**
```bash
cd ~/GP && pip3 install -e common pyzmq
./systemd/install_systemd.sh robot1    # or robot2 — installs udev rules too
sudo systemctl start gp-robot1         # preflight gates the start
```
Fallback at any time: `sudo systemctl disable --now 'gp-*'` then
`./rasp_cmd/robotN.sh` (tmux stack, still maintained).

**Robot 3:** flash `firmware/robot3_controller_v2/` (copy
`config_secrets.h.template` → `config_secrets.h` with your WiFi first).

## Testing & verification

```bash
python -m pytest tests/                          # 68 tests, no hardware
python dashboard_qt/main.py --sim                # full console vs simulator
python tools/soak_test.py --host robot2.local --minutes 30   # KPI gates
python tools/baseline_probe.py --host robot2.local           # legacy-path probe
```
Firmware v5 must pass `docs/bench_robot2_v5.md` (incl. the power gate)
before it goes on the robot. Demo procedure: `docs/runbook_demo_day.md`.

## YOLO models

`models/*.pt` are auto-discovered by the console's model selector.
`yolov8n-fire.pt` (default) is a dual-head model using the custom
`ConcatHead` layer — defined in `dashboard_qt/inference/concat_head.py` and
monkey-patched into ultralytics inside the inference child process only.
