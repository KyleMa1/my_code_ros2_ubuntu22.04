#include <cmath>
#include <cstdlib>
#include <sstream>
#include <string>
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

// C++ 驱动层：模拟 LiDAR 传感器数据采集
// 选型依据：传感器驱动需要 μs 级延迟和确定性时序，C++ Topic 延迟仅 16μs
class SensorDriver : public rclcpp::Node {
public:
    SensorDriver() : Node("sensor_driver"), tick_(0) {
        scan_pub_ = create_publisher<std_msgs::msg::String>("/scan_data", 10);

        // 20Hz 传感器采样 — 模拟 LiDAR 旋转扫描
        timer_ = create_wall_timer(
            std::chrono::milliseconds(50),
            std::bind(&SensorDriver::scan_callback, this));

        RCLCPP_INFO(get_logger(), "[C++] Sensor driver started — 36-ray LiDAR @ 20Hz");
    }

private:
    static constexpr int NUM_RAYS = 36;
    static constexpr double ANGLE_STEP = 2.0 * M_PI / NUM_RAYS;
    static constexpr double MAX_RANGE = 10.0;

    void scan_callback() {
        std::ostringstream json;
        json << std::fixed;
        json.precision(3);
        json << R"({"tick":)" << tick_ << R"(,"num_rays":)" << NUM_RAYS
             << R"(,"ranges":[)";

        // 模拟一个绕机器人移动的障碍物
        double obs_angle = std::fmod(tick_ * 0.05, 2.0 * M_PI);
        double obs_base_dist = 1.2 + 0.8 * std::sin(tick_ * 0.02);

        for (int i = 0; i < NUM_RAYS; ++i) {
            double angle = i * ANGLE_STEP;
            double range = MAX_RANGE;

            // 主障碍物：角度展宽 ~30°
            double diff = std::abs(angle - obs_angle);
            if (diff > M_PI) diff = 2.0 * M_PI - diff;
            if (diff < 0.26) {
                range = obs_base_dist * (1.0 + diff * 2.0);
            }

            // 静态墙壁（180° 方向，距离 3m）
            double wall_diff = std::abs(angle - M_PI);
            if (wall_diff < 0.15) {
                range = std::min(range, 3.0 + 0.1 * wall_diff);
            }

            // 传感器噪声 ±2cm
            double noise = ((std::rand() % 100) - 50) * 0.0004;
            range = std::max(0.05, std::min(MAX_RANGE, range + noise));

            if (i > 0) json << ",";
            json << range;
        }

        json << "]}";

        auto msg = std_msgs::msg::String();
        msg.data = json.str();
        scan_pub_->publish(msg);

        if (tick_ % 100 == 0) {
            RCLCPP_INFO(get_logger(), "Published %lu scans, obstacle at %.1f° dist=%.2fm",
                        tick_, obs_angle * 180.0 / M_PI, obs_base_dist);
        }
        tick_++;
    }

    rclcpp::Publisher<std_msgs::msg::String>::SharedPtr scan_pub_;
    rclcpp::TimerBase::SharedPtr timer_;
    uint64_t tick_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SensorDriver>());
    rclcpp::shutdown();
    return 0;
}
