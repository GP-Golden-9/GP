# Chapter 3 (System Analysis & Design) — Paste-Ready Corrections

Every corrected value below was verified against a repo file, cited inline.
Originals are quoted exactly. Physical specs not tracked in the repo are
flagged under "VERIFY WITH HARDWARE TEAM"; clear arithmetic/typo errors are
fixed in place.

---

## Table 3.1 — Main components of the Mapping Explorer Robot (Alpha)

The original table (PAGE 49-50) lists an IMU and optical encoders for Alpha
that do not exist in the configuration, plus a wrong Pi 4 clock and wrong
battery arithmetic.

| Field (row) | Old | Corrected | Evidence file |
|---|---|---|---|
| Sensor — IMU row | `MPU-9250 IMU` / `9-axis IMU (present in structure, unused on Alpha)` | **REMOVE the row.** Alpha has no IMU. The only fleet IMU is Beta's GY-87 (MPU6050 + HMC5883L + BMP180). | `config/robot1.yaml` (no `imu:` block); `config/robot2.yaml`; `CLAUDE.md` fleet table |
| Sensor — Wheel Encoders row | `Wheel Encoders` / `Optical incremental (JGB37-520, unused on Alpha)` | **REMOVE the row.** Alpha has no wheel encoders; it uses rf2o laser odometry (scan-matching). | `config/robot1.yaml` (no encoder/`ticks_per_rev`; `lidar:` + rf2o); `CLAUDE.md` ("RPLIDAR A1M8, rf2o laser odometry, no wheel encoders") |
| Processing Unit — Raspberry Pi 4 | `Quad-core ARM Cortex-A72 @ 1.8 GHz, 8 GB RAM, 64 GB microSD, Ubuntu 22.04 LTS` | `Quad-core ARM Cortex-A72 @ **1.5 GHz**, 8 GB RAM, 64 GB microSD, Ubuntu 22.04 LTS` | Pi 4B spec (1.5 GHz). RAM/SD/OS = VERIFY WITH HARDWARE TEAM (not in repo) |
| Power System — 3S LiPo | `11.1 V, 5000 mAh, ~67 Wh` | `11.1 V, 5000 mAh, **~55.5 Wh**` (11.1 V x 5.0 Ah = 55.5 Wh) | Arithmetic fix. Battery spec itself = VERIFY WITH HARDWARE TEAM (not in repo) |
| Sensor — RPLidar A1M8 | `360 deg 2D scanning, 12 m range, 5.5 Hz update rate` | KEEP (correct) | `mapping/mapper.yaml` (`max_laser_range: 12.0`, `resolution: 0.025`); 5.5 Hz confirmed |
| Real-Time Control Unit — Arduino Mega 2560 | `ATmega2560 MCU @ 16 MHz` | KEEP, but NOTE: per `CLAUDE.md`, Alpha's brain is the Pi 4 + RPLIDAR; the Mega/encoders belong to **Beta**, not Alpha. The team should confirm whether Alpha actually carries a Mega at all. | `CLAUDE.md` fleet table (Mega + encoders listed under Beta only) |

> NOTE: Table 3.1 is titled "Mapping Explorer Robot" (Alpha). Listing a Mega
> 2560 with "Motor control, encoder processing" describes **Beta's** hardware,
> not Alpha's. Recommend the team confirm Alpha's actual onboard MCU before
> publishing; if Alpha has no Mega, drop that row too.

---

## Table 3.2 — Sensor specifications

Original table on PAGE 50-51.

| Field (row) | Old | Corrected | Evidence file |
|---|---|---|---|
| MPU6050 / GY-87 — Accuracy | `±0.3°/s (gyro)` | `gyro full-scale range **±250 to ±2000 °/s** (configured ±500 °/s)` — the "±0.3°/s accuracy" figure is invented; replace with the datasheet FS range. | `firmware/robot2_controller_v5/robot2_controller_v5.ino:98` `#define MPU_GYRO_FS 1  // 0:±250 1:±500 2:±1000 3:±2000 °/s` |
| Wheel Encoders — Specification | `JGB37-520 (Alpha, unused) / 25GA370 (Beta, 408 CPR)` | `**25GA370 Hall-effect quadrature, 408 CPR — Beta only.** Alpha has no encoders (rf2o laser odometry).` | `config/robot2.yaml:59` `ticks_per_rev: 408`; `docs/design_notes/wheel_odometry_imu_fusion_25ga370_gy87.md`; `config/robot1.yaml` (none) |
| RPLidar A1M8 | `360 deg 2D scan, 12m range / ±1% / 5.5 Hz` | KEEP | `mapping/mapper.yaml` (`max_laser_range: 12.0`; "<1%" accuracy referenced in resolution comment) |
| USB Camera | `640x480 resolution at 15 fps (Beta) / 15 fps` | KEEP | `config/robot2.yaml:26-28` (`width: 640`, `height: 480`, `fps: 15`) |
| MQ-5 Gas Sensor | `LPG, natural gas, coal gas detection / Threshold-based analog trigger` | KEEP | `config/robot3.yaml:22-24` (`gas: alarm_threshold: 3000`) |
| HC-SR04 Ultrasonic | `range 2cm-400cm / ±3mm / 10 Hz` | Datasheet range OK; NOTE firmware caps echo at ~150 cm and reads each sensor ~16 Hz. Optional: change "10 Hz" to "~16 Hz (round-robin)". | `config/robot2.yaml:164` `max_cm: 150`; `firmware/...v5.ino:145` `US_TICK_MS 30UL // each sensor ~= 16 Hz` |

