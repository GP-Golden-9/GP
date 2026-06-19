# Chapter 4 (Implementation) — Paste-Ready Corrections

Source text audited: `book_ch4.txt`. Every corrected value was verified against
the repository code/config cited under each edit. Quotes of the original are
exact (whitespace/line-wrap normalized only where the PDF extraction split a
word across lines).

---

## 4.2.2 Visual Hazard Detection Implementation

### Edit 1 — YOLO model roles (SERIOUS)

**Location:** 4.2.2, "Dashboard YOLO Manager" bullet (page 67), the line
beginning "Loads the YOLO fire model...".

**FIND (exact):**
> Loads the YOLO fire model (defaulting to fire.pt model parameters)

**REPLACE:**
> Loads two YOLO models: the PRIMARY is a clean COCO network
> (defaulting to `yolov8s.pt`) used for person/dog/cat detection, and an
> optional SECONDARY fire-only network (`fire.pt`) whose detections are
> trusted only for the `Fire` class. The fire fine-tune wrecked `fire.pt`'s
> COCO classes (on a real backlit frame it scored 0% on a person that
> `yolov8s.pt` scored 92% on), so it is never used as the primary detector.

**Reason + Evidence:** The default model is `yolov8s.pt`, not `fire.pt`.
`config/fleet.yaml` lines 16-22 set `default_model: yolov8s.pt` and
`fire_model: fire.pt  # secondary; only its 'Fire' class is trusted`, with a
comment that fire.pt "must never be the primary." `dashboard_qt/app_config.py`
lines 65-68 (`default_model: str = 'yolov8s.pt'`) and the docstring of
`_child_main` in `dashboard_qt/inference/yolo_worker.py` lines 130-137
("the PRIMARY model (a clean COCO net) ... an optional secondary model
(fire.pt) handles ONLY 'fire'") confirm the roles.

---

### Edit 2 — Add the real 3-stage detection pipeline (MISSING)

**Location:** 4.2.2, "Dashboard YOLO Manager" bullet, immediately after the
warm-up sentence ("Runs a throwaway black-frame forward pass...").

**FIND (exact):**
> Receives incoming frames via multiprocessing input queues

**REPLACE:**
> Runs a three-stage detection pipeline on every frame: (1) the primary COCO
> model (`yolov8s.pt`) for person/dog/cat; (2) the secondary fire-only model
> (`fire.pt`), restricted to its `Fire` class; and (3) a classical
> color/shape flame-prop detector (`detect_flame_prop`) that finds a
> printed/animated flame the trained net cannot see — a tall blob holding both
> saturated red/orange and saturated yellow. The three result sets are merged,
> with flame-prop hits added only when they do not overlap a real-fire box.
> Receives incoming frames via multiprocessing input queues

**Reason + Evidence:** `dashboard_qt/inference/yolo_worker.py`: primary
inference at lines 220-222, secondary fire pass at lines 226-229, the classical
`detect_flame_prop` (lines 51-91) invoked as the "Tertiary pass" at lines
230-237 with the IoU overlap guard (`_iou(...) < 0.3`). The flame-prop stage is
gated by `fire_prop_detector: true` in `config/fleet.yaml` line 53.

---

### Edit 3 — Worker returns an empty JPEG, not an annotated one (SERIOUS)

**Location:** 4.2.2, "Dashboard YOLO Manager" bullet, the line beginning
"Performs inference, plots bounding boxes...".

**FIND (exact):**
> Performs inference, plots bounding boxes, and returns annotated JPEGs and a detection list

**REPLACE:**
> Performs inference and returns an EMPTY JPEG placeholder (`b''`) together
> with a list of normalized detections; it does not draw on the frame.
> Rendering is decoupled: the UI displays the raw camera frame as soon as it
> arrives and overlays the bounding boxes as vector graphics, so live video
> latency is bounded by the network, not by inference, and no second JPEG is
> re-encoded or shipped across the process boundary.

**Reason + Evidence:** `dashboard_qt/inference/yolo_worker.py` line 245 emits
`out_q.put(('annotated', frame_id, b'', detections))` — the third element is
the empty bytes `b''`. The comment at lines 239-244 explains the "Decoupled
rendering: the UI shows the RAW frame ... and overlays these boxes as vectors
... we skip plot() + JPEG re-encode."

---

### Edit 4 — Generic USB camera, not "Logitech"

**Location:** 4.2.2, "Robot Video Streamer" bullet (page 67).

**FIND (exact):**
> It captures frames from the Logitech USB camera (640x480 resolution at 15 FPS)

**REPLACE:**
> It captures frames from a generic USB camera (device index 0, 640x480
> resolution at 15 FPS)

**Reason + Evidence:** `config/robot2.yaml` lines 24-28 set the camera by
device index only (`device: 0`, `width: 640`, `height: 480`, `fps: 15`) — no
specific make/model is configured.

---

## 4.2.3 Sensor Integration

### Edit 5 — Beta odometry runs on the LAPTOP, not on-robot (SERIOUS)

**Location:** 4.2.3, "Outcome" paragraph (page 68).

**FIND (exact):**
> Beta uses a custom complementary filter in navigation/robot2_odom.py fusing wheel encoders (408 CPR) and the GY-87 IMU gyroscope Z-axis rate.

**REPLACE:**
> Beta uses a custom complementary filter (not an EKF) that fuses the wheel
> encoders (408 counts/rev) with the GY-87 IMU gyroscope Z-axis rate. This
> fusion was MOVED OFF the Pi onto the laptop
> (`dashboard_qt/state/local_odom.py`), which reconstructs the pose from the
> raw encoder and gyro values streamed in each telemetry frame; the heading
> itself is integrated at 50 Hz on the Pi-side bridge
> (`navigation/robot2_bridge.py`) for accuracy. The legacy on-robot node
> `navigation/robot2_odom.py` is no longer in the live path.

**Reason + Evidence:** `dashboard_qt/state/local_odom.py` module docstring
(lines 1-15): "Laptop-side wheel + gyro odometry (moved OFF the Pi,
2026-06-16). `navigation/robot2_odom.py` fused encoders + IMU ... burned ~80%
of a Pi 3B+ core ... the powerful laptop reconstructs the pose here." The class
keeps "Same kinematics, slip gate, gyro-bias auto-cal." The 50 Hz heading
integration lives in `navigation/robot2_bridge.py` lines 160-173 ("50 Hz yaw
integration done HERE, not in the gateway"), confirmed by the consuming comment
in `gateway/gateway_node.py` lines 181-184 ("Beta's bridge integrates yaw at
50 Hz"). CLAUDE.md "Current hardware state" records the same move. The
complementary-filter (non-EKF) characterization is retained as correct.
(Note: 408 is counts per revolution at 1x decoding per `config/robot2.yaml`
lines 57-59; "408 CPR" was reworded to "408 counts/rev" for precision.)

---

### Edit 6 — Add Beta's two front HC-SR04 ultrasonics (MISSING)

**Location:** 4.2.3, "Low-Level (Arduino)" bullet list (page 68), and the
"Outcome" paragraph.

**FIND (exact):**
> • Reads ultrasonic distance sensors (Beta Mega) and MQ-5 gas sensor (Gamma ESP32)

**REPLACE:**
> • Reads two front-facing HC-SR04 ultrasonic distance sensors on Beta's Mega
>   (LEFT trig=30/echo=31, RIGHT trig=32/echo=33) and the MQ-5 gas sensor on
>   Gamma's ESP32

Additionally, append to the end of the 4.2.3 "Outcome" paragraph:

**ADD (after the Gamma sentence ending "...to ensure reliable hazard detection."):**
> Because Beta carries no LiDAR, its two front HC-SR04 ultrasonics are its only
> real-time obstacle sense: the firmware reads them round-robin and
> median-filters them, and the bridge publishes them as `/ultrasonic/{left,right}`.
> They back-stop both manual driving and autonomous goto — forward motion is
> hard-stopped at 25 cm (re-enabled above 40 cm by hysteresis) and goto begins a
> proportional slow-down at 60 cm.

**Reason + Evidence:** `config/robot2.yaml` `ultrasonic:` block lines 156-176:
`stop_cm: 25`, `clear_cm: 40`, `slow_cm: 60`, and the pin comment "LEFT
TRIG=30 ECHO=31 RIGHT TRIG=32 ECHO=33"; header comment "Beta has no lidar, so
these are its only real-time obstacle sense ... blocks forward motion under
stop_cm; goto slows under slow_cm." CLAUDE.md "Current hardware state" lists the
same wiring and the forward-stop/slowdown guard.

---

## 4.1 Hardware Implementation / Table 4.1 (Power)

### Edit 7 — Beta has no steering servo; the BEC servo claim is conflated (SERIOUS)

**Location:** 4.1, "Implemented Power Solution" paragraph (page 64).

**FIND (exact):**
> The second converter (a dedicated BEC buck) regulates the voltage to 6.0 V / 3 A, dedicated to Beta's SG90 navigation servo motor.

**REPLACE:**
> The second converter (a dedicated BEC buck) regulates the voltage to a
> servo-rail level for the auxiliary servos. Beta is a four-wheel skid-steer
> platform with NO steering servo — its single servo is an ARM servo (firmware
> pin 5); steering is done differentially by the four drive motors. The
> steerable sensor-mount servo is on Gamma (the ESP32 inspector), driven via
> its `/servo?deg=` endpoint.

**Reason + Evidence:** `config/robot2.yaml` `accessories.servo` lines 184-189
(`pin: 5`, range 10-170 deg, `home_deg: 90`) is the arm servo; there is no
steering servo entry. The drive section (`drive:`, lines 51-108) is skid-steer
(`turn_pwm`, four-wheel pivots that "scrub four wheels"). Gamma's sensor-mount
servo is the steerable one: `config/robot3.yaml` and book 4.2.4 already note
"`/servo?deg=S` for steering the sensor mount." CLAUDE.md fleet table lists
Beta with an "arm servo" and Gamma with a "servo" sensor mount.
**Servo-rail voltage = VERIFY WITH HARDWARE TEAM** (no servo-rail voltage value
exists in code/config; the "6.0 V" figure cannot be confirmed from the repo).

---

### Edit 8 — Buck "5.1 V" understates the Pi-pin setpoint

**Location:** 4.1, "Implemented Power Solution" paragraph (page 64), and Table 4.1.

**FIND (exact):**
> The first converter regulates the battery voltage to 5.1 V / 5 A, dedicated to powering the Raspberry Pi and Arduino Mega logic.

**REPLACE:**
> The first converter supplies the Raspberry Pi and Arduino Mega logic rail. The
> design ceiling is 5.25 V measured AT THE PI PINS; because the wiring path
> drops roughly 0.4-0.5 V under load, the buck output is set higher than the
> Pi-pin target to compensate. Heatsinks are recommended (Beta reached a 69 °C
> soft cap under load).

**Reason + Evidence:** CLAUDE.md "Current hardware state": "Pi power: the 5.25 V
ceiling is AT THE PI PINS, not the buck (~0.4-0.5 V path drop). Heatsinks
recommended (Beta hit 69 °C soft-cap)." The exact buck-output dial setting and
the 5 A current rating are not in code — see VERIFY section.

---

### Edit 9 — Acknowledge the two over-voltage incidents (MISSING)

**Location:** 4.1, end of the "Implemented Power Solution" discussion, just
before "A summary of the implemented power architecture..." (page 64-65).

**ADD (new sentences):**
> Power-safety discipline was reinforced by two over-voltage incidents during
> development. In one, a buck converter mistakenly set to 10 V was connected to
> Gamma's electronics, stressing the ESP32, its IMU, and the MQ gas sensor (the
> ESP32 survived; the IMU was likely lost). This was the team's second
> over-voltage event, after which the standing rule became: always measure the
> buck output at the terminals before connecting any load.

**Reason + Evidence:** CLAUDE.md "Current hardware state": "Gamma over-voltage
(2026-06-13): a buck set to 10 V hit the ESP32 + IMU + MQ sensor. ESP32 SURVIVED
(verified). IMU likely dead ... Always measure the buck at the terminals before
connecting — this was the team's 2nd over-voltage event."

---

### Corrected Table 4.1

| Component | Specification | Function |
|-----------|---------------|----------|
| Main Battery | 3S LiPo, 11.1 V nominal, 5000 mAh (~67 Wh) | Primary energy source; powers motor drivers and pump relay directly |
| Buck Converter 1 | 11.1 V -> Pi/logic rail; target 5.25 V at the Pi pins (buck set higher to offset ~0.4-0.5 V path drop) | Powers Raspberry Pi and Arduino Mega logic components |
| Buck Converter 2 (BEC) | 11.1 V -> servo rail (voltage VERIFY WITH HARDWARE TEAM) | Servo rail for auxiliary servos: Beta's ARM servo (pin 5) and Gamma's steerable sensor-mount servo. Beta is skid-steer with NO steering servo |
| Capacitive Filters | Output-stage capacitors | Suppress voltage ripple and transients |
| Inline Fuse | Load-based rated fuse | Overcurrent and short-circuit protection |
| Voltage Monitoring | Designed voltage divider (not in firmware) | Manual monitoring via chassis-mounted LED voltmeters |

Notes vs. the original table:
- Buck 1: "5.1 V / 5 A" -> Pi-pin target 5.25 V with documented path drop
  (CLAUDE.md). The "5 A" rating is not in the repo (VERIFY).
- Buck 2 (BEC): "6.0 V / 3 A ... Beta's SG90 navigation servo" was wrong —
  Beta has no steering servo (Edit 7). Voltage/current ratings are not in the
  repo (VERIFY).

---

## 4.2.5 Dashboard Implementation

### Edit 11 — Esp32Link poll rate is 3 Hz, not 2 Hz

**Location:** 4.2.5, "State Store & Transport Threading" paragraph (page 69).

**FIND (exact):**
> Esp32Link (polls the HTTP endpoints at 2 Hz)

**REPLACE:**
> Esp32Link (polls the HTTP endpoints at 3 Hz)

**Reason + Evidence:** `config/robot3.yaml` line 11: `poll_hz: 3
# fresher gas/telemetry for the gauge`.

---

## 4.3 System Integration

### Edit 10 — Firmware watchdog is a flat 1.0 s, not "1.0 to 2.0 second"

**Location:** 4.3, "Command Deadman and Safety Chains" paragraph (page 70-71).

**FIND (exact):**
> Finally, the Arduino Mega firmware implements a 1.0 to 2.0-second hardware watchdog that immediately cuts off motor PWM and de-energizes the water pump relay if USB communication is interrupted.

**REPLACE:**
> Finally, the Arduino Mega firmware implements a flat 1.0-second hardware
> watchdog that immediately cuts off motor PWM and de-energizes the water pump
> relay if USB communication is interrupted.

**Reason + Evidence:** `firmware/robot2_controller_v5/robot2_controller_v5.ino`
line 131: `#define WATCHDOG_MS 1000UL   // auto-stop if no command`, enforced at
lines 1034-1039. (The 2000 ms value belongs to Alpha's
`robot1_controller_v3.ino` `TIMEOUT_MS`, not Beta's Mega in this safety chain.)

---

## 4.2.1 SLAM Implementation

### Edit 12 — Clarify: scan-matching only, no wheel odometry (optional)

**Location:** 4.2.1, "Code and Launch Integration" bullet describing
`rf2o_laser_odometry` (page 66).

**FIND (exact):**
> rf2o_laser_odometry: uses scan matching to publish /odom and odom->base_link TF

**REPLACE:**
> rf2o_laser_odometry: uses scan matching to publish /odom and odom->base_link
> TF. Alpha carries no wheel encoders in the SLAM path — rf2o scan matching
> estimates ALL of the robot's motion from the laser alone.

**Reason + Evidence:** `mapping/mapper.yaml` line 27 `use_scan_matching: true`
and line 29 comment: "No wheel odometry on robot1: scan matching estimates ALL
motion." Consistent with CLAUDE.md fleet table (Alpha: "rf2o laser odometry, no
wheel encoders").

---

## VERIFY WITH HARDWARE TEAM (power specs not in code)

These figures appear only in the book's Table 4.1 / power prose and have no
source in the repository. Confirm them against the physical hardware before
publishing:

1. **Buck Converter 1 current rating "5 A"** — no current rating in code; only
   the 5.25 V Pi-pin ceiling is documented (CLAUDE.md).
2. **Buck Converter 1 dialed output voltage** — CLAUDE.md gives the Pi-pin
   target (5.25 V) and the path drop (~0.4-0.5 V) but not the exact buck-output
   setpoint; confirm the value the team dials in.
3. **Buck Converter 2 (BEC) output voltage "6.0 V"** — no servo-rail voltage in
   code. Confirm the actual servo-rail voltage for Beta's arm servo and Gamma's
   sensor-mount servo.
4. **Buck Converter 2 (BEC) current rating "3 A"** — not in code.
5. **Inline fuse rating** — "load-based rated fuse"; the actual amperage is not
   in the repo.
6. **Capacitive filter values** — not specified in code.
7. **LiPo "~67 Wh" usable energy** — derived figure (11.1 V x 5000 mAh ~= 55.5
   Wh nominal; 67 Wh implies a higher count). Confirm the battery's actual pack
   nameplate. (Not flagged as a required fix, but worth a sanity check.)
