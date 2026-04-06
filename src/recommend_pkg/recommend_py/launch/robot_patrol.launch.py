"""
一键启动机器人巡逻系统 — 三语言协作示例

架构:
  sensor_driver (C++)  →  safety_monitor (Rust)  →  patrol_planner (Python)
                                ↓                          ↓
                       motor_controller (C++)  ←──────── /cmd_vel
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        # ── 驱动层 (C++): 低延迟传感器采集 ──
        Node(
            package="recommend_cpp",
            executable="sensor_driver",
            name="sensor_driver",
            output="screen",
        ),

        # ── 驱动层 (C++): 实时运动控制 ──
        Node(
            package="recommend_cpp",
            executable="motor_controller",
            name="motor_controller",
            output="screen",
        ),

        # ── 安全层 (Rust): 编译期安全保证 ──
        Node(
            package="recommend_rust",
            executable="safety_monitor",
            name="safety_monitor",
            output="screen",
            parameters=[{
                "min_safe_distance": 0.5,
                "emergency_distance": 0.2,
                "max_speed": 1.0,
            }],
        ),

        # ── 应用层 (Python): 状态机 + AI 决策 ──
        Node(
            package="recommend_py",
            executable="patrol_planner",
            name="patrol_planner",
            output="screen",
            parameters=[{
                "patrol_speed": 0.3,
                "turn_speed": 0.5,
                "avoid_duration_sec": 2.0,
            }],
        ),
    ])
