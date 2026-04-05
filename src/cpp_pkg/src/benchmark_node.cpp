#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <iostream>
#include <mutex>
#include <numeric>
#include <vector>
#include <thread>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp/executors/multi_threaded_executor.hpp"
#include "rclcpp_action/rclcpp_action.hpp"
#include "std_msgs/msg/string.hpp"
#include "example_interfaces/srv/add_two_ints.hpp"
#include "example_interfaces/action/fibonacci.hpp"

using namespace std::chrono;
using Fibonacci = example_interfaces::action::Fibonacci;
using GoalHandleFib = rclcpp_action::ServerGoalHandle<Fibonacci>;

struct Stats {
    double avg_ns;
    double min_ns;
    double max_ns;
    double p50_ns;
    double p95_ns;
    double p99_ns;
    double throughput;
};

Stats compute_stats(std::vector<int64_t>& latencies, double elapsed_s) {
    std::sort(latencies.begin(), latencies.end());
    size_t n = latencies.size();
    double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
    return Stats{
        sum / n,
        static_cast<double>(latencies.front()),
        static_cast<double>(latencies.back()),
        static_cast<double>(latencies[n / 2]),
        static_cast<double>(latencies[static_cast<size_t>(n * 0.95)]),
        static_cast<double>(latencies[static_cast<size_t>(n * 0.99)]),
        n / elapsed_s
    };
}

void print_json_stats(const std::string& name, const Stats& s) {
    std::cout << "  \"" << name << "\": {"
              << "\"avg_us\": " << s.avg_ns / 1000.0
              << ", \"min_us\": " << s.min_ns / 1000.0
              << ", \"max_us\": " << s.max_ns / 1000.0
              << ", \"p50_us\": " << s.p50_ns / 1000.0
              << ", \"p95_us\": " << s.p95_ns / 1000.0
              << ", \"p99_us\": " << s.p99_ns / 1000.0
              << ", \"throughput\": " << s.throughput
              << "}";
}

void benchmark_topic(rclcpp::Node::SharedPtr node, int iterations) {
    auto pub = node->create_publisher<std_msgs::msg::String>("bench_topic_cpp", rclcpp::QoS(100));
    std::vector<int64_t> latencies;
    latencies.reserve(iterations);

    auto sub = node->create_subscription<std_msgs::msg::String>(
        "bench_topic_cpp", rclcpp::QoS(100),
        [&latencies](const std_msgs::msg::String::SharedPtr msg) {
            auto now = high_resolution_clock::now().time_since_epoch();
            auto now_ns = duration_cast<nanoseconds>(now).count();
            auto sent_ns = std::stoll(msg->data);
            latencies.push_back(now_ns - sent_ns);
        });

    auto start = high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        auto msg = std_msgs::msg::String();
        auto now_ns = duration_cast<nanoseconds>(
            high_resolution_clock::now().time_since_epoch()).count();
        msg.data = std::to_string(now_ns);
        pub->publish(msg);
        rclcpp::spin_some(node);
        std::this_thread::sleep_for(microseconds(10));
    }
    for (int i = 0; i < 50; ++i) {
        rclcpp::spin_some(node);
        std::this_thread::sleep_for(milliseconds(1));
    }
    auto end = high_resolution_clock::now();
    double elapsed_s = duration<double>(end - start).count();

    if (!latencies.empty()) {
        auto stats = compute_stats(latencies, elapsed_s);
        print_json_stats("topic", stats);
    } else {
        std::cout << "  \"topic\": {\"error\": \"no messages received\"}";
    }
}

