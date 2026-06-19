# -*- coding: utf-8 -*-
# Machine-applyable edit list for Chapter 3 of the GP book (Word .docx).
#
# Verification basis:
#   - Prose finds verified as contiguous, unique substrings within a SINGLE
#     "Pxxxxx: " line of docx_paras.txt (the "Pxxxxx: " prefix is NOT part of
#     the find string).
#   - Table cells verified against docx_tables.txt. docx Table 8 = Book Table
#     3.1; docx Table 9 = Book Table 3.2; docx Table 10 = Book Table 3.3 (NOT
#     edited). Tables are 0-indexed; row 0 = header. "new_text" replaces the
#     ENTIRE cell text.
#
# NOTE ON NODE LISTS: the book renders each node as its OWN paragraph
# (e.g. P00743 = "IMU Node ...", P00744 = "Odometry Node ..."). The corrections
# doc quoted them as multi-line blocks, but no contiguous multi-line substring
# exists in a single paragraph. They are therefore applied as per-paragraph
# edits below.

EDITS = [
    # ----------------------------------------------------------------------
    # PROSE EDITS
    # ----------------------------------------------------------------------

    # Fix 1 - Alpha node list: drop fabricated IMU node, point at rf2o.
    # (P00743 is the IMU Node line; P00744 is the wheel-Odometry line.)
    {"type": "para",
     "find": "IMU Node – Publishes inertial data for orientation estimation.",
     "replace": "Laser Odometry Node (rf2o) – Estimates Alpha's motion by scan-matching successive LiDAR scans; Alpha carries no IMU.",
     "expect": 1,
     "note": "Fix 1a (P00743): Alpha has no IMU; motion is rf2o laser scan-matching. config/robot1.yaml has no imu block."},

    {"type": "para",
     "find": "Odometry Node – Computes wheel-based odometry information.",
     "replace": "All Alpha motion estimation is laser-based (rf2o scan-matching); Alpha has no wheel encoders.",
     "expect": 1,
     "note": "Fix 1b (P00744): Alpha has no wheel encoders (mapping/mapper.yaml: scan matching estimates ALL motion)."},

    # Fix 2 - Gamma (Environmental Sensing) node list: ESP32 runs NO ROS nodes;
    # it is HTTP/JSON. Rewrite each of the four item paragraphs in place.
    {"type": "para",
     "find": "Hardware Interface Node – Manages motors and sensor connections.",
     "replace": "Gamma is an ESP32 microcontroller with an embedded HTTP server and runs NO ROS nodes. Motor control endpoint - GET /control?dir=F|B|L|R|S drives the four motors.",
     "expect": 1,
     "note": "Fix 2a (P00758): config/robot3.yaml kind: esp32, HTTP API, no ROS; /control endpoint."},

    {"type": "para",
     "find": "Gas Sensor Node – Reads data from MQ-series gas sensors and publishes environmental measurements.",
     "replace": "Gas / telemetry endpoint - GET /telemetry returns JSON {d,g,x,y,a,rssi,uptime,last_cmd_age}; the MQ-5 gas reading is polled by the operations center at 3 Hz.",
     "expect": 1,
     "note": "Fix 2b (P00759): config/robot3.yaml /telemetry endpoint, poll_hz: 3."},

    {"type": "para",
     "find": "Odometry Node – Computes motion estimates from wheel encoders.",
     "replace": "Local sensor task - samples the MQ-5 gas sensor and applies the alarm / clear thresholds onboard.",
     "expect": 1,
     "note": "Fix 2c (P00760): Gamma firmware applies gas thresholds onboard; config/robot3.yaml lines 22-24."},

    {"type": "para",
     "find": "Localization Support Node – Estimates robot position using IMU and odometry data.",
     "replace": "Gamma has no IMU/odometry localization on board; the operations center wraps its HTTP/JSON telemetry laptop-side.",
     "expect": 1,
     "note": "Fix 2d (P00761): Gamma is not ROS - plain HTTP/JSON, wrapped laptop-side (CLAUDE.md)."},

    # Fix 3 - A* runs console-side (P00732). Replace just the navigation sentence.
    {"type": "para",
     "find": "Navigation-related functions such as waypoint following (via A*) and obstacle avoidance operate within this layer to support autonomous movement.",
     "replace": "Global path planning (A*, 8-connected with an octile heuristic over a dilated costmap) runs CONSOLE-side on the operator laptop, which feeds the robot one path leg at a time. The robot itself runs only reactive local navigation - ultrasonic-repulsion obstacle avoidance fused with the laptop's streamed heading bias - so the onboard layer never plans a full route.",
     "expect": 1,
     "note": "Fix 3 (P00732): A* in dashboard_qt/ui/map/planner.py (console-side); robot runs robot2_local_nav.py reactive nav."},

    # Fix 4 - telemetry rate (P00794). 20 Hz, not "20 onboard / 10 to gateway".
    {"type": "para",
     "find": "Telemetry updates: 20 Hz (onboard), published to ZMQ gateway at 10 Hz",
     "replace": "Telemetry updates: 20 Hz (the gateway publishes tele.full at 20 Hz)",
     "expect": 1,
     "note": "Fix 4 (P00794): gateway_node.py TELE_HZ = 20.0. The 10 Hz figure is the drive-command stream, not telemetry."},

    # Fix 5 - ESP32 gas polling (P00797). 3 Hz, not 2 Hz.
    {"type": "para",
     "find": "ESP32 gas readings: 2 Hz HTTP polling rate",
     "replace": "ESP32 gas readings: 3 Hz HTTP polling rate",
     "expect": 1,
     "note": "Fix 5 (P00797): config/robot3.yaml poll_hz: 3."},

    # Fix 6 - camera FPS / bandwidth consistency (P00803 + P00805). 15 fps.
    {"type": "para",
     "find": "Camera stream (compressed): 10 FPS × 50 KB per frame ≈ 500 KB/s",
     "replace": "Camera stream (compressed): 15 FPS × 50 KB per frame ≈ 750 KB/s",
     "expect": 1,
     "note": "Fix 6a (P00803): configured camera fps is 15 everywhere (config/robot2.yaml fps: 15); 15 x 50 = 750 KB/s."},

    {"type": "para",
     "find": "The total estimated bandwidth usage is approximately 600 KB/s, which is well within the capacity of standard WiFi networks.",
     "replace": "The total estimated bandwidth usage is approximately 870 KB/s (LiDAR ~16 KB/s + camera ~750 KB/s + auxiliary ~100 KB/s), which is well within the capacity of standard WiFi networks.",
     "expect": 1,
     "note": "Fix 6b (P00805): recompute total with 15 fps camera (16 + 750 + 100 = ~870 KB/s)."},

    # Fix 7 - deadman timeout (P00831, in 3.7 Risks). Replace ">2 seconds" sentence.
    # The preceding "multi-layer deadman safety chain ... operations center to the
    # gateway and low-level firmware" phrasing is correct and is left intact.
    # 3.6 (P01064) already states the layered 0.6/0.8/1.0-2.0 s chain correctly -
    # no single "2 second" statement there to fix (Fix 7 Location B needs no edit).
    {"type": "para",
     "find": "If the heartbeat signal is lost for more than 2 seconds, the robot automatically cuts motor power to prevent runaway conditions.",
     "replace": "Motor power is cut by a layered deadman chain rather than a single timeout: the gateway stops the drive after 0.6 s of silence, the onboard bridge after 0.8 s, and the firmware watchdog after 1.0 s - whichever fires first. This redundancy prevents runaway conditions even if one layer hangs.",
     "expect": 1,
     "note": "Fix 7 (P00831): gateway DEADMAN_S 0.60 / bridge deadman_timeout_s 0.8 / firmware WATCHDOG_MS 1000."},

    # Fix 8 - Logitech camera -> USB camera (P00611, P00649).
    {"type": "para",
     "find": "integrating the Logitech camera,",
     "replace": "integrating the USB camera,",
     "expect": 1,
     "note": "Fix 8a (P00611): repo uses a generic USB capture device (config/robot2.yaml camera: device 0), no brand."},

    {"type": "para",
     "find": "live video streams from the onboard Logitech camera",
     "replace": "live video streams from the onboard USB camera",
     "expect": 1,
     "note": "Fix 8b (P00649): FR5 onboard camera is a generic USB camera."},

    # Fix 9 - YOLOv8n -> configured models (P00601, P00611, P00624).
    # "YOLOv8n" alone is not unique (5 hits incl. TOC), so each find is widened
    # to a unique surrounding phrase. TOC entries (P00162, P01184) left untouched.
    {"type": "para",
     "find": "object detection using YOLOv8n, dashboard development",
     "replace": "object detection using YOLOv8 (yolov8s.pt primary + fire.pt secondary), dashboard development",
     "expect": 1,
     "note": "Fix 9a (P00601): config/fleet.yaml default_model yolov8s.pt + fire_model fire.pt; no yolov8n configured."},

    {"type": "para",
     "find": "object detection using YOLOv8n on the external laptop",
     "replace": "object detection using YOLOv8 (yolov8s.pt primary + fire.pt secondary) on the external laptop",
     "expect": 1,
     "note": "Fix 9b (P00611): same evidence as 9a."},

    {"type": "para",
     "find": "integration of YOLOv8n-based object detection",
     "replace": "integration of YOLOv8 (yolov8s.pt primary + fire.pt secondary)-based object detection",
     "expect": 1,
     "note": "Fix 9c (P00624): same evidence as 9a."},

    # Fix 10 - RViz2 role (P00674). The paragraph text ends "as illustrated "
    # (the "in Figure 3.2" tail is truncated in the extract), so the find anchors
    # only on the RViz2 sentence body that is actually present.
    {"type": "para",
     "find": "RViz2 is integrated into the architecture to provide real-time visualization of the map, robot pose, and sensor data during operation and testing",
     "replace": "RViz2 is used only as a developer-side debug and visualization aid during bring-up and testing; it is NOT the runtime operator interface. The operational UI for live missions is the native PySide6 desktop operations console, which renders the map, robot pose, video, and detections for the operator",
     "expect": 1,
     "note": "Fix 10 (P00674): operator console is the PySide6 app (dashboard_qt/main.py); RViz2 is a debug aid only."},

    # ----------------------------------------------------------------------
    # TABLE EDITS
    # ----------------------------------------------------------------------

    # Table 8 = Book Table 3.1 (Alpha components). Cols: 0 Category | 1 Component
    # | 2 Specifications | 3 Function.
    # Row 3 = "Sensor | MPU-9250 IMU | 9-axis IMU (present in structure, unused
    # on Alpha) | Orientation and motion estimation".
    {"type": "cell", "table": 8, "row": 3, "col": 1,
     "new_text": "(No IMU on Alpha)",
     "note": "T3.1 MPU-9250 row Component: Alpha has no IMU (config/robot1.yaml has no imu block)."},
    {"type": "cell", "table": 8, "row": 3, "col": 2,
     "new_text": "Alpha localizes by laser scan-matching (rf2o); no IMU present",
     "note": "T3.1 MPU-9250 row Specifications."},
    {"type": "cell", "table": 8, "row": 3, "col": 3,
     "new_text": "N/A",
     "note": "T3.1 MPU-9250 row Function."},

    # Row 4 = "Sensor | Wheel Encoders | Optical incremental (JGB37-520, unused
    # on Alpha) | Physically present but unused by current firmware".
    {"type": "cell", "table": 8, "row": 4, "col": 2,
     "new_text": "None on Alpha (rf2o laser odometry provides motion). Beta uses 25GA370 Hall-effect quadrature, 408 CPR",
     "note": "T3.1 Wheel Encoders row Specifications: real encoders are on Beta (25GA370, 408 CPR), not Alpha."},
    {"type": "cell", "table": 8, "row": 4, "col": 3,
     "new_text": "Alpha: not used (scan-matching). Beta: wheel odometry",
     "note": "T3.1 Wheel Encoders row Function."},

    # Row 5 = "Processing Unit | Raspberry Pi 4 Model B | Quad-core ARM
    # Cortex-A72 @ 1.8 GHz, 8 GB RAM, 64 GB microSD, Ubuntu 22.04 LTS | ...".
    {"type": "cell", "table": 8, "row": 5, "col": 2,
     "new_text": "Quad-core ARM Cortex-A72 @ 1.5 GHz, 8 GB RAM, 64 GB microSD, Ubuntu 22.04 LTS",
     "note": "T3.1 Raspberry Pi 4 row Specifications: Pi 4B clock is 1.5 GHz, not 1.8 GHz."},

    # Row 6 = "Power System | 3S LiPo Battery | 11.1 V, 5000 mAh, ~67 Wh |
    # Primary power supply".
    {"type": "cell", "table": 8, "row": 6, "col": 2,
     "new_text": "11.1 V, 5000 mAh, ~55.5 Wh",
     "note": "T3.1 3S LiPo row Specifications: 11.1 V x 5.0 Ah = ~55.5 Wh, not ~67 Wh (arithmetic fix)."},

    # Table 9 = Book Table 3.2 (sensor specs). Cols: 0 Sensor | 1 Specification
    # | 2 Accuracy | 3 Update Rate.
    # Row 2 = "MPU6050 / GY-87 | 6-axis / 10-DOF IMU (accel + gyro + mag) |
    # +/-0.3 deg/s (gyro) | 100+ Hz".
    {"type": "cell", "table": 9, "row": 2, "col": 2,
     "new_text": "±250 to ±2000 °/s FS range (configured ±500 °/s)",
     "note": "T3.2 MPU6050/GY-87 row Accuracy: the +/-0.3 deg/s figure is fabricated; firmware MPU_GYRO_FS=1 -> +/-500 deg/s."},

    # Row 3 = "Wheel Encoders | JGB37-520 (Alpha, unused) / 25GA370 (Beta, 408
    # CPR) | +/-1 count | ~100 Hz".
    {"type": "cell", "table": 9, "row": 3, "col": 1,
     "new_text": "25GA370 (Beta), 408 CPR quadrature; Alpha has no wheel encoders (rf2o laser odometry)",
     "note": "T3.2 Wheel Encoders row Specification: config/robot2.yaml ticks_per_rev: 408; Alpha has none."},
]
