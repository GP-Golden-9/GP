# Chapter 6 (Conclusion & Future Work) + References — Paste-Ready Corrections

These are surgical, paste-ready edits for Chapter 6 of the GP graduation book.
Each fix removes an overclaim or corrects a factual error so the conclusion
honestly represents what was built, while preserving the real achievements.
Every claim below is grounded in a repo file (cited under each edit). Original
text is quoted exactly from `book_ch6_refs.txt`.

Tone target: honest-but-positive academic — overclaims are reframed as
accurate achievements plus acknowledged limitations, not deleted.

---

## Edit 1 — 6.2 Visual Perception (fire/smoke detection OVERCLAIM)

**Location:** Section 6.2 "Achievements of the Project" → "Visual Perception"
(page 83, lines 51-52).

**FIND (exact quote):**
> Visual Perception : Real-time fire, smoke, and flame detection was successfully
> implemented using YOLO-based models (defaulting to fire.pt).

**REPLACE (paste-ready):**
> Visual Perception : A real-time hazard-detection pipeline was implemented,
> combining a primary clean COCO YOLOv8s network (person/dog/cat) with a
> secondary fire-only neural model (fire.pt) and a classical flame-property
> detector for saturated red-and-yellow flame shapes. Of the neural fire model,
> only its single "Fire" class is trusted (it does not provide reliable separate
> smoke or flame classes). It must be stated honestly that the neural fire
> model's measured confidence on real fire imagery is limited (approximately
> 28-37 percent against a 0.80 alarm gate), so dependable demonstration
> detection currently leans on the classical flame-property detector. Raising
> the accuracy of the neural fire model on genuine fire is identified as the
> project's primary item of future work (see Section 6.3).

