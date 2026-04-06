import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import rclpy
from rclpy.action import ActionClient as RclpyActionClient
from rclpy.action import ActionServer as RclpyActionServer
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor, MultiThreadedExecutor
from rclpy.callback_groups import ReentrantCallbackGroup
from std_msgs.msg import String
from example_interfaces.srv import AddTwoInts
from example_interfaces.action import Fibonacci


def percentile(sorted_data, pct):
    idx = int(len(sorted_data) * pct / 100.0)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def compute_stats(latencies, elapsed_s):
    latencies.sort()
    n = len(latencies)
    return {
        "avg_us": sum(latencies) / n / 1000.0,
        "min_us": latencies[0] / 1000.0,
        "max_us": latencies[-1] / 1000.0,
        "p50_us": percentile(latencies, 50) / 1000.0,
        "p95_us": percentile(latencies, 95) / 1000.0,
        "p99_us": percentile(latencies, 99) / 1000.0,
        "throughput": n / elapsed_s,
    }


def benchmark_topic(iterations):
    node = Node("py_bench_topic")
    pub = node.create_publisher(String, "bench_topic_py", 100)
    latencies = []

    def on_msg(msg):
        now_ns = time.time_ns()
        sent_ns = int(msg.data)
        latencies.append(now_ns - sent_ns)

    node.create_subscription(String, "bench_topic_py", on_msg, 100)

    start = time.time()
    for _ in range(iterations):
        msg = String()
        msg.data = str(time.time_ns())
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0)
        time.sleep(0.00001)

    for _ in range(50):
        rclpy.spin_once(node, timeout_sec=0.001)

    elapsed = time.time() - start
    node.destroy_node()

    if latencies:
        return compute_stats(latencies, elapsed)
    return {"error": "no messages received"}


def benchmark_service(iterations):
    node = Node("py_bench_service")

    def handle(req, resp):
        resp.sum = req.a + req.b
        return resp

    node.create_service(AddTwoInts, "bench_srv_py", handle)
    client = node.create_client(AddTwoInts, "bench_srv_py")
    while not client.wait_for_service(timeout_sec=0.1):
        rclpy.spin_once(node, timeout_sec=0)

    latencies = []
    start = time.time()
    for i in range(iterations):
        req = AddTwoInts.Request()
        req.a = i
        req.b = 1
        t0 = time.time_ns()
        future = client.call_async(req)
        rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
        t1 = time.time_ns()
        latencies.append(t1 - t0)
    elapsed = time.time() - start
    node.destroy_node()
    return compute_stats(latencies, elapsed)


def benchmark_action(fib_order):
    node = Node("py_bench_action")
    feedback_count = 0

    def execute_cb(goal_handle):
        fb = Fibonacci.Feedback()
        prev, curr = 0, 1
        for _ in range(goal_handle.request.order):
            fb.sequence.append(curr)
            goal_handle.publish_feedback(fb)
            prev, curr = curr, prev + curr
        goal_handle.succeed()
        result = Fibonacci.Result()
        result.sequence = fb.sequence
        return result

    _server = RclpyActionServer(node, Fibonacci, "bench_action_py", execute_cb)
    action_client = RclpyActionClient(node, Fibonacci, "bench_action_py")
    action_client.wait_for_server(timeout_sec=5.0)

    goal = Fibonacci.Goal()
    goal.order = fib_order

    def fb_cb(_feedback_msg):
        nonlocal feedback_count
        feedback_count += 1

    t0 = time.time_ns()
    future = action_client.send_goal_async(goal, feedback_callback=fb_cb)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    goal_handle = future.result()

    if goal_handle and goal_handle.accepted:
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future, timeout_sec=10.0)

    t1 = time.time_ns()
    node.destroy_node()

    return {
        "total_us": (t1 - t0) / 1000.0,
        "feedback_count": feedback_count,
        "fib_order": fib_order,
    }


