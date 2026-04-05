use anyhow::Result;
use rclrs::*;
use std::time::{SystemTime, UNIX_EPOCH};

fn main() -> Result<()> {
    let context = Context::default_from_env()?;
    let executor = context.create_basic_executor();
    let node = executor.create_node("rust_topic_pub")?;
    let publisher = node.create_publisher::<example_interfaces::msg::String>("benchmark_topic")?;

    println!("Rust topic publisher started");
    let mut count: u64 = 0;
    while context.ok() {
        let now_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let mut msg = example_interfaces::msg::String::default();
        msg.data = format!("{now_ns}|seq={count}");
        publisher.publish(&msg)?;
        count += 1;
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    Ok(())
}
