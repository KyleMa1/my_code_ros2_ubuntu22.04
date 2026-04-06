#!/bin/bash
# CycloneDDS 环境设置脚本
# 用法: source config/setup_dds.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 加载 CycloneDDS 配置
export CYCLONEDDS_URI="file://${SCRIPT_DIR}/cyclonedds.xml"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

echo "[DDS] RMW_IMPLEMENTATION = $RMW_IMPLEMENTATION"
echo "[DDS] CYCLONEDDS_URI     = $CYCLONEDDS_URI"

# 检查并建议调整内核 socket buffer 上限
RMEM_MAX=$(cat /proc/sys/net/core/rmem_max 2>/dev/null)
WMEM_MAX=$(cat /proc/sys/net/core/wmem_max 2>/dev/null)
DESIRED=8388608  # 8MB

if [ "$RMEM_MAX" -lt "$DESIRED" ] 2>/dev/null; then
    echo ""
    echo "[DDS] 警告: 内核 socket buffer 上限偏小 (rmem_max=${RMEM_MAX})"
    echo "[DDS] 建议执行以下命令提升 benchmark 性能:"
    echo ""
    echo "  sudo sysctl -w net.core.rmem_max=8388608"
    echo "  sudo sysctl -w net.core.wmem_max=8388608"
    echo "  sudo sysctl -w net.core.rmem_default=1048576"
    echo "  sudo sysctl -w net.core.wmem_default=1048576"
    echo ""
fi
