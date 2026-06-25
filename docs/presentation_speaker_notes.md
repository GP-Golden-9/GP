# Speaker Notes — *Swarm Emergency Robotics System* (final presentation)

A slide-by-slide presenter script for `docs/Graduation project Presentation-final
version.pdf` (26 slides). For each slide: **what's on it**, **what to say** (a
natural spoken script — say it in your own words, don't read it), **emphasize**,
and a **transition** to the next slide. Technical claims match the real system
(see `docs/presentation_qa.md` for the deep Q&A).

> Timing: aim ~30–45 s on content slides, ~10 s on section dividers. 26 slides ≈
> **12–15 minutes** of talking, leaving time for the demo + questions. Decide who
> presents which block and rehearse the **transitions** — that's what makes a team
> talk feel smooth.

---

## Slide 1 — Title: "Graduation Project · Computer Engineering · 2025–2026"
**On screen:** project/department/year title card.
**Say:** "Good morning. Thank you for being here. We're the Computer Engineering
graduation team, and today we'll present our project: a **Swarm Emergency
Robotics System**."
**Emphasize:** confident open, smile, make eye contact. Don't rush.
**Transition:** "First, let me introduce the team and our supervisors."

## Slide 2 — Title: "Swarm Emergency Robotics System" + supervisors
**On screen:** project name; Dr. Hassan Ibrahim; Eng. Asmaa Sabet; Eng. Hager
Mohamed.
**Say:** "Our project is supervised by Dr. Hassan Ibrahim, with Engineer Asmaa
Sabet and Engineer Hager Mohamed. The team is [say each member's name and the
part they led — e.g., mapping, vision, hardware, the console]."
**Emphasize:** thank the supervisors by name; state who built what (shows real
ownership).
**Transition:** "Here's how the next 15 minutes will go."

## Slide 3 — Agenda (7 sections)
**On screen:** 1 Introduction & Problem · 2 Theoretical Background · 3 System
Architecture · 4 Implementation Hardware · 5 Software & Algorithms · 6 Testing &
Results · 7 Future Work.
**Say:** "We'll start with the problem that motivated us, cover the theory behind
our solution, then go through the system architecture, the hardware, the software
and algorithms, our testing and results, and finish with future work."
**Emphasize:** keep it to ~10 seconds — don't read all seven items slowly.
**Transition:** "Let's begin with why this project matters."

## Slide 4 — Section divider: "Introduction & Problem Statement"
**Say:** "To understand our motivation, consider a real disaster."
**Transition:** straight into slide 5.

## Slide 5 — Introduction: the real disaster
**On screen:** Rescuers ready but forbidden to enter for **9 days** · toxic gas
(Methane & CO) unknown/unstable · no rescue in time · **all 29 miners died**.
**Say:** "In a real mining disaster, rescue teams were ready and waiting — but
they were forbidden from entering for nine days. Why? Because the levels of toxic
gas, methane and carbon monoxide, were unknown and unstable. No one could tell if
it was safe. By the time conditions were understood, it was too late: all
twenty-nine miners died. This is the Pike River mine disaster — and it's the kind
of situation our system is built for."
**Emphasize:** slow down here. Let the "29 miners died" land. This is your
emotional hook — the judges remember it.
**Transition:** "This tragedy points to a clear set of problems."

## Slide 6 — Problem Statement (4 challenges)
**On screen:** Inaccessible Environments · Lethal Atmospheric Hazards · Critical
Time Latency · Obstacles.
**Say:** "Four core problems. **Inaccessible environments** — collapsed or
unstable structures humans can't enter. **Lethal atmospheric hazards** —
invisible gases that kill before you see them. **Critical time latency** — every
minute of delay costs lives. And **obstacles** — debris and unknown layouts that
make navigation hard. A human rescuer faces all four at once."
**Emphasize:** these four map directly to our three robots' jobs — set that up.
**Transition:** "So our solution sends robots in first."

