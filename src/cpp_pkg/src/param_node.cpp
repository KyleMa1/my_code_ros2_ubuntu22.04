#include "rclcpp/rclcpp.hpp"

class ParamNode : public rclcpp::Node {
public:
    ParamNode() : Node("cpp_param_node") {
        this->declare_parameter("my_int", 42);
        this->declare_parameter("my_double", 3.14);
        this->declare_parameter("my_string", "hello");
        this->declare_parameter("my_bool", true);

        param_callback_handle_ = this->add_on_set_parameters_callback(
            std::bind(&ParamNode::on_param_change, this, std::placeholders::_1));

        timer_ = this->create_wall_timer(
            std::chrono::seconds(1),
            std::bind(&ParamNode::timer_callback, this));

        RCLCPP_INFO(this->get_logger(), "C++ param node started");
    }

private:
    rcl_interfaces::msg::SetParametersResult on_param_change(
        const std::vector<rclcpp::Parameter>& params) {
        rcl_interfaces::msg::SetParametersResult result;
        result.successful = true;
        for (const auto& p : params) {
            RCLCPP_INFO(this->get_logger(), "Param changed: %s = %s",
                p.get_name().c_str(), p.value_to_string().c_str());
        }
        return result;
    }

    void timer_callback() {
        auto val = this->get_parameter("my_int").as_int();
        RCLCPP_INFO(this->get_logger(), "my_int = %ld", val);
    }

    rclcpp::TimerBase::SharedPtr timer_;
    rclcpp::node_interfaces::OnSetParametersCallbackHandle::SharedPtr param_callback_handle_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<ParamNode>());
    rclcpp::shutdown();
    return 0;
}
