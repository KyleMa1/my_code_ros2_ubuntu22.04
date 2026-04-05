import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts


class ServiceServer(Node):
    def __init__(self):
        super().__init__("py_service_server")
        self.srv = self.create_service(
            AddTwoInts, "benchmark_add_two_ints", self.handle_request
        )
        self.get_logger().info("Python service server started")

    def handle_request(self, request, response):
        response.sum = request.a + request.b
        return response


def main(args=None):
    rclpy.init(args=args)
    node = ServiceServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