void benchmark_service(rclcpp::Node::SharedPtr node, int iterations) {
    auto srv = node->create_service<example_interfaces::srv::AddTwoInts>(
        "bench_srv_cpp",
        [](const example_interfaces::srv::AddTwoInts::Request::SharedPtr req,
           example_interfaces::srv::AddTwoInts::Response::SharedPtr resp) {
            resp->sum = req->a + req->b;
        });

    auto client = node->create_client<example_interfaces::srv::AddTwoInts>("bench_srv_cpp");
    while (!client->wait_for_service(seconds(1))) {
        rclcpp::spin_some(node);
    }

    std::vector<int64_t> latencies;
    latencies.reserve(iterations);

    auto start = high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        auto req = std::make_shared<example_interfaces::srv::AddTwoInts::Request>();
        req->a = i;
        req->b = 1;
        auto t0 = high_resolution_clock::now();
        auto future = client->async_send_request(req);
        rclcpp::spin_until_future_complete(node, future, seconds(5));
        auto t1 = high_resolution_clock::now();
        latencies.push_back(duration_cast<nanoseconds>(t1 - t0).count());
    }
    auto end = high_resolution_clock::now();
    double elapsed_s = duration<double>(end - start).count();

    auto stats = compute_stats(latencies, elapsed_s);
    print_json_stats("service", stats);
}

void benchmark_action(rclcpp::Node::SharedPtr node, int fib_order) {
    auto action_server = rclcpp_action::create_server<Fibonacci>(
        node, "bench_action_cpp",
        [](const rclcpp_action::GoalUUID&, std::shared_ptr<const Fibonacci::Goal>) {
            return rclcpp_action::GoalResponse::ACCEPT_AND_EXECUTE;
        },
        [](const std::shared_ptr<GoalHandleFib>) {
            return rclcpp_action::CancelResponse::ACCEPT;
        },
        [](const std::shared_ptr<GoalHandleFib> gh) {
            std::thread([gh]() {
                auto goal = gh->get_goal();
                auto fb = std::make_shared<Fibonacci::Feedback>();
                auto result = std::make_shared<Fibonacci::Result>();
                int prev = 0, curr = 1;
                for (int i = 0; i < goal->order; ++i) {
                    fb->sequence.push_back(curr);
                    gh->publish_feedback(fb);
                    int next = prev + curr;
                    prev = curr;
                    curr = next;
                }
                result->sequence = fb->sequence;
                gh->succeed(result);
            }).detach();
        });

    auto action_client = rclcpp_action::create_client<Fibonacci>(node, "bench_action_cpp");
    action_client->wait_for_action_server(seconds(5));

    auto goal = Fibonacci::Goal();
    goal.order = fib_order;
    int feedback_count = 0;

    auto opts = rclcpp_action::Client<Fibonacci>::SendGoalOptions();
    opts.feedback_callback = [&feedback_count](auto, auto) { ++feedback_count; };

    auto t0 = high_resolution_clock::now();
    auto goal_future = action_client->async_send_goal(goal, opts);
    rclcpp::spin_until_future_complete(node, goal_future, seconds(10));
    auto goal_handle = goal_future.get();
    if (goal_handle) {
        auto result_future = action_client->async_get_result(goal_handle);
        rclcpp::spin_until_future_complete(node, result_future, seconds(10));
    }
    auto t1 = high_resolution_clock::now();
    double elapsed_us = duration_cast<microseconds>(t1 - t0).count();

    std::cout << "  \"action\": {"
              << "\"total_us\": " << elapsed_us
              << ", \"feedback_count\": " << feedback_count
              << ", \"fib_order\": " << fib_order
              << "}";
}

void benchmark_param(rclcpp::Node::SharedPtr node, int iterations) {
    node->declare_parameter("bench_int", 0);
    node->declare_parameter("bench_str", "init");

    auto t0 = high_resolution_clock::now();
    for (int i = 0; i < iterations; ++i) {
        node->set_parameter(rclcpp::Parameter("bench_int", i));
    }
    auto t1 = high_resolution_clock::now();
    double write_elapsed_s = duration<double>(t1 - t0).count();

    auto t2 = high_resolution_clock::now();
    volatile int64_t sink = 0;
    for (int i = 0; i < iterations; ++i) {
        sink = node->get_parameter("bench_int").as_int();
    }
    auto t3 = high_resolution_clock::now();
    double read_elapsed_s = duration<double>(t3 - t2).count();

    std::cout << "  \"param\": {"
              << "\"write_ops_per_sec\": " << iterations / write_elapsed_s
              << ", \"read_ops_per_sec\": " << iterations / read_elapsed_s
              << ", \"iterations\": " << iterations
              << "}";
}

