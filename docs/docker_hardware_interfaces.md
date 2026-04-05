# Docker 硬件接口驱动支持指南

> 环境：Ubuntu 22.04 + Docker + ROS 2 Humble
> 日期：2026-04-05

## 核心原理

Docker 容器与宿主机**共享 Linux 内核**。硬件驱动运行在内核空间，容器运行在用户空间。因此：

- 只要宿主机驱动正常，容器里就能用
- 关键在于**如何把设备传进容器**

```
┌─────────────────────────────────────────────┐
│                 宿主机 Linux 内核             │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ 串口驱动  │ │ SocketCAN│ │ IgH EtherCAT │ │
│  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │
│       │             │              │          │
│  /dev/ttyUSB0    can0        /dev/EtherCAT0  │
├───────┼─────────────┼──────────────┼─────────┤
│       ▼             ▼              ▼          │
│  ┌─────────────────────────────────────────┐ │
│  │           Docker 容器                    │ │
│  │  --device    --net=host    --privileged  │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## 支持情况总览

| 接口 | 支持程度 | 传入方式 | 实时性 | 复杂度 |
|------|---------|---------|--------|--------|
| RS-232 | 完美 | `--device` | 无要求 | 低 |
| RS-485 | 完美 | `--device` | 无要求 | 低 |
| Modbus RTU | 完美 | `--device`（走串口） | 无要求 | 低 |
| Modbus TCP | 完美 | 默认网络即可 | 无要求 | 零 |
| TCP/IP 通用 | 完美 | 默认网络即可 | 无要求 | 零 |
| CAN 总线 | 良好 | `--network=host` | 毫秒级 | 中 |
| EtherCAT | 可用 | `--privileged` + `--net=host` | 需 RT 内核 | 高 |

---

## 1. RS-232 / RS-485

串口在 Linux 中表现为设备文件，直接透传给容器即可。

### docker run

```bash
docker run --rm -it --device=/dev/ttyUSB0 your_image bash
```

### docker-compose.yml

```yaml
services:
  dev:
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

### 稳定设备路径

USB 转串口设备在插拔后 `/dev/ttyUSB0` 编号可能变化。生产环境建议使用 `by-id` 路径：

```bash
# 查看稳定路径
ls -l /dev/serial/by-id/
```

```yaml
services:
  dev:
    devices:
      - /dev/serial/by-id/usb-FTDI_FT232R-if00-port0:/dev/ttyUSB0
```

### 常见设备路径

| 类型 | 典型路径 |
|------|---------|
| 板载串口 | `/dev/ttyS0`, `/dev/ttyS1` |
| USB 转串口 | `/dev/ttyUSB0`, `/dev/ttyACM0` |
| RS-485（板载） | `/dev/ttyS1`（具体看硬件） |

---

## 2. Modbus RTU

Modbus RTU 运行在串口之上，处理方式与 RS-485 完全相同。

```yaml
services:
  modbus_slave:
    image: your_image
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
```

容器内使用示例（Python）：

```python
from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port='/dev/ttyUSB0',
    baudrate=9600,
    parity='N',
    stopbits=1,
)
client.connect()
result = client.read_holding_registers(address=0, count=10, slave=1)
```

---

## 3. Modbus TCP / TCP 通用

纯软件协议，走网络栈，Docker 默认支持，**零额外配置**。

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('192.168.1.100', port=502)
client.connect()
result = client.read_holding_registers(address=0, count=10, slave=1)
```

如果容器需要监听端口，做端口映射：

```yaml
services:
  modbus_server:
    ports:
      - "502:502"
```

或直接使用 host 网络（ROS 2 场景推荐）：

```yaml
services:
  dev:
    network_mode: host
```

---

## 4. CAN 总线

CAN 在 Linux 里走 **SocketCAN** 框架，表现为网络接口（类似 `eth0`），而非设备文件。

### 宿主机配置 CAN 接口

```bash
# 设置波特率并启用
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up

# 验证
ip -details link show can0
```

### Docker 访问 CAN

由于 CAN 是网络接口，必须使用 host 网络模式：

```yaml
services:
  dev:
    network_mode: host    # 必须，否则看不到 can0
```

### 容器内使用

```bash
# 监听 CAN 帧
candump can0

# 发送 CAN 帧
cansend can0 123#DEADBEEF
```

ROS 2 + CAN 示例（C++/Rust 可用 SocketCAN 库直接操作）：

```bash
# 容器内安装 can-utils
apt-get install -y can-utils
```

### 虚拟 CAN（开发测试用）

没有物理 CAN 硬件时，可在宿主机创建虚拟 CAN 接口：

```bash
sudo modprobe vcan
sudo ip link add dev vcan0 type vcan
sudo ip link set vcan0 up
```

容器内通过 `--network=host` 同样可见。

---

## 5. EtherCAT

EtherCAT 是门槛最高的接口，涉及**内核模块 + 实时性要求**。

### 架构

```
宿主机（必须）：
  ├── PREEMPT_RT 实时内核
  ├── IgH EtherCAT Master 内核模块
  │     → 生成 /dev/EtherCAT0
  └── Docker 容器（特权模式）：
       └── EtherCAT 应用程序
