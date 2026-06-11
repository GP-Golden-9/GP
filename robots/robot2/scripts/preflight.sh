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

# 4. Power health (Pi 3B+ is the brown-out-prone one — block on live undervoltage)
# Boot inrush (USB enumeration + WiFi radio) can trip the undervoltage bit
# for an instant right when this service runs; sample up to 3x over 10 s
# and block only if the sag PERSISTS. Field case 2026-06-11: capacitors
# fixed the rail, but preflight kept failing on the boot blip.
mkdir -p "$HOME/gp_logs"
for attempt in 1 2 3; do
    THROTTLED=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
    echo "$(date '+%F %T') preflight try$attempt ${THROTTLED:-n/a}" >> "$HOME/gp_logs/throttled.log"
    case "${THROTTLED:-}" in
        *1|*3|*5|*7|*9|*b|*d|*f) [ "$attempt" -lt 3 ] && { say "⚠ undervoltage flag (try $attempt/3) — settling…"; sleep 5; } ;;
        *) break ;;
    esac
done
case "${THROTTLED:-}" in
    *1|*3|*5|*7|*9|*b|*d|*f) bad "UNDERVOLTAGE PERSISTS (get_throttled=${THROTTLED}) — fix power before driving" ;;
    "")                      say "⚠ vcgencmd unavailable (not a Pi?)" ;;
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

# 6. Load average sanity (Pi 3B+: refuse to start into an overloaded system)
LOAD1=$(cut -d' ' -f1 /proc/loadavg)
awk -v l="$LOAD1" 'BEGIN {exit !(l < 3.0)}' && ok "load ${LOAD1}" || bad "load ${LOAD1} ≥ 3.0 — investigate before launch"

[ $FAIL -eq 0 ] && say "PREFLIGHT PASS" || say "PREFLIGHT FAIL"
exit $FAIL
