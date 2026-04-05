# ══════════════════════════════════════════════════════════
#  rust_ws — 统一构建入口
#  用法: make <target>
# ══════════════════════════════════════════════════════════

SHELL := /bin/bash
.DEFAULT_GOAL := help

ROS_DISTRO   ?= humble
DOCKER_IMAGE ?= rust_ws:humble-dev

COLCON_OVERRIDES := \
	action_msgs builtin_interfaces common_interfaces \
	composition_interfaces diagnostic_msgs example_interfaces \
	geometry_msgs lifecycle_msgs nav_msgs rcl_interfaces \
	rosgraph_msgs rosidl_default_generators rosidl_default_runtime \
	sensor_msgs sensor_msgs_py shape_msgs statistics_msgs \
	std_msgs std_srvs stereo_msgs test_msgs trajectory_msgs \
	unique_identifier_msgs visualization_msgs

# ── 帮助 ─────────────────────────────────────────────────
.PHONY: help
help: ## 显示此帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── 构建 ─────────────────────────────────────────────────
.PHONY: build
build: ## colcon 全量构建
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	colcon build --symlink-install --allow-overriding $(COLCON_OVERRIDES)

.PHONY: build-pkg
build-pkg: ## 构建单个包: make build-pkg PKG=rust_pkg
	@if [ -z "$(PKG)" ]; then echo "用法: make build-pkg PKG=<包名>"; exit 1; fi
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	colcon build --symlink-install --packages-select $(PKG)

.PHONY: build-up-to
build-up-to: ## 构建某个包及其依赖: make build-up-to PKG=rust_pkg
	@if [ -z "$(PKG)" ]; then echo "用法: make build-up-to PKG=<包名>"; exit 1; fi
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	colcon build --symlink-install --packages-up-to $(PKG)

# ── 测试 ─────────────────────────────────────────────────
.PHONY: test
test: ## colcon 全量测试
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	source install/setup.bash && \
	colcon test && \
	colcon test-result --verbose

.PHONY: test-pkg
test-pkg: ## 测试单个包: make test-pkg PKG=rust_pkg
	@if [ -z "$(PKG)" ]; then echo "用法: make test-pkg PKG=<包名>"; exit 1; fi
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	source install/setup.bash && \
	colcon test --packages-select $(PKG) && \
	colcon test-result --verbose

# ── 清理 ─────────────────────────────────────────────────
.PHONY: clean
clean: ## 清理 build/ install/ log/
	rm -rf build/ install/ log/
	@echo "已清理 build/ install/ log/"

# ── Docker ───────────────────────────────────────────────
.PHONY: docker-build
docker-build: ## 构建 Docker 镜像
	docker compose build

.PHONY: docker-dev
docker-dev: ## 启动 Docker 开发环境
	docker compose run --rm dev

.PHONY: docker-run-build
docker-run-build: ## 在 Docker 中执行完整构建+测试
	docker compose run --rm build

.PHONY: docker-down
docker-down: ## 停止并清理 Docker 容器
	docker compose down

# ── 依赖 ─────────────────────────────────────────────────
.PHONY: deps-import
deps-import: ## 导入 ros2_rust 依赖仓库 (vcs import)
	vcs import src < src/ros2_rust/ros2_rust_humble.repos

.PHONY: deps-update
deps-update: ## 更新所有 vcs 管理的仓库
	vcs pull src

# ── Git ──────────────────────────────────────────────────
.PHONY: git-tool
git-tool: ## 启动 Git 交互式管理工具
	./scripts/git-tool.sh

# ── Benchmark ────────────────────────────────────────────
.PHONY: benchmark
benchmark: ## 运行三语言 Benchmark (需先 build)
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	source install/setup.bash && \
	python3 benchmarks/run_benchmark.py --skip-build-time

.PHONY: benchmark-full
benchmark-full: ## 运行完整 Benchmark (含编译时间测量)
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	source install/setup.bash && \
	python3 benchmarks/run_benchmark.py

.PHONY: benchmark-quick
benchmark-quick: ## 快速 Benchmark (减少迭代次数)
	source /opt/ros/$(ROS_DISTRO)/setup.bash && \
	source install/setup.bash && \
	python3 benchmarks/run_benchmark.py --skip-build-time \
		--topic-iters=500 --service-iters=200 --param-iters=10000

# ── 代码质量 ─────────────────────────────────────────────
.PHONY: lint
lint: ## 运行代码格式检查
	@echo "── Python ──"
	cd src/py_pkg && python3 -m flake8 py_pkg/ tests/ || true
	@echo "── Rust ──"
	cd src/rust_pkg && cargo fmt --check || true
	cd src/rust_pkg && cargo clippy || true
	@echo "── C++ ──"
	@find src/cpp_pkg -name '*.cpp' -o -name '*.h' | head -20 | \
		xargs clang-format --dry-run -Werror 2>/dev/null || \
		echo "  clang-format 未安装，跳过"

.PHONY: fmt
fmt: ## 自动格式化代码
	@echo "── Python ──"
	cd src/py_pkg && python3 -m black py_pkg/ tests/ 2>/dev/null || echo "  black 未安装，跳过"
	@echo "── Rust ──"
	cd src/rust_pkg && cargo fmt || true
	@echo "── C++ ──"
	@find src/cpp_pkg -name '*.cpp' -o -name '*.h' | head -20 | \
		xargs clang-format -i 2>/dev/null || echo "  clang-format 未安装，跳过"
