#!/bin/bash
# Install GP systemd units on a robot Pi.
#
#   ./install_systemd.sh robot1            # repo at /home/pi/GP (default)
#   ./install_systemd.sh robot2 /opt/GP    # repo elsewhere
#
# Also installs the udev serial rules and reloads them.
set -euo pipefail

ROBOT="${1:?usage: install_systemd.sh robot1|robot2 [repo_dir]}"
GP_DIR="${2:-/home/pi/GP}"
HERE="$(cd "$(dirname "$0")" && pwd)"

[ -d "$HERE/$ROBOT" ] || { echo "unknown robot '$ROBOT'"; exit 1; }

echo "Installing udev serial rules…"
sudo cp "$HERE/99-gp-serial.rules" /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

echo "Installing units for $ROBOT (repo: $GP_DIR)…"
for unit in "$HERE/$ROBOT"/*.service; do
    name="$(basename "$unit")"
    # Rewrite the default repo path if this checkout lives elsewhere
    sed "s|/home/pi/GP|$GP_DIR|g" "$unit" | sudo tee "/etc/systemd/system/$name" >/dev/null
    echo "  installed $name"
done

sudo systemctl daemon-reload
for unit in "$HERE/$ROBOT"/*.service; do
    sudo systemctl enable "$(basename "$unit")"
done

cat <<EOF

Done. Control with:
  sudo systemctl start  gp-${ROBOT}.service     # full stack (runs preflight first)
  sudo systemctl status gp-preflight gp-${ROBOT} $( [ "$ROBOT" = robot2 ] && echo gp-camera )
  journalctl -u 'gp-*' -f                        # live logs
Rollback to tmux: sudo systemctl disable --now 'gp-*' && ./rasp_cmd/${ROBOT}.sh
EOF
