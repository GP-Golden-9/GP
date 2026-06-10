#!/usr/bin/env python3
"""Robot 2 (Beta) launch — bridge + odometry + goto + gateway.

NOTE: the camera deliberately does NOT live here. camera_pub.py has no ROS
dependency and runs as its own systemd unit (gp-camera.service) so video
survives a ROS stack crash — and a camera fault can't take down control.

    ros2 launch robots/robot2/launch/robot2.launch.py [enable_rosbridge:=false]
"""

import os
import time
import uuid

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            IncludeLaunchDescription, SetEnvironmentVariable)
from launch.conditions import IfCondition
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
RUN_ID = time.strftime('%Y%m%dT%H%M', time.gmtime()) + '-' + uuid.uuid4().hex[:4]

ROS_DOMAIN_ID = '12'


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
        DeclareLaunchArgument('enable_rosbridge', default_value='true',
                              description='legacy NiceGUI fallback path'),

        SetEnvironmentVariable('ROS_DOMAIN_ID', ROS_DOMAIN_ID),
        SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1'),
        SetEnvironmentVariable('GP_RUN_ID', RUN_ID),

        _py('navigation/robot2_bridge.py'),
        _py('navigation/robot2_odom.py'),
        _py('navigation/robot2_goto.py'),
        _py('gateway/gateway_node.py', '--config',
            os.path.join(REPO, 'config', 'robot2.yaml')),

        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(rosbridge_launch),
            condition=IfCondition(enable_rosbridge),
        ),
    ])
