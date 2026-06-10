#!/usr/bin/env python3
"""Robot 1 (Alpha) launch — LiDAR + SLAM + bridge + explorer + gateway.

Replaces the tmux half of rasp_cmd/robot1.sh with supervised launch:
  * ROS_LOCALHOST_ONLY=1  → DDS never crosses WiFi (gateway is the only door)
  * every process respawns 2 s after a crash
  * one GP_RUN_ID minted here and inherited by every node → correlated logs

    ros2 launch robots/robot1/launch/robot1.launch.py [enable_rosbridge:=false]
"""

import os
import time
import uuid

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            IncludeLaunchDescription, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.launch_description_sources import (AnyLaunchDescriptionSource,
                                               PythonLaunchDescriptionSource)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
RUN_ID = time.strftime('%Y%m%dT%H%M', time.gmtime()) + '-' + uuid.uuid4().hex[:4]

ROS_DOMAIN_ID = '11'
LIDAR_PORT = '/dev/rplidar'


def _py(script_rel: str, *args: str) -> ExecuteProcess:
    return ExecuteProcess(
        cmd=['python3', os.path.join(REPO, script_rel), *args],
        output='screen',
        respawn=True,
        respawn_delay=2.0,
    )


def generate_launch_description():
    enable_rosbridge = LaunchConfiguration('enable_rosbridge')

    try:
        from ament_index_python.packages import get_package_share_directory
        rosbridge_launch = os.path.join(
            get_package_share_directory('rosbridge_server'),
            'launch', 'rosbridge_websocket_launch.xml')
    except Exception:                      # allows syntax-checking off-robot
        rosbridge_launch = '/dev/null'

    return LaunchDescription([
        DeclareLaunchArgument('enable_rosbridge', default_value='false',
                              description='optional rosbridge for debugging '
                                          '(the console uses the ZMQ gateway)'),

        SetEnvironmentVariable('ROS_DOMAIN_ID', ROS_DOMAIN_ID),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('GP_RUN_ID', RUN_ID),

        # LiDAR driver — run DIRECTLY (not via rplidar_a1_launch.py) so OUR
        # respawn applies. Field failure 2026-06-11: the included launch ran
        # the driver without respawn; one abort at boot (-6 before the serial
        # port settled) left /scan dead until a manual service restart, and
        # the scan_watchdog's pkill rung assumes respawn exists.
        Node(
            package='rplidar_ros',
            executable='rplidar_node',
            name='rplidar_node',
            output='screen',
            respawn=True,
            respawn_delay=3.0,             # USB needs a beat after an abort
            parameters=[{
                'serial_port': LIDAR_PORT,    # A1 defaults from
                'serial_baudrate': 115200,    # rplidar_a1_launch.py
                'frame_id': 'laser',
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': 'Sensitivity',
            }],
        ),

        # SLAM (existing launch file in mapping/)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(REPO, 'mapping', 'slam_only.py')),
        ),

        _py('navigation/robot1_bridge.py'),
        _py('navigation/simple_explorer.py'),
        _py('robots/robot1/nodes/scan_watchdog.py'),
        _py('gateway/gateway_node.py', '--config',
            os.path.join(REPO, 'config', 'robot1.yaml')),

        # Legacy dashboard path — drop with enable_rosbridge:=false after
        # the Qt console passes its parity gate.
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(rosbridge_launch),
            condition=IfCondition(enable_rosbridge),
        ),
    ])