## Slide 7 — Solution: Swarm Emergency Robotics System
**On screen:** Map the Unknown · Sense the Invisible · Spot the Survivors.
**Say:** "Our answer is a team of robots that goes in before any human. They do
three things: **map the unknown** — build a live map of a space no one has seen;
**sense the invisible** — measure the toxic gases; and **spot the survivors** —
use a camera and AI to find people. Three jobs, three specialized robots, one
operator."
**Emphasize:** "before any human" — that's the whole value proposition.
**Transition:** "The key idea that makes this work is collaborative
intelligence."

## Slide 8 — "Collaborative Intelligence"
**On screen:** *"Collaborative Intelligence — distributing specialized sensory
workloads across heterogeneous robotic agents to tackle high-risk, unstructured
environments."*
**Say:** "The principle behind our design is **collaborative intelligence**.
Instead of one expensive robot that does everything poorly, we distribute the
work across **heterogeneous** agents — robots with different bodies and sensors,
each expert at one task. One maps, one intervenes, one inspects gas. Together
they cover a dangerous, unstructured environment far better than any single
machine."
**Emphasize:** the word **heterogeneous** — different robots, not identical ones.
That's your academic contribution.
**Transition:** "Concretely, our objectives were three."

## Slide 9 — Project Objectives
**On screen:** Reduce human risk · Improve exploration coverage · Real-time
monitoring and detection.
**Say:** "We set three measurable objectives. **Reduce human risk** — keep
rescuers out until we know it's safe. **Improve exploration coverage** — multiple
robots cover more ground, faster, than one. And **real-time monitoring and
detection** — stream live map, gas, and victim detection to an operator who makes
the call."
**Emphasize:** these are the goals you'll prove you met in Testing & Results.
**Transition:** "Before the architecture, some background on the key concepts."

## Slide 10 — Section divider: "Theoretical Background"
**Say:** "Let's quickly cover the theory we build on."
**Transition:** into slide 11.

## Slide 11 — Limitations of Traditional Solutions
**On screen:** Human-based rescue · Single robot systems · Limited field of view ·
Limited coverage area.
**Say:** "Why not existing solutions? **Human rescue** is exactly what fails in a
gas-filled space. A **single-robot system** is a single point of failure — if it
gets stuck or breaks, the mission ends. And a single robot has a **limited field
of view** and **limited coverage** — it can only be in one place, looking one
way. Our multi-robot approach attacks all of these."
**Emphasize:** single robot = single point of failure → motivates the swarm.
**Transition:** "And what does the research literature say?"

## Slide 12 — Related Work
**On screen:** Most studies focus on **Simulation** · Physical Implementation ·
Fabrication.
**Say:** "When we surveyed related work, we found that **most studies stop at
simulation** — they prove an idea in software but never build it. Our project's
contribution is the opposite: a **physical implementation** — real robots, real
fabrication, real sensors talking over a real network. Going from simulation to
working hardware is where most of the hard engineering lives, and it's where we
focused."
**Emphasize:** "we actually built it" — judges value real hardware over a sim.
**Transition:** "So why a swarm specifically?"

## Slide 13 — Why Swarm Robotics?
**On screen:** Parallelism · Redundancy · Cooperative behavior.
**Say:** "Three reasons. **Parallelism** — robots work at the same time, so the
area is covered faster. **Redundancy** — if one robot fails, the others continue;
no single point of failure. And **cooperative behavior** — they share
information; our mapper's map is used by the others to navigate. The whole is more
capable than the sum of the parts."
**Emphasize:** tie each word to your system (parallel SCAN, redundant fleet,
shared map).
**Transition:** "Two core technologies make it possible — first, SLAM."

## Slide 14 — Concept: SLAM
**On screen:** Simultaneous Localization And Mapping · building a map without GPS.
**Say:** "The first is **SLAM** — Simultaneous Localization and Mapping. It solves
a chicken-and-egg problem: to build a map you need to know where you are, but to
know where you are you need a map. SLAM does both **at the same time**, using a
laser scanner. Crucially, it works **without GPS** — which is essential indoors,
underground, or in a collapsed building where GPS doesn't reach. Our mapper robot
runs SLAM to build a live 2.5-centimeter map."
**Emphasize:** "without GPS" — that's the indoor/underground point.
**Transition:** "The second technology is computer vision."

