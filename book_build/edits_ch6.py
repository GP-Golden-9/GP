# -*- coding: utf-8 -*-
# Machine-applyable edit list for Chapter 6 (Conclusion & Future Work) + References.
#
# Each "find" is verified to appear EXACTLY (including unicode such as the degree
# sign and the arrow ->) as a contiguous substring within a SINGLE paragraph of the
# real Word document (anchored against docx_paras.txt, paragraphs P01277-P01295).
# "replace" rewrites that substring in an honest-but-positive academic tone.
#
# Anchors (docx paragraph -> fix):
#   P01277 -> Edit 2  (6.2 Power Stability)
#   P01279 -> Edit 3  (6.2 Sensor Fusion)
#   P01280 -> Edit 1  (6.2 Visual Perception)
#   P01283 -> Edit 4  (6.2 Environmental Sensing)
#   P01290 -> Edit 5  (6.3 Future Enhancements: Beta ultrasonic item -> next steps)
#   P01293 -> Edit 6  (6.4 Deployment: SAR overclaim -> indoor + SAR aspiration)
#
# References: no concrete paragraph to change in the docx -- see "# MANUAL:" notes
# at the bottom. RTAB-Map ([9]) does NOT appear anywhere in docx_paras.txt, so there
# is nothing to anchor; recommendations are left as manual comments only.

