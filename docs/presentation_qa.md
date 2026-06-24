# GP Swarm — Presentation Question Bank (English)

A study guide of the questions a graduation committee is likely to ask, with
answers grounded in how this project *actually* works. Use it to understand the
system end-to-end, not just to memorize. Numbers and behaviors here match the
code/config in this repo (`config/*.yaml`, `navigation/`, `gateway/`,
`dashboard_qt/`, `mapping/`).

> One-line pitch: **Three heterogeneous robots and a Windows operator console
> cooperate over a dedicated LAN to map an area, detect a fire/hazard, and
> intervene — with the laptop as the coordinator and each robot kept as an
> isolated, recoverable island.**

---

## 1. Project overview & motivation

**Q: In one sentence, what is your project?**
A multi-robot emergency/inspection system: a mapper robot builds a live map, an
intervener robot navigates that map to a detected fire and pumps water, and an
inspector robot reads gas — all commanded from one operator console over a
private wireless LAN, with no internet required.

**Q: What problem does it solve / why is it useful?**
Emergency response in places dangerous for humans (fire, gas leaks, collapsed
or smoke-filled rooms). One operator supervises a small team of specialized
robots instead of risking people. It is an inspection/first-response platform.

**Q: Why THREE robots instead of one capable robot?**
Specialization and redundancy. Each robot is optimized for one job (mapping,
intervention, gas inspection) with cheaper hardware than one do-everything
robot, and the loss of one does not stop the mission. It also demonstrates
**heterogeneous multi-robot coordination**, which is the academic contribution.

**Q: Why "swarm"? Is this really a swarm?**
Honestly, it is **centralized multi-robot coordination**, not a decentralized
biological swarm. The laptop is the brain; robots do not talk to each other
directly. We use "swarm" loosely for "a coordinated team of robots." Being
precise about this in the defense is a strength, not a weakness.

---

## 2. System architecture

**Q: Describe the overall architecture.**
Three layers:
1. **Robots** — each runs its own control stack locally (ROS 2 on the Pis,
   bare firmware on the ESP32). All inter-process traffic stays on localhost.
2. **Gateways** — one per robot; the ONLY door between a robot and the network.
   Speaks a versioned **msgpack-over-ZMQ** protocol.
3. **Operator console** — a Windows PySide6 desktop app that connects to every
   gateway, holds the shared map, plans routes, runs the autonomy, and shows
   video + telemetry.

**Q: What is the "ROS islands + gateway" pattern and why did you choose it?**
Each Pi keeps all its ROS 2 / DDS traffic on `127.0.0.1` (localhost only). The
robots do NOT share a ROS graph over WiFi. The single gateway node bridges the
robot's internal ROS topics to a small, explicit set of network channels.
Benefits: (a) WiFi problems can't corrupt the internal control loop; (b) the
network protocol is small, versioned and debuggable; (c) robots are isolated —
a crash or a topic-name clash on one cannot affect another.

**Q: Who is the "brain"? Where does the intelligence live?**
The **laptop/console**. It holds the map, runs A* path planning, the coverage
planner, the mission executor, and YOLO detection. The robots run deliberately
**simple, reliable** local controllers (go-to-goal, reactive ultrasonic
avoidance). "Plan on the laptop, execute dumbly on the robot" is a core design
decision.

**Q: What happens if the laptop disconnects mid-mission?**
The robots stop safely. Drive commands use a **deadman**: the gateway zeroes
velocity ~0.6 s after the last command, and the on-robot reactive node stops
wandering if the console heartbeat goes stale (~2 s). Firmware has its own
~1 s command watchdog as the last line.

---

## 3. The robots (hardware)

**Q: Describe each robot.**

| Robot | Name | Brain | Role | Key hardware |
|-------|------|-------|------|--------------|
| robot1 | **Alpha** | Raspberry Pi 4 | SLAM mapper | RPLIDAR A1M8, scan-matching odometry, **no wheel encoders** |
| robot2 | **Beta** | Pi 3B+ + Arduino Mega 2560 | Intervener | 4 motors + 4 quadrature encoders, GY-87 IMU, camera, water pump, arm servo, **2 front HC-SR04 ultrasonics**, **no lidar** |
| robot3 | **Gamma** | ESP32 | Inspector | 4 motors, ultrasonic, **MQ gas sensor**, MPU6050 IMU, servo; HTTP UI |

