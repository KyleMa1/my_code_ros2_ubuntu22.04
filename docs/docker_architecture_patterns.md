# Docker 架构模式：整体 vs 独立 vs 混合

> 环境：ROS 2 Humble + colcon
> 日期：2026-04-05

## 三种常见模式

### 模式一：整个 WS 一个 Docker

```
rust_ws/
├── Dockerfile           ← 一个镜像，包含所有依赖
├── docker-compose.yml
└── src/
    ├── py_pkg/
    ├── cpp_pkg/
    └── rust_pkg/
```

所有包共享同一个容器环境，`colcon build` 一次编译全部包。

**优点**：
- 开发体验最好，一个环境全搞定
- 包间依赖天然支持（msg/srv 直接引用）
- `colcon build` 能看到完整依赖图

**缺点**：
- 镜像较大（全家桶）
- 一个节点崩溃可能影响整个环境
- 所有人共享同一套依赖版本

**适合**：开发阶段、原型验证、小团队、包间有编译依赖。

---

### 模式二：每个 PKG 独立 Docker（微服务模式）

```
rust_ws/
├── docker-compose.yml     ← 编排所有服务
└── src/
    ├── py_pkg/
    │   └── Dockerfile     ← 只装 Python 依赖
    ├── cpp_pkg/
    │   └── Dockerfile     ← 只装 C++ 依赖
    └── rust_pkg/
        └── Dockerfile     ← 只装 Rust 依赖
```

docker-compose.yml：

```yaml
services:
  py_node:
    build: src/py_pkg
    network_mode: host
    command: ros2 run py_pkg my_node

  cpp_node:
    build: src/cpp_pkg
    network_mode: host
    command: ros2 run cpp_pkg my_node

  rust_node:
    build: src/rust_pkg
    network_mode: host
    command: ros2 run rust_pkg my_node
```

每个节点运行在独立容器中，通过 ROS 2 DDS 通信。

**优点**：
- 故障隔离（一个崩不影响其他）
- 镜像小，各取所需
- 可以独立更新、独立扩缩容
- 不同节点可用不同基础镜像

**缺点**：
- 开发调试麻烦（跨容器日志、通信排查）
- 消息包（msg/srv）需要每个镜像都装，或做基础镜像
- 无法用 `colcon build` 一次编译

**适合**：生产部署、大团队分组开发、节点间无编译依赖。

---

### 模式三：混合模式（推荐的企业做法）

```
rust_ws/
├── Dockerfile                ← 开发用：全家桶镜像
├── docker-compose.yml        ← 开发用：单容器
├── docker-compose.prod.yml   ← 部署用：多容器
└── src/
    ├── py_pkg/
    │   └── Dockerfile        ← 部署用：最小镜像
    ├── cpp_pkg/
    │   └── Dockerfile
    └── rust_pkg/
        └── Dockerfile
```

开发和部署使用不同的配置：

```bash
# 开发环境（全家桶，方便调试）
docker compose up dev

# 生产部署（每个节点独立，故障隔离）
docker compose -f docker-compose.prod.yml up
```

**这是企业里最常见的做法**：开发追求效率，部署追求稳定。

---

## 对比表

| | 整体 Docker | 独立 Docker | 混合模式 |
|---|---|---|---|
| **开发体验** | 最好 | 麻烦 | 最好（用整体） |
| **编译方式** | `colcon build` 一次搞定 | 每个包单独编译 | 开发整体，部署独立 |
| **包间依赖** | 天然支持 | 需跨容器 DDS 通信 | 开发时天然支持 |
| **msg/srv 共享** | 直接引用 | 每个镜像都要装 | 开发直接引用 |
| **故障隔离** | 无 | 完全隔离 | 部署时隔离 |
| **镜像大小** | 大 | 小 | 开发大，部署小 |
| **独立更新** | 全部重新部署 | 单个节点更新 | 部署时单个更新 |
| **复杂度** | 低 | 中 | 高（两套配置） |
| **适合阶段** | 开发/原型 | 生产/大团队 | 全生命周期 |

---

## 消息包（msg/srv）共享策略

独立 Docker 模式下，最大的痛点是消息包共享。常见解决方案：

### 方案 A：基础镜像分层

```dockerfile
# 基础镜像：包含所有消息定义
FROM ros:humble AS msgs-base
COPY src/my_msgs /ws/src/my_msgs
RUN cd /ws && colcon build --packages-select my_msgs
```

```dockerfile
# 各节点镜像：基于 msgs-base
FROM msgs-base AS py-node
COPY src/py_pkg /ws/src/py_pkg
RUN cd /ws && colcon build --packages-select py_pkg
```

### 方案 B：预编译消息包发布到私有仓库

```bash
# 把消息包编译为 deb 或 pip 包，推送到私有 apt/pip 仓库
# 各节点镜像直接 apt install / pip install
```

### 方案 C：使用 ROS 2 标准消息

尽量使用 `std_msgs`、`sensor_msgs`、`geometry_msgs` 等官方消息类型，避免自定义消息的分发问题。

---

## 决策流程

```
你的项目处于什么阶段？
│
├── 个人开发 / 原型验证 / 小团队（< 5人）
│   └── 模式一：整体 Docker ✅
│       （你当前的选择，正确）
│
├── 中型团队（5-20人）/ 多模块并行开发
│   └── 模式三：混合模式 ✅
│       （开发用整体，部署用独立）
│
└── 大型项目 / 微服务架构 / 生产环境
    └── 模式二或三：独立 Docker ✅
        （每个节点独立镜像，CI/CD 独立流水线）
```

---

## 本工作空间的现状与演进路径

### 现在（模式一 — 整体）

```yaml
# docker-compose.yml
services:
  dev:
    build: .
    volumes:
      - .:/ws
    network_mode: host
```

适合当前阶段：`rclrs`、`std_msgs` 等消息包是编译时依赖，拆开会非常麻烦。

### 未来（演进到模式三 — 混合）

当项目增长到需要独立部署时，添加 `docker-compose.prod.yml`：

```yaml
# docker-compose.prod.yml
services:
  publisher:
    build:
      context: .
      dockerfile: src/rust_pkg/Dockerfile
    network_mode: host
    command: ros2 run rust_pkg my_publisher
    restart: unless-stopped

  subscriber:
    build:
      context: .
      dockerfile: src/py_pkg/Dockerfile
    network_mode: host
    command: ros2 run py_pkg my_subscriber
    restart: unless-stopped
```

**不需要现在就做**，等项目规模到了再拆分，避免过度设计。
