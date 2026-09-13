# Launch LIMO (Ackermann) on the SKKU H-Mobility race track world instead
# of the plain empty_world.model. Same server/client setup as
# ackermann_gazebo.launch.py (xvfb-run for gzserver, no eol_gui plugin for
# gzclient, delayed spawn) - only the world file and GAZEBO_MODEL_PATH
# (needed so Gazebo can resolve "model://race_track/...") differ.

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.actions import TimerAction
from launch.substitutions import LaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch_ros.actions import Node


def generate_launch_description():

    package_name = 'limo_car'
    world_file_path = 'worlds/track_world.model'
    rviz_path = 'rviz/gazebo.rviz'
    models_path = 'models'

    pkg_path = os.path.join(get_package_share_directory(package_name))
    world_path = os.path.join(pkg_path, world_file_path)
    default_rviz_config_path = os.path.join(pkg_path, rviz_path)
    gazebo_model_path = os.path.join(pkg_path, models_path)

    env = os.environ.copy()
    # Gazebo only falls back to its compiled-in default model path
    # (/usr/share/gazebo-11/models, where "ground_plane"/"sun" live) when
    # GAZEBO_MODEL_PATH is completely unset. Since we set it ourselves for
    # our own models dir, that fallback never kicks in unless we add the
    # system path back in explicitly.
    system_gazebo_models = '/usr/share/gazebo-11/models'
    env['GAZEBO_MODEL_PATH'] = os.pathsep.join(filter(None, [
        gazebo_model_path, system_gazebo_models, env.get('GAZEBO_MODEL_PATH', '')
    ]))
    # gzserver checks models.gazebosim.org on startup ("Getting models
    # from... may take a few seconds") even though our world only needs the
    # local race_track model. That check hangs for a long time in this
    # environment, so point it at localhost to fail fast instead.
    env['GAZEBO_MODEL_DATABASE_URI'] = 'http://127.0.0.1:9'

    rviz_arg = DeclareLaunchArgument(name='rvizconfig', default_value=str(default_rviz_config_path),
                                     description='Absolute path to rviz config file')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', LaunchConfiguration('rvizconfig')],
    )

    # Startpose auf der "Start"-Linie, visuell in Gazebo bestätigt (per
    # /tf odom->base_footprint abgelesen und hier übernommen).
    spawn_x_val = '-0.5137'
    spawn_y_val = '-3.2524'
    spawn_z_val = '0.05'
    spawn_yaw_val = '0.0066'

    mbot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory(package_name), 'launch', 'ackermann.launch.py'
        )]), launch_arguments={'use_sim_time': 'true', 'world': world_path}.items()
    )

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

    gazebo_client = ExecuteProcess(
        cmd=['gzclient'],
        output='screen',
        additional_env=env,
    )

    spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-topic', 'robot_description',
                                   '-entity', 'mbot',
                                   '-x', spawn_x_val,
                                   '-y', spawn_y_val,
                                   '-z', spawn_z_val,
                                   '-Y', spawn_yaw_val],
                        output='screen')

    delayed_spawn_entity = TimerAction(period=5.0, actions=[spawn_entity])

    return LaunchDescription([
        mbot,
        gazebo_server,
        gazebo_client,
        delayed_spawn_entity,
        rviz_arg,
        rviz_node
    ])
