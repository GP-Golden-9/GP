#!/bin/bash
# ═══════════════════════════════════════════════
# ROBOT 1 (Alpha) — LiDAR + SLAM + Explorer
# ═══════════════════════════════════════════════
# Phase-1 hardening:
#   * ROS_DOMAIN_ID=11   → robot1 is its own DDS island (robot2 uses 12);
#     without this, both robots share domain 0 over WiFi and robot1's
#     explorer /cmd_vel can drive robot2.
#   * /dev/rplidar, /dev/mega udev symlinks → no more LiDAR/Arduino port swap
#     (install systemd/99-gp-serial.rules first — script warns if missing).
#   * every pane wrapped in a restart loop → a crashed node comes back in 2 s.
#   * undervoltage logger → ~/gp_logs/throttled.log (0x0 = healthy).

SESSION="robot1"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ENV="export ROS_DOMAIN_ID=11; source /opt/ros/humble/setup.bash"

mkdir -p "$HOME/gp_logs"

# Stable serial names (from systemd/99-gp-serial.rules)
LIDAR_PORT="/dev/rplidar"
if [ ! -e "$LIDAR_PORT" ]; then
    echo "⚠️  $LIDAR_PORT missing — udev rules not installed!"
    echo "    sudo cp $DIR/../systemd/99-gp-serial.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger"
    echo "    Falling back to /dev/ttyUSB1 (UNSAFE: may hit the Arduino if enumeration flipped)"
    LIDAR_PORT="/dev/ttyUSB1"
    sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 2>/dev/null
fi

# Kill any existing session
tmux kill-session -t $SESSION 2>/dev/null

# RUN <name> <command...>  — restart loop so a crash never ends the pane
RUN() { local n=$1; shift; echo "while true; do $*; echo '[gp] $n exited — restart in 2s'; sleep 2; done"; }

# 1. LiDAR
tmux new-session -d -s $SESSION -n "Sensors" \
    "$ENV; $(RUN lidar "ros2 launch rplidar_ros rplidar_a1_launch.py serial_port:=$LIDAR_PORT")"

# 2. SLAM (Mapping)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; cd $DIR/../mapping && $(RUN slam 'ros2 launch slam_only.py')" C-m

# 3. MOTOR BRIDGE
tmux split-window -h -t $SESSION
tmux send-keys -t $SESSION "$ENV; cd $DIR/../navigation && $(RUN bridge 'python3 robot1_bridge.py')" C-m

# 4. ROS BRIDGE (dashboard websocket)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; $(RUN rosbridge 'ros2 launch rosbridge_server rosbridge_websocket_launch.xml')" C-m

# 5. EXPLORER (autonomous)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; cd $DIR/../navigation && $(RUN explorer 'python3 simple_explorer.py')" C-m

# 6. HEALTH LOGGER (undervoltage / throttling, 1/min)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "while true; do echo \"\$(date '+%F %T') \$(vcgencmd get_throttled)\" >> $HOME/gp_logs/throttled.log; sleep 60; done" C-m

tmux select-layout -t $SESSION tiled

echo "✅ Robot 1 (Alpha) started — DDS domain 11, lidar on $LIDAR_PORT"
echo "   Panes: lidar | slam | bridge | rosbridge | explorer | health"
echo "   Logs:  tmux attach -t $SESSION    Throttle: tail ~/gp_logs/throttled.log"
