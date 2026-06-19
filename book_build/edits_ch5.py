# -*- coding: utf-8 -*-
# Chapter 5 verified edit list -- machine-applyable against the real Word document.
#
# Built from docs/book_corrections/chapter5_corrections.md (honest, repo-traced
# corrections) verified against docx_paras.txt (Pxxxxx prose lines) and
# docx_tables.txt (current cell text).
#
# ACADEMIC INTEGRITY: every filled table cell below is either
#   (a) traced to a repo artifact (measured, tagged "(sim)"/"(gate)"),
#   (b) a configured design value (tagged "(configured)"), or
#   (c) "Not measured".
# No experimental result is fabricated.
#
# Each "para" find string was verified to occur EXACTLY ONCE as a contiguous
# substring of a single Pxxxxx paragraph line in docx_paras.txt.
#
# Table mapping (verified against docx_tables.txt):
#   Table 12 = Book 5.1 SLAM        (5x4)  rows 1-4 data, row 0 header
#   Table 13 = Book 5.2 detection   (5x5)
#   Table 14 = Book 5.3 localization(4x4)
#   Table 15 = Book 5.4 gas         (4x5)
#   Table 16 = Book 5.5 network     (5x5)

EDITS = [
    # ------------------------------------------------------------------ #
    # (A) PROSE EDITS                                                     #
    # ------------------------------------------------------------------ #

    # A1 -- pytest count + omitted modules (P01123)
    {
        "type": "para",
        "find": "the software logic was validated using an automated test suite of 91 pytest unit and integration tests. This logic verification suite ran on both Windows and the Pi platforms, testing serialization envelopes (for sequence numbering and integrity), serial bridge packet parsers, differential-drive odometry math, A* route planner optimization, rigid 2D map coordinate projections, and alert latching debounces.",
        "replace": "the software logic was validated using an automated pytest suite of 106 test functions across 13 test modules. This logic verification suite ran on both Windows and the Pi platforms, covering serialization envelopes for sequence numbering and integrity (test_envelope), serial-bridge packet parsing and command framing (test_mega_parser, test_mega_commands, test_commands), differential-drive odometry math (test_diff_drive), the goto controller and Beta's reactive local navigation (test_goto_controller, test_local_nav), A* route-planner optimization (test_planner), rigid 2D map coordinate projection (test_projection), coverage-path generation for the SCAN AREA mode (test_coverage), gateway msgpack-over-ZMQ round-trips (test_gateway_roundtrip), config loading from config/*.yaml (test_config_loader), and alert-latching debounces (test_alerts).",
        "expect": 1,
        "note": "A1: 91 -> 106 functions across 13 modules; names the previously omitted modules. Evidence: grep -c 'def test_' tests/*.py = 106.",
    },

    # A2 -- Alpha hardware misattribution (P01130)
    {
        "type": "para",
        "find": "Alpha was equipped with a Raspberry Pi 4 (8 GB RAM), an Arduino Mega 2560 (with encoders unused), an RPLidar A1M8, and ran ROS 2 Humble.",
        "replace": "Alpha was equipped with a Raspberry Pi 4 (8 GB RAM) and an RPLidar A1M8, and ran ROS 2 Humble. Alpha has no Arduino Mega and no wheel encoders; it derives its motion estimate from rf2o laser odometry (scan-matching on the RPLidar stream) rather than dead reckoning.",
        "expect": 1,
        "note": "A2: Alpha has no Mega/encoders; uses rf2o laser odometry. Evidence: CLAUDE.md fleet table; config/robot1.yaml.",
    },

    # A3a -- detection model naming, body (P01138)
    {
        "type": "para",
        "find": "The visual hazard detection pipeline used YOLO-based fire, smoke, and flame models (defaulting to fire.pt) over a ZeroMQ video stream.",
        "replace": "The visual hazard detection pipeline ran YOLOv8 on the operator laptop. The primary model is yolov8s.pt (clean COCO classes -- person/dog/cat), and fire.pt is a secondary, fire-only network whose only trusted output is its Fire class. fire.pt is never used as the primary model because its fire fine-tune degraded its COCO classes (it scored 0% on a person that yolov8s.pt detected at 92%). The console restricts inference to the classes person, dog, cat, and fire.",
        "expect": 1,
        "note": "A3: YOLOv8n/fire.pt-default -> yolov8s.pt primary + fire.pt secondary. Evidence: config/fleet.yaml default_model/fire_model.",
    },

    # A3b -- Table 5.2 caption text (P01184)
    {
        "type": "para",
        "find": "Table 5.2: YOLOv8n Object Detection Results",
        "replace": "Table 5.2: Object Detection Results (primary yolov8s.pt + secondary fire.pt)",
        "expect": 2,
        "note": "A3: Table 5.2 caption -- occurs twice (TOC list of figures P00162 and caption P01184); replace both. Drops 'YOLOv8n'.",
    },

    # A3c -- crash-isolated child process running fire.pt (P01224)
    {
        "type": "para",
        "find": "Offloading YOLO inference to a crash-isolated child process running fire.pt on the laptop proved highly effective.",
        "replace": "Offloading YOLO inference to a crash-isolated child process on the laptop (primary yolov8s.pt, with fire.pt as a secondary fire-only detector) proved highly effective.",
        "expect": 1,
        "note": "A3: removes 'running fire.pt' as the sole model. Evidence: config/fleet.yaml.",
    },

    # A4 -- confidence threshold / alarm gate (P01183)
    {
        "type": "para",
        "find": "Confidence thresholds in config/fleet.yaml (defaulting to 0.60) were balanced to optimize detection accuracy while preventing false positives from common objects.",
        "replace": "Per-class map-marker confidence floors live in config/fleet.yaml (person 0.70; dog/cat/fire 0.60). The audible fire-alarm gate is separate and set to 0.80 (fire_conf_min), raised after night-room testing produced false alarms. An honest caveat: fire.pt's measured confidence on real fire photos is only 28-37%, so at the 0.80 alarm gate the audible alarm essentially never triggers with the current model; the detections panel still lists everything the model sees, and the F9 key drills the alarm UX. The fix is a better-trained model, not a lower threshold.",
        "expect": 1,
        "note": "A4: documents per-class floors + 0.80 fire alarm gate + honest 28-37% caveat. Evidence: config/fleet.yaml fire_conf_min/detect.conf.",
    },

    # A5 -- gas polling rate 2 Hz -> 3 Hz (P01198)
    {
        "type": "para",
        "find": "The raw ADC values were polled by the dashboard's Esp32Link at 2 Hz, triggering a latched local alarm buzzer on the robot and a pulsing warning banner on the PySide6 console when exceeding the 3000 ADC count threshold.",
        "replace": "The raw ADC values were polled by the dashboard's Esp32Link at 3 Hz, triggering a latched local alarm buzzer on the robot and a pulsing warning banner on the PySide6 console when exceeding the 3000 ADC-count alarm threshold.",
        "expect": 1,
        "note": "A5: 2 Hz -> 3 Hz. Evidence: config/robot3.yaml http.poll_hz: 3.",
    },

    # A6 -- Gamma localization mischaracterized (P01229)
    # NOTE: this same paragraph is also the anchor for appending limitations
    # (A9). To avoid two edits colliding on one paragraph, A6 rewrites the
    # body and A9 is applied to the Beta-Ultrasonics paragraph (P01231) instead.
    {
        "type": "para",
        "find": "Odometry and Wheel Slip: Localization on Beta and Gamma relies on dead-reckoning. Rotational drift was mitigated by complementary gyro fusion, but translational wheel slip still accumulates error over long explorations. Frequent coordinate set-pose updates on the dashboard are required to align non-mapping robots with the global map frame.",
        "replace": "Odometry and Wheel Slip: Beta's localization relies on dead reckoning -- a complementary fusion of its 25GA370 wheel encoders and the GY-87 gyro Z-rate, computed laptop-side. Rotational drift was mitigated by gyro fusion and per-unit scale calibration, but translational wheel slip still accumulates error over long explorations, so frequent set-pose updates on the dashboard are required to align Beta with Alpha's global map frame. Gamma is not a ROS robot and runs none of Beta's odometry stack; it is a non-ROS ESP32 inspector exposing an HTTP/JSON telemetry endpoint, and its reported pose is the ESP32's own coarse estimate, not the encoder/IMU complementary filter used on Beta.",
        "expect": 1,
        "note": "A6: Gamma is a non-ROS HTTP inspector, not a dead-reckoning ROS robot. Evidence: CLAUDE.md; config/robot3.yaml kind: esp32.",
    },

    # A7 + A9 -- Beta ultrasonics ARE wired, AND append the omitted limitations
    # paragraph here (this is the last item before the closing limitations
    # sentence P01232, so appending keeps the new limitations inside the list).
    {
        "type": "para",
        "find": "Beta Ultrasonics: Although the forward-collision slowdown and obstacle avoidance guards are implemented in Beta's bridge and firmware, the physical sensors were not wired in the current build, requiring the operator to maintain active manual supervision around obstacles.",
        "replace": (
            "Beta Ultrasonics: Beta carries two forward-facing HC-SR04 ultrasonic sensors that are wired and active in the current build (LEFT TRIG=30/ECHO=31, RIGHT TRIG=32/ECHO=33, 5 V), mounted at the front edge and tilted slightly outward for field of view. The firmware median-filters them and appends the ranges to the serial packet; the bridge publishes /ultrasonic/{left,right}, hard-stops forward motion under 25 cm (re-enabling above 40 cm with hysteresis), and the goto controller begins a proportional slow-down under 60 cm. These are Beta's only real-time obstacle sense, as it has no lidar. "
            "Additional limitations observed: (1) GY-87 IMU intermittent I2C dropout -- on a marginal power line Beta's GY-87 intermittently drops off the I2C bus, after which the firmware streams frozen non-zero gyro values, heading freezes, and the map arrow goes static until a power-cycle; an encoder-heading fallback keeps driven turns working, and the pending fix is to rewire VCC 3.3 V to 5 V and resolder. "
            "(2) Gamma over-voltage damage -- a buck regulator set to 10 V was connected to Gamma's ESP32, IMU, and MQ sensor; the ESP32 survived, but the onboard IMU is likely dead (firmware tolerates its absence) and the MQ sensor needs re-verification. "
            "(3) Fire-detection model weakness -- fire.pt reads only 28-37% confidence on real fire, well below the 0.80 alarm gate, so reliable fire alarming requires a better-trained model. "
            "(4) Residual yaw drift -- even after gyro scale calibration, about 25 deg of rotational drift remains over a multi-turn run. "
            "(5) LAN-only, no GPS -- the system runs over a dedicated offline LAN with no internet and no GPS, so all localization is relative and absolute positioning is unavailable. "
            "(6) No 30-minute real-robot soak yet -- network KPIs are validated only against the in-process simulator over loopback; a full 30-minute real-robot field soak has not been recorded."
        ),
        "expect": 1,
        "note": "A7: ultrasonics ARE wired/active. A9: appends the 6 omitted honest limitations (GY-87 dropout, Gamma over-voltage, fire-model weakness, ~25 deg residual drift, LAN-only/no-GPS, no 30-min soak). Evidence: config/robot2.yaml; CLAUDE.md tickets; runbook; docs/baseline/.",
    },

    # A8a -- '30-minute test' in §5.2.4 (P01149)
    {
        "type": "para",
        "find": "Network stability was evaluated by measuring bandwidth, latency, and packet success across the ZeroMQ gateway channels (telemetry, map, commands, health, and video) during a continuous 30-minute test.",
        "replace": "Network stability was evaluated with the protocol soak harness (tools/soak_test.py), which measures telemetry sequence-loss, video FPS and capture-age, map and health inter-arrival gaps, and command-to-ACK round-trip time against fixed acceptance gates. A full 30-minute real-robot soak has not yet been performed; the recorded baseline artifacts are short (~0.4-minute) runs against the in-process simulator (127.0.0.1), so the network numbers below are reported as sim-soak measurements and acceptance-gate targets, not as a 30-minute field run.",
        "expect": 1,
        "note": "A8: corrects the '30-minute test' claim -- only ~0.4-min sim soaks exist. Evidence: docs/baseline/ (two 127.0.0.1, 0.4-min artifacts).",
    },

    # A8b -- '30-minute operating window' in §5.2.4 (P01151)
    {
        "type": "para",
        "find": "Network stability was evaluated by measuring bandwidth consumption, average message latency, and packet success rate across the critical ZeroMQ gateway channels during a continuous 30-minute operating window.",
        "replace": "Network stability was evaluated by measuring telemetry sequence-loss, video FPS and capture-age, map and health inter-arrival gaps, and command-to-ACK latency across the critical ZeroMQ gateway channels using the protocol soak harness. The recorded soak artifacts are short (~0.4-minute) simulator runs over loopback rather than a continuous 30-minute real-robot operating window, which has not yet been captured.",
        "expect": 1,
        "note": "A8: second '30-minute operating window' claim corrected. Note: per-stream bandwidth is not actually measured (no MB/s tool); reworded to measured quantities. Evidence: docs/baseline/.",
    },

    # ------------------------------------------------------------------ #
    # (B) TABLE CELL FILLS  (replace whole TBD cell)                     #
    # ------------------------------------------------------------------ #

    # ---- Table 12 : SLAM (5x4) ----
    # cols: 0 Metric | 1 Expected/Physical | 2 Experimental Result | 3 Error Margin
    {"type": "cell", "table": 12, "row": 1, "col": 2, "new_text": "Not measured",
     "note": "Test Area Dimensions experimental result -- no map-vs-ground-truth artifact."},
    {"type": "cell", "table": 12, "row": 1, "col": 3, "new_text": "Not measured",
     "note": "Test Area Dimensions error margin -- not measured."},
    {"type": "cell", "table": 12, "row": 2, "col": 3, "new_text": "Not measured",
     "note": "Grid Resolution error margin -- not measured (resolution is configured 0.025 m/cell)."},
    {"type": "cell", "table": 12, "row": 3, "col": 2, "new_text": "<=1.0 Hz (configured)",
     "note": "Map Update Rate experimental -- configured map-publish ceiling. Evidence: channels.py PORT_MAP map.grid ~1 Hz."},
    {"type": "cell", "table": 12, "row": 3, "col": 3, "new_text": "Not measured",
     "note": "Map Update Rate error margin -- not measured."},
    {"type": "cell", "table": 12, "row": 4, "col": 2, "new_text": "Not measured",
     "note": "Map Generation Time experimental -- no timing artifact."},
    {"type": "cell", "table": 12, "row": 4, "col": 3, "new_text": "Not measured",
     "note": "Map Generation Time error margin -- not measured."},
    # (Table 12 row 1 col1 stays '4.00 m x 4.00 m'; row 2 col1/col2 already '0.025 m/cell' -- leave; mark physical as configured via row3 col1)
    {"type": "cell", "table": 12, "row": 1, "col": 1, "new_text": "4.00 m x 4.00 m (configured)",
     "note": "Test Area dims kept as-is, labeled configured (physical test arena)."},
    {"type": "cell", "table": 12, "row": 2, "col": 1, "new_text": "0.025 m/cell (configured)",
     "note": "Grid Resolution expected -- configured (slam_toolbox)."},
    {"type": "cell", "table": 12, "row": 2, "col": 2, "new_text": "0.025 m/cell (configured)",
     "note": "Grid Resolution experimental -- configured value, not an independent measurement."},
    {"type": "cell", "table": 12, "row": 3, "col": 1, "new_text": "<= 1.0 Hz (configured)",
     "note": "Map Update Rate expected -- configured."},

    # ---- Table 13 : Detection (5x5) ----
    # cols: 0 Test Condition | 1 FPS | 2 Detection Accuracy (%) | 3 mAP IoU=0.50 (%) | 4 Confidence Threshold
    # Row 1 Well-Lit (Static)
    {"type": "cell", "table": 13, "row": 1, "col": 1, "new_text": "~15.25 fps (sim)",
     "note": "Pipeline FPS from docs/baseline/soak_*.json video_fps 15.25 (SIM loopback). Labeled (sim)."},
    {"type": "cell", "table": 13, "row": 1, "col": 2, "new_text": "Not measured (no labeled eval set)",
     "note": "Detection accuracy -- no labeled evaluation set / no mAP harness in repo."},
    {"type": "cell", "table": 13, "row": 1, "col": 3, "new_text": "Not measured (no labeled eval set)",
     "note": "mAP -- no mAP-scoring harness in repo."},
    {"type": "cell", "table": 13, "row": 1, "col": 4, "new_text": "fire alarm 0.80; floors person 0.70 / fire 0.60 (configured)",
     "note": "Configured thresholds. Evidence: config/fleet.yaml fire_conf_min 0.80; detect.conf floors."},
    # Row 2 Well-Lit (Moving)
    {"type": "cell", "table": 13, "row": 2, "col": 1, "new_text": "Not measured",
     "note": "FPS (moving) -- not separately measured."},
    {"type": "cell", "table": 13, "row": 2, "col": 2, "new_text": "Not measured (no labeled eval set)",
     "note": "Detection accuracy -- not measured."},
    {"type": "cell", "table": 13, "row": 2, "col": 3, "new_text": "Not measured (no labeled eval set)",
     "note": "mAP -- not measured."},
    {"type": "cell", "table": 13, "row": 2, "col": 4, "new_text": "fire alarm 0.80 (configured)",
     "note": "Configured alarm gate."},
    # Row 3 Dimly Lit (Static)
    {"type": "cell", "table": 13, "row": 3, "col": 1, "new_text": "Not measured",
     "note": "FPS (dim) -- not measured."},
    {"type": "cell", "table": 13, "row": 3, "col": 2, "new_text": "Not measured (no labeled eval set)",
     "note": "Detection accuracy -- not measured."},
    {"type": "cell", "table": 13, "row": 3, "col": 3, "new_text": "Not measured (no labeled eval set)",
     "note": "mAP -- not measured."},
    {"type": "cell", "table": 13, "row": 3, "col": 4, "new_text": "fire alarm 0.80 (configured)",
     "note": "Configured alarm gate."},
    # Row 4 Aggregate System Avg
    {"type": "cell", "table": 13, "row": 4, "col": 1, "new_text": "gate >= 12 fps (gate target)",
     "note": "Acceptance-gate target. Evidence: tools/soak_test.py video_fps >= 12."},
    {"type": "cell", "table": 13, "row": 4, "col": 2, "new_text": "Not measured (no labeled eval set)",
     "note": "Detection accuracy -- not measured."},
    {"type": "cell", "table": 13, "row": 4, "col": 3, "new_text": "Not measured (no labeled eval set)",
     "note": "mAP -- not measured."},
    {"type": "cell", "table": 13, "row": 4, "col": 4, "new_text": "fire alarm 0.80 (configured)",
     "note": "Configured alarm gate."},

    # ---- Table 14 : Localization (4x4) ----
    # cols: 0 Trajectory | 1 Distance | 2 Translation Error (RMSE) | 3 Rotational Drift
    {"type": "cell", "table": 14, "row": 1, "col": 2, "new_text": "Not measured",
     "note": "Translation RMSE -- no trajectory ground-truth artifact."},
    {"type": "cell", "table": 14, "row": 1, "col": 3, "new_text": "~45 deg -> ~25 deg after gyro_scale 1.0304",
     "note": "Measured rotational drift before/after gyro calibration. Evidence: runbook + config/robot2.yaml gyro_scale_correction 1.0304."},
    {"type": "cell", "table": 14, "row": 2, "col": 2, "new_text": "Not measured",
     "note": "Translation RMSE -- not measured."},
    {"type": "cell", "table": 14, "row": 2, "col": 3, "new_text": "~45 deg -> ~25 deg after gyro_scale 1.0304",
     "note": "Same measured drift result (the one real localization metric)."},
    {"type": "cell", "table": 14, "row": 3, "col": 2, "new_text": "Not measured",
     "note": "Translation RMSE -- not measured."},
    {"type": "cell", "table": 14, "row": 3, "col": 3, "new_text": "~45 deg -> ~25 deg after gyro_scale 1.0304",
     "note": "Same measured drift result."},

    # ---- Table 15 : Gas (4x5) ----
    # cols: 0 Hazard | 1 Baseline (ADC) | 2 Peak (ADC) | 3 Response Time | 4 Publish Latency
    # Row 1 Clean Air (control) -- col3 already 'N/A'
    {"type": "cell", "table": 15, "row": 1, "col": 1, "new_text": "Not measured",
     "note": "Baseline ADC -- no gas-exposure measurement artifact."},
    {"type": "cell", "table": 15, "row": 1, "col": 2, "new_text": "Not measured",
     "note": "Peak ADC -- not measured."},
    {"type": "cell", "table": 15, "row": 1, "col": 4, "new_text": "Not measured",
     "note": "Publish latency -- not measured."},
    # Row 2 Simulated Smoke
    {"type": "cell", "table": 15, "row": 2, "col": 1, "new_text": "Not measured",
     "note": "Baseline ADC -- not measured."},
    {"type": "cell", "table": 15, "row": 2, "col": 2, "new_text": "Not measured (alarm 3000 / clear 2000 ADC configured)",
     "note": "Peak ADC not measured; configured thresholds noted. Evidence: config/robot3.yaml gas.alarm_threshold 3000 / clear 2000."},
    {"type": "cell", "table": 15, "row": 2, "col": 3, "new_text": "Not measured (latch >= 10 s configured)",
     "note": "Response time not measured; configured alarm latch noted. Evidence: config/robot3.yaml."},
    {"type": "cell", "table": 15, "row": 2, "col": 4, "new_text": "Not measured",
     "note": "Publish latency -- not measured."},
    # Row 3 Butane Gas Burst
    {"type": "cell", "table": 15, "row": 3, "col": 1, "new_text": "Not measured",
     "note": "Baseline ADC -- not measured."},
    {"type": "cell", "table": 15, "row": 3, "col": 2, "new_text": "Not measured (alarm 3000 / clear 2000 ADC configured)",
     "note": "Peak ADC not measured; configured thresholds noted."},
    {"type": "cell", "table": 15, "row": 3, "col": 3, "new_text": "Not measured (latch >= 10 s configured)",
     "note": "Response time not measured; configured latch noted."},
    {"type": "cell", "table": 15, "row": 3, "col": 4, "new_text": "Not measured",
     "note": "Publish latency -- not measured."},

    # ---- Table 16 : Network (5x5) ----
    # cols: 0 Data Stream | 1 Protocol | 2 Avg Bandwidth | 3 Avg Latency | 4 Packet Success Rate
    # Row 1 Motion Control (cmd.drive)
    {"type": "cell", "table": 16, "row": 1, "col": 2, "new_text": "Not measured (no per-stream MB/s tool)",
     "note": "Per-stream bandwidth -- no tool measures per-channel MB/s."},
    {"type": "cell", "table": 16, "row": 1, "col": 3, "new_text": "cmd->ACK p95 ~12.7-13.3 ms (sim); gate <= 150 ms",
     "note": "Measured sim-soak ACK p95 + gate target. Evidence: soak_*.json ack_p95_ms; tools/soak_test.py."},
    {"type": "cell", "table": 16, "row": 1, "col": 4, "new_text": "50 ACKs/run (sim)",
     "note": "Measured sim-soak ack_count. Evidence: soak_*.json."},
    # Row 2 Sensor Telemetry (tele.full)
    {"type": "cell", "table": 16, "row": 2, "col": 2, "new_text": "Not measured (no per-stream MB/s tool)",
     "note": "Per-stream bandwidth -- not measured."},
    {"type": "cell", "table": 16, "row": 2, "col": 3, "new_text": "~19.6-19.7 Hz rate (sim)",
     "note": "Measured sim-soak telemetry rate. Evidence: soak_*.json tele_rate_hz."},
    {"type": "cell", "table": 16, "row": 2, "col": 4, "new_text": "seq loss 0.0% (clean sim) / 20.7% (degraded sim); gate < 1%",
     "note": "Measured sim-soak loss (one run passed, one failed) + gate. Evidence: soak_*.json tele_loss_pct."},
    # Row 3 Compressed Video Stream
    {"type": "cell", "table": 16, "row": 3, "col": 2, "new_text": "Not measured (no per-stream MB/s tool)",
     "note": "Per-stream bandwidth -- not measured."},
    {"type": "cell", "table": 16, "row": 3, "col": 3, "new_text": "~15.25 fps; capture-age p95 0.1-0.2 ms (sim); gate fps>=12, age<=350 ms",
     "note": "Measured sim-soak fps/age + gates. Evidence: soak_*.json video_fps/video_age_p95_ms."},
    {"type": "cell", "table": 16, "row": 3, "col": 4, "new_text": "fps 15.25 (sim)",
     "note": "Measured sim-soak video_fps. Evidence: soak_*.json."},
    # Row 4 SLAM Map Updates (map.grid)
    {"type": "cell", "table": 16, "row": 4, "col": 2, "new_text": "Not measured (no per-stream MB/s tool)",
     "note": "Per-stream bandwidth -- not measured."},
    {"type": "cell", "table": 16, "row": 4, "col": 3, "new_text": "inter-arrival p95 ~1.01 s (sim); gate <= 2.0 s",
     "note": "Measured sim-soak map gap + gate. Evidence: soak_*.json map_gap_p95_s."},
    {"type": "cell", "table": 16, "row": 4, "col": 4, "new_text": "map gaps observed (sim)",
     "note": "Measured sim-soak observation. Evidence: soak_*.json."},
]

# ----------------------------------------------------------------------
# MANUAL (unanchorable) follow-ups -- NOT applied automatically:
#
# MANUAL: P00029 (abstract/intro) and P00190, P00198, P00290, P01273, P01280
#   still say "YOLO-based fire ... detection". These are accurate enough at a
#   high level (YOLO IS used), so they are intentionally NOT rewritten here.
#   If the team wants the primary/secondary model distinction everywhere,
#   edit those paragraphs by hand -- their phrasing is not a unique single
#   substring shared with the A3 anchor and rewriting all of them risks
#   over-editing the conclusion chapter.
#
# MANUAL: Any "30-minute" mention outside P01149/P01151 (none found in ch5)
#   should be reviewed by hand if the document is edited further.
# ----------------------------------------------------------------------
