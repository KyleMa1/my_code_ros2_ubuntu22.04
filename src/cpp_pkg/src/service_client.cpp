#include <chrono>
#include "rclcpp/rclcpp.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("cpp_service_client");
    auto client = node->create_client<example_interfaces::srv::AddTwoInts>(
        "benchmark_add_two_ints");

    while (!client->wait_for_service(std::chrono::seconds(1))) {
        if (!rclcpp::ok()) { return 1; }
        RCLCPP_INFO(node->get_logger(), "Waiting for service...");
    }

    auto request = std::make_shared<example_interfaces::srv::AddTwoInts::Request>();
    request->a = 41;
    request->b = 1;

    auto future = client->async_send_request(request);
    if (rclcpp::spin_until_future_complete(node, future) == rclcpp::FutureReturnCode::SUCCESS) {
        RCLCPP_INFO(node->get_logger(), "Result: %ld", future.get()->sum);
    }

    rclcpp::shutdown();
    return 0;
}
