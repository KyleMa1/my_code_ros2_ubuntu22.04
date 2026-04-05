import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class TopicSubscriber(Node):
    def __init__(self):
        super().__init__("py_topic_sub")
        self.subscription = self.create_subscription(
            String, "benchmark_topic", self.listener_callback, 10
        )
        self.get_logger().info("Python topic subscriber started")

    def listener_callback(self, msg):
        now_ns = time.time_ns()
        parts = msg.data.split("|", 1)
        if len(parts) == 2:
            sent_ns = int(parts[0])
            latency_us = (now_ns - sent_ns) / 1000.0
            self.get_logger().info(f"Received [{parts[1]}] latency={latency_us:.1f} us")


def main(args=None):
    rclpy.init(args=args)
    node = TopicSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
