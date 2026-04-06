# ROS2 高并发 Topic 的 QoS 调优实战

## 问题现象

在 ROS2 多语言 Benchmark 的高并发 Topic 测试中（4 线程 × 1000 条 = 4000 条消息），三种语言的消息接收率都远低于预期：

| 语言 | 发送 | 接收 | 丢失率 |
|------|------|------|--------|
| C++ | 4000 | 2039 | **49%** |
| Python | 4000 | 1626 | **59%** |
| Rust | 4000 | 46 | **99%** |

Rust 尤其严重——几乎全部丢失。

## 根因分析

### 1. QoS 深度不足（核心原因）

ROS2 的 Topic 通信基于 DDS（Data Distribution Service），发布和订阅各有一个消息队列（History）。默认 QoS 策略为：

```
History = KeepLast
Depth = 10        ← 只缓存最近 10 条！
Reliability = Reliable
```

当 4 个线程以微秒级速度暴发 4000 条消息时：
- 发布端队列溢出：深度 10 的 publisher 缓冲区被瞬间填满，旧消息被覆盖
- 订阅端队列溢出：subscriber 处理速度跟不上到达速度，新消息挤掉未处理的旧消息
- DDS Reliable 协议重传：虽然配置了 Reliable，但 KeepLast(10) 意味着发布端只保留最新 10 条用于重传，更早的消息已无法重传

### 2. 订阅端处理瓶颈（加剧因素）

| 语言 | Executor 类型 | 回调处理能力 |
|------|---------------|-------------|
| C++ | MultiThreadedExecutor | 多线程并行处理回调，速度快 |
| Python | MultiThreadedExecutor | 有 GIL 限制，实际串行 |
| Rust | BasicExecutor (单线程) | 严格串行，处理最慢 |

C++ 丢 49%（深度 2000 不够，但 Executor 快），Rust 丢 99%（深度 10 + 单线程 Executor 双重瓶颈）。

### 3. 跨 Context DDS 发现延迟（仅影响 Rust multi_node）

Rust 的多节点模式为每组 pub/sub 创建独立的 `rclrs::Context`（= 独立 DDS participant）。DDS 的 SPDP（Simple Participant Discovery Protocol）发现周期默认约 1 秒，导致 publisher 在 subscriber 尚未发现时就已经开始发送。

## 解决方案

### Step 1: 设置 QoS 深度匹配消息总量

**原则**：`KeepLast(depth)` 的 depth ≥ 预期的最大未处理消息数。

#### C++

```cpp
// 修复前
auto sub = node->create_subscription<String>("topic", rclcpp::QoS(2000), callback);
auto pub = node->create_publisher<String>("topic", rclcpp::QoS(2000));

// 修复后 — depth 匹配总消息数 + reliable 明确声明
int total_msgs = num_threads * msgs_per_thread;  // = 4000
auto sub = node->create_subscription<String>(
    "topic", rclcpp::QoS(total_msgs).reliable(), callback);
auto pub = node->create_publisher<String>(
    "topic", rclcpp::QoS(total_msgs).reliable());
```

#### Python

```python
# 修复前
node.create_subscription(String, "topic", on_msg, 2000)
pub = node.create_publisher(String, "topic", 2000)

# 修复后 — 使用 QoSProfile 显式配置
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

total_msgs = num_threads * msgs_per_thread  # = 4000
topic_qos = QoSProfile(
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=total_msgs,
    reliability=QoSReliabilityPolicy.RELIABLE,
)
node.create_subscription(String, "topic", on_msg, topic_qos)
pub = node.create_publisher(String, "topic", topic_qos)
```

#### Rust (rclrs)

```rust
// 修复前 — 默认 QoS, KeepLast(10)
let sub = node.create_subscription("topic", callback)?;
let pub_ = node.create_publisher("topic")?;

// 修复后 — 链式 QoS API (rclrs IntoPrimitiveOptions trait)
let total_msgs = num_threads * msgs_per_thread;  // = 4000
let sub = node.create_subscription(
    "topic".keep_last(total_msgs as u32).reliable(),
    callback,
)?;
let pub_ = node.create_publisher(
    "topic".keep_last(total_msgs as u32).reliable(),
)?;
```

