#include <cmath>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "std_msgs/msg/bool.hpp"

// C++ 驱动层：运动控制器 — 接收速度指令，模拟电机输出
// 选型依据：运动控制要求 <1ms 硬实时响应，C++ 在此场景无可替代
class MotorController : public rclcpp::Node {
public:
    MotorController()
        : Node("motor_controller"),
          current_linear_(0.0), current_angular_(0.0),
          target_linear_(0.0), target_angular_(0.0),
          emergency_stop_(false), tick_(0) {

        cmd_sub_ = create_subscription<geometry_msgs::msg::Twist>(
            "/cmd_vel", 10,
            std::bind(&MotorController::cmd_callback, this, std::placeholders::_1));

        estop_sub_ = create_subscription<std_msgs::msg::Bool>(
            "/emergency_stop", 10,
            std::bind(&MotorController::estop_callback, this, std::placeholders::_1));

        // 50Hz 控制环路 — 模拟电机 PID 输出
        control_timer_ = create_wall_timer(
            std::chrono::milliseconds(20),
            std::bind(&MotorController::control_loop, this));

        RCLCPP_INFO(get_logger(), "[C++] Motor controller started — 50Hz control loop");
    }

private:
    static constexpr double RAMP_RATE = 0.05;

    void cmd_callback(const geometry_msgs::msg::Twist::SharedPtr msg) {
        target_linear_ = msg->linear.x;
        target_angular_ = msg->angular.z;
    }

    void estop_callback(const std_msgs::msg::Bool::SharedPtr msg) {
        if (msg->data && !emergency_stop_) {
            RCLCPP_WARN(get_logger(), "EMERGENCY STOP activated!");
        } else if (!msg->data && emergency_stop_) {
            RCLCPP_INFO(get_logger(), "Emergency stop released");
        }
        emergency_stop_ = msg->data;
    }

    // 速度渐变：避免瞬间加减速
    static double ramp(double current, double target, double rate) {
        double diff = target - current;
        if (std::abs(diff) < rate) return target;
        return current + (diff > 0 ? rate : -rate);
    }

    void control_loop() {
        if (emergency_stop_) {
            current_linear_ = ramp(current_linear_, 0.0, RAMP_RATE * 3.0);
            current_angular_ = ramp(current_angular_, 0.0, RAMP_RATE * 3.0);
        } else {
            current_linear_ = ramp(current_linear_, target_linear_, RAMP_RATE);
            current_angular_ = ramp(current_angular_, target_angular_, RAMP_RATE);
        }

        if (tick_ % 50 == 0) {
            RCLCPP_INFO(get_logger(),
                "Motor output: linear=%.3f angular=%.3f | target: l=%.3f a=%.3f | estop=%s",
                current_linear_, current_angular_,
                target_linear_, target_angular_,
                emergency_stop_ ? "ON" : "off");
        }
        tick_++;
    }

    rclcpp::Subscription<geometry_msgs::msg::Twist>::SharedPtr cmd_sub_;
    rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr estop_sub_;
    rclcpp::TimerBase::SharedPtr control_timer_;

    double current_linear_, current_angular_;
    double target_linear_, target_angular_;
    bool emergency_stop_;
    uint64_t tick_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<MotorController>());
    rclcpp::shutdown();
    return 0;
}
