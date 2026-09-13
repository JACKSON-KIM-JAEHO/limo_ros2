# LIMO 시뮬레이션 맵 가이드

이 저장소에는 원본(`Readme.md`, `README.txt`)에 없던 커리큘럼용 맵과 통합 launch 파일이 추가되어 있습니다.

## 실행 방법

```bash
cd ~/nova_ws
source install/setup.bash
ros2 launch limo_car ackermann_sim.launch.py map:=<맵이름>
```

`map` 인자를 생략하면 기본값은 `track`입니다.

공통 사항:
- `gzserver`는 `xvfb-run`(가상 디스플레이) 안에서 뜹니다 — depth camera 센서가 실제 디스플레이(X11/Wayland)에서 렌더링 충돌로 크래시하는 문제를 우회하기 위함입니다. `gzclient`(3D 뷰어)는 실제 화면에 정상적으로 뜹니다.
- RViz가 같이 뜨며 `/scan`, `/odom`, `/imu`, depth camera 토픽을 확인할 수 있습니다.
- 로봇 스폰 위치/자세는 각 맵마다 다르며, 아래 표에 기재되어 있습니다.

## 맵 목록

| `map:=` 값 | 설명 | 스폰 위치 (x, y, yaw) | 비고 |
|---|---|---|---|
| `empty` | 빈 월드 + 박스 장애물 3개 | (0, 0, 0°) | 최초 동작 확인용 (Phase 0) |
| `straight_line` | 8m 직선 코스, 노란 벽으로 통로 표시, 신호등 1개 + 장애물 1개 | (-3.5, 0, 0°) | 직진 주행 + 신호 인식 + 장애물 감지 연습 (Phase 1~3) |
| `track` | 레이싱 트랙(차선/횡단보도/주차구획 텍스처) + 신호등 1개 + 장애물 2개 | (-0.51, -3.25, 0°) | 기본 트랙 — 신호등/장애물이 기본 포함됨 |
| `track_obstacles` | `track`과 동일 구성 (신호등 + 장애물 2개), 별도 변형으로 유지 | (-0.51, -3.25, 0°) | `track`과 사실상 동일, 이름만 구분용으로 남겨둠 |
| `maze` | 10x10 절차적 생성 미로, 신호등 1개(시작칸), 출구 있음 | (0, 0, 0°) | SLAM/미로 탈출 미션 (Phase 5) — 상세는 아래 참고 |
| `ramp` | 경사로(오르막→평지→내리막) + 과속방지턱 2개 | (0, 0, 0°) | IMU pitch 변화 관찰용 (Phase 4) |
| `room` | 비정형 건물(방 2개 + 좁은 복도), 가구 장애물 포함 | (0.5, 1.5, 0°) | 실제 건물 형태 SLAM 지도 품질 비교용 |
| `parking` | `track` 바닥 + 주차 목표 구역 2개(반투명 색 표시) | (-0.51, -3.25, 0°) | 전진/후진 주차 연습 — 좌표는 근사치, 아래 참고 |
| `traffic_light` | `track` 바닥 + 신호등 1개 + 장애물 2개 | (-0.51, -3.25, 0°) | 신호 인식/정지출발 연습, 색 변경법 아래 참고 |
| `integration` | 트랙 + 신호등 + 장애물 2개 + 주차 구역 2개 종합 | (-0.51, -3.25, 0°) | Phase 8 통합 프로젝트용 |

신호등과 장애물 위치는 확정되어 `track`, `track_obstacles`, `traffic_light`, `straight_line`, `maze` 다섯 맵에 공통 적용돼 있습니다 (같은 `<pose>` 값 재사용). `ramp`/`room`/`parking`/`integration`은 성격상 제외했거나(`ramp`, `room`) 이미 포함되어 있습니다(`integration`).

## 맵별 상세

### `maze` — 미로 탈출

- 재귀 백트래킹 알고리즘으로 생성 (시드 고정, 재현 가능). 10×10 셀, 셀 크기 1.0m, 벽 두께 0.06m, 벽 높이 0.3m.
- **통로 폭 1.0m는 의도적으로 넉넉하게 잡았습니다**: LIMO의 최소 회전 지름(약 0.83m, ackermann 최대 조향각 30° 기준 계산)보다 넓어서, **막다른 길에서 후진 없이 제자리 U턴으로 빠져나올 수 있습니다**. Ackermann 조향은 후진 시 좌우가 반전돼서 후진 로직이 더 까다로운데, 통로를 넓게 해서 이 문제를 우회했습니다.
- 막다른 길 9곳, 정답 경로 71칸 (꽤 복잡함).
- **목표는 "탈출"** — 미로 안의 어떤 지점이 아니라, 우측 하단 모서리 바깥벽에 뚫어놓은 출구(월드 좌표 x=9.5, y=-9.0)를 통과해서 그 1m 밖 열린 공간에 있는 초록 깃발(10.5, -9.0)에 도달하는 것이 미션입니다.
- 장애물 3개가 정답 경로 위에 배치되어 있습니다.
- 그리드 크기·셀 크기·시드는 `worlds/maze_world.model`을 생성한 스크립트 파라미터이며, 재생성하려면 알려주시면 다시 만들어드릴 수 있습니다 (현재는 생성된 결과 SDF만 저장되어 있고 생성 스크립트 자체는 저장소에 없습니다).

