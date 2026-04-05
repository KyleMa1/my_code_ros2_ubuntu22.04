# colcon build --symlink-install 详解

> 环境：ROS 2 Humble + colcon
> 日期：2026-04-05

## 核心区别

`colcon build` 安装到 `install/` 目录时，有两种方式：

### 默认模式（复制）

```
src/py_pkg/__init__.py  ──复制──>  install/py_pkg/lib/python3/py_pkg/__init__.py
```

`install/` 里是源文件的**独立副本**，改了源码必须重新 build 才能生效。

### --symlink-install 模式（符号链接）

```
src/py_pkg/__init__.py  <──软链接──  install/py_pkg/lib/python3/py_pkg/__init__.py
```

`install/` 里是指向源文件的**符号链接**，改了源码立即生效，无需重新编译。

## 对比表

| 场景                 | 默认（复制）     | `--symlink-install`（链接）              |
| -------------------- | ---------------- | ---------------------------------------- |
| 修改 Python 脚本     | 需要重新 build   | **立即生效**                             |
| 修改 launch 文件     | 需要重新 build   | **立即生效**                             |
| 修改 yaml 参数文件   | 需要重新 build   | **立即生效**                             |
| 修改 C++ / Rust 源码 | 需要重新 build   | 仍需重新 build（编译型语言必须重新编译） |
| 磁盘占用             | 较大（两份文件） | 较小（只有链接）                         |
| 部署 / 发布          | 适合（独立完整） | 不适合（链接指向 src，离开工作空间会断） |

## 什么时候用哪个

```
日常开发  →  colcon build --symlink-install  （改脚本不用反复编译）
CI / 部署 →  colcon build                    （install/ 目录独立完整）
```

本工作空间的 Makefile 已配置为 `--symlink-install`：

```makefile
build:
	source /opt/ros/humble/setup.bash && \
	colcon build --symlink-install --allow-overriding ...
```

日常开发直接 `make build` 即可。

## 常见问题

### Q: 混用两种模式会怎样？

会出现符号链接冲突错误：

```
failed to create symbolic link '...' because existing path cannot be removed: Is a directory
```

默认模式创建的是真实目录，`--symlink-install` 模式需要在同一路径创建符号链接，无法覆盖目录。

**解决方法**：清除冲突包的构建缓存后重新编译。

```bash
# 清除单个包
rm -rf build/<包名> install/<包名>

# 或者全部清除
make clean    # 等同于 rm -rf build/ install/ log/
```

### Q: 一键清除所有有冲突的包？

```bash
for pkg in build/*/ament_cmake_python; do
  pkg_dir=$(dirname "$pkg")
  pkg_name=$(basename "$pkg_dir")
  target="${pkg_dir}/ament_cmake_python/${pkg_name}/${pkg_name}"
  if [ -d "$target" ] && [ ! -L "$target" ]; then
    echo "清除: ${pkg_name}"
    rm -rf "build/${pkg_name}" "install/${pkg_name}"
  fi
done
```

这段脚本会检查 `build/` 下每个包：如果该路径是真实目录（不是符号链接），说明是旧模式的残留，自动清除。

### Q: --symlink-install 对编译型语言（C++ / Rust）有用吗？

有用，但好处不在源码层面：

- **C++ / Rust 源码**：改了仍然需要重新编译，符号链接帮不了
- **但其附带的非编译文件会受益**：
  - `package.xml`
  - `launch/` 文件
  - `config/` 参数文件
  - `msg/srv/action` 接口定义文件

所以即使是纯 C++ 包，`--symlink-install` 在修改 launch 和配置文件时也能省去重新 build 的步骤。

### Q: 为什么 CI 不用 --symlink-install？

CI 环境中 `install/` 目录可能需要打包为 artifact 或部署到其他机器。符号链接指向的是构建机器上的 `src/` 路径，复制到别的机器后链接会断裂。默认的复制模式保证 `install/` 目录是完全独立的。

## 总结

```
                     改 Python/launch/yaml    改 C++/Rust     部署场景
                     ──────────────────────   ────────────   ──────────
--symlink-install     ✅ 立即生效              ❌ 仍需编译     ❌ 链接会断
默认（复制）            ❌ 需要重新 build        ❌ 仍需编译     ✅ 独立完整
```

**结论**：开发环境统一使用 `--symlink-install`，CI/部署使用默认模式。切勿混用。