**Q: Why a Pi 4 for Alpha but a Pi 3B+ for Beta?**
Alpha runs SLAM (slam_toolbox + Ceres solver), which is CPU-heavy, so it gets
the faster Pi 4. Beta's heavy lifting (odometry, planning) was **moved to the
laptop**, so a Pi 3B+ is enough — it only runs one lightweight reactive node.

**Q: Why does Beta have an Arduino Mega in addition to the Pi?**
Real-time motor/encoder/sensor I/O. The Mega handles the 4 motors, 4 quadrature
encoders, the IMU, ultrasonics, pump and servo at a steady loop; the Pi does
the higher-level ROS work and talks to the Mega over USB serial. Splitting hard
real-time (Mega) from Linux/ROS (Pi) is standard and avoids timing jitter.

**Q: Why does the inspector (Gamma) use an ESP32 and not ROS?**
It is a simple, cheap sensor node — drive + gas + ultrasonic. An ESP32 with
WiFi and an HTTP/JSON interface is sufficient and far cheaper than a Pi+ROS
stack. The console wraps Gamma's HTTP behind the same interface as the other
robots, so the operator sees a uniform fleet.

**Q: What are Beta's exact drive parameters?**
85 mm wheels; encoders give **408 counts per wheel-revolution** (12 PPR encoder
× 34:1 gearbox); wheel base ≈ 0.225 m (skid-steer, 4 wheels). Footprint ≈
0.20 m wide, ±0.10 m half-width. These live in `config/robot2.yaml` and are the
single source of truth shared by the bridge, the laptop odometry, and firmware.

---

## 4. SLAM & mapping

**Q: How do you build the map?**
Alpha runs **slam_toolbox** (ROS 2) in mapping mode with its RPLIDAR A1M8. It
produces an occupancy grid (`/map`) and the `map -> base_link` transform. The
gateway compresses the grid (zlib) and publishes it; the console renders it.

**Q: What is SLAM and which algorithm do you use?**
SLAM = Simultaneous Localization And Mapping: building a map while
simultaneously tracking the robot's pose in it. We use slam_toolbox's
graph-based SLAM with the **Ceres** non-linear solver (Levenberg-Marquardt),
**scan matching** to register successive laser scans into a pose graph.

**Q: Alpha has no wheel encoders — how does it know it moved?**
Pure **scan matching**. slam_toolbox estimates ALL motion by aligning each new
lidar scan to the existing map (`use_scan_matching: true`). We register a new
graph node only after the robot has moved ≥ 0.10 m or rotated ≥ ~10°
(`minimum_travel_distance` / `minimum_travel_heading`) — otherwise identical
stationary scans get re-registered ~3×/s and waste CPU + add speckle noise.

**Q: What map resolution do you use and why?**
**0.025 m** (2.5 cm) per cell. The A1M8's <1% range error supports it, and it
doubles wall crispness versus the default 5 cm. The trade-off is 4× the cells,
so we watch the Pi 4 CPU and would fall back to 5 cm if load spikes.

**Q: Why does the map sometimes flicker or jump (and how did you fix it)?**
Originally every scan was processed and the map re-published ~3×/s, saturating
the Pi 4 → flicker and pose jumps. Fix: `map_update_interval: 1.0` (publish
1×/s) and the travel-distance gate above. CPU dropped and the map became
stable.

**Q: What is the maximum lidar range you use?**
12 m (`max_laser_range`), which comfortably covers the arena; returns beyond
that are dropped.

---

## 5. Localization & odometry

**Q: How does BETA localize? It has no lidar.**
Beta uses **dead reckoning**: wheel **encoders** for distance + the **GY-87
gyroscope** for heading, fused into a pose. This runs **on the laptop**
(`dashboard_qt/state/local_odom.py`) from Beta's raw telemetry, and the
operator **aligns** Beta onto Alpha's shared map once with **SET POSE** (like
RViz's "2D Pose Estimate").

**Q: That drifts over time — isn't that a problem?**
Yes, and we are honest about it: this is the system's **fundamental
limitation**. Without a lidar or absolute reference, Beta's estimated pose
drifts. We **tolerate** it (the planner frees a disc around Beta's own cell so a
slightly-wrong pose doesn't read "inside a wall"; the reactive ultrasonics
reflect reality), and the practical mitigation is a periodic **SET POSE**
re-align during a long run. The real cure would be giving Beta a lidar or
scan-matching, which is future work.

