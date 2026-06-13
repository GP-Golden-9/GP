---
name: fleet-ops-and-hardware-tickets
description: "Redacted snapshot — resolved root causes, hardware findings, and open tickets from the live field sessions. Access secrets removed."
metadata:
  type: project
---

> **Redacted for git.** SSH/WiFi/OTA credentials are NOT here — they live in
> the gitignored `firmware/**/config_secrets.h` and the team's key store.
> Deploy access is SSH (key auth) as the user configured in `config/*.yaml`.

**Robot access / deploy:**
- robot1 (Alpha/mapper, Pi 4) and robot2 (Beta/intervener, Pi 3B+): SSH to
  `robot.local` / `robot2.local`, repo at `~/GP`. User + host are in
  `config/robot{1,2}.yaml`; `install_systemd.sh` derives the user from the
  repo owner.
- robot1's WiFi often has no internet — deploy via `git bundle create` +
  `scp` + `git pull --ff-only x.bundle main` (bundle must be based on the
  robot's actual HEAD). robot2 has had working internet.

**RESOLVED (robot2 power + motion saga — verified working):**
- Under-voltage was a 0.4–0.5 V DELIVERY drop (buck→USB connector→polyfuse),
  NOT charge level. Fix: 1000 µF caps both ends + re-gauged cable + set the
  buck by measuring AT THE PI's GPIO pins UNDER LOAD (buck terminals 5.52 V →
  Pi pins 5.05 V). Rule: the 5.25 V ceiling applies at the Pi pins; the buck
  legitimately sits higher to pay path losses.
- Motors dead = ENA/ENB enable wires had come off; re-seated. Direct-serial
  test (stop the stack, send P255 + F/L, watch D: encoder deltas) is the
  definitive hardware-vs-software splitter.
- "Gateway ACKs but robot never moves" — FINAL root cause after three wrong
  theories (SHM debris, discovery lease, USB serial): **ROS_LOCALHOST_ONLY=1's
  interface tracking silently kills ALL local DDS delivery whenever a flaky
  wlan changes state** (variable death times = next WiFi event; robot1 immune
  on a stable radio; restarts cured everything equally, which masked it). FIX
  THAT HELD: localhost isolation moved to the TRANSPORT —
  interfaceWhiteList 127.0.0.1 in `config/fastdds_udp_only.xml` +
  ROS_LOCALHOST_ONLY=0 in both launch files + a localhost discovery server +
  distinct domains. Verified by a 6-min endurance watch and live driving.
  Defense-in-depth also kept: SHM purge ExecStartPre, UDP-only transport,
  discovery server, bridge serial-reconnect, /manual_cmd & /cmd_vel arrival
  logging. NOTE: the `ros2` CLI is BLIND in discovery-server mode (Humble) —
  use the bridge's arrival logs and gateway freshness ages instead.

**robot2 motion fixes (carpet / overshoot / drift):**
- Slip gate in robot2_odom: when encoder-implied rotation disagrees with the
  gyro beyond `drive.slip_gate_rad_s`, the gyro takes heading and distance is
  discounted (carpet wheel-spin no longer fakes movement).
- PWM soft-launch ramp in robot2_bridge (`drive.ramp_pwm_per_s`): launches
  from rest ramp up instead of a torque kick that breaks traction.
- Drive-replay overshoot ("1 s commanded = 2–3 s driven") was two bugs: the
  console retried stale cmd.drive on ACK timeout, and the gateway executed the
  whole post-stall backlog. Fix: never retry drives/pings; gateway conflates
  cmd.drive to the NEWEST in a drain.
- Gyro zero-rate bias was integrated raw into heading → drift at rest. Now
  auto-learned whenever wheels are stopped, subtracted everywhere, heading
  frozen while parked.
- robot2_goto: stuck watchdog abandons a goal after 8 s without progress.

