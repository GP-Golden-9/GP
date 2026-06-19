# Citation Placement Map

Where to insert each new reference, by section. Place the citation **immediately after
the sentence/term** noted (Mendeley Cite → put cursor there → Insert Citation → pick the
source). A source can (and should) be cited in more than one place. Mendeley assigns the
[n] number automatically and reuses it on repeat citations.

> Rule of thumb followed here: cite where the text **names a specific technology, method,
> prior system, or established fact** — those are defensible, verifiable attributions.
> Review each before accepting; the final scholarly call is yours.

## Chapter 1 — Introduction
| Place (anchor phrase) | Cite |
|---|---|
| §1.1/§1.2 first mention of "search and rescue" motivation | **[SAR]** |
| §1.1 "ROS 2" as the middleware | **[ROS2]** |
| §1.1/§1.2 "slam_toolbox" / "SLAM" first named | **[SLAMTB]**, **[SLAMSURVEY]** |
| §1.1 "YOLO-based … detection" | **[YOLO]**, **[YOLOV8]** |
| §1.1 "ZeroMQ (ZMQ) … msgpack" | **[ZMQ]** |

## Chapter 2 — Literature Review (most citations belong here)
| Place | Cite |
|---|---|
| §2.1/§2.2 swarm & multi-robot framing | *(you already cite [1],[2],[4]; keep)* |
| §2.3 "search and rescue robotic systems" | **[SAR]** |
| §2.4.1 "SLAM fundamentals" / definition of SLAM | **[SLAMSURVEY]** |
| §2.4.1 "occupancy grid" first defined | **[ELFES]** |
| §2.4.2 where **slam_toolbox** is named as the chosen library | **[SLAMTB]** |
| §2.4.2/§2.4.3 laser/scan odometry → "rf2o" | **[RF2O]** |
| §2.4.4 "sensor fusion" / "complementary filter" | **[MAHONY]** |
| §2.5.2 "YOLO (You Only Look Once)" definition | **[YOLO]** |
| §2.5.2 mention of the YOLOv8 family / Ultralytics | **[YOLOV8]** |
| §2.6.1 "Robot Operating System (ROS)" | **[ROS2]** |
| §2.6.2 "ZeroMQ" / network communication | **[ZMQ]** |
| §2.7.3 "differential-drive" / mobile-robot kinematics | **[AMR]** |
| §2.x path-planning / A* discussion | **[ASTAR]** |

## Chapter 3 — System Analysis & Design
| Place | Cite |
|---|---|
| §3.4 "occupancy grid map" shared representation | **[ELFES]** |
| §3.5.2 ROS 2 node architecture | **[ROS2]** |
| §3.5.2 SLAM via slam_toolbox | **[SLAMTB]** |
| §3.5.2 "A* route planning" first named | **[ASTAR]** |
| §3.5 complementary-filter odometry design | **[MAHONY]** |
| §3.6 "ZeroMQ (ZMQ) gateway" | **[ZMQ]** |

## Chapter 4 — Implementation
| Place | Cite |
|---|---|
| §4.2.1 "async_slam_toolbox_node" / slam_toolbox | **[SLAMTB]** |
| §4.2.1 "rf2o laser odometry" | **[RF2O]** |
| §4.2.2 "YOLOv8 … yolov8s.pt" detection pipeline | **[YOLOV8]** (and **[YOLO]** for the base method) |
| §4.2.3 complementary filter (encoder + gyro) | **[MAHONY]** |
| §4.2.4 msgpack-over-ZMQ gateway | **[ZMQ]** |
| §4.2.4 ROS 2 islands | **[ROS2]** |
| §4.3 A* planner (octile, inflation) | **[ASTAR]** |

## Chapter 5 — Testing & Results
| Place | Cite |
|---|---|
| §5.1 testing methodology referencing mobile-robot practice | **[AMR]** |
| §5.3.1 SLAM/mapping evaluation | **[SLAMTB]**, **[SLAMSURVEY]** |
| §5.3.3 localization/odometry (complementary filter) | **[MAHONY]** |

## Chapter 6 — Conclusion
- No new citations strictly required; if you restate a capability, reuse the citation
  introduced earlier (e.g., SLAM → **[SLAMTB]**, detection → **[YOLOV8]**).

---
### Coverage note (honest scope)
This map covers the **named technologies/methods/established facts**. It does **not**
blanket-cite every sentence — attaching a source to a claim it doesn't actually support
would be worse than no citation in a defense. If you have additional sources you read for
specific empirical claims (e.g., a particular SAR statistic), add those where they belong.
