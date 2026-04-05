#include <chrono>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

class TopicPublisher : public rclcpp::Node {
public:
    TopicPublisher() : Node("cpp_topic_pub"), count_(0) {
        publisher_ = this->create_publisher<std_msgs::msg::String>("benchmark_topic", 10);
        timer_ = this->create_wall_timer(
            std::chrono::milliseconds(100),
            std::bind(&TopicPublisher::timer_callback, this));
        RCLCPP_INFO(this->get_logger(), "C++ topic publisher started");
    }

private:
    void timer_callback() {
        auto msg = std_msgs::msg::String();
        auto now = std::chrono::high_resolution_clock::now();
        auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
            now.time_since_epoch()).count();
        msg.data = std::to_string(ns) + "|seq=" + std::to_string(count_++);
        publisher_->publish(msg);
    }

    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
    rclcpp::TimerBase::SharedPtr timer_;
    size_t count_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<TopicPublisher>());
    rclcpp::shutdown();
    return 0;
}
