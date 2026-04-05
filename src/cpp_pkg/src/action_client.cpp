#include <chrono>
#include <iostream>
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "example_interfaces/action/fibonacci.hpp"

using Fibonacci = example_interfaces::action::Fibonacci;

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    auto node = rclcpp::Node::make_shared("cpp_action_client");
    auto client = rclcpp_action::create_client<Fibonacci>(node, "benchmark_fibonacci");

    if (!client->wait_for_action_server(std::chrono::seconds(5))) {
        RCLCPP_ERROR(node->get_logger(), "Action server not available");
        return 1;
    }

    auto goal = Fibonacci::Goal();
    goal.order = 10;

    auto send_goal_options = rclcpp_action::Client<Fibonacci>::SendGoalOptions();
    send_goal_options.feedback_callback =
        [&node](auto, const auto& feedback) {
            auto& seq = feedback->sequence;
            if (!seq.empty()) {
                RCLCPP_INFO(node->get_logger(), "Feedback: len=%zu last=%d",
                    seq.size(), seq.back());
            }
        };

    auto goal_future = client->async_send_goal(goal, send_goal_options);
    if (rclcpp::spin_until_future_complete(node, goal_future) != rclcpp::FutureReturnCode::SUCCESS) {
        RCLCPP_ERROR(node->get_logger(), "Failed to send goal");
        return 1;
    }

    auto goal_handle = goal_future.get();
    if (!goal_handle) {
        RCLCPP_ERROR(node->get_logger(), "Goal was rejected");
        return 1;
    }

    auto result_future = client->async_get_result(goal_handle);
    if (rclcpp::spin_until_future_complete(node, result_future) == rclcpp::FutureReturnCode::SUCCESS) {
        auto& seq = result_future.get().result->sequence;
        RCLCPP_INFO(node->get_logger(), "Result: %zu elements", seq.size());
    }

    rclcpp::shutdown();
    return 0;
}
