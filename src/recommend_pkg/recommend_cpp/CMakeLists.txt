cmake_minimum_required(VERSION 3.20)
project(recommend_cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

macro(add_ros_executable target_name source_file)
  add_executable(${target_name} ${source_file})
  ament_target_dependencies(${target_name} rclcpp std_msgs geometry_msgs)
  install(TARGETS ${target_name} DESTINATION lib/${PROJECT_NAME})
endmacro()

add_ros_executable(sensor_driver src/sensor_driver.cpp)
add_ros_executable(motor_controller src/motor_controller.cpp)

ament_package()
