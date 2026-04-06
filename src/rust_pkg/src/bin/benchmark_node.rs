use anyhow::Result;
use rclrs::*;
use example_interfaces::action::{Fibonacci, Fibonacci_Feedback, Fibonacci_Goal, Fibonacci_Result};
use example_interfaces::srv::*;
use futures::StreamExt;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc::unbounded_channel;

fn now_ns() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos() as i64
}

fn compute_stats(latencies: &mut Vec<i64>, elapsed_s: f64) -> serde_json::Value {
    latencies.sort();
    let n = latencies.len();
    let sum: i64 = latencies.iter().sum();
    serde_json::json!({
        "avg_us": sum as f64 / n as f64 / 1000.0,
        "min_us": latencies[0] as f64 / 1000.0,
        "max_us": latencies[n - 1] as f64 / 1000.0,
        "p50_us": latencies[n / 2] as f64 / 1000.0,
        "p95_us": latencies[(n as f64 * 0.95) as usize] as f64 / 1000.0,
        "p99_us": latencies[(n as f64 * 0.99) as usize] as f64 / 1000.0,
        "throughput": n as f64 / elapsed_s,
    })
}

fn benchmark_topic(iterations: usize) -> serde_json::Value {
    let context = Context::default_from_env().unwrap();
    let mut executor = context.create_basic_executor();
    let node = executor.create_node("rust_bench_topic").unwrap();

    let publisher = node
        .create_publisher::<example_interfaces::msg::String>("bench_topic_rust")
        .unwrap();

    let latencies = Arc::new(Mutex::new(Vec::with_capacity(iterations)));
    let lat_clone = Arc::clone(&latencies);

    let _sub = node
        .create_subscription::<example_interfaces::msg::String, _>(
            "bench_topic_rust",
            move |msg: example_interfaces::msg::String| {
                let recv_ns = now_ns();
                if let Ok(sent_ns) = msg.data.parse::<i64>() {
                    lat_clone.lock().unwrap().push(recv_ns - sent_ns);
                }
            },
        )
        .unwrap();

    let start = Instant::now();
    for _ in 0..iterations {
        let mut msg = example_interfaces::msg::String::default();
        msg.data = now_ns().to_string();
        publisher.publish(&msg).unwrap();
        executor.spin(SpinOptions::new().timeout(Duration::from_micros(10)));
        std::thread::sleep(Duration::from_micros(10));
    }
    for _ in 0..50 {
        executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
    }
    let elapsed_s = start.elapsed().as_secs_f64();

    let mut lats = latencies.lock().unwrap();
    if lats.is_empty() {
        serde_json::json!({"error": "no messages received"})
    } else {
        compute_stats(&mut lats, elapsed_s)
    }
}

fn benchmark_service(iterations: usize) -> serde_json::Value {
    let context = Context::default_from_env().unwrap();
    let mut executor = context.create_basic_executor();
    let node = executor.create_node("rust_bench_service").unwrap();

    let _server = node
        .create_service::<AddTwoInts, _>("bench_srv_rust", |req: AddTwoInts_Request, _info: ServiceInfo| {
            AddTwoInts_Response {
                sum: req.a + req.b,
            }
        })
        .unwrap();

    let client = node.create_client::<AddTwoInts>("bench_srv_rust").unwrap();
    while !client.service_is_ready().unwrap() {
        executor.spin(SpinOptions::new().timeout(Duration::from_millis(10)));
    }

    let latencies = Arc::new(Mutex::new(Vec::with_capacity(iterations)));

    let start = Instant::now();
    for i in 0..iterations {
        let t0 = Instant::now();
        let lat_clone = Arc::clone(&latencies);
        let promise = client
            .call_then(
                &AddTwoInts_Request {
                    a: i as i64,
                    b: 1,
                },
                move |_resp: AddTwoInts_Response| {
                    let elapsed = t0.elapsed().as_nanos() as i64;
                    lat_clone.lock().unwrap().push(elapsed);
                },
            )
            .unwrap();
        executor.spin(SpinOptions::new().until_promise_resolved(promise));
    }
    let elapsed_s = start.elapsed().as_secs_f64();

    let mut lats = latencies.lock().unwrap();
    compute_stats(&mut lats, elapsed_s)
}

