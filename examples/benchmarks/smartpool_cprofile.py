"""
SmartPool-only profiling script for cProfile.

Designed to keep noise low:
- Uses only the SmartPool adapter
- Disables adapter stats and performance metrics
- Disables logging output by default
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from typing import Any

from omni_cache import create_adapter
from omni_cache.core.interfaces import CacheBackend


@dataclass
class PooledData:
    """Simple pooled object used by the benchmark loop."""

    data: str
    updated_at: float
    key: str


def _factory(key: str | None = None) -> PooledData:
    key_name = key or "default_pool_key"
    return PooledData(
        data="x" * 1024,
        updated_at=time.time(),
        key=key_name,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SmartPool-only hot-loop for cProfile.")
    parser.add_argument(
        "--mode",
        choices=("borrow", "borrow_fast", "getput"),
        default="borrow",
        help="Operation mode to profile.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=500_000,
        help="Number of operations in the measured loop.",
    )
    parser.add_argument(
        "--warmup-iterations",
        type=int,
        default=20_000,
        help="Warmup operations before measured loop.",
    )
    parser.add_argument(
        "--keyspace",
        type=int,
        default=1000,
        help="Number of logical keys used by workload.",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1000,
        help="SmartPool max_size configuration.",
    )
    parser.add_argument(
        "--initial-size",
        type=int,
        default=2,
        help="SmartPool initial_size configuration.",
    )
    parser.add_argument(
        "--no-disable-logs",
        action="store_true",
        help="Keep logs enabled (disabled by default).",
    )
    parser.add_argument(
        "--disconnect",
        action="store_true",
        help="Call adapter.disconnect() at the end (disabled by default for cleaner profiles).",
    )
    parser.add_argument(
        "--auto-wrap",
        action="store_true",
        help=(
            "Enable SmartPool object wrapping (disabled by default for cleaner hot-path profiling)."
        ),
    )
    return parser.parse_args()


def _build_adapter(initial_size: int, max_size: int, auto_wrap: bool) -> Any:
    config = {
        "name": "smartpool_cprofile",
        "backend": CacheBackend.SMARTPOOL.value,
        "factory_function": _factory,
        "factory_kwargs": {},
        "initial_size": initial_size,
        "min_size": min(2, initial_size),
        "max_size": max_size,
        "memory_preset": "HIGH_THROUGHPUT",
        "enable_auto_tuning": False,
        "enable_performance_metrics": False,
        "enable_stats": False,
        "auto_wrap_objects": auto_wrap,
        "log_level": "CRITICAL",
    }
    adapter = create_adapter(CacheBackend.SMARTPOOL, config)
    if not adapter.connect() or not adapter.is_connected():
        raise RuntimeError("Failed to connect SmartPool adapter")
    return adapter


def _run_borrow(adapter: Any, total: int, keyspace: int) -> None:
    for i in range(total):
        key = f"key{i % keyspace}"
        with adapter.borrow(key) as obj:
            obj.data = str(i)


def _run_borrow_fast(adapter: Any, total: int, keyspace: int) -> None:
    borrow_fast = getattr(adapter, "borrow_fast", None)
    if not callable(borrow_fast):
        raise RuntimeError("Adapter does not expose borrow_fast()")
    for i in range(total):
        key = f"key{i % keyspace}"
        with borrow_fast(key) as obj:
            obj.data = str(i)


def _run_getput(adapter: Any, total: int, keyspace: int) -> None:
    for i in range(total):
        key = f"key{i % keyspace}"
        obj = adapter.get(key)
        if obj is None:
            continue
        obj.data = str(i)
        adapter.put(obj)


def main() -> None:
    args = parse_args()

    if not args.no_disable_logs:
        # Silence all logging noise for cleaner cProfile traces.
        logging.disable(logging.CRITICAL)

    adapter = _build_adapter(
        initial_size=args.initial_size,
        max_size=args.max_size,
        auto_wrap=args.auto_wrap,
    )
    try:
        if args.warmup_iterations > 0:
            if args.mode == "borrow":
                _run_borrow(adapter, args.warmup_iterations, args.keyspace)
            elif args.mode == "borrow_fast":
                _run_borrow_fast(adapter, args.warmup_iterations, args.keyspace)
            else:
                _run_getput(adapter, args.warmup_iterations, args.keyspace)

        started = time.perf_counter()
        if args.mode == "borrow":
            _run_borrow(adapter, args.iterations, args.keyspace)
        elif args.mode == "borrow_fast":
            _run_borrow_fast(adapter, args.iterations, args.keyspace)
        else:
            _run_getput(adapter, args.iterations, args.keyspace)
        elapsed = time.perf_counter() - started

        # Minimal output (single line) to keep profiling runs clean.
        print(
            f"mode={args.mode} iterations={args.iterations} "
            f"elapsed_s={elapsed:.4f} ops_per_sec={args.iterations / max(elapsed, 1e-9):.1f}"
        )
    finally:
        if args.disconnect:
            adapter.disconnect()


if __name__ == "__main__":
    main()
