import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class TopicPublisher(Node):
    def __init__(self):
        super().__init__("py_topic_pub")
        self.publisher_ = self.create_publisher(String, "benchmark_topic", 10)
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.count = 0
        self.get_logger().info("Python topic publisher started")

    def timer_callback(self):
        msg = String()
        msg.data = f"{time.time_ns()}|seq={self.count}"
        self.publisher_.publish(msg)
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = TopicPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
