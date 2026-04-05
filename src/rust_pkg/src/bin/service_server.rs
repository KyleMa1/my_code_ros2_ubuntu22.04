use anyhow::Result;
use example_interfaces::srv::*;
use rclrs::*;

fn handle_service(request: AddTwoInts_Request, _info: ServiceInfo) -> AddTwoInts_Response {
    AddTwoInts_Response {
        sum: request.a + request.b,
    }
}

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_service_server")?;
    let _server = node.create_service::<AddTwoInts, _>("benchmark_add_two_ints", handle_service)?;

    println!("Rust service server started");
    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
