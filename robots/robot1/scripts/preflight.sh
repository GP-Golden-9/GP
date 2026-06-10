#!/bin/bash
# Robot 1 preflight — hard gate before gp-robot1.service starts.
# Exits non-zero on any blocking failure; systemd dependency stops the launch.
set -u
GP_DIR="${GP_DIR:-/home/pi/GP}"
FAIL=0

say()  { echo "[preflight] $*"; }
ok()   { say "✅ $*"; }
bad()  { say "❌ $*"; FAIL=1; }

# 1. Serial identities (udev rules installed and devices present)
[ -e /dev/rplidar ] && ok "/dev/rplidar present" || bad "/dev/rplidar missing (udev rules? cable?)"
[ -e /dev/mega ]    && ok "/dev/mega present"    || bad "/dev/mega missing (udev rules? cable?)"

# 2. Disk space (maps + logs need room)
FREE_MB=$(df -Pm / | awk 'NR==2 {print $4}')
if [ "${FREE_MB:-0}" -ge 500 ]; then ok "disk ${FREE_MB} MB free"; else bad "disk only ${FREE_MB} MB free (<500)"; fi

# 3. Power health — record now; bit 0 set = undervoltage RIGHT NOW (block)
THROTTLED=$(vcgencmd get_throttled 2>/dev/null | cut -d= -f2)
mkdir -p "$HOME/gp_logs"
echo "$(date '+%F %T') preflight ${THROTTLED:-n/a}" >> "$HOME/gp_logs/throttled.log"
case "${THROTTLED:-}" in
    *1|*3|*5|*7|*9|*b|*d|*f) bad "UNDERVOLTAGE NOW (get_throttled=${THROTTLED}) — fix power before driving" ;;
    "")                      say "⚠ vcgencmd unavailable (not a Pi?)" ;;
    *)                       ok "power flags ${THROTTLED}" ;;
esac

# 4. ROS 2 + python deps
# ROS's setup.bash trips `set -u` (references unbound vars) — relax around it
set +u
source /opt/ros/humble/setup.bash 2>/dev/null && ok "ROS 2 humble sourced" || bad "cannot source ROS 2 humble"
set -u
python3 - <<EOF && ok "python deps + config valid" || bad "python deps/config check failed"
import sys
sys.path.insert(0, "$GP_DIR/common")
import zmq, msgpack, yaml                      # noqa
from gpcore.config import load_robot_config
load_robot_config("$GP_DIR/config/robot1.yaml")
EOF

# 5. Time sync (best effort — wall clocks correlate logs across machines)
if command -v chronyc >/dev/null 2>&1; then
    chronyc waitsync 2 0.5 >/dev/null 2>&1 && ok "clock synced" || say "⚠ clock not synced (continuing)"
fi

[ $FAIL -eq 0 ] && say "PREFLIGHT PASS" || say "PREFLIGHT FAIL"
exit $FAIL