---

## Prose fixes

### Fix 1 — §3.5.2 Mapping Explorer (Alpha) node list

**Location:** PAGE 52-53, "Mapping Explorer Robot Nodes" (items 3 and 4).

**FIND:**
```
3. IMU Node – Publishes inertial data for orientation estimation.
4. Odometry Node – Computes wheel-based odometry information.
```

**REPLACE:**
```
3. Laser Odometry Node (rf2o) – Estimates Alpha's motion by scan-matching
   successive LiDAR scans. Alpha carries no IMU and no wheel encoders, so all
   motion estimation is laser-based.
```
(Renumber the remaining SLAM/Navigation nodes accordingly.)

**Reason+Evidence:** Alpha has no IMU and no encoders; it uses rf2o laser
odometry. `config/robot1.yaml` has no `imu:` block and no encoder params;
`mapping/mapper.yaml:29` "No wheel odometry on robot1: scan matching estimates
ALL motion." `CLAUDE.md` fleet table: "RPLIDAR A1M8, rf2o laser odometry, no
wheel encoders."

---

### Fix 2 — §3.5.2 Environmental Sensing (Gamma) node list

**Location:** PAGE 53-54, "Environmental Sensing Robot Nodes".

**FIND:**
```
1. Hardware Interface Node – Manages motors and sensor connections.
2. Gas Sensor Node – Reads data from MQ-series gas sensors and publishes
environmental measurements.
3. Odometry Node – Computes motion estimates from wheel encoders.
4. Localization Support Node – Estimates robot position using IMU and odometry data.
```

**REPLACE:**
```
Gamma is an ESP32 microcontroller running plain firmware with an embedded HTTP
server — it runs NO ROS nodes. Its firmware tasks and HTTP endpoints are:
1. Motor control endpoint – GET /control?dir=F|B|L|R|S drives the four motors.
2. Gas / telemetry endpoint – GET /telemetry returns JSON {d,g,x,y,a,rssi,
   uptime,last_cmd_age}; the MQ-5 gas reading is polled by the operations
   center at 3 Hz.
3. Local sensor task – samples the MQ-5 gas sensor and applies the alarm /
   clear thresholds onboard.
```

**Reason+Evidence:** `config/robot3.yaml:6` `kind: esp32`; line 1 comment
"ESP32, HTTP API, no ROS"; endpoints at lines 9-12 (`/control`, `/telemetry`,
`poll_hz: 3`); thresholds at lines 22-24. `CLAUDE.md`: "Gamma is not ROS —
plain HTTP/JSON, wrapped laptop-side."

---

### Fix 3 — §3.5.2 Layer 3, clarify A* runs console-side

**Location:** PAGE 52, "Layer 3: Navigation and Localization".

**FIND:**
```
Navigation-related functions such as waypoint following (via A*) and obstacle
avoidance operate within this layer to support autonomous movement.
```

**REPLACE:**
```
Global path planning (A*, 8-connected with an octile heuristic over a dilated
costmap) runs CONSOLE-side on the operator laptop, which feeds the robot one
path leg at a time. The robot itself runs only reactive local navigation —
ultrasonic-repulsion obstacle avoidance fused with the laptop's streamed
heading bias — so the onboard layer never plans a full route.
```

**Reason+Evidence:** `dashboard_qt/ui/map/planner.py:12` "A* (8-connected,
octile heuristic) on the cost field"; `plan_path()` at line 150 "A* route
start->goal in world meters." Robot-side reactive nav:
`navigation/robot2_local_nav.py` (the single `/cmd_vel` publisher; GOAL mode
fuses `/cmd_vel_bias` with ultrasonic repulsion — `config/robot2.yaml:122-154`).

