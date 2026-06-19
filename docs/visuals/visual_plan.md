# Visual & Diagram Plan — Swarm Robot System Graduation Book

A complete, ready-to-generate catalog of the graphics the document needs. Every spec
below is grounded in the **actual system** (ports, models, values), so the output is
technically correct — not generic stock art. Each item has: where it goes, what it must
show, and a **paste-ready prompt** for Claude Design.

---

## 1. How to use this file
- Generate each visual with the **Prompt** block; feed the **Content** bullets as the data.
- Keep the **Global Design System** (§2) identical across every figure for a cohesive book.
- Diagrams marked **[Mermaid]** are cleanest as Mermaid/diagram code; **[Illustration]**
  want a designed SVG/graphic; **[Chart]** are data charts — *use only the real numbers given*.
- Suggested figure numbers slot alongside the existing figures (2.1, 3.1–3.7, 5.1, 5.2);
  renumber sequentially once inserted (see §5).

## 2. Global Design System (apply to ALL visuals)
- **Palette:** primary navy `#1F3864`; neutrals `#44546A` / `#8A94A6` / `#EEF2F8`; white background.
- **Per-robot accent colors (use consistently everywhere):** **Alpha** = blue `#2E6FB7` (mapper), **Beta** = amber-red `#C0504D` (intervener), **Gamma** = green `#4E9A51` (inspector), **Operations Center** = navy `#1F3864`.
- **Typography:** sans-serif, bold titles, regular labels (Calibri-like) to match the book; **all label text dark `#1A1A1A`** (no light-grey body text).
- **Style:** clean, flat, minimal; rounded rectangles (6–8px radius); thin connectors with arrowheads; subtle shadow only on top-level blocks; a small legend when colors carry meaning.
- **Format:** vector **SVG** (export PNG ≥ 300 dpi); white or transparent background; sized to **A4 content width ≈ 16.5 cm** (landscape for architecture/fllow, portrait where it fits).
- **Accessibility:** color-blind-safe (don't rely on color alone — add labels/icons); legible at 100% print.
- **⚠ Data integrity:** charts may use **only** the measured/configured values listed here. Do **not** invent accuracy/mAP/latency numbers. Label each value `measured (sim)`, `configured`, or `acceptance gate`.

---

## 3. Visual Catalog

### A — Problem & Motivation

#### A1. Problem → Solution Infographic  *(the "what we solve" centerpiece)*  [Illustration]
- **Placement:** §1.3 Problem Statement / §1.4 Motivation.
- **Purpose:** one beautiful panel mapping real-world problems to the system's answers.
- **Content (left = Problem → right = Our Solution):**
  - Human responders at risk in hazardous/unknown indoor spaces → **autonomous exploration & mapping (Alpha + SLAM)**.
  - Slow/incomplete area coverage → **boustrophedon SCAN-AREA autonomy**.
  - Undetected fire → **vision fire/smoke/flame detection + GO-TO-FIRE → 5 s water-pump intervention (Beta)**.
  - Invisible gas hazards → **MQ-5 gas sensing with latched alarm (Gamma)**.
  - No shared situational picture → **single operations console with a shared live map**.
  - Fragile field comms → **ROS-island isolation + ACKed ZMQ gateway + 4-layer safety**.
- **Prompt:** "Design a clean, modern flat infographic titled *Problems the Swarm Robot System Solves*. Two columns: left 'Challenge', right 'Our Solution', six paired rows connected by arrows. Use line icons (warning person, grid/coverage, flame, gas cloud, map, network shield). Color-code the solution side by robot: Alpha blue, Beta amber-red, Gamma green, console navy. White background, navy headings, dark labels, generous spacing, A4-landscape. Output SVG."

#### A2. Deployment / Test Scenario Map  [Illustration]
- **Placement:** §1.6 Scope / §5.1.2 Physical Test Environment.
- **Purpose:** show the 4×4 m, 4-room arena with the three robots in action.
- **Content:** top-down floor plan, **4 m × 4 m, four rooms** + doorways; Alpha sweeping a lidar fan mapping walls; Beta en route to a flame icon with a water-spray; Gamma near a gas-cloud icon; operations-center laptop + Wi-Fi router off to the side; legend of robot colors/roles. Scale bar.
- **Prompt:** "Top-down isometric-lite floor plan of a 4 m × 4 m indoor arena divided into four rooms with doorways. Place three robots: a blue mapping robot emitting a 360° lidar fan, an amber-red robot driving toward a flame icon and spraying water, a green robot beside a gas-cloud icon. Show a Wi-Fi router and an operator laptop at the edge. Flat, clean, labeled, scale bar, legend. White bg, dark labels. SVG, A4-landscape."

---

### B — System Architecture

#### B1. Overall Multi-Robot System Architecture  *(upgrades Figure 3.2)*  [Illustration/Mermaid]
- **Placement:** §3.4 System Architecture.
- **Purpose:** the master diagram — three robots, the gateway protocol, and the console.
- **Content:**
  - **Alpha (Pi 4 + Arduino Mega 2560):** RPLIDAR A1M8 → rf2o laser odometry → slam_toolbox; ROS 2 Humble (domain 11); **Gateway**.
  - **Beta (Pi 3B+ + Arduino Mega 2560):** Logitech C270 camera, GY-87 IMU, 25GA370 encoders, 2× HC-SR04, water pump; ROS 2 Humble (domain 12); reactive local-nav; **Gateway**.
  - **Gamma (ESP32):** MQ-5 gas, 1× HC-SR04, MPU6050, buzzer; **HTTP/JSON** (no ROS); OTA.
  - **Operations Center (Windows, PySide6):** state store, A* planner, YOLO worker (subprocess), shared map.
  - **Link:** all robot↔console traffic over a dedicated **Wi-Fi LAN router**; Pis on 5 GHz, Gamma on 2.4 GHz. Show "ROS 2 / DDS stays local to each robot" inside each Pi.
- **Prompt:** "Create a professional system-architecture diagram. Three robot boxes (Alpha=blue, Beta=amber-red, Gamma=green) and one Operations Center box (navy), all connecting to a central Wi-Fi LAN router. Inside Alpha and Beta show a 'ROS 2 (local DDS)' inner box feeding a 'Gateway' edge box; Gamma shows 'HTTP/JSON'. List each robot's key sensors/actuators as small chips. The console box lists: shared map, A* planner, YOLO worker, state store. Label robot↔console links 'msgpack/ZMQ'. Annotate 'Pis: 5 GHz · Gamma: 2.4 GHz'. Flat, rounded boxes, clear arrows, legend. White bg, dark text. SVG, A4-landscape."

#### B2. Communication Protocol Stack  [Illustration/Mermaid]
- **Placement:** §3.6 Communication Design / §4.2.4.
- **Purpose:** show the exact ZMQ channels and patterns.
- **Content (per robot, robot → console unless noted):**
  - `5556` **telemetry** (PUB, `tele.full` 20 Hz + `tele.scan` ≤5 Hz)
  - `5557` **map** (PUB, `map.grid` ≤1 Hz, zlib)
  - `5558` **commands** (ROUTER/DEALER, **ACKed**, dedup, deadman)
  - `5559` **health** (PUB, 1 Hz: temp, throttle, RSSI)
  - `5560` **video** (PUB, JPEG 15 fps)
  - Gamma: HTTP `/telemetry` (3 Hz), `/control?dir=`.
  - All wrapped in a **versioned msgpack envelope**.
- **Prompt:** "Draw a communication-channels diagram between a Robot and the Operations Center. Five labeled ZMQ channels as horizontal lanes: 5556 telemetry (PUB→), 5557 map (PUB→), 5559 health (PUB→), 5560 video (PUB→), and 5558 commands (ROUTER/DEALER, bidirectional with an ACK arrow back). Add a separate small lane for Gamma 'HTTP/JSON /telemetry, /control'. Show a 'msgpack envelope {v, seq, type, payload}' band wrapping them. Direction arrows + rates on each lane. Flat, color-coded by direction, dark labels, white bg. SVG."

#### B3. ROS-Island Isolation & Gateway  [Mermaid/Illustration]
- **Placement:** §3.4 / a callout in §4.2.4.
- **Purpose:** explain the hard-won design — DDS confined to localhost, only the gateway crosses Wi-Fi.
- **Content:** inside each Pi: ROS 2 nodes ↔ DDS bound to `127.0.0.1` (FastDDS UDP whitelist + localhost discovery server, distinct domains 11/12); a single Gateway node bridges ROS↔ZMQ; only ZMQ leaves over Wi-Fi. Caption the rationale (Wi-Fi flaps don't kill local DDS).
- **Prompt:** "Conceptual diagram: two robot 'islands' (rounded containers). Inside each: several ROS 2 node circles connected by a 'DDS (localhost 127.0.0.1)' bus, with a small lock icon labeled 'UDP whitelist + discovery server, domain 11/12'. A 'Gateway (ROS↔ZMQ)' block sits on each island's edge; only its arrow crosses a dashed 'Wi-Fi' boundary to the Operations Center. Minimal, flat, dark labels. SVG."

#### B4. Software Stack / ROS 2 Node Architecture  *(upgrades Figure 3.5)*  [Mermaid]
- **Placement:** §3.5.2 Software Design.
- **Purpose:** layered software view per platform.
- **Content (layers, bottom→top):** Firmware (Mega: motor control, 50 Hz sensor packet; ESP32: HTTP) → Drivers/Bridges (rplidar, robot2_bridge serial, rf2o) → Nav/Perception (slam_toolbox on Alpha; robot2_local_nav reactive fuser on Beta) → Gateway (msgpack/ZMQ) → Operations Center (state store, A* planner, YOLO worker subprocess, PySide6 UI). Note odometry runs **laptop-side** (local_odom).
- **Prompt:** "Layered software-architecture stack (5 horizontal layers) for a multi-robot system: Firmware, Drivers/Bridges, Navigation & Perception, Gateway (msgpack/ZMQ), Operations Center. Put real module names as chips in each layer (rplidar driver, rf2o, robot2_bridge, slam_toolbox, robot2_local_nav, gateway_node, A* planner, YOLO worker, PySide6 UI, laptop-side odometry). Color the Operations-Center layer navy. Clean flat layers with thin dividers, dark labels, white bg. SVG, A4."

#### B5. Per-Robot Hardware Block Diagrams (×3)  [Illustration]
- **Placement:** §3.5.1 Hardware Design (one per robot).
- **Purpose:** wiring/component blocks for Alpha, Beta, Gamma.
- **Content:**
  - **Alpha:** Pi 4 ↔ Arduino Mega 2560 (USB) → 4× JGB37-520 motors via L298N (Hall encoders present but inactive); RPLIDAR A1M8 (USB); 3S LiPo 11.1 V 5200 mAh → XL4015 buck (~5.25 V) → Pi/Mega; motors battery-direct.
  - **Beta:** Pi 3B+ ↔ Mega 2560 (USB) → 4× 25GA370 motors (408 CPR encoders) via L298N; GY-87 IMU (I²C); 2× HC-SR04 (front L/R); Logitech C270 (USB); water pump (relay); 3S LiPo 2200 mAh → XL4015 → logic.
  - **Gamma:** ESP32 → motors; MQ-5 gas; 1× HC-SR04; MPU6050 (I²C); buzzer; 3× 18650 Li-ion.
  - Use icon chips; show bus type on each link (USB, I²C, GPIO, relay, power).
- **Prompt (run 3×, one per robot):** "Hardware block diagram for the [Alpha/Beta/Gamma] robot. Central compute block ([Raspberry Pi 4 / Pi 3B+ / ESP32]) with labeled connections to its sensors and actuators (list provided), each link tagged with its bus (USB, I²C, GPIO, relay, power). Include a small power sub-block (battery → XL4015 buck → logic; motors battery-direct via L298N). Color the robot's accent ([blue/amber-red/green]). Flat, rounded chips, dark labels, white bg. SVG."

#### B6. Power Architecture Diagram  [Illustration/Mermaid]
- **Placement:** §4.1 / Table 4.1.
- **Purpose:** the power tree.
- **Content:** 3S LiPo (11.1 V; Alpha 5200 mAh, Beta 2200 mAh) → split: **direct** to L298N motor drivers + water-pump relay; via **XL4015 5 A adjustable buck (~5.25 V at the Pi pins)** to Pi + Mega logic. Protection: **15 A & 10 A inline fuses**, **1000 µF** filter caps, LED voltmeter. Gamma: 3× 18650 → ESP32. Note delivery-path drop fix + over-voltage lesson as a caption.
- **Prompt:** "Power-distribution tree diagram. Source: 3S LiPo (11.1 V). Two branches: (1) battery-direct to 'L298N motor drivers' and 'water-pump relay'; (2) through an 'XL4015 5 A buck → ~5.25 V' block to 'Raspberry Pi + Arduino Mega'. Add inline-fuse symbols labeled 15 A and 10 A, a 1000 µF capacitor symbol at the buck output, and an LED-voltmeter. Clean electrical-style flat diagram, dark labels, white bg. SVG."

#### B7. Operations-Center Dashboard Layout  *(can replace the Fig 3.6 mockup later)*  [Illustration]
- **Placement:** §3.6 / §4.2.5.
- **Purpose:** annotated wireframe of the PySide6 console.
- **Content:** central **Map** (occupancy grid, robot icons, trails, markers); docks — **Fleet** (status cards), **Live Feed** (video + YOLO boxes), **Operations** (joystick, speed, pump, E-STOP), **Autonomy** (SCAN AREA, GO TO FIRE), **Bottom drawer** (log, detections, diagnostics); top command bar (robot pills, model selector, ALL-STOP).
- **Prompt:** "Annotated UI wireframe of a desktop operations console (dark theme). Central map panel with robot markers and an occupancy grid; left status cards; right docks for Live Video (with detection boxes), Operations (joystick + E-STOP), and Autonomy (SCAN AREA / GO TO FIRE buttons); bottom log/detections drawer; top command bar. Label each region with a callout line. Clean, flat, professional, dark labels on light callouts. SVG, A4-landscape."

---

### C — Pipelines & Flowcharts

#### C1. SLAM & Mapping Pipeline  [Mermaid]
- **Placement:** §4.2.1.
- **Flow:** RPLIDAR A1M8 `/scan` → rf2o laser odometry `/odom` → slam_toolbox (async) → occupancy grid 0.025 m/cell → Gateway `map.grid` (≤1 Hz, zlib) → Operations-Center shared map.
- **Prompt:** "Horizontal flowchart (left→right): RPLIDAR A1M8 /scan → rf2o laser odometry → slam_toolbox (async) → occupancy grid 0.025 m/cell → ZMQ map.grid ≤1 Hz → Operations-Center map. Rounded nodes, labeled arrows, Alpha-blue accent. SVG."

#### C2. Fire-Detection Pipeline (3-stage)  [Mermaid]
- **Placement:** §4.2.2.
- **Flow:** Beta camera → JPEG → ZMQ `video` (5560) → **YOLO worker subprocess** running 3 detectors in parallel: (1) **yolov8s.pt** (COCO: person/dog/cat), (2) **fire.pt** (Fire class only), (3) **classical flame-prop detector** → merge detections → monocular projection (HFOV 62°) → map marker + **alarm if fire ≥ 0.80**.
- **Prompt:** "Flowchart of a vision pipeline: Camera → JPEG → ZMQ video(5560) → 'YOLO worker (crash-isolated subprocess)' fanning into three parallel detectors [yolov8s.pt COCO | fire.pt Fire-only | classical flame-prop] → merge → 'project to map (HFOV 62°)' → two outputs: 'incident marker on map' and 'audible alarm if fire conf ≥ 0.80'. Beta amber-red accent, flat, dark labels. SVG."

#### C3. GO-TO-FIRE Mission Flowchart  [Mermaid]
- **Placement:** §4.3 / §5 demo.
- **Flow:** Operator places fire on map → A* plan (console) → stream waypoint (CMD_GOAL) + heading bias (CMD_NAV_BIAS @10 Hz) → Beta local-nav fuses bias + ultrasonic repulsion → arrived? → **PUMP ON 5 s** → RETURN (A* home) → done. Include the safety branch: heartbeat/deadman lost → STOP.
- **Prompt:** "Decision flowchart for an autonomous fire-response mission: Place fire → A* path (console) → stream goal + 10 Hz heading bias → robot fuses bias with ultrasonic avoidance → decision 'Arrived?' (no→keep driving) → 'Pump ON 5 s' → 'Return home via A*' → End. Add a red safety branch: 'heartbeat/deadman lost → STOP'. Rounded nodes, diamond decisions, Beta amber-red accent, dark labels, white bg. SVG, portrait."

#### C4. SCAN-AREA Coverage Flowchart  [Mermaid]
- **Placement:** §4.3.
- **Flow:** capture Alpha map → erode free space (clearance) → generate **boustrophedon** lane waypoints (0.6 m spacing) → mission executor walks waypoints (skip unreachable) → return to base.
- **Prompt:** "Flowchart: occupancy map → erode for clearance → generate boustrophedon (lawnmower) coverage waypoints (0.6 m lanes) → mission executor follows waypoints, skipping unreachable ones → return to home. Add a tiny inset showing the zig-zag coverage path over a room outline. Flat, dark labels. SVG."

#### C5. Sensor-Fusion / Odometry Flow  [Mermaid]
- **Placement:** §4.2.3 / §3.5.
- **Flow:** Mega 50 Hz packet (encoders + GY-87 gyro) → laptop **complementary filter** (encoder + gyro Z) with **slip gate (0.6 rad/s)** and **gyro_scale 1.0304**; **IMU-dropout → encoder-heading fallback**; output pose (x, y, θ) to shared map.
- **Prompt:** "Data-flow diagram of odometry fusion: '50 Hz serial packet (4 encoders + GY-87 gyro)' → 'complementary filter (encoder + gyro Z)' with side-inputs 'slip gate 0.6 rad/s' and 'gyro scale 1.0304'; a conditional branch 'IMU dropout? → encoder-heading fallback'; output 'pose (x, y, θ) → shared map'. Flat, dark labels. SVG."

#### C6. Four-Layer Deadman Safety Chain  [Mermaid/Illustration]
- **Placement:** §3.7 / §4.3 (strong selling point).
- **Content:** nested timeouts: **Console 10 Hz heartbeat → Gateway 0.6 s → Bridge 0.8 s → Firmware 1.0 s** → motors cut + pump off. Plus E-stop latch and pump 5 s hard cap.
- **Prompt:** "Diagram of a layered safety 'deadman' chain as 4 concentric/cascading timeout stages with their values: Console (10 Hz heartbeat) → Gateway (0.6 s) → Serial Bridge (0.8 s) → Firmware watchdog (1.0 s) → 'motors stop + pump off'. Add two callouts: 'E-STOP latch' and 'pump hard-capped 5 s'. Use a shield motif, navy + red accents, dark labels. SVG."

#### C7. Command ACK / Dedup / Deadman Sequence  [Mermaid]
- **Placement:** §3.6 / §4.2.4.
- **Content:** UML sequence: Console → (DEALER) cmd{cmd_id} → Gateway(ROUTER): dedup check → execute → ACK back; retry on 300 ms timeout (×2); drive-stream + deadman stop on silence.
- **Prompt:** "UML sequence diagram between 'Operations Console' and 'Robot Gateway': console sends cmd with cmd_id (DEALER→ROUTER); gateway checks dedup, executes, returns ACK; show a retry loop '300 ms timeout, ×2'; show a separate 10 Hz drive stream and a 'deadman: stop on silence (0.6 s)'. Clean, standard sequence-diagram style, dark labels. SVG."

#### C8. Stall-Detection / Anti-Lockup State Machine  [Mermaid]
- **Placement:** §4.2.3 / §5.4.2.
- **Content:** States: DRIVING → (encoders frozen >3 s under command) → STALL-DISARM (motors off) → COOLDOWN 2 s (block same direction; allow escape) → back to DRIVING; after 4 stalls/20 s → STUCK (report to console).
- **Prompt:** "State-machine diagram: DRIVING → [encoders frozen > 3 s while commanded] → STALL-DISARM (motors off) → COOLDOWN 2 s (same direction blocked, escape allowed) → DRIVING; transition '4 stalls in 20 s → STUCK (notify operator)'. Rounded state nodes, labeled transitions, dark labels. SVG."

#### C9. Boot & Supervision (systemd)  [Mermaid] *(optional)*
- **Placement:** §4.3 System Integration.
- **Content:** power-on → gp-preflight (oneshot gate) → gp-discovery (localhost DDS) → gp-robotN launch (respawn) + gp-camera (independent); Restart=always; lidar idle hand-off (Alpha).
- **Prompt:** "Boot/supervision flow: Power on → gp-preflight (checks) → gp-discovery (DDS server) → gp-robotN (ROS launch, respawn) and gp-camera (independent) in parallel → running. Note 'Restart=always' and an Alpha-only 'lidar idle hand-off'. Flat, dark labels. SVG."

---

### D — Data Charts (results) — **real values only**

#### D1. Network KPIs vs Acceptance Gates  [Chart]
- **Placement:** §5.3.5 / Table 5.5.
- **Data (sim soak vs gate):** cmd ACK p95 **~13 ms** vs gate **≤150 ms**; telemetry rate **~19.7 Hz** (nominal); video **15.2 fps** vs gate **≥12 fps**; map inter-arrival p95 **~1.0 s** vs gate **≤2.0 s**; telemetry seq loss **0.0 %** (nominal) vs gate **<1 %**.
- **Prompt:** "Grouped bar chart 'Measured (simulation soak) vs Acceptance Gate' for four metrics: ACK latency p95 (13 ms vs 150 ms), video FPS (15.2 vs 12), map inter-arrival p95 (1.0 s vs 2.0 s), telemetry loss (0.0% vs 1%). Two bars per metric (measured = navy, gate = grey). Label values; note 'simulation/loopback'. Clean flat chart, dark labels, white bg. SVG."

#### D2. Heading Drift Before vs After Calibration  [Chart]
- **Placement:** §5.3.3 / Table 5.3.
- **Data:** before gyro calibration **~45°**; after **gyro_scale 1.0304** → **~25°** (multi-turn run). Measured.
- **Prompt:** "Simple two-bar comparison chart 'Heading drift over a multi-turn run': Before calibration ≈ 45°, After gyro-scale 1.0304 ≈ 25°. Down-arrow annotation showing improvement. Navy bars, dark labels, white bg. SVG."

#### D3. Gas Alarm Threshold & Hysteresis  [Chart]
- **Placement:** §5.3.4 / Table 5.4.
- **Data (configured):** alarm at **3000 ADC**, clears below **2000 ADC** (hysteresis), latch **≥10 s**, poll **3 Hz**.
- **Prompt:** "Line/threshold chart of MQ-5 gas ADC vs time (illustrative curve rising then falling) with two horizontal threshold lines: 'Alarm = 3000 ADC' (red) and 'Clear = 2000 ADC' (green), a shaded hysteresis band between them, and a marker 'alarm latched ≥ 10 s'. Label 'polled at 3 Hz'. Mark the curve as illustrative. Clean flat, dark labels. SVG."

#### D4. Detection Confidence Thresholds  [Chart]
- **Placement:** §5.3.2 / §4.2.2.
- **Data (configured):** map-marker floors — person **0.70**, dog/cat/fire **0.60**; audible fire-alarm gate **0.80**.
- **Prompt:** "Horizontal bar chart of configured confidence thresholds: person 0.70, dog 0.60, cat 0.60, fire (map marker) 0.60, fire (audible alarm) 0.80. Highlight the 0.80 alarm gate. Range 0–1. Navy bars, dark labels, white bg. SVG."

#### D5. Pipeline Throughput / Latency Summary  [Chart] *(optional)*
- **Placement:** §5.3.2 / §5.3.5.
- **Data:** video pipeline **15.2 fps (sim)** ≥ 12 gate; ACK p95 ~13 ms; map ~1.0 s. (Same sources as D1 — combine only if not redundant.)

---

### E — Conceptual & Project

#### E1. Robot Roles Overview  [Illustration]
- **Placement:** §1.1 / §3.1.
- **Content:** three cards — **Alpha: Mapper** (Pi 4, RPLIDAR, SLAM), **Beta: Intervener** (Pi 3B+, camera, pump, fire), **Gamma: Inspector** (ESP32, MQ-5 gas) — with role icon, key hardware, one-line job. Robot accent colors.
- **Prompt:** "Three clean role-cards side by side: 'Alpha — Mapper' (blue, lidar icon), 'Beta — Intervener' (amber-red, flame+water icon), 'Gamma — Inspector' (green, gas icon). Each card: robot name, brain (Pi 4 / Pi 3B+ / ESP32), 3 key components, one-line mission. Flat, rounded cards, dark labels, white bg. SVG, A4-landscape."

#### E2. Shared-Map / Frame Alignment Concept  [Illustration] *(optional)*
- **Placement:** §3.4 design notes.
- **Content:** Alpha's SLAM frame = world; Beta/Gamma aligned into it via operator **SET POSE**; all poses + detections shown on one map.
- **Prompt:** "Concept diagram: one shared world map (Alpha's SLAM frame). Show Beta and Gamma being 'aligned' into it via a 'SET POSE' transform arrow, with all three robot icons + a fire/gas marker on the single map. Flat, dark labels. SVG."

#### E3. Project Timeline / Gantt  [Chart]
- **Placement:** §3.1.2 Project Timeline and Gantt Chart.
- **Content:** phases over ~8 months — Research/Lit Review → Hardware build → Firmware → SLAM → Detection → Comms/Gateway → Dashboard → Integration → Testing → Writing. (Use your real dates/durations; placeholder months otherwise — mark as such.)
- **Prompt:** "Horizontal Gantt chart of project phases across 8 months (M1–M8): Literature Review, Hardware Build, Firmware, SLAM, Object Detection, Communication/Gateway, Dashboard, Integration, Testing, Documentation — overlapping bars. Navy bars, month grid, dark labels, white bg. SVG, A4-landscape. (Durations are placeholders to be confirmed.)"

#### E4. Robot Operating-Mode State Diagram  [Mermaid] *(optional)*
- **Placement:** §3.5.2 / §4.2.5.
- **Content:** IDLE ↔ MANUAL (teleop) ↔ AUTONOMOUS (scan / go-to-fire); any state → **E-STOP (latched)** → release → IDLE.
- **Prompt:** "State diagram of robot operating modes: IDLE ↔ MANUAL (joystick/WASD) ↔ AUTONOMOUS (SCAN / GO-TO-FIRE); from any state an 'E-STOP (latched)' transition → after release → IDLE. Rounded states, dark labels. SVG."

#### E5. Use-Case / Functional-Requirements Diagram  [Mermaid] *(optional)*
- **Placement:** §3.3.2 Functional Requirements.
- **Content:** Actor 'Operator' → use cases: Drive robot, Start SCAN, Trigger GO-TO-FIRE, Monitor map/video, Acknowledge alerts, E-STOP. Actor 'System' → Map area, Detect fire/gas, Navigate, Pump.
- **Prompt:** "UML use-case diagram: actor 'Operator' connected to ovals (Teleoperate, Start Area Scan, Trigger Fire Response, Monitor Map & Video, Acknowledge Alerts, Emergency Stop); actor 'Robot System' connected to (Map Environment, Detect Fire/Gas, Autonomous Navigation, Water-Pump Intervention). Standard UML style, dark labels. SVG."

---

## 4. Priority (if generating in batches)
1. **A1** Problem→Solution infographic, **B1** overall architecture, **E1** robot roles — highest impact / most-seen.
2. **B2, B4, C2, C3, C6** — core technical credibility (protocol, software, detection, mission, safety).
3. **B5, B6, C1, C5, D1, D2** — depth (hardware, power, pipelines, results).
4. Remaining (B3, B7, C4, C7–C9, D3–D5, E2–E5) as time allows.

## 5. Figure numbering & integration
- Existing figures: 2.1, 3.1–3.7, 5.1, 5.2. Insert new ones in their sections and **renumber sequentially per chapter** (e.g., new architecture set becomes 3.x; pipeline/flow set 4.x; result charts 5.x).
- After inserting figures, the **List of Figures + page numbers shift** — tell me and I'll re-run the figure-list/TOC page-number pass and regenerate the PDF.
- Keep captions in the book's style ("Figure X.Y — Title", centered, dark).

## 6. Production checklist (per visual)
- [ ] Uses the §2 palette + robot accent colors consistently
- [ ] All labels dark, legible at print size, A4 content width
- [ ] Exported as SVG (+ 300 dpi PNG fallback)
- [ ] Any numbers match the **real values** in this file (measured / configured / gate) — nothing invented
- [ ] Caption + figure number added; List of Figures updated