def benchmark_param(iterations):
    node = Node("py_bench_param")
    node.declare_parameter("bench_int", 0)
    node.declare_parameter("bench_str", "init")

    t0 = time.time()
    for i in range(iterations):
        node.set_parameters(
            [rclpy.parameter.Parameter("bench_int", value=i)]
        )
    t1 = time.time()
    write_elapsed = t1 - t0

    t2 = time.time()
    for _ in range(iterations):
        _ = node.get_parameter("bench_int").value
    t3 = time.time()
    read_elapsed = t3 - t2

    node.destroy_node()
    return {
        "write_ops_per_sec": iterations / write_elapsed,
        "read_ops_per_sec": iterations / read_elapsed,
        "iterations": iterations,
    }


def benchmark_concurrency(num_threads, msgs_per_thread, calls_per_thread,
                          param_ops_per_thread):
    conc = {"thread_count": num_threads}

    # --- Multi-publisher topic ---
    total_msgs = num_threads * msgs_per_thread
    node = Node("py_bench_conc_topic")
    latencies = []
    lat_lock = threading.Lock()
    recv_count = [0]

    from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
    topic_qos = QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=total_msgs,
        reliability=QoSReliabilityPolicy.RELIABLE,
    )

    def on_msg(msg):
        now_ns = time.time_ns()
        sent_ns = int(msg.data)
        with lat_lock:
            latencies.append(now_ns - sent_ns)
            recv_count[0] += 1

    cb_group = ReentrantCallbackGroup()
    node.create_subscription(String, "bench_conc_topic_py", on_msg, topic_qos,
                             callback_group=cb_group)

    executor = MultiThreadedExecutor(num_threads=num_threads + 1)
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    def pub_worker():
        pub = node.create_publisher(String, "bench_conc_topic_py", topic_qos)
        for _ in range(msgs_per_thread):
            msg = String()
            msg.data = str(time.time_ns())
            pub.publish(msg)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futs = [pool.submit(pub_worker) for _ in range(num_threads)]
        for f in futs:
            f.result()
    drain_start = time.time()
    while time.time() - drain_start < 5.0:
        with lat_lock:
            if recv_count[0] >= total_msgs:
                break
        time.sleep(0.01)
    t1 = time.time()
    elapsed = t1 - t0

    executor.shutdown()

    total_sent = total_msgs
    received = len(latencies)
    avg_lat = (sum(latencies) / received / 1000.0) if received else 0
    conc["topic_multi_pub"] = {
        "total_sent": total_sent,
        "total_received": received,
        "elapsed_s": round(elapsed, 4),
        "aggregate_throughput": round(received / elapsed, 2),
        "avg_latency_us": round(avg_lat, 2),
    }
    node.destroy_node()

    # --- Concurrent service calls ---
    node = Node("py_bench_conc_srv")
    cb_group = ReentrantCallbackGroup()

    def handle(req, resp):
        resp.sum = req.a + req.b
        return resp

    node.create_service(AddTwoInts, "bench_conc_srv_py", handle,
                        callback_group=cb_group)
    client = node.create_client(AddTwoInts, "bench_conc_srv_py",
                                callback_group=cb_group)

    executor = MultiThreadedExecutor(num_threads=num_threads + 1)
    executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    while not client.wait_for_service(timeout_sec=0.1):
        pass

    call_latencies = []
    call_lock = threading.Lock()
    call_count = [0]

    def srv_worker(tid):
        for i in range(calls_per_thread):
            req = AddTwoInts.Request()
            req.a = tid
            req.b = i
            ct0 = time.time_ns()
            future = client.call_async(req)
            rclpy.spin_until_future_complete(node, future, timeout_sec=5.0)
            ct1 = time.time_ns()
            with call_lock:
                call_latencies.append(ct1 - ct0)
                call_count[0] += 1

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futs = [pool.submit(srv_worker, t) for t in range(num_threads)]
        for f in futs:
            f.result()
    t1 = time.time()
    elapsed = t1 - t0

    executor.shutdown()

    total_calls = call_count[0]
    avg_lat = (sum(call_latencies) / total_calls / 1000.0) if total_calls else 0
    conc["service_concurrent"] = {
        "total_calls": total_calls,
        "elapsed_s": round(elapsed, 4),
        "aggregate_throughput": round(total_calls / elapsed, 2),
        "avg_latency_us": round(avg_lat, 2),
    }
    node.destroy_node()

    # --- Concurrent param read/write ---
    node = Node("py_bench_conc_param")
    node.declare_parameter("conc_int", 0)
    total_ops = [0]
    ops_lock = threading.Lock()

    def param_worker(tid):
        local_ops = 0
        for i in range(param_ops_per_thread):
            node.set_parameters(
                [rclpy.parameter.Parameter("conc_int", value=tid * 1000 + i)]
            )
            _ = node.get_parameter("conc_int").value
            local_ops += 2
        with ops_lock:
            total_ops[0] += local_ops

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futs = [pool.submit(param_worker, t) for t in range(num_threads)]
        for f in futs:
            f.result()
    t1 = time.time()
    elapsed = t1 - t0

    conc["param_concurrent_rw"] = {
        "total_ops": total_ops[0],
        "elapsed_s": round(elapsed, 4),
        "aggregate_throughput": round(total_ops[0] / elapsed, 2),
    }
    node.destroy_node()

    return conc


