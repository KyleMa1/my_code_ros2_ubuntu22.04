use anyhow::Result;
use rclrs::*;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

fn now_ns() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos() as i64
}

fn main() -> Result<()> {
    let num_threads = 4usize;
    let msgs_per_thread = 2000usize;

    let latencies = Arc::new(Mutex::new(Vec::with_capacity(num_threads * msgs_per_thread)));
    let stop = Arc::new(AtomicBool::new(false));
    let received = Arc::new(AtomicUsize::new(0));

    let lat_c = Arc::clone(&latencies);
    let stop_c = Arc::clone(&stop);
    let recv_c = Arc::clone(&received);
    let sub_handle = std::thread::spawn(move || {
        let ctx = Context::default_from_env().unwrap();
        let mut executor = ctx.create_basic_executor();
        let node = executor.create_node("mn_subscriber").unwrap();

        let _sub = node
            .create_subscription::<example_interfaces::msg::String, _>(
                "multi_node_topic",
                move |msg: example_interfaces::msg::String| {
                    let recv_ns = now_ns();
                    if let Ok(sent_ns) = msg.data.parse::<i64>() {
                        lat_c.lock().unwrap().push(recv_ns - sent_ns);
                        recv_c.fetch_add(1, Ordering::Relaxed);
                    }
                },
            )
            .unwrap();

        while !stop_c.load(Ordering::Relaxed) {
            executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
        }
    });

    std::thread::sleep(Duration::from_millis(200));

    let start = Instant::now();
    let mut pub_handles = Vec::new();
    for i in 0..num_threads {
        pub_handles.push(std::thread::spawn(move || {
            let ctx = Context::default_from_env().unwrap();
            let executor = ctx.create_basic_executor();
            let node = executor
                .create_node(&format!("mn_publisher_{i}"))
                .unwrap();
            let publisher = node
                .create_publisher::<example_interfaces::msg::String>("multi_node_topic")
                .unwrap();

            for _ in 0..msgs_per_thread {
                let mut msg = example_interfaces::msg::String::default();
                msg.data = now_ns().to_string();
                let _ = publisher.publish(&msg);
            }
        }));
    }
    for h in pub_handles {
        h.join().unwrap();
    }

    std::thread::sleep(Duration::from_millis(500));
    stop.store(true, Ordering::Relaxed);
    sub_handle.join().unwrap();

    let elapsed = start.elapsed().as_secs_f64();
    let total_sent = num_threads * msgs_per_thread;
    let total_received = received.load(Ordering::Relaxed);
    let lats = latencies.lock().unwrap();
    let avg_lat_us = if !lats.is_empty() {
        lats.iter().sum::<i64>() as f64 / lats.len() as f64 / 1000.0
    } else {
        0.0
    };

    println!("=== Multi-Node Multi-Thread Demo ===");
    println!("Threads: {num_threads}, msgs/thread: {msgs_per_thread}");
    println!("Sent: {total_sent}, Received: {total_received}");
    println!("Elapsed: {elapsed:.3}s");
    println!("Throughput: {:.0} msg/s", total_received as f64 / elapsed);
    println!("Avg latency: {avg_lat_us:.2} us");

    Ok(())
}