**Q: How is Beta's heading measured, and what is the known failure?**
Heading is integrated from the GY-87 gyro **in the bridge at 50 Hz** using the
Arduino's own timestamp (immune to Linux/serial jitter), with a measured scale
correction (~1.03). Known failure: the GY-87 **intermittently drops off the I2C
bus** and streams *frozen* non-zero gyro values → heading freezes → the map
arrow goes static. Fix now: power-cycle. Permanent fix: rewire its VCC from
3.3 V to 5 V (the top hardware ticket). There is also an encoder-only heading
fallback when the gyro is detected dead.

**Q: Why is Alpha's localization more reliable than Beta's?**
Alpha has a lidar and runs SLAM, so its pose is **continuously corrected**
against the map (drift-corrected). Beta only dead-reckons, so it drifts. That is
exactly why the FIRE task (precise navigation to a point) was assigned to Alpha.

---

## 6. Path planning & navigation

**Q: How do you plan a path?**
On the console, in `dashboard_qt/ui/map/planner.py`: **A\*** on the occupancy
grid (8-connected, octile heuristic). Obstacles are inflated by the robot radius
(so the whole robot fits), unknown cells are treated as blocked, and the dense
cell-path is simplified to a few straight waypoints the robot's executor can
follow.

**Q: Why A\* and not RRT / Dijkstra / nav2?**
A* is optimal, fast on arena-scale grids (tens of ms), and easy to tune. The
grid is small, so sampling planners (RRT) aren't needed. We deliberately did NOT
adopt the full nav2 stack on Beta because Beta is lidar-less and nav2 assumes
good localization; our "plan on laptop, execute simply on robot" split is more
robust for our hardware.

**Q: What is the "cost map / soft cost" and why?**
Around hard obstacles we add **soft cost rings** (extra traversal cost up to
~40 cm from walls). A* then prefers the **center of open space** instead of
hugging walls. This is safer for a drift-prone robot (more clearance) and was a
direct response to "routes hug the walls."

**Q: How does the robot actually follow the planned path?**
The **mission executor** (`dashboard_qt/ui/mission.py`) sends one waypoint at a
time and watches the robot's pose. For **Alpha**, it sends a goal
(`cmd.goal`) and Alpha's on-board lidar go-to-goal drives there. For **Beta**,
the laptop streams a **heading bias** (`cmd.nav_bias`) that Beta's reactive node
fuses with its ultrasonics. It advances to the next waypoint when close enough.

**Q: What is "rotate-then-drive"?**
The controller first rotates to face the waypoint (forward speed = 0 while the
heading error is large), then drives forward. It keeps motion simple and
odometry-friendly (no curved dead-reckoning).

**Q: What was the "decisive turn-around" fix?**
When the next waypoint is **directly behind**, the heading error sits at the
±π wrap, where tiny pose noise flips its sign and the robot **rocks in place /
loops** instead of turning around. Fix: once the error exceeds ~80°, **commit
to one spin direction** and hold it until the robot faces the goal. Applied to
Beta's mission and Alpha's goto.

**Q: How do you detect that a robot is "stuck"?**
Progress-based, not a fixed timer. A waypoint is only abandoned if the robot
stops making progress toward it — where progress = **getting closer OR turning
to face it**. A slow legitimate turn no longer counts as "stuck." After several
consecutive unreachable waypoints it gives up cleanly.

---

## 7. Obstacle avoidance

**Q: How does Beta avoid obstacles without a lidar?**
Two front **HC-SR04 ultrasonic** sensors + a reactive fuser
(`navigation/robot2_local_nav.py`, math in `local_nav_math.py`). It fuses the
laptop's heading bias (attraction to the goal) with **ultrasonic repulsion**
(push away from the nearer wall). It hard-stops at 25 cm, slows from 60 cm.

**Q: What was the doorway-freeze bug and how did you fix it?**
Originally forward speed was gated by the **nearer** wall, so at a doorway one
door-post (~27 cm) would zero the forward speed and Beta **froze** in a
potential-field local minimum. Fix: gate forward motion on the **more-open**
side — a wall on one side lets Beta keep moving and steer past it; it only
stops when **both** sides are blocked.

**Q: What does Beta do when it actually hits a dead end / corner?**
A recovery ladder: **reverse → pivot → commit forward**, alternating the turn
direction if it traps again. This breaks the "pivot-in-place" oscillation. After
several stalls it reports STUCK rather than grinding.

