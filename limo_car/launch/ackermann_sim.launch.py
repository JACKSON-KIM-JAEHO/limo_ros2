# Unified LIMO (Ackermann) simulation launch: pick the world with the
# `map` launch argument instead of having one launch file per world.
#
#   ros2 launch limo_car ackermann_sim.launch.py map:=straight_line
#   ros2 launch limo_car ackermann_sim.launch.py map:=track
#   ros2 launch limo_car ackermann_sim.launch.py map:=track_obstacles
#   ros2 launch limo_car ackermann_sim.launch.py map:=maze
#   ros2 launch limo_car ackermann_sim.launch.py map:=ramp
#   ros2 launch limo_car ackermann_sim.launch.py map:=room
#   ros2 launch limo_car ackermann_sim.launch.py map:=parking
#   ros2 launch limo_car ackermann_sim.launch.py map:=traffic_light
#   ros2 launch limo_car ackermann_sim.launch.py map:=integration
#   ros2 launch limo_car ackermann_sim.launch.py map:=empty
#
# Same gzserver/gzclient/spawn setup as ackermann_gazebo.launch.py /
# ackermann_track_gazebo.launch.py (xvfb-run for gzserver so the depth
# camera doesn't crash it, gzclient without the eol_gui plugin, delayed
# spawn). Only the world file, GAZEBO_MODEL_PATH and spawn pose change
# per map, so an OpaqueFunction picks those based on the `map` argument.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.actions import OpaqueFunction
from launch.actions import TimerAction
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node

# map name -> (world file relative to share/limo_car, spawn x, y, z, yaw)
MAPS = {
    'empty': ('worlds/empty_world.model', '0.0', '0.0', '0.0', '0.0'),
    'straight_line': ('worlds/straight_line_world.model', '-3.5', '0.0', '0.05', '0.0'),
    'track': ('worlds/track_world.model', '-0.5137', '-3.2524', '0.05', '0.0066'),
    'track_obstacles': ('worlds/track_world_obstacles.model', '-0.5137', '-3.2524', '0.05', '0.0066'),
    'maze': ('worlds/maze_world.model', '0.0', '0.0', '0.05', '0.0'),
    'ramp': ('worlds/ramp_world.model', '0.0', '0.0', '0.05', '0.0'),
    'room': ('worlds/room_world.model', '0.5', '1.5', '0.05', '0.0'),
    'parking': ('worlds/parking_world.model', '-0.5137', '-3.2524', '0.05', '0.0066'),
    'traffic_light': ('worlds/traffic_light_world.model', '-0.5137', '-3.2524', '0.05', '0.0066'),
    'integration': ('worlds/integration_world.model', '-0.5137', '-3.2524', '0.05', '0.0066'),
}


def launch_setup(context, *args, **kwargs):
    package_name = 'limo_car'
    pkg_path = get_package_share_directory(package_name)

    map_name = LaunchConfiguration('map').perform(context)
    if map_name not in MAPS:
        raise RuntimeError(
            f"Unknown map '{map_name}'. Valid options: {', '.join(MAPS.keys())}"
        )
    world_file_path, spawn_x, spawn_y, spawn_z, spawn_yaw = MAPS[map_name]

    world_path = os.path.join(pkg_path, world_file_path)
    default_rviz_config_path = os.path.join(pkg_path, 'rviz', 'gazebo.rviz')
    gazebo_model_path = os.path.join(pkg_path, 'models')

    env = os.environ.copy()
    # Gazebo only falls back to its compiled-in default model path
    # (/usr/share/gazebo-11/models, where "ground_plane"/"sun" live) when
    # GAZEBO_MODEL_PATH is completely unset. Since we set it ourselves for
    # our own models dir, that fallback never kicks in unless we add the
    # system path back in explicitly - otherwise model://ground_plane
    # fails to resolve and spawned robots fall through the floor forever.
    system_gazebo_models = '/usr/share/gazebo-11/models'
    env['GAZEBO_MODEL_PATH'] = os.pathsep.join(filter(None, [
        gazebo_model_path, system_gazebo_models, env.get('GAZEBO_MODEL_PATH', '')
    ]))
    # gzserver checks models.gazebosim.org on startup ("Getting models
    # from... may take a few seconds"), which hangs for a long time in
    # this environment even for worlds that only need local models.
    env['GAZEBO_MODEL_DATABASE_URI'] = 'http://127.0.0.1:9'

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', default_rviz_config_path],
    )

    dashboard_node = Node(
        package='limo_dashboard',
        executable='dashboard_node',
        name='limo_dashboard',
        output='screen',
    )

    mbot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(pkg_path, 'launch', 'ackermann.launch.py')]),
        launch_arguments={'use_sim_time': 'true', 'world': world_path}.items()
    )

    # gzserver läuft unter xvfb-run (virtuelles X-Display) - die depth
    # camera stürzt gzserver sonst mit einer rendering::Scene-Assertion
    # ab, unabhängig von Session (X11/Wayland) oder Treiber.
    gazebo_server = ExecuteProcess(
        cmd=[
            'xvfb-run', '-a',
            'gzserver', world_path,
            '-slibgazebo_ros_init.so',
            '-slibgazebo_ros_factory.so',
            '-slibgazebo_ros_force_system.so',
        ],
        output='screen',
        additional_env=env,
    )

    # gazebo_ros/launch/gzclient.launch.py hängt fest "--gui-client-plugin=
    # libgazebo_ros_eol_gui.so" an, was gzclient mit einer Camera-Assertion
    # abstürzen lässt. Deshalb gzclient hier direkt ohne dieses Plugin.
    gazebo_client = ExecuteProcess(
        cmd=['gzclient'],
        output='screen',
        additional_env=env,
    )

    spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-topic', 'robot_description',
                                   '-entity', 'mbot',
                                   '-x', spawn_x,
                                   '-y', spawn_y,
                                   '-z', spawn_z,
                                   '-Y', spawn_yaw],
                        output='screen')

    # gzclient braucht Zeit für seine eigene Kamera-Initialisierung, bevor
    # es eine "Modell einfügen"-Nachricht von gzserver verarbeiten kann.
    delayed_spawn_entity = TimerAction(period=5.0, actions=[spawn_entity])

    return [mbot, gazebo_server, gazebo_client, delayed_spawn_entity, rviz_node, dashboard_node]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'map', default_value='track',
            description=f"Which world to load: {', '.join(MAPS.keys())}"
        ),
        OpaqueFunction(function=launch_setup),
    ])