void benchmark_concurrency(int num_threads, int msgs_per_thread,
                           int calls_per_thread, int param_ops_per_thread) {
    std::cout << "  \"concurrency\": {\"thread_count\": " << num_threads;

    // --- Multi-publisher topic ---
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_conc_topic");
        std::mutex lat_mutex;
        std::vector<int64_t> latencies;
        latencies.reserve(num_threads * msgs_per_thread);

        auto sub = node->create_subscription<std_msgs::msg::String>(
            "bench_conc_topic_cpp", rclcpp::QoS(2000),
            [&](const std_msgs::msg::String::SharedPtr msg) {
                auto now_ns = duration_cast<nanoseconds>(
                    high_resolution_clock::now().time_since_epoch()).count();
                auto sent_ns = std::stoll(msg->data);
                std::lock_guard<std::mutex> lk(lat_mutex);
                latencies.push_back(now_ns - sent_ns);
            });

        auto executor = std::make_shared<rclcpp::executors::MultiThreadedExecutor>();
        executor->add_node(node);
        std::thread spin_thread([&executor]() { executor->spin(); });

        std::vector<std::thread> workers;
        auto t0 = high_resolution_clock::now();
        for (int t = 0; t < num_threads; ++t) {
            workers.emplace_back([&node, msgs_per_thread]() {
                auto pub = node->create_publisher<std_msgs::msg::String>(
                    "bench_conc_topic_cpp", rclcpp::QoS(2000));
                for (int i = 0; i < msgs_per_thread; ++i) {
                    auto msg = std_msgs::msg::String();
                    msg.data = std::to_string(duration_cast<nanoseconds>(
                        high_resolution_clock::now().time_since_epoch()).count());
                    pub->publish(msg);
                }
            });
        }
        for (auto& w : workers) w.join();
        std::this_thread::sleep_for(milliseconds(300));
        auto t1 = high_resolution_clock::now();
        double elapsed_s = duration<double>(t1 - t0).count();

        executor->cancel();
        spin_thread.join();

        size_t received = latencies.size();
        double avg_lat = 0;
        if (!latencies.empty()) {
            double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
            avg_lat = sum / latencies.size() / 1000.0;
        }

        std::cout << ", \"topic_multi_pub\": {"
                  << "\"total_sent\": " << num_threads * msgs_per_thread
                  << ", \"total_received\": " << received
                  << ", \"elapsed_s\": " << elapsed_s
                  << ", \"aggregate_throughput\": " << received / elapsed_s
                  << ", \"avg_latency_us\": " << avg_lat << "}";
    }

    // --- Concurrent service calls ---
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_conc_srv");
        auto srv = node->create_service<example_interfaces::srv::AddTwoInts>(
            "bench_conc_srv_cpp",
            [](const example_interfaces::srv::AddTwoInts::Request::SharedPtr req,
               example_interfaces::srv::AddTwoInts::Response::SharedPtr resp) {
                resp->sum = req->a + req->b;
            });

        auto executor = std::make_shared<rclcpp::executors::MultiThreadedExecutor>();
        executor->add_node(node);
        std::thread spin_thread([&executor]() { executor->spin(); });

        auto client = node->create_client<example_interfaces::srv::AddTwoInts>("bench_conc_srv_cpp");
        while (!client->wait_for_service(seconds(1))) {}

        std::atomic<int64_t> total_calls{0};
        std::mutex lat_mutex;
        std::vector<int64_t> latencies;
        latencies.reserve(num_threads * calls_per_thread);

        std::vector<std::thread> workers;
        auto t0 = high_resolution_clock::now();
        for (int t = 0; t < num_threads; ++t) {
            workers.emplace_back([&, t]() {
                for (int i = 0; i < calls_per_thread; ++i) {
                    auto req = std::make_shared<example_interfaces::srv::AddTwoInts::Request>();
                    req->a = t;
                    req->b = i;
                    auto call_t0 = high_resolution_clock::now();
                    auto future = client->async_send_request(req);
                    if (future.wait_for(seconds(5)) == std::future_status::ready) {
                        auto call_t1 = high_resolution_clock::now();
                        auto lat = duration_cast<nanoseconds>(call_t1 - call_t0).count();
                        std::lock_guard<std::mutex> lk(lat_mutex);
                        latencies.push_back(lat);
                        total_calls.fetch_add(1);
                    }
                }
            });
        }
        for (auto& w : workers) w.join();
        auto t1 = high_resolution_clock::now();
        double elapsed_s = duration<double>(t1 - t0).count();

        executor->cancel();
        spin_thread.join();

        double avg_lat = 0;
        if (!latencies.empty()) {
            double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
            avg_lat = sum / latencies.size() / 1000.0;
        }

        std::cout << ", \"service_concurrent\": {"
                  << "\"total_calls\": " << total_calls.load()
                  << ", \"elapsed_s\": " << elapsed_s
                  << ", \"aggregate_throughput\": " << total_calls.load() / elapsed_s
                  << ", \"avg_latency_us\": " << avg_lat << "}";
    }

    // --- Concurrent param read/write ---
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_conc_param");
        node->declare_parameter("conc_int", 0);

        std::atomic<int64_t> total_ops{0};
        std::vector<std::thread> workers;
        auto t0 = high_resolution_clock::now();
        for (int t = 0; t < num_threads; ++t) {
            workers.emplace_back([&node, param_ops_per_thread, &total_ops, t]() {
                for (int i = 0; i < param_ops_per_thread; ++i) {
                    node->set_parameter(rclcpp::Parameter("conc_int", t * 1000 + i));
                    volatile auto v = node->get_parameter("conc_int").as_int();
                    (void)v;
                    total_ops.fetch_add(2);
                }
            });
        }
        for (auto& w : workers) w.join();
        auto t1 = high_resolution_clock::now();
        double elapsed_s = duration<double>(t1 - t0).count();

        std::cout << ", \"param_concurrent_rw\": {"
                  << "\"total_ops\": " << total_ops.load()
                  << ", \"elapsed_s\": " << elapsed_s
                  << ", \"aggregate_throughput\": " << total_ops.load() / elapsed_s << "}";
    }

    std::cout << "}";
}

