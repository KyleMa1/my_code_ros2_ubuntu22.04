import rclpy
from rclpy.node import Node
from rcl_interfaces.msg import SetParametersResult


class ParamNode(Node):
    def __init__(self):
        super().__init__("py_param_node")
        self.declare_parameter("my_int", 42)
        self.declare_parameter("my_double", 3.14)
        self.declare_parameter("my_string", "hello")
        self.declare_parameter("my_bool", True)

        self.add_on_set_parameters_callback(self.on_param_change)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.get_logger().info("Python param node started")

    def on_param_change(self, params):
        for p in params:
            self.get_logger().info(f"Param changed: {p.name} = {p.value}")
        return SetParametersResult(successful=True)

    def timer_callback(self):
        val = self.get_parameter("my_int").value
        self.get_logger().info(f"my_int = {val}")


def main(args=None):
    rclpy.init(args=args)
    node = ParamNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
