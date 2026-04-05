# my_code_ros2_ubuntu22.04 — Multi-Language ROS 2 Workspace

[![CI](https://github.com/KyleMa1/my_code_ros2_ubuntu22.04/actions/workflows/ci.yml/badge.svg)](https://github.com/KyleMa1/my_code_ros2_ubuntu22.04/actions)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

ROS 2 Humble 工作空间，包含 Python、C++ 和 Rust 包。

## 目录结构

```
.
├── .github/workflows/ci.yml    # GitHub Actions CI/CD
├── .vscode/                    # 编辑器统一配置
├── configs/
│   ├── launch/                 # ROS 2 launch 文件
│   └── params/                 # 参数 YAML
├── docker/
│   └── entrypoint.sh           # 容器启动脚本
├── docs/                       # 文档
├── scripts/
│   └── git-tool.sh             # Git 交互式管理工具
├── src/
│   ├── py_pkg/                 # Python 包
│   ├── cpp_pkg/                # C++ 包
│   ├── rust_pkg/               # Rust 包
│   └── ros2_rust/              # ros2_rust 库
├── Dockerfile                  # 开发环境定义
├── docker-compose.yml          # 一键启动
├── Makefile                    # 统一构建入口
├── CHANGELOG.md                # 版本变更记录
└── LICENSE                     # Apache 2.0
```

## 快速开始（推荐：Docker）

```bash
git clone https://github.com/KyleMa1/my_code_ros2_ubuntu22.04.git
cd my_code_ros2_ubuntu22.04
make docker-build
make docker-dev
```

详细说明见 [Docker 企业级开发指南](docs/docker_enterprise_guide.md)。

## 快速开始（手动）

参考 [ROS 2 Rust 手动安装指南](docs/ros2_rust_setup.md)。

## 常用命令

```bash
make help           # 查看所有可用命令
make build          # colcon 全量构建
make build-pkg PKG=rust_pkg   # 构建单个包
make test           # 全量测试
make lint           # 代码格式检查
make fmt            # 自动格式化
make clean          # 清理构建产物
make git-tool       # Git 交互式管理
```

## 文档

| 文档 | 说明 |
|------|------|
| [Docker 企业级开发指南](docs/docker_enterprise_guide.md) | Docker 工作流、CI/CD、日常操作 |
| [Docker 硬件接口指南](docs/docker_hardware_interfaces.md) | RS232/485/CAN/Modbus/EtherCAT |
| [ROS 2 Rust 安装指南](docs/ros2_rust_setup.md) | 手动环境搭建步骤 |

## CI/CD

每次 push 到 `main` 或创建 PR，GitHub Actions 自动构建 & 测试。

配置：[.github/workflows/ci.yml](.github/workflows/ci.yml)

## License

[Apache License 2.0](LICENSE)
