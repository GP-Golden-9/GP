# Phase 0 — Baseline & Root-Cause Verification

Goal: attach **numbers** to every reported failure before changing anything, so
every later phase can prove it improved things. Create one file per robot per
session: `robot1_YYYYMMDD.md`, `robot2_YYYYMMDD.md` using the template below.

## 1. Laptop-side probe (30 min per robot, while driving)

```bash
python tools/baseline_probe.py --host robot.local  --duration 1800   # robot 1
python tools/baseline_probe.py --host robot2.local --duration 1800   # robot 2
```

During the run: hold forward > 2 s several times, do turns, let the map grow,
walk between the robot and the router to provoke WiFi fade.

## 2. Pi-side capture (SSH, paste output into the session file)

```bash
vcgencmd get_throttled     # 0x0 healthy | bit0 undervolt NOW | bit16 undervolt since boot
vcgencmd measure_temp
top -b -n 1 | head -20
free -h
dmesg | grep -iE 'usb|under-volt|brown' | tail -30
iwconfig wlan0 | grep -E 'Signal|Bit Rate'
df -h /
# Serial identity (run with both LiDAR and Arduino plugged in):
for d in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0; do
  echo "== $d"; udevadm info -q property -n $d 2>/dev/null | grep -E 'ID_VENDOR_ID|ID_MODEL_ID|ID_MODEL='
done
```

CP210x (`10c4:ea60`) = RPLidar. Mega (`2341:0042`) or CH340 (`1a86:7523`) = Arduino.
Record WHICH name each got — then power-cycle the Pi and record again. If they
ever swap, root cause #3 is confirmed.

## 3. Root-cause repro drills (one line of evidence each)

| # | Drill | Confirms |
|---|-------|----------|
| RC1 | Watch robot2 video latency while waving a hand: count seconds between motion and display | Video queue/latency (wrong camera script) |
| RC2 | Hold FORWARD from dashboard for 5 s; watch robot + Arduino serial monitor for `WARN`/timeout | Watchdog stall (bridge sends only on change) |
| RC3 | Power-cycle robot1 5×, record serial identities each boot (commands above) | LiDAR/Arduino port swap |
| RC4 | With BOTH robots on: on robot2's Pi run `ros2 topic list` and `ros2 topic echo /cmd_vel --once` while robot1's explorer runs | Cross-robot DDS leakage |
| RC5 | Press dashboard E-stop while robot drives autonomously; does it stop? (`ros2 topic echo /emergency_stop` on the Pi — anything?) | E-stop not wired |
| RC6 | Watch dashboard map for 10 min of driving; note every disappear/jump with timestamp | Map pipeline overload |
| RC7 | Robot3 driving forward via dashboard → turn the router OFF. Does it stop? | ESP32 missing watchdog |

## 4. Session file template

```markdown
# Baseline — robotN — YYYY-MM-DD — run by <name>
## Probe summary (paste probe_*.json "streams")
## Pi capture (paste command outputs)
## KPI table
| KPI | Value |
|---|---|
| video rate (Hz) / gap p95 (ms) | |
| /map rate / gap p95 | |
| /odom rate / gap p95 | |
| /scan rate / gap p95 | |
| get_throttled | |
| WiFi signal (dBm) | |
## Verdict table
| RC# | Verdict (confirmed / denied / not tested) | Evidence |
|---|---|---|
| RC1..RC7 | | |
```

After Phase 1 lands, re-run the exact same procedure and diff the KPI tables.