**Q: How does Alpha avoid obstacles?**
Alpha uses its **lidar** in `robot1_goto.py`: every scan is checked against the
measured footprint — a forward corridor (hard stop with hysteresis) and a
rotation circle (the 30 cm rear overhang sweeps 0.34 m, so rotation is blocked
if something is in that circle). It also learns a **self-occlusion mask** at
boot so its own cable/bracket in the lidar plane is ignored instead of
permanently blocking goals.

---

## 8. Multi-robot coordination

**Q: How do the robots coordinate? Do they talk to each other?**
No direct robot-to-robot link — by design. The **laptop is the coordinator**.
It holds Alpha's map, and when Beta needs to navigate that map, the laptop
plans the route and streams Beta simple commands. This avoids a fragile
robot-to-robot map-sharing link and keeps each robot an isolated island.

**Q: How does Beta use Alpha's map if they're separate ROS islands?**
Through the laptop. The console receives Alpha's map over the gateway, plans
Beta's global route on it, and sends Beta the resulting waypoints/heading bias.
Beta never needs Alpha's ROS graph.

**Q: How are robots kept from interfering (e.g., commanding the wrong robot)?**
Distinct ROS domains (Alpha = 11, Beta = 12), localhost-only DDS, and separate
gateways on separate ports. A topic on one robot cannot reach another.

---

## 9. Communication & networking

**Q: What protocol do the laptop and robots use?**
A custom **versioned msgpack-over-ZMQ** protocol (`common/gpcore/protocol`).
msgpack = compact binary serialization; ZMQ = the messaging library. Each robot
exposes fixed channels/ports:

| Port | Channel | Purpose |
|------|---------|---------|
| 5556 | telemetry (PUB) | pose, encoders, IMU, ultrasonics, nav status (~20 Hz) |
| 5557 | map (PUB) | zlib-compressed occupancy grid (~1 Hz) |
| 5558 | command (ROUTER) | drive/goal/pump/estop… with **ACKs** |
| 5559 | health (PUB) | CPU temp, throttling, RSSI, stream ages |
| 5560 | video (PUB) | JPEG frames |

**Q: How are commands made reliable?**
The command channel uses request/ACK: each command carries an ID; if no ACK in
**300 ms** it retries (×2) with the **same ID**, and the gateway de-duplicates
so safety-critical commands (pump, servo) happen **exactly once**.

**Q: Why ZMQ instead of just using ROS over WiFi (or rosbridge)?**
ROS/DDS over WiFi is fragile (the project hit exactly this — see next answer)
and exposes the whole ROS graph to the network. A small explicit ZMQ protocol
is robust, versioned, and easy to debug. (rosbridge was used early, then
retired.)

**Q: What was the hardest networking bug you solved?**
`ROS_LOCALHOST_ONLY=1`'s interface tracking **silently killed all local DDS
delivery** whenever the WiFi interface changed state — Beta would die at random
times while Alpha (on a stable radio) was immune. Fix: move localhost isolation
to the **transport layer** — `interfaceWhiteList 127.0.0.1` in the Fast-DDS XML,
`ROS_LOCALHOST_ONLY=0`, plus a localhost discovery server and distinct domains.
A subtle, high-value debugging story.

**Q: Do you need internet?**
No. The fleet runs on a **dedicated WiFi router** with no internet. Everything
(map, video, commands) is local LAN.

---

## 10. The operator console (dashboard)

**Q: What is the console built with and why?**
A **PySide6** (Qt for Python) native desktop app (`dashboard_qt/`). Native
rendering (not a browser) for a smooth live map + video, a background QThread
per robot for the network transport so the UI never freezes, and the AI model
runs in a **separate process** so an inference crash can't take down the
console.

**Q: What can the operator do from the console?**
See the live map + every robot's pose/trail, watch video with detections,
drive any robot (joystick/WASD), set a robot's pose, drop/remove markers, plan
& run the autonomy (SCAN / FIRE), and E-STOP. Health badges show each robot as
FRESH / STALE / DEAD.

**Q: Walk me through the SCAN operator flow.**
**SCAN AREA** generates a coverage path and shows it as **draggable numbered
nodes** (green START / orange END) — but does NOT move. The operator can drag /
add / remove nodes (the A* route re-plans around walls live), then **START
SCAN** drives it. Manual nudging the joystick mid-run **pauses** the mission and
resumes from the new pose on release. This "plan → review/edit → start" flow is
deliberate operator control.