### `parking` / `traffic_light` / `integration` — 좌표 근사치 주의

`track` 계열 바닥은 레이스트랙 텍스처 이미지를 8.25×6.2m 평면에 입힌 것뿐이라, 이미지 픽셀과 월드 좌표 사이의 정확한 변환식이 없습니다. 확인된 건 "Start" 표시가 있는 지점 딱 하나(픽셀 (77,222) = 월드 (-0.5137, -3.2524), 로봇이 그 자리에서 yaw≈0°로 있으면 맞다는 것)뿐입니다.

- **주차 구역 2곳**은 이 하나의 기준점에서 역산한 추정치입니다. 트랙 텍스처에 그려진 실제 주차 칸 그림과 정확히 안 맞을 수 있습니다.
- **신호등 위치**도 시작선 기준 대략적인 위치입니다.

둘 다 Gazebo에서 눈으로 보고 위치가 어긋나 있으면 알려주세요 — `worlds/parking_world.model`, `worlds/traffic_light_world.model`, `worlds/integration_world.model`의 `<pose>` 값만 조정하면 됩니다.

### `traffic_light` — 신호 색 바꾸기

`libgazebo_ros_properties.so`(ros-humble-gazebo-ros 표준 플러그인, 커스텀 컴파일 불필요)로 신호등의 각 전구(`light`)를 개별 제어합니다.

```bash
# 빨간불 끄기
ros2 service call /set_light_properties gazebo_msgs/srv/SetLightProperties \
  "{light_name: 'traffic_light::pole::red_light', diffuse: {r: 0.05, g: 0.05, b: 0.05, a: 1.0}, attenuation_constant: 0.2}"

# 초록불 켜기
ros2 service call /set_light_properties gazebo_msgs/srv/SetLightProperties \
  "{light_name: 'traffic_light::pole::green_light', diffuse: {r: 0.0, g: 1.0, b: 0.0, a: 1.0}, attenuation_constant: 0.2}"

# 노란불 켜기
ros2 service call /set_light_properties gazebo_msgs/srv/SetLightProperties \
  "{light_name: 'traffic_light::pole::yellow_light', diffuse: {r: 1.0, g: 0.85, b: 0.0, a: 1.0}, attenuation_constant: 0.2}"
```

`light_name` 형식은 `<모델 인스턴스 이름>::<링크 이름>::<라이트 이름>`입니다 (`traffic_light_world.model`에서 모델을 `<name>traffic_light</name>`로 include했고, 내부 링크 이름은 `pole`). 다른 월드에 두 번째 신호등을 추가하면 인스턴스 이름이 달라지니 그에 맞게 바꿔야 합니다.

기본 상태는 빨간불 켜짐, 노랑/초록은 꺼짐(어두운 회색)입니다.

## 트랙/신호등 텍스처 출처

`models/race_track/`의 텍스처와 재질 스크립트는 성균관대 자동화연구실의 [SKKUAutoLab/H-Mobility-Autonomous-Advanced-Course-Simulation](https://github.com/SKKUAutoLab/H-Mobility-Autonomous-Advanced-Course-Simulation) (GPL-2.0)에서 가져왔습니다. 원본은 실제 크기(1:1) 차량(Prius 등) 기준으로 제작되어 있어, LIMO 스케일(약 1/13.5)로 축소해서 재사용했습니다 (`track_world.model`의 ground plane `<size>` 참고).

## 성능 관련

`limo_base_lean.stl` / `limo_wheel_lean.stl`은 원본 메쉬(`meshes/original_backup/`는 삭제됨, git 히스토리의 `humble` 브랜치에 원본 보존)를 색상 그룹별로 병합·정점 용접·폴리곤 감소한 결과물입니다. 원본은 1619개의 별도 조각(드로우콜)으로 쪼개져 있어 렉의 원인이 되었는데, 이를 병합해서 해결했습니다. 자세한 배경은 `git log`의 커밋 메시지를 참고하세요.
