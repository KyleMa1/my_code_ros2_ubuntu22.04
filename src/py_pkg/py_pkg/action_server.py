import rclpy
from rclpy.action import ActionServer
from rclpy.node import Node
from example_interfaces.action import Fibonacci


class FibonacciActionServer(Node):
    def __init__(self):
        super().__init__("py_action_server")
        self._action_server = ActionServer(
            self, Fibonacci, "benchmark_fibonacci", self.execute_callback
        )
        self.get_logger().info("Python action server started")

    def execute_callback(self, goal_handle):
        feedback_msg = Fibonacci.Feedback()
        prev, curr = 0, 1
        for i in range(goal_handle.request.order):
            feedback_msg.sequence.append(curr)
            goal_handle.publish_feedback(feedback_msg)
            prev, curr = curr, prev + curr

        goal_handle.succeed()
        result = Fibonacci.Result()
        result.sequence = feedback_msg.sequence
        return result


def main(args=None):
    rclpy.init(args=args)
    node = FibonacciActionServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
