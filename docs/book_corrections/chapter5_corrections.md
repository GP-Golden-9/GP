# Chapter 5 (Testing, Results & Evaluation) — Paste-Ready Corrections

Audit-driven corrections for `book_ch5.txt`. Every value below is traced to a repo
artifact and labeled **measured**, **configured (design target)**, or
**Not measured**. No experimental results were invented. Cells with no basis in the
repo are explicitly left as "Not measured" — see Section C (Integrity Note).

Evidence files consulted:
`CLAUDE.md`, `config/fleet.yaml`, `config/robot1.yaml`, `config/robot2.yaml`,
`config/robot3.yaml`, `common/gpcore/protocol/channels.py`, `tools/soak_test.py`,
`tools/yaw_calib.py`, `docs/baseline/soak_127_0_0_1_*.json`,
`docs/baseline/README.md`, `docs/field_fixes_and_runbook_2026-06-18.md`,
`tests/test_*.py` (13 modules).

---

## (A) PROSE FIND / REPLACE EDITS

### A1. Pytest count and omitted modules (§5.1.1, line ~48)

**FIND:**
> the software logic was validated using an automated test suite of 91 pytest unit and integration tests. This logic verification suite ran on both Windows and the Pi platforms, testing serialization envelopes (for sequence numbering and integrity), serial bridge packet parsers, differential-drive odometry math, A* route planner optimization, rigid 2D map coordinate projections, and alert latching debounces.

**REPLACE:**
> the software logic was validated using an automated pytest suite of **106 test functions across 13 test modules**. This logic verification suite ran on both Windows and the Pi platforms, covering: serialization envelopes for sequence numbering and integrity (`test_envelope`), serial-bridge packet parsing and command framing (`test_mega_parser`, `test_mega_commands`, `test_commands`), differential-drive odometry math (`test_diff_drive`), the goto controller and Beta's reactive local navigation (`test_goto_controller`, `test_local_nav`), A* route-planner optimization (`test_planner`), rigid 2D map coordinate projection (`test_projection`), coverage-path generation for SCAN AREA (`test_coverage`), gateway msgpack-over-ZMQ round-trips (`test_gateway_roundtrip`), config loading from `config/*.yaml` (`test_config_loader`), and alert-latching debounces (`test_alerts`).

**EVIDENCE:** `grep -c "def test_" tests/*.py` = 106 across 13 files
(`test_projection` 7, `test_planner` 7, `test_mega_parser` 8, `test_mega_commands` 8,
`test_local_nav` 12, `test_commands` 8, `test_envelope` 9, `test_alerts` 9,
`test_diff_drive` 9, `test_goto_controller` 8, `test_config_loader` 6,
`test_gateway_roundtrip` 7, `test_coverage` 8).

---

### A2. Alpha hardware misattributed (§5.1.3, lines ~79-80)

**FIND:**
> Alpha was equipped with a Raspberry Pi 4 (8 GB RAM), an Arduino Mega 2560 (with encoders unused), an RPLidar A1M8, and ran ROS 2 Humble.

**REPLACE:**
> Alpha was equipped with a Raspberry Pi 4 (8 GB RAM) and an RPLidar A1M8, and ran ROS 2 Humble. Alpha has **no Arduino Mega and no wheel encoders**; it derives its motion estimate from **rf2o laser odometry** (scan-matching on the RPLidar stream) rather than dead reckoning.

**EVIDENCE:** `CLAUDE.md` fleet table — robot1 "Alpha | Pi 4 | RPLIDAR A1M8, rf2o
laser odometry, no wheel encoders." Only Beta has the Mega + encoders.
`config/robot1.yaml` declares `lidar:` but no `drive` encoder block.

---

### A3. Detection model naming (§5.2.2 lines ~113-114; Table 5.2 title line ~231; §5.4.1 line ~439)

**FIND (§5.2.2):**
> The visual hazard detection pipeline used YOLO-based fire, smoke, and flame models (defaulting to fire.pt) over a ZeroMQ video stream.

**REPLACE:**
> The visual hazard detection pipeline ran YOLOv8 on the operator laptop. The **primary model is `yolov8s.pt`** (clean COCO classes — person/dog/cat), and **`fire.pt` is a secondary, fire-only network** whose only trusted output is its `Fire` class. `fire.pt` is never used as the primary model because its fire fine-tune degraded its COCO classes (it scored 0% on a person that `yolov8s.pt` detected at 92%). The console restricts inference to the classes `person, dog, cat, fire`.

**FIND (Table 5.2 title, line ~231):**
> Table 5.2: YOLOv8n Object Detection Results