**Q: How does the console stay responsive with video + map + AI at once?**
Threading/process isolation: transport on QThreads, inference in a child
process with a shared-frame ring, map/video render throttled, and only the GUI
thread touches widgets.

---

## 11. Computer vision / detection

**Q: How do you detect fire / people?**
**YOLO** (Ultralytics) in a crash-isolated subprocess. The primary model is a
clean COCO net (`yolov8s.pt`) for person/dog/cat; a secondary fire-only net
(`fire.pt`) is trusted **only** for its Fire class. Detections above a per-class
confidence floor are drawn on the video and dropped as **markers on the map**.

**Q: Why two models instead of one fire model?**
The fire fine-tune **destroyed** the model's COCO classes — on a real backlit
frame `fire.pt` scored 0% on a person that `yolov8s` got 92% on. So the clean
COCO model must stay primary, and the fire model is secondary for flames only.
An honest, data-driven decision.

**Q: Your fire confidence is low — isn't detection unreliable?**
We're transparent about this: real fire photos score ~28–37% with our model,
while night-room false positives reached 26–39% — the ranges **overlap**, so a
threshold alone can't separate them. The audible **alarm** gate was raised to
0.80 on the team's request (so it rarely false-alarms), while the detections
table still lists everything seen. The real fix is a **better-trained model**,
not a threshold — stated as future work. (A classical flame-prop detector
exists for demos.)

**Q: How does a 2D detection become a map marker?**
The detection's bearing + an estimated range are projected from the robot's
current pose into the shared map frame; nearby detections of the same class are
merged so one fire = one marker (monocular range jitters frame-to-frame).

---

## 12. Firmware & embedded

**Q: What runs on the Arduino Mega (Beta)?**
The real-time controller (`firmware/robot2_controller_v5/`): reads 4 quadrature
encoders and the IMU, drives 4 motors (PWM), reads the 2 ultrasonics
(round-robin + median filter), runs the pump and arm servo, and exchanges a
compact serial packet with the Pi. It has a **command watchdog** (auto-stop on
serial silence) and a **pump auto-off** safety cap.

**Q: What runs on the ESP32 (Gamma)?**
`firmware/robot3_controller_v2/`: motor drive, MQ gas reading with a **local
latched alarm** (threshold 2700 raw ADC, clears < 2000 with hysteresis +
buzzer), ultrasonic, servo, and a WiFi HTTP/JSON interface. The gas alarm works
even with no network.

**Q: Why is there an over-voltage warning about Gamma?**
A buck converter set to 10 V once hit the ESP32 + IMU + MQ sensor (the team's
2nd over-voltage event). The ESP32 survived; the lesson encoded everywhere:
**measure the buck at the terminals before connecting**.

---

## 13. Safety systems

**Q: What are your layers of safety?**
Defense in depth:
1. **Firmware watchdog** — motors auto-stop if serial goes silent (~1 s).
2. **Gateway deadman** — velocity zeroed ~0.6 s after the last drive command.
3. **Console heartbeat** — the reactive node stops wandering if the operator
   app stops re-affirming AUTONOMOUS (~2 s).
4. **Real end-to-end E-STOP** — Esc/button → sent 5× and **latched** at the
   gateway → motors + pump off.
5. **Ultrasonic / lidar hard stops** — 25 cm (Beta), footprint corridor
   (Alpha).
6. **Pump auto-off** — firmware hard-caps the pump run time (5–10 s).

**Q: Can the operator always stop the robots?**
Yes — **Esc** is the software E-STOP, always enabled, and it's latched so a
robot can't silently resume. There is also a physical e-stop on the hardware.

**Q: What happens on a stalled motor (the 30-second lock-up story)?**
A stalled DC motor pulls near locked-rotor current → the rail sags → the Pi
browns out/throttles → commands queue for ~30 s. It was an **undervoltage
cascade**, not a code loop. Fix: **stall-disarm** — if the wheels stay frozen
under a drive command for ~3 s, kill the motors and block re-issuing the SAME
direction briefly (a different/escape direction is allowed immediately).

---

## 14. The autonomy demo (SCAN & FIRE)

