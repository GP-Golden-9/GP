# GP — Multi-Robot Emergency/Inspection Swarm

Claude Code auto-loads this file on any machine that opens this repo. It is
the portable project memory: clone the repo on a new device, run `claude`
inside it, and Claude starts with the full picture below. **No secrets live
here** — see "Credentials" at the end.

CS graduation project (Arabic-speaking team). Three robots + a Windows
PySide6 operator console, talking over a dedicated LAN router (no internet
required for operation).

---

## The fleet

| Robot | Name | Brain | Role | Key hardware |
|-------|------|-------|------|--------------|
| robot1 | **Alpha** | Pi 4 | SLAM mapper | RPLIDAR A1M8, rf2o laser odometry, no wheel encoders |
| robot2 | **Beta** | Pi 3B+ + Arduino Mega 2560 | Intervener | 4 motors + 4 quad encoders, GY-87 IMU, camera, water pump, arm servo, **2 front HC-SR04 ultrasonics**. No lidar. |
| robot3 | **Gamma** | ESP32 | Inspector | 4 motors, ultrasonic, MQ gas, MPU6050, servo. HTTP UI + ArduinoOTA. Onboard USB-serial DEAD → flash via FTDI (`docs/robot3_flashing.md`). |

ROS 2 Humble on the Pis (Alpha domain 11, Beta domain 12). Gamma is not ROS
— plain HTTP/JSON, wrapped laptop-side.

---

## Architecture

- **ROS islands + gateway.** Each Pi keeps all DDS traffic on localhost; the
  ONLY door to the network is a per-robot **gateway** (`gateway/gateway_node.py`)
  speaking a versioned **msgpack-over-ZMQ** protocol (`common/gpcore/protocol`).
  Ports per robot: 5556 telemetry, 5557 map, 5558 commands (ROUTER, ACKed),
  5559 health, 5560 video.
- **Console** = PySide6 desktop app in `dashboard_qt/` (native rendering,
  QThread transport, YOLO in a crash-isolated subprocess).
- **Supervision**: ros2 launch (`respawn=True`) wrapped in systemd units
  (`systemd/`, `Restart=always`), localhost discovery server, serial
  auto-reconnect in the bridges.

### The DDS transport fix (hard-won — do not regress)
`ROS_LOCALHOST_ONLY=1`'s interface tracking **silently kills all local DDS
delivery** whenever a flaky wlan changes state (Beta died at variable times;
Alpha was immune on a stable radio). FIX: localhost isolation moved to the
TRANSPORT — `interfaceWhiteList 127.0.0.1` in `config/fastdds_udp_only.xml`,
`ROS_LOCALHOST_ONLY=0` in the launch files, plus a localhost discovery server
(`systemd/.../gp-discovery.service`) and distinct domains. NOTE: the `ros2`
CLI is **blind in discovery-server mode** on Humble — debug with the bridge's
arrival logs and the gateway freshness ages, not `ros2 topic`.

---

## Repo layout

- `common/gpcore/` — pure-Python shared lib (protocol, serial parsers,
  kinematics, config loader). `pip install -e`.
- `config/` — **single source of truth** for calibration/ports: `fleet.yaml`,
  `robot1.yaml`, `robot2.yaml`, `robot3.yaml`, `fastdds_udp_only.xml`.
- `gateway/` — ROS↔ZMQ bridge + health aggregator.
- `navigation/` — per-robot bridges, odometry, goto controllers.
- `robots/robot{1,2}/launch/` — launch files. `mapping/` — SLAM.
- `firmware/` — `robot2_controller_v5/` (Mega), `robot3_controller_v2/` (ESP32).
- `dashboard_qt/` — the PySide6 console (`main.py` is the entry).
- `systemd/` — unit files + udev rules. `tools/` — probes/log collectors.
- `tests/` — pytest (pure-logic tests, no hardware). `docs/` — runbooks.

---

## Running it

**Console (Windows laptop):**
```
python dashboard_qt/main.py            # real robots (config/fleet.yaml)
python dashboard_qt/main.py --sim      # ZERO hardware — spawns fake robots
```
`--sim` is the way to develop/demo the console on any machine with no robots
attached. `--no-ai` disables the YOLO worker.

**Tests:** `python -m pytest tests -q`

**Deploy to a Pi** (Alpha/Beta): SSH in, `git pull`, restart the unit:
```
ssh muc@robot.local  "cd ~/GP && git pull && sudo systemctl restart gp-robot1"
ssh muc@robot2.local "cd ~/GP && git pull && sudo systemctl restart gp-robot2"
```
Robot restart **clears Alpha's live map** — never restart mid-mapping.
When Alpha's WiFi has no internet, deploy by git bundle:
`git bundle create x.bundle <robot-HEAD>..main` → scp → `git pull --ff-only x.bundle main`.

**Firmware:** Mega (Beta) flashes over USB from the Arduino IDE; ESP32 (Gamma)
flashes via FTDI then ArduinoOTA — see `docs/robot3_flashing.md`.

---

## Conventions

- Calibration/ports live in `config/*.yaml`. `robot2_odom.py` loads them via
  gpcore; the bridges mirror them into declared-parameter defaults (keep both
  in sync). Firmware `#define`s mirror the yaml too — change both.
- Commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`.
  Push only when asked.
- Files are CRLF locally; git normalizes to LF (the warnings are harmless).
- Windows console is cp1252 — keep tool output ASCII (no `──`, `→`, `✓`).
- mDNS is flaky per-call; fall back to IPs (Alpha 192.168.1.200, Beta .203).

---

## Current hardware state & open tickets (2026-06-13)

- **Beta ultrasonics**: code shipped across firmware/bridge/goto/gateway/config
  (forward-collision guard + graceful nav slowdown). Sensors NOT yet wired;
  Mega needs reflashing once they are. Pins: LEFT trig=30/echo=31,
  RIGHT trig=32/echo=33; 5 V power.
- **Beta GY-87 IMU**: intermittent on the marginal 3.3 V feed — rewire VCC→5 V.
  The odometry slip gate + gyro-bias auto-cal depend on a live IMU; with it
  dead, odometry falls back to encoder-only and drifts.
- **Gamma over-voltage (2026-06-13)**: a buck set to 10 V hit the ESP32 + IMU
  + MQ sensor. ESP32 SURVIVED (verified). IMU likely dead (I2C-scan @0x68 to
  confirm; firmware tolerates it). MQ probably OK but re-check
  `GAS_ALARM_THRESHOLD`. **Always measure the buck at the terminals before
  connecting** — this was the team's 2nd over-voltage event.
- **Alpha**: a cable/bracket sits in the lidar plane on the left flank;
  `robot1_goto` carries an exclusion pocket — tuck it away and shrink the pocket.
- Pi power: the 5.25 V ceiling is AT THE PI PINS, not the buck (≈0.4–0.5 V
  path drop). Heatsinks recommended (Beta hit 69 °C soft-cap).

---

## Credentials (NOT in git)

- Robot SSH: user `muc` on `robot.local` / `robot2.local` (key auth installed;
  ask the team for the key/password — never commit it).
- WiFi + OTA secrets live in `firmware/**/config_secrets.h`, which is
  **gitignored**. A `.template` is committed.
- ⚠ WiFi credentials leaked into OLD git history (initial commit) — rotate the
  WiFi password or keep this repo PRIVATE.
- **Never commit chat transcripts** — they contain passwords typed during
  sessions.
