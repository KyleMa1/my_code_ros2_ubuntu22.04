cmake_minimum_required(VERSION 3.20)
project(cpp_pkg VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_library(cpp_pkg src/cpp_pkg.cpp)
target_include_directories(cpp_pkg PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

enable_testing()

add_executable(cpp_pkg_test tests/test_greet.cpp)
target_link_libraries(cpp_pkg_test PRIVATE cpp_pkg)
add_test(NAME cpp_pkg_test COMMAND cpp_pkg_test)