EDITS = [

    # --- Edit 1: 6.2 Visual Perception (P01280) -------------------------------
    {
        "type": "para",
        "find": "Visual Perception : Real-time fire, smoke, and flame detection was successfully implemented using YOLO-based models (defaulting to fire.pt).",
        "replace": "Visual Perception : A real-time hazard-detection pipeline was implemented, combining a primary clean COCO YOLOv8s network (person/dog/cat) with a secondary fire-only neural model (fire.pt) and a classical flame-property detector for saturated red-and-yellow flame shapes. Of the neural fire model, only its single \"Fire\" class is trusted (it does not provide reliable separate smoke or flame classes). It must be stated honestly that the neural fire model's measured confidence on real fire imagery is limited (approximately 28-37 percent against a 0.80 alarm gate), so dependable demonstration detection currently leans on the classical flame-property detector. Raising the accuracy of the neural fire model on genuine fire is identified as the project's primary item of future work (see Section 6.3).",
        "expect": 1,
        "note": "Reframe fire-detection 'successfully implemented' as a 3-stage pipeline (COCO yolov8s primary + fire.pt secondary + classical flame-prop detector); acknowledge ~28-37% real-fire confidence vs 0.80 gate. Evidence: config/fleet.yaml; docs/field_debug_report_2026-06-11.md C-7.",
    },

    # --- Edit 2: 6.2 Power Stability (P01277) ---------------------------------
    {
        "type": "para",
        "find": "Power Stability: A robust power architecture was implemented, featuring a 3S LiPo battery and dual independent buck converters to protect sensitive electronics, such as the Raspberry Pi 4, from motor-induced voltage brownouts.",
        "replace": "Power Stability: Power-delivery problems were systematically diagnosed and mitigated. The platform uses a 3S LiPo battery with dual independent buck converters intended to isolate sensitive electronics, such as the Raspberry Pi, from motor-induced voltage brownouts. Achieving stable delivery proved to be a recurring engineering challenge rather than a one-time design: brownout crash-loops were traced to a 0.4-0.5 V drop along the cable-and-connector path between the buck terminals and the Pi pins, which was corrected by tuning the buck against a reading taken at the Pi pins under load (with bulk capacitors added at the buck output and the Pi connector). The team also records, as a hard lesson, an over-voltage incident in which a buck mis-set to 10 V damaged peripherals on the inspector robot (Gamma); the adopted procedure is now to measure voltage at the terminals before every connection.",
        "expect": 1,
        "note": "'robust ... protects from brownouts' -> 'diagnosed and mitigated', acknowledge delivery-path drop fix and the Gamma over-voltage incident. Evidence: docs/field_debug_report_2026-06-11.md B-7/B-8/B-12; CLAUDE.md. NOTE: docx paragraph has a trailing space after 'brownouts.'; find omits it (still a unique contiguous substring of P01277).",
    },

    # --- Edit 3: 6.2 Sensor Fusion (P01279) -----------------------------------
    {
        "type": "para",
        "find": "Sensor Fusion : The implementation of a custom complementary filter (fusing 25GA370 encoders and the GY-87 IMU gyroscope Z-axis rate) significantly improved rotational stability and reduced drift, with auto-bias calibration protecting translational tracking.",
        "replace": "Sensor Fusion : A custom complementary filter (fusing 25GA370 wheel encoders with the GY-87 IMU gyroscope Z-axis rate) was implemented and significantly improved rotational stability and reduced drift, with auto-bias calibration and a per-unit gyro scale correction protecting heading tracking. Two limitations are acknowledged honestly. First, residual yaw drift of approximately 25 degrees remains after calibration (down from roughly 45 degrees before), driven by the IMU's per-unit scale tolerance; this is why the platform is best characterized as dead-reckoning rather than drift-free localization. Second, Beta's GY-87 IMU intermittently drops off the I2C bus, at which point the firmware streams frozen gyro values and the heading freezes until a power cycle; a hardware rewire of the IMU supply (from 3.3 V to 5 V) and resolder is the top open hardware ticket. An encoder-only heading fallback exists to survive a total gyro dropout.",
        "expect": 1,
        "note": "Add GY-87 I2C dropout + ~25 degree residual drift caveats. Evidence: CLAUDE.md (top demo ticket); docs/field_fixes_and_runbook_2026-06-18.md sec.2; config/robot2.yaml gyro_scale_correction 1.0304.",
    },

    # --- Edit 4: 6.2 Environmental Sensing (P01283) ---------------------------
    {
        "type": "para",
        "find": "Environmental Sensing : The integration of the MQ-5 gas sensor on the ESP32 Gamma platform allowed for the reliable detection of hazardous gases, triggering latched local alarms and dashboard warning banners when exceeding the 3000 ADC count threshold.",
        "replace": "Environmental Sensing : An MQ-5 gas sensor was integrated on the ESP32 Gamma platform, with firmware that triggers latched local alarms and dashboard warning banners when readings exceed the configured ADC-count threshold. One caveat must be recorded: an over-voltage incident (a buck mis-set to 10 V) struck Gamma's electronics. The ESP32 itself survived and was verified, but the onboard IMU is likely damaged and the MQ gas sensor reading and alarm threshold should be re-verified before relying on gas detection; the firmware is written to tolerate a missing IMU.",
        "expect": 1,
        "note": "Add Gamma over-voltage hardware-damage caveat; soften the specific '3000 ADC count' to 'configured threshold' pending re-verification. Evidence: CLAUDE.md (Gamma over-voltage 2026-06-13).",
    },

    # --- Edit 5: 6.3 Future Enhancements (P01290) -----------------------------
    # The docx 'Beta Sensor Integration' work is ALREADY DONE (ultrasonics wired,
    # forward-stop guard live). Replace the whole paragraph with three genuine
    # next steps. NOTE: the docx paragraph has NO leading bullet character; the
    # replacement also uses no bullet glyph, just the three labelled items.
    {
        "type": "para",
        "find": "Beta Sensor Integration: Completing the physical wiring and firmware integration for Beta's ultrasonic sensors. This will enable the forward-collision slowdown and obstacle avoidance guards to function automatically, removing the need for continuous manual operator supervision around physical hazards.",
        "replace": "Improved Fire-Detection Model: Training a fire-detection model on the team's own footage so that genuine fire scores well above the look-alike false positives that currently overlap it. This is the project's foremost acknowledged limitation (Section 6.2): with the present neural fire model a usable alarm threshold cannot separate real fire from false positives, so a better-trained model, not a higher threshold, is the real fix. IMU Hardware Rectification: Rewiring Beta's GY-87 IMU supply from the 3.3 V pin to 5 V and resoldering its connections to stop the intermittent I2C bus dropouts that currently freeze the heading estimate, then re-running the gyro scale calibration to reduce residual yaw drift. Direct Robot-to-Robot Communication (optional): The fleet is currently centralized by design, with all inter-robot coordination brokered through the operator console; a future enhancement could add direct robot-to-robot messaging for tighter cooperative behaviors without a console in the loop.",
        "expect": 1,
        "note": "Beta ultrasonic item already done -> replace with genuine next steps (better fire model; GY-87 3.3->5V rewire; optional robot-to-robot comms). Battery/EKF/video items (P01287/P01288/P01289) left unchanged. Evidence: CLAUDE.md (Beta ultrasonics WIRED; IMU ticket); config/robot2.yaml. NOTE: corrections doc shows '* ' bullet prefixes and em dashes; docx paragraph has neither, so replace uses plain labelled sentences.",
    },

    # --- Edit 6: 6.4 Potential Real-World Deployment (P01293) ------------------
    # Soften the SAR / collapsed-buildings overclaim. docx paragraph has no
    # leading bullet character; replacement keeps the same convention.
    {
        "type": "para",
        "find": "Search and Rescue (SAR): In collapsed buildings, industrial areas, or disaster zones, the system can quickly generate maps, identify hazards using visual fire and smoke detection, and assess structural or atmospheric hazards early in the mission.",
        "replace": "Indoor Facility Monitoring and Inspection (primary target): Within controlled indoor environments such as warehouses, industrial floors, hospitals, and similar facilities, the system can generate occupancy maps, flag visual hazards, and sample for hazardous gases while keeping personnel out of harm's way. This is the deployment class the current prototype is genuinely tuned for: it operates on a self-contained LAN with no internet and no GPS, navigates by dead-reckoning (with the approximately 25-degree residual yaw drift noted in Section 6.2), and is calibrated for flat indoor floors. Search and Rescue (long-term aspiration): Collapsed-building and disaster-zone search and rescue is a compelling long-term goal, but reaching it would require substantial further work beyond the current prototype, including robust localization on unstructured rubble, communication that does not depend on a fixed LAN, and ruggedized mobility. It is presented here as a direction for future research, not a demonstrated capability.",
        "expect": 1,
        "note": "Soften 'collapsed buildings/disaster zones' to controlled indoor facility monitoring (primary); recast rubble-SAR as long-term aspiration. Existing 'Industrial and Facility Monitoring' (P01294) and 'Routine Inspections' (P01295) left unchanged. Evidence: CLAUDE.md (LAN, no internet/GPS); docs/field_fixes_and_runbook_2026-06-18.md sec.2; config/robot2.yaml; mapping/mapper.yaml.",
    },

]