**robot2 front ultrasonics (2026-06-13):** two HC-SR04 on Mega pins
LEFT trig=30/echo=31, RIGHT trig=32/echo=33 (5 V power). Firmware reads them
round-robin + median-filtered, appends to the D: packet; bridge publishes
/ultrasonic/{left,right} (Range) and hard-blocks FORWARD under
`ultrasonic.stop_cm` (manual + auto, hysteretic); goto slows from `slow_cm`.
Sensors not yet wired at time of writing → Mega needs reflash once they are.

**robot3 "Gamma" (ESP32 inspector):**
- Onboard USB-serial is DEAD — flash via FT232RL FTDI. Procedure in
  `docs/robot3_flashing.md` (3.3 V jumper, power the ESP from USB/5 V while the
  FTDI does data only, crossed TX/RX, GPIO0→GND + tap RST). Strapping-pin
  gotcha: ECHO=GPIO5 + buzzer=GPIO15 — flash with peripherals unplugged. After
  the first wired flash, use ArduinoOTA (network port `robot3`; OTA password is
  in `config_secrets.h`).
- Servo added on GPIO19 (slew-limited), plus the existing 4 motors, ultrasonic,
  MQ gas, MPU6050. No wheel encoders.
- ⚠ OVER-VOLTAGE 2026-06-13: a buck accidentally at 10 V hit ESP32 + IMU + MQ.
  ESP32 SURVIVED (verified: enumerated, full flash hash-verified — 10 V went
  through the VIN regulator, not the core). IMU survival NOT YET VERIFIED (LDO
  maxes ~6 V → likely dead; I2C-scan @0x68; firmware tolerates a dead MPU). MQ
  likely survived but heater ran 4× power → re-check `GAS_ALARM_THRESHOLD`.
  Team's 2nd over-voltage event — ALWAYS measure the buck at the terminals
  before connecting.

**Open hardware tickets:**
- robot2: GY-87 IMU intermittent on the marginal 3.3 V feed — rewire VCC→5 V +
  solder jumpers. Slip gate + bias-cal depend on a live IMU; dead → encoder-
  only odometry that drifts. Magnetometer FAIL on cold boots is the GY-87
  bypass-mode quirk (harmless, compass unused).
- robot1: a cable/bracket sits in the lidar plane on the left flank;
  robot1_goto carries an exclusion pocket — tuck it away and shrink the pocket.
- robot2: drives in a slight rightward arc open-loop (left encoders count more
  than right) — motor imbalance; goto self-corrects, manual driving veers.
- Heatsinks: a Pi hit ~69 °C (soft 1200 MHz cap) — add before demo day.
- Backpowering: the Mega backfeeds the Pi over USB; tape over VBUS or add a
  master switch; until then use the SHUTDOWN button first, then cut power.

**Fleet ops from the console:**
- Full lifecycle in the Diagnostics tab: PING / STATUS / RESTART STACK / STOP
  STACK / COLLECT LOGS / REBOOT / SHUTDOWN (SSH as the configured robot user).
- Header pills are three-state: green = heartbeat READY, amber = TCP-reachable
  but stack down, red = unreachable.
- gp-lidar-idle.service holds the A1 motor off whenever gp-robot1 is down;
  hand-off is ONE-DIRECTIONAL. LESSON: systemd `Conflicts=` is bidirectional
  and once let the holder kill a restarting stack — never pair Conflicts with a
  stop-hook that restarts the conflicting unit.
- Team uses a dedicated carry-along router (no internet — operation is pure
  LAN). Mobile dashboard isn't feasible (PySide6); remote-desktop from a phone
  to the laptop is the workaround.

**Operator decisions:** fire-alarm gate raised to 0.80 (`fleet.yaml`) after
night false alarms — the model measures low on real fire, so the audible alarm
is drill-only (F9) until a better model; the detections table still shows
everything. robot2 kinematics measured: 85 mm wheels, chassis 30×20 cm, track
~0.225 m (spin-calibrate).

**Verified working end-to-end:** robot1 click-to-navigate (arc-turn + guarded
reverse in narrow corridors), RESET MAP, rf2o + SLAM at 0.025 m; robot2 camera
+ real fire detection, teleop + encoders + odometry. Repo state advances per
commit history; SET POSE re-anchors a drifted robot on the shared map.
