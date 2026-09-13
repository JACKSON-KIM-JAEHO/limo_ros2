# Autor: Zhui Li
# E-Mail: lz554113510@gmail.com
# Company: Institut für Intermodale Transport- und Logistiksysteme in Technische Universität Braunschweig
# Description: Diese py-Datei basiert auf Regeln und definiert Funktionen durch python,
# um den Launch der Simulation in Gazebo zu ermöglichen. Danach mit der Simulation in Gazebo kann man die weitere
# Forschung arbeiten. Diese Launch-Datei dient zu Ackermann-Type.

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

    # definiert Path für Modell
    package_name = 'limo_car'
    world_file_path = 'worlds/empty_world.model'
    rviz_path = 'rviz/gazebo.rviz'

    pkg_path = os.path.join(get_package_share_directory(package_name))
    world_path = os.path.join(pkg_path, world_file_path)
    default_rviz_config_path = os.path.join(pkg_path, rviz_path)

    rviz_arg = DeclareLaunchArgument(name='rvizconfig', default_value=str(default_rviz_config_path),
                                     description='Absolute path to rviz config file')
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', LaunchConfiguration('rvizconfig')],
    )

    # Position dafür, wo die Modelle herstellt werden
    spawn_x_val = '0.0'
    spawn_y_val = '0.0'
    spawn_z_val = '0.0'
    spawn_yaw_val = '0.0'

    mbot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([os.path.join(
            get_package_share_directory(package_name),'launch', 'ackermann.launch.py'
        )]), launch_arguments={'use_sim_time': 'true', 'world': world_path}.items()
    )

    # gzserver läuft unter xvfb-run (virtuelles X-Display), da die depth
    # camera sonst mit einer rendering::Scene-Assertion abstürzt, sobald ein
    # Modell mit Kamera-Sensor gespawnt wird - unabhängig von Session
    # (X11/Wayland) oder Treiber (Software/NVIDIA). gzclient läuft weiterhin
    # auf dem echten Display (unten), nur der Server braucht das virtuelle.
    gazebo_server = ExecuteProcess(
        cmd=[
            'xvfb-run', '-a',
            'gzserver', world_path,
            '-slibgazebo_ros_init.so',
            '-slibgazebo_ros_factory.so',
            '-slibgazebo_ros_force_system.so',
        ],
        output='screen',
    )

    # gazebo_ros/launch/gzclient.launch.py hängt fest "--gui-client-plugin=
    # libgazebo_ros_eol_gui.so" an (End-of-Life-Hinweisfenster für Gazebo
    # Classic). Dieses Plugin stürzt bei uns mit einer Camera-Assertion ab,
    # bevor irgendein Rendering stattfindet. Deshalb starten wir gzclient
    # hier direkt, ohne dieses Plugin.
    gazebo_client = ExecuteProcess(
        cmd=['gzclient'],
        output='screen',
    )

    # laufen ein leere node aus den gazebo_ros package
    spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-topic', 'robot_description',
                                   '-entity', 'mbot',
                                   '-x', spawn_x_val,
                                   '-y', spawn_y_val,
                                   '-z', spawn_z_val,
                                   '-Y', spawn_yaw_val],
                        output='screen')


    # gzclient braucht Zeit, um seine eigene Kamera zu initialisieren, bevor
    # es eine "Modell einfügen"-Nachricht von gzserver verarbeiten kann.
    # Ohne Verzögerung stürzt gzclient mit einer Camera-Assertion ab.
    delayed_spawn_entity = TimerAction(period=5.0, actions=[spawn_entity])

    return LaunchDescription([
        mbot,
        gazebo_server,
        gazebo_client,
        delayed_spawn_entity,
        rviz_arg,
        rviz_node
    ])