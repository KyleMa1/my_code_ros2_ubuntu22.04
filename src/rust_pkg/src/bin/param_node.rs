use anyhow::Result;
use rclrs::*;
use std::sync::Arc;

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_param_node")?;

    let my_int: MandatoryParameter<i64> = node
        .declare_parameter("my_int")
        .default(42)
        .mandatory()?;

    let my_string: MandatoryParameter<Arc<str>> = node
        .declare_parameter("my_string")
        .default("hello".into())
        .mandatory()?;

    let _timer = node.create_timer_repeating(
        std::time::Duration::from_secs(1),
        move || {
            println!("my_int = {}, my_string = {}", my_int.get(), my_string.get());
        },
    )?;

    println!("Rust param node started");
    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
