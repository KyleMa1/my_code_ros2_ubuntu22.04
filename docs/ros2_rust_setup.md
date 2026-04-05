# ROS 2 Rust (rclrs) 安装指南

> 环境：Ubuntu 22.04 + ROS 2 Humble
> 日期：2026-04-05

## 前置条件

- ROS 2 Humble 已安装并可用（`/opt/ros/humble`）
- 已 source ROS 2 环境：`source /opt/ros/humble/setup.bash`

## 第一步：安装 Rust 工具链

apt 源中的 Rust（1.75）版本过旧，ros2_rust main 分支要求 **Rust >= 1.82**（使用了 `unsafe extern "C"` 语法）。需通过 rustup 安装最新稳定版。

```bash
# 如果之前通过 apt 安装了旧版 Rust，先卸载
apt-get remove -y rustc cargo

# 通过 USTC 镜像下载 rustup-init 并安装（加速国内下载）
export RUSTUP_DIST_SERVER=https://mirrors.ustc.edu.cn/rust-static
export RUSTUP_UPDATE_ROOT=https://mirrors.ustc.edu.cn/rust-static/rustup
curl --proto '=https' --tlsv1.2 -sSf \
  https://mirrors.ustc.edu.cn/rust-static/rustup/dist/x86_64-unknown-linux-gnu/rustup-init \
  -o /tmp/rustup-init
chmod +x /tmp/rustup-init
/tmp/rustup-init -y

# 加载 Rust 环境
source "$HOME/.cargo/env"

# 验证（应 >= 1.82）
rustc --version
cargo --version
```

## 第二步：安装系统依赖

```bash
apt-get update
apt-get install -y git libclang-dev python3-vcstool
```

## 第三步：安装 colcon Cargo 插件

colcon 默认不支持构建 `ament_cargo` 类型的包，需要安装插件：

```bash
pip install colcon-cargo colcon-ros-cargo
```

## 第四步：克隆 ros2_rust 到工作空间

```bash
cd /home/ma/rust_ws/src
git clone https://github.com/ros2-rust/ros2_rust.git
```

> **注意**：ros2_rust 已不存在 `humble` 分支，直接使用 `main` 分支即可。
> `main` 分支中包含 `ros2_rust_humble.repos` 文件用于拉取 Humble 兼容的依赖。

## 第五步：导入依赖仓库

```bash
cd /home/ma/rust_ws
vcs import src < src/ros2_rust/ros2_rust_humble.repos
```

此命令会自动克隆以下依赖仓库到 `src/` 下：

| 仓库 | 说明 |
|------|------|
| `ros2-rust/rosidl_rust` | Rust 消息生成器 |
| `ros2-rust/rosidl_runtime_rs` | Rust 消息运行时 |
| `ros2-rust/examples` | rclrs 示例节点 |
| `ros2/common_interfaces` | 标准消息接口 |
| `ros2/example_interfaces` | 示例接口 |
| `ros2/rcl_interfaces` | rcl 接口定义 |
| `ros2/test_interface_files` | 测试接口文件 |
| `ros2/rosidl_defaults` | rosidl 默认配置 |
| `ros2/unique_identifier_msgs` | UUID 消息类型 |

## 第六步：编译

```bash
cd /home/ma/rust_ws
source /opt/ros/humble/setup.bash
colcon build --allow-overriding \
  action_msgs builtin_interfaces common_interfaces \
  composition_interfaces diagnostic_msgs example_interfaces \
  geometry_msgs lifecycle_msgs nav_msgs rcl_interfaces \
  rosgraph_msgs rosidl_default_generators rosidl_default_runtime \
  sensor_msgs sensor_msgs_py shape_msgs statistics_msgs \
  std_msgs std_srvs stereo_msgs test_msgs trajectory_msgs \
  unique_identifier_msgs visualization_msgs
```

> `--allow-overriding` 参数用于允许覆盖 `/opt/ros/humble` 中已有的同名包。

首次编译耗时约 5 分钟，主要时间花在 `rosidl_runtime_rs` 和 `rclrs` 的 Rust 编译上。

## 第七步：验证

```bash
source /home/ma/rust_ws/install/setup.bash

# 查看 rclrs 相关包
ros2 pkg list | grep rclrs

# 查看可用的 Rust 示例节点
ros2 pkg executables | grep rclrs
```

预期输出中应包含：

```
examples_rclrs_minimal_pub_sub minimal_publisher
examples_rclrs_minimal_pub_sub minimal_subscriber
examples_rclrs_minimal_client_service minimal_client
examples_rclrs_minimal_client_service minimal_service
...
```

## 快速测试

打开两个终端：

**终端 1 — 运行 Subscriber：**

```bash
source /opt/ros/humble/setup.bash
source /home/ma/rust_ws/install/setup.bash
ros2 run examples_rclrs_minimal_pub_sub minimal_subscriber
```

**终端 2 — 运行 Publisher：**

```bash
source /opt/ros/humble/setup.bash
source /home/ma/rust_ws/install/setup.bash
ros2 run examples_rclrs_minimal_pub_sub minimal_publisher
```

## 常见问题

### Q: `No task extension to 'build' a 'ros.ament_cargo' package`

colcon 缺少 Cargo 构建插件，执行：

```bash
pip install colcon-cargo colcon-ros-cargo
```

### Q: `error: extern block cannot be declared unsafe`

Rust 版本过旧（< 1.82），需升级到最新稳定版。参见第一步。

### Q: `git checkout humble` 报错

ros2_rust 已不再维护独立的 `humble` 分支，直接使用 `main` 分支，其中已包含 `ros2_rust_humble.repos`。
