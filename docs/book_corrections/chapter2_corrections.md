# Chapter 2 (Literature Review) — Paste-Ready Corrections

Source chapter: `book_ch2.txt`. Corrections below touch ONLY claims that
describe THIS project's own choices. General background was left intact.
Each edit gives an exact FIND quote (for find-and-replace), the REPLACE
text, and the repo evidence.

---

## Edit 1 — §2.5.2: detection-model roles are INVERTED (SERIOUS)

**Location:** §2.5.2 (YOLO), Page 30-31, paragraph beginning "Based on the
literature review, YOLO was selected..."

**FIND** (exact quote):

> The dashboard supports selectable YOLO models, with the default configuration using a fire-detection model (fire.pt) to identify fire-related hazards and project detections onto the shared map. General object and human detection remains available as an alternative model configuration for broader situational awareness.[16][10]

**REPLACE** (paste-ready):

> The dashboard supports selectable YOLO models. The default (primary) model is a clean COCO-trained network (yolov8s.pt) used for general object and human detection — for example person, dog, and cat — and to project detections onto the shared map. A secondary, fire-only model (fire.pt) is available for identifying fire-related hazards in emergency-response scenarios. The fire-tuned model is deliberately kept as the secondary option and is never used as the primary, because its fire fine-tuning degrades its general (COCO) detection performance.[16][10]

**Reason + Evidence:** The book has the roles backwards. `config/fleet.yaml`
sets `default_model: yolov8s.pt` (the clean COCO net for person/dog/cat) as
PRIMARY, and `fire_model: fire.pt` as the SECONDARY, fire-only net. The
config comment is explicit: "the primary is a CLEAN COCO net
(person/dog/cat); fire.pt is the secondary, fire-ONLY net... it must never be
the primary." `dashboard_qt/inference/yolo_worker.py` reinforces this:
"Labels routed to the secondary fire model, never to the primary COCO net."
Evidence: `config/fleet.yaml` (lines 16-22, 32-43);
`dashboard_qt/inference/yolo_worker.py` (lines 1-16, 33-34).

---

## Edit 2 — §2.9 summary: same inverted model emphasis (SERIOUS)

**Location:** §2.9 (Summary of Literature Review), Page 36, paragraph
beginning "From a software and communication perspective..."

**FIND** (exact quote):

> In the area of perception, YOLO-based object detection methods emerged as a practical choice for real-time visual detection, with the deployed system focusing primarily on fire, smoke, and flame detection to support emergency response scenarios.

**REPLACE** (paste-ready):

> In the area of perception, YOLO-based object detection methods emerged as a practical choice for real-time visual detection. The deployed system uses a clean COCO-trained model as its primary detector for general object and human detection, with a dedicated secondary model available for fire, smoke, and flame detection to support emergency-response scenarios.

**Reason + Evidence:** Mirrors Edit 1 — the summary repeats the claim that
fire detection is the primary/default use case. Per `config/fleet.yaml` the
primary default model is the COCO net `yolov8s.pt`; fire detection is the
secondary path. Evidence: `config/fleet.yaml` (lines 16-22).

---

## Edit 3 — §2.2.2: "differential-drive configuration" conflicts with the four-wheel hardware

**Location:** §2.2.2 (Reviewed Projects and Systems), Page 26, "Research and
Educational Platforms" bullet (TurtleBot).

**FIND** (exact quote):

> These findings directly influenced our project’s decision to adopt ROS, use a differential-drive configuration, and rely on 2D LiDAR for mapping and localization[1].

**REPLACE** (paste-ready):

> These findings directly influenced our project’s decision to adopt ROS, use a four-wheel skid-steer base controlled kinematically as a differential drive, and rely on 2D LiDAR for mapping and localization[1].

**Reason + Evidence:** The intervention robot (Beta) uses four motors and four
quad encoders — a four-wheel platform, not a two-wheel differential-drive
chassis. This also aligns with §2.7.3, which states a four-wheel
configuration was selected. The base is driven kinematically as a
differential drive (left/right wheel-pair commands). Evidence: `CLAUDE.md`
("robot2 ... 4 motors + 4 quad encoders"); `book_ch2.txt` §2.7.3 (Page 35,
"a four-wheel configuration was identified as advantageous").

---

## Edit 4 — §2.6.3: clarify "in-process YOLO" (it is a crash-isolated subprocess)

**Location:** §2.6.3 (Dashboard and Monitoring), Page 32-33, paragraph
beginning "After evaluating both web-based and native desktop frameworks..."

**FIND** (exact quote):

> its ability to integrate directly with ZeroMQ transport and in-process YOLO inference without browser-imposed constraints.

**REPLACE** (paste-ready):

> its ability to integrate directly with ZeroMQ transport and to host YOLO inference inside the desktop application. Rather than running the model in the UI thread, the console isolates YOLO in a dedicated crash-isolated subprocess, so a model crash, hang, or out-of-memory event cannot freeze or kill the operator console — a level of native integration and process control that a browser-based dashboard cannot provide.

**Reason + Evidence:** "in-process YOLO" understates and slightly misstates
the design. YOLO does not run in the PySide6 process itself; it runs in a
crash-isolated CHILD PROCESS managed by the desktop app, with hang detection
and respawn. The distinction (vs. a browser) is the point being made.
Evidence: `dashboard_qt/inference/yolo_worker.py` (docstring lines 1-16: "The
model runs in a CHILD PROCESS: a torch/ultralytics crash, OOM, or hang can
never freeze or kill the operator console"); `CLAUDE.md` ("YOLO in a
crash-isolated subprocess").

---

## Verified correct (no change needed)

The following passages were audited against the repo and are ACCURATE as
written. They describe approaches reviewed in the literature but explicitly
NOT adopted by this project, with the correct adopted alternative stated.
Leave them unchanged.

- **§2.4.4 — EKF / `robot_localization`.** The text says EKF-based fusion was
  studied in the review but the actual implementation uses a custom
  complementary encoder+gyro fusion for the intervention robot and rf2o laser
  scan odometry + slam_toolbox for the mapping robot. This matches the project
  (CLAUDE.md: "yaw integrated in the bridge... encoder-heading fallback";
  "rf2o laser odometry"; odometry runs laptop-side). Correctly disclaimed.

- **§2.4.2 / §2.9 — GMapping vs. slam_toolbox.** The text says GMapping was an
  initial candidate but the final implementation adopted slam_toolbox (rf2o
  laser odometry, 0.025 m resolution). Consistent with CLAUDE.md (Alpha is the
  SLAM mapper with rf2o laser odometry). Correctly disclaimed.

- **§2.4.2 — Cartographer.** Reviewed for insight, not selected. Background
  only; no project-specific claim to correct.

- **§2.4.2 Table 2.3 / RTAB-MAP.** Listed in the SLAM comparison table as
  background; not claimed as adopted. No change needed.

- **§2.6.3 — rosbridge / ROS web bridge.** The text says rosbridge is an
  optional debug-only fallback and NOT used in the production monitoring
  workflow; the primary path is ZMQ/msgpack directly to the PySide6 dashboard.
  This matches the architecture (CLAUDE.md: msgpack-over-ZMQ gateway is the
  only network door; PySide6 console over QThread transport). Correctly
  disclaimed.

- **§2.6.2 — ZeroMQ/msgpack over TCP, ROS confined to localhost.** Matches
  CLAUDE.md (msgpack-over-ZMQ protocol; ports 5556-5560; ROS DDS kept on
  localhost only). Accurate.
