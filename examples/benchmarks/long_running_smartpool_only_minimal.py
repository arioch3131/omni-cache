"""
Long-running SmartPool-only benchmark (minimal overhead).

Goal:
- Provide an "in-between" benchmark to compare with:
  1) micro cProfile benchmark (very synthetic)
  2) full long_running_performance.py (integrated, noisier)
"""

from __future__ import annotations

import argparse
import random
import string
import time
from dataclasses import dataclass
from typing import Any

from omni_cache import create_adapter
from omni_cache.core.interfaces import CacheBackend


def generate_random_string(length: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


@dataclass
class PooledData:
    data: str
    timestamp: float
    item_id: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal SmartPool long-running benchmark.")
    parser.add_argument("--duration-seconds", type=int, default=60)
    parser.add_argument("--report-interval-seconds", type=int, default=30)
    parser.add_argument("--iterations-per-batch", type=int, default=1000)
    parser.add_argument("--keyspace", type=int, default=1000)
    parser.add_argument("--mode", choices=("borrow", "getput"), default="borrow")
    parser.add_argument("--auto-wrap", action="store_true")
    parser.add_argument("--max-size", type=int, default=1000)
    parser.add_argument("--initial-size", type=int, default=2)
    parser.add_argument("--enable-perf-metrics", action="store_true")
    parser.add_argument(
        "--payload",
        choices=("random", "static"),
        default="random",
        help="Payload generation mode for per-op updates.",
    )
    return parser.parse_args()


def make_adapter(args: argparse.Namespace) -> Any:
    def create_simple_data_object(key: str | None = None) -> PooledData:
        _ = key
        return PooledData(
            data=generate_random_string(1024),
            timestamp=time.time(),
            item_id=random.randint(1, 1_000_000),
        )

    config = {
        "name": "smartpool_only_minimal",
        "backend": CacheBackend.SMARTPOOL.value,
        "factory_function": create_simple_data_object,
        "initial_size": args.initial_size,
        "min_size": min(2, args.initial_size),
        "max_size": args.max_size,
        "enable_auto_tuning": False,
        "enable_performance_metrics": args.enable_perf_metrics,
        "enable_stats": False,
        "auto_wrap_objects": args.auto_wrap,
        "memory_preset": "HIGH_THROUGHPUT",
        "log_level": "CRITICAL",
    }
    adapter = create_adapter(CacheBackend.SMARTPOOL, config)
    if not adapter.connect() or not adapter.is_connected():
        raise RuntimeError("Failed to connect SmartPool adapter")
    return adapter


def run_benchmark(adapter: Any, args: argparse.Namespace) -> None:
    print("Starting minimal smartpool long-running benchmark...")
    print("=" * 60)
    print(
        f"mode={args.mode} duration={args.duration_seconds}s keyspace={args.keyspace} "
        f"auto_wrap={args.auto_wrap} payload={args.payload}"
    )

    started = time.time()
    last_report = started
    total_ops = 0
    total_duration = 0.0
    static_value = "x" * 1024

    while (time.time() - started) < args.duration_seconds:
        iter_start = time.perf_counter()

        if args.mode == "borrow":
            for i in range(args.iterations_per_batch):
                idx = (total_ops + i) % args.keyspace
                key = f"key{idx}"
                value = static_value if args.payload == "static" else generate_random_string(1024)
                with adapter.borrow(key) as obj:
                    obj.data = value
        else:
            for i in range(args.iterations_per_batch):
                idx = (total_ops + i) % args.keyspace
                key = f"key{idx}"
                value = static_value if args.payload == "static" else generate_random_string(1024)
                obj = adapter.get(key)
                if obj is None:
                    continue
                obj.data = value
                adapter.put(obj)

        iter_end = time.perf_counter()
        total_ops += args.iterations_per_batch
        total_duration += iter_end - iter_start

        now = time.time()
        if now - last_report >= args.report_interval_seconds:
            elapsed = now - started
            avg_ms = (total_duration / max(total_ops, 1)) * 1000
            ops_s = total_ops / max(elapsed, 1e-9)
            print(f"[{int(elapsed)}s] avg={avg_ms:.2f}ms throughput={ops_s:.1f} ops/sec")
            last_report = now

    elapsed = time.time() - started
    avg_ms = (total_duration / max(total_ops, 1)) * 1000
    ops_s = total_ops / max(elapsed, 1e-9)
    print("\n--- Final Results ---")
    print(f"Total Operations: {total_ops}")
    print(f"Average Time: {avg_ms:.2f}ms")
    print(f"Overall Throughput: {ops_s:.1f} ops/sec")


def main() -> None:
    args = parse_args()
    adapter = make_adapter(args)
    try:
        run_benchmark(adapter, args)
    finally:
        adapter.disconnect()


if __name__ == "__main__":
    main()
