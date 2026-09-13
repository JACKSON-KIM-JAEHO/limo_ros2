"""Single-window Qt dashboard for the LIMO sim.

Combines traffic light color control and robot steering (equivalent to
`ros2 run rqt_robot_steering rqt_robot_steering`, publishing
geometry_msgs/Twist on /cmd_vel) into one window, launched alongside
the simulator.

Traffic light color is set by publishing std_msgs/String ("red" |
"yellow" | "green" | "off") on /traffic_light/color, read by the
traffic_light_plugin Gazebo model plugin (limo_plugin package). We
originally tried the standard gazebo_msgs/SetLightProperties service,
but that only changes a <light> (illumination) - Gazebo Classic has no
public API to change a spawned model's <visual> material, which is
what actually makes a lens sphere look colored. See
limo_plugin/src/traffic_light_plugin.cpp for why a custom plugin is
needed here.

To add a new panel later: write a `_build_..._group(self) -> QGroupBox`
method and add it to the QVBoxLayout in `_build_ui`.
"""

import sys
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QSlider, QLabel,
)

LIGHT_COLORS = ['red', 'yellow', 'green']

MAX_LINEAR = 1.0    # m/s
MAX_ANGULAR = 3.0   # rad/s
PUBLISH_HZ = 20.0


class DashboardNode(Node):
    """Just the ROS I/O side (publishers). No Qt here."""

    def __init__(self):
        super().__init__('limo_dashboard')
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.light_pub = self.create_publisher(String, '/traffic_light/color', 10)

    def publish_cmd_vel(self, linear, angular):
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.cmd_vel_pub.publish(msg)

    def set_light(self, color):
        self.light_pub.publish(String(data=color))


class DashboardWindow(QMainWindow):

    def __init__(self, ros_node: DashboardNode):
        super().__init__()
        self.ros_node = ros_node
        self.setWindowTitle('LIMO Dashboard')
        self._build_ui()

        # rqt_robot_steering-style: keep publishing the current slider
        # value at a fixed rate, not just on change, so the robot keeps
        # moving while a slider is held away from zero.
        self._linear = 0.0
        self._angular = 0.0
        self._cmd_timer = QTimer(self)
        self._cmd_timer.timeout.connect(self._publish_cmd_vel)
        self._cmd_timer.start(int(1000 / PUBLISH_HZ))

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self._build_traffic_light_group())
        layout.addWidget(self._build_steering_group())
        # Add future panels here, e.g.:
        # layout.addWidget(self._build_mission_status_group())
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_traffic_light_group(self) -> QGroupBox:
        group = QGroupBox('Traffic Light')
        row = QHBoxLayout()
        colors = {'red': '#d62728', 'yellow': '#e0b400', 'green': '#2ca02c'}
        for color, hexcode in colors.items():
            btn = QPushButton(color.capitalize())
            btn.setStyleSheet(
                f'background-color: {hexcode}; color: white; font-weight: bold; padding: 8px;'
            )
            btn.clicked.connect(lambda checked, c=color: self._set_traffic_light(c))
            row.addWidget(btn)
        group.setLayout(row)
        return group

    def _set_traffic_light(self, active_color):
        self.ros_node.set_light(active_color)

    def _build_steering_group(self) -> QGroupBox:
        group = QGroupBox('Robot Steering (cmd_vel)')
        layout = QVBoxLayout()

        layout.addWidget(QLabel('Linear (m/s)'))
        self.linear_slider = QSlider(Qt.Horizontal)
        self.linear_slider.setRange(-100, 100)
        self.linear_slider.setValue(0)
        self.linear_slider.valueChanged.connect(self._on_linear_changed)
        layout.addWidget(self.linear_slider)
        self.linear_label = QLabel('0.00 m/s')
        layout.addWidget(self.linear_label)

        layout.addWidget(QLabel('Angular (rad/s)'))
        self.angular_slider = QSlider(Qt.Horizontal)
        self.angular_slider.setRange(-100, 100)
        self.angular_slider.setValue(0)
        self.angular_slider.valueChanged.connect(self._on_angular_changed)
        layout.addWidget(self.angular_slider)
        self.angular_label = QLabel('0.00 rad/s')
        layout.addWidget(self.angular_label)

        stop_btn = QPushButton('STOP')
        stop_btn.setStyleSheet('background-color: #d62728; color: white; font-weight: bold; padding: 10px;')
        stop_btn.clicked.connect(self._stop)
        layout.addWidget(stop_btn)

        group.setLayout(layout)
        return group

    def _on_linear_changed(self, value):
        self._linear = (value / 100.0) * MAX_LINEAR
        self.linear_label.setText(f'{self._linear:.2f} m/s')

    def _on_angular_changed(self, value):
        # Slider right (+) should turn the robot right, which is a
        # negative angular.z in the standard ROS convention (+z is
        # counter-clockwise/left) - negate so slider direction matches
        # turn direction.
        self._angular = -(value / 100.0) * MAX_ANGULAR
        self.angular_label.setText(f'{self._angular:.2f} rad/s')

    def _stop(self):
        self.linear_slider.setValue(0)
        self.angular_slider.setValue(0)
        self._linear = 0.0
        self._angular = 0.0
        self.ros_node.publish_cmd_vel(0.0, 0.0)

    def _publish_cmd_vel(self):
        self.ros_node.publish_cmd_vel(self._linear, self._angular)

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)


def main(args=None):
    rclpy.init(args=args)
    ros_node = DashboardNode()

    spin_thread = threading.Thread(target=rclpy.spin, args=(ros_node,), daemon=True)
    spin_thread.start()

    app = QApplication(sys.argv)
    window = DashboardWindow(ros_node)
    window.resize(360, 420)
    window.show()
    exit_code = app.exec_()

    rclpy.shutdown()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
