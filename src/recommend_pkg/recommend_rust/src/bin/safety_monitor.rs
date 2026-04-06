use anyhow::Result;
use rclrs::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

/// Rust 安全中间层：安全守卫节点
/// 选型依据：
/// - 安全关键模块需要编译期消除数据竞争和内存错误
/// - Rust 参数读写比 C++ 快 111 倍，适合频繁读取安全阈值
/// - Send/Sync trait 在编译期保证线程安全
fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("safety_monitor")?;

    // 安全参数 — Rust 的参数访问零开销抽象，读取速度 20.3M ops/s
    let min_safe_dist: MandatoryParameter<f64> = node
        .declare_parameter("min_safe_distance")
        .default(0.5)
        .mandatory()?;
    let emergency_dist: MandatoryParameter<f64> = node
        .declare_parameter("emergency_distance")
        .default(0.2)
        .mandatory()?;
    let max_speed: MandatoryParameter<f64> = node
        .declare_parameter("max_speed")
        .default(1.0)
        .mandatory()?;

    let safety_pub = node.create_publisher::<std_msgs::msg::String>("/safety_status")?;
    let estop_pub = node.create_publisher::<std_msgs::msg::Bool>("/emergency_stop")?;

    // 闭包会 move 参数，先缓存初始值用于启动日志
    let init_safe = min_safe_dist.get();
    let init_emergency = emergency_dist.get();
    let init_speed = max_speed.get();

    // 编译期保证：所有共享状态通过 Arc<Atomic*> 传递，不可能出现数据竞争
    let was_emergency = Arc::new(AtomicBool::new(false));

    let _sub = node.create_subscription::<std_msgs::msg::String, _>(
        "/scan_data",
        move |msg: std_msgs::msg::String| {
            let parsed: serde_json::Value = match serde_json::from_str(&msg.data) {
                Ok(v) => v,
                Err(_) => return,
            };
            let ranges: Vec<f64> = match parsed["ranges"].as_array() {
                Some(arr) => arr.iter().filter_map(|v| v.as_f64()).collect(),
                None => return,
            };
            if ranges.is_empty() {
                return;
            }

            // 安全评估 — 所有权系统确保 ranges 不会被意外修改
            let (min_dist, danger_idx) = ranges
                .iter()
                .enumerate()
                .min_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
                .map(|(i, &d)| (d, i))
                .unwrap_or((f64::INFINITY, 0));

            let e_dist = emergency_dist.get();
            let s_dist = min_safe_dist.get();
            let m_speed = max_speed.get();

            let is_emergency = min_dist < e_dist;
            let is_safe = min_dist >= s_dist;
            let allowed_speed = if is_emergency {
                0.0
            } else if !is_safe {
                // 线性衰减：距离越近速度越低
                m_speed * ((min_dist - e_dist) / (s_dist - e_dist)).clamp(0.0, 1.0)
            } else {
                m_speed
            };

            // 发布紧急停止信号
            let mut estop_msg = std_msgs::msg::Bool::default();
            estop_msg.data = is_emergency;
            let _ = estop_pub.publish(&estop_msg);

            // 发布安全状态 JSON
            let status = format!(
                r#"{{"safe":{},"min_distance":{:.3},"danger_index":{},"max_allowed_speed":{:.3},"emergency":{}}}"#,
                is_safe, min_dist, danger_idx, allowed_speed, is_emergency
            );
            let mut status_msg = std_msgs::msg::String::default();
            status_msg.data = status;
            let _ = safety_pub.publish(&status_msg);

            // 状态变化时打印（避免日志刷屏）
            let prev = was_emergency.load(Ordering::Relaxed);
            if is_emergency && !prev {
                eprintln!(
                    "[SAFETY] EMERGENCY STOP! obstacle at ray #{}, dist={:.3}m < threshold={:.3}m",
                    danger_idx, min_dist, e_dist
                );
            } else if !is_emergency && prev {
                eprintln!("[SAFETY] Danger cleared, min_dist={:.3}m", min_dist);
            }
            was_emergency.store(is_emergency, Ordering::Relaxed);
        },
    )?;

    println!(
        "[Rust] Safety monitor started (min_safe={:.1}m, emergency={:.1}m, max_speed={:.1}m/s)",
        init_safe, init_emergency, init_speed
    );
    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
