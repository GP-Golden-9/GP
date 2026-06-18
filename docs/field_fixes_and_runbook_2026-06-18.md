# GP — Field Fixes & Runbook (through 2026-06-18)

For the team. Everything we hit on Beta/Alpha, the root cause, and the fix —
plus how to run the autonomous FIRE TEST and how to deploy. **No secrets
here** (SSH/WiFi/OTA creds live in the gitignored `config_secrets.h`).

---

## TL;DR — what changed and how to run

- Beta now navigates autonomously to an operator-placed fire on the map
  (global A* over Alpha's map + ultrasonic dodging) via the **FIRE TEST** tab.
- Major bugs fixed: wall-crashes from serial lag, ~45° yaw drift, the ~30 s
  motor-stall lock-up, the ~3 min slow boot.
- **One hardware thing still matters most:** the GY-87 IMU is on a marginal
  3.3 V feed and drops out intermittently → **rewire VCC to 5 V before the
  demo.** A power-cycle revives it temporarily.

### Run the FIRE TEST
1. Power Alpha; let it SLAM and **map the area** (the map must show in the
   console — Beta plans its global route over Alpha's map).
2. Power Beta. In the console, select Beta.
3. **⌖ SET POSE** Beta: press where it physically is, drag toward where it
   faces, release. (One-time alignment — Beta has no lidar/compass.)
4. **FIRE TEST** tab → **① PLACE FIRE** → click the map where the fire is.
5. **② GO TO FIRE.** Beta routes there, dodging unmapped obstacles. Status
   shows EN ROUTE → ARRIVED. **STOP** (panel) or **Esc** (e-stop) any time.

---

## Errors we hit and how they're fixed

### 1. Beta drives into walls "fine for a minute, then crashes"
- **Cause:** the bridge serial reader processed every 50 Hz packet FIFO; on a
  loaded Pi it fell behind, the kernel serial buffer filled, and every read
  returned **seconds-old** data — so the obstacle guard saw a wall that was
  already hit, and the heading integrated stale gyro.
- **Fix:** `robot2_bridge._serial_reader` now **drains to the latest packet**
  each pass (drops stale ones; encoders are cumulative so no odometry is
  lost). Latency is bounded to one cycle. Watch for `SERIAL BACKLOG: skipped N`
  in the log — that's the fix *working*, not a fault.

### 2. Yaw drift (~45°, then ~25° after calibration)
- **Cause A:** heading was integrated on the laptop at ~20 Hz from telemetry
  that gets thinned/jittered — integrating an angular *rate* with dropped
  samples loses angle on every turn.
- **Fix A:** heading is now integrated **in the bridge at 50 Hz using the
  Mega's own `ts` timestamp** (immune to CPU/serial jitter), shipped in the
  IMU orientation; the gateway forwards it; the laptop uses it directly.
- **Cause B:** the MPU6050's per-unit scale tolerance (~3%) — drift
  proportional to *rotation*, not time.
- **Fix B:** `drive.gyro_scale_correction: 1.0304` (measured with
  `tools/yaw_calib.py`, 3 turns: 1048° read for 1080° actual). To re-measure
  on another robot: `python tools/yaw_calib.py <robot-ip> 1080`, rotate 3
  slow full turns, paste the printed factor into `config/robotN.yaml`.

### 3. The ~30-second motor-stall LOCK-UP (lost manual + auto control)
- **Cause:** a stalled DC motor pulls near locked-rotor current → the rail
  sags → the Pi browns out / throttles to 600 MHz → the bridge/gateway crawl
  → commands queue for ~30 s. An **undervoltage cascade**, not a code loop.
- **Fix:** `robot2_bridge` **stall-disarm** — when the wheels stay frozen
  under a drive command for `drive.stall_disarm_s` (3.0 s), it **kills the
  motors** and blocks re-issuing the **same** direction for
  `stall_cooldown_s` (2 s); a **different** direction is allowed immediately
  so you can escape. Re-arms each cooldown. Works for manual AND auto.
- **Escape (auto):** `robot2_local_nav` subscribes `/stall` → **reverse +
  reorient** to the more-open side (fires even when ultrasonics read clear —
  a low obstacle or high-centred). After 4 stalls in 20 s it gives up
  (`STUCK`) rather than grind forever.
- If the lock-up ever returns, the rail can't hold 3 s of stall current —
  lower `stall_disarm_s` toward 1.5 and/or fix the power (caps + buck).

### 4. ~3-minute slow boot
- **Cause:** the systemd units waited on `network-online.target`
  (NetworkManager-wait-online, ~120 s timeout) — pointless for a
  localhost-only stack.
- **Fix:** removed `network-online.target` from
  `gp-robot{1,2}` / `gp-preflight` / `gp-camera`. Boot is now ~1 min.

### 5. "It rotates in real life but the map arrow is static" → IMU dropout
- **Cause:** the GY-87 dropped off the I2C bus; firmware `mpuRead()` fails
  silently and **streams the last-good values FROZEN** (identical every
  frame, and *non-zero*, so the all-zero dead-detector misses it). No live
  rotation → frozen heading → static arrow.
- **Diagnose:** `python tools/yaw_calib.py <ip>` (or watch the heading) while
  rotating — if `gz` never spikes past ~1 rad/s, the gyro is dead/frozen.
- **Fix now:** **power-cycle the robot** (re-inits + recalibrates the MPU).
  Confirmed working after a power-cycle (peak |gz| 1.65 rad/s, heading
  tracked 360°).
- **Fix for good:** rewire the GY-87 **VCC 3.3 V → 5 V** and resolder. The
  3.3 V pin is marginal; it *will* drop again until this is done.

### 6. DDS "gateway ACKs but robot never moves" (earlier session, kept)
- **Cause:** `ROS_LOCALHOST_ONLY=1` interface tracking silently killed all
  local DDS delivery on a flaky WiFi state change.
- **Fix:** isolation moved to the transport — `interfaceWhiteList 127.0.0.1`
  in `config/fastdds_udp_only.xml`, `ROS_LOCALHOST_ONLY=0`, localhost
  discovery server, distinct domains. NOTE: the `ros2` CLI is **blind in
  discovery-server mode** — debug with the bridge's arrival logs + gateway
  freshness, not `ros2 topic`.

---

## Deploying to the robots

Units live in `/etc/systemd/system` — a plain `git pull` does NOT update them.
For a systemd/unit change, after pulling run:
`sudo bash systemd/install_systemd.sh robotN ~/GP` (or `tools/deploy_and_verify.sh robotN`).

### Beta has no GitHub internet → deploy by git BUNDLE over the LAN
```
# on the laptop (BASE must be Beta's actual HEAD — its origin/main is stale):
git bundle create ~/gp.bundle <beta-HEAD>..main
scp ~/gp.bundle muc@<beta-ip>:~/         # NOT /tmp (it's a 50 MB full tmpfs)
# on Beta:
cd ~/GP && git fetch ~/gp.bundle main && git merge --ff-only FETCH_HEAD
sudo systemctl restart gp-robot2
```
Alpha (`robot.local`) usually has working internet → normal `git pull`.

---

## Architecture notes (so the team isn't surprised)

- **Odometry runs on the LAPTOP** now (`dashboard_qt/state/local_odom.py`),
  not the Pi — it reconstructs Beta's pose from telemetry (enc+gyro+heading).
  This freed ~80 % of a Pi core; Beta's launch runs ONE reactive node
  (`robot2_local_nav.py`).
- **The map link is via the laptop**, by design: ROS islands are isolated, so
  the console holds Alpha's map and plans Beta's global A* route, streaming
  Beta a simple `/cmd_vel_bias` it fuses with its ultrasonics. No fragile
  robot-to-robot map link.
- **Smooth/odometry-safe motion** is tuned conservative (config: turn ≤
  0.25 rad/s, lin ≤ 0.12 m/s, gentle 300 PWM/s accel ramp) to avoid wheel
  slip that corrupts the yaw.

---

## Open hardware tickets (do before the demo)
1. **GY-87 IMU: VCC 3.3 V → 5 V + resolder** (highest priority — it drops out).
2. Alpha: cable/bracket in the lidar plane on the left flank — tuck it away.
3. Heatsinks on the Pis (Beta has run warm).
4. VBUS backpower: the Mega backfeeds the Pi over USB — tape over VBUS or a
   master switch; SHUTDOWN from the console first, then cut power.
5. Re-measure robot2 track width with a 360° spin if pivots over/under-rotate.

## Handy tools
- `tools/yaw_calib.py <ip> [deg]` — measure the gyro scale factor.
- `tools/deploy_and_verify.sh robotN` — pull + reinstall units + restart + show boot chain.
- `tools/fleet_healthcheck.py`, `tools/collect_logs.py` — diagnostics.
