# Limo ROS2 Humble

## 1. Introduction of Function Package

```
└── limo_ros2
    ├── limo_base
    ├── limo_bringup
    ├── limo_car
    ├── limo_msgs
    └── Readme.md

```

limo_base ：This folder is the driver package

limo_bringup：This folder stores some launch files

limo_car：The folder is gazebo simulation function package

limo_msgs：This folder is some message files

## 2. Environment

### Development Environment

 ubuntu 22.04 + [ROS2 Humble desktop full](http://docs.ros.org/en/humble/Installation/Alternatives/Ubuntu-Development-Setup.html)

### Download and install required function package

Download and install joint-state-publisher-gui package.This package is used to visualize the joint control.

```
sudo apt-get install ros-humble-joint-state-publisher-gui 
```

Download and install rqt-robot-steering plug-in, rqt_robot_steering is a ROS tool closely related to robot motion control, it can send the control command of robot linear motion and steering motion, and the robot motion can be easily controlled through the sliding bar

```
sudo apt-get update
sudo apt-get install ros-humble-rqt-robot-steering
```

Download and install teleop-twist-keyboard

###  Download package and Build

```
mkdir -p nova_ws/src
cd nova_ws/src
git clone https://github.com/JACKSON-KIM-JAEHO/limo_ros2.git
cd ~/nova_ws
colcon build
```

## Usage

Start the base node for limo

```
ros2 launch limo_base limo_base.launch.py 
```

Start the keyboard teleop node

```
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

## 커리큘럼 시뮬레이션 맵 (LIMO Gazebo)

원본 패키지에 없던 맵 10종(직선 주행, 레이싱 트랙, 신호등, 장애물, 미로, 경사로, 주차 등)과
이를 한 번에 켜는 통합 launch 파일, 신호등/조향 대시보드가 `limo_car` 패키지에 추가되어 있습니다.

```bash
cd ~/nova_ws
source install/setup.bash
ros2 launch limo_car ackermann_sim.launch.py map:=<맵이름>
```

`map` 인자를 생략하면 기본값은 `track`입니다. `map:=` 에 넣을 수 있는 값:

| 값 | 내용 |
|---|---|
| `empty` | 빈 월드 + 박스 장애물 3개 (최초 동작 확인용) |
| `straight_line` | 8m 직선 코스 + 신호등 1개 + 장애물 1개 |
| `track` | 레이싱 트랙 + 신호등 1개 + 장애물 2개 (기본값) |
| `track_obstacles` | `track`과 동일 구성 (변형용 별칭) |
| `maze` | 10x10 절차적 생성 미로, SLAM/미로 탈출 미션 |
| `ramp` | 경사로(오르막→평지→내리막) + 과속방지턱 2개 |
| `room` | 비정형 건물(방 2개 + 좁은 복도), SLAM 지도 비교용 |
| `parking` | `track` 바닥 + 주차 목표 구역 2개 |
| `traffic_light` | `track` 바닥 + 신호등 1개 + 장애물 2개 |
| `integration` | 트랙 + 신호등 + 장애물 2개 + 주차 구역 2개 종합 |

스폰 좌표, 신호등 색 변경법, 대시보드(Keyboard Teleop, Max speed/turn, 신호등 버튼)
사용법 등 상세 내용은 [`limo_car/MAPS.md`](limo_car/MAPS.md)에 정리되어 있습니다.

# statement

The limo_car gazebo simulation function package is provided by us and the Institute for **Intermodal Transport and Logistics SystemsTU Braunschweig, Germany **jointly developed, thanks for their efforts











