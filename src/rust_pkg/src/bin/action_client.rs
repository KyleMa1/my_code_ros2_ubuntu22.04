use anyhow::Result;
use rclrs::*;
use example_interfaces::action::{Fibonacci, Fibonacci_Goal};
use futures::StreamExt;

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_action_client")?;
    let client = node.create_action_client::<Fibonacci>("benchmark_fibonacci")?;

    let request = client.request_goal(Fibonacci_Goal { order: 10 });

    let promise = executor.commands().run(async move {
        match request.await {
            Some(goal_client) => {
                let mut stream = goal_client.stream();
                while let Some(event) = stream.next().await {
                    match event {
                        GoalEvent::Feedback(fb) => {
                            println!("Feedback: len={}", fb.sequence.len());
                        }
                        GoalEvent::Status(s) => {
                            println!("Status: {:?}", s.code);
                        }
                        GoalEvent::Result((status, result)) => {
                            println!("Result: status={:?}, {} elements", status, result.sequence.len());
                            return;
                        }
                    }
                }
            }
            None => {
                println!("Goal was rejected");
            }
        }
    });

    executor.spin(SpinOptions::default().until_promise_resolved(promise));
    Ok(())
}
