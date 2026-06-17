---
name: project-goal
description: The GP graduation project goal + master/slave demo scenario — Alpha maps & commands (master), Beta navigates/detects/acts on fire with a 5s operator-interruptible pump, Gamma reads gas at the fire; all centralized, master->slave logs mocked. Invoke to recall the goal and check current work against it.
---

# GP Project Goal — Multi-Robot Emergency-Response Swarm

## The goal (always keep this in mind)

A coordinated **3-robot emergency / inspection swarm**, orchestrated
**CENTRALLY by the laptop dashboard**. The robots do **NOT** talk to each other
in reality — the "master sends orders to slaves" is **mocked in the dashboard
UI logs**; all real control is centralized in the laptop software.

- **robot1 "Alpha" — MAPPER + MASTER.** Builds the map (SLAM) and issues the
  (virtual) orders to the other robots.
- **robot2 "Beta" — INTERVENER.** Navigates through the map, finds
  hazards/obstacles, and **detects objects** in the area. When it detects a
  **FIRE**, it takes an **ACTION** (e.g., run the water **pump** to put it out).
  The dashboard operator can **INTERRUPT** the action; if **not interrupted
  within 5 seconds**, the action executes automatically.
- **robot3 "Gamma" — INSPECTOR.** Goes to the **fire location** and stands near
  it to measure the **GAS level** in that area.

## Demo flow (graduation presentation)

1. The robots start positioned **beside each other**.
2. Alpha maps, then commands Beta to navigate the map and find objects.
3. Beta navigates → detects the fire → **action (pump)** with a **5 s
   operator-interruptible countdown** → extinguishes.
4. Alpha commands Gamma to go to the fire and read the gas level there.
5. Every step shows in the logs as a **master → slave** command, e.g.:
   - `robot1 sent an action to robot2 to navigate through the map and find objects`
   - `robot1 sent action to robot3 to go to the fire place to get the gas level there`

## Hard constraints

- **Centralized only** — no real robot-to-robot communication. The master/slave
  messaging is simulated in the dashboard logs.
- **Operator override at every step** — the 5 s interruptible action, plus a
  global ABORT.
- For the presentation the scenario runs as a **pure dashboard simulation**
  (robots don't have to actually move/pump), so it's safe and repeatable.

## Status (keep updated)

- **Built (full scenario):** master/slave **MISSION** tab as a pure simulation —
  Alpha returns → commands Beta to navigate & find objects → Beta detects fire →
  goes to extinguish → **5 s operator-interruptible PUMP countdown** → Gamma
  commanded to the fire to read the **gas level** → done. Exact log phrasing
  ("robot1 sent an action to robot2 …"). Files:
  `dashboard_qt/ui/master_mission.py`, `dashboard_qt/ui/mission_panel.py`,
  wired in `dashboard_qt/ui/main_window.py`.
- Operator controls: AUTO/MANUAL, NEXT PHASE, **INTERRUPT PUMP** (5 s window),
  ABORT.
- **Dashboard support features** (help run the demo cleanly): map markers cap +
  TTL and **clamp robot icons to the map** (lidar-less Beta drifts off otherwise);
  a **REMOVE** map tool to delete a wrong/misleading detection (suppressed from
  reappearing); proximity readout flags a dead ultrasonic as **NO ECHO**; map
  pose tracks the robot with minimal delay; 50 Hz robot-side heading + telemetry
  coalescing to keep the map smooth.

## Known hardware reality (Beta)

Beta has **no lidar** → its map pose is dead-reckoning and drifts; it also
**overheats/throttles (~80 °C)** and is **power-marginal**, and one front
ultrasonic / a wheel encoder can be flaky. So the live demo runs as a
**simulation** (above) to stay safe and repeatable; real autonomous driving is
best-effort and needs cooling + a firm 5 V to be reliable.

## When this skill is invoked

Restate the goal above, then check the current task/diff against it — confirm
new work serves this scenario and flag anything that drifts from it.