# ============================================================================
# MANUAL / ADVISORY (no machine edit -- nothing concrete to anchor in the docx)
# ============================================================================
#
# MANUAL: References [9] RTAB-Map -- the corrections doc recommends flagging
#   reference [9] (RTAB-Map) as related-work rather than the implemented method
#   (the project uses slam_toolbox / CeresSolver @ 0.025 m/cell, per
#   mapping/mapper.yaml). However, NO RTAB-Map citation, "Real-Time
#   Localization", or "AMR" string appears anywhere in docx_paras.txt, so there
#   is no paragraph to edit. ACTION FOR AUTHOR: if/when the reference list and
#   its in-text citations are present in the document, ensure the prose does not
#   imply RTAB-Map was implemented; add a sentence distinguishing the surveyed
#   approach from the implemented slam_toolbox backend.
#
# MANUAL: Missing citations for the core toolchain -- the conclusion names
#   technologies that are uncited (advisory only, not anchorable as prose edits):
#     - slam_toolbox  (Macenski & Jambrecic, JOSS 2021)        [mapping/mapper.yaml]
#     - rf2o laser odometry (Jaimez et al., ICRA 2016)         [field_debug_report A-6]
#     - ZeroMQ (msgpack-over-ZMQ gateway transport)            [CLAUDE.md / config]
#     - MessagePack (wire serialization)                       [CLAUDE.md]
#     - PySide6 / Qt (operator console)                        [CLAUDE.md / dashboard_qt]
#     - YOLOv8 / Ultralytics (detection backbone)              [config/fleet.yaml]
#   ACTION FOR AUTHOR: add these to the reference list and cite them where the
#   conclusion mentions each technology.
