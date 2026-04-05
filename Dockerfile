ARG ROS_DISTRO=humble
FROM ros:${ROS_DISTRO} AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG RUST_VERSION=1.85.0

# ── 系统依赖 ──────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    curl \
    git \
    libclang-dev \
    python3-pip \
    python3-vcstool \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# ── Rust 工具链 ──────────────────────────────────────────
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
    | sh -s -- --default-toolchain ${RUST_VERSION} -y
ENV PATH="/root/.cargo/bin:${PATH}"

# ── colcon Cargo 插件 ────────────────────────────────────
RUN pip install --upgrade pytest \
    && pip install \
        git+https://github.com/colcon/colcon-cargo.git \
        git+https://github.com/colcon/colcon-ros-cargo.git

# ── rosidl_rust overlay (Humble 需要手动构建) ────────────
RUN mkdir -p /tmp/rosidl_rust_overlay/src \
    && git clone https://github.com/ros2-rust/rosidl_rust \
        /tmp/rosidl_rust_overlay/src \
    && cd /tmp/rosidl_rust_overlay \
    && . /opt/ros/${ROS_DISTRO}/setup.sh \
    && colcon build

# ── 工作空间 ─────────────────────────────────────────────
WORKDIR /ws

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