**REPLACE:**
> Table 5.2: Object Detection Results (primary yolov8s.pt + secondary fire.pt)

**FIND (§5.4.1, line ~439):**
> Offloading YOLO inference to a crash-isolated child process running fire.pt on the laptop proved highly effective.

**REPLACE:**
> Offloading YOLO inference to a crash-isolated child process on the laptop (primary `yolov8s.pt`, with `fire.pt` as a secondary fire-only detector) proved highly effective.

**EVIDENCE:** `config/fleet.yaml`: `default_model: yolov8s.pt`,
`fire_model: fire.pt # secondary; only its 'Fire' class is trusted`, plus the
inline note "On a real backlit frame fire.pt scored 0% on a person that yolov8s got
92% on."

---

### A4. Fire confidence threshold and alarm gate (§5.3.2, lines ~229-230)

**FIND:**
> Confidence thresholds in config/fleet.yaml (defaulting to 0.60) were balanced to optimize detection accuracy while preventing false positives from common objects.

**REPLACE:**
> Per-class map-marker confidence floors live in `config/fleet.yaml` (person 0.70; dog/cat/fire 0.60). The **audible fire-alarm gate is separate and set to 0.80** (`fire_conf_min`), raised after night-room testing produced false alarms in the 26-39% range. An important honest caveat: `fire.pt`'s measured confidence on **real fire photos is only 28-37%**, so at the 0.80 alarm gate the audible alarm essentially never triggers with the current model — the detections panel still lists everything the model sees, and the F9 key drills the alarm UX. The fix is a better-trained model, not a lower threshold.

**EVIDENCE:** `config/fleet.yaml`: `fire_conf_min: 0.80`; `detect.conf` block
(person 0.70, dog 0.60, cat 0.60, fire 0.60); inline comment "fire.pt's measured
confidence on REAL fire photos is 28-37% — at 0.80 the audible alarm will
essentially never trigger."

---

### A5. Gas polling rate (§5.3.4, lines ~310-313)

**FIND:**
> The raw ADC values were polled by the dashboard's Esp32Link at 2 Hz, triggering a latched local alarm buzzer on the robot and a pulsing warning banner on the PySide6 console when exceeding the 3000 ADC count threshold.

**REPLACE:**
> The raw ADC values were polled by the dashboard's Esp32Link at **3 Hz**, triggering a latched local alarm buzzer on the robot and a pulsing warning banner on the PySide6 console when exceeding the 3000 ADC-count alarm threshold.

**EVIDENCE:** `config/robot3.yaml`: `http.poll_hz: 3`; `gas.alarm_threshold: 3000`.

---

### A6. Gamma localization mischaracterized (§5.4.2, lines ~451-454)

**FIND:**
> Odometry and Wheel Slip: Localization on Beta and Gamma relies on dead-reckoning. Rotational drift was mitigated by complementary gyro fusion, but translational wheel slip still accumulates error over long explorations. Frequent coordinate set-pose updates on the dashboard are required to align non-mapping robots with the global map frame.

**REPLACE:**
> Odometry and Wheel Slip: **Beta's** localization relies on dead reckoning — a complementary fusion of its 25GA370 wheel encoders and the GY-87 gyro Z-rate, computed laptop-side. Rotational drift was mitigated by gyro fusion and per-unit scale calibration, but translational wheel slip still accumulates error over long explorations, so frequent set-pose updates on the dashboard are required to align Beta with Alpha's global map frame. **Gamma is not a ROS robot and runs none of Beta's odometry stack**; it is a non-ROS ESP32 inspector exposing an HTTP/JSON telemetry endpoint, and its reported pose is the ESP32's own coarse estimate, not the encoder/IMU complementary filter used on Beta.

**EVIDENCE:** `CLAUDE.md` fleet table — Gamma "ESP32 | Inspector ... HTTP UI";
"Gamma is not ROS — plain HTTP/JSON, wrapped laptop-side." `config/robot3.yaml`
`kind: esp32`, all `zmq` ports 0. Beta's odometry stack
(`dashboard_qt/state/local_odom.py`, `navigation/robot2_local_nav.py`) is robot2-only.

---

### A7. Beta ultrasonics — FLAT ERROR (§5.4.2, lines ~464-467)

**FIND:**
> Beta Ultrasonics: Although the forward-collision slowdown and obstacle avoidance guards are implemented in Beta's bridge and firmware, the physical sensors were not wired in the current build, requiring the operator to maintain active manual supervision around obstacles.