---

### Fix 4 — §3.6 telemetry vs command rate

**Location:** PAGE 56, "Message Rates and Data Flow".

**FIND:**
```
• Telemetry updates: 20 Hz (onboard), published to ZMQ gateway at 10 Hz
```

**REPLACE:**
```
• Telemetry updates: 20 Hz (the gateway publishes tele.full at 20 Hz)
```

**Reason+Evidence:** `gateway/gateway_node.py:56` `TELE_HZ = 20.0` and line 162
`create_timer(1.0 / TELE_HZ, ...)`; header comment line 8 "tele.full 20 Hz."
The "10 Hz" figure is the **drive-command** stream, not telemetry —
`config/fleet.yaml:10` `drive_stream_hz: 10  # held-key command rate`. The
book's separate "Velocity commands: 10 Hz" bullet (PAGE 56) is the correct
home for that number; leave it.

---

### Fix 5 — §3.6 ESP32 gas polling rate

**Location:** PAGE 56, "Message Rates and Data Flow".

**FIND:**
```
• ESP32 gas readings: 2 Hz HTTP polling rate
```

**REPLACE:**
```
• ESP32 gas readings: 3 Hz HTTP polling rate
```

**Reason+Evidence:** `config/robot3.yaml:11` `poll_hz: 3`.

---

### Fix 6 — §3.6 camera FPS / bandwidth consistency

**Location:** PAGE 57, "Bandwidth Estimation".

**FIND:**
```
• Camera stream (compressed): 10 FPS × 50 KB per frame ≈ 500 KB/s
```

**REPLACE:**
```
• Camera stream (compressed): 15 FPS × 50 KB per frame ≈ 750 KB/s
```

And update the total:

**FIND:**
```
The total estimated bandwidth usage is approximately 600 KB/s, which is well
within the capacity of standard WiFi networks.
```

**REPLACE:**
```
The total estimated bandwidth usage is approximately 870 KB/s (LiDAR ~16 KB/s
+ camera ~750 KB/s + auxiliary ~100 KB/s), which is well within the capacity
of standard WiFi networks.
```

**Reason+Evidence:** The configured camera rate is 15 fps everywhere else
(`config/robot2.yaml:28` `fps: 15`; book "Camera video stream: 15 FPS" PAGE 57,
"15 frames per second" PAGE 49). Using 10 FPS in the bandwidth line is
internally inconsistent. Per-frame size (50 KB) is the book's own assumption —
kept; recompute: 15 x 50 = 750 KB/s; 16 + 750 + 100 = 866 ~= 870 KB/s.

---

### Fix 7 — §3.7 (and §3.6) deadman timeout, layered chain

**Location A:** PAGE 58, "Risks and Mitigation Strategies".

**FIND:**
```
If the heartbeat signal is lost for more than 2 seconds, the robot
automatically cuts motor power to prevent runaway conditions.
```

**REPLACE:**
```
Motor power is cut by a layered deadman chain rather than a single timeout:
the gateway stops the drive after 0.6 s of silence, the onboard bridge after
0.8 s, and the firmware watchdog after 1.0 s — whichever fires first. This
redundancy prevents runaway conditions even if one layer hangs.
```

**Location B:** §3.6 — the book mentions "a multi-layer deadman safety chain
from the operations center to the gateway and low-level firmware" (PAGE 58,
under Risks). That phrasing is correct; if any §3.6 passage states a single
"2 second" value, apply the same three-tier wording.

**Reason+Evidence:**
- Gateway 0.60 s: `common/gpcore/protocol/commands.py:44` `DEADMAN_S = 0.60`
  (consumed by `gateway/zmq_server.py` `DriveDeadman`).
- Bridge 0.8 s: `config/robot1.yaml:31` and `config/robot2.yaml:94`
  `deadman_timeout_s: 0.8`.
- Firmware 1.0 s: `firmware/robot2_controller_v5/robot2_controller_v5.ino:131`
  `#define WATCHDOG_MS 1000UL  // auto-stop if no command`.

---

### Fix 8 — "Logitech camera" -> generic USB camera

**Location:** PAGE 41 (Team Organization) "integrating the Logitech camera",
and PAGE 44 (FR5) "the onboard Logitech camera".

**FIND (each occurrence):** `Logitech camera`

**REPLACE:** `USB camera`

