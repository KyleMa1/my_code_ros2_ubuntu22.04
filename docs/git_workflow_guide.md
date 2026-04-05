# Git 工作流与提交规范指南

> 仓库：<https://github.com/KyleMa1/my_code_ros2_ubuntu22.04>
> 日期：2026-04-05

## 基本概念

### Git 的三个区域

```
工作区（Working Directory）     暂存区（Staging Area）     本地仓库（Repository）     远程仓库（Remote）
    你编辑的文件          ──add──>    准备提交的快照    ──commit──>   本地提交历史    ──push──>   GitHub
                         <─restore─                   <──reset──                  <──pull──
```

### 一次完整的提交流程

```bash
git add -A                    # 1. 把所有改动放入暂存区
git commit -m "feat: 新功能"   # 2. 把暂存区的内容生成一个提交（本地）
git push origin 260405_dev    # 3. 把本地提交推送到 GitHub
```

`git-tool.sh` 的选项 `1) 一键 push` 就是把这三步合成一步。

---

## Commit 信息规范

### 格式

```
<类型>: <简短描述>
```

一行搞定。如果需要详细说明，空一行写正文：

```
<类型>: <简短描述>

- 详细说明第一点
- 详细说明第二点
```

### 类型（Type）

| 类型 | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: 添加 Velodyne 点云订阅节点` |
| `fix` | 修复 bug | `fix: 修复 CAN 帧解析溢出` |
| `docs` | 文档变更 | `docs: 更新 Docker 部署文档` |
| `refactor` | 重构（不改功能） | `refactor: 拆分 publisher 为独立模块` |
| `test` | 添加/修改测试 | `test: 为 Modbus 客户端添加单元测试` |
| `chore` | 构建/工具/依赖 | `chore: 升级 Rust 到 1.85` |
| `style` | 格式调整（不改逻辑） | `style: 统一缩进为 4 空格` |
| `perf` | 性能优化 | `perf: 点云处理改用零拷贝` |
| `init` | 初始化 | `init: 企业级工作空间初始化` |

### 好的 vs 不好的 Commit 信息

```
❌ 不好的：
  "update"
  "修改了一些东西"
  "fix bug"
  "1"
  "asdf"

✅ 好的：
  "feat: 添加 RS-485 Modbus RTU 通信节点"
  "fix: 修复订阅者回调中的内存泄漏"
  "docs: 添加 EtherCAT 硬件接口说明"
  "chore: Dockerfile 升级 ROS Humble 基础镜像"
```

### 规则

1. **用中文或英文都行**，但同一项目保持一致
2. **简短描述不超过 50 个字**
3. **不加句号**
4. **用祈使语气**：写"添加"而不是"添加了"

---

## 分支管理

### 分支命名规范

```
<日期>_<类型>       例：260405_dev
<功能名>            例：velodyne_driver
<类型>/<描述>       例：feature/can-node, fix/memory-leak
```

### 常见分支策略

```
main（或 master）
  │
  ├── 260405_dev        ← 你当前的开发分支
  │     │
  │     ├── 日常开发、提交
  │     │
  │     └── 稳定后 → merge 回 main
  │
  ├── feature/xxx       ← 新功能分支
  │
  └── fix/xxx           ← 修复分支
```

### 日常操作

```bash
# 创建新分支
git checkout -b feature/velodyne

# 切换分支
git checkout 260405_dev

# 查看所有分支
git branch -a

# 合并分支（先切到目标分支）
git checkout main
git merge 260405_dev

# 删除分支（合并后）
git branch -d feature/velodyne
```

---

## git-tool.sh 功能速查

```bash
cd ~/rust_ws
./scripts/git-tool.sh
```

### 日常操作

| 选项 | 功能 | 对应 git 命令 |
|------|------|--------------|
| 1 | 一键 push | `git add -A && git commit && git push` |
| 2 | 切换/新建分支 | `git checkout` / `git checkout -b` |
| 3 | 拉取更新 | `git pull` |

### 查看差分

| 选项 | 功能 | 对应 git 命令 |
|------|------|--------------|
| 4 | 工作区改动 | `git diff` |
| 5 | 暂存区改动 | `git diff --cached` |
| 6 | 提交历史 | `git log --oneline --graph` |
| 7 | 对比两个提交 | `git diff <A> <B>` |

### 回退操作

| 选项 | 功能 | 危险等级 | 对应 git 命令 |
|------|------|---------|--------------|
| 8 | 撤销工作区改动 | 中 | `git checkout -- <file>` |
| 9 | 软回退 | 低（保留改动） | `git reset --soft <hash>` |
| 10 | 硬回退 | **高（丢弃改动）** | `git reset --hard <hash>` |
| 11 | 回滚提交 | 低（生成反向提交） | `git revert <hash>` |

### 回退方式怎么选

```
想撤销最近的改动，还没 commit？
  └── 选 8：撤销工作区改动

想撤销最近的 commit，但保留代码？
  └── 选 9：软回退

想撤销最近的 commit，代码也不要了？
  └── 选 10：硬回退（不可恢复！）

已经 push 到远程，想安全回退？
  └── 选 11：回滚（生成反向提交，不改历史）
```

---

## SSH 认证

本仓库使用 SSH 方式连接 GitHub，无需每次输密码。

### 配置信息

```
远程地址：git@github.com:KyleMa1/my_code_ros2_ubuntu22.04.git
SSH 密钥：~/.ssh/id_ed25519
公钥位置：~/.ssh/id_ed25519.pub
```

### 测试连接

```bash
ssh -T git@github.com
# 应输出：Hi KyleMa1! You've successfully authenticated...
```

### 换电脑后怎么办

1. 在新电脑生成 SSH 密钥：`ssh-keygen -t ed25519 -C "a13842028269@163.com"`
2. 复制公钥：`cat ~/.ssh/id_ed25519.pub`
3. 添加到 GitHub：Settings → SSH and GPG keys → New SSH key
4. 克隆仓库：`git clone git@github.com:KyleMa1/my_code_ros2_ubuntu22.04.git`

---

## 常见问题

### Q: commit 信息写错了怎么办？

还没 push 的话：

```bash
git commit --amend -m "新的信息"
```

已经 push 了就不要改了，直接提一个新 commit。

### Q: 不小心 commit 了不该提交的文件？

```bash
# 从暂存区移除（文件保留）
git reset HEAD <文件>

# 如果已经 commit 了，软回退
git reset --soft HEAD~1
# 然后修改后重新 commit
```

### Q: push 被拒绝（rejected）？

说明远程有新的提交你本地没有：

```bash
git pull --rebase origin 260405_dev
git push origin 260405_dev
```

### Q: 想看某个文件的修改历史？

```bash
git log --oneline -- src/rust_pkg/src/lib.rs
```

### Q: 想看某次 commit 改了什么？

```bash
git show <commit-hash>
```
