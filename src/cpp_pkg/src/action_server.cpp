#include <memory>
#include <thread>
#include "rclcpp/rclcpp.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "example_interfaces/action/fibonacci.hpp"

using Fibonacci = example_interfaces::action::Fibonacci;
using GoalHandleFib = rclcpp_action::ServerGoalHandle<Fibonacci>;

class FibonacciActionServer : public rclcpp::Node {
public:
    FibonacciActionServer() : Node("cpp_action_server") {
        action_server_ = rclcpp_action::create_server<Fibonacci>(
            this, "benchmark_fibonacci",
            std::bind(&FibonacciActionServer::handle_goal, this,
                std::placeholders::_1, std::placeholders::_2),
            std::bind(&FibonacciActionServer::handle_cancel, this,
                std::placeholders::_1),
            std::bind(&FibonacciActionServer::handle_accepted, this,
                std::placeholders::_1));
        RCLCPP_INFO(this->get_logger(), "C++ action server started");
    }

private:
    rclcpp_action::GoalResponse handle_goal(
        const rclcpp_action::GoalUUID&,
        std::shared_ptr<const Fibonacci::Goal> goal) {
        return (goal->order >= 0)
            ? rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE
            : rclcpp_action::GoalResponse::REJECT;
    }

    rclcpp_action::CancelResponse handle_cancel(
        const std::shared_ptr<GoalHandleFib>) {
        return rclcpp_action::CancelResponse::ACCEPT;
    }

    void handle_accepted(const std::shared_ptr<GoalHandleFib> goal_handle) {
        std::thread([this, goal_handle]() { execute(goal_handle); }).detach();
    }

    void execute(const std::shared_ptr<GoalHandleFib> goal_handle) {
        auto goal = goal_handle->get_goal();
        auto feedback = std::make_shared<Fibonacci::Feedback>();
        auto result = std::make_shared<Fibonacci::Result>();

        int prev = 0, curr = 1;
        for (int i = 0; i < goal->order; ++i) {
            if (goal_handle->is_canceling()) {
                result->sequence = feedback->sequence;
                goal_handle->canceled(result);
                return;
            }
            feedback->sequence.push_back(curr);
            goal_handle->publish_feedback(feedback);
            int next = prev + curr;
            prev = curr;
            curr = next;
        }
        result->sequence = feedback->sequence;
        goal_handle->succeed(result);
    }

    rclcpp_action::Server<Fibonacci>::SharedPtr action_server_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<FibonacciActionServer>());
    rclcpp::shutdown();
    return 0;
}
