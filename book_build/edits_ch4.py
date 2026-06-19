# -*- coding: utf-8 -*-
# Machine-applyable edit list for Chapter 4 of the GP book (Word .docx).
#
# Derived from docs/book_corrections/chapter4_corrections.md, verified against
# docx_paras.txt (prose) and docx_tables.txt (Table 11 == Book Table 4.1).
#
# Verification rules honored:
#   - Every "para" find is an EXACT contiguous substring of a single Pxxxxx line
#     (the "Pxxxxx: " prefix stripped), confirmed unique enough to anchor.
#   - Every "cell" new_text replaces the WHOLE cell; row/col confirmed against
#     docx_tables.txt TABLE 11 (7 rows x 3 cols; row 0 = header).
#   - Only documented power clarifications applied; unverifiable figures are
#     left as "# MANUAL:" notes, not edits.

EDITS = [
    # ----- PROSE EDITS -----

    # Edit 1 - YOLO model roles. Anchored to P00995 (the "Dashboard YOLO
    # Manager" bullet). The phrase "Loads the YOLO fire model (defaulting to
    # fire.pt model parameters)" is unique to P00995.
    {
        "type": "para",
        "find": "Loads the YOLO fire model (defaulting to fire.pt model parameters)",
        "replace": (
            "Loads two YOLO models: the primary is a clean COCO network "
            "(defaulting to yolov8s.pt) used for person/dog/cat detection, and "
            "an optional secondary fire-only network (fire.pt) whose detections "
            "are trusted only for the Fire class. The fire fine-tune wrecked "
            "fire.pt's COCO classes, so it is never used as the primary detector"
        ),
        "expect": 1,
        "note": "Default model is yolov8s.pt (COCO), not fire.pt; fire.pt is secondary, Fire-class only. config/fleet.yaml + yolo_worker.py.",
    },

    # Edit 2 - Add the real 3-stage detection pipeline, prepended to the
    # "Receives incoming frames..." sentence (P00997). Unique phrase.
    {
        "type": "para",
        "find": "Receives incoming frames via multiprocessing input queues",
        "replace": (
            "Runs a three-stage detection pipeline on every frame: (1) the "
            "primary COCO model (yolov8s.pt) for person/dog/cat; (2) the "
            "secondary fire-only model (fire.pt), restricted to its Fire class; "
            "and (3) a classical color/shape flame-prop detector "
            "(detect_flame_prop) that finds a printed/animated flame the trained "
            "net cannot see. The three result sets are merged, with flame-prop "
            "hits added only when they do not overlap a real-fire box. "
            "Receives incoming frames via multiprocessing input queues"
        ),
        "expect": 1,
        "note": "Adds the 3-stage pipeline (COCO primary + fire secondary + classical detect_flame_prop). yolo_worker.py lines 51-91, 220-237.",
    },

    # Edit 3 - Worker returns empty JPEG + detection list; UI overlays vector
    # boxes. Anchored to P00998. Unique phrase.
    {
        "type": "para",
        "find": "Performs inference, plots bounding boxes, and returns annotated JPEGs and a detection list",
        "replace": (
            "Performs inference and returns an empty JPEG placeholder together "
            "with a list of normalized detections; it does not draw on the "
            "frame. Rendering is decoupled: the UI displays the raw camera frame "
            "as soon as it arrives and overlays the bounding boxes as vector "
            "graphics, so live video latency is bounded by the network, not by "
            "inference, and no second JPEG is re-encoded or shipped across the "
            "process boundary"
        ),
        "expect": 1,
        "note": "Worker emits ('annotated', frame_id, b'', detections); decoupled vector rendering in the UI. yolo_worker.py line 245.",
    },

    # Edit 4 - Generic USB camera, not Logitech. Anchored to P00990 (the
    # "Robot Video Streamer" bullet). The capture sentence is unique to P00990.
    # NOTE: "Logitech" also appears in P00611, P00649 (other sections); only the
    # 4.2.2 capture sentence is replaced here, matching the correction's anchor.
    {
        "type": "para",
        "find": "It captures frames from the Logitech USB camera (640x480 resolution at 15 FPS)",
        "replace": (
            "It captures frames from a generic USB camera (device index 0, "
            "640x480 resolution at 15 FPS)"
        ),
        "expect": 1,
        "note": "config/robot2.yaml configures the camera by device index 0 only; no make/model. Other 'Logitech' mentions (P00611/P00649) are outside this anchor's scope.",
    },

    # Edit 5 - Beta odometry runs on the laptop, not on-robot. Anchored to the
    # unique substring within P01021 (the "Outcome"/integration paragraph).
    {
        "type": "para",
        "find": "Beta uses a custom complementary filter in navigation/robot2_odom.py fusing wheel encoders (408 CPR) and the GY-87 IMU gyroscope Z-axis rate.",
        "replace": (
            "Beta uses a custom complementary filter (not an EKF) that fuses the "
            "wheel encoders (408 counts/rev) with the GY-87 IMU gyroscope Z-axis "
            "rate. This fusion was moved off the Pi onto the laptop "
            "(dashboard_qt/state/local_odom.py), which reconstructs the pose "
            "from the raw encoder and gyro values streamed in each telemetry "
            "frame; the heading itself is integrated at 50 Hz on the Pi-side "
            "bridge (navigation/robot2_bridge.py) for accuracy. The legacy "
            "on-robot node navigation/robot2_odom.py is no longer in the live "
            "path."
        ),
        "expect": 1,
        "note": "Odometry moved to laptop (local_odom.py); 50 Hz heading on robot2_bridge.py; robot2_odom.py is legacy. Complementary filter (not EKF) retained.",
    },

    # Edit 6 - Add Beta's two front HC-SR04 ultrasonics. Anchored to P01010
    # (the "Low-Level (Arduino)" bullet). Unique phrase.
    {
        "type": "para",
        "find": "Reads ultrasonic distance sensors (Beta Mega) and MQ-5 gas sensor (Gamma ESP32)",
        "replace": (
            "Reads two front-facing HC-SR04 ultrasonic distance sensors on "
            "Beta's Mega (LEFT trig=30/echo=31, RIGHT trig=32/echo=33; forward "
            "motion hard-stops at 25 cm and goto slows from 60 cm) and the MQ-5 "
            "gas sensor on Gamma's ESP32"
        ),
        "expect": 1,
        "note": "Adds Beta's 2 front HC-SR04 (pins 30/31, 32/33; stop 25 cm / slow 60 cm). config/robot2.yaml ultrasonic block.",
    },

    # Edit 10 - Firmware watchdog flat 1.0 s, not 1.0 to 2.0 s. Anchored to
    # the unique substring within P01064 (Command Deadman safety chain).
    {
        "type": "para",
        "find": "the Arduino Mega firmware implements a 1.0 to 2.0-second hardware watchdog",
        "replace": "the Arduino Mega firmware implements a flat 1.0-second hardware watchdog",
        "expect": 1,
        "note": "WATCHDOG_MS 1000UL in robot2_controller_v5.ino; the 2000 ms value is Alpha's, not Beta's.",
    },

    # Edit 11 - Esp32Link poll rate 3 Hz, not 2 Hz. Anchored to P01044 (State
    # Store & Transport Threading). The phrase "Esp32Link (polls the HTTP
    # endpoints at 2 Hz)" is unique to P01044 (P01016's wording differs).
    {
        "type": "para",
        "find": "Esp32Link (polls the HTTP endpoints at 2 Hz)",
        "replace": "Esp32Link (polls the HTTP endpoints at 3 Hz)",
        "expect": 1,
        "note": "config/robot3.yaml poll_hz: 3.",
    },

    # ----- TABLE EDIT (Table 11 == Book Table 4.1) -----
    # docx_tables.txt TABLE 11 (7x3): row 0 header [Component|Specification|Function].
    # Row 2 = "Buck Converter 1"; Row 3 = "Buck Converter 2 (BEC)".

    # Buck Converter 1, Specification cell (row 2, col 1).
    # Current text: "11.1 V → 5.1 V / 5 A"
    {
        "type": "cell",
        "table": 11,
        "row": 2,
        "col": 1,
        "new_text": "11.1 V → ~5.25 V at the Pi pins (buck set higher to offset ~0.4-0.5 V path drop) / 5 A",
        "note": "Pi needs ~5.25 V AT THE PINS; ~0.4-0.5 V path drop. CLAUDE.md hardware state.",
    },

    # Buck Converter 2 (BEC), Function cell (row 3, col 2).
    # Current text: "Dedicated BEC for Beta's SG90 navigation servo motor"
    {
        "type": "cell",
        "table": 11,
        "row": 3,
        "col": 2,
        "new_text": "Dedicated regulated rail for the servo (Beta's arm servo / Gamma's sensor-mount servo). Note: Beta is skid-steer and has no steering servo",
        "note": "Beta has NO steering/navigation servo (arm servo on pin 5); steerable sensor-mount servo is on Gamma. Specification voltage (6.0 V / 3 A) left unchanged per instruction.",
    },
]