**Reason+Evidence:** The repo configures a generic USB capture device, no
brand: `config/robot2.yaml:24-28` `camera: device: 0, width: 640, height: 480,
fps: 15`. Table 3.2 and the §3.5.1 Beta description already say "USB camera" —
this makes the document consistent. (Note: PAGE 51 FR5 still says "Logitech
camera" too; fix all three.)

---

### Fix 9 — YOLO model naming (YOLOv8n -> configured models)

**Locations:** PAGE 40 ("object detection using YOLOv8n"), PAGE 41
("object detection using YOLOv8n on the external laptop"), PAGE 41 Month-4
timeline ("YOLOv8n-based object detection").

**FIND (each):** `YOLOv8n`

**REPLACE:** `YOLOv8 (yolov8s.pt primary + fire.pt secondary)`

**Reason+Evidence:** `config/fleet.yaml:21` `default_model: yolov8s.pt` and
line 22 `fire_model: fire.pt  # secondary`. No `yolov8n` model is configured
anywhere. The later FRs (FR6, §3.4, §3.5.2 modules) already say "YOLOv8" /
"fire.pt" correctly — these three early "YOLOv8n" mentions are the outliers.
Table 3.3 "Object Detection: YOLOv8" is correct, leave it.

---

### Fix 10 — RViz2 role in Fig 3.2 architecture

**Location:** PAGE 46, paragraph ending in Figure 3.2.

**FIND:**
```
RViz2 is integrated into the architecture to provide real-time visualization
of the map, robot pose, and sensor data during operation and testing, as
illustrated in Figure 3.2.
```

**REPLACE:**
```
RViz2 is used only as a developer-side debug and visualization aid during
bring-up and testing; it is NOT the runtime operator interface. The operational
UI for live missions is the native PySide6 desktop operations console, which
renders the map, robot pose, video, and detections for the operator.
```

**Reason+Evidence:** `CLAUDE.md` / repo: the operator console is the PySide6
app (`dashboard_qt/main.py`). RViz2 is not part of the operator runtime; the
book's own §3.4 and §3.6 describe the PySide6 console as the operator
interface. (Optional but recommended for accuracy.)

---

## VERIFY WITH HARDWARE TEAM (specs not tracked in the repo)

These appear in the book but are NOT defined in any config/firmware file, so
they cannot be confirmed against the codebase. The team must confirm them
against the physical hardware:

- **Battery chemistry/capacity:** "3S LiPo, 11.1 V, 5000 mAh." Only the
  arithmetic was corrected (~55.5 Wh, not ~67 Wh). Confirm the actual cell.
- **Raspberry Pi 4 RAM / microSD / OS image:** "8 GB RAM, 64 GB microSD,
  Ubuntu 22.04." Clock corrected to 1.5 GHz (Pi 4B spec); the rest is
  unverified by repo.
- **Chassis dimensions & weight:** book says "~40 cm x 30 cm x 25 cm, ~10 kg."
  `config/robot1.yaml:48-49` confirms Alpha footprint 0.40 m x 0.30 m
  (length x width), but **height (25 cm) and weight (10 kg) are not in the
  repo** — confirm. Note Beta's footprint is 0.30 m x 0.20 m
  (`config/robot2.yaml:45-46`), smaller than the single figure the book gives.
- **Whether Alpha carries an Arduino Mega 2560 at all** (see Table 3.1 note):
  the fleet table in `CLAUDE.md` attributes the Mega + encoders to Beta only.
- **Buck converter voltages** ("12 V motors, 5 V/3 A logic"): not in repo;
  confirm with the power subteam.

---

## Confirmed CORRECT — leave unchanged

- Table 3.3 software stack (Ubuntu 22.04, ROS 2 Humble, slam_toolbox, YOLOv8,
  PyTorch, PySide6, Git/GitHub, "Real-Time OS: None").
- ZMQ port map 5556 telemetry / 5557 map / 5558 cmd / 5559 health / 5560 video
  (`config/robot1.yaml:22-27`, `gateway/gateway_node.py` header).
- msgpack envelope; ROUTER/DEALER ACK + dedupe + retry (ACK timeout 300 ms,
  x2 retries — `common/gpcore/protocol/commands.py:6`).
- Map updates <=1 Hz (`gateway/gateway_node.py:58` `MAP_FORWARD_HZ = 1.0`;
  `mapping/mapper.yaml:16` `map_update_interval: 1.0`).
- LiDAR scan forwarding <=5 Hz (`gateway/gateway_node.py:57`
  `SCAN_FORWARD_HZ = 5.0`).
- Velocity commands 10 Hz during teleop (`config/fleet.yaml:10`).
- Map resolution 0.025 m, 12 m range, 5.5 Hz (`mapping/mapper.yaml`).