int main(int argc, char* argv[]) {
    rclcpp::init(argc, argv);

    int topic_iters = 5000;
    int service_iters = 2000;
    int action_order = 20;
    int param_iters = 100000;

    int conc_threads = 4;
    int conc_msgs = 2000;
    int conc_calls = 500;
    int conc_param_ops = 10000;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg.find("--topic-iters=") == 0) topic_iters = std::stoi(arg.substr(14));
        else if (arg.find("--service-iters=") == 0) service_iters = std::stoi(arg.substr(16));
        else if (arg.find("--action-order=") == 0) action_order = std::stoi(arg.substr(15));
        else if (arg.find("--param-iters=") == 0) param_iters = std::stoi(arg.substr(14));
        else if (arg.find("--conc-threads=") == 0) conc_threads = std::stoi(arg.substr(15));
        else if (arg.find("--conc-msgs=") == 0) conc_msgs = std::stoi(arg.substr(12));
        else if (arg.find("--conc-calls=") == 0) conc_calls = std::stoi(arg.substr(13));
        else if (arg.find("--conc-param-ops=") == 0) conc_param_ops = std::stoi(arg.substr(17));
    }

    std::cout << "{\"language\": \"cpp\"," << std::endl;

    {
        auto node = rclcpp::Node::make_shared("cpp_bench_topic");
        benchmark_topic(node, topic_iters);
        std::cout << "," << std::endl;
    }
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_service");
        benchmark_service(node, service_iters);
        std::cout << "," << std::endl;
    }
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_action");
        benchmark_action(node, action_order);
        std::cout << "," << std::endl;
    }
    {
        auto node = rclcpp::Node::make_shared("cpp_bench_param");
        benchmark_param(node, param_iters);
        std::cout << "," << std::endl;
    }

    benchmark_concurrency(conc_threads, conc_msgs, conc_calls, conc_param_ops);
    std::cout << std::endl;

    std::cout << "}" << std::endl;
    rclcpp::shutdown();
    return 0;
}