**Q: Describe the full demo scenario.**
1. **Alpha maps** the area (drive or autonomous) until the map is complete.
2. **Beta SCAN** — sweeps the mapped area on a coverage path, dodging obstacles
   with ultrasonics, and **detects** the fire (camera + YOLO → map marker).
3. **FIRE response** — operator places/confirms the fire; **Alpha drives to it**
   with its lidar, **pumps water for 10 s**, and **returns** to its start.
4. **Gamma** reads gas at the hazard (inspection).
All commanded and coordinated from the one console.

**Q: Why does Beta do SCAN but Alpha does FIRE?**
Task-to-capability matching. SCAN is a broad sweep where small pose drift is
fine and ultrasonic reactive avoidance is enough — Beta. FIRE requires
**precise** navigation to an exact point, which needs reliable localization —
Alpha (lidar SLAM). Putting the pump on the precisely-localizing robot is the
right call.

**Q: How is the coverage (sweep) path generated?**
A **boustrophedon** ("lawnmower") pattern over the free cells of the map
(`dashboard_qt/ui/map/coverage.py`): the free space is eroded by the robot's
clearance (no waypoint on a wall), each row uses its largest open run, unknown
cells are blocked, and the path is capped to a simple handful of sweeps. A* then
stitches the sweep nodes together **through doorways**.

**Q: Is the demo real or simulated?**
The autonomy logic is **real** and runs on the actual robots. We also built a
faithful **simulator** (`--sim`, `dashboard_qt/sim/`) that binds the real
protocol ports and reproduces the physics, so the console and autonomy can be
developed and demoed with **zero hardware** — and it's paced to the wall clock
so it behaves like the real robots.

---

## 15. Software engineering & reliability

**Q: How do you keep the system running (supervision)?**
**systemd** units (`Restart=always`) wrap ROS 2 launch files (`respawn=true`),
so a crashed node or process is **automatically restarted** (target MTTR ≤ ~10
s). Serial links auto-reconnect. A localhost discovery server and preflight
checks run at boot.

**Q: How do you test a robotics system without constantly using hardware?**
We extracted the **pure logic** (protocol, serial parsers, kinematics, planner,
coverage, the navigation fusion math) into a hardware-free library and wrote
**pytest** tests for it (currently **114 passing**), plus the `--sim` simulator
for end-to-end console testing. Hardware-specific tuning stays in config.

**Q: How do you deploy code to the robots?**
Alpha usually has internet → `git pull` + restart its systemd unit. Beta often
has **no internet**, so we deploy by **git bundle over the LAN** (bundle on the
laptop → scp → `git fetch`/merge on Beta → restart). Unit-file changes need a
reinstall step, not just a pull.

**Q: Where is configuration kept?**
A single source of truth in `config/*.yaml` (`fleet.yaml`, `robot1/2/3.yaml`).
Calibration, ports, gains, thresholds all live there; the bridges and firmware
mirror the same numbers so they can't drift apart.

---

## 16. Challenges, trade-offs & design decisions

**Q: What were your biggest challenges?**
1. **WiFi/DDS instability** (the localhost-only interface-tracking bug).
2. **Beta's lidar-less drift** — navigating a map with no absolute reference.
3. **Reactive navigation getting stuck** at doorways/corners (fixed via
   open-side fusion + recovery ladder + decisive turn-around).
4. **Power integrity** — stall brown-outs and an over-voltage event.
5. **Fire detection reliability** — model confidence overlaps false positives.

**Q: What is the single most important design decision?**
**ROS islands + a gateway, with the laptop as the planner.** It made the system
debuggable, robust to WiFi, and let us keep the robots simple and recoverable.

**Q: What trade-offs did you accept?**
- Centralized (laptop) coordination → simpler & robust, but a single point of
  dependence (mitigated by deadman/heartbeat safe-stops).
- Beta lidar-less → cheaper, but drifts (mitigated by SET POSE + drift-tolerant
  planning).
- Conservative speeds → smooth, odometry-safe motion over raw speed.

---

## 17. Limitations & future work

**Q: What are the honest limitations?**
- **Beta's odometry drift** (no lidar/absolute reference) — the core limit.
- **Fire-model confidence** overlaps false positives; needs a better dataset.
- **GY-87 IMU** intermittently drops out (a wiring fix, not yet permanent).
- Centralized coordination — no true decentralized autonomy.

