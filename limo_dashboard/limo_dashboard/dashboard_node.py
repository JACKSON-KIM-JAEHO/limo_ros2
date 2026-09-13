"""Single-window Qt dashboard for the LIMO sim.

Combines traffic light color control and robot steering (a toggle-able
in-window equivalent of `ros2 run teleop_twist_keyboard
teleop_twist_keyboard`, publishing geometry_msgs/Twist on /cmd_vel)
into one window, launched alongside the simulator.

Traffic light color is set by publishing std_msgs/String ("red" |
"yellow" | "green" | "off") on /traffic_light/color, read by the
traffic_light_plugin Gazebo model plugin (limo_plugin package). We
originally tried the standard gazebo_msgs/SetLightProperties service,
but that only changes a <light> (illumination) - Gazebo Classic has no
public API to change a spawned model's <visual> material, which is
what actually makes a lens sphere look colored. See
limo_plugin/src/traffic_light_plugin.cpp for why a custom plugin is
needed here.

Steering used to be sliders, but releasing one to adjust the other
zeroed it out, making it impossible to hold a simultaneous
linear+angular command for a curve. Replaced with the actual
teleop_twist_keyboard key bindings (i/j/k/l/u/o/m/,/./q/z/w/x/e/c)
captured directly in this window instead of a separate terminal, toggled
on/off with a button so normal typing/clicking elsewhere isn't
accidentally read as a drive command.

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
    QGroupBox, QPushButton, QLabel,
)

LIGHT_COLORS = ['red', 'yellow', 'green']

PUBLISH_HZ = 20.0

# Same keys as teleop_twist_keyboard, but linear and angular are set
# independently instead of as fixed combos - teleop_twist_keyboard's
# own i/j/k/l zero out the other axis (i = pure forward, j = pure
# turn-in-place), so holding forward and tapping a turn key doesn't
# curve the path, only u/o/m/. (fixed diagonals) do. Setting each axis
# on its own key lets "i" (hold forward) + "l" (nudge right) combine
# into an actual curve.
LINEAR_KEYS = {Qt.Key_I: 1, Qt.Key_Comma: -1}
ANGULAR_KEYS = {Qt.Key_J: 1, Qt.Key_L: -1}
STOP_KEYS = {Qt.Key_K}
SPEED_STEP = 1.1  # multiply/divide by this, same as teleop_twist_keyboard's 10% (1/1.1 ~= 0.9)
SPEED_UP_KEYS = {Qt.Key_Q}
SPEED_DOWN_KEYS = {Qt.Key_Z}
LINEAR_UP_KEYS = {Qt.Key_W}
LINEAR_DOWN_KEYS = {Qt.Key_X}
ANGULAR_UP_KEYS = {Qt.Key_E}
ANGULAR_DOWN_KEYS = {Qt.Key_C}


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

        self._teleop_active = False
        self._linear = 0.0
        self._angular = 0.0
        self._speed = 0.5   # m/s, teleop_twist_keyboard's default
        self._turn = 1.0    # rad/s, teleop_twist_keyboard's default

        self._build_ui()
        self.setFocusPolicy(Qt.StrongFocus)

        # Keep publishing the current command at a fixed rate, not just
        # on key press, so the robot keeps moving until the next key
        # (matching teleop_twist_keyboard's own behavior).
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
        group = QGroupBox('Robot Steering (keyboard teleop)')
        layout = QVBoxLayout()

        self.teleop_btn = QPushButton('Keyboard Teleop: OFF')
        self.teleop_btn.setCheckable(True)
        self._style_teleop_button()
        self.teleop_btn.clicked.connect(self._toggle_teleop)
        layout.addWidget(self.teleop_btn)

        layout.addWidget(QLabel(
            'i/,: forward/back   j/l: turn left/right\n'
            '(hold i, tap j/l to curve - axes are independent)   k: stop\n'
            'q/z: speed ±10%   w/x: linear only   e/c: angular only'
        ))

        self.speed_label = QLabel(f'speed {self._speed:.2f} m/s  turn {self._turn:.2f} rad/s')
        layout.addWidget(self.speed_label)
        self.cmd_label = QLabel('linear 0.00 m/s  angular 0.00 rad/s')
        layout.addWidget(self.cmd_label)

        stop_btn = QPushButton('STOP')
        stop_btn.setStyleSheet('background-color: #d62728; color: white; font-weight: bold; padding: 10px;')
        stop_btn.clicked.connect(self._stop)
        layout.addWidget(stop_btn)

        group.setLayout(layout)
        return group

    def _style_teleop_button(self):
        if self._teleop_active:
            self.teleop_btn.setText('Keyboard Teleop: ON')
            self.teleop_btn.setStyleSheet(
                'background-color: #2ca02c; color: white; font-weight: bold; padding: 10px;')
        else:
            self.teleop_btn.setText('Keyboard Teleop: OFF')
            self.teleop_btn.setStyleSheet(
                'background-color: #888888; color: white; font-weight: bold; padding: 10px;')

    def _toggle_teleop(self):
        self._teleop_active = not self._teleop_active
        self._style_teleop_button()
        if self._teleop_active:
            self.setFocus()  # so key presses reach keyPressEvent below
        else:
            self._linear = 0.0
            self._angular = 0.0
            self._update_cmd_label()

    def keyPressEvent(self, event):
        if not self._teleop_active or event.isAutoRepeat():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in LINEAR_KEYS:
            self._linear = LINEAR_KEYS[key] * self._speed
        elif key in ANGULAR_KEYS:
            self._angular = ANGULAR_KEYS[key] * self._turn
        elif key in STOP_KEYS:
            self._linear = 0.0
            self._angular = 0.0
        elif key in SPEED_UP_KEYS:
            self._speed *= SPEED_STEP
            self._turn *= SPEED_STEP
        elif key in SPEED_DOWN_KEYS:
            self._speed /= SPEED_STEP
            self._turn /= SPEED_STEP
        elif key in LINEAR_UP_KEYS:
            self._speed *= SPEED_STEP
        elif key in LINEAR_DOWN_KEYS:
            self._speed /= SPEED_STEP
        elif key in ANGULAR_UP_KEYS:
            self._turn *= SPEED_STEP
        elif key in ANGULAR_DOWN_KEYS:
            self._turn /= SPEED_STEP
        else:
            super().keyPressEvent(event)
            return
        self.speed_label.setText(f'speed {self._speed:.2f} m/s  turn {self._turn:.2f} rad/s')
        self._update_cmd_label()

    def _update_cmd_label(self):
        self.cmd_label.setText(f'linear {self._linear:.2f} m/s  angular {self._angular:.2f} rad/s')

    def _stop(self):
        self._linear = 0.0
        self._angular = 0.0
        self._update_cmd_label()
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
