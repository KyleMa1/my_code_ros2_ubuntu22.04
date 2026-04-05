"""示例 launch 文件 — 可根据实际需要修改。"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),

        Node(
            package='examples_rclrs_minimal_pub_sub',
            executable='minimal_publisher',
            name='rust_publisher',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }],
            output='screen',
        ),

        Node(
            package='examples_rclrs_minimal_pub_sub',
            executable='minimal_subscriber',
            name='rust_subscriber',
            parameters=[{
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            }],
            output='screen',
        ),
    ])
