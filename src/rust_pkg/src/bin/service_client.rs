use anyhow::Result;
use example_interfaces::srv::*;
use rclrs::*;

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_service_client")?;
    let client = node.create_client::<AddTwoInts>("benchmark_add_two_ints")?;

    println!("Waiting for service...");
    while !client.service_is_ready()? {
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    let request = AddTwoInts_Request { a: 41, b: 1 };
    let promise = client
        .call_then(&request, move |response: AddTwoInts_Response| {
            println!("Result: {}", response.sum);
        })
        .unwrap();

    executor
        .spin(SpinOptions::new().until_promise_resolved(promise))
        .first_error()?;
    Ok(())
}