fn benchmark_action(fib_order: i32) -> serde_json::Value {
    let context = Context::default_from_env().unwrap();
    let mut executor = context.create_basic_executor();
    let node = executor.create_node("rust_bench_action").unwrap();

    let _server = node
        .create_action_server("bench_action_rust", |handle: RequestedGoal<Fibonacci>| async move {
            let goal_order = handle.goal().order;
            let mut result = Fibonacci_Result::default();
            let executing = match handle.accept().begin() {
                BeginAcceptedGoal::Execute(e) => e,
                BeginAcceptedGoal::Cancel(c) => return c.cancelled_with(result),
            };

            let (sender, mut receiver) = unbounded_channel();
            std::thread::spawn(move || {
                let mut prev = 0i32;
                let mut curr = 1i32;
                for _ in 0..goal_order {
                    if sender.send(curr).is_err() { return; }
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
                        executing.publish_feedback(Fibonacci_Feedback { sequence: sequence.clone() });
                    }
                    Ok(None) => {
                        result.sequence = sequence;
                        return executing.succeeded_with(result);
                    }
                    Err(_) => {
                        let c = executing.begin_cancelling();
                        result.sequence = sequence;
                        return c.cancelled_with(result);
                    }
                }
            }
        })
        .unwrap();

    let client = node.create_action_client::<Fibonacci>("bench_action_rust").unwrap();
    let feedback_count = Arc::new(Mutex::new(0usize));

    let t0 = Instant::now();
    let request = client.request_goal(Fibonacci_Goal { order: fib_order });
    let fc = Arc::clone(&feedback_count);

    let promise = executor.commands().run(async move {
        if let Some(goal_client) = request.await {
            let mut stream = goal_client.stream();
            while let Some(event) = stream.next().await {
                match event {
                    GoalEvent::Feedback(_) => { *fc.lock().unwrap() += 1; }
                    GoalEvent::Result(_) => return,
                    _ => {}
                }
            }
        }
    });

    executor.spin(SpinOptions::new().until_promise_resolved(promise));
    let elapsed_us = t0.elapsed().as_micros() as f64;
    let fc = *feedback_count.lock().unwrap();

    serde_json::json!({
        "total_us": elapsed_us,
        "feedback_count": fc,
        "fib_order": fib_order,
    })
}

fn benchmark_param(iterations: usize) -> serde_json::Value {
    let context = Context::default_from_env().unwrap();
    let executor = context.create_basic_executor();
    let node = executor.create_node("rust_bench_param").unwrap();

    let param: MandatoryParameter<i64> = node
        .declare_parameter("bench_int")
        .default(0)
        .mandatory()
        .unwrap();

    let t0 = Instant::now();
    for i in 0..iterations {
        param.set(i as i64).unwrap();
    }
    let write_elapsed = t0.elapsed().as_secs_f64();

    let t2 = Instant::now();
    let mut sink: i64 = 0;
    for _ in 0..iterations {
        sink = param.get();
    }
    let read_elapsed = t2.elapsed().as_secs_f64();
    let _ = sink;

    serde_json::json!({
        "write_ops_per_sec": iterations as f64 / write_elapsed,
        "read_ops_per_sec": iterations as f64 / read_elapsed,
        "iterations": iterations,
    })
}

