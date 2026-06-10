import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    """
    SLAM-only (No RViz, No LiDAR)
    - Assumes LiDAR is already running
    - No RViz (saves resources on RPi)
    """
    cwd = os.path.dirname(os.path.abspath(__file__))
    slam_params_file = os.path.join(cwd, 'mapper.yaml')

    ld = LaunchDescription()

    # odom -> base_link comes from rf2o laser odometry (robot1.launch.py).
    # The static identity TF that used to live here would FIGHT rf2o's
    # dynamic transform — never publish both.

    # TF: base_link -> laser. The A1's 0 deg axis faces the chassis REAR
    # (measured 2026-06-11: map arrow pointed backward) -> yaw = pi so
    # base_link +x is the robot's true forward. Keep in sync with
    # footprint.laser_yaw_rad in config/robot1.yaml.
    ld.add_action(Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        arguments=['--x', '0', '--y', '0', '--z', '0',
                   '--roll', '0', '--pitch', '0', '--yaw', '3.14159265',
                   '--frame-id', 'base_link', '--child-frame-id', 'laser'],
        output='log',
        respawn=True,
        respawn_delay=2.0
    ))

    # SLAM Toolbox (no RViz!) — respawn: a SLAM crash must not end mapping
    # for the whole run (the map restarts fresh, same as RESET MAP)
    ld.add_action(Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_params_file],
        respawn=True,
        respawn_delay=2.0
    ))

    return ld
