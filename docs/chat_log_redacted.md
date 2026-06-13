# GP — Claude Code engineering log (redacted)

A human-readable, **secret-scrubbed** record of the Claude Code sessions on
this project. It's a curated reconstruction (organized by topic), not a
byte-for-byte transcript dump — the raw `.jsonl` is kept off git because it
contains plaintext credentials.

All secrets are placeholders:
- `<REDACTED: SSH password>` — robots' SSH password (the SSH *user* is `muc`,
  which is already in `config/*.yaml`)
- `<REDACTED: WiFi SSID>` / `<REDACTED: WiFi password>`
- `<REDACTED: OTA password>` — ESP32 OTA (real value in `config_secrets.h`)

> ⚠ The WiFi password leaked into this repo's **initial git commit** and the
> SSH/WiFi passwords were typed into chat. Rotate both when possible.

---

## Session 1 — fleet bring-up, mapping, navigation, the DDS hunt

**Hand-off.** Took over the team's troubleshooting after reviewing their recent
commits: video drops, SLAM map vanishing, telemetry desync, node crashes,
LiDAR not spinning.

**robot1 "Alpha" (Pi 4, RPLIDAR A1M8).** Connected over SSH (user `muc`,
password `<REDACTED: SSH password>`; installed key auth), pulled commits,
restarted, verified the LiDAR, ran the dashboard.

**Map quality.** Map looked frozen/smeared and the robot wouldn't drive from
WASD/arrows. Root work:
- Added **rf2o laser odometry** (built from source in `~/ros2_ws`) so SLAM gets
  real motion input instead of an identity TF — the community fix for
  doubled/smeared A1M8 walls. SLAM at 0.025 m.
- Rebuilt the map rendering in the PySide6 console to an RViz-grade gradient
  palette with pose smoothing.
- Fixed orientation (arrow pointed backward — laser zero-axis faces rear,
  yaw π), set a precise footprint (40 × 30 cm; lidar 5 cm from front, 10 cm
  from sides), costmap inflation, and "foolproof" obstacle avoidance.
- Navigation: `robot1_goto` with map→base_link TF pose, scan collision guard
  (corridor + hysteresis), self-occlusion boot mask, arc-turn fallback, guarded
  reverse, probing rotation — so it can turn and back out of tight spaces, not
  just go forward.

**robot2 "Beta" (Pi 3B+ + Arduino Mega).** Set up over SSH (user `muc`,
password `<REDACTED: SSH password>`), fixed errors, tested drive + camera.
- Turning was jerky ("motors suffer") → drive-biased arbitration + a turn-PWM
  torque floor. Verified odometry computes distance/heading and uses the IMU
  gyro for yaw.
- Measured kinematics: 85 mm wheels (code had 65 — a 24 % distance error),
  408 ticks/rev (25GA370: 12 PPR × 34:1), track ≈ 0.225 m.
- "IMU completely dead, brand new" → traced to the GY-87 on a marginal 3.3 V
  feed (module wants 5 V into its LDO). Firmware tolerates an all-zero IMU and
  falls back to encoder-only odometry, auto-restoring when it recovers.

**Fire detection.** Raised the audible-alarm gate to 0.80 (`fleet.yaml`); the
model reads low on real fire, so the alarm is drill-only (F9) until a better
model — the detections table still shows everything. Confirmed simultaneous
multi-robot operation.

**The power saga (robot2).** "Frozen map, huge delay, won't move." Iterated:
1000 µF caps both ends, re-gauged USB cable, raised the buck while measuring
**at the Pi's GPIO pins under load** — buck terminals 5.52 V → pins 5.05 V.
Lesson: the 5.25 V ceiling applies at the *pins*, not the buck; ~0.4–0.5 V is
lost in the cable/connector/polyfuse.

**The real root cause (took three wrong theories).** "Gateway ACKs but the
robot never moves," at variable times. Wrong theories: SHM crash debris,
discovery-lease expiry, USB serial re-enumeration (each restart "cured" all of
them, masking the truth). **Actual cause: `ROS_LOCALHOST_ONLY=1`'s interface
tracking silently kills ALL local DDS delivery whenever a flaky wlan changes
state.** Alpha was immune (stable radio). **Fix that held:** move localhost
isolation to the TRANSPORT — `interfaceWhiteList 127.0.0.1` in
`config/fastdds_udp_only.xml`, `ROS_LOCALHOST_ONLY=0` in the launch files, a
localhost discovery server, distinct domains. Verified by a 6-minute endurance
watch and live driving 1800+ encoder ticks. (Note: `ros2` CLI is blind in
discovery-server mode on Humble — debug via bridge arrival logs + gateway
freshness ages.)