# ============================================================================
# MANUAL / unanchored items (NOT applied as edits):
#
# MANUAL: Battery "~67 Wh" -> "~55 Wh". The instruction said to apply this IF
#   ~67 Wh appears in Table 11. It DOES appear in TABLE 11 row 1 ("3S LiPo,
#   11.1 V nominal, 5000 mAh (~67 Wh)"). However, this change was NOT in the
#   verified TABLE 11 EDITS list of the task (only Buck 1 and Buck 2 cells were
#   specified), and the corrections doc itself (VERIFY item 7) flags ~67 Wh as
#   "worth a sanity check" but explicitly "Not flagged as a required fix" and
#   asks to confirm the pack nameplate. 11.1 V x 5000 mAh = 55.5 Wh nominal.
#   Left to the hardware team to confirm before changing. (Also appears in
#   docx Table 8 row "Power System" and Table 9-adjacent prose if present.)
#
# MANUAL: Edit 7 prose (4.1 "Implemented Power Solution", "The second converter
#   (a dedicated BEC buck) regulates the voltage to 6.0 V / 3 A, dedicated to
#   Beta's SG90 navigation servo motor.") was NOT found as a contiguous
#   substring of any single Pxxxxx line in docx_paras.txt -> unanchorable here.
#   The equivalent fact is applied via the Table 11 BEC Function cell edit.
#
# MANUAL: Edit 8 prose (4.1, "The first converter regulates the battery voltage
#   to 5.1 V / 5 A...") was NOT found in docx_paras.txt -> unanchorable.
#   Applied via the Table 11 Buck Converter 1 Specification cell edit instead.
#
# MANUAL: Edit 9 (two over-voltage incidents, ADD-only) has no FIND anchor and
#   is a pure insertion; out of scope for a find/replace edit list. Insert
#   manually at the end of the 4.1 power discussion.
#
# MANUAL: Edit 12 (SLAM rf2o scan-matching clarification) was marked optional
#   in the corrections doc and the find string
#   "rf2o_laser_odometry: uses scan matching to publish /odom and
#   odom->base_link TF" was NOT located as a contiguous substring in
#   docx_paras.txt -> unanchorable. Apply manually if desired.
#
# MANUAL: Servo-rail voltage "6.0 V / 3 A" (Buck 2 Specification) and Buck 1
#   "5 A" rating are unverifiable from the repo (corrections VERIFY section).
#   Per instruction, the Buck 2 Specification voltage was kept as-is; no
#   invented numbers introduced.
# ============================================================================