def benchmark_multi_node(num_threads, msgs_per_thread, calls_per_thread):
    from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
    mn = {"thread_count": num_threads}
    total_msgs = num_threads * msgs_per_thread

    topic_qos = QoSProfile(
        history=QoSHistoryPolicy.KEEP_LAST,
        depth=total_msgs,
        reliability=QoSReliabilityPolicy.RELIABLE,
    )

    # --- Multi-node topic: each pub thread owns its own node ---
    latencies = []
    lat_lock = threading.Lock()
    recv_count = [0]
    sub_ready = threading.Event()
    stop_sub = threading.Event()

    def sub_worker():
        sub_node = Node("py_mn_sub")
        sub_executor = SingleThreadedExecutor()
        sub_executor.add_node(sub_node)

        def on_msg(msg):
            now_ns = time.time_ns()
            sent_ns = int(msg.data)
            with lat_lock:
                latencies.append(now_ns - sent_ns)
                recv_count[0] += 1

        sub_node.create_subscription(String, "bench_mn_topic_py", on_msg, topic_qos)
        sub_ready.set()
        while not stop_sub.is_set():
            sub_executor.spin_once(timeout_sec=0.001)
        sub_node.destroy_node()

    sub_thread = threading.Thread(target=sub_worker, daemon=True)
    sub_thread.start()
    sub_ready.wait()
    time.sleep(0.1)

    def pub_worker(tid):
        pub_node = Node(f"py_mn_pub_{tid}")
        pub = pub_node.create_publisher(String, "bench_mn_topic_py", topic_qos)
        for _ in range(msgs_per_thread):
            msg = String()
            msg.data = str(time.time_ns())
            pub.publish(msg)
        pub_node.destroy_node()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futs = [pool.submit(pub_worker, t) for t in range(num_threads)]
        for f in futs:
            f.result()
    drain_start = time.time()
    while time.time() - drain_start < 5.0:
        with lat_lock:
            if recv_count[0] >= total_msgs:
                break
        time.sleep(0.01)
    t1 = time.time()
    elapsed = t1 - t0

    stop_sub.set()
    sub_thread.join(timeout=2)

    total_sent = total_msgs
    received = len(latencies)
    avg_lat = (sum(latencies) / received / 1000.0) if received else 0
    mn["topic"] = {
        "total_sent": total_sent,
        "total_received": received,
        "elapsed_s": round(elapsed, 4),
        "aggregate_throughput": round(received / elapsed, 2),
        "avg_latency_us": round(avg_lat, 2),
    }

    # --- Multi-node service: server in own thread, each client in own node ---
    srv_ready = threading.Event()
    stop_srv = threading.Event()

    def srv_worker():
        srv_node = Node("py_mn_srv")
        srv_executor = SingleThreadedExecutor()
        srv_executor.add_node(srv_node)

        def handle(req, resp):
            resp.sum = req.a + req.b
            return resp

        srv_node.create_service(AddTwoInts, "bench_mn_srv_py", handle)
        srv_ready.set()
        while not stop_srv.is_set():
            srv_executor.spin_once(timeout_sec=0.001)
        srv_node.destroy_node()

    srv_thread = threading.Thread(target=srv_worker, daemon=True)
    srv_thread.start()
    srv_ready.wait()
    time.sleep(0.1)

    call_latencies = []
    call_lock = threading.Lock()
    call_count = [0]

    def cli_worker(tid):
        cli_node = Node(f"py_mn_cli_{tid}")
        cli_executor = SingleThreadedExecutor()
        cli_executor.add_node(cli_node)
        client = cli_node.create_client(AddTwoInts, "bench_mn_srv_py")
        while not client.wait_for_service(timeout_sec=0.1):
            cli_executor.spin_once(timeout_sec=0)
        for i in range(calls_per_thread):
            req = AddTwoInts.Request()
            req.a = tid
            req.b = i
            ct0 = time.time_ns()
            future = client.call_async(req)
            cli_executor.spin_until_future_complete(future, timeout_sec=5.0)
            ct1 = time.time_ns()
            with call_lock:
                call_latencies.append(ct1 - ct0)
                call_count[0] += 1
        cli_node.destroy_node()

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futs = [pool.submit(cli_worker, t) for t in range(num_threads)]
        for f in futs:
            f.result()
    t1 = time.time()
    elapsed = t1 - t0

    stop_srv.set()
    srv_thread.join(timeout=2)

    total_calls = call_count[0]
    avg_lat = (sum(call_latencies) / total_calls / 1000.0) if total_calls else 0
    mn["service"] = {
        "total_calls": total_calls,
        "elapsed_s": round(elapsed, 4),
        "aggregate_throughput": round(total_calls / elapsed, 2),
        "avg_latency_us": round(avg_lat, 2),
    }

    return mn


