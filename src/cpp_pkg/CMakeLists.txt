cmake_minimum_required(VERSION 3.20)
project(cpp_pkg VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_action REQUIRED)
find_package(std_msgs REQUIRED)
find_package(example_interfaces REQUIRED)

add_library(cpp_pkg_lib src/cpp_pkg.cpp)
target_include_directories(cpp_pkg_lib PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

macro(add_ros_executable target_name source_file)
  add_executable(${target_name} ${source_file})
  target_link_libraries(${target_name} cpp_pkg_lib)
  ament_target_dependencies(${target_name}
    rclcpp rclcpp_action std_msgs example_interfaces)
  install(TARGETS ${target_name} DESTINATION lib/${PROJECT_NAME})
endmacro()

add_ros_executable(topic_pub src/topic_publisher.cpp)
add_ros_executable(topic_sub src/topic_subscriber.cpp)
add_ros_executable(service_server src/service_server.cpp)
add_ros_executable(service_client src/service_client.cpp)
add_ros_executable(action_server src/action_server.cpp)
add_ros_executable(action_client src/action_client.cpp)
add_ros_executable(param_node src/param_node.cpp)
add_ros_executable(benchmark_node src/benchmark_node.cpp)

enable_testing()
add_executable(cpp_pkg_test tests/test_greet.cpp)
target_link_libraries(cpp_pkg_test PRIVATE cpp_pkg_lib)
add_test(NAME cpp_pkg_test COMMAND cpp_pkg_test)

ament_package()
