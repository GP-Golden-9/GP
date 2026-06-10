#!/bin/bash
# ═══════════════════════════════════════════════
# ROBOT 2 (Beta) — Camera + Odometry + GoTo
# ═══════════════════════════════════════════════
# Phase-1 hardening:
#   * ROS_DOMAIN_ID=12   → robot2 is its own DDS island (robot1 uses 11).
#   * camera now runs tcp_rasp_zmq.py (q35, 30 fps, SNDHWM=1). The old
#     tcp_rasp.py (q80, unbounded ZMQ queue) was the root cause of the
#     multi-second video lag / drops on the Pi 3B+.
#   * /dev/mega udev symlink for the Arduino (systemd/99-gp-serial.rules).
#   * every pane wrapped in a restart loop; undervoltage logger pane.

SESSION="robot2"
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ENV="export ROS_DOMAIN_ID=12; source /opt/ros/humble/setup.bash"

mkdir -p "$HOME/gp_logs"

if [ ! -e /dev/mega ]; then
    echo "⚠️  /dev/mega missing — udev rules not installed!"
    echo "    sudo cp $DIR/../systemd/99-gp-serial.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger"
    echo "    Falling back to raw ttyUSB names."
    sudo chmod 666 /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 2>/dev/null
fi

# Kill any existing session
tmux kill-session -t $SESSION 2>/dev/null

# RUN <name> <command...>  — restart loop so a crash never ends the pane
RUN() { local n=$1; shift; echo "while true; do $*; echo '[gp] $n exited — restart in 2s'; sleep 2; done"; }

# 1. MOTOR BRIDGE (Arduino + IMU)
tmux new-session -d -s $SESSION -n "Motors" \
    "$ENV; cd $DIR/../navigation && $(RUN bridge 'python3 robot2_bridge.py')"

# 2. ROS BRIDGE (dashboard websocket)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; $(RUN rosbridge 'ros2 launch rosbridge_server rosbridge_websocket_launch.xml')" C-m

# 3. CAMERA STREAM (ZMQ, tuned: q35 / 30 fps / SNDHWM=1)
tmux split-window -h -t $SESSION
tmux send-keys -t $SESSION "cd $DIR/../classification && $(RUN camera 'python3 tcp_rasp_zmq.py')" C-m

# 4. ODOMETRY (encoders + IMU → /odom)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; cd $DIR/../navigation && $(RUN odom 'python3 robot2_odom.py')" C-m

# 5. GOTO NAVIGATOR (/goal_pose → drives to it)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "$ENV; cd $DIR/../navigation && $(RUN goto 'python3 robot2_goto.py')" C-m

# 6. HEALTH LOGGER (undervoltage / throttling, 1/min)
tmux split-window -v -t $SESSION
tmux send-keys -t $SESSION "while true; do echo \"\$(date '+%F %T') \$(vcgencmd get_throttled)\" >> $HOME/gp_logs/throttled.log; sleep 60; done" C-m

tmux select-layout -t $SESSION tiled

echo "✅ Robot 2 (Beta) started — DDS domain 12, camera = tcp_rasp_zmq.py"
echo "   Panes: bridge | rosbridge | camera | odom | goto | health"
echo "   Logs:  tmux attach -t $SESSION    Throttle: tail ~/gp_logs/throttled.log"
