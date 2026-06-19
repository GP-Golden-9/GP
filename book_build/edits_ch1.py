# -*- coding: utf-8 -*-
# Chapter 1 machine-applyable edit list.
# Each "find" was verified to appear character-for-character (including unicode
# curly apostrophes U+2019 and en-dashes U+2013) as a contiguous substring of a
# SINGLE paragraph line in docx_paras.txt (prefix "Pxxxxx: " stripped).

EDITS = [
    # --- Fix 1: Autonomous decision-making is IN scope ---
    # 1a: delete the Out-of-Scope line (P00353). The replace empties the line text.
    {
        "type": "para",
        "find": "Autonomous decision-making and action execution (current phase focuses on mapping and detection)",
        "replace": "",
        "expect": 1,
        "note": "Fix 1a: remove 'autonomous decision-making' from the Out-of-Scope list (P00353); two autonomous behaviors ship",
    },
    # 1b: extend the Software Scope list after the dashboard bullet (P00344).
    {
        "type": "para",
        "find": "Dashboard interface for monitoring and control",
        "replace": (
            "Dashboard interface for monitoring and control\n"
            "Autonomous mission execution from the operations center: area-coverage "
            "scanning of the shared map (SCAN AREA) and a GO TO FIRE -> dispense (5 s "
            "pump) -> RETURN sequence, both built on the A* planner and reactive "
            "obstacle avoidance"
        ),
        "expect": 1,
        "note": "Fix 1b: add autonomous mission-execution bullet to Software Scope (P00344)",
    },

    # --- Fix 2: Alpha has NO wheel encoders (P00189) ---
    {
        "type": "para",
        "find": "Alpha’s wheel encoders are present but unused for localization; mapping relies entirely on scan-based odometry.",
        "replace": "Alpha has no wheel encoders; localization relies entirely on scan-based odometry (rf2o laser odometry feeding slam_toolbox).",
        "expect": 1,
        "note": "Fix 2: Alpha has no wheel encoders (P00189)",
    },

    # --- Fix 3: only the two Pis use 5 GHz; Gamma is 2.4 GHz (P00193) ---
    {
        "type": "para",
        "find": "All robots communicate over a 5 GHz WiFi network. The Raspberry Pi–based robots (Alpha and Beta) run ROS 2 locally and expose telemetry, map data, video, and commands through a ZeroMQ/msgpack gateway protocol.",
        "replace": "The robots communicate over a shared WiFi network. The Raspberry Pi–based robots (Alpha and Beta) connect on 5 GHz, run ROS 2 locally, and expose telemetry, map data, video, and commands through a ZeroMQ/msgpack gateway protocol; the ESP32-based Gamma robot has no 5 GHz radio and joins the network's 2.4 GHz band.",
        "expect": 1,
        "note": "Fix 3: Gamma (ESP32) is 2.4 GHz only; only the Pis use 5 GHz (P00193)",
    },
    # 3b: §1.7 Network Constraints softening (P00378)
    {
        "type": "para",
        "find": "Communication relies on 5GHz WiFi network",
        "replace": "Communication relies on a shared WiFi network (5 GHz for the Raspberry Pi robots; 2.4 GHz for the ESP32 robot)",
        "expect": 1,
        "note": "Fix 3b: soften the 5 GHz-only Network Constraint (P00378)",
    },

    # --- Fix 4: Gamma's IMU is MPU6050 (P00191) ---
    {
        "type": "para",
        "find": "an MQ-5 gas sensor, HC-SR04 ultrasonic sensor, MPU6050/GY-87 IMU, a buzzer, and a servo mechanism.",
        "replace": "an MQ-5 gas sensor, HC-SR04 ultrasonic sensor, an MPU6050 IMU, a buzzer, and a servo mechanism.",
        "expect": 1,
        "note": "Fix 4: Gamma IMU is MPU6050, not GY-87 (P00191). Longer anchor used since 'MPU6050/GY-87 IMU' alone appears in 3 paras.",
    },
    # 4b: Beta is the GY-87 robot (P00190). 'GY-87/MPU6050 IMU' also appears in
    # P00880, so anchor on Beta's surrounding context.
    {
        "type": "para",
        "find": "a USB camera, GY-87/MPU6050 IMU, four 25GA370 encoder motors",
        "replace": "a USB camera, a GY-87 IMU, four 25GA370 encoder motors",
        "expect": 1,
        "note": "Fix 4b: Beta IMU is GY-87 (P00190). Anchor includes context to stay unique.",
    },

    # --- Fix 5: project simulator is the console --sim mode, not Gazebo (P00232) ---
    {
        "type": "para",
        "find": "Simulation Environment: Gazebo simulator for testing without physical robots.",
        "replace": "Simulation Environment: ROS integrates with simulators such as Gazebo. (This project does not use Gazebo; hardware-free testing is provided by the operations center's own built-in --sim mode, which spawns simulated robots speaking the production protocol.)",
        "expect": 1,
        "note": "Fix 5: clarify Gazebo is generic ROS; project simulator is --sim mode (P00232). Dropped the 'Section X' cross-reference per the note.",
    },

    # --- Fix 6: 'modular ROS packages' / 'System runs on ROS' overstate ROS coverage ---
    # 6a: §1.4 ROS Standardization (P00277). Docx ends '...modular ROS packages,.'
    {
        "type": "para",
        "find": "ROS Standardization: Building the system within the ROS ecosystem ensures that results are reproducible and extensible. Each component (SLAM, object detection, communication) is implemented as modular ROS packages,.",
        "replace": "ROS Standardization: Building the mapping and intervention robots within the ROS 2 ecosystem ensures that those components are reproducible and extensible. ROS 2 Humble runs only on the two Raspberry Pi robots (Alpha and Beta); the PySide6 operations center and the shared common/gpcore core library are ROS-free, and the ESP32-based Gamma robot runs no ROS, exposing a plain HTTP/JSON interface instead.",
        "expect": 1,
        "note": "Fix 6a: ROS 2 runs only on the two Pis; console and gpcore are ROS-free; Gamma is non-ROS (P00277)",
    },
    # 6b: §1.7 Software Constraints (P00374 + P00375 are two separate paras).
    # Replace the first bullet's full text and fold the second bullet's intent in.
    {
        "type": "para",
        "find": "System runs on ROS under Ubuntu Linux",
        "replace": "The Raspberry Pi robots run ROS 2 Humble under Ubuntu Linux; the operations center is a native PySide6 desktop application (no ROS), and the ESP32 robot runs firmware with an HTTP/JSON interface (no ROS)",
        "expect": 1,
        "note": "Fix 6b-i: rewrite 'System runs on ROS' Software Constraint (P00374)",
    },
    {
        "type": "para",
        "find": "Software must be compatible with ROS ecosystem",
        "replace": "Per-robot ROS 2 DDS traffic is confined to localhost; the only network doorway is the ZMQ/msgpack gateway",
        "expect": 1,
        "note": "Fix 6b-ii: rewrite 'compatible with ROS ecosystem' Software Constraint (P00375)",
    },
]

# ---------------------------------------------------------------------------
# Items intentionally NOT included as edits:
#
# MANUAL: "Optional additions" (markdown lines ~235-258) are explicitly optional
#   (gateway centerpiece, --sim mode add, SET POSE) -- not factual corrections,
#   so excluded per instructions.
#
# MANUAL: "Verify with hardware team" items (markdown ~261-282) excluded by rule
#   (do NOT include verify-with-hardware-team items): 4x4 m arena / 4 rooms;
#   chassis aluminum 1m x 1m x 1.5mm; Beta 85 mm wheels / 25GA370 408 CPR.
#
# MANUAL: Fix 4's parenthetical wiring-doc note and Fix 5's "Section X" guidance
#   are author guidance, not literal document text -- handled inline above.
# ---------------------------------------------------------------------------
