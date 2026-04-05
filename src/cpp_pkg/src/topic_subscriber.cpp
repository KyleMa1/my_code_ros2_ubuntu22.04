#include <chrono>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

class TopicSubscriber : public rclcpp::Node {
public:
    TopicSubscriber() : Node("cpp_topic_sub") {
        subscription_ = this->create_subscription<std_msgs::msg::String>(
            "benchmark_topic", 10,
            std::bind(&TopicSubscriber::topic_callback, this, std::placeholders::_1));
        RCLCPP_INFO(this->get_logger(), "C++ topic subscriber started");
    }

private:
    void topic_callback(const std_msgs::msg::String::SharedPtr msg) {
        auto now = std::chrono::high_resolution_clock::now();
        auto now_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            now.time_since_epoch()).count();
        auto sep = msg->data.find('|');
        if (sep != std::string::npos) {
            auto sent_ns = std::stoll(msg->data.substr(0, sep));
            auto latency_us = (now_ns - sent_ns) / 1000.0;
            RCLCPP_INFO(this->get_logger(), "Received [%s] latency=%.1f us",
                msg->data.substr(sep + 1).c_str(), latency_us);
        }
    }

    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<TopicSubscriber>());
    rclcpp::shutdown();
    return 0;
}
