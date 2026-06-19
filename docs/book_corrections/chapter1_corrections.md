# Chapter 1 — Paste-Ready Corrections

Audit of Chapter 1 (`book_ch1.txt`) against the actual project. Each required
edit gives the **exact original quote** (so the team can find-and-replace),
the corrected **paste-ready** text, and the repo evidence. Optional additions
and hardware-verify notes follow.

---

## Required fixes

### 1. §1.6 Project Scope — Autonomous decision-making is IN scope (SERIOUS)

The book lists autonomous decision-making/action execution as OUT of scope.
This is wrong: the console ships two autonomous behaviors (SCAN AREA coverage
of Alpha's map, and GO TO FIRE -> PUMP 5 s -> RETURN), both real and
operator-armed.

**Location:** §1.6 Project Scope, "Out of Scope" list (book page 20).

**FIND** (exact original line in the Out-of-Scope list):
```
• Autonomous decision-making and action execution (current phase focuses on 
mapping and detection) 
```

**REPLACE** (remove the line entirely from the Out-of-Scope list; delete it).

Then, in the **Software Scope** list of the same section (book page 20),
**FIND**:
```
• Dashboard interface for monitoring and control 
```

**REPLACE**:
```
• Dashboard interface for monitoring and control 
• Autonomous mission execution from the operations center: area-coverage 
scanning of the shared map (SCAN AREA) and a GO TO FIRE -> dispense (5 s 
pump) -> RETURN sequence, both built on the A* planner and reactive 
obstacle avoidance 
```

**Reason + Evidence:** The autonomy state machine (SCAN / FIRE sequences,
single-shot 5 s pump timer, coverage path, AUTONOMY dock) is implemented in
`dashboard_qt/ui/main_window.py` (e.g. autonomous sequence state machine and
`_pump_timer` set to single-shot; `coverage_path` from `ui/map/coverage.py`).
Corroborated by `CLAUDE.md` ("Console AUTONOMY dock: SCAN AREA ... + GO TO
FIRE -> PUMP 5s -> RETURN, both real").

---

### 2. §1.1 — Alpha has NO wheel encoders

The book claims Alpha "wheel encoders are present but unused." Alpha has no
wheel encoders at all; it localizes via rf2o laser odometry + slam_toolbox.

**Location:** §1.1 Project Overview, System Composition, item 1 Alpha (book page 13).

**FIND** (exact original):
```
Alpha’s wheel encoders 
are present but unused for localization; mapping relies entirely on scan-based 
odometry.[4] 
```

**REPLACE**:
```
Alpha has no wheel encoders; localization relies entirely on scan-based 
odometry (rf2o laser odometry feeding slam_toolbox).[4] 
```

**Reason + Evidence:** `firmware/robot1_controller_v3/robot1_controller_v3.ino`
header: "4WD - no encoders used (SLAM localizes by scan match)". `CLAUDE.md`
fleet table: Alpha "no wheel encoders." `config/robot1.yaml` defines only
lidar/footprint/goto params, no encoder calibration. This now matches §1.7,
which already states "Alpha uses driven wheels without encoder-based
odometry."

---

### 3. §1.1 — Only the two Pis use 5 GHz WiFi; Gamma (ESP32) is 2.4 GHz only

**Location:** §1.1 Project Overview, System Composition closing paragraph (book pages 13–14).

**FIND** (exact original):
```
All robots communicate over a 5 GHz WiFi network. The Raspberry Pi–based robots (Alpha 
and Beta) run ROS 2 locally and expose telemetry, map data, video, and commands through a 
ZeroMQ/msgpack gateway protocol.
```

**REPLACE**:
```
The robots communicate over a shared WiFi network. The Raspberry Pi–based robots (Alpha 
and Beta) connect on 5 GHz, run ROS 2 locally, and expose telemetry, map data, video, and 
commands through a ZeroMQ/msgpack gateway protocol; the ESP32-based Gamma robot has no 5 GHz 
radio and joins the network's 2.4 GHz band.
```

**Reason + Evidence:** `docs/wiring/robot3.md`: "2.4 GHz network only (ESP32
has no 5 GHz!) — give it the router's 2.4 GHz SSID."

Note: §1.6 Assumptions ("WiFi network (5GHz) will be available") and §1.7
Network Constraints ("Communication relies on 5GHz WiFi network") carry the
same over-broad claim. Recommended softening — **FIND** (§1.7):
```
• Communication relies on 5GHz WiFi network 
```
**REPLACE**:
```
• Communication relies on a shared WiFi network (5 GHz for the Raspberry 
Pi robots; 2.4 GHz for the ESP32 robot) 
```

---

### 4. §1.1 — Gamma's IMU is MPU6050 (not GY-87); GY-87 is Beta's

**Location:** §1.1 Project Overview, System Composition, item 3 Gamma (book page 13).

**FIND** (exact original):
```
an MQ-5 gas sensor, HC-SR04 ultrasonic sensor, MPU6050/GY-87 
IMU, a buzzer, and a servo mechanism.
```

**REPLACE**:
```
an MQ-5 gas sensor, HC-SR04 ultrasonic sensor, an MPU6050 
IMU, a buzzer, and a servo mechanism.
```

Optionally also correct Beta (item 2, page 13), which is the GY-87 robot.
**FIND**:
```
GY-87/MPU6050 IMU
```
**REPLACE**:
```
GY-87 IMU
```

**Reason + Evidence:** `firmware/robot3_controller_v2/robot3_controller_v2.ino`:
"MPU6050 IMU" (header) and `Adafruit_MPU6050 mpu;`. `CLAUDE.md` fleet table:
Gamma has "MPU6050," Beta has "GY-87 IMU." (Note: `docs/wiring/robot3.md`
labels it "GY-87/MPU6050" because a GY-87 breakout physically carries the
MPU6050 chip; the firmware drives only the MPU6050, so MPU6050 is the
accurate designation for Gamma.)

---

### 5. §1.2 — The project's simulator is the console's --sim mode, not Gazebo

§1.2 lists Gazebo under ROS's "Simulation Environment." That bullet describes
ROS generically, which is fine — but the chapter should not leave the reader
assuming Gazebo is the project's simulator. The project's simulation is the
console's own `--sim` mode.

**Location:** §1.2 Background and Context, "Robot Operating System (ROS)" list (book page 16).

**FIND** (exact original):
```
• 
Simulation Environment: Gazebo simulator for testing without physical robots. 
```

**REPLACE**:
```
• 
Simulation Environment: ROS integrates with simulators such as Gazebo. (This 
project does not use Gazebo; hardware-free testing is provided by the operations 
center's own built-in --sim mode, which spawns simulated robots speaking the 
production protocol — see Section X.) 
```
(Replace "Section X" with the chapter/section where `--sim` is described, or
drop the cross-reference.)

**Reason + Evidence:** Simulation is implemented in `dashboard_qt/sim/`
(`fake_gateway.py`, `fake_esp32.py`); launched via `python dashboard_qt/main.py
--sim` (`README.md` Quick start; `CLAUDE.md` Running it). No Gazebo packages
or world files exist in the repo.

---

### 6. §1.4 / §1.7 — "modular ROS packages" and "System runs on ROS" overstate ROS coverage

ROS 2 Humble runs only on the two Pis. The PySide6 console and the
`common/gpcore` core are ROS-free, and Gamma (ESP32) is non-ROS HTTP/JSON.

**Location A:** §1.4 Motivation, "ROS Standardization" (book page 18).

**FIND** (exact original):
```
ROS Standardization: Building the system within the ROS ecosystem ensures that results are 
reproducible and extensible. Each component (SLAM, object detection, communication) is 
implemented as modular ROS packages[12],[13]. 
```

**REPLACE**:
```
ROS Standardization: Building the mapping and intervention robots within the ROS 2 ecosystem 
ensures that those components are reproducible and extensible. ROS 2 Humble runs only on the 
two Raspberry Pi robots (Alpha and Beta); the PySide6 operations center and the shared 
common/gpcore core library are ROS-free, and the ESP32-based Gamma robot runs no ROS, 
exposing a plain HTTP/JSON interface instead.[12],[13] 
```

**Location B:** §1.7 General Constraints, "Software Constraints" (book page 21).

**FIND** (exact original):
```
• System runs on ROS under Ubuntu Linux 
• Software must be compatible with ROS ecosystem 
```

**REPLACE**:
```
• The Raspberry Pi robots run ROS 2 Humble under Ubuntu Linux; the operations 
center is a native PySide6 desktop application (no ROS), and the ESP32 robot 
runs firmware with an HTTP/JSON interface (no ROS) 
• Per-robot ROS 2 DDS traffic is confined to localhost; the only network 
doorway is the ZMQ/msgpack gateway 
```

**Reason + Evidence:** `README.md`: "common/gpcore/ ROS-free core"; the
operations center is "native PySide6"; Gamma "HTTP API"; architecture diagram
shows ROS 2 islands only on Pi 4 / Pi 3B+. `CLAUDE.md`: "Gamma is not ROS —
plain HTTP/JSON, wrapped laptop-side"; "common/gpcore/ — pure-Python shared
lib." (No ROS package manifests — `package.xml`/`setup.py` ROS packages —
back the "modular ROS packages" phrasing.)

