use anyhow::Result;
use rclrs::*;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_topic_sub")?;

    let _sub = node.create_subscription::<example_interfaces::msg::String, _>(
        "benchmark_topic",
        move |msg: example_interfaces::msg::String| {
            let now_ns = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos() as i64;
            if let Some(sep) = msg.data.find('|') {
                if let Ok(sent_ns) = msg.data[..sep].parse::<i64>() {
                    let latency_us = (now_ns - sent_ns) as f64 / 1000.0;
                    println!("Received [{}] latency={:.1} us", &msg.data[sep + 1..], latency_us);
                }
            }
        },
    )?;

    println!("Rust topic subscriber started");
    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
