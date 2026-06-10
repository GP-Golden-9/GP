# GP Fleet Protocol v1

The ONLY traffic that crosses the WiFi. Each Pi is a DDS island
(`ROS_LOCALHOST_ONLY=1`); the gateway translates between local ROS topics
and these channels. Implemented in `common/gpcore/protocol/`; robot side in
`gateway/zmq_server.py`; consumer side in `dashboard_qt/transport/`.

## Ports (identical scheme per robot host)

| Port | Channel | Pattern | Content | Rate |
|---|---|---|---|---|
| 5555 | video-legacy | PUB | raw JPEG (NiceGUI fallback) | ≤30 fps, retired after Qt parity |
| 5556 | telemetry | PUB | `tele.full`, `tele.scan` | 20 Hz / 5 Hz |
| 5557 | map | PUB | `map.grid` | ≤1 Hz |
| 5558 | command | ROUTER↔DEALER | `cmd.*` in, `ack` out | on demand |
| 5559 | health | PUB | `health`, `log.event` | 1 Hz / event |
| 5560 | video | PUB | length-prefixed envelope+JPEG | 15 fps |

Robot3 (ESP32) speaks HTTP instead: `GET /control?dir=F|B|L|R|S`,
`GET /telemetry` → `{d,g,x,y,a,rssi,uptime,last_cmd_age}`; wrapped
laptop-side by `transport/esp32_link.py` behind the same signal surface.

## Envelope (msgpack map, every message)

```
{v:1, seq, t_mono, t_wall, run_id, src, type, payload}
```

* `seq` is **per message type** — `tele.scan` interleaving on the telemetry
  socket must not look like `tele.full` loss to gap detection.
* `t_mono` = sender monotonic seconds (staleness/latency math);
  `t_wall` = epoch (human log correlation); `run_id` = launch session id,
  identical across all nodes of one launch and in every log line.
* Video is ONE message: `4-byte BE header length ‖ envelope ‖ JPEG`.
  Multipart is forbidden on conflated channels — ZMQ `CONFLATE=1` hard-aborts
  the process on multipart (libzmq `fq.cpp` assert; found by our smoke test).

## Payloads

* `tele.full` — `{enc:[4], gyro:[3], accel:[3], odom:{x,y,th,v,w}, pump,
  servo_deg, estop, nav_status, motor_status, accessory}`
* `tele.scan` — `{a0, da, rmin, rmax, ranges:<float32-LE bytes>}`
* `map.grid` — `{w, h, res, ox, oy, enc:"zlib", data:<zlib int8 occupancy>}`
* `health` — `{uptime_s, streams_age_s:{...}, sys:{throttled, temp_c,
  rssi_dbm, load1, mem_free_mb, disk_free_mb}, cmd_stats, estop}`
* `video.meta` — `{w, h, fmt:"jpeg", cap_t_mono, frame_id}`

## Commands & ACKs

Types: `cmd.drive{vx,wz}` `cmd.estop{engage}` `cmd.pump{on}`
`cmd.servo{deg}` `cmd.explore{enable}` `cmd.goal{x,y}` `cmd.speed{value}`
`cmd.ping{}`. Every command carries a `cmd_id`; the robot replies
`ack{cmd_id, cmd_type, ok, detail}`.

* **Retry:** ACK timeout 300 ms, ×2 retries with the SAME `cmd_id`; the
  robot dedupes (64-entry LRU), so `cmd.pump`/`cmd.servo`/`cmd.goal` are
  exactly-once even under retry.
* **Drive stream:** the console repeats `cmd.drive` at 10 Hz while a control
  is held. Gateway deadman: 600 ms of silence while velocity ≠ 0 → stop.
  Layered below it: bridge deadman 0.8 s → firmware watchdog 1 s.
* **E-stop:** sent 5× at 50 ms spacing AND latches the gateway — drive
  commands are rejected (`estop latched`) until `cmd.estop{engage:false}`.
* **Liveness:** console pings 1 Hz; ack age > 3 s ⇒ link DOWN in the UI.

## Staleness (consumer side)

age < 2.5 s **FRESH** · < 5 s **STALE** · ≥ 5 s **DEAD** — swept every
250 ms per stream; badges in the health panel, NO SIGNAL banner on video.

## Verification

`tests/test_envelope.py`, `tests/test_commands.py`,
`tests/test_gateway_roundtrip.py` (inproc, no hardware) cover the wire
format, retry/dedupe, deadman and e-stop latch.
`tools/soak_test.py --host <robot> --minutes 30` measures the live KPIs
against the acceptance gates (loss <1 %, video ≥12 fps, ack p95 ≤150 ms…).