---

## Optional additions

These are not errors; the team may wish to add them for accuracy/impact.

- **The msgpack-over-ZMQ gateway as the architectural centerpiece.** Each Pi
  is a self-contained ROS 2 island with localhost-only DDS; the per-robot
  gateway is the single network doorway, speaking a versioned, sequence-
  numbered, ACKed msgpack/ZMQ protocol with per-stream freshness tracking
  (ports 5556 telemetry / 5557 map / 5558 commands / 5559 health / 5560
  video). Evidence: `README.md` Architecture, `CLAUDE.md` Architecture,
  `common/gpcore/protocol`.

- **Zero-hardware `--sim` mode.** `python dashboard_qt/main.py --sim` spawns
  fully simulated robots (arena, raycast LiDAR, physics, test fire video)
  speaking the production protocol bit-for-bit, enabling development and demos
  with no robots attached. Evidence: `dashboard_qt/sim/`, `README.md`,
  `CLAUDE.md`.

- **SET POSE shared-frame localization.** Alpha's SLAM frame is the world
  frame; other robots are dropped onto the shared map once with the RViz-style
  SET POSE tool (click = position, drag = heading), after which every pose,
  detection, and goal click is transformed between frames. Evidence:
  `README.md` "Shared-map multi-robot localization."

---