**REPLACE:**
> Beta Ultrasonics: Beta carries **two forward-facing HC-SR04 ultrasonic sensors that are wired and active** in the current build (LEFT TRIG=30/ECHO=31, RIGHT TRIG=32/ECHO=33, 5 V), mounted at the front edge and tilted slightly outward for field of view. The firmware median-filters them and appends the ranges to the serial packet; the bridge publishes `/ultrasonic/{left,right}`, hard-stops forward motion under 25 cm (re-enabling above 40 cm with hysteresis), and the goto controller begins a proportional slow-down under 60 cm. These are Beta's only real-time obstacle sense (it has no lidar).

**EVIDENCE:** `config/robot2.yaml` `ultrasonic.enabled: true` with
`stop_cm: 25`, `clear_cm: 40`, `slow_cm: 60`, and the wiring comment
"LEFT TRIG=30 ECHO=31  RIGHT TRIG=32 ECHO=33." `CLAUDE.md` open tickets:
"Beta ultrasonics: WIRED (2 front HC-SR04 ... 5 V) ... Forward-stop guard +
graceful slowdown live."

---

### A8. The "continuous 30-minute test" (§5.2.4 lines ~145-149; §5.3.5 intro)

**FIND (§5.2.4):**
> Network stability was evaluated by measuring bandwidth, latency, and packet success across the ZeroMQ gateway channels (telemetry, map, commands, health, and video) during a continuous 30-minute test.
> ... during a continuous 30-minute operating window.

**REPLACE:**
> Network stability was evaluated with the protocol soak harness (`tools/soak_test.py`), which measures telemetry sequence-loss, video FPS and capture-age, map and health inter-arrival gaps, and command-to-ACK round-trip time against fixed acceptance gates. **A full 30-minute real-robot soak has not yet been performed; the recorded baseline artifacts are short (~0.4-minute) runs against the in-process simulator (`127.0.0.1`)**, so the network numbers below are reported as sim-soak measurements and acceptance-gate targets, not as a 30-minute field run.

**EVIDENCE:** `docs/baseline/` contains only two artifacts, both
`"host": "127.0.0.1"`, `"minutes": 0.4`. `tools/soak_test.py` default is 30 min
but no 30-min/real-host JSON exists. `docs/baseline/README.md` describes a planned
"30 min per robot" probe that has not been captured here.

---

## (B) CORRECTED TABLES

Legend for every cell: **[M]** = measured (with artifact); **[C]** = configured /
design target (from config, not a measurement); **[NM]** = Not measured (no
evaluation pipeline / no artifact in repo).

### Table 5.1 — SLAM and Mapping Performance

| Metric | Expected / Physical | Result | Basis & Source |
|---|---|---|---|
| Test area dimensions | 4.00 m x 4.00 m | **[NM]** Not measured — no map-vs-ground-truth artifact in repo | — |
| Grid resolution | 0.025 m/cell | **[C]** 0.025 m/cell (configured) | slam_toolbox config; stated in §5.3.1 |
| Map update rate | <= 1.0 Hz | **[C]** <= ~1 Hz (design target) | `common/gpcore/protocol/channels.py`: `PORT_MAP 5557 ... map.grid @ ~1 Hz` |
| Map dimensional accuracy | N/A | **[NM]** Not measured — no labeled / surveyed reference map | — |
| Map generation time | N/A | **[NM]** Not measured | — |

> Note: SLAM ran via `async_slam_toolbox_node` with rf2o laser odometry on Alpha
> (no encoders). The only quantitative SLAM facts the repo supports are the
> **configured** grid resolution and the **configured** map-publish ceiling.

### Table 5.2 — Object Detection (primary yolov8s.pt + secondary fire.pt)

| Test Condition | FPS | Detection Accuracy (%) | mAP (IoU=0.50) (%) | Confidence Threshold | Basis & Source |
|---|---|---|---|---|---|
| Well-lit (static) | **[M]** ~15.25 fps end-to-end pipeline (sim) | **[NM]** Not measured | **[NM]** Not measured | **[C]** alarm gate 0.80; per-class floors person 0.70 / fire 0.60 | fps from `docs/baseline/soak_*.json` `video_fps: 15.25` (sim); thresholds `config/fleet.yaml` |
| Well-lit (moving) | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | as above | — |
| Dimly lit (static) | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | as above | — |
| Aggregate avg | KPI target >= 12 fps | **[NM]** Not measured | **[NM]** Not measured | — | gate `tools/soak_test.py` `video_fps >= 12` |

> **Detection accuracy and mAP cannot be filled** — there is **no labeled
> evaluation set and no mAP harness in the repo**. Qualitative observation only
> (from `config/fleet.yaml`, label it as such): `fire.pt`'s confidence on real
> fire photos is **28-37%**, below the 0.80 alarm gate. The ~15.25 fps figure is
> the streaming/pipeline frame rate from the SIM soak, not a model-throughput
> benchmark.

