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
- **`limo_dashboard`(커스텀 Qt 대시보드)가 항상 같이 뜹니다** — 신호등 색 버튼(빨강/노랑/초록)과 로봇 조종 슬라이더(`rqt_robot_steering` 대체)가 한 창에 있습니다. 아래 "대시보드" 절 참고.
- 로봇 스폰 위치/자세는 각 맵마다 다르며, 아래 표에 기재되어 있습니다.

## 대시보드 (`limo_dashboard`)

`ros2 launch limo_car ackermann_sim.launch.py map:=...`를 실행하면 자동으로 같이 뜹니다. 단독 실행도 가능합니다:

```bash
ros2 run limo_dashboard dashboard_node
```

- **Traffic Light**: 빨강/노랑/초록 버튼 — `/traffic_light/color`에 `std_msgs/String` 발행 (`limo_plugin`의 커스텀 Gazebo 플러그인이 실제 렌즈 색을 바꿈). 상세는 아래 "`traffic_light` — 신호 색 바꾸기" 참고.
- **Robot Steering**: 선속도/각속도 슬라이더 → `/cmd_vel` 퍼블리시 (20Hz 지속 발행). 슬라이더는 놓아도 값이 유지됩니다 (선속도+각속도를 동시에 유지해야 커브 주행이 되므로 `rqt_robot_steering`의 스프링백 동작은 일부러 안 씀). STOP 버튼으로 즉시 정지.
- 소스: `limo_dashboard/limo_dashboard/dashboard_node.py`. 패널을 더 추가하려면 `_build_..._group(self)` 메서드를 하나 더 만들고 `_build_ui`의 레이아웃에 추가하면 됩니다.

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

**`gazebo_msgs/SetLightProperties` 서비스는 안 씁니다** — 그건 `<light>`(조명)만 바꾸고, 실제로 눈에 보이는 렌즈(`<visual>`)의 재질 색은 안 바뀝니다 (Gazebo Classic이 스폰된 모델의 visual 재질을 바꾸는 공개 API를 제공하지 않음). 처음엔 이걸로 시도했다가 "버튼 눌러도 안 바뀌고 엉뚱한 곳에 색만 비친다"는 문제를 겪었습니다.

대신 **커스텀 Gazebo 모델 플러그인**(`limo_plugin` 패키지, `traffic_light_plugin.cpp`)이 렌즈별 링크(`red_light_link`/`yellow_light_link`/`green_light_link`)의 visual 메시지를 직접 재발행해서 재질을 바꿉니다. 트랙 텍스처를 가져온 SKKUAutoLab 레포의 `traffic_ctrl` 모델 + `plugin_pkg`를 참고해서 만들었습니다 (GPL-2.0).

색 변경은 토픽 발행으로 합니다:

```bash
ros2 topic pub -1 /traffic_light/color std_msgs/msg/String "{data: 'green'}"
ros2 topic pub -1 /traffic_light/color std_msgs/msg/String "{data: 'yellow'}"
ros2 topic pub -1 /traffic_light/color std_msgs/msg/String "{data: 'red'}"
ros2 topic pub -1 /traffic_light/color std_msgs/msg/String "{data: 'off'}"
```

대시보드의 빨강/노랑/초록 버튼도 내부적으로 이 토픽에 발행합니다. 모든 맵이 신호등 인스턴스 이름을 `traffic_light`로 통일해서 썼고, 플러그인이 그 안의 고정된 링크 이름(`red_light_link` 등)을 대상으로 하기 때문에 토픽 이름은 어느 맵에서든 동일합니다 — 단, **월드 하나에 신호등을 2개 이상 넣으면 토픽이 겹쳐서 구분이 안 됩니다** (아직 지원 안 함, 필요하면 `model.sdf`의 `<topic>` 태그로 인스턴스별로 다르게 설정 가능).

기본 상태는 빨간불 켜짐, 노랑/초록은 꺼짐(어두운 회색)입니다.

## 트랙/신호등 텍스처 출처

`models/race_track/`의 텍스처와 재질 스크립트는 성균관대 자동화연구실의 [SKKUAutoLab/H-Mobility-Autonomous-Advanced-Course-Simulation](https://github.com/SKKUAutoLab/H-Mobility-Autonomous-Advanced-Course-Simulation) (GPL-2.0)에서 가져왔습니다. 원본은 실제 크기(1:1) 차량(Prius 등) 기준으로 제작되어 있어, LIMO 스케일(약 1/13.5)로 축소해서 재사용했습니다 (`track_world.model`의 ground plane `<size>` 참고).

## 성능 관련

`limo_base_lean.stl` / `limo_wheel_lean.stl`은 원본 메쉬(`meshes/original_backup/`는 삭제됨, git 히스토리의 `humble` 브랜치에 원본 보존)를 색상 그룹별로 병합·정점 용접·폴리곤 감소한 결과물입니다. 원본은 1619개의 별도 조각(드로우콜)으로 쪼개져 있어 렉의 원인이 되었는데, 이를 병합해서 해결했습니다. 자세한 배경은 `git log`의 커밋 메시지를 참고하세요.