## Verify with hardware team

The following physical-build claims could NOT be confirmed or refuted from
code/docs. Do not delete them — confirm the numbers with the hardware team.

- **Test arena size / room count** — §1.5 Obj. 7, §1.6 Environment Scope,
  §1.8: "4x4 meter test area divided into 4 rooms." Not in any code/config.
  VERIFY WITH HARDWARE TEAM. (Note: `config/robot1.yaml` records a measured
  *chassis* of 40 cm x 30 cm — unrelated to the arena, but worth a sanity
  check against the chassis claim below.)

- **Chassis material/dimensions** — §1.7 Mechanical Constraints: "Chassis
  designed from aluminum sheet (1m x 1m, 1.5mm thickness)." The repo only
  records Alpha's *assembled footprint* (40 cm long x 30 cm wide,
  `config/robot1.yaml`), which is the robot's size, not the raw sheet stock.
  These are not contradictory, but the "1m x 1m, 1.5mm" sheet spec is
  unverifiable from code. VERIFY WITH HARDWARE TEAM.

- **Beta wheel diameter / motor spec** — §1.1 and §1.7: "85 mm wheels",
  "25GA370 encoder motors (408 CPR)." CPR/kinematics live in `config/robot2.yaml`
  (cross-check there); wheel diameter should be confirmed with the hardware
  team. VERIFY WITH HARDWARE TEAM.
