# Robot deployment (Phase 2)

One-time setup per Pi (repo assumed at `/home/pi/GP`):

```bash
cd ~/GP
pip3 install -e common            # gpcore (msgpack, pyyaml pulled in)
pip3 install pyzmq                # if not already present
./systemd/install_systemd.sh robot1     # or robot2
sudo systemctl start gp-robot1          # preflight gates the start
```

What runs where:

| | robot1 (Pi 4) | robot2 (Pi 3B+) |
|---|---|---|
| launch file | `robots/robot1/launch/robot1.launch.py` | `robots/robot2/launch/robot2.launch.py` |
| nodes | rplidar, slam_toolbox, robot1_bridge, simple_explorer, scan_watchdog, gateway | robot2_bridge, robot2_odom, robot2_goto, gateway |
| extra unit | — | `gp-camera.service` (camera_pub.py, ROS-free) |
| DDS | domain 11, localhost-only | domain 12, localhost-only |
| rosbridge | `enable_rosbridge:=true` (default, legacy dashboard) | same |

Network contract (the ONLY WiFi traffic): ZMQ 5556 telemetry / 5557 map /
5558 commands / 5559 health / 5560 video (+5555 legacy video during
migration), per robot. See `docs/protocol.md`.

Fallback to the old way at any time:

```bash
sudo systemctl disable --now 'gp-*'
./rasp_cmd/robot1.sh        # tmux stack, still maintained
```
