#!/bin/bash
# Robot 2 preflight — hard gate before gp-robot2.service starts.
set -u
GP_DIR="${GP_DIR:-/home/pi/GP}"
FAIL=0

say()  { echo "[preflight] $*"; }
ok()   { say "✅ $*"; }
bad()  { say "❌ $*"; FAIL=1; }

# 1. Arduino present under its stable name
[ -e /dev/mega ] && ok "/dev/mega present" || bad "/dev/mega missing (udev rules? cable?)"

# 2. Camera device
[ -e /dev/video0 ] && ok "/dev/video0 present" || bad "/dev/video0 missing (USB camera unplugged?)"

# 3. Disk space
FREE_MB=$(df -Pm / | awk 'NR==2 {print $4}')
if [ "${FREE_MB:-0}" -ge 300 ]; then ok "disk ${FREE_MB} MB free"; else bad "disk only ${FREE_MB} MB free (<300)"; fi

# 4. Power health — WARN ONLY (operator override 2026-06-15). Undervoltage
# no longer BLOCKS the stack: log it so the issue stays visible, but let the
# robot run. NOTE: running under real undervoltage risks brown-out resets /
# SD corruption, especially under motor load — fix the rail when you can.
mkdir -p "$HOME/gp_logs"
THROTTLED=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
echo "$(date '+%F %T') preflight ${THROTTLED:-n/a}" >> "$HOME/gp_logs/throttled.log"
case "${THROTTLED:-}" in
    *1|*3|*5|*7|*9|*b|*d|*f) say "WARN: undervoltage (get_throttled=${THROTTLED}) — continuing anyway (override)" ;;
    "")                      say "vcgencmd unavailable (not a Pi?)" ;;
    *)                       ok "power flags ${THROTTLED}" ;;
esac

# 5. ROS 2 + python deps + config
# ROS's setup.bash trips `set -u` (references unbound vars) — relax around it
set +u
source /opt/ros/humble/setup.bash 2>/dev/null && ok "ROS 2 humble sourced" || bad "cannot source ROS 2 humble"
set -u
python3 - <<EOF && ok "python deps + config valid" || bad "python deps/config check failed"
import sys
sys.path.insert(0, "$GP_DIR/common")
import cv2, zmq, msgpack, yaml                 # noqa
from gpcore.config import load_robot_config
load_robot_config("$GP_DIR/config/robot2.yaml")
EOF

# 6. Load average — WARN ONLY (operator override 2026-06-15). The Pi 3B+
# legitimately runs the full ROS stack + camera near load ~4, and restart
# churn spikes it higher, so this no longer blocks — it just logs. The stack
# starts regardless ("keep running").
LOAD1=$(cut -d' ' -f1 /proc/loadavg)
awk -v l="$LOAD1" 'BEGIN {exit !(l < 3.0)}' && ok "load ${LOAD1}" \
    || say "WARN: load ${LOAD1} high — continuing anyway (override)"

[ $FAIL -eq 0 ] && say "PREFLIGHT PASS" || say "PREFLIGHT FAIL"
exit $FAIL
