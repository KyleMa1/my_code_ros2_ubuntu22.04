import rclpy
from rclpy.node import Node
from example_interfaces.srv import AddTwoInts


def main(args=None):
    rclpy.init(args=args)
    node = Node("py_service_client")
    client = node.create_client(AddTwoInts, "benchmark_add_two_ints")

    while not client.wait_for_service(timeout_sec=1.0):
        node.get_logger().info("Waiting for service...")

    request = AddTwoInts.Request()
    request.a = 41
    request.b = 1

    future = client.call_async(request)
    rclpy.spin_until_future_complete(node, future)
    node.get_logger().info(f"Result: {future.result().sum}")

    node.destroy_node()
    rclpy.shutdown()