### Table 5.3 — Localization and Odometry (Beta)

| Trajectory Type | Distance | Translation RMSE | Rotational Drift | Basis & Source |
|---|---|---|---|---|
| Linear fwd/reverse | 4.0 m | **[NM]** Not measured | **[M]** see calibration result below | — |
| Square path (4 x 90 deg) | 12.0 m | **[NM]** Not measured | **[M]** see calibration result below | — |
| Complex room exploration | ~25.0 m | **[NM]** Not measured | **[M]** see calibration result below | — |

**Measured rotational-drift result (the one real metric available):**

| Quantity | Value | Basis & Source |
|---|---|---|
| Yaw drift before calibration | **[M]** ~45 deg | `docs/field_fixes_and_runbook_2026-06-18.md` (sec. "Yaw drift (~45 deg, then ~25 deg after calibration)") |
| Yaw drift after calibration | **[M]** ~25 deg residual | same runbook section |
| Gyro calibration measurement | **[M]** read 1048.2 deg for 1080 deg actual (3 turns) -> factor 1080 / 1048.2 = **1.0304** | `tools/yaw_calib.py` run noted in `config/robot2.yaml` comment; `gyro_scale_correction: 1.0304` |
| Wheel diameter | **[C]** 0.085 m | `config/robot2.yaml` `drive.wheel_diameter_m` |
| Ticks per wheel-rev | **[C]** 408 (12 PPR x 34:1) | `config/robot2.yaml` `drive.ticks_per_rev` |
| Wheel base (contact spacing) | **[C]** 0.225 m | `config/robot2.yaml` `drive.wheel_base_m` |

> Translational RMSE is **Not measured** — no trajectory ground-truth artifact
> exists in the repo. The only quantitative localization result is the gyro
> scale-calibration that cut residual yaw drift from ~45 deg to ~25 deg.

### Table 5.4 — MQ-5 Gas Sensor Performance (Gamma)

| Hazard Type | Baseline (ADC) | Peak Detected (ADC) | Response Time | Publish Latency | Basis & Source |
|---|---|---|---|---|---|
| Clean air (control) | **[NM]** Not measured | — | N/A | **[NM]** Not measured | — |
| Simulated smoke | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | — |
| Butane gas burst | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | **[NM]** Not measured | — |

**Configured gas thresholds (design targets, not measurements):**

| Parameter | Value | Source |
|---|---|---|
| Alarm threshold | **[C]** 3000 ADC | `config/robot3.yaml` `gas.alarm_threshold` |
| Clear (hysteresis) threshold | **[C]** 2000 ADC | `config/robot3.yaml` `gas.clear_threshold` |
| Alarm latch minimum | **[C]** >= 10 s | `config/robot3.yaml` comment "alarm also latches >= 10 s" |
| Poll rate | **[C]** 3 Hz | `config/robot3.yaml` `http.poll_hz` |

> **Baseline ADC, peak ADC, response time, and publish latency are Not
> measured** — there is no gas-exposure measurement artifact in the repo. Only
> the configured thresholds and poll rate are reportable.

### Table 5.5 — Network Communication Metrics

| Data Stream | Protocol / Port | Bandwidth | Latency | Packet Success | Basis & Source |
|---|---|---|---|---|---|
| Motion control (cmd.drive) | ZMQ ROUTER/DEALER (5558) | **[NM]** Not measured | **[M]** cmd->ACK p95 12.7-13.3 ms (sim); **[C]** gate <= 150 ms | **[M]** ack_count 50/run (sim) | `docs/baseline/soak_*.json` `ack_p95_ms`; gate `tools/soak_test.py` |
| Sensor telemetry (tele.full) | ZMQ PUB (5556) | **[NM]** Not measured | rate ~19.6-19.7 Hz (sim) | **[M]** seq loss 0.0% (clean run) / 20.7% (a degraded sim run); **[C]** gate < 1% | `docs/baseline/soak_*.json` `tele_loss_pct`, `tele_rate_hz` |
| Compressed video (port 5560) | ZMQ PUB (5560) | **[NM]** Not measured (no MB/s tool) | **[M]** ~15.25 fps; capture-age p95 0.1-0.2 ms (sim, local loopback); **[C]** gate fps >= 12, age p95 <= 350 ms | **[M]** video_fps 15.25 (sim) | `docs/baseline/soak_*.json` `video_fps`, `video_age_p95_ms` |
| SLAM map updates (map.grid) | ZMQ PUB (5557) | **[NM]** Not measured | **[M]** inter-arrival p95 ~1.01 s (sim); **[C]** gate <= 2.0 s | **[M]** map gaps observed (sim) | `docs/baseline/soak_*.json` `map_gap_p95_s`; channels.py "~1 Hz" |

