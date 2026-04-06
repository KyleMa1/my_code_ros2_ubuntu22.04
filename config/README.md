# CycloneDDS 配置说明

本目录包含 ROS 2 CycloneDDS 中间件的性能优化配置，主要面向本机 benchmark 场景。

## 文件说明

| 文件 | 用途 |
|---|---|
| `cyclonedds.xml` | CycloneDDS 运行时配置 |
| `setup_dds.sh` | 环境变量加载脚本 |
| `90-cyclonedds.conf` | Linux 内核 sysctl 持久化参数 |

## 快速使用

### 1. 安装内核参数（一次性，重启后依然生效）

```bash
sudo cp config/90-cyclonedds.conf /etc/sysctl.d/
sudo sysctl --system
```

验证生效：

```bash
cat /proc/sys/net/core/rmem_max   # 应输出 8388608
```

### 2. 加载 DDS 配置（每个终端会话执行一次）

```bash
source config/setup_dds.sh
```

脚本会设置以下环境变量：

- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`
- `CYCLONEDDS_URI=file://<绝对路径>/cyclonedds.xml`

### 3. 运行 benchmark

```bash
python3 benchmarks/run_benchmark.py
```

## cyclonedds.xml 配置详解

### 网络层

| 参数 | 值 | 说明 |
|---|---|---|
| NetworkInterface | `lo` | 仅使用 loopback 接口，排除外部网络干扰 |
| AllowMulticast | `spdp` | 仅在参与者发现阶段使用组播 |
| MaxMessageSize | `65500B` | 最大化单条 UDP 消息尺寸 |
| FragmentSize | `4000B` | 分片大小 |

### 内部参数

| 参数 | 值 | 说明 |
|---|---|---|
| SocketReceiveBufferSize | `1MB` | 增大收包缓冲（默认 208KB，需配合内核参数） |
| SocketSendBufferSize | `1MB` | 增大发包缓冲 |
| WhcHigh | `500kB` | 写入历史缓存高水位，减少 reliable 模式背压 |
| WriterLingerDuration | `0ms` | 数据立即发送，不等待合并 |
| NackDelay | `0ms` | 丢包时立即响应 NACK，加快重传 |
| PreEmptiveAckDelay | `0ms` | 取消预防性 ACK 延迟 |
| MultipleReceiveThreads | `true` | 启用多线程收包，降低延迟 |

### 发现

| 参数 | 值 | 说明 |
|---|---|---|
| ParticipantIndex | `auto` | 自动分配参与者索引 |
| MaxAutoParticipantIndex | `100` | 最大支持 100 个参与者 |

## 内核参数说明 (90-cyclonedds.conf)

| 参数 | 值 | 默认值 | 说明 |
|---|---|---|---|
| `net.core.rmem_max` | 8MB | 208KB | socket 接收缓冲区上限 |
| `net.core.wmem_max` | 8MB | 208KB | socket 发送缓冲区上限 |
| `net.core.rmem_default` | 1MB | 208KB | socket 接收缓冲区默认值 |
| `net.core.wmem_default` | 1MB | 208KB | socket 发送缓冲区默认值 |

> CycloneDDS 的 `SocketReceiveBufferSize` 受 `rmem_max` 限制，若不提升内核上限，XML 中设置的 1MB 会被截断至 208KB。

## 切换回默认配置

```bash
unset CYCLONEDDS_URI
```

## 用于实际部署（非 loopback）

如需在多机间通信，将 `cyclonedds.xml` 中的网络接口改为实际网卡：

```xml
<Interfaces>
  <NetworkInterface name="wlo1" multicast="true"/>
</Interfaces>
```
