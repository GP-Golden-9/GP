#!/bin/bash
# One-shot deploy + verify, run ON a robot Pi.
#
#   bash tools/deploy_and_verify.sh [robot1|robot2]
#
# Does the full software deploy in the right order:
#   1. git pull (tolerant of robot1's internet-less WiFi)
#   2. refresh the systemd units  (install_systemd.sh re-copies them into
#      /etc/systemd/system with the path/user substitution + daemon-reload)
#      — a plain `git pull` does NOT update the installed unit, which is why
#      the network-online startup fix needs this step to take effect.
#   3. restart the stack
#   4. print the boot critical-chain so you can SEE network-online is gone
#      and the stack starts in seconds, not ~3 minutes.
#
# Firmware (Mega ultrasonics / ESP32 servo) is flashed separately — this
# script only handles the Pi software.
set -uo pipefail

GP_DIR="${GP_DIR:-$HOME/GP}"
ROBOT="${1:-$(hostname | grep -oE 'robot[12]' || true)}"
if [ -z "$ROBOT" ]; then
    echo "usage: bash tools/deploy_and_verify.sh robot1|robot2" >&2
    exit 1
fi
echo "=== deploying $ROBOT from $GP_DIR ==="

cd "$GP_DIR" || { echo "no repo at $GP_DIR"; exit 1; }

echo "--- 1/4 git pull ---"
git pull --ff-only || echo "  (pull failed — offline? continuing with current checkout)"

echo "--- 2/4 refresh systemd units ---"
sudo bash "$GP_DIR/systemd/install_systemd.sh" "$ROBOT" "$GP_DIR"

echo "--- 3/4 restart stack ---"
sudo systemctl restart "gp-${ROBOT}.service"
sleep 8
echo "  state: $(systemctl is-active "gp-${ROBOT}.service")"

echo "--- 4/4 verify boot timing (network-online must NOT appear) ---"
systemd-analyze critical-chain "gp-${ROBOT}.service" 2>/dev/null || \
    echo "  (critical-chain needs a fresh boot to be meaningful; check after a reboot)"
echo "--- recent stack log ---"
journalctl -u "gp-${ROBOT}.service" --since '-20 seconds' --no-pager | tail -15

cat <<EOF

Done. To confirm the 3-minute delay is gone, REBOOT the Pi and time it:
  sudo reboot
  # after it comes back:
  systemd-analyze critical-chain gp-${ROBOT}.service   # no network-online.target
  systemd-analyze blame | head                          # wait-online no longer gates us
EOF