**Q: What would you do next?**
- Give Beta a lidar or visual odometry to remove drift.
- Train a better, higher-confidence fire model on real fire data.
- Permanent IMU 5 V rewire; tuck Alpha's lidar-plane bracket.
- Move toward more on-robot autonomy / decentralized coordination.
- Add automatic frontier exploration so Alpha maps unattended.

---

## 18. Likely "gotcha" / deep-dive questions

**Q: Why is the robot's planning on the laptop and not on the robot?**
Robots have limited CPU and (Beta) poor localization; the laptop has the map,
the compute, and the operator. Keeping the robot executor simple makes it
reliable and recoverable. The robot still owns real-time safety (ultrasonic
stop, watchdog).

**Q: If WiFi drops for 2 seconds, what exactly happens, step by step?**
Drive commands stop arriving → gateway deadman zeroes velocity at ~0.6 s →
Beta's reactive node stops wandering when the heartbeat is stale at ~2 s →
firmware watchdog would stop motors at ~1 s anyway. The robot **holds still**
and resumes cleanly when the link returns; the console shows it STALE → DEAD →
FRESH.

**Q: Two robots, same `/cmd_vel` topic name — how is that not a conflict?**
Because they are **separate ROS graphs** on separate domains, localhost-only.
The topic name is identical but the graphs never meet; only the gateway crosses
to the network, on per-robot ports.

**Q: How accurate is the map, in numbers?**
2.5 cm grid cells; A1M8 range error <1%; nodes registered every ≥10 cm /
≥10°. Wall position is good to a few cm in a well-covered area; unmapped/poorly
covered regions are marked UNKNOWN and treated as blocked by the planner.

**Q: Why 25 cm ultrasonic stop and 60 cm slow — where do those come from?**
They're tuned in `config/robot2.yaml` (`ultrasonic.stop_cm` / `slow_cm`):
25 cm leaves room to stop at Beta's speed without clipping; 60 cm starts a
graceful slow-down so it doesn't slam to a halt. The firmware also enforces a
forward-stop guard independently.

**Q: What is your contribution versus off-the-shelf parts?**
We didn't invent SLAM or YOLO. Our contribution is the **system**: the
gateway/protocol that makes a heterogeneous fleet robust over flaky WiFi, the
laptop-coordinated navigation for a lidar-less robot, the operator console and
autonomy workflow, the layered safety, and a hardware-free test + simulation
setup — integrated into a working emergency-response demo.

**Q: If a committee member presses "this is just teleoperation with extra
steps," how do you respond?**
It is genuinely autonomous at the task level: SCAN plans and follows a coverage
path while reacting to obstacles on its own; FIRE plans and drives a collision-
free route to a detected point, acts (pumps), and returns — the operator
supervises and confirms, but does not drive. The operator-in-the-loop design is
a deliberate **safety** choice for an emergency robot, not a lack of autonomy.

---

## Quick-fire spec sheet (memorize these)

- Robots: **Alpha** (Pi 4, lidar SLAM mapper), **Beta** (Pi 3B+ + Mega,
  intervener, ultrasonics, pump), **Gamma** (ESP32, gas inspector).
- ROS 2 **Humble**; domains **11 / 12**; Gamma = HTTP/JSON.
- Protocol: **msgpack over ZMQ**; ports **5556** telemetry, **5557** map,
  **5558** command (ACKed), **5559** health, **5560** video.
- SLAM: **slam_toolbox** + Ceres, **2.5 cm** grid, **12 m** range,
  scan-matching (no wheel odom on Alpha).
- Beta: 85 mm wheels, **408** ticks/rev, ~0.225 m wheel base, **2 HC-SR04**
  (stop 25 cm / slow 60 cm), **no lidar** → dead-reckoning + SET POSE.
- Planner: **A\*** on the grid, obstacle inflation, soft cost = prefer open
  space.
- Detection: **YOLOv8s** (COCO) primary + **fire.pt** secondary; alarm gate
  0.80.
- Safety: firmware watchdog ~1 s, gateway deadman 0.6 s, heartbeat ~2 s,
  latched E-STOP, pump auto-off 5–10 s.
- Reliability: **systemd** auto-restart, **114** pytest tests, faithful
  **`--sim`**.

---

*Tip for the defense: when you don't know an exact number, give the principle
and the source file ("it's tuned in `config/robot2.yaml`"). Knowing WHERE a
value lives and WHY it exists impresses more than reciting a digit.*
