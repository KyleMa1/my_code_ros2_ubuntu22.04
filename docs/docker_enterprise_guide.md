# Docker 企业级开发指南

> 仓库：<https://github.com/KyleMa1/my_code_ros2_ubuntu22.04>
> 环境：Ubuntu 22.04 + ROS 2 Humble + Rust 1.85
> 日期：2026-04-05

## 概述

本工作空间采用 **Git + Docker + GitHub Actions** 的企业级工作流：

| 工具 | 职责 | 对应文件 |
|------|------|----------|
| **Git / GitHub** | 源代码版本管理、协作、Code Review | `.git/`, GitHub PR |
| **Docker** | 开发环境标准化（OS + ROS + Rust + 工具链） | `Dockerfile`, `docker-compose.yml` |
| **GitHub Actions** | 自动化构建 & 测试（CI/CD） | `.github/workflows/ci.yml` |

核心理念：**Infrastructure as Code** — 不仅代码有版本，运行环境也有版本，谁来都能一键复现。

## 目录结构

```
rust_ws/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI/CD 流水线
├── docker/
│   └── entrypoint.sh           # 容器启动脚本（自动 source ROS 环境）
├── docs/
│   ├── docker_enterprise_guide.md   # ← 你正在看的这个文件
│   └── ros2_rust_setup.md           # 手动安装指南（参考用）
├── src/
│   ├── py_pkg/                 # Python 包
│   ├── cpp_pkg/                # C++ 包
│   ├── rust_pkg/               # Rust 包
│   ├── ros2_rust/              # ros2_rust 库
│   └── ...                     # 其他 ROS 2 依赖
├── Dockerfile                  # 开发环境定义
├── docker-compose.yml          # 一键启动配置
├── .gitignore                  # Git 忽略规则
├── .dockerignore               # Docker 构建忽略规则
└── README.md
```

## 前置条件

- 安装 [Docker Engine](https://docs.docker.com/engine/install/ubuntu/)
- 安装 [Docker Compose](https://docs.docker.com/compose/install/)（Docker Desktop 自带）

```bash
# 验证安装
docker --version
docker compose version
```

## 快速开始（新同事入职只需 3 步）

### 第一步：克隆仓库

```bash
git clone https://github.com/KyleMa1/my_code_ros2_ubuntu22.04.git
cd my_code_ros2_ubuntu22.04
```

### 第二步：构建 Docker 镜像

```bash
docker compose build
```

首次构建约 10-15 分钟（安装 ROS、Rust、colcon 插件等），之后有缓存会很快。

### 第三步：启动开发环境

```bash
docker compose run --rm dev
```

进入容器后，环境一切就绪，直接开始编译：

```bash
source /opt/ros/humble/setup.bash
vcs import src < src/ros2_rust/ros2_rust_humble.repos
colcon build --allow-overriding \
  action_msgs builtin_interfaces common_interfaces \
  composition_interfaces diagnostic_msgs example_interfaces \
  geometry_msgs lifecycle_msgs nav_msgs rcl_interfaces \
  rosgraph_msgs rosidl_default_generators rosidl_default_runtime \
  sensor_msgs sensor_msgs_py shape_msgs statistics_msgs \
  std_msgs std_srvs stereo_msgs test_msgs trajectory_msgs \
  unique_identifier_msgs visualization_msgs
```

## 日常开发工作流

### 启动 / 进入开发容器

```bash
# 启动并进入容器（退出后自动删除容器）
docker compose run --rm dev

# 或者后台启动，再 exec 进入（容器保持运行）
docker compose up -d dev
docker compose exec dev bash
```

### 在容器内编辑代码

代码通过 `volumes` 挂载，本地和容器内是**同一份文件**：
- 在宿主机用 VSCode / Cursor 编辑 → 容器内立即可见
- 在容器内编译测试 → 宿主机文件不受影响

### 一键构建 + 测试

```bash
docker compose run --rm build
```

### 停止并清理

```bash
docker compose down
```

## CI/CD：GitHub Actions

每次 `git push` 到 `main` 分支或创建 Pull Request 时，GitHub Actions 会自动：

1. 在 `ros:humble` 容器中拉起环境
2. 安装 Rust + colcon 插件
3. 执行 `colcon build` 构建
4. 执行 `colcon test` 测试
5. 报告结果（在 PR 页面可直接看到 ✅ / ❌）

配置文件：`.github/workflows/ci.yml`

无需任何手动操作，push 即触发。

## 对比：有 Docker vs 无 Docker

| | 无 Docker（手动） | 有 Docker（企业级） |
|---|---|---|
| **新人上手** | 按 `ros2_rust_setup.md` 一步步走，容易出错 | `git clone` + `docker compose run --rm dev`，3 分钟搞定 |
| **环境一致性** | 每台机器可能不同 | 100% 一致，Dockerfile 锁定版本 |
| **CI/CD** | 无 | 每次 push 自动构建测试 |
| **团队协作** | "在我电脑上能跑" | 在所有人电脑上都能跑 |
| **环境隔离** | 依赖可能和系统冲突 | 容器隔离，不污染宿主机 |

## 常见问题

### Q: 容器里修改的文件会丢失吗？

不会。`src/` 目录通过 `volumes` 挂载，容器内外是同一份文件。只有容器**内部**独有的文件（如 `/tmp` 下的临时文件）会在容器删除后丢失。

### Q: 我还需要在本地装 ROS / Rust 吗？

不需要。Docker 容器里已经包含了所有依赖。你本地只需要安装 Docker 和你喜欢的编辑器。

### Q: 构建很慢怎么办？

- 首次构建慢是正常的（需要下载基础镜像 + 编译依赖）
- 后续构建有 Docker 层缓存，只有改动的层才重新构建
- 可以把构建好的镜像推送到 GitHub Container Registry，团队共享：

```bash
docker tag rust_ws:humble-dev ghcr.io/kylema1/my_code_ros2_ubuntu22.04:humble-dev
docker push ghcr.io/kylema1/my_code_ros2_ubuntu22.04:humble-dev
```

### Q: 怎么在容器里用 GUI（如 RViz）？

```bash
# 允许 Docker 访问宿主机 X Server
xhost +local:docker

# 启动时传入显示变量
docker compose run --rm -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix dev
```

### Q: GitHub Actions 和 Docker 什么关系？

GitHub Actions 的 CI 流水线本身就跑在容器里（`image: ros:humble`）。它复现了你 Dockerfile 里定义的环境，确保"能在 CI 里跑 = 能在所有人机器上跑"。
