Legacy experiments quarantined here. Kept for reference; nothing imports them.
- nav2_params.yaml: Nav2 was never launched by any script in the repo.
- udp_*/mix_*: superseded streaming experiments (raw + chunked UDP).
- tcp_rasp.py: the q80/unbounded-queue camera script that caused the video
  lag (root cause #1) — replaced by tcp_rasp_zmq.py, then robots/robot2/nodes/camera_pub.py.
- tcp_lap.py / camera.py: laptop-side viewers replaced by dashboard_qt.
