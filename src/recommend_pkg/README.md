# recommend_pkg — ROS2 三语言协作机器人示例

> **C++ 管性能，Python 管效率，Rust 管安全。**

基于 [语言选型指南](../../docs/ros2_language_selection_guide.md) 的实测数据，本示例展示如何让三种语言各司其职，构建一个**机器人巡逻系统**。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                    应用层 · Python                            │
│  patrol_planner: 状态机 · 行为决策 · AI 推理入口              │
├──────────────────────────────────────────────────────────────┤
│                    安全层 · Rust                              │
│  safety_monitor: 安全阈值评估 · 紧急制动 · 参数管理           │
├──────────────────────────────────────────────────────────────┤
│                    驱动层 · C++                               │
│  sensor_driver: LiDAR 采集 (20Hz)                            │
│  motor_controller: 运动控制 (50Hz)                            │
└──────────────────────────────────────────────────────────────┘
```

## 数据流

```
sensor_driver ──/scan_data──→ safety_monitor ──/safety_status──→ patrol_planner
    (C++ 20Hz)       (String/JSON)    (Rust)      (String/JSON)      (Python 10Hz)
                                        │                                │
                                        │ /emergency_stop (Bool)         │ /cmd_vel (Twist)
                                        ↓                                ↓
                                   motor_controller ←────────────────────┘
                                      (C++ 50Hz)
```

## 各语言选型理由

| 节点 | 语言 | 选型依据 |
|------|------|---------|
| **sensor_driver** | C++ | 传感器驱动需要 μs 级延迟 (实测 Topic 延迟 16μs)，硬件接口 + 确定性时序 |
| **motor_controller** | C++ | 运动控制要求 <1ms 硬实时 (50Hz 控制环)，速度渐变、PID 等计算密集操作 |
| **safety_monitor** | Rust | 安全关键模块：编译期消除数据竞争，参数读写比 C++ 快 111 倍 (20.3M ops/s) |
| **patrol_planner** | Python | 状态机逻辑频繁变更、零编译迭代；未来可直接接入 PyTorch/TensorFlow 做 AI 推理 |

## Topic 一览

| Topic | 类型 | 发布者 | 订阅者 | 频率 |
|-------|------|--------|--------|------|
| `/scan_data` | `std_msgs/String` (JSON) | sensor_driver (C++) | safety_monitor (Rust) | 20 Hz |
| `/safety_status` | `std_msgs/String` (JSON) | safety_monitor (Rust) | patrol_planner (Python) | 20 Hz |
| `/emergency_stop` | `std_msgs/Bool` | safety_monitor (Rust) | motor_controller (C++) | 20 Hz |
| `/cmd_vel` | `geometry_msgs/Twist` | patrol_planner (Python) | motor_controller (C++) | 10 Hz |

## 构建 & 运行

```bash
# 构建三个包（及其依赖）
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-up-to recommend_cpp recommend_rust recommend_py \
  --allow-overriding std_msgs geometry_msgs builtin_interfaces

# 运行
source install/setup.bash
ros2 launch recommend_py robot_patrol.launch.py
```

### 单独启动各节点（调试用）

```bash
# 终端 1: C++ 传感器
ros2 run recommend_cpp sensor_driver

# 终端 2: Rust 安全守卫
ros2 run recommend_rust safety_monitor --ros-args -p min_safe_distance:=0.5 -p emergency_distance:=0.2

# 终端 3: Python 巡逻规划
ros2 run recommend_py patrol_planner

# 终端 4: C++ 电机控制
ros2 run recommend_cpp motor_controller
```

### 观察 Topic

```bash
ros2 topic echo /safety_status   # 查看安全状态 JSON
ros2 topic echo /cmd_vel          # 查看速度指令
ros2 topic hz /scan_data          # 确认 20Hz 采样率
```

## 包结构

```
recommend_pkg/
├── README.md
├── recommend_cpp/          # ament_cmake
│   ├── package.xml
│   ├── CMakeLists.txt
│   └── src/
│       ├── sensor_driver.cpp       # LiDAR 模拟 (20Hz)
│       └── motor_controller.cpp    # 电机控制 (50Hz)
├── recommend_rust/         # ament_cargo
│   ├── package.xml
│   ├── Cargo.toml
│   └── src/bin/
│       └── safety_monitor.rs       # 安全评估 + 参数管理
└── recommend_py/           # ament_python
    ├── package.xml
    ├── setup.py / setup.cfg / pyproject.toml
    ├── launch/
    │   └── robot_patrol.launch.py  # 一键启动
    └── recommend_py/
        └── patrol_planner.py       # 巡逻状态机
```