fn benchmark_concurrency(
    num_threads: usize,
    msgs_per_thread: usize,
    calls_per_thread: usize,
    param_ops_per_thread: usize,
) -> serde_json::Value {
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

    let mut conc = serde_json::Map::new();
    conc.insert("thread_count".into(), serde_json::json!(num_threads));

    // --- Multi-publisher topic ---
    // Move executor into a background spin thread so callbacks fire while publishers send.
    {
        let context = Context::default_from_env().unwrap();
        let mut executor = context.create_basic_executor();
        let node = executor.create_node("rust_bench_conc_topic").unwrap();

        let total_msgs = num_threads * msgs_per_thread;
        let latencies = Arc::new(Mutex::new(Vec::with_capacity(total_msgs)));
        let lat_clone = Arc::clone(&latencies);

        let _sub = node
            .create_subscription::<example_interfaces::msg::String, _>(
                "bench_conc_topic_rust".keep_last(total_msgs as u32).reliable(),
                move |msg: example_interfaces::msg::String| {
                    let recv_ns = now_ns();
                    if let Ok(sent_ns) = msg.data.parse::<i64>() {
                        lat_clone.lock().unwrap().push(recv_ns - sent_ns);
                    }
                },
            )
            .unwrap();

        let publisher = Arc::new(
            node.create_publisher::<example_interfaces::msg::String>(
                "bench_conc_topic_rust".keep_last(total_msgs as u32).reliable(),
            )
            .unwrap(),
        );

        let stop = Arc::new(AtomicBool::new(false));
        let stop_c = Arc::clone(&stop);
        let spin_handle = std::thread::spawn(move || {
            while !stop_c.load(Ordering::Relaxed) {
                executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
            }
        });

        let start = Instant::now();
        let mut handles = Vec::new();
        for _ in 0..num_threads {
            let pub_clone = Arc::clone(&publisher);
            let count = msgs_per_thread;
            handles.push(std::thread::spawn(move || {
                for _ in 0..count {
                    let mut msg = example_interfaces::msg::String::default();
                    msg.data = now_ns().to_string();
                    let _ = pub_clone.publish(&msg);
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        // Wait for subscriber to drain all buffered messages (up to 5s)
        let drain_start = Instant::now();
        while drain_start.elapsed() < Duration::from_secs(5) {
            if latencies.lock().unwrap().len() >= total_msgs {
                break;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        let elapsed_s = start.elapsed().as_secs_f64();

        stop.store(true, Ordering::Relaxed);
        spin_handle.join().unwrap();

        let lats = latencies.lock().unwrap();
        let received = lats.len();
        let avg_lat = if received > 0 {
            lats.iter().sum::<i64>() as f64 / received as f64 / 1000.0
        } else {
            0.0
        };

        conc.insert("topic_multi_pub".into(), serde_json::json!({
            "total_sent": num_threads * msgs_per_thread,
            "total_received": received,
            "elapsed_s": elapsed_s,
            "aggregate_throughput": received as f64 / elapsed_s,
            "avg_latency_us": avg_lat,
        }));
    }

    // --- Concurrent service calls ---
    {
        let context = Context::default_from_env().unwrap();
        let mut executor = context.create_basic_executor();
        let node = executor.create_node("rust_bench_conc_srv").unwrap();

        let _server = node
            .create_service::<AddTwoInts, _>(
                "bench_conc_srv_rust",
                |req: AddTwoInts_Request, _info: ServiceInfo| AddTwoInts_Response {
                    sum: req.a + req.b,
                },
            )
            .unwrap();

        let client = Arc::new(node.create_client::<AddTwoInts>("bench_conc_srv_rust").unwrap());
        while !client.service_is_ready().unwrap() {
            executor.spin(SpinOptions::new().timeout(Duration::from_millis(10)));
        }

        let call_latencies = Arc::new(Mutex::new(Vec::with_capacity(
            num_threads * calls_per_thread,
        )));
        let total_calls = Arc::new(AtomicUsize::new(0));
        let total_expected = num_threads * calls_per_thread;

        let stop = Arc::new(AtomicBool::new(false));
        let stop_c = Arc::clone(&stop);
        let spin_handle = std::thread::spawn(move || {
            while !stop_c.load(Ordering::Relaxed) {
                executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
            }
        });

        let start = Instant::now();
        let mut handles = Vec::new();
        for tid in 0..num_threads {
            let client_c = Arc::clone(&client);
            let lat_c = Arc::clone(&call_latencies);
            let tc = Arc::clone(&total_calls);
            let cpt = calls_per_thread;
            handles.push(std::thread::spawn(move || {
                for i in 0..cpt {
                    let ct0 = Instant::now();
                    let lat_c2 = Arc::clone(&lat_c);
                    let tc2 = Arc::clone(&tc);
                    let _ = client_c.call_then(
                        &AddTwoInts_Request {
                            a: tid as i64,
                            b: i as i64,
                        },
                        move |_resp: AddTwoInts_Response| {
                            let lat = ct0.elapsed().as_nanos() as i64;
                            lat_c2.lock().unwrap().push(lat);
                            tc2.fetch_add(1, Ordering::Relaxed);
                        },
                    );
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        let deadline = Instant::now() + Duration::from_secs(10);
        while total_calls.load(Ordering::Relaxed) < total_expected && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(1));
        }
        let elapsed_s = start.elapsed().as_secs_f64();

        stop.store(true, Ordering::Relaxed);
        spin_handle.join().unwrap();

        let lats = call_latencies.lock().unwrap();
        let done = lats.len();
        let avg_lat = if done > 0 {
            lats.iter().sum::<i64>() as f64 / done as f64 / 1000.0
        } else {
            0.0
        };

        conc.insert("service_concurrent".into(), serde_json::json!({
            "total_calls": done,
            "elapsed_s": elapsed_s,
            "aggregate_throughput": done as f64 / elapsed_s,
            "avg_latency_us": avg_lat,
        }));
    }

    // --- Concurrent param read/write (no executor needed) ---
    {
        let context = Context::default_from_env().unwrap();
        let executor = context.create_basic_executor();
        let node = executor.create_node("rust_bench_conc_param").unwrap();

        let param: Arc<MandatoryParameter<i64>> = Arc::new(
            node.declare_parameter("conc_int").default(0).mandatory().unwrap(),
        );
        let total_ops = Arc::new(AtomicUsize::new(0));

        let start = Instant::now();
        let mut handles = Vec::new();
        for tid in 0..num_threads {
            let p = Arc::clone(&param);
            let tc = Arc::clone(&total_ops);
            let ops = param_ops_per_thread;
            handles.push(std::thread::spawn(move || {
                for i in 0..ops {
                    let _ = p.set((tid * 1000 + i) as i64);
                    let _ = p.get();
                    tc.fetch_add(2, Ordering::Relaxed);
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        let elapsed_s = start.elapsed().as_secs_f64();
        let done = total_ops.load(Ordering::Relaxed);

        conc.insert("param_concurrent_rw".into(), serde_json::json!({
            "total_ops": done,
            "elapsed_s": elapsed_s,
            "aggregate_throughput": done as f64 / elapsed_s,
        }));
    }

    serde_json::Value::Object(conc)
}

fn benchmark_multi_node(
    num_threads: usize,
    msgs_per_thread: usize,
    calls_per_thread: usize,
) -> serde_json::Value {
    use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

    let mut mn = serde_json::Map::new();
    mn.insert("thread_count".into(), serde_json::json!(num_threads));

    // --- Multi-node topic: pub Context + sub Context (separate DDS participants) ---
    // Publishing is thread-safe and doesn't need executor spinning, so pubs share one Context.
    // Subscriber uses its own Context+Executor to process callbacks on a dedicated thread.
    {
        let latencies = Arc::new(Mutex::new(Vec::with_capacity(num_threads * msgs_per_thread)));
        let stop = Arc::new(AtomicBool::new(false));

        let total_msgs = num_threads * msgs_per_thread;
        let lat_c = Arc::clone(&latencies);
        let stop_c = Arc::clone(&stop);
        let sub_handle = std::thread::spawn(move || {
            let ctx = Context::default_from_env().unwrap();
            let mut executor = ctx.create_basic_executor();
            let node = executor.create_node("rust_mn_sub").unwrap();
            let _sub = node
                .create_subscription::<example_interfaces::msg::String, _>(
                    "bench_mn_topic_rust".keep_last(total_msgs as u32).reliable(),
                    move |msg: example_interfaces::msg::String| {
                        let recv_ns = now_ns();
                        if let Ok(sent_ns) = msg.data.parse::<i64>() {
                            lat_c.lock().unwrap().push(recv_ns - sent_ns);
                        }
                    },
                )
                .unwrap();
            while !stop_c.load(Ordering::Relaxed) {
                executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
            }
        });

        let pub_ctx = Context::default_from_env().unwrap();
        let pub_executor = pub_ctx.create_basic_executor();
        let pub_node = pub_executor.create_node("rust_mn_pub").unwrap();
        let publishers: Vec<_> = (0..num_threads)
            .map(|_| {
                Arc::new(
                    pub_node
                        .create_publisher::<example_interfaces::msg::String>(
                            "bench_mn_topic_rust".keep_last(total_msgs as u32).reliable(),
                        )
                        .unwrap(),
                )
            })
            .collect();

        std::thread::sleep(Duration::from_secs(2));

        let start = Instant::now();
        let mut handles = Vec::new();
        for i in 0..num_threads {
            let count = msgs_per_thread;
            let pub_c = Arc::clone(&publishers[i]);
            handles.push(std::thread::spawn(move || {
                for _ in 0..count {
                    let mut msg = example_interfaces::msg::String::default();
                    msg.data = now_ns().to_string();
                    let _ = pub_c.publish(&msg);
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        // Wait for subscriber to drain all buffered messages (up to 5s)
        let drain_start = Instant::now();
        while drain_start.elapsed() < Duration::from_secs(5) {
            if latencies.lock().unwrap().len() >= total_msgs {
                break;
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        let elapsed_s = start.elapsed().as_secs_f64();

        stop.store(true, Ordering::Relaxed);
        sub_handle.join().unwrap();

        let lats = latencies.lock().unwrap();
        let received = lats.len();
        let avg_lat = if received > 0 {
            lats.iter().sum::<i64>() as f64 / received as f64 / 1000.0
        } else {
            0.0
        };

        mn.insert("topic".into(), serde_json::json!({
            "total_sent": total_msgs,
            "total_received": received,
            "elapsed_s": elapsed_s,
            "aggregate_throughput": received as f64 / elapsed_s,
            "avg_latency_us": avg_lat,
        }));
    }

    // --- Multi-node service: server in own thread, each client in own Context ---
    {
        let stop_srv = Arc::new(AtomicBool::new(false));
        let stop_srv_c = Arc::clone(&stop_srv);

        let srv_handle = std::thread::spawn(move || {
            let ctx = Context::default_from_env().unwrap();
            let mut executor = ctx.create_basic_executor();
            let node = executor.create_node("rust_mn_srv").unwrap();
            let _server = node
                .create_service::<AddTwoInts, _>(
                    "bench_mn_srv_rust",
                    |req: AddTwoInts_Request, _info: ServiceInfo| AddTwoInts_Response {
                        sum: req.a + req.b,
                    },
                )
                .unwrap();
            while !stop_srv_c.load(Ordering::Relaxed) {
                executor.spin(SpinOptions::new().timeout(Duration::from_millis(1)));
            }
        });

        std::thread::sleep(Duration::from_millis(200));

        let call_latencies = Arc::new(Mutex::new(Vec::with_capacity(
            num_threads * calls_per_thread,
        )));
        let total_calls = Arc::new(AtomicUsize::new(0));

        let start = Instant::now();
        let mut handles = Vec::new();
        for tid in 0..num_threads {
            let lat_c = Arc::clone(&call_latencies);
            let tc = Arc::clone(&total_calls);
            let cpt = calls_per_thread;
            handles.push(std::thread::spawn(move || {
                let ctx = Context::default_from_env().unwrap();
                let mut executor = ctx.create_basic_executor();
                let node = executor
                    .create_node(&format!("rust_mn_cli_{tid}"))
                    .unwrap();
                let client = node
                    .create_client::<AddTwoInts>("bench_mn_srv_rust")
                    .unwrap();
                while !client.service_is_ready().unwrap() {
                    executor.spin(SpinOptions::new().timeout(Duration::from_millis(10)));
                }
                for i in 0..cpt {
                    let ct0 = Instant::now();
                    let lat_c2 = Arc::clone(&lat_c);
                    let tc2 = Arc::clone(&tc);
                    let promise = client
                        .call_then(
                            &AddTwoInts_Request {
                                a: tid as i64,
                                b: i as i64,
                            },
                            move |_resp: AddTwoInts_Response| {
                                let lat = ct0.elapsed().as_nanos() as i64;
                                lat_c2.lock().unwrap().push(lat);
                                tc2.fetch_add(1, Ordering::Relaxed);
                            },
                        )
                        .unwrap();
                    executor.spin(SpinOptions::new().until_promise_resolved(promise));
                }
            }));
        }
        for h in handles {
            h.join().unwrap();
        }
        let elapsed_s = start.elapsed().as_secs_f64();

        stop_srv.store(true, Ordering::Relaxed);
        srv_handle.join().unwrap();

        let lats = call_latencies.lock().unwrap();
        let done = lats.len();
        let avg_lat = if done > 0 {
            lats.iter().sum::<i64>() as f64 / done as f64 / 1000.0
        } else {
            0.0
        };

        mn.insert("service".into(), serde_json::json!({
            "total_calls": done,
            "elapsed_s": elapsed_s,
            "aggregate_throughput": done as f64 / elapsed_s,
            "avg_latency_us": avg_lat,
        }));
    }

    serde_json::Value::Object(mn)
}

fn main() -> Result<()> {
    let mut topic_iters: usize = 5000;
    let mut service_iters: usize = 2000;
    let mut action_order: i32 = 20;
    let mut param_iters: usize = 100000;
    let mut conc_threads: usize = 4;
    let mut conc_msgs: usize = 2000;
    let mut conc_calls: usize = 500;
    let mut conc_param_ops: usize = 10000;

    for arg in std::env::args().skip(1) {
        if let Some(v) = arg.strip_prefix("--topic-iters=") {
            topic_iters = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--service-iters=") {
            service_iters = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--action-order=") {
            action_order = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--param-iters=") {
            param_iters = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--conc-threads=") {
            conc_threads = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--conc-msgs=") {
            conc_msgs = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--conc-calls=") {
            conc_calls = v.parse().unwrap();
        } else if let Some(v) = arg.strip_prefix("--conc-param-ops=") {
            conc_param_ops = v.parse().unwrap();
        }
    }

    let mut results = serde_json::Map::new();
    results.insert("language".into(), serde_json::json!("rust"));

    results.insert("topic".into(), benchmark_topic(topic_iters));
    results.insert("service".into(), benchmark_service(service_iters));
    results.insert("action".into(), benchmark_action(action_order));
    results.insert("param".into(), benchmark_param(param_iters));
    results.insert("concurrency".into(), benchmark_concurrency(
        conc_threads, conc_msgs, conc_calls, conc_param_ops));
    results.insert("multi_node".into(), benchmark_multi_node(
        conc_threads, conc_msgs, conc_calls));

    println!("{}", serde_json::to_string_pretty(&serde_json::Value::Object(results))?);
    Ok(())
}