def main(args=None):
    rclpy.init(args=args)

    topic_iters = 5000
    service_iters = 2000
    action_order = 20
    param_iters = 100000
    conc_threads = 4
    conc_msgs = 2000
    conc_calls = 500
    conc_param_ops = 10000

    argv = sys.argv[1:]
    for arg in argv:
        if arg.startswith("--topic-iters="):
            topic_iters = int(arg.split("=")[1])
        elif arg.startswith("--service-iters="):
            service_iters = int(arg.split("=")[1])
        elif arg.startswith("--action-order="):
            action_order = int(arg.split("=")[1])
        elif arg.startswith("--param-iters="):
            param_iters = int(arg.split("=")[1])
        elif arg.startswith("--conc-threads="):
            conc_threads = int(arg.split("=")[1])
        elif arg.startswith("--conc-msgs="):
            conc_msgs = int(arg.split("=")[1])
        elif arg.startswith("--conc-calls="):
            conc_calls = int(arg.split("=")[1])
        elif arg.startswith("--conc-param-ops="):
            conc_param_ops = int(arg.split("=")[1])

    results = {"language": "python"}
    results["topic"] = benchmark_topic(topic_iters)
    results["service"] = benchmark_service(service_iters)
    results["action"] = benchmark_action(action_order)
    results["param"] = benchmark_param(param_iters)
    results["concurrency"] = benchmark_concurrency(
        conc_threads, conc_msgs, conc_calls, conc_param_ops)
    results["multi_node"] = benchmark_multi_node(
        conc_threads, conc_msgs, conc_calls)

    print(json.dumps(results, indent=2))
    rclpy.shutdown()
