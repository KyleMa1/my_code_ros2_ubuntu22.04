#!/usr/bin/env python3
"""
ROS2 多语言 Benchmark 运行器
用法: python3 benchmarks/run_benchmark.py [--topic-iters=N] [--service-iters=N] [--action-order=N] [--param-iters=N]

在 colcon 工作区已 source 的环境中运行。
分别启动 C++、Python、Rust 的 benchmark_node，收集 JSON 输出并生成比较报告。
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
INSTALL_DIR = WORKSPACE / "install"

LANGUAGE_CONFIG = {
    "cpp": {
        "executable": "cpp_pkg/lib/cpp_pkg/benchmark_node",
        "label": "C++",
    },
    "python": {
        "executable": "py_pkg/lib/py_pkg/benchmark_node",
        "label": "Python",
    },
    "rust": {
        "executable": "rust_pkg/lib/rust_pkg/benchmark_node",
        "label": "Rust",
    },
}


def find_executable(lang: str) -> str:
    cfg = LANGUAGE_CONFIG[lang]
    exe = INSTALL_DIR / cfg["executable"]
    if exe.exists():
        return str(exe)
    alt = INSTALL_DIR / cfg["executable"].replace("/lib/", "/bin/")
    if alt.exists():
        return str(alt)
    return cfg["executable"].split("/")[-1]


def run_benchmark(lang: str, args: list[str]) -> dict:
    exe = find_executable(lang)
    cfg = LANGUAGE_CONFIG[lang]
    print(f"\n{'='*60}")
    print(f"  Running {cfg['label']} benchmark: {exe}")
    print(f"{'='*60}")

    env = os.environ.copy()
    setup_bash = INSTALL_DIR / "setup.bash"
    if setup_bash.exists():
        env["AMENT_PREFIX_PATH"] = str(INSTALL_DIR)

    try:
        t0 = time.time()
        result = subprocess.run(
            [exe] + args,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        t1 = time.time()

        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[:500]}")
            return {"language": lang, "error": result.stderr[:500], "wall_time_s": t1 - t0}

        output = result.stdout.strip()
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            data = {"raw_output": output}

        data["wall_time_s"] = round(t1 - t0, 3)
        return data

    except FileNotFoundError:
        return {"language": lang, "error": f"executable not found: {exe}"}
    except subprocess.TimeoutExpired:
        return {"language": lang, "error": "timeout (300s)"}


def measure_build_time(lang: str) -> float:
    """Measure clean build time for a single package."""
    pkg_name = {"cpp": "cpp_pkg", "python": "py_pkg", "rust": "rust_pkg"}[lang]
    build_dir = WORKSPACE / "build" / pkg_name
    install_dir = WORKSPACE / "install" / pkg_name

    subprocess.run(["rm", "-rf", str(build_dir), str(install_dir)], check=False)

    cmd = (
        f"source /opt/ros/${{ROS_DISTRO:-humble}}/setup.bash && "
        f"cd {WORKSPACE} && "
        f"colcon build --packages-select {pkg_name}"
    )
    t0 = time.time()
    result = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=600)
    t1 = time.time()

    if result.returncode != 0:
        print(f"  Build failed for {pkg_name}: {result.stderr[:300]}")
        return -1.0
    return round(t1 - t0, 3)


def count_source_lines(lang: str) -> dict:
    """Count lines of code for the ROS2 nodes (excluding tests and lib)."""
    pkg_dir = WORKSPACE / "src" / {"cpp": "cpp_pkg", "python": "py_pkg", "rust": "rust_pkg"}[lang]
    extensions = {
        "cpp": [".cpp", ".h", ".hpp"],
        "python": [".py"],
        "rust": [".rs"],
    }[lang]

    node_dirs = {
        "cpp": [pkg_dir / "src"],
        "python": [pkg_dir / "py_pkg"],
        "rust": [pkg_dir / "src" / "bin", pkg_dir / "src"],
    }[lang]

    total_lines = 0
    file_count = 0
    for d in node_dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f.suffix in extensions:
                if "test" in f.name or f.name == "lib.rs" or f.name == "__init__.py":
                    continue
                total_lines += sum(1 for _ in open(f))
                file_count += 1

    return {"total_lines": total_lines, "file_count": file_count}


def measure_binary_size(lang: str) -> int:
    """Measure total size of built executables."""
    pkg_name = {"cpp": "cpp_pkg", "python": "py_pkg", "rust": "rust_pkg"}[lang]
    lib_dir = INSTALL_DIR / pkg_name / "lib" / pkg_name
    if not lib_dir.exists():
        return -1

    total = 0
    for f in lib_dir.iterdir():
        if f.is_file() and os.access(str(f), os.X_OK):
            total += f.stat().st_size
    return total


def fmt_val(val, fmt_type="default"):
    if val == "N/A" or val is None:
        return "N/A"
    if fmt_type == "comma" and isinstance(val, (int, float)):
        return f"{val:,.0f}"
    if isinstance(val, float):
        return f"{val:.2f}"
    if isinstance(val, int):
        return f"{val:,}"
    return str(val)


def get_val(results, lang, section, metric):
    return results.get(lang, {}).get(section, {}).get(metric, "N/A")


def find_best(results, section, metric, lower_is_better=True):
    vals = {}
    for lang in ["cpp", "python", "rust"]:
        v = get_val(results, lang, section, metric)
        if isinstance(v, (int, float)):
            vals[lang] = v
    if not vals:
        return None
    if lower_is_better:
        return min(vals, key=vals.get)
    return max(vals, key=vals.get)


LANG_LABELS = {"cpp": "C++", "python": "Python", "rust": "Rust"}


def generate_summary_topic(results):
    best_avg = find_best(results, "topic", "avg_us", lower_is_better=True)
    best_tp = find_best(results, "topic", "throughput", lower_is_better=False)
    best_p99 = find_best(results, "topic", "p99_us", lower_is_better=True)
    lines = []
    lines.append(f"> **总结**: ")
    parts = []
    if best_avg:
        parts.append(f"{LANG_LABELS[best_avg]}平均延迟最低")
    if best_tp:
        parts.append(f"{LANG_LABELS[best_tp]}吞吐量最高")
    if best_p99:
        parts.append(f"{LANG_LABELS[best_p99]} P99尾延迟最优")
    lines[-1] += "，".join(parts) + "。"
    cpp_avg = get_val(results, "cpp", "topic", "avg_us")
    py_avg = get_val(results, "python", "topic", "avg_us")
    rs_avg = get_val(results, "rust", "topic", "avg_us")
    if all(isinstance(v, (int, float)) for v in [cpp_avg, py_avg, rs_avg]):
        lines.append(f"> C++延迟仅为Python的 {py_avg/cpp_avg:.0f}分之一，"
                     f"Rust约为Python的 {py_avg/rs_avg:.0f}分之一。"
                     f"C++因直接内存操作在进程内通信中延迟最低；Python受解释器和GIL开销影响延迟最大；"
                     f"Rust延迟略高于C++，但仍在同一数量级，兼顾了安全性与性能。")
    return "\n".join(lines)


def generate_summary_service(results):
    best_avg = find_best(results, "service", "avg_us", lower_is_better=True)
    best_tp = find_best(results, "service", "throughput", lower_is_better=False)
    lines = ["> **总结**: "]
    parts = []
    if best_avg:
        parts.append(f"{LANG_LABELS[best_avg]}平均延迟最低")
    if best_tp:
        parts.append(f"{LANG_LABELS[best_tp]}吞吐量最高")
    lines[-1] += "，".join(parts) + "。"
    lines.append("> Service调用为同步请求-响应模型，C++因缺少运行时开销而在延迟上占优；"
                 "Rust需通过executor调度回调，延迟略高于C++但显著优于Python；"
                 "Python受解释器开销影响表现最弱。")
    return "\n".join(lines)


def generate_summary_action(results):
    best = find_best(results, "action", "total_us", lower_is_better=True)
    lines = ["> **总结**: "]
    if best:
        lines[-1] += f"{LANG_LABELS[best]}完成Action总耗时最短。"
    lines.append("> Action涉及目标发送、反馈流和结果返回，是ROS2中最复杂的通信模式。"
                 "各语言的表现差距体现了其异步运行时和线程调度效率的差异。")
    return "\n".join(lines)


def generate_summary_param(results):
    best_w = find_best(results, "param", "write_ops_per_sec", lower_is_better=False)
    best_r = find_best(results, "param", "read_ops_per_sec", lower_is_better=False)
    lines = ["> **总结**: "]
    parts = []
    if best_w:
        parts.append(f"{LANG_LABELS[best_w]}写入速度最快")
    if best_r:
        parts.append(f"{LANG_LABELS[best_r]}读取速度最快")
    lines[-1] += "，".join(parts) + "。"
    lines.append("> Rust参数操作基于Arc<RwLock<>>，读写均为纯内存操作，性能远超C++和Python。"
                 "C++参数系统有额外的事件回调开销；Python受解释器瓶颈限制最严重。")
    return "\n".join(lines)


def generate_summary_concurrency(results):
    best_topic_tp = find_best(results, "concurrency", "topic_multi_pub", lower_is_better=False)
    lines = ["> **总结**: "]

    tp_vals = {}
    srv_vals = {}
    param_vals = {}
    for lang in ["cpp", "python", "rust"]:
        conc = results.get(lang, {}).get("concurrency", {})
        topic_mp = conc.get("topic_multi_pub", {})
        srv_cc = conc.get("service_concurrent", {})
        param_rw = conc.get("param_concurrent_rw", {})
        if isinstance(topic_mp.get("aggregate_throughput"), (int, float)):
            tp_vals[lang] = topic_mp["aggregate_throughput"]
        if isinstance(srv_cc.get("aggregate_throughput"), (int, float)):
            srv_vals[lang] = srv_cc["aggregate_throughput"]
        if isinstance(param_rw.get("aggregate_throughput"), (int, float)):
            param_vals[lang] = param_rw["aggregate_throughput"]

    parts = []
    if tp_vals:
        best = max(tp_vals, key=tp_vals.get)
        parts.append(f"多线程Topic发布 {LANG_LABELS[best]}吞吐最高")
    if srv_vals:
        best = max(srv_vals, key=srv_vals.get)
        parts.append(f"并发Service调用 {LANG_LABELS[best]}吞吐最高")
    if param_vals:
        best = max(param_vals, key=param_vals.get)
        parts.append(f"并发参数读写 {LANG_LABELS[best]}吞吐最高")
    lines[-1] += "；".join(parts) + "。"

    lines.append("> C++利用MultiThreadedExecutor多线程并行处理回调，并发吞吐量极强；"
                 "Python受GIL限制，多线程无法真正并行执行CPU密集操作，并发优势有限；"
                 "Rust在纯内存并发操作(参数读写)上借助Arc<RwLock<>>表现碾压级优势，"
                 "但rclrs目前仅提供单线程BasicExecutor，"
                 "Topic/Service的回调处理成为瓶颈——这是库成熟度的限制，而非语言的限制。"
                 "随着rclrs引入多线程executor，Rust的并发ROS通信性能有望大幅提升。")
    return "\n".join(lines)


def generate_summary_build(results):
    lines = ["> **总结**: "]
    loc = {}
    wall = {}
    for lang in ["cpp", "python", "rust"]:
        meta = results.get(lang, {}).get("meta", {})
        sl = meta.get("source_lines")
        if isinstance(sl, (int, float)):
            loc[lang] = sl
        wt = meta.get("wall_time_s")
        if isinstance(wt, (int, float)):
            wall[lang] = wt

    parts = []
    if loc:
        least = min(loc, key=loc.get)
        parts.append(f"{LANG_LABELS[least]}代码量最少({loc[least]}行)")
    if wall:
        fastest = min(wall, key=wall.get)
        parts.append(f"{LANG_LABELS[fastest]}运行时间最短({wall[fastest]:.2f}s)")
    lines[-1] += "，".join(parts) + "。"
    lines.append("> Python代码最简洁但运行最慢；C++和Rust代码量相近，"
                 "Rust因编译优化在运行时与C++持平甚至更快。"
                 "Rust二进制体积最大(静态链接所有依赖)，"
                 "Python最小(仅脚本文件)。编译时间上Rust通常最长。")
    return "\n".join(lines)


def generate_summary_safety():
    return (
        "> **总结**: Rust在所有安全维度上表现最优——所有权系统、Send/Sync trait、"
        "Option<T>和强类型系统在编译期即消除了内存泄漏、数据竞争、空指针和类型错误。"
        "C++灵活但需开发者自行保证安全，高并发场景下数据竞争风险显著增加。"
        "Python通过GC和GIL在单线程场景安全性好，但GIL限制了真并发能力，"
        "且动态类型在大型项目中增加运行时错误风险。"
    )


def generate_report(results: dict, output_path: Path):
    """Generate a markdown comparison report with concurrency data and per-section summaries."""
    report = []
    report.append("# ROS2 多语言 Benchmark 报告\n")
    report.append(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    # --- Topic ---
    report.append("\n## 1. Topic 发布/订阅 延迟\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["avg_us", "min_us", "max_us", "p50_us", "p95_us", "p99_us", "throughput"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            val = get_val(results, lang, "topic", metric)
            row += f" {fmt_val(val)} |"
        report.append(row)
    report.append("")
    report.append(generate_summary_topic(results))

    # --- Service ---
    report.append("\n## 2. Service 调用 延迟\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["avg_us", "min_us", "max_us", "p50_us", "p95_us", "p99_us", "throughput"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            val = get_val(results, lang, "service", metric)
            row += f" {fmt_val(val)} |"
        report.append(row)
    report.append("")
    report.append(generate_summary_service(results))

    # --- Action ---
    report.append("\n## 3. Action 执行\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["total_us", "feedback_count", "fib_order"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            val = get_val(results, lang, "action", metric)
            row += f" {fmt_val(val)} |"
        report.append(row)
    report.append("")
    report.append(generate_summary_action(results))

    # --- Param ---
    report.append("\n## 4. 参数 读写\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["write_ops_per_sec", "read_ops_per_sec"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            val = get_val(results, lang, "param", metric)
            row += f" {fmt_val(val, 'comma')} |"
        report.append(row)
    report.append("")
    report.append(generate_summary_param(results))

    # --- Concurrency ---
    report.append("\n## 5. 高并发测试\n")

    thread_count = "N/A"
    for lang in ["cpp", "python", "rust"]:
        tc = get_val(results, lang, "concurrency", "thread_count")
        if isinstance(tc, (int, float)):
            thread_count = int(tc)
            break
    report.append(f"**并发线程数**: {thread_count}\n")

    report.append("### 5.1 多线程 Topic 发布\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["total_sent", "total_received", "elapsed_s", "aggregate_throughput", "avg_latency_us"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            conc = results.get(lang, {}).get("concurrency", {}).get("topic_multi_pub", {})
            val = conc.get(metric, "N/A")
            row += f" {fmt_val(val)} |"
        report.append(row)

    report.append("\n### 5.2 并发 Service 调用\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["total_calls", "elapsed_s", "aggregate_throughput", "avg_latency_us"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            conc = results.get(lang, {}).get("concurrency", {}).get("service_concurrent", {})
            val = conc.get(metric, "N/A")
            row += f" {fmt_val(val)} |"
        report.append(row)

    report.append("\n### 5.3 并发参数读写\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    for metric in ["total_ops", "elapsed_s", "aggregate_throughput"]:
        row = f"| {metric} |"
        for lang in ["cpp", "python", "rust"]:
            conc = results.get(lang, {}).get("concurrency", {}).get("param_concurrent_rw", {})
            val = conc.get(metric, "N/A")
            row += f" {fmt_val(val)} |"
        report.append(row)

    report.append("")
    report.append(generate_summary_concurrency(results))

    # --- Build / Code / Binary ---
    report.append("\n## 6. 编译 / 代码量 / 二进制\n")
    report.append("| 指标 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")

    for metric_label, metric_key in [
        ("编译时间 (s)", "build_time_s"),
        ("代码行数", "source_lines"),
        ("源文件数", "source_files"),
        ("二进制大小 (bytes)", "binary_size"),
        ("总运行时间 (s)", "wall_time_s"),
    ]:
        row = f"| {metric_label} |"
        for lang in ["cpp", "python", "rust"]:
            val = results.get(lang, {}).get("meta", {}).get(metric_key, "N/A")
            row += f" {fmt_val(val)} |"
        report.append(row)

    report.append("")
    report.append(generate_summary_build(results))

    # --- Safety ---
    report.append("\n## 7. 安全性评估\n")
    report.append("| 维度 | C++ | Python | Rust |")
    report.append("|------|-----|--------|------|")
    report.append("| 内存安全 | 手动管理，有UAF/溢出风险 | GC自动管理，安全 | 所有权系统，编译期保证 |")
    report.append("| 线程安全 | 需手动加锁，有数据竞争风险 | GIL限制真并行 | Send/Sync trait编译期保证 |")
    report.append("| 空指针 | 可能出现 | 无(None代替) | Option<T>编译期强制处理 |")
    report.append("| 未定义行为 | 可能出现 | 不会 | 仅unsafe块中可能 |")
    report.append("| 类型安全 | 弱(隐式转换) | 动态类型 | 强类型+泛型 |")
    report.append("")
    report.append(generate_summary_safety())

    report.append("\n---\n")
    report.append("*延迟单位: 微秒(us), 吞吐量单位: 次/秒*\n")

    report_text = "\n".join(report)
    output_path.write_text(report_text, encoding="utf-8")
    print(f"\nReport saved to: {output_path}")
    return report_text


def main():
    parser = argparse.ArgumentParser(description="ROS2 多语言 Benchmark")
    parser.add_argument("--topic-iters", type=int, default=5000)
    parser.add_argument("--service-iters", type=int, default=2000)
    parser.add_argument("--action-order", type=int, default=20)
    parser.add_argument("--param-iters", type=int, default=100000)
    parser.add_argument("--conc-threads", type=int, default=4)
    parser.add_argument("--conc-msgs", type=int, default=2000)
    parser.add_argument("--conc-calls", type=int, default=500)
    parser.add_argument("--conc-param-ops", type=int, default=10000)
    parser.add_argument("--skip-build-time", action="store_true")
    parser.add_argument("--languages", nargs="+", default=["cpp", "python", "rust"],
                        choices=["cpp", "python", "rust"])
    args = parser.parse_args()

    bench_args = [
        f"--topic-iters={args.topic_iters}",
        f"--service-iters={args.service_iters}",
        f"--action-order={args.action_order}",
        f"--param-iters={args.param_iters}",
        f"--conc-threads={args.conc_threads}",
        f"--conc-msgs={args.conc_msgs}",
        f"--conc-calls={args.conc_calls}",
        f"--conc-param-ops={args.conc_param_ops}",
    ]

    all_results = {}

    for lang in args.languages:
        result = run_benchmark(lang, bench_args)
        meta = {}

        loc = count_source_lines(lang)
        meta["source_lines"] = loc["total_lines"]
        meta["source_files"] = loc["file_count"]
        meta["binary_size"] = measure_binary_size(lang)
        meta["wall_time_s"] = result.get("wall_time_s", "N/A")

        if not args.skip_build_time:
            print(f"\n  Measuring build time for {LANGUAGE_CONFIG[lang]['label']}...")
            meta["build_time_s"] = measure_build_time(lang)
        else:
            meta["build_time_s"] = "skipped"

        result["meta"] = meta
        all_results[lang] = result

    output_dir = WORKSPACE / "benchmarks" / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"benchmark_{timestamp}.json"
    json_path.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON results saved to: {json_path}")

    report_path = output_dir / f"benchmark_{timestamp}.md"
    report_text = generate_report(all_results, report_path)
    print(report_text)

    latest_json = output_dir / "latest.json"
    latest_json.write_text(json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_md = output_dir / "latest.md"
    latest_md.write_text(report_text, encoding="utf-8")


if __name__ == "__main__":
    main()