## Slide 15 — Concept: Computer Vision (YOLO)
**On screen:** YOLO (You Only Look Once) · real-time detection · victims vs.
debris.
**Say:** "The second is **computer vision** for finding people. We use **YOLO** —
'You Only Look Once' — a real-time object detector. In a single pass over each
camera frame it locates and labels objects, fast enough for a live video stream.
The key job is telling a **survivor apart from debris** — a person versus a pile
of rubble — so the operator's attention goes to what matters."
**Emphasize:** "real-time" and "person vs. debris" — that's why YOLO, not a slow
classifier.
**Transition:** "Now, how does the whole system fit together?"

## Slide 16 — Section divider: "System Architecture"
**Say:** "Here's how we engineered the full system."
**Transition:** into slide 17.

## Slide 17 — System Requirements Matrix
**On screen:** Functional (Real-Time Mapping — 2.5 cm grid; Hazard Projection onto
shared maps; Gas Sensing — 3 Hz polling with threshold latching) · Non-Functional
(Low-Latency — P95 command ACK ≤ 150 ms; Compute Offloading — YOLO in a
crash-isolated laptop subprocess; Console Stability; Dynamic navigation via the
dashboard).
**Say:** "We defined clear, measurable requirements. **Functionally**: real-time
mapping at a 2.5-centimeter grid; automatic projection of detected hazards onto
the shared map; and gas sensing polled at 3 hertz with a latching threshold, so
an alarm stays on once it trips. **Non-functionally**: low latency — 95% of
commands acknowledged in under 150 milliseconds; **compute offloading** — the
heavy YOLO AI runs in a separate, crash-isolated process on the laptop; and
console stability — an AI crash can never freeze the operator's screen. These
aren't vague goals; each one is a number we tested against."
**Emphasize:** the **numbers** (2.5 cm, 3 Hz, 150 ms) and "crash-isolated" — this
slide proves engineering rigor. This is a strong slide; spend time here.
**Transition:** "Architecturally, those requirements led to a distributed
design."

## Slide 18 — System Architecture & Data Flow
**On screen:** Distributed Computing · Communication Layer · Communication
network (likely a block diagram).
**Say:** "The system is **distributed**. Each robot runs its own control software
locally and stays an **isolated island** — its internal robotics traffic never
goes on the wireless network. The only door to the network is a small **gateway**
per robot, which speaks a compact, efficient binary protocol over a dedicated
WiFi router — no internet needed. The **laptop is the coordinator**: it collects
each robot's map, video, and sensors, plans the navigation, and sends back simple
commands. This design is what makes the system robust to flaky WiFi — a network
hiccup can't corrupt a robot's control loop."
**Emphasize:** "isolated islands + one gateway + laptop coordinator." If asked,
name it: msgpack-over-ZMQ on fixed ports, with acknowledged commands.
**Transition:** "All of this surfaces to the operator through one dashboard."

## Slide 19 — Dashboard & Monitoring
**On screen:** Live Detection · Live Localization · Manual Control · Sensor
Readings · Robots Status (likely a screenshot of the console).
**Say:** "Everything comes together in one operator console — a native desktop
app. From a single screen the operator sees **live detections** drawn on the
video, **live localization** of every robot on the shared map, **manual control**
to drive any robot, **sensor readings** like gas and distance, and the **status**
of each robot — fresh, stale, or disconnected. One person supervises the whole
fleet. The operator stays in the loop and can hit an emergency stop at any
instant — a deliberate safety choice for an emergency robot."
**Emphasize:** "one operator, one screen, always-available E-STOP." If this slide
has a screenshot, point to the map and the video.
**Transition:** "So — does it work? Let's look at testing and results."

