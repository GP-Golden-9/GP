# GP Swarm Emergency Robotics — Field Debugging & Hardening Report

**Period covered:** 2026-06-10 (night) → 2026-06-11 (evening)
**Robots:** Alpha (robot1, Pi 4 mapper) · Beta (robot2, Pi 3B+ intervener)
**Console:** GP Operations Center (PySide6, Windows laptop)
**Commit range:** `fb9b33d` … `e18d699` (34 commits, all pushed to `origin/main`)
**Authors:** GP team (hardware) + Claude (software, diagnostics)

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [How to Read This Report](#how-to-read-this-report)
- [Part I — System Context](#part-i--system-context)
  - [1.1 Architecture in one page](#11-architecture-in-one-page)
  - [1.2 Why the failures were layered](#12-why-the-failures-were-layered)
- [Part II — Console & Protocol Incidents](#part-ii--console--protocol-incidents)
  - [C-1: Review of the team's ten field commits](#c-1-review-of-the-teams-ten-field-commits)
  - [C-2: The /pose guard that never guarded](#c-2-the-pose-guard-that-never-guarded)
  - [C-3: RESET MAP aimed at the wrong robot](#c-3-reset-map-aimed-at-the-wrong-robot)
  - [C-4: The MultiThreadedExecutor placebo](#c-4-the-multithreadedexecutor-placebo)
  - [C-5: Keyboard teleop swallowed by a combo box](#c-5-keyboard-teleop-swallowed-by-a-combo-box)
  - [C-6: Two long-standing console warnings](#c-6-two-long-standing-console-warnings)
  - [C-7: Fire alarm sensitivity and the honest threshold](#c-7-fire-alarm-sensitivity-and-the-honest-threshold)
- [Part III — Robot 1 (Alpha) Incidents](#part-iii--robot-1-alpha-incidents)
  - [A-1: First contact — state survey and repo rescue](#a-1-first-contact--state-survey-and-repo-rescue)
  - [A-2: LiDAR dead until reboot — the unsupervised driver](#a-2-lidar-dead-until-reboot--the-unsupervised-driver)
  - [A-3: The watchdog that killed a healthy LiDAR](#a-3-the-watchdog-that-killed-a-healthy-lidar)
  - [A-4: "Map frozen, robot won't drive" — one focus bug](#a-4-map-frozen-robot-wont-drive--one-focus-bug)
  - [A-5: Map quality — research-driven upgrades](#a-5-map-quality--research-driven-upgrades)
  - [A-6: rf2o laser odometry from source](#a-6-rf2o-laser-odometry-from-source)
  - [A-7: The backwards arrow — a 180° lidar](#a-7-the-backwards-arrow--a-180-lidar)
  - [A-8: Navigation that never existed](#a-8-navigation-that-never-existed)
  - [A-9: The goto gauntlet — five field iterations](#a-9-the-goto-gauntlet--five-field-iterations)
  - [A-10: RESET MAP used in anger — and it worked](#a-10-reset-map-used-in-anger--and-it-worked)
- [Part IV — Robot 2 (Beta) Incidents](#part-iv--robot-2-beta-incidents)
  - [B-1: First contact — undervoltage and a stale repo](#b-1-first-contact--undervoltage-and-a-stale-repo)
  - [B-2: The infinite boot-banner drain](#b-2-the-infinite-boot-banner-drain)
  - [B-3: Odometry blind to a dead IMU](#b-3-odometry-blind-to-a-dead-imu)
  - [B-4: First full test — camera, motion, a real detection](#b-4-first-full-test--camera-motion-a-real-detection)
  - [B-5: Turning that "made the motors suffer"](#b-5-turning-that-made-the-motors-suffer)
  - [B-6: The IMU that was never dead](#b-6-the-imu-that-was-never-dead)
  - [B-7: The brownout crash-loop and the gate that held](#b-7-the-brownout-crash-loop-and-the-gate-that-held)
  - [B-8: Capacitors, cables, and the boot-inrush blip](#b-8-capacitors-cables-and-the-boot-inrush-blip)
  - [B-9: The encoder spec hidden in a research doc](#b-9-the-encoder-spec-hidden-in-a-research-doc)
  - [B-10: Motors dead — the ENA/ENB wires](#b-10-motors-dead--the-enaenb-wires)
  - [B-11: The default speed that could not move](#b-11-the-default-speed-that-could-not-move)
  - [B-12: 4.83 volts — the delivery-path discovery](#b-12-483-volts--the-delivery-path-discovery)
  - [B-13: The silent shared-memory corruption](#b-13-the-silent-shared-memory-corruption)
- [Part V — Cross-Cutting Lessons](#part-v--cross-cutting-lessons)
- [Part VI — Final System State & Verification Matrix](#part-vi--final-system-state--verification-matrix)
- [Part VII — Outstanding Items & Demo-Day Recommendations](#part-vii--outstanding-items--demo-day-recommendations)
- [Appendix A — Complete Commit Log](#appendix-a--complete-commit-log)
- [Appendix B — Diagnostic Cookbook](#appendix-b--diagnostic-cookbook)
- [Appendix C — Calibration Constants](#appendix-c--calibration-constants)
- [Appendix D — Power Delivery Reference (Pi 3B+)](#appendix-d--power-delivery-reference-pi-3b)

---

## Executive Summary

Over roughly twenty-four hours of live testing on real hardware, the team and
the assistant found and fixed **twenty-six distinct defects** spanning every
layer of the system: chassis wiring, power delivery, firmware-adjacent serial
handling, ROS transport internals, navigation logic, UI event routing, and
calibration constants.

The headline outcomes:

- **Robot 1 (Alpha)** went from "LiDAR randomly dead, map frozen, cannot be
  driven, navigation does not exist" to a robot that **navigated to five
  clicked goals in live testing**, with arc-turns and guarded reversing in
  corridors narrower than its own pivot circle, laser odometry feeding SLAM,
  and a one-click SLAM reset proven under fire.
- **Robot 2 (Beta)** went from "browns out, reboots itself, stalls on every
  turn, map marker frozen" to a robot that **drives smoothly, pivots with
  correct encoder kinematics, streams 13 FPS AI-annotated video, and tracks
  its motion on the map** — confirmed by the operator in the final test.
- **The console** gained footprint-true robot rendering, RViz-grade occupancy
  shading, smooth pose animation, a SLAM reset button, per-robot footprint
  planning, and lost three separate input-routing bugs.

Two findings deserve special mention because they will save future debugging
days:

1. **The 0.4–0.5 V delivery drop** between a buck converter's terminals and
   the Pi's chip (cable + connector + polyfuse). Battery charge level kept
   *moving* this symptom around, which made it masquerade as "needs charging"
   for most of a day. The correct procedure — measure at the Pi's GPIO pins
   under load, adjust the buck until *that* reading is 5.1 V — ended it.
2. **Stale FastDDS shared-memory segments** left in `/dev/shm` by brownout
   crash-loops. Discovery still matches (every tool says "connected"), but
   message delivery silently dies. The robot ACKed 695 operator commands and
   executed none of them. Both robots now purge stale segments on every
   service start.

Every fix in this report is committed, pushed, and deployed; every claim of
"verified" was demonstrated on the physical robots, not in simulation.

---

## How to Read This Report

Each incident chapter follows the same shape:

| Section | Content |
|---|---|
| **Symptom** | What the operator saw, as reported |
| **Investigation** | The steps and evidence that narrowed it down |
| **Root cause** | The precise mechanism, stated plainly |
| **Fix** | What changed, with the commit hash |
| **Verification** | How we proved it fixed |
| **Lesson** | What this teaches about the system or the method |

Incidents are grouped by subsystem, ordered roughly chronologically inside
each group. Cross-references use chapter IDs (e.g., "see B-12").

---

## Part I — System Context

### 1.1 Architecture in one page

Three robots, one operator console, no shared middleware over the air:

```
ROBOT 1 · Pi 4                ROBOT 2 · Pi 3B+              ROBOT 3 · ESP32
RPLidar → slam_toolbox        camera_pub (own systemd       MQ-5 + buzzer
rf2o odom · bridge ·          unit) · bridge · odom ·       HTTP API · OTA
goto · explorer · gateway     goto · gateway                command watchdog
ROS 2 island (domain 11,      ROS 2 island (domain 12,
localhost-only DDS)           localhost-only DDS)
     │ ZMQ 5556-5560               │ ZMQ 5555-5560               │ HTTP
     └───────────────┬─────────────┴──────────────┬─────────────┘
                     ▼                            ▼
           versioned msgpack protocol      (docs/protocol.md)
           telemetry · map · video · health · ACKed commands
                     │
                     ▼
           GP OPERATIONS CENTER (Windows laptop, PySide6)
           map+A* planner · YOLO child process · alerts · diagnostics
```

Key properties that mattered during debugging:

- **Each Pi is a sealed ROS island** (`ROS_LOCALHOST_ONLY=1`, distinct
  domains). Robots cannot hear each other's DDS traffic; the per-robot ZMQ
  *gateway* is the only network doorway. This meant every cross-machine
  symptom could be localized to the explicit protocol channels.
- **The camera is its own systemd unit**, independent of the ROS stack. This
  is why a "half-alive" robot (video working, control dead) was possible —
  and twice misleading (B-7, B-13).
- **Four-layer drive safety**: console 10 Hz stream → gateway deadman
  (0.6 s) → bridge deadman (0.8 s) → firmware watchdog (1 s). These fired
  correctly all day and never had to be debugged themselves.

### 1.2 Why the failures were layered

A recurring pattern: **each fix exposed the next fault**. Robot 2's day is
the canonical example — six independent defects stood between the operator
and a moving robot, and any five of them being fixed still produced the same
visible symptom ("it doesn't move"). The only way through was instrumented
elimination: prove each layer healthy with direct evidence before moving to
the next. The Diagnostic Cookbook (Appendix B) captures the exact probes
that did this, because they will be needed again.

---

## Part II — Console & Protocol Incidents

### C-1: Review of the team's ten field commits

**Symptom.** The session opened with: "we encountered several issues, some
already resolved — review the recent commits and take over."

**Investigation.** The team had pushed ten commits from real-robot testing
(`710f4ba`…`4966a4e`): ZMQ context isolation, a 50 Hz poll restoration, a
global key event filter, gateway pose fallbacks from `/pose` and TF, and a
RESET MAP button. The robot itself carried uncommitted working-tree changes.
Each commit was read in full diff form and audited.

**Findings.** Four genuine bugs (C-2 through C-5 below) plus several gaps:
the simulator did not implement the new `cmd.reset_map`; the command was not
in the exactly-once dedupe set; duplicate inline imports; protocol docs not
updated. The good news: the team's *intent* in every commit was correct, and
two of their fixes (dedicated ZMQ contexts; non-blocking poll restoration)
were sound as written.

**Fixes.** All in `fb9b33d`, plus preservation of the robot's unpushed
working-tree fixes in `c42700b` (the `set +u` wrap around ROS sourcing in
preflight — without which the *pushed* preflight failed — and executable
bits on all five shell scripts).

**Lesson.** Field fixes written at 2 AM on a robot deserve a code review
with the same care as any PR — and the robot's *working tree* can contain
load-bearing fixes that never made it into a commit. Always diff the robot
before syncing it.

### C-2: The /pose guard that never guarded

**Symptom.** Latent — found by review, would have surfaced as robot2's
odometry being silently overwritten by SLAM poses.

**Investigation.** The new `_pose_cb` in the gateway read:

```python
# Don't overwrite if actual odom is flowing (with velocities)
if self.state.get('odom') and ... and self.state['odom']['v'] != 0.0:
     pass # keep true odom
self.state['odom'] = {...}      # ← runs unconditionally
```

The guard's body was `pass`, then control fell through to the overwrite.

**Root cause.** A `pass` where a `return` was intended. On any robot with
real wheel odometry, every `/pose` message would stomp the live estimate.

**Fix** (`fb9b33d`). `return` on the guard path; type annotations and
duplicate `import math` cleanup; the module-level import moved above use.

**Verification.** Code-level (the path is robot1-only in practice today);
the later A-6 work replaced this logic with the map→base_link merge, which
was verified live.

**Lesson.** `pass` and `return` look identical in a 2 AM diff. Comments
that *say* what the code should do ("keep true odom") are gold for
reviewers — the comment is what exposed the bug.

### C-3: RESET MAP aimed at the wrong robot

**Symptom.** Latent — found by review. RESET MAP on the console while
controlling robot2 would have restarted a service that doesn't exist on
robot2's Pi, with no error and no map reset.

**Investigation.** Two halves: the gateway handler ran a hardcoded
`sudo systemctl restart gp-robot1.service` regardless of which robot it ran
on; the console sent `cmd.reset_map` to the *active* robot, but SLAM only
runs on the mapper.

**Root cause.** Identity confusion — "the map robot" was assumed to be both
"this robot" (gateway) and "the selected robot" (console), and both
assumptions break the moment the operator controls Beta.

**Fix** (`fb9b33d`). The gateway restarts its *own* `gp-<robot_id>.service`
derived from config. The console tracks which robot actually publishes the
map (`_map_source_id`, set on every map message) and routes the reset there
regardless of selection. A confirmation dialog guards the one-click stack
restart, `cmd.reset_map` joined the exactly-once dedupe set (a retry must
not restart the stack twice), the simulator implements it (map blanks ~3 s
then rebuilds), and the protocol doc documents the sudoers requirement.

**Verification.** End-to-end protocol test against the simulator: ACK →
duplicate retry deduped → map blank → map rebuilt. Later verified on real
hardware by the operator (A-10).

**Lesson.** Any command that names a service, host, or robot ID in a string
literal is a bug waiting for the fleet to grow. Derive identity from config.

### C-4: The MultiThreadedExecutor placebo

**Symptom.** Latent — the team's commit message said "prevent ZMQ ACK
starvation on Pi 3B+", but the starvation could still occur.

**Investigation.** `MultiThreadedExecutor(num_threads=4)` was added, but
every callback still shared the node's default **mutually exclusive**
callback group. In rclpy, that group serializes all of its callbacks no
matter how many executor threads exist — four threads, zero parallelism.
A slow `/map` compression callback would still block the 50 Hz command
poll, which is exactly the ACK starvation being fought.

**Root cause.** The executor controls *capacity*; callback groups control
*permission to run concurrently*. Adding threads without splitting groups
changes nothing.

**Fix** (`fb9b33d`). The command-poll timer moved into its own
`MutuallyExclusiveCallbackGroup`, giving it a private lane. Because that
makes publishes genuinely concurrent across threads — and ZMQ sockets are
not thread-safe — `GatewayServer.publish` gained a lock serializing the
sequence counters and socket sends.

**Verification.** Unit suite (the gateway server is fully testable over
inproc transports) plus a day of live operation with zero ACK timeouts
under map load.

**Lesson.** In rclpy, "multi-threaded executor" is necessary but not
sufficient; audit the callback groups. And the moment two executor threads
can run your code, every shared socket needs a lock.

### C-5: Keyboard teleop swallowed by a combo box

**Symptom (real, reported).** "Robot not move from WASD or arrows, why?"

**Investigation.** The team's global event filter intercepted drive keys
app-wide — correct idea. The review hardened it to pass keys through to
text-entry widgets so typing couldn't drive the robot. The exemption list
included `QComboBox` wholesale. The model-selector combo in the command bar
turned out to be **the only focusable widget in the toolbar** — so it held
keyboard focus from application startup, and every drive key was passed
into it. Arrows silently changed the YOLO model. Confirmed by code reading:
every other control had `setFocusPolicy(Qt.NoFocus)`; the combo did not.

**Root cause.** Two stacked errors: a combo box that could take focus in a
console where nothing else can, and a filter exemption treating a plain
(non-editable) combo as a text-entry widget.

**Fix** (`1b47545`). Both combos (model selector, diagnostics robot picker)
became `NoFocus` like every other control; the filter exemption narrowed to
true text inputs only (`QLineEdit`, spin boxes, *editable* combos,
non-read-only text edits). Escape (E-STOP) is intercepted unconditionally —
the panic key works even while typing.

**Verification.** Live: scripted key presses produced visible
`cmd.drive` traffic (including honest `FAILED: no ACK` entries when aimed
at an offline robot — proving the path), then real driving with map trail.

**Lesson.** "It feels like the robot ignores the keyboard" is almost always
focus routing, not transport. An operator console should have exactly one
keyboard owner; everything else `NoFocus`.

### C-6: Two long-standing console warnings

**Symptom.** Console stderr emitted `Could not parse stylesheet of object
RobotCard` repeatedly, and `QMainWindow::saveState(): 'objectName' not set
for QToolBar 'Command'` on exit.

**Investigation & root causes.**
1. The RobotCard stylesheet was built from an f-string *concatenated with a
   plain string that still used f-string brace escaping* — `'…}} QLabel…'`
   in a non-f-string stays a literal `}}`, producing an unparseable
   stylesheet. The cards had silently never been styled.
2. The command toolbar had no `objectName`, so layout persistence skipped
   it.

**Fixes** (`fb9b33d`). Single `}` in the concatenated literal (both call
sites); `setObjectName('commandBar')`.

**Verification.** Clean console output on the next sim run; toolbar state
persists.

**Lesson.** Treat Qt's parse warnings as failures: a stylesheet that fails
to parse applies *nothing*, and the visual difference can go unnoticed for
weeks.

### C-7: Fire alarm sensitivity and the honest threshold

**Symptom (reported).** "Fire detection is too sensitive, triggering false
positives on everything — only alarm above 80% confidence." Night-room
testing produced alerts at 26–48% on people and lights.

**Investigation.** The deployed model (`fire.pt`) was previously
benchmarked at **28–37% confidence on real fire photos**. The night's false
positives sat at 26–48% — the two distributions overlap almost completely.
No threshold can separate them.

**Decision & fix** (`cd0e173`). The gate was raised to 0.80 as requested,
with the trade-off documented in config: at 0.80 the audible alarm is
effectively drill-only (F9) with this model; the detections table still
lists everything the model sees. The *real* fix is recorded as a future
action: fine-tune a model on the team's own footage so real fire scores
separate from look-alikes.

**Operational note.** One follow-up confusion was self-inflicted physics:
alerts kept firing below 80% because the *running* console predated the
config change — `fleet.yaml` is read at startup. A console restart applied
it. Worth remembering: config edits require relaunching the console.

**Lesson.** A threshold is not a classifier. When signal and noise overlap,
say so and put the number where the next engineer will read it.

---

## Part III — Robot 1 (Alpha) Incidents

### A-1: First contact — state survey and repo rescue

**Symptom.** "Robot 1 is live on ssh, access it, check state and pull."

**Investigation.** Key-based SSH installed (bootstrapped over password
auth). Survey found: Pi 4 on Ubuntu 22.04, clean power (`0x0` throttle
bits), services healthy, udev symlinks correct (`/dev/rplidar`,
`/dev/mega`), passwordless sudo (needed by RESET MAP), ROS Humble present.
Two git findings: the robot was **7 commits behind** origin, and its
working tree carried **uncommitted changes** to four files.

**The uncommitted changes mattered.** Diffing showed most matched what the
team had since pushed — but `preflight.sh` carried an *unpushed, essential*
fix: ROS's `setup.bash` references unbound variables, so sourcing it under
the script's `set -u` makes preflight report "cannot source ROS 2" and
block the stack. The robot-side wrap in `set +u`/`set -u` was the only
reason preflight passed. Also unpushed: executable bits on the shell
scripts.

**Fix** (`c42700b`). Both fixes landed properly in the repo (applied to
robot2's preflight too, which still hardcoded `/home/pi`); all five shell
scripts got their executable bit stored in git. Only then was the robot's
tree stashed and fast-forwarded.

**Verification.** Robot at origin head, clean tree, services restarted and
healthy.

**Lesson.** Never `git checkout .` on a robot. The working tree is part of
the crime scene — and sometimes part of the cure.

### A-2: LiDAR dead until reboot — the unsupervised driver

**Symptom.** Health stream showed `scan` age at **394 seconds and
climbing** while everything else was green. The journal had one line:
`rplidar_node … process has died [exit code -6]` shortly after boot — and
nothing after it.

**Investigation.** The launch file pulled the driver in via
`IncludeLaunchDescription(rplidar_a1_launch.py)` — the vendor's launch
file, whose internal node has **no respawn**. Our `respawn=True` only ever
applied to the `_py()` processes we start ourselves. One abort at boot
(serial port not yet settled → RCLError → SIGABRT) and the driver was gone
for the session. Worse, the scan watchdog's last-resort recovery is
`pkill` the driver, *relying on launch respawn that did not exist* — its
own escalation assumed supervision that wasn't there.

**Root cause.** Supervision didn't compose through `IncludeLaunchDescription`.

**Fix** (`16c941d`). The driver is now a directly-declared `Node` with
`respawn=True, respawn_delay=3.0` and the A1 parameters inlined
(`Sensitivity` mode, 115200 baud, frame `laser`). The same hole was closed
in `slam_only.py`: `slam_toolbox` and both static TF publishers now respawn
(a SLAM crash restarts mapping instead of silently ending it).

**Verification.** Post-deploy boot: driver up, S/N read, health OK,
scanning at 10 Hz — and later that night the respawn was *observed working*
when the watchdog (next chapter) killed the driver: `process started with
pid [4459]` appeared three seconds later.

**Lesson.** `respawn=True` is a property of the node *declaration*, not of
the launch session. Audit every `IncludeLaunchDescription` for what it
actually supervises — and never build a recovery ladder whose bottom rung
assumes a mechanism you haven't verified exists.

### A-3: The watchdog that killed a healthy LiDAR

**Symptom.** After fixing A-2, the LiDAR *still* died — now repeatedly.
Journal: driver starts, scans at 10 Hz… then `Stop`, then
`scan_watchdog: motor cycle did not help — restarting driver` every six
seconds, forever.

**Investigation.** The timeline reconstructed from timestamps:

1. Driver starts scanning at t+0.
2. Watchdog node arms at t+0.3 — its scan-rate window is empty and DDS is
   still discovering the `/scan` publisher.
3. At t+1.1 (its **first** check; `_last_action` initialized to `0.0`, so
   no grace applied) it measures "0.0 Hz" and **stops the healthy motor**.
4. Inside the motor kick it calls `time.sleep(1.0)` twice — blocking its
   own executor, stalling its own `/scan` subscription, guaranteeing the
   next measurement also reads low.
5. At t+7 it escalates to `pkill`. The driver takes ~5 s from respawn to
   scanning; the watchdog re-kills every 6 s. **A permanent kill-loop.**
   Before A-2 (no respawn), the very first kill was simply final.

**Root cause.** Three compounding flaws: no startup grace (DDS discovery
latency reads as silence), executor-blocking sleeps corrupting its own
measurements, and an escalation cadence faster than the recovery it
depends on.

**Fix** (`fd9a19a`). 20 s startup grace before any action; a separate 20 s
post-kill grace so a respawned driver can reach scanning; the motor kick
rebuilt around a one-shot timer instead of sleeping in the callback; stall
grace raised 5→8 s.

**Verification.** Live, definitive: after deploy, a 70-second continuous
watch showed scan age holding at 0.02–0.64 s, zero watchdog actions in the
journal (the previous session's kill-loop had stamped 38 of them), and the
map updating every second.

**Lesson.** A watchdog must be *more* patient than the thing it guards is
slow. Measure your recovery path's worst-case latency first, then set the
escalation clock; and never `sleep()` inside the callback that feeds your
own sensor of health.

### A-4: "Map frozen, robot won't drive" — one focus bug

**Symptom (reported).** "The map looks terrible… completely stuck on the
initial frame. When the robot moves, there are no new updates… Also robot
not move from WASD or arrows, why?"

**Investigation.** These turned out to be **one bug with two faces**. The
WASD failure was C-5 (combo-box focus). And SLAM only integrates scans when
the robot *moves* — a robot that can't be driven produces a map that never
changes, while the 1 Hz map messages keep flowing with identical content.
Health data proved messages were arriving on time; their *content* was
static because the robot was static.

**Root cause.** The focus regression (C-5). The "frozen map" was correct
behavior given an undriveable robot.

**Fix.** C-5's fix; no map-pipeline change was needed for this symptom.

**Verification.** With keys restored, the operator drove and the map grew;
the scan overlay's apparent misalignment also vanished once the pose
updated continuously.

**Lesson.** When two symptoms appear together, look for the single upstream
cause before fixing them separately. Here, "renderer is bad" would have
been a week of wasted work — the renderer was fine.

### A-5: Map quality — research-driven upgrades

**Symptom (reported).** "The generated map is extremely poor… I need
mapping on par with — if not superior to — what RViz produces. Implement
the latest, state-of-the-art mapping." The user also supplied two research
reports on A1M8 map quality.

**Investigation.** The reports were read in full and triaged against our
stack. Several recommendations were already satisfied (we stream the raw
occupancy grid and render client-side — RViz's exact data path — so no
PGM-export degradation applies). Three were actionable: laser odometry
(rf2o — see A-6), finer resolution *given* good odometry, and registration
thresholds.

Independent findings from our own session: `minimum_travel_heading: 0.0`
made *every* stationary scan pass slam_toolbox's has-moved test, so
identical scans were re-registered ~3×/s — CPU churn and speckle noise in
free space. And the console rendered occupancy as a binary threshold,
discarding the probability information RViz displays.

**Fixes** (`1b47545`, `d096025`).
- slam: `minimum_travel_distance 0.05→0.10`, `minimum_travel_heading
  0.0→0.17` (nodes register on real motion only); resolution `0.05→0.025`
  after rf2o landed (the A1M8's <1% ranging accuracy supports it).
- Console: 256-entry indexed palette rendering occupancy 0–100 as a
  continuous free→occupied confidence gradient, unknown distinct; scan
  overlay refined (smaller, translucent points); planning-only despeckle
  (A-9) so noise cells can't block routes.
- Gateway: the robot's reported pose is now always the drift-corrected
  `map→base_link` transform when one exists, with `/odom` velocities
  merged in — the dashboard never sees an uncorrected frame.

**Verification.** Side-by-side screenshots before/after: from a blocky
starburst with detached scan points to solid rooms with walls the scan
overlay hugs. The user's verdict after the final session: "map work…
nice work."

**Lesson.** "Make it like RViz" decomposed into: same data path (already
true), same shading (one palette), and *better input data* (odometry).
Renderer polish without odometry would have polished noise.

### A-6: rf2o laser odometry from source

**Symptom.** slam_toolbox ran on pure scan matching with a static
`odom→base_link` identity TF — the research reports' primary diagnosis for
smeared A1M8 maps, and the cause of robot1's pose only updating at
registration instants (visible as scan-overlay lag).

**Investigation.** No Humble binary exists for `rf2o_laser_odometry`; the
robot already had a colcon workspace.

**Fix** (`0f07a3a`). Cloned MAPIRlab/rf2o (ros2 branch) into `~/ros2_ws`,
built (2 m 18 s on the Pi 4), wired into the launch as a supervised node
publishing `/odom` + the `odom→base_link` TF at 10 Hz; **removed the static
identity TF it replaces** (publishing both would fight); the systemd unit
sources the workspace overlay when present; the unit installer now derives
the service user from the repo owner instead of hardcoding `pi`.

**Verification.** `/odom` at 7.3 Hz (scan-rate-bound, healthy), full
`map→odom→base_link` chain resolving, single rf2o process, CPU headroom
fine (load 1.2/4 cores) — and the qualitative map transformation in A-5.

**Lesson.** When the right dependency has no binary, budget the source
build — it was under three minutes of compile for the single biggest map
quality lever of the day.

### A-7: The backwards arrow — a 180° lidar

**Symptom (reported).** "The robot's directional arrow points backward
while the physical robot faces forward… also the rotation animation is
jerky."

**Investigation.** With everything derived from the lidar, "forward" is
whatever direction the lidar's 0° axis points — and on this chassis the A1
was mounted with its 0° axis facing the **rear**. The identity
`base_link→laser` TF propagated that backwards convention into every pose.

**Fixes** (`5e2e789`).
- `base_link→laser` static TF now carries yaw = π (the research report's
  prescribed fix for exactly this).
- The gateway adds the configured laser yaw to scan angles so the console's
  scan overlay stays base-frame correct (otherwise the fix would have
  flipped the overlay instead).
- Jerkiness: poses arrive in ~7 Hz steps; the *drawn* pose now
  exponentially chases the true pose (angle-wrap aware, snap on teleports
  like SET POSE so there's no fake gliding). Planning reads the raw pose —
  zero added control latency.

**Verification.** TF echo on the robot shows RPY yaw 3.142; subsequent
driving showed arrow, motion direction, and scan overlay all agreeing.

**Lesson.** Sensor mounting conventions are config, not code — and any fix
to a frame must be chased through *every* consumer of that frame (the scan
overlay would have silently broken).

### A-8: Navigation that never existed

**Symptom (reported).** "When I send a Nav-to-Goal command, the robot
remains completely stationary."

**Investigation.** `ros2 topic info /goal_pose` on robot1: **zero
subscribers**. Click-to-navigate had been designed to execute on robot2
(the README even said so); robot1, the only robot present, had no
point-to-point controller at all. The console dutifully planned A* routes
and streamed waypoints into the void.

**Fix** (`5e2e789`). New `navigation/robot1_goto.py`, designed for a
mapper: pose from the drift-corrected `map→base_link` TF (the same frame
map clicks arrive in — no offset arithmetic), rotate-then-drive control,
and a scan-based collision guard sized from the measured footprint
(40×30 cm chassis, lidar center 10 cm behind the front edge — supplied by
the team). Cancels on manual override, e-stop, or explorer enable.
Footprint constants went to `config/robot1.yaml`; the console's A*
inflation became per-robot (hard = half-width + 5 cm; soft cost extended
to the circumscribed radius so the 30 cm tail is priced away from walls
without hard-blocking doorways); the map draws the true-scale chassis
rectangle with the lidar dot at its real offset.

**Verification.** See A-9 — after the guard iterations, five live goal
arrivals.

**Lesson.** "Robot doesn't navigate" sometimes means "navigation was never
wired for this robot." Check topic subscriber counts before debugging
controllers that don't exist.

### A-9: The goto gauntlet — five field iterations

This chapter documents the most instructive sequence of the project: five
rapid iterations over one evening, each driven by live diagnostic data, to
make A-8's controller survive a real cluttered room. The breakthrough tool
was added in iteration 3: **the BLOCKED log line now prints the exact
body-frame coordinates of the nearest obstacle**, converting every failure
from a mystery into a measurement.

**Iteration 1 — the robot saw itself** (`fc7acc9`).
*Symptom:* every goal aborted `BLOCKED:ROTATE` instantly.
*Evidence:* a scan probe showed persistent returns at 0.15–0.30 m… behind
the lidar. The lidar sits at the *front* of a 40 cm body: it sees its own
rear deck, posts and cables — all inside the 0.38 m rotation-clearance
circle. *Fix:* returns inside the body envelope are excluded from the
guard.

**Iteration 2 — noise became walls** (`9715bf3`).
*Symptom:* `NO PATH` reported in visibly open rooms.
*Evidence:* at the new 0.025 m resolution, a single noise cell inflates
into an 8-cell-radius blob; speckle from the earlier no-odometry sessions
turned free space into an archipelago of fake obstacles.
*Fix:* planning-only despeckle — isolated occupied cells with zero occupied
neighbors are dropped before inflation (any real object spans several
cells at 2.5 cm); SLAM data and display untouched.

**Iteration 3 — the naive circle** (`4851f1a`).
*Symptom:* still `BLOCKED:ROTATE` almost everywhere indoors.
*Evidence (new diagnostics):* `nearest x=-0.01 y=-0.28` — a real wall
28 cm to the side. The guard treated the rotation sweep as a full 0.38 m
circle, but the *front* corners only reach 0.18 m — a wall ahead can never
be struck by turning. Indoors, something is nearly always within 0.38 m of
*some* bearing, so the naive circle vetoed almost all rotation.
*Fix:* geometry-true check — block only on returns grazing the body side
(< 0.21 m anywhere) or in the rear half-plane within 0.36 m (where the
0.335 m rear-corner sweep actually goes). Every BLOCKED line now carries
the nearest-point coordinates.

**Iteration 4 — driving like a driver** (`b4e9460`).
*Symptom (reported):* "he didn't know how to return back to go to place
behind… he just can go if place only forward."
*Evidence:* the logs showed corridors with walls at 0.26–0.33 m on the
side — the guard was *correct* that pivoting would clip (rear corner
sweeps 0.335 m). The robot needed different maneuvers, not a braver guard.
*Fix:* goal to the side with pivot blocked but front clear → **arc turn**
(creep 0.06 m/s forward while turning; the tail tracks inside the front
path); goal behind with no room to turn → **guarded reverse** (the 360°
lidar watches a rear corridor sized for the 0.30 m tail; stop at 0.15 m
rear clearance). Pivot-in-place remains the choice when room exists.

**Iteration 5 — the shape-shifting fixture** (`5f3892d`, `424b292`,
`cb65351`).
*Symptom:* one blocker kept returning at `y≈+0.21–0.24` — but it moved
between boots, defeating the boot-time per-beam self-mask (one boot: 0
beams learned; next: 77; after a tight-corner boot: 376 — half the scan!).
*Evidence:* it tracked a constant *body-frame* position through every
pivot and translation → attached hardware (a cable or bracket on the left
flank, in the scan plane), but loose enough to shift across power cycles.
*Fixes:* (a) self-mask hardening — masked beams ignore returns only within
a ±6 cm *band* of the learned fixture distance (anything sliding closer
trips the guard again), and a mask claiming >25% of the scan refuses
itself (the robot booted against the environment, not seeing fixtures);
(b) a documented exclusion pocket for the measured fixture envelope;
(c) **probing rotation** as the general fallback: rotate at 0.15 rad/s
while watching the blocker — attached hardware turns with the robot
(distance constant → rotation completes); a real object closes in (3 cm
trend) → instant hard block.

**Outcome.** Five goals navigated and arrived during live testing, with
the guard's remaining refusals all verifiably correct (e.g., a real object
5 cm from the robot's nose). A standing hardware action: tuck the
left-flank cable out of the scan plane and shrink the pocket away.

**Lessons.**
- Diagnostics that print *coordinates* turn debugging from theory into
  measurement. Iteration velocity tripled after the nearest-point log.
- A safety guard that is geometrically honest will still make the robot
  useless if the *maneuver repertoire* is too small for the environment.
  Tight spaces need arc turns and reversing, not just permission checks.
- Self-sensing (a robot seeing its own body) is a class of problem:
  boot-learning, band-masking and probing rotation compose into a general
  solution, but the best fix is hardware — keep the scan plane clean.

### A-10: RESET MAP used in anger — and it worked

**Symptom.** None — this is the positive proof. During live testing the
operator clicked RESET MAP on the real robot.

**Evidence (console log).** `robot1 SLAM reset requested — map will
rebuild` → `robot1 command link DOWN` → `robot1 command link up` (~7 s) —
exactly the designed sequence (ACK before restart, stack bounce,
reconnect), followed by a fresh map at the new 0.025 m resolution.

**Lesson.** Features verified only in simulation are promises; this one
was kept on hardware within hours of being written, which is the right
cadence for an operator-facing control.

---

## Part IV — Robot 2 (Beta) Incidents

### B-1: First contact — undervoltage and a stale repo

**Symptom.** "Now I will run robot 2 to fix all errors on it."

**Investigation.** Key auth installed; survey found the Pi 3B+ **actively
under-voltage at first boot** (`get_throttled=0x50005` — the brown-out
robot living up to its reputation), 16 commits behind, with the same class
of local hand-fixes robot1 had (paths, `set -u`, exec bits — all already
upstream in proper form). Services ran; devices present; strong WiFi.

**Fixes.** Stash + sync to head; units reinstalled via the now
user-deriving installer. The undervoltage was flagged immediately as the
session's likely antagonist — which B-5 through B-12 confirmed repeatedly.

**Lesson.** Write the power reading down at first contact. Half of this
robot's day traces to that one hex value.

### B-2: The infinite boot-banner drain

**Symptom.** Robot2 published nothing: no `/encoders`, no `/imu/data_raw`,
no `/odom` — while services showed green and topics existed.

**Investigation.** The journal showed the bridge logging **every** firmware
telemetry line as `Arduino: D:…` — 8,933 lines in minutes — and never
printing "Bridge started". The bridge's `_connect_arduino` drains the boot
banner with `while self.arduino.in_waiting:` … but v5 firmware streams
telemetry at 50 Hz. With a new line arriving every 20 ms and each journald
write costing milliseconds, `in_waiting` never goes quiet: **the
constructor loops forever**, the serial reader thread never starts, and the
node looks alive while doing nothing.

**Root cause.** An unbounded drain loop written for chatty-then-quiet
firmware, run against continuously-streaming firmware.

**Fix** (`d625986`). The drain is time-bounded (3 s) and skips telemetry
lines; only the banner and INIT results are logged.

**Verification.** Bridge connects in 1.5 s; encoders/IMU/odom all publish;
end-to-end telemetry reached the laptop with real values. This bug is the
leading suspect for the project's historical "robot2 randomly doesn't
respond" mystery — it would strike any boot where the firmware won the
race to the serial port.

**Lesson.** `while in_waiting:` is a latent infinite loop whenever the
peer streams. Bound every drain by time, not by buffer emptiness.

### B-3: Odometry blind to a dead IMU

**Symptom.** Firmware reported `MPU6050 FAIL` at init (wiring — see B-6),
yet `/imu/data_raw` kept publishing fresh-looking messages.

**Investigation.** The bridge forwards the D-packet's IMU fields
unconditionally — a dead chip reads raw zeros, which arrive as perfectly
fresh all-zero messages. The odometry's complementary filter blended
70% gyro into heading; 70% of zero meant **every turn registered at 30% of
its true angle**. No staleness check can catch a chip that lies at 50 Hz.

**Root cause.** Sensor death indistinguishable from sensor silence at the
message level.

**Fix** (`353f403`). Physics as the detector: a live MPU has a noise floor
(raw values always jitter); only a dead chip reads *exactly* zero on all
six axes. After ~1 s of exact zeros the filter falls back to pure encoder
heading — loudly — and restores gyro blending automatically when real
values return.

**Verification.** The warning fired live on boot with the chip
disconnected, and the restore path fired the same day when the chip came
back (B-6) — both transitions observed in the journal.

**Lesson.** For sensors that can fail-to-zero, detect the *statistics* of
death, not the absence of messages.

### B-4: First full test — camera, motion, a real detection

**Symptom.** None — baseline capture. "Run dash to test robot 2 movement
and camera."

**Results.**
- Video: 13.3 FPS at 61 ms latency through the framed protocol, AI overlay
  live — including a genuine fire-model detection (39%) on something in the
  dark room, auto-cleared by the debounce. Whole detection pipeline
  exercised on real robot2 video.
- Motion: a scripted 3-press forward pulse drove ~35 cm; encoders counted
  on all four channels; odometry integrated.
- Observation logged for the team: open-loop driving arcs right (left
  encoders count ~1.6× right) — motor imbalance; goto self-corrects, manual
  driving veers.

**Lesson.** Capture a healthy baseline the moment one exists. Every later
"is it broken or was it always like this?" question got answered against
this snapshot.

### B-5: Turning that "made the motors suffer"

**Symptom (reported).** "Robot 2 is struggling severely with turning; the
rotation is highly inefficient, jerky, and the motors seem to suffer."

**Investigation.** Three defects in the bridge's Twist-to-serial mapping:

1. **PWM was only ever set from linear speed** — and only sent when
   `abs(linear) > 0.05`. A pure pivot ran on whatever PWM the last straight
   drive used; at low slider settings that meant four skid-steering wheels
   scrubbing sideways at PWM ~120 — stall-judder, groaning.
2. **No turn torque budget**: skid-steer pivots need *more* torque than
   driving, not leftovers.
3. **Forward/pivot flapping**: `abs(linear) > abs(angular)` arbitration
   flipped the command between `F` and full-pivot `L` whenever the goto
   controller steered while driving — the visible mid-drive jerk.

**Fixes** (`06c84dc`, `27af3b4`). Pivots get a configured torque floor
(`turn_pwm: 215`); PWM is computed per maneuver including turns (with
serial spam damping); steering must dominate 2× before a drive becomes a
pivot. Plus a **motor stall detector**: motion commanded with frozen
encoders for 1.5 s raises `MOTOR STALL: cmd=… PWM=…` into the console's
incident feed — the silently-grinding state became a named, visible event
(and earned its keep within hours: B-7, B-12).

Same commit family fixed the **kinematics** the user supplied specs for:
wheel diameter 65→85 mm (the old value under-read every distance by 24%),
track width estimated 0.225 m with a documented spin-calibration procedure,
chassis footprint (30×20 cm) added for the planner. One spec was
physically impossible as given ("axle height 2.0–2.5 cm" with an 85 mm
wheel whose axle is at 42.5 mm) — treated as chassis ground clearance and
documented as such.

On the user's direct question — *"is the system actually utilizing the IMU
for yaw?"* — the honest answer was recorded: **no, not while the GY-87 was
disconnected**; the fusion filter existed and would re-engage by itself
when the chip returned (it did — B-6). A full EKF was explicitly deferred:
with zero working IMU there is nothing to fuse, and the complementary
filter is the right tool at this scale.

**Verification.** Later sessions (post power fix) showed clean pivots with
correct per-side encoder signs and smooth heading sweep — see B-13's final
test.

**Lesson.** "The motors suffer" was four problems wearing one symptom:
control mapping, torque budget, arbitration, and (underneath everything)
power. Fixing the software layers first made the hardware signal legible.

### B-6: The IMU that was never dead

**Symptom (reported).** "How is the IMU completely dead? I just bought it
brand new!" — with the wiring: VCC→3.3 V pin, GND, SDA→20, SCL→21.

**Investigation.** The firmware's boot-time I2C scan gave the verdict
across multiple boots: some boots `found: (none)`, later boots
`found: 0x0D 0x68 0x77` with all three chips initializing OK. **The module
was intermittent, not dead** — the signature of marginal power or loose
jumpers, not silicon failure.

Wiring analysis: SDA/SCL pins correct. The weak point was **VCC on the
Mega's 3.3 V pin**: the GY-87 carries its own 3.3 V regulator and is
designed for 5 V input — feeding 3.3 V runs that regulator below dropout
(sensors see ~2.9 V), and the Mega's 3.3 V rail is limited to ~50 mA while
the module's three chips, LED and LDO overhead spike near it. Marginal
voltage + starved rail + motor noise = a bus that drops out by mood.

A second curiosity was decoded for the team: the magnetometer failing on
*cold* boots only. On the GY-87 the QMC5883L sits behind the MPU6050's
auxiliary bus, visible only when the MPU's bypass switch is enabled — a
switch that survives warm resets but clears on power cycles. Harmless
(nothing uses the compass), documented as a firmware init-order nuance.

**Fix.** Hardware advice: VCC to the 5 V pin (after confirming the onboard
`662K` regulator is present), solder the jumpers, route I2C away from
motor wires. Software was already resilient via B-3's fallback.

**Verification.** Post-rewire cold boot: `MPU6050: OK`, gyro bias
calibrated, live gyro noise floor visible in telemetry (±0.001 rad/s
jitter, gravity at 9.53 m/s²), fusion active — and B-3's restore message
confirming the handover.

**Lesson.** "Brand new" argues *for* a wiring/power diagnosis, not against
it. And an I2C scan at boot, printed to the log, is worth an hour of
multimeter guesswork — build it into every firmware.

### B-7: The brownout crash-loop and the gate that held

**Symptom (reported).** "Robot 2 appears normally, the camera is working,
and I can control it, but it doesn't move on the map. There's also an
extremely huge delay… honestly, it feels like it's not moving at all."

**Investigation.** Probe results in sequence: telemetry port silent → mDNS
gone → SSH refusing → ping perfect but ports 5556/5558 closed while video
5560 lived → SSH back, `uptime: 1 min`. The robot was **brown-out crashing
and rebooting under the operator**, and on each boot the preflight power
gate did its designed job:

```
[preflight] ❌ UNDERVOLTAGE NOW (get_throttled=0x50005) — fix power before driving
Dependency failed for GP Robot2 ROS stack
```

No gateway → no telemetry → frozen map and "stale" feel. The camera's
independent unit kept streaming, making the robot look deceptively
half-alive (the architecture's graceful degradation, read backwards).

**Root cause.** Exhausted/inadequate 5 V supply; the software refused to
pretend otherwise.

**Fix.** None needed in software — this chapter is the system *working*:
the gate that exists because this board has burned components before held
the line. The tmux fallback (`rasp_cmd/robot2.sh`) was documented as the
eyes-open escape hatch, with the SD-corruption warning attached.

**Lesson.** A protective gate will eventually be mistaken for a bug.
Logging its verdict in plain language ("fix power before driving") is what
turns that moment from an argument into a to-do.

### B-8: Capacitors, cables, and the boot-inrush blip

**Symptom.** After the team's hardware response — 1000 µF/25 V capacitors
at the buck output *and* at the Pi connector, the thin USB power lead
re-built with heavy-gauge wire — the rail read clean seconds after boot
(`0x50000`)… yet preflight still failed.

**Investigation.** Preflight runs as a boot dependency — *during* USB
enumeration and WiFi radio bring-up, the highest-draw instant of the boot.
It sampled `0x50005` in that window; seconds later the system read clean.
The gate was punishing a transient its own timing created.

**Fix** (`7b0fad5`). The power check samples up to 3× over 10 s and blocks
only if undervoltage *persists*. A genuinely sagging supply still blocks
exactly as before. Applied to both robots.

**Verification.** Next boot: `⚠ undervoltage flag (try 1/3) — settling…`
then `✅ power flags 0x50000`, `PREFLIGHT PASS`, full stack up.

**Lesson.** Any boot-time health check must distinguish inrush from steady
state. Sample twice with a gap before declaring hardware bad.

### B-9: The encoder spec hidden in a research doc

**Symptom.** None — a documentation find with calibration consequences.

**Investigation.** A research document the team dropped into the repo
(filed to `docs/design_notes/`) carried the official 25GA370 motor spec:
**12 PPR × 34:1 gearbox = 408 counts per wheel revolution** at 1×
decoding — exactly what the firmware's rising-edge-on-A ISR counts. The
config said 330. History reconstructed: the old `(65 mm, 330)` pair was an
empirical calibration whose two errors nearly cancelled; when B-5 fixed
the wheel to the measured 85 mm, the stale 330 alone began inflating every
distance by 24%.

**Fix** (`c99ce84`). `ticks_per_rev: 408`, with the derivation cited in
config. (Also evicted from the repo root: an unrelated DNS zone export
that had wandered in — moved out and gitignored.)

**Verification.** Distance plausibility on subsequent drives; a tape-
measure check is recommended as final confirmation (1.00 m commanded ≈
1.00 m reported).

**Lesson.** Empirical calibration pairs hide each other's errors. When one
constant is corrected from first principles, re-derive its partners from
first principles too — never leave half a calibration.

### B-10: Motors dead — the ENA/ENB wires

**Symptom (reported).** "No camera signal, no movements" → after console
restart fixed the stale connections: commands confirmed reaching the Mega
(`STS` echoed the applied PWM), e-stop clear — **encoders absolutely
frozen** during commanded drive. Earlier the same morning the identical
path had moved the robot.

**Investigation.** Between the two states: the robot had been opened on
the bench for the power rewiring. Commands reaching firmware + zero wheel
motion + zero encoder counts = motor *power stage* not energized. The
decision tree given to the team: L298N power LED off → 12 V feed; LED on
but silent → **the ENA/ENB enable wires from Mega pins 10/11** (boards
often shipped with jumper caps there; with caps gone and wires off, the
driver is disabled regardless of every other signal); then common ground;
then OUT terminals.

The team found and re-seated the ENA/ENB wires. To certify the repair —
and to split hardware from software with zero ambiguity — a **direct
serial test** was run on the Pi (stack stopped, `P255` + `F`/`L` straight
to `/dev/mega`, encoder deltas parsed from the raw D-stream):

```
FWD   : (492, 397, 325, 459)      ← all four forward
PIVOT : (39, -100, 602, 858)      ← left back, right forward: true pivot
```

**Root cause.** Enable wires displaced during bench work.

**Fix.** Hardware re-seat (team) + the direct-serial test added to the
diagnostic cookbook as the canonical hardware-vs-software splitter.

**Lesson.** After any bench session, the first test is a *full-power,
software-free* motor command. It costs thirty seconds and instantly
partitions the universe of causes in half.

### B-11: The default speed that could not move

**Symptom.** With hardware certified by B-10's test, console driving
*still* produced nothing at default settings — yet the morning session had
worked.

**Investigation.** The difference was one number. The bridge mapped speed
to PWM as `80 + factor×175`; the console's default speed slider (0.15 m/s
of a 0.5 max) lands at **PWM ≈ 132 — below the ~150 static-friction
threshold** of this chassis. The morning's success had run with the slider
high (PWM 215+) by happenstance; the restarted console reset the slider to
default, turning every polite drive command into an inaudible hum.

**Root cause.** The bottom 40% of the speed range commanded torques that
cannot move the robot — a silent no-op zone.

**Fix** (`77514e1` + `d5e594d` — the second commit applying the formula
the first one only declared, an honest miss caught within minutes). Drive
PWM now maps `min_pwm(150) → 255`, so every slider position produces real
motion; config documents the measured threshold.

**Verification.** Immediate live drive at default settings; the user's own
"robot move now."

**Lesson.** Map control ranges to the *useful* actuator range, not the
theoretical one. If the bottom of your slider does nothing, the slider is
lying to the operator.

### B-12: 4.83 volts — the delivery-path discovery

**Symptom (reported).** Link flapping (`command link DOWN/up` twice in
three minutes) plus `MOTOR STALL` returned — and then, decisively: **"it
charged… it's not related to charging, why is everything you tell me
charge?"** with the pack measured at 11.8 V.

**Investigation.** The user was right, and the proof came in three
measurements:

1. `get_throttled=0x50005` **at idle, with an 11.8 V pack** — under-voltage
   with a healthy source means the deficit is in *delivery*, not charge.
2. CPU clock pinned at **600 MHz** (vs 1400 normal) with load average 5.65
   — the throttled CPU couldn't keep the gateway's timing, explaining the
   link flaps; WiFi signal itself was excellent (−44 dBm).
3. The keystone: multimeter on the **Pi's GPIO 5 V pins under load: 4.83 V**
   while the buck terminals showed 5.22 V. The cable, USB connector and
   the Pi's polyfuse were eating ~0.4 V at the 1.5–2 A this Pi draws —
   parking the chip 0.2 V above the 4.63 V brownout trigger, where every
   WiFi burst dipped it under.

Battery charge had shifted this margin up and down all day, which is why
"charge it" kept *seeming* to be the answer: more input headroom let the
buck mask the path loss for a while. The symptom moved; the cause never did.

**Fix.** Procedure, not part: raise the buck while watching the *Pi-pin*
reading under load, stop at 5.10–5.15 V there (buck terminals legitimately
read ~5.5 — the difference is consumed by the path; the 5.25 V ceiling
applies at the Pi, not at the buck). The user landed at buck 5.52 → pins
5.05.

**Verification.** Flags went even (`0xd0008`, then `0x80000` after the
restart — no live undervoltage), CPU stepped 600 → 1200 → 1400 MHz as the
board also cooled (69 °C had engaged the soft thermal cap; a heatsink is
recommended before demo day).

**Lesson — the most transferable of the report.** *Measure voltage at the
load, under load.* A supply's terminal voltage is marketing; the chip's
pin voltage is truth. And when an operator says "it's not what you keep
saying it is" — instrument their claim immediately; they were right.

### B-13: The silent shared-memory corruption

**Symptom (reported).** With power finally healthy and a fresh stack:
"why not move?" — again. But this time every layer had an alibi.

**Investigation.** The elimination run, in order:

1. Robot-side state: bridge connected, e-stop clear, **no stall warnings**
   — meaning no drive command had even *reached* the bridge.
2. Gateway health counters: **`cmds: 695, acks: 695, rejected: 0`** — the
   operator's commands were arriving at the robot and being acknowledged.
3. Direct-serial motor test: hardware perfect (it had just been fixed).
4. A `/set_speed` poke published directly on the robot: the bridge's STS
   echo did **not** change — its ROS subscriptions were deaf while its
   serial thread streamed happily.
5. `py-spy dump` on the live bridge: MainThread **idle** in
   `wait_for_ready_callbacks` — not stuck, *waiting for messages that never
   came* — while the topic graph showed publisher and subscribers matched.

Discovery matched; delivery dead. That is the fingerprint of **stale
FastDDS shared-memory transport**: with `ROS_LOCALHOST_ONLY=1`, messages
travel through `/dev/shm` segments, and the day's brownout crash-loops had
left five stale segments whose locks/state silently swallowed every
message while UDP discovery kept reporting healthy matches.

**Root cause.** Crash-orphaned SHM segments poisoning the localhost DDS
transport — the gateway honestly ACKed 695 commands and delivered none.

**Fix** (`e18d699`). Immediate: stop stack, `rm /dev/shm/fastrtps_*`,
start — delivery restored instantly (`/set_speed` poke → `STS:237` on the
next sample). Permanent: both robots' systemd units purge stale segments
in `ExecStartPre`, the one moment nothing can legitimately own them.

**Verification.** Final end-to-end test: console keys → encoders swinging
(`[888, 86, −247, −1059]`), odometry integrating, the operator driving and
— their words — "robot move now and map work and move in map."

**Lesson.** When discovery says yes and data says no, suspect the
transport's *shared state on disk*, not the code. Any system that can
crash hard must clean its IPC litter on the way back up — make the purge
part of the service, not part of tribal knowledge.

---

## Part V — Cross-Cutting Lessons

1. **Layered failures are the norm, not the exception.** Robot 2 needed
   six independent fixes (power delivery, boot gate, enable wires, PWM
   floor, kinematics, SHM transport) before "press W, robot moves" was
   true end-to-end. Any debugging method that stops at the first plausible
   cause would have failed five times. The discipline that worked: prove
   each layer with its own instrument, then move exactly one layer.

2. **Instrument first, theorize second.** The decisive moments were all
   measurements, not insights: the scan probe that revealed self-hits, the
   nearest-blocker coordinates in BLOCKED logs, the gateway's command
   counters, the py-spy stack dump, the multimeter on GPIO pins under
   load. Every one of these took minutes to build and ended hours of
   speculation.

3. **Make the system tell on itself.** The best fixes of the period were
   diagnostics: the MOTOR STALL announcer, the BLOCKED-with-coordinates
   log, the boot I2C scan, preflight's plain-language verdicts, the
   IMU-dead warning. Each converted a future silent failure into a named
   event in the operator's incident feed.

4. **Protective gates need grace periods.** Twice, a correct safety
   mechanism (the scan watchdog, the preflight power gate) attacked a
   healthy system because it sampled during a transient its own timing
   guaranteed. The pattern fix is the same: a startup grace longer than
   the worst-case bring-up, and escalation slower than recovery.

5. **Calibration constants travel in pairs.** Wheel diameter and ticks-
   per-rev had compensating errors; fixing one alone made things worse.
   Whenever a constant is corrected from first principles, audit every
   constant that was tuned in its presence.

6. **The operator's pushback is data.** "It's not related to charging"
   was the pivot of the entire power saga. Instrumenting the user's claim
   (pack voltage vs pin voltage) cracked a problem that had been
   misattributed for twelve hours.

7. **Hardware and software take turns hiding each other.** The ENA/ENB
   wires hid behind the PWM floor bug, which hid behind the SHM
   corruption, which hid behind the brownouts. The direct-serial motor
   test — thirty seconds, no software above the firmware — was the knife
   that cut every such knot. Keep it sharp (Appendix B).

8. **Verify on the metal, narrate honestly.** Every "fixed" in this report
   is backed by an observation on the physical robot, and the two
   genuinely embarrassing moments (the min_pwm formula committed without
   being applied; the combo-focus regression introduced by our own
   hardening) are recorded as such. The credibility of the next "it
   works" depends on it.

---

## Part VI — Final System State & Verification Matrix

| Capability | Robot | Status | Evidence |
|---|---|---|---|
| LiDAR supervised + auto-recovering | Alpha | ✅ | respawn observed live; 70 s scan-age watch 0.02–0.64 s |
| Scan watchdog (graced) | Alpha | ✅ | zero false kills post-fix; journal clean |
| rf2o laser odometry → SLAM | Alpha | ✅ | /odom 7.3 Hz; full TF chain; map quality jump |
| 0.025 m maps, gradient render | Alpha | ✅ | screenshots; operator confirmation |
| Click-to-navigate + collision guard | Alpha | ✅ | 5 live arrivals; correct refusals with coordinates |
| Arc-turn / guarded reverse | Alpha | ✅ | corridor maneuvers in live logs |
| RESET MAP end-to-end | Alpha | ✅ | operator-triggered live; designed sequence in log |
| Power delivery (5 V at chip) | Beta | ✅ | pins 5.05 V under load; flags 0x80000; CPU 1200+ MHz |
| Preflight power gate (graced) | Beta | ✅ | PASS on healthy boot; still blocks persistent sag |
| Serial bridge (bounded drain) | Beta | ✅ | connect 1.5 s; telemetry 19.8 Hz, 0 gaps |
| Motors + enable wiring | Beta | ✅ | direct-serial FWD/PIVOT deltas; operator driving |
| PWM floor (all speeds move) | Beta | ✅ | default-speed drive verified |
| Kinematics (85 mm / 408 CPR) | Beta | ✅ | spec-derived; plausible distances (tape-check advised) |
| IMU fusion + dead-zero fallback | Beta | ✅ | both transitions observed live |
| Pivot turning (torque floor) | Beta | ✅ | correct per-side encoder signs; smooth th sweep |
| Stall detection → incident feed | Beta | ✅ | fired correctly during real stalls |
| DDS SHM auto-purge | Both | ✅ | delivery restored instantly; ExecStartPre deployed |
| Camera + AI detection | Beta | ✅ | 13.3 FPS / 61 ms; real detection + debounce clear |
| Map tracking of motion | Beta | ✅ | operator: "move in map, nice work" |
| Multi-robot isolation | Both | ✅ | runtime env verified: domains 11/12, localhost-only |
| Fire alarm gate 0.80 | Console | ✅ | deployed; trade-off documented |

---

## Part VII — Outstanding Items & Demo-Day Recommendations

**Hardware (team actions):**
1. **Robot1 left flank:** tuck the cable/bracket out of the lidar scan
   plane (measured envelope x −0.15…+0.23, y +0.15…0.28 from lidar
   center); then shrink the software exclusion pocket.
2. **Robot2 GY-87:** finalize VCC on 5 V, solder the jumpers, dress I2C
   away from motor wiring (it works now; make it stay working).
3. **Robot2 heatsink:** the SoC hit 69 °C and engaged the soft thermal
   cap; a heatsink (or chassis airflow) buys back the last 200 MHz.
4. **Power for demo day:** strongly consider the split topology — motors
   on the 12 V pack, **Pi on its own USB power bank**. It decouples the
   computer from every motor transient and retires this report's biggest
   chapter permanently. Bring a charged spare pack regardless.
5. **Robot2 motor trim:** open-loop right-arc (left ~1.6× right counts) —
   acceptable for navigation (goto corrects), annoying for manual lines;
   PWM trim if time permits.
6. **Spin calibration:** command a 360° pivot, adjust `wheel_base_m`
   (currently estimated 0.225) until reported = actual; tape-measure a
   1.00 m straight run to confirm 408 CPR end-to-end.

**Software (low-risk, when convenient):**
7. Fine-tune a fire model on the team's own footage — the only real
   answer to the 26–48% false-positive overlap (C-7).
8. Firmware: order the GY-87 magnetometer init after MPU bypass-enable so
   cold boots stop printing a harmless FAIL (B-6).
9. Robot3 (Gamma) was untouched these two days; give it one live session
   before the demo.

**Demo-day runbook deltas:**
10. Power on Alpha first (map source), then Beta; SET POSE Beta once on
    the shared map.
11. After any robot power-cycle, restart the console too (fresh
    connections + current config) — two minutes that prevent two
    "mystery" symptoms documented in this report.
12. `vcgencmd get_throttled` on both Pis at T-30: demand a trailing even
    digit.
13. F9 is the fire-alarm drill; the live model will rarely cross 0.80 by
    design.

---

## Appendix A — Complete Commit Log

All commits on `main`, oldest first, for the period covered:

| Commit | Summary |
|---|---|
| `fb9b33d` | Hardened the team's field fixes: reset_map routing, /pose guard, real command-tick isolation + publish lock, key filter carve-outs, sim reset_map, stylesheet/objectName fixes |
| `c42700b` | Preserved robot-side preflight fixes (set ±u, GP_DIR) on both robots; stored exec bits on all shell scripts |
| `16c941d` | robot1: LiDAR driver supervised directly (respawn); slam_toolbox + static TFs respawn |
| `fd9a19a` | scan_watchdog: startup & post-kill grace, non-blocking motor kick |
| `5b7b2e3` | Dropped accidentally committed throwaway script |
| `1b47545` | Teleop focus regression fixed (NoFocus combos, narrowed filter); RViz-grade occupancy gradient; scan polish; SLAM registration thresholds |
| `a1ade31` | LiDAR map-quality research notes filed into docs/design_notes/ |
| `d096025` | 0.025 m SLAM resolution; gateway reports map-frame pose merged with odom velocities |
| `0f07a3a` | rf2o laser odometry integrated (source build, launch, overlay sourcing, installer user fix) |
| `5e2e789` | 180° laser TF; robot1_goto controller with LiDAR collision guard; footprint-accurate planning; smooth pose animation; true-scale footprint rendering |
| `fc7acc9` | goto: chassis self-hit exclusion |
| `9715bf3` | goto: boot-learned self-occlusion mask; planner despeckle |
| `4851f1a` | goto: rotation guard by true sweep geometry; BLOCKED logs carry nearest-point coordinates |
| `b4e9460` | goto: arc turns and guarded reversing for tight spaces |
| `5f3892d` | goto: self-mask hardening (distance band, size cap, tighter bound) |
| `424b292` | goto: probing rotation; measured left-fixture exclusion pocket |
| `cb65351` | goto: pocket widened to full observed envelope (the robot1 navigation series `fc7acc9`…`cb65351` was deployed via SSH git bundles during robot1's internet outage) |
| `353f403` | robot2 odom: pure-encoder heading on dead-zero IMU, auto-restore |
| `d625986` | robot2_bridge: bounded boot-banner drain (the 50 Hz stream infinite loop) |
| `06c84dc` | robot2: real kinematics (85 mm), turn torque floor, drive-biased arbitration |
| `27af3b4` | robot2_bridge: MOTOR STALL announcer |
| `cd0e173` | Fire alarm gate 0.80 with documented model-overlap trade-off |
| `7b0fad5` | preflight: boot-inrush grace (3 samples / 10 s) on both robots |
| `c99ce84` | robot2: 408 CPR per 25GA370 spec; research docs filed; stray file evicted |
| `c801e27` | Dropped throwaway lag probe |
| `77514e1` | robot2: min_pwm declared (formula application missed) |
| `d5e594d` | robot2_bridge: min_pwm actually applied in the mapping |
| `debcbde` | Dropped session throwaway probes |
| `e18d699` | systemd: FastDDS shared-memory purge in ExecStartPre on both robots |

## Appendix B — Diagnostic Cookbook

The probes that solved this period's mysteries, ready for reuse.

**Power truth (run on the Pi):**
```bash
vcgencmd get_throttled      # trailing digit ODD = undervolted RIGHT NOW
vcgencmd measure_clock arm  # 600 MHz = throttled; 1200 = thermal cap; 1400 = healthy
vcgencmd measure_temp
```
Rule: also put a multimeter on GPIO pin 2/4 (+5 V) vs pin 6 (GND) **while
the system is under load**. That number, not the buck's terminal voltage,
decides everything. Target 5.10–5.15 V.

**Hardware-vs-software motor splitter (run on the Pi; the knife):**
```bash
sudo systemctl stop gp-robot2.service
python3 - <<'EOF'
import serial, time
s = serial.Serial('/dev/mega', 115200, timeout=0.2); time.sleep(2.5)
s.reset_input_buffer(); s.write(b'P255\n')
t=time.time()+0.8
while time.time()<t: s.write(b'F\n'); time.sleep(0.2)
s.write(b'S\nS\n')
# watch D: lines for encoder deltas
EOF
sudo systemctl start gp-robot2.service
```
Wheels turn → hardware fine, blame software. Frozen at P255 → electrical.

**"Connected but no data" (the SHM check):**
```bash
ls /dev/shm/ | grep fastrtps          # stale segments after crashes
# cure (stack stopped): rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing*
# now automatic via ExecStartPre in both gp-robot units
```

**Is the robot even receiving commands? (gateway counters, from laptop):**
subscribe to health (port 5559) and read `cmd_stats` — `cmds`/`acks`
climbing proves the network path; zero proves console-side.

**Where is a Python node stuck? (on the Pi):**
```bash
pip3 install py-spy
py-spy dump --pid $(pgrep -f robot2_bridge.py)
# MainThread in wait_for_ready_callbacks = healthy-but-starved (suspect transport)
```

**Did the goto refuse correctly?** Read the BLOCKED line — it prints the
nearest obstacle's body-frame x/y/distance. `y=+0.21` recurring at a fixed
body position across motion = something bolted to the robot.

**ROS topic sanity (on the Pi; islands need the env):**
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=12 ROS_LOCALHOST_ONLY=1     # 11 on robot1
ros2 topic info /manual_cmd      # pub/sub counts: discovery
ros2 topic hz /encoders          # delivery (the part SHM corruption kills)
```

**Firmware boot verdicts:** the Mega prints an I2C scan and per-device
INIT results on every reset (bridge restart = Mega reset). One journal
grep replaces an hour of multimeter work:
```bash
journalctl -u gp-robot2.service -b -o cat | grep -aE 'SCAN|INIT'
```

## Appendix C — Calibration Constants

Robot 2 (Beta) — all values now spec- or measurement-derived:

| Constant | Old | New | Source |
|---|---|---|---|
| Wheel diameter | 0.065 m | **0.085 m** | team measurement |
| Ticks per wheel rev | 330 | **408** | 25GA370 spec: 12 PPR × 34:1, 1× decode |
| Track width | 0.23 m | **0.225 m** (estimate) | chassis 0.20 m + wheel; spin-calibrate |
| Meters per tick | 6.19e-4 | **6.54e-4** | derived |
| Drive PWM range | 80–255 | **150–255** | static-friction threshold measured |
| Turn PWM floor | (none) | **215** | skid-pivot torque requirement |
| Chassis footprint | — | **0.30 × 0.20 m** | team measurement |
| IMU heading weight | 0.7 gyro / 0.3 enc | same, **with dead-zero fallback** | B-3 |

Robot 1 (Alpha):

| Constant | Value | Source |
|---|---|---|
| Chassis footprint | 0.40 × 0.30 m | team measurement |
| Lidar center → front edge | 0.10 m | team measurement (5 cm body + 5 cm lidar radius) |
| Rear overhang from lidar | 0.30 m | derived — drives the 0.335 m pivot sweep |
| base_link→laser yaw | **π** | A-7 (A1 zero-axis faces rear) |
| SLAM resolution | 0.025 m | A-5 (with rf2o) |
| SLAM registration | 0.10 m / 0.17 rad | A-5 |
| Planner hard inflation | half-width + 0.05 m | per-robot from footprint |
| Goto corridors | ±0.21 m drive · 0.36 m rear swing · 0.16 m floor | A-9 |

## Appendix D — Power Delivery Reference (Pi 3B+)

The numbers that ended the longest argument of the project:

- Brownout detector threshold: **~4.63 V** at the chip. Below it: the
  `0x…[odd]` flag, CPU pinned to 600 MHz, WiFi instability.
- Specified input: 5 V ± 5% → ceiling **5.25 V — measured at the Pi**, not
  at the supply.
- Measured path loss on this robot (buck → re-gauged cable → micro-USB
  connector → polyfuse): **0.4–0.5 V at 1.5–2 A**. Setpoint to compensate:
  buck 5.52 V → Pi pins 5.05 V under load.
- Boot inrush (USB enumeration + WiFi radio) can flag undervoltage for an
  instant even on a healthy rail — hence preflight's 3-sample grace.
- Capacitors that mattered: 1000 µF/25 V electrolytic at the buck output
  *and* at the Pi connector (stripe to GND — a reversed electrolytic at
  first power-on fails violently), 100 nF ceramic in parallel where
  available, plus 1000 µF/25 V across the L298N's 12 V input to kill motor
  inrush at the source.
- Soft thermal limit: 60 °C → 1200 MHz cap (observed at 69 °C). Heatsink
  recommended.
- The protective chain, verified working end to end: sagging rail →
  `get_throttled` flags → preflight blocks the stack with a plain-language
  reason → console shows the robot honestly absent instead of half-alive.

---

*Report generated 2026-06-11. Every commit referenced is on
`origin/main`; every verification was performed on the physical robots.
For the protocol itself see `docs/protocol.md`; for demo-day procedure see
`docs/runbook_demo_day.md`; for wiring see `docs/wiring/`.*