**Reason + Evidence:** "Real-time fire, smoke, and flame detection successfully
implemented (fire.pt)" overstates the result. `config/fleet.yaml` documents that
`default_model: yolov8s.pt` is the primary, `fire_model: fire.pt` is "secondary;
only its 'Fire' class is trusted", `fire_conf_min: 0.80`, and the comment states
"fire.pt's measured confidence on REAL fire photos is 28-37% -- at 0.80 the
audible alarm will essentially never trigger with this model ... The real fix
... is a better-trained model, not a threshold." The same file shows
`fire_prop_detector: true` ("Classical detector for a PRINTED/animated flame
prop ... that the real-fire net can't see -- for demos").
File: `config/fleet.yaml` (lines 16-53). Corroborated by
`docs/field_debug_report_2026-06-11.md` C-7 ("Fire alarm sensitivity and the
honest threshold").

---

## Edit 2 — 6.2 Power Stability (power "robustness" OVERCLAIM)

**Location:** Section 6.2 "Achievements of the Project" → "Power Stability"
(page 83, lines 41-43).

**FIND (exact quote):**
> Power Stability: A robust power architecture was implemented, featuring a 3S LiPo
> battery and dual independent buck converters to protect sensitive electronics, such as
> the Raspberry Pi 4, from motor-induced voltage brownouts.

**REPLACE (paste-ready):**
> Power Stability: Power-delivery problems were systematically diagnosed and
> mitigated. The platform uses a 3S LiPo battery with dual independent buck
> converters intended to isolate sensitive electronics, such as the Raspberry
> Pi, from motor-induced voltage brownouts. Achieving stable delivery proved to
> be a recurring engineering challenge rather than a one-time design: brownout
> crash-loops were traced to a 0.4-0.5 V drop along the cable-and-connector path
> between the buck terminals and the Pi pins, which was corrected by tuning the
> buck against a reading taken at the Pi pins under load (with bulk capacitors
> added at the buck output and the Pi connector). The team also records, as a
> hard lesson, an over-voltage incident in which a buck mis-set to 10 V damaged
> peripherals on the inspector robot (Gamma); the adopted procedure is now to
> measure voltage at the terminals before every connection.

**Reason + Evidence:** "A robust power architecture was implemented ... to
protect ... from ... brownouts" is presented as a finished, robust achievement.
The record shows it was a recurring battle: `docs/field_debug_report_2026-06-11.md`
documents brownout crash-loops (B-7 "The brownout crash-loop and the gate that
held"), the 0.4-0.5 V delivery-path drop (Executive Summary item 1; B-12
"4.83 volts -- the delivery-path discovery"), and the capacitor/cable fixes
(B-8). `CLAUDE.md` ("Current hardware state") records the Gamma over-voltage
event: "a buck set to 10 V hit the ESP32 + IMU + MQ sensor ... Always measure
the buck at the terminals before connecting -- this was the team's 2nd
over-voltage event."
Files: `docs/field_debug_report_2026-06-11.md` (B-7, B-8, B-12), `CLAUDE.md`.

---

## Edit 3 — 6.2 Sensor Fusion (missing IMU/drift CAVEAT)

**Location:** Section 6.2 "Achievements of the Project" → "Sensor Fusion"
(page 83, lines 47-50).

**FIND (exact quote):**
> Sensor Fusion : The implementation of a custom complementary filter (fusing
> 25GA370 encoders and the GY-87 IMU gyroscope Z-axis rate) significantly improved
> rotational stability and reduced drift, with auto-bias calibration protecting translational
> tracking.

**REPLACE (paste-ready):**
> Sensor Fusion : A custom complementary filter (fusing 25GA370 wheel encoders
> with the GY-87 IMU gyroscope Z-axis rate) was implemented and significantly
> improved rotational stability and reduced drift, with auto-bias calibration and
> a per-unit gyro scale correction protecting heading tracking. Two limitations
> are acknowledged honestly. First, residual yaw drift of approximately
> 25 degrees remains after calibration (down from roughly 45 degrees before),
> driven by the IMU's per-unit scale tolerance; this is why the platform is best
> characterized as dead-reckoning rather than drift-free localization. Second,
> Beta's GY-87 IMU intermittently drops off the I2C bus, at which point the
> firmware streams frozen gyro values and the heading freezes until a power
> cycle; a hardware rewire of the IMU supply (from 3.3 V to 5 V) and resolder is
> the top open hardware ticket. An encoder-only heading fallback exists to
> survive a total gyro dropout.

**Reason + Evidence:** The achievement is real but omits two documented
limitations. `CLAUDE.md` ("Current hardware state") lists the GY-87 as the
"top demo ticket": "intermittently DROPS OFF the I2C bus -- rewire VCC 3.3 V->5 V
+ resolder ... When it drops, firmware streams FROZEN non-zero gyro values ->
heading freezes." The ~25 deg residual drift is documented in
`docs/field_fixes_and_runbook_2026-06-18.md` section 2 "Yaw drift (~45 deg,
then ~25 deg after calibration)" and `config/robot2.yaml` (`gyro_scale_correction:
1.0304`, "the residual yaw drift after the 50 Hz heading fix"). The encoder
fallback is noted in `CLAUDE.md` and `config/robot2.yaml`
(`encoder_heading_weight`).
Files: `CLAUDE.md`, `docs/field_fixes_and_runbook_2026-06-18.md` (sec. 2),
`config/robot2.yaml` (lines 64-74).

---

## Edit 4 — 6.2 Environmental Sensing (missing Gamma hardware CAVEAT)

**Location:** Section 6.2 "Achievements of the Project" → "Environmental Sensing"
(page 83, lines 57-60).

**FIND (exact quote):**
> Environmental Sensing : The integration of the MQ-5 gas sensor on the ESP32
> Gamma platform allowed for the reliable detection of hazardous gases, triggering
> latched local alarms and dashboard warning banners when exceeding the 3000 ADC
> count threshold.

**REPLACE (paste-ready):**
> Environmental Sensing : An MQ-5 gas sensor was integrated on the ESP32 Gamma
> platform, with firmware that triggers latched local alarms and dashboard
> warning banners when readings exceed the configured ADC-count threshold. One
> caveat must be recorded: an over-voltage incident (a buck mis-set to 10 V)
> struck Gamma's electronics. The ESP32 itself survived and was verified, but the
> onboard IMU is likely damaged and the MQ gas sensor reading and alarm threshold
> should be re-verified before relying on gas detection; the firmware is written
> to tolerate a missing IMU.

**Reason + Evidence:** "reliable detection of hazardous gases" omits the
over-voltage damage. `CLAUDE.md` ("Current hardware state"): "Gamma
over-voltage (2026-06-13): a buck set to 10 V hit the ESP32 + IMU + MQ sensor.
ESP32 SURVIVED (verified). IMU likely dead ... MQ probably OK but re-check
`GAS_ALARM_THRESHOLD`." (Note: the threshold is named/configured in firmware,
hence the book's specific "3000 ADC count" figure is softened to "configured
threshold" pending re-verification.)
File: `CLAUDE.md`.

---

## Edit 5 — 6.3 Future Enhancements (Beta ultrasonic item is ALREADY DONE)

**Location:** Section 6.3 "Future Enhancements" → "Beta Sensor Integration"
bullet (page 84, lines 89-92).

**FIND (exact quote):**
> • Beta Sensor Integration: Completing the physical wiring and firmware integration
> for Beta's ultrasonic sensors. This will enable the forward-collision slowdown
> and obstacle avoidance guards to function automatically, removing the need for
> continuous manual operator supervision around physical hazards.

**REPLACE (paste-ready):**
> • Improved Fire-Detection Model: Training a fire-detection model on the team's
> own footage so that genuine fire scores well above the look-alike false
> positives that currently overlap it. This is the project's foremost
> acknowledged limitation (Section 6.2): with the present neural fire model a
> usable alarm threshold cannot separate real fire from false positives, so a
> better-trained model — not a higher threshold — is the real fix.
> • IMU Hardware Rectification: Rewiring Beta's GY-87 IMU supply from the 3.3 V
> pin to 5 V and resoldering its connections to stop the intermittent I2C bus
> dropouts that currently freeze the heading estimate, then re-running the gyro
> scale calibration to reduce residual yaw drift.
> • Direct Robot-to-Robot Communication (optional): The fleet is currently
> centralized by design — all inter-robot coordination is brokered through the
> operator console. A future enhancement could add direct robot-to-robot
> messaging for tighter cooperative behaviors without a console in the loop.

**Reason + Evidence:** The original bullet describes future work that is already
complete. Beta's two front HC-SR04 ultrasonics are WIRED and integrated with a
live forward-stop guard fused into autonomous navigation. `CLAUDE.md` ("Current
hardware state"): "Beta ultrasonics: WIRED (2 front HC-SR04, LEFT trig=30/echo=31,
RIGHT trig=32/echo=33, 5 V) ... Forward-stop guard + graceful slowdown live."
`config/robot2.yaml` (lines 156-176): `ultrasonic: enabled: true`,
`stop_cm: 25`, `slow_cm: 60`, with the bridge publishing `/ultrasonic/{left,right}`
and the local-nav fuser using them. The replacements are genuine next steps:
the fire-model gap (`config/fleet.yaml` comments; `docs/field_debug_report_2026-06-11.md`
C-7), the IMU rewire ticket (`CLAUDE.md`), and the console-brokered design
(`CLAUDE.md` architecture; "all centralized" per project goal).
Files: `CLAUDE.md`, `config/robot2.yaml` (lines 156-176), `config/fleet.yaml`.

> Note to author: the three existing legitimate future items — Battery
> Monitoring Integration (lines 74-78), Sensor Fusion and Odometry Upgrades /
> EKF or visual odometry (lines 79-83), and Video Stream Protocol Optimization
> (lines 84-88) — are accurate and should be KEPT unchanged. Only the
> "Beta Sensor Integration" bullet is replaced.

---

## Edit 6 — 6.4 Potential Real-World Deployment (SAR / disaster-zone OVERCLAIM)

**Location:** Section 6.4 "Potential Real-World Deployment" → "Search and
Rescue (SAR)" bullet (page 84, lines 97-100).

**FIND (exact quote):**
> • Search and Rescue (SAR): In collapsed buildings, industrial areas, or disaster
> zones, the system can quickly generate maps, identify hazards using visual fire
> and smoke detection, and assess structural or atmospheric hazards early in the
> mission.

**REPLACE (paste-ready):**
> • Indoor Facility Monitoring and Inspection (primary target): Within controlled
> indoor environments — warehouses, industrial floors, hospitals, and similar
> facilities — the system can generate occupancy maps, flag visual hazards, and
> sample for hazardous gases while keeping personnel out of harm's way. This is
> the deployment class the current prototype is genuinely tuned for: it operates
> on a self-contained LAN with no internet and no GPS, navigates by
> dead-reckoning (with the approximately 25-degree residual yaw drift noted in
> Section 6.2), and is calibrated for flat indoor floors.
> • Search and Rescue (long-term aspiration): Collapsed-building and disaster-zone
> search and rescue is a compelling long-term goal, but reaching it would require
> substantial further work beyond the current prototype — robust localization on
> unstructured rubble, communication that does not depend on a fixed LAN, and
> ruggedized mobility. It is presented here as a direction for future research,
> not a demonstrated capability.

**Reason + Evidence:** "collapsed buildings ... disaster zones ... assess
structural ... hazards" overstates a LAN-only, GPS-less, indoor-flat-tuned
dead-reckoning prototype. `CLAUDE.md` describes a "dedicated LAN router (no
internet required for operation)" and gives no GPS/global localization; the
~25 deg residual yaw drift is documented (`docs/field_fixes_and_runbook_2026-06-18.md`
sec. 2; `config/robot2.yaml`); SLAM and tuning are indoor/flat-floor oriented
(`mapping/mapper.yaml` resolution tuned for indoor A1M8 mapping; `config/robot2.yaml`
notes "low-friction tile" / carpet handling). Reframed toward controlled indoor
facility monitoring with rubble-SAR as a stated aspiration.
Files: `CLAUDE.md`, `docs/field_fixes_and_runbook_2026-06-18.md` (sec. 2),
`config/robot2.yaml`, `mapping/mapper.yaml`.

> Note to author: the existing "Industrial and Facility Monitoring" (lines
> 101-103) and "Routine Inspections" (lines 104-106) bullets are accurate and
> can be KEPT; Edit 6 only replaces the over-reaching SAR bullet. If the author
> prefers, the new "Indoor Facility Monitoring" item may be merged with the
> existing "Industrial and Facility Monitoring" bullet to avoid overlap.

---

## References — recommendations

These are advisory notes for the author; they do not change the achievements
text. The reference list itself is otherwise well-formed.

1. **Flag reference [9] (RTAB-Map) as related-work, not the implemented method.**
   Ref [9] — C. J. Lin, C. C. Peng, and S. Y. Lu, "Real-Time Localization for an
   AMR Based on RTAB-MAP" — is cited, but the project does NOT use RTAB-Map. The
   implemented SLAM backend is `slam_toolbox` (Ceres solver, 0.025 m/cell), per
   `mapping/mapper.yaml` (`solver_plugin: solver_plugins::CeresSolver`,
   `resolution: 0.025`). Keep [9] as legitimate related-work context, but ensure
   the prose does not imply RTAB-Map was used, and consider adding a sentence
   distinguishing the surveyed approach from the one implemented.

2. **Add citations for the actual core toolchain (currently uncited).** The book
   names several core technologies in the conclusion that have no corresponding
   reference. Recommend adding citations for:
   - **slam_toolbox** (S. Macenski and I. Jambrecic, "SLAM Toolbox: SLAM for the
     dynamic world," JOSS, 2021) — the implemented SLAM. Evidence:
     `mapping/mapper.yaml`.
   - **rf2o laser odometry** (Jaimez, Monroy, Gonzalez-Jimenez, "Planar Odometry
     from a Radial Laser Scanner," ICRA 2016) — the laser-odometry source build.
     Evidence: `docs/field_debug_report_2026-06-11.md` A-6.
   - **ZeroMQ** — the inter-process / network transport (msgpack-over-ZMQ
     gateway). Evidence: `CLAUDE.md` (Architecture), `config/robot2.yaml` (zmq
     ports).
   - **MessagePack (msgpack)** — the wire serialization format. Evidence:
     `CLAUDE.md` ("versioned msgpack-over-ZMQ protocol").
   - **PySide6 / Qt** — the operator console framework. Evidence: `CLAUDE.md`,
     `dashboard_qt/`.
   - **YOLOv8 / Ultralytics** — the object-detection backbone. Evidence:
     `config/fleet.yaml` (`yolov8s.pt`, `fire.pt`).
   Citing these strengthens the academic record by grounding the conclusion's
   technology claims in the literature.

---

## Summary of what was preserved (verified true — do NOT weaken)

For the author's confidence, these conclusion claims were checked and are
accurate as written:
- Offloaded, crash-isolated YOLO inference in a child subprocess over a ZMQ
  video stream (`CLAUDE.md`, `config/fleet.yaml`, `dashboard_qt/`).
- Native PySide6 desktop dashboard aggregating ZMQ + HTTP streams (`CLAUDE.md`).
- Custom complementary filter (NOT an EKF) for odometry (`config/robot2.yaml`,
  `docs/field_debug_report_2026-06-11.md` B-5).
- 0.025 m/cell occupancy mapping via slam_toolbox (`mapping/mapper.yaml`).
- The >= 12 FPS video KPI, met (13.3 FPS measured,
  `docs/field_debug_report_2026-06-11.md` B-4).