```

### 为什么需要特殊处理

| 要求 | 原因 |
|------|------|
| **PREEMPT_RT 内核** | EtherCAT 伺服控制要求 <10μs 抖动，标准内核做不到 |
| **IgH 内核模块** | EtherCAT Master 实现为内核模块，必须在宿主机加载 |
| **特权模式** | 容器需要访问 `/dev/EtherCAT0` 和原始网络接口 |

### 宿主机准备

```bash
# 1. 安装 PREEMPT_RT 内核
sudo apt install linux-image-rt-amd64

# 2. 编译安装 IgH EtherCAT Master
git clone https://gitlab.com/etherlab.org/ethercat.git
cd ethercat
./bootstrap
./configure --enable-generic
make && sudo make install

# 3. 加载内核模块
sudo modprobe ec_master
sudo modprobe ec_generic
```

### docker-compose.yml

```yaml
services:
  ethercat_app:
    build: .
    privileged: true
    network_mode: host
    devices:
      - /dev/EtherCAT0:/dev/EtherCAT0
    volumes:
      - /lib/modules:/lib/modules:ro
      - /usr/local/etherlab:/usr/local/etherlab:ro
    command: bash
```

### 实测性能

在 PREEMPT_RT 宿主机 + Docker 容器内：

| 模式 | 标准内核抖动 | RT 内核抖动 |
|------|------------|------------|
| 周期同步速度模式 | 6.31 μs | 3.58 μs |
| 周期同步力矩模式 | 50.05 μs | 2.11 μs |

> 参考：[2b-t/linux-realtime](https://github.com/2b-t/linux-realtime) — Docker 实时应用完整指南

---

## 本工作空间的 docker-compose.yml 扩展示例

在现有配置基础上按需添加硬件设备支持：

```yaml
services:
  dev:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        ROS_DISTRO: humble
        RUST_VERSION: "1.85.0"
    image: rust_ws:humble-dev
    container_name: rust_ws_dev
    volumes:
      - .:/ws
    network_mode: host              # ROS 2 DDS + CAN 都需要
    ipc: host
    pid: host
    stdin_open: true
    tty: true
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0   # RS-232/485/Modbus RTU
      # - /dev/ttyUSB1:/dev/ttyUSB1 # 第二个串口设备
      # - /dev/EtherCAT0:/dev/EtherCAT0  # EtherCAT
    # privileged: true              # EtherCAT 需要时取消注释
    command: bash
```

---

## 常见问题

### Q: 容器内看不到 `/dev/ttyUSB0`？

1. 确认宿主机能看到：`ls -l /dev/ttyUSB0`
2. 确认 docker-compose 中配了 `devices`
3. 确认设备在容器**启动前**已插入（`--device` 不支持热插拔）

### Q: CAN 接口在容器内 `ip link` 看不到？

确认使用了 `network_mode: host`。CAN 是网络接口，桥接网络（默认）下不可见。

### Q: 串口权限不足 `Permission denied`？

```bash
# 方法一：把用户加入 dialout 组（宿主机）
sudo usermod -aG dialout $USER

# 方法二：容器以 root 运行（默认行为）

# 方法三：指定设备权限
devices:
  - /dev/ttyUSB0:/dev/ttyUSB0:rwm
```

### Q: Docker 里能跑硬实时任务吗？

Docker 本身不引入额外延迟（共享内核），但需要：
- 宿主机安装 **PREEMPT_RT** 内核
- 容器使用 `--privileged` 模式
- 应用进程设置实时调度策略（`SCHED_FIFO`）

对延迟要求 <1μs 的场景（如高速伺服插补），建议直接裸机或使用 Xenomai，不走 Docker。

### Q: `--privileged` 安全吗？

`--privileged` 关闭了容器的所有安全隔离，相当于在宿主机上直接运行。仅在 EtherCAT 等确实需要的场景使用，日常开发不要开。

---

## 决策流程图

```
你的应用需要什么接口？
│
├── 串口（232/485/Modbus RTU）
│   └── --device=/dev/ttyUSBx ✅ 简单
│
├── TCP 网络（Modbus TCP / 通用 TCP）
│   └── 默认就行 ✅ 零配置
│
├── CAN 总线
│   └── --network=host ✅ 中等
│
├── EtherCAT
│   ├── 宿主机需要 RT 内核 + IgH 内核模块
│   └── --privileged + --net=host ⚠️ 复杂
│
└── 硬实时 <1μs
    └── 不建议用 Docker ❌ 直接裸机
```
