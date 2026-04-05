# Changelog

本文件记录所有重要变更，格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added
- Docker 企业级开发环境（Dockerfile, docker-compose.yml）
- GitHub Actions CI/CD 流水线
- Makefile 统一构建入口
- Git 交互式管理工具（scripts/git-tool.sh）
- ROS 2 Rust (rclrs) 集成
- 示例 launch 文件和参数配置
- 文档：Docker 开发指南、硬件接口指南、ROS 2 Rust 安装指南

### Structure
- `src/py_pkg/` — Python 包
- `src/cpp_pkg/` — C++ 包
- `src/rust_pkg/` — Rust 包
- `src/ros2_rust/` — ros2_rust 库

---

<!--
版本发布模板：

## [0.1.0] - 2026-XX-XX

### Added
- 新功能

### Changed
- 修改

### Fixed
- 修复

### Removed
- 删除
-->
