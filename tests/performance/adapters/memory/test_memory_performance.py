"""
Performance tests for Memory Adapter.

This module contains performance-focused tests for the MemoryAdapter,
including benchmarks, load tests, and performance regression tests.
"""

import gc
import os
import random
import statistics
import threading
import time

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig

# pylint: disable=import-outside-toplevel,too-many-locals

# Skip all performance tests if not explicitly requested
pytestmark = pytest.mark.slow


class PerformanceProfiler:
    """Utility class for performance profiling."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.memory_before = None
        self.memory_after = None

    def start(self):
        """Start profiling."""
        gc.collect()  # Clean up before measurement
        self.start_time = time.perf_counter()
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            self.memory_before = process.memory_info().rss
        except ImportError:
            self.memory_before = None

    def stop(self):
        """Stop profiling."""
        self.end_time = time.perf_counter()
        try:
            import os

            import psutil

            process = psutil.Process(os.getpid())
            self.memory_after = process.memory_info().rss
        except ImportError:
            self.memory_after = None

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    @property
    def memory_increase(self) -> int:
        """Get memory increase in bytes."""
        if self.memory_before is None or self.memory_after is None:
            return 0
        return self.memory_after - self.memory_before

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class TestMemoryAdapterBasicPerformance:
    """Basic performance tests for memory adapter operations."""

    @pytest.fixture
    def perf_adapter(self):
        """Create a performance-optimized memory adapter."""
        config = MemoryAdapterConfig(
            name="performance_test",
            max_size=100000,
            cleanup_interval=10.0,  # Less frequent cleanup for performance
            enable_stats=True,
        )
        adapter = MemoryAdapter(config)
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_single_set_performance(self, perf_adapter):
        """Test performance of individual set operations."""
        adapter = perf_adapter
        iterations = 10000

        # Warm up
        for i in range(100):
            adapter.set(f"warmup_{i}", f"value_{i}")

        # Measure set performance
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            adapter.set(f"perf_key_{i}", f"performance_value_{i}")
            end = time.perf_counter()
            times.append(end - start)

        # Analyze performance
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        p95_time = sorted(times)[int(0.95 * len(times))]

        # Performance assertions (in microseconds)
        assert avg_time < 0.0001, f"Average set time too high: {avg_time * 1000000:.2f}μs"
        assert p95_time < 0.0005, f"P95 set time too high: {p95_time * 1000000:.2f}μs"

        print(
            f"Set Operations - Avg: {avg_time * 1000000:.2f}μs, "
            f"Median: {median_time * 1000000:.2f}μs, "
            f"P95: {p95_time * 1000000:.2f}μs"
        )

    def test_single_get_performance(self, perf_adapter):
        """Test performance of individual get operations."""
        adapter = perf_adapter
        iterations = 10000

        # Pre-populate cache
        for i in range(iterations):
            adapter.set(f"perf_key_{i}", f"performance_value_{i}")

        # Warm up
        for i in range(100):
            adapter.get(f"perf_key_{i}")

        # Measure get performance
        times = []
        for i in range(iterations):
            start = time.perf_counter()
            result = adapter.get(f"perf_key_{i}")
            end = time.perf_counter()
            times.append(end - start)
            assert result is not None

        # Analyze performance
        avg_time = statistics.mean(times)
        median_time = statistics.median(times)
        p95_time = sorted(times)[int(0.95 * len(times))]

        # Performance assertions
        assert avg_time < 0.00005, f"Average get time too high: {avg_time * 1000000:.2f}μs"
        assert p95_time < 0.0002, f"P95 get time too high: {p95_time * 1000000:.2f}μs"

        print(
            f"Get Operations - Avg: {avg_time * 1000000:.2f}μs, "
            f"Median: {median_time * 1000000:.2f}μs, "
            f"P95: {p95_time * 1000000:.2f}μs"
        )

    def test_bulk_operations_performance(self, perf_adapter):
        """Test performance of bulk operations."""
        adapter = perf_adapter
        batch_sizes = [10, 50, 100, 500, 1000]
        iterations_per_batch = 3
        min_set_rate = 150 if os.getenv("CI", "").lower() == "true" else 300

        for batch_size in batch_sizes:
            # Prepare bulk data
            bulk_data = {f"bulk_key_{i}": f"bulk_value_{i}" for i in range(batch_size)}

            keys = list(bulk_data.keys())
            set_rates = []
            get_rates = []

            for run_idx in range(iterations_per_batch):
                # Measure bulk set performance
                with PerformanceProfiler(f"bulk_set_{batch_size}_{run_idx}") as prof:
                    result = adapter.set_many(bulk_data)
                assert all(result.values())
                set_rates.append(batch_size / prof.elapsed)

                # Measure bulk get performance
                with PerformanceProfiler(f"bulk_get_{batch_size}_{run_idx}") as prof:
                    results = adapter.get_many(keys)
                assert len(results) == batch_size
                get_rates.append(batch_size / prof.elapsed)

            set_rate = statistics.median(set_rates)
            get_rate = statistics.median(get_rates)

            print(
                f"Batch size {batch_size}: "
                f"Set rate: {set_rate:.0f} ops/sec, "
                f"Get rate: {get_rate:.0f} ops/sec"
            )

            # Performance assertions
            assert set_rate > min_set_rate, (
                f"Bulk set rate too low for batch {batch_size}: {set_rate:.0f}"
            )
            assert get_rate > 5000, f"Bulk get rate too low for batch {batch_size}: {get_rate:.0f}"

    def test_memory_usage_growth(self, perf_adapter):
        """Test memory usage growth patterns."""
        adapter = perf_adapter

        memory_points = []
        item_counts = [1000, 2000, 5000, 10000, 20000]

        for target_count in item_counts:
            current_count = adapter.size()
            items_to_add = target_count - current_count

            with PerformanceProfiler(f"add_{items_to_add}_items") as prof:
                for i in range(items_to_add):
                    key = f"memory_test_{current_count + i}"
                    value = {
                        "id": current_count + i,
                        "data": "x" * 100,  # 100 bytes payload
                        "metadata": {"created": time.time()},
                    }
                    adapter.set(key, value)

            memory_points.append(
                {
                    "item_count": target_count,
                    "memory_increase": prof.memory_increase,
                    "time_taken": prof.elapsed,
                }
            )

        # Analyze memory growth
        for point in memory_points:
            items = point["item_count"]
            memory_mb = point["memory_increase"] / (1024 * 1024)
            time_sec = point["time_taken"]

            print(f"Items: {items:,}, Memory increase: {memory_mb:.2f}MB, Time: {time_sec:.3f}s")

        # Memory usage should grow roughly linearly
        if len(memory_points) >= 2:
            first_point = memory_points[0]
            last_point = memory_points[-1]

            memory_per_item = (last_point["memory_increase"] - first_point["memory_increase"]) / (
                last_point["item_count"] - first_point["item_count"]
            )

            # Each item should use reasonable memory (adjust based on payload)
            assert memory_per_item < 1000, f"Memory per item too high: {memory_per_item} bytes"


class TestMemoryAdapterEvictionPerformance:
    """Performance tests for eviction policies."""

    @pytest.mark.parametrize("policy", ["lru", "fifo", "random"])
    def test_eviction_policy_performance(self, policy):
        """Test performance of different eviction policies."""
        config = MemoryAdapterConfig(
            name=f"eviction_perf_{policy}", max_size=1000, eviction_policy=policy, enable_stats=True
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            operations = 5000  # More operations than cache size

            with PerformanceProfiler(f"eviction_{policy}") as prof:
                for i in range(operations):
                    key = f"eviction_key_{i}"
                    value = f"eviction_value_{i}"
                    success = adapter.set(key, value)
                    assert success

            # Verify cache size is within limits
            assert adapter.size() <= config.max_size

            # Get performance metrics
            ops_per_sec = operations / prof.elapsed
            stats = adapter.get_stats()

            print(
                f"Eviction policy {policy}: {ops_per_sec:.0f} ops/sec, {stats.evictions} evictions"
            )

            # Performance assertions
            assert ops_per_sec > 1000, (
                f"Eviction performance too low for {policy}: {ops_per_sec:.0f}"
            )
            assert stats.evictions > 0, f"No evictions occurred for {policy}"

        finally:
            adapter.disconnect()

    def test_eviction_overhead_comparison_robust(self):
        """Compare overhead of different eviction policies with multiple runs."""
        policies = ["lru", "fifo", "random"]
        num_runs = 3  # Run multiple times to get more stable results

        all_results = {}

        for run in range(num_runs):
            run_results = {}

            for policy in policies:
                config = MemoryAdapterConfig(
                    name=f"overhead_{policy}_{run}", max_size=500, eviction_policy=policy
                )
                adapter = MemoryAdapter(config)
                adapter.connect()

                try:
                    operations = 2000

                    with PerformanceProfiler(f"overhead_{policy}_{run}") as prof:
                        for i in range(operations):
                            adapter.set(f"overhead_key_{i}", f"value_{i}")

                    run_results[policy] = prof.elapsed

                finally:
                    adapter.disconnect()

            all_results[run] = run_results

        # Calculate average times across runs
        avg_results = {}
        for policy in policies:
            times = [all_results[run][policy] for run in range(num_runs)]
            avg_results[policy] = sum(times) / len(times)

        # Compare results using averages
        fastest_policy = min(avg_results.keys(), key=lambda p: avg_results[p])
        slowest_policy = max(avg_results.keys(), key=lambda p: avg_results[p])

        fastest_time = avg_results[fastest_policy]
        slowest_time = avg_results[slowest_policy]
        overhead_ratio = slowest_time / fastest_time

        print(f"Average Eviction Policy Performance (over {num_runs} runs):")
        for policy, avg_time in avg_results.items():
            print(f"  {policy.upper()}: {avg_time:.3f}s average")

        print(f"Overhead ratio: {overhead_ratio:.2f}x")

        # Use a more reasonable threshold
        assert overhead_ratio < 30.0, f"Average eviction overhead too high: {overhead_ratio:.2f}x"


class TestMemoryAdapterConcurrentPerformance:
    """Performance tests for concurrent operations."""

    def test_read_scaling_performance(self):
        """Test how read performance scales with concurrent readers."""
        config = MemoryAdapterConfig(name="read_scaling", max_size=10000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Pre-populate cache
            num_items = 1000
            for i in range(num_items):
                adapter.set(f"scaling_key_{i}", f"scaling_value_{i}")

            thread_counts = [1, 2, 4, 8, 16]
            operations_per_thread = 1000

            for num_threads in thread_counts:

                def worker():
                    """Worker function for concurrent reads."""
                    for _ in range(operations_per_thread):
                        key = f"scaling_key_{random.randint(0, num_items - 1)}"
                        result = adapter.get(key)
                        assert result is not None

                with PerformanceProfiler(f"read_scaling_{num_threads}") as prof:
                    threads = []
                    for _ in range(num_threads):
                        thread = threading.Thread(target=worker)
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()

                total_operations = num_threads * operations_per_thread
                throughput = total_operations / prof.elapsed

                print(
                    f"Threads: {num_threads:2d}, "
                    f"Throughput: {throughput:6.0f} ops/sec, "
                    f"Per-thread: {throughput / num_threads:6.0f} ops/sec"
                )

                # Throughput should generally increase with more threads (up to a point)
                assert throughput > 1000, f"Throughput too low with {num_threads} threads"

        finally:
            adapter.disconnect()

    def test_write_contention_performance(self):
        """Test write performance under contention."""
        config = MemoryAdapterConfig(name="write_contention", max_size=10000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            thread_counts = [1, 2, 4, 8]
            operations_per_thread = 500

            for num_threads in thread_counts:

                def worker(worker_id: int):
                    """Worker function for concurrent writes."""
                    for i in range(operations_per_thread):
                        key = f"contention_key_{worker_id}_{i}"
                        value = f"contention_value_{worker_id}_{i}"
                        success = adapter.set(key, value)
                        assert success

                with PerformanceProfiler(f"write_contention_{num_threads}") as prof:
                    threads = []
                    for i in range(num_threads):
                        thread = threading.Thread(target=worker, args=(i,))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()

                total_operations = num_threads * operations_per_thread
                throughput = total_operations / prof.elapsed

                print(f"Write Threads: {num_threads:2d}, Throughput: {throughput:6.0f} ops/sec")

                assert throughput > 500, f"Write throughput too low with {num_threads} threads"

        finally:
            adapter.disconnect()

    def test_mixed_workload_performance(self):
        """Test performance with mixed read/write workloads."""
        config = MemoryAdapterConfig(name="mixed_workload", max_size=5000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Pre-populate with some data
            for i in range(1000):
                adapter.set(f"mixed_key_{i}", f"mixed_value_{i}")

            def read_worker():
                """Worker that performs mostly reads."""
                for _ in range(800):
                    key = f"mixed_key_{random.randint(0, 999)}"
                    adapter.get(key)

            def write_worker():
                """Worker that performs writes."""
                for i in range(200):
                    key = f"write_key_{threading.current_thread().ident}_{i}"
                    value = f"write_value_{i}"
                    adapter.set(key, value)

            def mixed_worker():
                """Worker that performs mixed operations."""
                for i in range(500):
                    if random.random() < 0.7:  # 70% reads
                        key = f"mixed_key_{random.randint(0, 999)}"
                        adapter.get(key)
                    else:  # 30% writes
                        key = f"mixed_new_key_{threading.current_thread().ident}_{i}"
                        value = f"mixed_new_value_{i}"
                        adapter.set(key, value)

            with PerformanceProfiler("mixed_workload") as prof:
                threads = []

                # 4 read workers
                for _ in range(4):
                    threads.append(threading.Thread(target=read_worker))

                # 2 write workers
                for _ in range(2):
                    threads.append(threading.Thread(target=write_worker))

                # 2 mixed workers
                for _ in range(2):
                    threads.append(threading.Thread(target=mixed_worker))

                for thread in threads:
                    thread.start()

                for thread in threads:
                    thread.join()

            # Calculate approximate total operations
            total_ops = (4 * 800) + (2 * 200) + (2 * 500)  # 6000 operations
            throughput = total_ops / prof.elapsed

            print(f"Mixed Workload Throughput: {throughput:.0f} ops/sec")

            stats = adapter.get_stats()
            print(f"Hit Rate: {stats.hit_rate:.2%}, Sets: {stats.sets}, Hits: {stats.hits}")

            assert throughput > 2000, f"Mixed workload throughput too low: {throughput:.0f}"

        finally:
            adapter.disconnect()


class TestMemoryAdapterTTLPerformance:
    """Performance tests for TTL functionality."""

    def test_ttl_overhead_measurement(self):
        """Measure overhead of TTL functionality."""
        configs = [
            ("no_ttl", MemoryAdapterConfig(name="no_ttl", cleanup_interval=999)),
            (
                "with_ttl",
                MemoryAdapterConfig(name="with_ttl", default_ttl=300, cleanup_interval=999),
            ),
        ]

        results = {}
        operations = 5000

        for name, config in configs:
            adapter = MemoryAdapter(config)
            adapter.connect()

            try:
                with PerformanceProfiler(name) as prof:
                    for i in range(operations):
                        key = f"ttl_test_{i}"
                        value = f"ttl_value_{i}"
                        if name == "no_ttl":
                            adapter.set(key, value)
                        else:
                            adapter.set(key, value, ttl=300)

                results[name] = {"time": prof.elapsed, "ops_per_sec": operations / prof.elapsed}

            finally:
                adapter.disconnect()

        # Compare results
        no_ttl_rate = results["no_ttl"]["ops_per_sec"]
        ttl_rate = results["with_ttl"]["ops_per_sec"]
        overhead = (results["with_ttl"]["time"] - results["no_ttl"]["time"]) / results["no_ttl"][
            "time"
        ]

        print(f"No TTL: {no_ttl_rate:.0f} ops/sec")
        print(f"With TTL: {ttl_rate:.0f} ops/sec")
        print(f"TTL overhead: {overhead:.1%}")

        # TTL overhead should be minimal
        assert overhead < 0.5, f"TTL overhead too high: {overhead:.1%}"
        assert ttl_rate > no_ttl_rate * 0.7, "TTL performance degradation too high"

    def test_cleanup_performance_impact(self):
        """Test performance impact of cleanup operations."""
        config = MemoryAdapterConfig(
            name="cleanup_test",
            cleanup_interval=0.1,
            default_ttl=0.5,  # Frequent cleanup
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            operations = 2000
            operation_times = []

            for i in range(operations):
                start = time.perf_counter()

                # Mix of operations that might trigger cleanup
                if i % 3 == 0:
                    adapter.set(f"cleanup_key_{i}", f"cleanup_value_{i}")
                elif i % 3 == 1:
                    adapter.get(f"cleanup_key_{random.randint(max(0, i - 100), i)}")
                else:
                    adapter.exists(f"cleanup_key_{random.randint(max(0, i - 100), i)}")

                end = time.perf_counter()
                operation_times.append(end - start)

                # Small delay to allow cleanup to occur
                if i % 100 == 0:
                    time.sleep(0.01)

            # Analyze performance distribution
            avg_time = statistics.mean(operation_times)
            p95_time = sorted(operation_times)[int(0.95 * len(operation_times))]
            p99_time = sorted(operation_times)[int(0.99 * len(operation_times))]

            print(
                f"Cleanup Impact - Avg: {avg_time * 1000:.2f}ms, "
                f"P95: {p95_time * 1000:.2f}ms, "
                f"P99: {p99_time * 1000:.2f}ms"
            )

            # Even with frequent cleanup, operations should be fast
            assert avg_time < 0.001, (
                f"Average operation time too high with cleanup: {avg_time * 1000:.2f}ms"
            )
            assert p99_time < 0.01, (
                f"P99 operation time too high with cleanup: {p99_time * 1000:.2f}ms"
            )

        finally:
            adapter.disconnect()


class TestMemoryAdapterMemoryBenchmarks:
    """Memory usage and efficiency benchmarks."""

    def test_memory_efficiency_by_item_size(self):
        """Test memory efficiency for different item sizes."""
        item_sizes = [10, 100, 1000, 10000]  # bytes
        results = {}

        for size in item_sizes:
            config = MemoryAdapterConfig(
                name=f"memory_test_{size}",
                cleanup_interval=999,  # Disable cleanup for measurement
            )
            adapter = MemoryAdapter(config)
            adapter.connect()

            try:
                num_items = min(1000, 100000 // size)  # Adjust count based on size
                payload = "x" * size

                with PerformanceProfiler(f"memory_test_{size}") as prof:
                    for i in range(num_items):
                        key = f"mem_key_{i}"
                        value = {"data": payload, "id": i}
                        adapter.set(key, value)

                memory_per_item = prof.memory_increase / num_items if num_items > 0 else 0
                overhead_ratio = memory_per_item / size if size > 0 else 0

                results[size] = {
                    "memory_per_item": memory_per_item,
                    "overhead_ratio": overhead_ratio,
                    "total_items": num_items,
                }

                print(
                    f"Item size: {size:5d} bytes, "
                    f"Memory/item: {memory_per_item:6.1f} bytes, "
                    f"Overhead: {overhead_ratio:.2f}x"
                )

            finally:
                adapter.disconnect()

        # Memory overhead should be reasonable
        for size, result in results.items():
            if size >= 100:  # For larger items, overhead should be lower
                assert result["overhead_ratio"] < 3.0, f"Memory overhead too high for {size}B items"

    def test_cache_size_vs_memory_usage(self):
        """Test relationship between cache size and memory usage."""
        cache_sizes = [100, 500, 1000, 5000]

        for max_size in cache_sizes:
            config = MemoryAdapterConfig(
                name=f"size_test_{max_size}", max_size=max_size, eviction_policy="lru"
            )
            adapter = MemoryAdapter(config)
            adapter.connect()

            try:
                # Fill cache to capacity
                payload_size = 200  # bytes
                payload = "x" * payload_size

                with PerformanceProfiler(f"fill_cache_{max_size}") as prof:
                    # Add more items than capacity to trigger evictions
                    for i in range(max_size * 2):
                        key = f"size_key_{i}"
                        value = {"data": payload, "id": i}
                        adapter.set(key, value)

                actual_size = adapter.size()
                memory_usage = prof.memory_increase
                memory_per_item = memory_usage / actual_size if actual_size > 0 else 0

                print(
                    f"Max size: {max_size:4d}, "
                    f"Actual: {actual_size:4d}, "
                    f"Memory: {memory_usage / 1024:.1f}KB, "
                    f"Per item: {memory_per_item:.0f} bytes"
                )

                # Verify cache size is within limits
                assert actual_size <= max_size

                # Memory usage should scale roughly with cache size
                expected_memory = actual_size * (payload_size + 100)  # Rough estimate with overhead
                assert memory_usage < expected_memory * 3, "Memory usage too high"

            finally:
                adapter.disconnect()


class TestMemoryAdapterPerformanceBenchmarks:
    """Performance benchmark tests for memory adapter."""

    @pytest.mark.slow
    def test_sequential_operations_benchmark(self, performance_timer):
        """Benchmark sequential operations performance."""
        config = MemoryAdapterConfig(name="sequential_benchmark", max_size=10000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            num_operations = 1000

            # Benchmark sequential writes
            with performance_timer() as timer:
                for i in range(num_operations):
                    key = f"seq_key_{i}"
                    value = {"id": i, "data": f"value_{i}"}
                    adapter.set(key, value)

            write_time = timer.elapsed
            write_rate = num_operations / write_time

            # Benchmark sequential reads
            with performance_timer() as timer:
                for i in range(num_operations):
                    key = f"seq_key_{i}"
                    result = adapter.get(key)
                    assert result is not None

            read_time = timer.elapsed
            read_rate = num_operations / read_time

            # Performance assertions (adjust based on expectations)
            assert write_rate > 1000, f"Write rate too low: {write_rate:.0f} ops/sec"
            assert read_rate > 5000, f"Read rate too low: {read_rate:.0f} ops/sec"

            print(f"Sequential Write Rate: {write_rate:.0f} ops/sec")
            print(f"Sequential Read Rate: {read_rate:.0f} ops/sec")

        finally:
            adapter.disconnect()

    @pytest.mark.slow
    def test_random_operations_benchmark(self, performance_timer):
        """Benchmark random access operations performance."""
        config = MemoryAdapterConfig(name="random_benchmark", max_size=5000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Pre-populate cache
            num_items = 1000
            for i in range(num_items):
                key = f"random_key_{i}"
                value = {"id": i, "data": f"value_{i}" * 10}
                adapter.set(key, value)

            num_operations = 2000

            # Benchmark random access
            with performance_timer() as timer:
                for _ in range(num_operations):
                    operation = random.choice(["get", "set", "exists"])
                    key_id = random.randint(0, num_items - 1)
                    key = f"random_key_{key_id}"

                    if operation == "get":
                        adapter.get(key)
                    elif operation == "set":
                        value = {"updated": time.time(), "data": "new_data"}
                        adapter.set(key, value)
                    elif operation == "exists":
                        adapter.exists(key)

            random_time = timer.elapsed
            random_rate = num_operations / random_time

            assert random_rate > 2000, f"Random access rate too low: {random_rate:.0f} ops/sec"

            print(f"Random Operations Rate: {random_rate:.0f} ops/sec")

            # Verify cache statistics
            stats = adapter.get_stats()
            assert stats.hit_rate > 0.5, f"Hit rate too low: {stats.hit_rate:.2%}"

        finally:
            adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "slow"])
