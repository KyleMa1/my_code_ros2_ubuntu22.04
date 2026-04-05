use anyhow::Result;
use rclrs::*;
use example_interfaces::action::{Fibonacci, Fibonacci_Feedback, Fibonacci_Result};
use tokio::sync::mpsc::unbounded_channel;

async fn fibonacci_action(handle: RequestedGoal<Fibonacci>) -> TerminatedGoal {
    let goal_order = handle.goal().order;
    if goal_order < 0 {
        return handle.reject();
    }

    let mut result = Fibonacci_Result::default();
    let executing = match handle.accept().begin() {
        BeginAcceptedGoal::Execute(executing) => executing,
        BeginAcceptedGoal::Cancel(cancelling) => {
            return cancelling.cancelled_with(result);
        }
    };

    let (sender, mut receiver) = unbounded_channel();
    std::thread::spawn(move || {
        let mut prev = 0i32;
        let mut curr = 1i32;
        for _ in 0..goal_order {
            if sender.send(curr).is_err() {
                return;
            }
            let next = prev + curr;
            prev = curr;
            curr = next;
        }
    });

    let mut sequence = Vec::new();
    loop {
        match executing.unless_cancel_requested(receiver.recv()).await {
            Ok(Some(next)) => {
                sequence.push(next);
                executing.publish_feedback(Fibonacci_Feedback {
                    sequence: sequence.clone(),
                });
            }
            Ok(None) => {
                result.sequence = sequence;
                return executing.succeeded_with(result);
            }
            Err(_) => {
                let cancelling = executing.begin_cancelling();
                result.sequence = sequence;
                return cancelling.cancelled_with(result);
            }
        }
    }
}

fn main() -> Result<()> {
    let mut executor = Context::default_from_env()?.create_basic_executor();
    let node = executor.create_node("rust_action_server")?;
    let _server = node.create_action_server("benchmark_fibonacci", fibonacci_action)?;

    println!("Rust action server started");
    executor.spin(SpinOptions::default()).first_error()?;
    Ok(())
}
