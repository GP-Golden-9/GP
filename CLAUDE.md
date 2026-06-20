# GP — Multi-Robot Emergency/Inspection Swarm

Claude Code auto-loads this file on any machine that opens this repo. It is
the portable project memory: clone the repo on a new device, run `claude`
inside it, and Claude starts with the full picture below. **No secrets live
here** — see "Credentials" at the end.

CS graduation project (Arabic-speaking team). Three robots + a Windows
PySide6 operator console, talking over a dedicated LAN router (no internet
required for operation).

**New teammate?** `docs/using_claude_code.md` = how to drive this CLI on the
project; `docs/field_fixes_and_runbook_2026-06-18.md` = every fix + how to run
the demo.

> **SESSION START — restore chat history.** At the **start of a new session**,
> ASK the user: *"Do you have an old Claude session zip to restore? If so, give
> me the path."* If they provide a path, run
> `pwsh tools/claude_sessions.ps1 import -Zip <path>` (or
> `./tools/claude_sessions.sh import <path>`), then tell them to **exit and run
> `claude --resume`** to open the old chat (it can't be loaded into the running
> session). If they say no / it's the same machine, skip it and carry on. Don't
> ask more than once per session. Details: `docs/using_claude_code.md` §6.

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

## Current hardware state & open tickets (2026-06-20)

> Full session fix list + runbook: **`docs/field_fixes_and_runbook_2026-06-18.md`**.
> SCAN-stuck fixes (2026-06-20, commit 63df654): `goal_fusion` gates forward on
> the OPEN ultrasonic side so Beta no longer freezes at doorways/one-side walls
> (REAL Beta — bundle-deploy `robot2_local_nav`); mission counts TURNING toward
> a waypoint as progress (no false "stuck" on slow auto turns); SCAN plans A*
> between coverage waypoints (through doorways). Sim made faithful (real-time
> physics pacing + ported corner-escape ladder).
> Operator autonomy (2026-06-20, console-only): SCAN is now PLAN → review/edit →
> START (draggable numbered nodes, EDIT PATH, A* re-route around walls, no
> straight-through), manual ASSIST pauses/resumes a run, decisive turn-around,
> wide-open routing + drift tolerance. Forward/back oscillation next to a wall
> is the on-robot escape ladder (`robot2_local_nav`), tune there with NAV LOG.
> Recent: serial-lag wall-crash fixed (bridge drains to latest packet); yaw
> integrated in the bridge at 50 Hz + scale-cal `gyro_scale_correction 1.0304`
> + encoder-heading fallback on gyro dropout; stall-disarm anti-lockup
> (`drive.stall_disarm_s 3.0`) + commit-forward escape; boot ~3min→~1min
> (dropped `network-online.target`); odometry on the laptop
> (`dashboard_qt/state/local_odom.py`), Beta runs one reactive node
> `robot2_local_nav.py`. Console **AUTONOMY** dock: **SCAN AREA** (coverage of
> Alpha's map, `ui/map/coverage.py`) + **GO TO FIRE -> PUMP 5s -> RETURN**,
> both real, loose progress-based path following. LIVE FEED falls back to
> Beta's camera when on Alpha.

- **Beta ultrasonics**: WIRED (2 front HC-SR04, LEFT trig=30/echo=31,
  RIGHT trig=32/echo=33, 5 V), operator tilted them slightly outward for FOV.
  Forward-stop guard + graceful slowdown live.
- **Beta GY-87 IMU**: ⚠ intermittently DROPS OFF the I2C bus — **rewire
  VCC 3.3 V→5 V + resolder (top demo ticket)**. When it drops, firmware streams
  FROZEN non-zero gyro values → heading freezes → map arrow goes static. A
  power-cycle revives it. Heading needs the gyro (encoder-only fallback offered,
  not yet built).
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

## 2026-06-20 session — autonomy hardening (problems → fixes)

Read this before touching SCAN / Beta navigation. Full detail +
how-to-run is in `docs/field_fixes_and_runbook_2026-06-18.md`. Commits:
`63df654`, `ad412be`, `1b819d6` (+ doc commits). **The one ROBOT-side fix
(#2) is deployed to Beta; everything else is console-only.**

The whole session traced ONE complaint — "SCAN stops with nothing in front of
it" — down through several layers, then added operator controls. Root tool:
a faithful `--sim` + a headless ZMQ operator that drives the real fake-gateway.

**Navigation root causes (fixes that change how Beta moves):**
1. **SCAN didn't plan around interior walls** — it fed the raw coverage
   skeleton to the bias-follower, which aimed Beta straight at walls. FIX:
   `_route_through` runs A* between coverage nodes (through doorways).
   Console: `dashboard_qt/ui/main_window.py`.
2. **`goal_fusion` froze Beta at one-sided walls / doorways** (forward speed
   gated by the NEARER wall → potential-field local minimum). FIX: gate forward
   on the MORE-OPEN side (`min` closeness); stop only when BOTH sides blocked.
   **ROBOT-side** (`navigation/local_nav_math.py`, used by `robot2_local_nav`)
   — DEPLOYED to Beta; redeploy if you change it (bundle + restart gp-robot2).
3. **"Stuck" was distance-only** so a slow rotate-then-drive turn read as
   stuck. FIX: count TURNING toward the waypoint as progress too
   (`dashboard_qt/ui/mission.py`).
4. **Path drawn straight THROUGH objects after deleting a node** — an earlier
   "drive un-routable nodes directly" fallback plowed through walls. FIX:
   reverted — A* routes around obstacles; a walled-off node is DROPPED, never
   straight-lined. The robot's OWN drifted pose is handled in `plan_path`
   (frees a disc around Beta's cell) so the first leg still plans.
5. **Won't turn around to a behind node (rocks / inches back & forth)** — the
   ±π heading wrap flipped the turn sign. FIX: decisive turn-commit — pick one
   spin direction past ~80° and hold it (no driving) until facing the goal
   (`mission.py`).
6. **Routes hugged walls** → planner now prefers the CENTRE of open space
   (4 soft-cost rings, `dashboard_qt/ui/map/planner.py`).
7. **Drift tolerance** (Beta is lidar-less → pose drifts → map can read it
   "inside a wall" and refuse to move): planner frees a disc around the robot
   cell + wider goal snap; on a true NO PATH, Beta heads for a single goal
   REACTIVELY (ultrasonics = reality, a real wall still stops it at 25 cm).

**Sim faithfulness (no robot impact, but needed to trust `--sim`):** the fake
gateway paced physics to the wall clock (was 2-3× real-time → control
oscillation) and got `robot2_local_nav`'s reverse→pivot→commit corner-escape
ported in (`dashboard_qt/sim/fake_gateway.py`).

**Operator controls (console-only):** SCAN is now **PLAN → review/edit →
START** (it does NOT move on SCAN AREA); the suggested path shows as draggable
NUMBERED nodes (green START / orange END) — **EDIT PATH**: drag=move,
click=add, right-click=remove, A* re-routes live; **manual ASSIST** — nudging
the joystick mid-run PAUSES the mission and RESUMES from the new pose on
release (no cancel).

**Still true / open:**
- The fundamental limit is **Beta's lidar-less odometry drift** — these
  changes TOLERATE it, they don't remove it. A periodic **SET POSE** re-align
  during a long run is the practical mitigation (no scan-match hardware).
- Residual **forward/back oscillation right next to a wall** lives in the
  ON-ROBOT escape ladder (`robot2_local_nav`), not the console — grab the NAV
  LOG during it and tune the ladder there, then redeploy to Beta.
- GY-87 IMU 5 V rewire is still the #1 hardware ticket (above).

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
