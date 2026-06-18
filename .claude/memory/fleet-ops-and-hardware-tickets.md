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

**SESSION 2026-06-16..18 (full fix list → docs/field_fixes_and_runbook_2026-06-18.md):**
- Wall-crash from serial lag: bridge serial reader now DRAINS to the latest
  D: packet (was FIFO → kernel buffer filled → seconds-stale readings).
- Odometry moved OFF the Pi to the laptop (state/local_odom.py); Pi load
  ~3.7→1.3. Launch runs ONE reactive node (robot2_local_nav.py) replacing
  robot2_goto + robot2_autonomous; laptop streams /cmd_vel_bias.
- Yaw: integrated IN THE BRIDGE at 50 Hz using the Mega ts timestamp, shipped
  in IMU orientation, gateway forwards. Scale-cal gyro_scale_correction=1.0304
  (tools/yaw_calib.py). Smooth tuning: turn≤0.25, lin≤0.12, ramp 600→300.
- STALL-DISARM (the ~30s lock-up = undervoltage cascade): bridge kills motors
  after drive.stall_disarm_s (3.0s) frozen, blocks same dir cooldown (2s),
  allows escape, publishes /stall; local_nav reverses + reorients, gives up
  (STUCK) after 4/20s.
- Dashboard FIRE TEST tab (ui/fire_panel.py) replaced master/slave sim
  (master_mission.py, mission_panel.py, live_handoff.py DELETED): place fire →
  Beta autonomous-navigates (A* over Alpha map + ultrasonic dodge).
- Boot ~3min→~1min: dropped network-online.target from the units.

⚠ **GY-87 IMU dropout CONFIRMED LIVE 2026-06-18:** gyro fell off I2C, firmware
streamed FROZEN non-zero values (all-zero dead-detect misses it), heading
froze, map arrow static. Power-cycle revived it (|gz| 1.65 rad/s, heading
tracked 360°). **#1 ticket: rewire GY-87 VCC 3.3V→5V + resolder** — it WILL
drop again. Offered/not-built: encoder-heading fallback. The 2 front
ultrasonics were tilted slightly outward by the operator (kept as-is; advised
re-mount lower + add fixed sensors over a pan-servo).

⚠ Alpha NOT touched this session — FIRE TEST needs its map; verify its DDS
config adopted on next restart. Repo at 61515a9, all pushed, both robots
deployed (Beta via git bundle over the LAN — its origin/main is stale, base
the bundle on Beta's actual HEAD; scp to ~ not /tmp = 50MB tmpfs).

**AUTONOMY DEMO BUILD (2026-06-19, repo at 061feff, all pushed; full
description in docs/field_fixes_and_runbook_2026-06-18.md):** Console AUTONOMY
dock (right side, tabbed w/ OPERATIONS — map stays visible) with two
independent REAL Beta actions:
- SCAN AREA: coverage-path generator (`dashboard_qt/ui/map/coverage.py`,
  boustrophedon, ERODE free space by clearance so no waypoint hits a wall,
  largest open run per row, UNKNOWN=blocked, CAP ~14 waypoints/auto-widen
  lanes) → Beta follows it as a reference (bias + ultrasonic deviate/merge) →
  returns to base. Reference path drawn dashed; "DEVIATING" shown on dodge.
- GO TO FIRE → PUMP 5s → RETURN: navigate to placed FIRE/PIN marker, hold +
  pump 5s, return to start. FIRE precise (no skip); SCAN loose.
- FLEXIBLE following (mission.py): skip a waypoint only on NO PROGRESS (Beta
  stops getting closer) — NOT on a fixed timer (that false-"stuck" a big map
  by skipping far-but-reachable waypoints). Give up after 4 consecutive.
- ESCAPE robustness (local_nav): reverse → pivot → COMMIT FORWARD to clear the
  obstacle before re-seeking goal (breaks pivot-in-place trap); alternates dir.
- Faster auto rotation: auto_turn_pwm 200→235, max_angular_rps 0.25→0.35.
- ENCODER-HEADING FALLBACK now BUILT (bridge): frozen-gyro signature detect →
  integrate wheel differential so driven turns keep heading through a GY-87
  dropout; auto-restores. (5V rewire + firmware MPU auto-reinit still the
  stronger fixes; auto-reinit NOT built.)
- UI: AUTONOMY widget stripped to ASCII (no emoji); LIVE FEED falls back to
  Beta's camera when active robot (Alpha) has no camera.
- Both robots ran live this session; Alpha mapped (298x150 @ 2.5cm, reaching
  console). SCAN tuning lives in _scan_area + mission.py; map quality on a
  large/irregular arena makes full coverage slow — re-map a tidier area or
  accept the coarse 14-wp sweep for the demo.
