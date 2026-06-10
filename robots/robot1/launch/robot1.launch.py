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
        rplidar_launch = os.path.join(get_package_share_directory('rplidar_ros'),
                                      'launch', 'rplidar_a1_launch.py')
        rosbridge_launch = os.path.join(
            get_package_share_directory('rosbridge_server'),
            'launch', 'rosbridge_websocket_launch.xml')
    except Exception:                      # allows syntax-checking off-robot
        rplidar_launch = rosbridge_launch = '/dev/null'

    return LaunchDescription([
        DeclareLaunchArgument('enable_rosbridge', default_value='true',
                              description='legacy NiceGUI fallback path'),

        SetEnvironmentVariable('ROS_DOMAIN_ID', ROS_DOMAIN_ID),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('GP_RUN_ID', RUN_ID),

        # LiDAR driver (restart-on-stall handled by scan_watchdog + respawn)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rplidar_launch),
            launch_arguments={'serial_port': LIDAR_PORT}.items(),
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