> **rclrs QoS API 说明**：rclrs 通过 `IntoPrimitiveOptions` trait 为 `&str` 扩展了链式调用，支持 `.keep_last(depth)`, `.keep_all()`, `.reliable()`, `.best_effort()`, `.transient_local()`, `.qos(profile)` 等方法，使用 `use rclrs::*;` 即可引入。

### Step 2: 添加消息接收等待逻辑

暴发发送结束后，DDS 的 Reliable 协议仍在重传和确认。必须等待 subscriber 处理完所有缓存消息，而不是固定 sleep：

```cpp
// C++ — 等待直到全部收到或超时 5 秒
auto drain_start = high_resolution_clock::now();
while (duration<double>(high_resolution_clock::now() - drain_start).count() < 5.0) {
    if (recv_count.load() >= total_msgs) break;
    std::this_thread::sleep_for(milliseconds(10));
}
```

```python
# Python — 同样逻辑
drain_start = time.time()
while time.time() - drain_start < 5.0:
    with lat_lock:
        if recv_count[0] >= total_msgs:
            break
    time.sleep(0.01)
```

```rust
// Rust — 同样逻辑
let drain_start = Instant::now();
while drain_start.elapsed() < Duration::from_secs(5) {
    if latencies.lock().unwrap().len() >= total_msgs {
        break;
    }
    std::thread::sleep(Duration::from_millis(50));
}
```

### Step 3: 跨 Context 的 DDS 发现等待（Rust multi_node 特有）

当使用独立 `Context`（独立 DDS participant）时，需要预留 DDS 发现时间：

```rust
// 创建 subscriber Context (独立线程)
let sub_handle = std::thread::spawn(move || { /* ... */ });

// 创建 publisher Context
let pub_ctx = Context::default_from_env().unwrap();
let pub_node = pub_executor.create_node("rust_mn_pub").unwrap();
let publishers = /* ... */;

// 等待 DDS 发现（SPDP 默认周期 ~1s）
std::thread::sleep(Duration::from_secs(2));

// 此时再开始发送
```

也可通过 CycloneDDS 配置加速发现：

```xml
<!-- cyclonedds.xml -->
<Discovery>
  <ParticipantIndex>auto</ParticipantIndex>
  <MaxAutoParticipantIndex>100</MaxAutoParticipantIndex>
</Discovery>
```

## 修复效果

| 语言 | 修复前 | 修复后 | 吞吐量 |
|------|--------|--------|--------|
| C++ | 2039/4000 (51%) | **4000/4000 (100%)** | 86,709 msg/s |
| Python | 1626/4000 (41%) | **4000/4000 (100%)** | 5,043 msg/s |
| Rust | 46/4000 (1%) | **4000/4000 (100%)** | 57,030 msg/s |

三种语言全部实现 **消息零丢失**，吞吐量数据才具有可比性。

## QoS 策略选择指南

| 场景 | History | Depth | Reliability | 说明 |
|------|---------|-------|-------------|------|
| 实时传感器（允许丢帧） | KeepLast | 1~10 | BestEffort | 低延迟优先 |
| 命令/控制（不允许丢失） | KeepLast | ≥ 预期突发量 | Reliable | 本文场景 |
| 日志/录包（全量保存） | KeepAll | — | Reliable | 内存需关注 |
| Benchmark（测吞吐极限） | KeepLast | = 总消息数 | Reliable | 消除缓冲区瓶颈 |

## 关键教训

1. **默认 QoS 不适合高并发暴发场景**：`KeepLast(10)` 在微秒级暴发面前形同虚设
2. **三种语言的 QoS 必须对齐**：Benchmark 比较的公平性取决于一致的 QoS 配置
3. **Reliable ≠ 不丢消息**：Reliable 只保证 *缓冲区内* 的消息可靠投递，缓冲区溢出的消息无法重传
4. **接收端处理速度决定上限**：QoS 深度解决了缓冲问题，但 Executor 的回调处理速度决定了实际吞吐量上限
5. **独立 Context 有 DDS 发现开销**：跨 participant 通信需要额外的发现等待时间
