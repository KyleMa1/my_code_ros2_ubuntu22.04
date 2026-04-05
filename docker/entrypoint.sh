#!/bin/bash
set -e

source "/opt/ros/$ROS_DISTRO/setup.bash" --

if [ -f "/tmp/rosidl_rust_overlay/install/setup.bash" ]; then
  source /tmp/rosidl_rust_overlay/install/setup.bash --
fi

if [ -f "/ws/install/setup.bash" ]; then
  source /ws/install/setup.bash --
fi

exec "$@"