## Slide 20 — Section divider: "Testing & Results"
**Say:** "We validated the system on real hardware, not just in simulation."
**Transition:** into slide 21.

## Slide 21 — Results (image/graphic slide)
**On screen:** results imagery — most likely a SLAM map next to the real arena,
detection screenshots, and/or the dashboard in action.
**Say:** "Here are our results. On the [left/top] is the **map our robot built
live** of the test environment, next to a photo of the real space — you can see
the walls and doorways line up. Here you can see the system **detecting a person
and a fire** and dropping markers on the map. We met our latency target —
commands acknowledged well under our 150-millisecond budget — and our pure-logic
software is covered by an automated test suite that all passes. Most importantly,
the full scenario runs end-to-end: the mapper maps, the intervener sweeps and
detects, and it drives to the hazard and acts."
**Emphasize:** WALK the judges through whatever is actually on this image — the
map fidelity, a detection, the dashboard. If you have a **live demo**, this is
the moment: "rather than just show slides, let me demonstrate it live." Have a
backup video in case WiFi fails.
**Transition:** "We're proud of what works — and clear-eyed about what's next."

## Slide 22 — Section divider: "Future Work"
**Say:** "Finally, where this goes next."
**Transition:** into slide 23.

## Slide 23 — Heterogeneous Swarm & Mesh Networking
**On screen:** Aerial-Ground Collaboration · Mesh Topology · Extended Range.
**Say:** "First, scaling the swarm. **Aerial-ground collaboration** — add drones
to map from above while ground robots work below. **Mesh networking** — let
robots relay through each other instead of all talking to one access point, so
the network self-heals. And **extended range** — those two together let the fleet
operate far deeper into a site than a single WiFi link allows."
**Emphasize:** mesh = removes the single-access-point limitation we have today.
**Transition:** "Second, smarter perception and more autonomy."

## Slide 24 — Advanced Perception & Autonomy
**On screen:** 3D Volumetric Mapping · Multi-Modal Sensing · Full Autonomy.
**Say:** "On perception and autonomy: move from a flat 2D map to **3D volumetric
mapping**, so we understand height and collapsed geometry. Add **multi-modal
sensing** — thermal cameras to see body heat through smoke, and more gas types.
And push toward **full autonomy**, where the robots explore and make more
decisions on their own, with the human supervising rather than directing. A
better-trained fire/victim detection model is part of this."
**Emphasize:** honest framing — today the human is in the loop by design; full
autonomy is the roadmap.
**Transition:** "And that brings us to the end."

## Slide 25 — (image/graphic slide — likely team photo / system render / summary)
**On screen:** an image — possibly the assembled robots, the team, or a closing
visual.
**Say:** "This is our system / our team. [If robots: "the three robots you've
heard about — the mapper, the intervener, and the gas inspector."] Everything
we've shown — the mapping, the detection, the coordination — runs on the hardware
in front of you."
**Emphasize:** bring it back to the physical, real, working system.
**Transition:** "Thank you."

## Slide 26 — "THANK YOU"
**Say:** "Thank you for your time and attention. We'd be happy to answer any
questions, and we have the system here for a live demonstration."
**Emphasize:** confident close; invite questions; offer the demo. Then **stop
talking** — let the panel ask.

---

## Presenter checklist (rehearse these)
- **Decide who says each block** and practice the hand-offs ("…and now [Name] will
  cover the architecture").
- **The hook (slide 5)** and **the results (slide 21)** are your two most important
  slides — over-rehearse those.
- **Have the demo ready AND a backup video** — WiFi can fail; never let a dead
  link kill the talk.
- **Know your numbers** (slide 17): 2.5 cm grid, 3 Hz gas, 150 ms ACK. If asked
  for one you forgot, name the principle and where it's configured.
- For deep technical Q&A, study `docs/presentation_qa.md` (full question bank).
- **Speak slowly on the disaster and the results.** Pauses read as confidence.
- End on slide 26 and **invite the live demo** — finishing with a working robot
  beats finishing with a slide.
```
