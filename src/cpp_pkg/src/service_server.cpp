#include "rclcpp/rclcpp.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"

class ServiceServer : public rclcpp::Node {
public:
    ServiceServer() : Node("cpp_service_server") {
        service_ = this->create_service<example_interfaces::srv::AddTwoInts>(
            "benchmark_add_two_ints",
            std::bind(&ServiceServer::handle_request, this,
                std::placeholders::_1, std::placeholders::_2));
        RCLCPP_INFO(this->get_logger(), "C++ service server started");
    }

private:
    void handle_request(
        const example_interfaces::srv::AddTwoInts::Request::SharedPtr request,
        example_interfaces::srv::AddTwoInts::Response::SharedPtr response) {
        response->sum = request->a + request->b;
    }

    rclcpp::Service<example_interfaces::srv::AddTwoInts>::SharedPtr service_;
};

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<ServiceServer>());
    rclcpp::shutdown();
    return 0;
}