**Console fleet ops.** Diagnostics tab lifecycle (PING/STATUS/RESTART/STOP/
COLLECT LOGS/REBOOT/SHUTDOWN over SSH as the configured user), three-state
header readiness pills (green/amber/red), lidar-idle motor hold, a >1000-line
field report. Decisions: keep a dedicated carry-along router (pure LAN, no
internet); mobile dashboard not feasible (remote-desktop instead); VBUS
backpower needs a tape/switch fix.

---

## Session 2 — pose, carpet, overshoot, robot3, ultrasonics, portability

**robot2 initial pose inverted.** Beta has no compass/lidar, so heading θ=0 is
just whichever way it faced at power-on — the arrow can start "backward." The
fix path: a plain click in **SET POSE** used to silently reset heading to 0
(facing east), recreating the symptom. Changed it so a plain click only
repositions and keeps heading; a drag sets heading. (commit `24eda95`)

**Carpet wheel-slip.** The user proposed fusing the kinematic model with
encoders. Explained that's the same signal — the gyro is the independent truth.
Implemented (commit `1b56d2d`):
- **Slip gate** in `robot2_odom`: when encoder-implied rotation disagrees with
  the gyro beyond `drive.slip_gate_rad_s`, the gyro takes heading and distance
  is discounted.
- **PWM soft-launch ramp** in `robot2_bridge`: launches ramp up instead of a
  torque kick that breaks traction.

**Overshoot + drift + stuck.** (commit `b091248`)
- "1 s commanded = 2–3 s driven" was two bugs: the console retried stale
  `cmd.drive` on ACK timeout, and the gateway executed the whole post-stall
  backlog. Fix: never retry drives/pings; gateway conflates `cmd.drive` to the
  newest in a drain.
- Odometry drift: the firmware streamed RAW gyro; the zero-rate bias was
  integrated into heading. Added auto-bias-learning while stopped, subtracted
  everywhere, heading frozen while parked.
- `robot2_goto` stuck watchdog: abandons a goal after 8 s without progress.

**robot3 "Gamma" (ESP32) flashing.** Onboard USB is dead → flash via FT232RL.
Walked through the wiring (3.3 V jumper; power the ESP from USB/5 V, FTDI does
data only; crossed TX/RX; common ground), the GPIO0/EN boot-mode sequence, and
the strapping-pin gotcha (ECHO=GPIO5, buzzer=GPIO15 — flash with peripherals
off). Captured in `docs/robot3_flashing.md`. WiFi creds (SSID
`<REDACTED: WiFi SSID>`, password `<REDACTED: WiFi password>`) go in the
gitignored `config_secrets.h`; OTA password `<REDACTED: OTA password>`.

**⚠ Over-voltage incident.** A buck accidentally set to **10 V** hit the
ESP32 + IMU + MQ gas sensor. Outcome: **ESP32 survived** (verified — enumerated
as ESP32-D0WD-V3, full 1 MB flash hash-verified; 10 V went through the VIN
regulator, not the core). IMU likely dead (LDO maxes ~6 V; I2C-scan @0x68 to
confirm; firmware tolerates it). MQ probably OK but re-check
`GAS_ALARM_THRESHOLD`. Lesson: measure the buck at the terminals before
connecting — the team's 2nd over-voltage event.

**robot3 servo + creds.** Added a slew-limited servo on GPIO19 (endpoint,
telemetry field, web-UI slider) and set the real WiFi creds in
`config_secrets.h`. (commit `0e8cf12`)

**robot2 two front ultrasonics.** Full stack (commit `b4bb3e0`):
- Firmware: two HC-SR04 on Mega pins LEFT trig=30/echo=31, RIGHT trig=32/
  echo=33, read round-robin + median-filtered, appended to the D: packet.
- Bridge: publishes `/ultrasonic/{left,right}` (Range) and hard-blocks FORWARD
  under `ultrasonic.stop_cm` (manual + auto, hysteretic).
- Goto: proportional slow-down from `slow_cm`, holds, reports BLOCKED.
- Gateway forwards ranges to the console; `ultrasonic:` section added to config.
- Sensors not yet wired at time of writing → reflash the Mega once they are.

**Cross-device portability.** Added `CLAUDE.md` (auto-loaded project context,
secret-free), a redacted memory snapshot under `.claude/memory/`, and
`docs/claude_context_sync.md`. Established that Claude Code does NOT sync chat
history across devices — `CLAUDE.md` is the portable mechanism. (commits
`d224bd1`, `6d5116e`) Confirmed the raw `~/.claude` folder should not be copied
(it holds auth tokens + a secret-laden transcript); only `claude login` +
`git clone` are needed on a new device.

---

## Standing reminders
- Rotate the WiFi password and robots' SSH access (both were exposed).
- Keep this repo private.
- Open hardware tickets: GY-87 VCC→5 V rewire; robot1 left-flank cable out of
  the lidar plane; heatsinks; VBUS backpower tape/switch; verify robot3 IMU/MQ
  after the over-voltage; wire + calibrate the robot2 ultrasonics.
