import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from example_interfaces.action import Fibonacci


class FibonacciActionClient(Node):
    def __init__(self):
        super().__init__("py_action_client")
        self._client = ActionClient(self, Fibonacci, "benchmark_fibonacci")

    def send_goal(self, order):
        goal = Fibonacci.Goal()
        goal.order = order
        self._client.wait_for_server()

        future = self._client.send_goal_async(
            goal, feedback_callback=self.feedback_callback
        )
        rclpy.spin_until_future_complete(self, future)
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().info("Goal rejected")
            return

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        self.get_logger().info(f"Result: {len(result.sequence)} elements")

    def feedback_callback(self, feedback_msg):
        seq = feedback_msg.feedback.sequence
        if seq:
            self.get_logger().info(f"Feedback: len={len(seq)} last={seq[-1]}")


def main(args=None):
    rclpy.init(args=args)
    node = FibonacciActionClient()
    node.send_goal(10)
    node.destroy_node()
    rclpy.shutdown()