> **Acceptance gate targets** (`tools/soak_test.py`): tele seq loss < 1%; video
> fps >= 12; video capture-age p95 <= 350 ms; map inter-arrival p95 <= 2.0 s;
> cmd->ACK p95 <= 150 ms; health gap p95 <= 2.5 s.
> **Sim-soak measurements** are from two ~0.4-minute runs vs `127.0.0.1`
> (loopback, in-process sim): one PASSED all gates, the other FAILED on telemetry
> loss (20.7%). These are SIM numbers over loopback, NOT real-robot WiFi figures.
> **Per-stream bandwidth in MB/s is Not measured** — no tool in the repo computes
> per-channel byte throughput.

---

## (C) ACADEMIC-INTEGRITY NOTE — cells that MUST stay "Not measured"

The following cells have **no factual basis anywhere in the repo** and must remain
"Not measured" (or "Not measured — no evaluation pipeline in repo"). Filling them
with any number would be fabrication:

1. **Detection accuracy (%) and mAP@0.50 (Table 5.2, all rows).** There is no
   labeled evaluation/validation set and no mAP-scoring harness in the repo. The
   only honest detection figure is the **qualitative** note that `fire.pt` reads
   28-37% confidence on real fire (from `config/fleet.yaml`), which must be
   labeled "observed/qualitative," not a measured accuracy metric.

2. **Gas response time, baseline ADC, and peak ADC (Table 5.4).** No
   gas-exposure measurement artifact exists. Only the configured thresholds
   (alarm 3000, clear 2000, latch >= 10 s, poll 3 Hz) are reportable, and only as
   **configured design values**.

3. **Per-stream bandwidth in MB/s (Table 5.5, all rows).** No tool measures
   per-channel byte throughput; `soak_test.py` measures rates, loss, latency and
   gaps — not bandwidth.

4. **Map dimensional accuracy / dimensional error and map generation time
   (Table 5.1).** No surveyed reference map or timing artifact exists.

5. **Translational RMSE (Table 5.3, all trajectories).** No trajectory
   ground-truth artifact exists. Only the rotational-drift calibration
   (45 deg -> 25 deg via factor 1.0304) is a real measured result.

Additionally, all numbers carried from `docs/baseline/soak_*.json` MUST be labeled
**"SIM soak, ~0.4 min vs 127.0.0.1 (loopback)"** — they are not real-robot WiFi
measurements, and one of the two runs failed its telemetry-loss gate.

---

## (D) §5.4.2 — Honest limitations to ADD

Append these to the limitations list (they are real, sourced, and currently omitted):

- **GY-87 IMU intermittent I2C dropout (top hardware ticket).** Beta's GY-87
  intermittently drops off the I2C bus on a marginal power line; when it does, the
  firmware streams frozen non-zero gyro values, heading freezes, and the map arrow
  goes static until a power-cycle. An encoder-heading fallback keeps driven turns
  working during a dropout. Pending fix: rewire VCC 3.3 V -> 5 V and resolder.
  (`CLAUDE.md`, `docs/field_fixes_and_runbook_2026-06-18.md`.)

- **Gamma over-voltage hardware damage.** A buck regulator set to 10 V was
  connected to Gamma's ESP32 + IMU + MQ sensor (2026-06-13). The ESP32 survived,
  but the **onboard IMU is likely dead** (firmware tolerates its absence) and the
  MQ sensor needs re-verification. This degrades Gamma's onboard sensing.
  (`CLAUDE.md`.)

- **Fire-detection model weakness.** `fire.pt` reads only 28-37% confidence on
  real fire, well below the 0.80 alarm gate, so the audible fire alarm will rarely
  trigger with the current model; reliable fire alarming requires a
  better-trained model. (`config/fleet.yaml`.)

- **Residual yaw drift (~25 deg).** Even after gyro scale calibration, ~25 deg of
  rotational drift remains over a multi-turn run.
  (`docs/field_fixes_and_runbook_2026-06-18.md`.)

- **LAN-only operation, no GPS / no global localization.** The system runs over a
  dedicated offline LAN router with no internet and no GPS; all localization is
  relative (Alpha's SLAM map + Beta's dead reckoning), so absolute positioning is
  unavailable. (`CLAUDE.md`.)

- **No 30-minute real-robot soak yet.** Network KPIs are validated only against
  the sim over loopback; a full 30-minute real-robot field soak with the
  kill/recovery drills has not been recorded. (`docs/baseline/`.)
