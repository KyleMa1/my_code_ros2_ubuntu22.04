"""
Python 应用层：巡逻规划节点 — 状态机 + AI 决策

选型依据：
- 行为树/状态机逻辑频繁变更，Python 零编译、改了就跑
- AI/ML 生态无可替代（PyTorch/TensorFlow 直接调用）
- 代码最简洁，适合高层业务逻辑的快速迭代
"""

import json
import math

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String


class PatrolPlanner(Node):

    IDLE = "IDLE"
    PATROL = "PATROL"
    AVOID = "AVOID_OBSTACLE"
    EMERGENCY = "EMERGENCY_STOP"

    def __init__(self):
        super().__init__("patrol_planner")

        self.declare_parameter("patrol_speed", 0.3)
        self.declare_parameter("turn_speed", 0.5)
        self.declare_parameter("avoid_duration_sec", 2.0)

        self.state = self.IDLE
        self.safety_data = None
        self.patrol_phase = 0.0
        self.avoid_start = None
        self.idle_ticks = 0

        self.safety_sub = self.create_subscription(
            String, "/safety_status", self._on_safety, 10
        )
        self.cmd_pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # 10Hz 规划循环 — Python 的 GIL 在此频率下毫无影响
        self.timer = self.create_timer(0.1, self._plan_loop)

        self.get_logger().info(f"[Python] Patrol planner started — state: {self.state}")

    def _on_safety(self, msg: String):
        try:
            self.safety_data = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _transition(self, new_state: str):
        if new_state != self.state:
            self.get_logger().info(f"State: {self.state} → {new_state}")
            if new_state == self.AVOID:
                self.avoid_start = self.get_clock().now()
            self.state = new_state

    def _plan_loop(self):
        cmd = Twist()

        if self.safety_data is None:
            self.idle_ticks += 1
            if self.idle_ticks % 50 == 1:
                self.get_logger().info("Waiting for safety status from Rust node...")
            self.cmd_pub.publish(cmd)
            return

        is_emergency = self.safety_data.get("emergency", False)
        is_safe = self.safety_data.get("safe", True)
        max_speed = self.safety_data.get("max_allowed_speed", 0.0)
        danger_idx = self.safety_data.get("danger_index", -1)

        # 状态转移逻辑 — 典型行为树/状态机，Python 表达最直观
        if is_emergency:
            self._transition(self.EMERGENCY)
        elif not is_safe and self.state == self.PATROL:
            self._transition(self.AVOID)
        elif is_safe and self.state == self.EMERGENCY:
            self._transition(self.IDLE)
        elif is_safe and self.state == self.AVOID:
            self._transition(self.PATROL)
        elif self.state == self.IDLE and is_safe:
            self._transition(self.PATROL)

        patrol_speed = self.get_parameter("patrol_speed").value
        turn_speed = self.get_parameter("turn_speed").value
        avoid_dur = self.get_parameter("avoid_duration_sec").value

        if self.state == self.PATROL:
            # 巡逻模式：匀速前进 + 正弦摆动模拟巡逻路径
            cmd.linear.x = min(patrol_speed, max_speed)
            self.patrol_phase += 0.08
            cmd.angular.z = 0.3 * math.sin(self.patrol_phase)

        elif self.state == self.AVOID:
            # 避障模式：低速前进 + 转向远离障碍物方向
            cmd.linear.x = min(0.1, max_speed)
            # 36 rays: 0~17 为左侧(0~180°), 18~35 为右侧(180~360°)
            if 0 <= danger_idx < 18:
                cmd.angular.z = -turn_speed  # 障碍在左，右转
            else:
                cmd.angular.z = turn_speed  # 障碍在右，左转

            if self.avoid_start is not None:
                elapsed = (self.get_clock().now() - self.avoid_start).nanoseconds * 1e-9
                if elapsed > avoid_dur:
                    self._transition(self.PATROL)

        elif self.state == self.EMERGENCY:
            cmd.linear.x = 0.0
            cmd.angular.z = 0.0

        self.cmd_pub.publish(cmd)


def main(args=None):
    rclpy.init(args=args)
    node = PatrolPlanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
