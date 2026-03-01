# =============================================================================
# EXAMPLE: Enhanced Performance Comparison and Stress Testing
# File: examples/benchmarks/performance_stress_comparison.py
# =============================================================================

"""
Enhanced performance comparison and stress testing example.

This example demonstrates:
- Memory vs Redis vs Memcached backend performance comparison
- Stress testing with large datasets
- Memory usage monitoring and optimization
- Concurrent access performance
- Cache hit ratio optimization under load
- Memory pressure simulation
- Large object caching performance
"""

import asyncio
import gc
import hashlib
import os
import random
import statistics
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import psutil

from omni_cache import (
    CacheBackend,
    cached,
    clear_cache,
    create_adapter,
    get_cache_stats,
    memoize,
    setup,
)

# =============================================================================
# Enhanced Configuration and Setup
# =============================================================================


@dataclass
class StressTestConfig:
    """Configuration for stress testing."""

    # Basic benchmark settings
    warmup_iterations: int = 50
    benchmark_iterations: int = 500
    concurrent_threads: int = 8

    # Memory stress settings
    large_object_sizes: list[int] = None
    memory_pressure_sizes: list[int] = None
    cache_sizes: list[int] = None

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 3  # Use separate DB for testing
    memcached_host: str = "localhost"
    memcached_port: int = 11211

    def __post_init__(self):
        if self.large_object_sizes is None:
            self.large_object_sizes = [1_000, 10_000, 100_000, 1_000_000]
        if self.memory_pressure_sizes is None:
            self.memory_pressure_sizes = [50_000, 100_000, 500_000, 1_000_000]
        if self.cache_sizes is None:
            self.cache_sizes = [100, 1_000, 5_000, 10_000]


config = StressTestConfig()

print("🚀 Enhanced Omni-Cache Performance Testing Suite")
print("=" * 60)

# =============================================================================
# Enhanced Adapter Setup
# =============================================================================


def setup_adapters():
    """Setup Memory, Redis, and Memcached adapters with comprehensive configuration."""
    print("🔧 Setting up adapters...")

    # Create manager
    manager = setup(log_level="WARNING")

    # Setup Memory adapter with different configurations
    memory_adapter = create_adapter(
        CacheBackend.MEMORY,
        {"max_size": 10_000, "eviction_policy": "lru", "default_ttl": 3600, "enable_stats": True},
    )
    manager.register_adapter("memory", memory_adapter)

    # Setup Large Memory adapter for stress tests
    large_memory_adapter = create_adapter(
        CacheBackend.MEMORY,
        {"max_size": 50_000, "eviction_policy": "lru", "default_ttl": 1800, "enable_stats": True},
    )
    manager.register_adapter("large_memory", large_memory_adapter)

    # Try to setup Redis adapter
    redis_available = False
    try:
        redis_adapter = create_adapter(
            CacheBackend.REDIS,
            {
                "host": config.redis_host,
                "port": config.redis_port,
                "db": config.redis_db,
                "socket_timeout": 5.0,
                "connection_pool_max_connections": 20,
                "enable_stats": True,
            },
        )
        manager.register_adapter("redis", redis_adapter)

        # Test connection
        if redis_adapter.is_connected():
            print("✅ Redis adapter configured and connected")
            redis_available = True
        else:
            print("❌ Redis adapter failed to connect")

    except Exception as e:
        print(f"⚠️  Redis not available: {e}")
        print("   Continuing with remaining adapters")

    # Try to setup Memcached adapter
    memcached_available = False
    try:
        memcached_adapter = create_adapter(
            CacheBackend.MEMCACHED,
            {
                "host": config.memcached_host,
                "port": config.memcached_port,
                "timeout": 3.0,
                "connect_timeout": 2.0,
                "enable_stats": True,
            },
        )
        manager.register_adapter("memcached", memcached_adapter)

        # Test connection
        if memcached_adapter.is_connected():
            print("✅ Memcached adapter configured and connected")
            memcached_available = True
        else:
            print("❌ Memcached adapter failed to connect")
    except Exception as e:
        print(f"⚠️  Memcached not available: {e}")
        print("   Continuing with remaining adapters")

    # Set default adapter
    manager._config.default_adapter = "memory"

    # Configure routing rules
    manager.add_routing_rule("memory", "memory")
    manager.add_routing_rule("large", "large_memory")
    manager.add_routing_rule("redis", "redis")
    manager.add_routing_rule("memcached", "memcached")

    print("✅ Adapters configured successfully")
    return manager, redis_available, memcached_available


# Setup global manager and check backend availability
global_manager, redis_enabled, memcached_enabled = setup_adapters()

# =============================================================================
# Enhanced Test Functions
# =============================================================================


def generate_test_data(size: int, complexity: str = "simple") -> Any:
    """Generate test data of various types and sizes."""
    if complexity == "simple":
        return list(range(size))
    elif complexity == "nested":
        return {
            "id": size,
            "data": [{"item": i, "value": random.random()} for i in range(size)],
            "metadata": {"size": size, "timestamp": time.time()},
        }
    elif complexity == "binary":
        return os.urandom(size)
    elif complexity == "text":
        return "x" * size
    else:
        return list(range(size))


def expensive_cpu_operation(n: int, complexity: int = 100) -> int:
    """CPU-intensive operation with configurable complexity."""
    result = 0
    for _i in range(complexity):
        result += sum(range(n))
    return result


def expensive_memory_operation(size: int, data_type: str = "simple") -> Any:
    """Memory-intensive operation creating large objects."""
    return generate_test_data(size, data_type)


def expensive_io_simulation(delay: float = 0.01) -> dict[str, Any]:
    """Simulate I/O operation with realistic data."""
    time.sleep(delay)
    return {
        "timestamp": time.time(),
        "data": [random.randint(1, 1000) for _ in range(100)],
        "hash": hashlib.sha256(str(time.time()).encode()).hexdigest(),
        "status": "completed",
    }


# =============================================================================
# Cached Function Variants
# =============================================================================


# Memory-based cached functions
@cached(ttl=300, adapter="memory")
def cached_cpu_memory(n: int, complexity: int = 100) -> int:
    return expensive_cpu_operation(n, complexity)


@cached(ttl=600, adapter="large_memory")
def cached_memory_large(size: int, data_type: str = "simple") -> Any:
    return expensive_memory_operation(size, data_type)


@cached(ttl=180, adapter="memory")
def cached_io_memory(delay: float = 0.01) -> dict[str, Any]:
    return expensive_io_simulation(delay)


# Redis-based cached functions (if available)
if redis_enabled:

    @cached(ttl=300, adapter="redis")
    def cached_cpu_redis(n: int, complexity: int = 100) -> int:
        return expensive_cpu_operation(n, complexity)

    @cached(ttl=600, adapter="redis")
    def cached_memory_redis(size: int, data_type: str = "simple") -> Any:
        return expensive_memory_operation(size, data_type)

    @cached(ttl=180, adapter="redis")
    def cached_io_redis(delay: float = 0.01) -> dict[str, Any]:
        return expensive_io_simulation(delay)


# Memcached-based cached functions (if available)
if memcached_enabled:

    @cached(ttl=300, adapter="memcached")
    def cached_cpu_memcached(n: int, complexity: int = 100) -> int:
        return expensive_cpu_operation(n, complexity)

    @cached(ttl=600, adapter="memcached")
    def cached_memory_memcached(size: int, data_type: str = "simple") -> Any:
        return expensive_memory_operation(size, data_type)

    @cached(ttl=180, adapter="memcached")
    def cached_io_memcached(delay: float = 0.01) -> dict[str, Any]:
        return expensive_io_simulation(delay)


# Memoized functions with different cache sizes
@memoize(maxsize=1000)
def memoized_cpu_small(n: int, complexity: int = 50) -> int:
    return expensive_cpu_operation(n, complexity)


@memoize(maxsize=10000)
def memoized_cpu_large(n: int, complexity: int = 50) -> int:
    return expensive_cpu_operation(n, complexity)


# =============================================================================
# Enhanced Benchmark Framework
# =============================================================================


class MemoryMonitor:
    """Monitor memory usage during tests."""

    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.peak_memory = None

    def start(self):
        """Start monitoring memory."""
        gc.collect()  # Force garbage collection
        self.start_memory = self.process.memory_info().rss
        self.peak_memory = self.start_memory

    def update(self):
        """Update peak memory usage."""
        current = self.process.memory_info().rss
        if current > self.peak_memory:
            self.peak_memory = current

    def get_stats(self) -> dict[str, float]:
        """Get memory statistics in MB."""
        current = self.process.memory_info().rss
        return {
            "start_mb": self.start_memory / 1024 / 1024 if self.start_memory else 0,
            "current_mb": current / 1024 / 1024,
            "peak_mb": self.peak_memory / 1024 / 1024 if self.peak_memory else 0,
            "delta_mb": (current - self.start_memory) / 1024 / 1024 if self.start_memory else 0,
        }


class EnhancedBenchmarkResult:
    """Enhanced benchmark result with memory and cache metrics."""

    def __init__(self, name: str):
        self.name = name
        self.times: list[float] = []
        self.memory_stats: list[dict[str, float]] = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.errors = 0
        self.thread_count = 1

    def add_measurement(self, execution_time: float, memory_stats: dict[str, float] = None):
        """Add a performance measurement."""
        self.times.append(execution_time)
        if memory_stats:
            self.memory_stats.append(memory_stats)

    def add_error(self):
        """Record an error."""
        self.errors += 1

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive statistics."""
        if not self.times:
            return {"name": self.name, "error": "No measurements"}

        # Time statistics
        mean_time = statistics.mean(self.times)
        median_time = statistics.median(self.times)
        std_dev = statistics.stdev(self.times) if len(self.times) > 1 else 0
        total_time = sum(self.times)
        throughput = len(self.times) / total_time if total_time > 0 else 0

        # Memory statistics
        memory_stats = {}
        if self.memory_stats:
            memory_stats = {
                "avg_memory_mb": statistics.mean([m["current_mb"] for m in self.memory_stats]),
                "peak_memory_mb": max([m["peak_mb"] for m in self.memory_stats]),
                "avg_delta_mb": statistics.mean([m["delta_mb"] for m in self.memory_stats]),
            }

        # Cache statistics
        total_ops = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_ops if total_ops > 0 else 0

        return {
            "name": self.name,
            "mean_time_ms": mean_time * 1000,
            "median_time_ms": median_time * 1000,
            "min_time_ms": min(self.times) * 1000,
            "max_time_ms": max(self.times) * 1000,
            "std_dev_ms": std_dev * 1000,
            "total_time_s": total_time,
            "iterations": len(self.times),
            "errors": self.errors,
            "throughput_ops_sec": throughput,
            "throughput_per_thread": throughput / self.thread_count,
            "cache_hit_rate": hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            **memory_stats,
        }


class StressBenchmarker:
    """Enhanced benchmarker with stress testing capabilities."""

    def __init__(self):
        self.results: dict[str, EnhancedBenchmarkResult] = {}
        self.memory_monitor = MemoryMonitor()

    @staticmethod
    def _extract_cache_counters(stats: Any) -> tuple[int, int]:
        """Extract (hits, misses) from cache stats payloads."""
        if not isinstance(stats, dict):
            return 0, 0

        cache_stats = stats.get("cache", stats)

        if isinstance(cache_stats, dict):
            hits = cache_stats.get("hits", 0)
            misses = cache_stats.get("misses", 0)
        else:
            hits = getattr(cache_stats, "hits", 0)
            misses = getattr(cache_stats, "misses", 0)

        return int(hits or 0), int(misses or 0)

    def _get_cache_counters(self) -> tuple[int, int]:
        """Read current global cache counters."""
        try:
            return self._extract_cache_counters(get_cache_stats())
        except Exception:
            return 0, 0

    def benchmark_function(
        self,
        name: str,
        func: Callable,
        iterations: int = 100,
        warmup: int = 10,
        monitor_memory: bool = True,
        threads: int = 1,
    ) -> EnhancedBenchmarkResult:
        """Enhanced benchmark with memory monitoring and threading."""

        print(f"🏃 Benchmarking {name} ({iterations} iterations, {threads} threads)...")

        result = EnhancedBenchmarkResult(name)
        result.thread_count = threads

        if monitor_memory:
            self.memory_monitor.start()

        # Warmup phase
        for _ in range(warmup):
            try:
                func()
            except Exception:
                pass

        start_hits, start_misses = self._get_cache_counters()

        if threads == 1:
            # Single-threaded execution
            for _i in range(iterations):
                try:
                    start_time = time.time()
                    func()
                    end_time = time.time()

                    memory_stats = None
                    if monitor_memory:
                        self.memory_monitor.update()
                        memory_stats = self.memory_monitor.get_stats()

                    result.add_measurement(end_time - start_time, memory_stats)

                except Exception as e:
                    print(f"❌ Error in {name}: {e}")
                    result.add_error()
        else:
            # Multi-threaded execution
            def worker():
                measurements = []
                for _ in range(iterations // threads):
                    try:
                        start_time = time.time()
                        func()
                        end_time = time.time()
                        measurements.append(end_time - start_time)
                    except Exception:
                        result.add_error()
                return measurements

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(worker) for _ in range(threads)]
                for future in as_completed(futures):
                    try:
                        measurements = future.result()
                        for measurement in measurements:
                            result.add_measurement(measurement)
                    except Exception:
                        result.add_error()

        end_hits, end_misses = self._get_cache_counters()
        result.cache_hits = max(0, end_hits - start_hits)
        result.cache_misses = max(0, end_misses - start_misses)

        self.results[name] = result

        # Print results
        stats = result.get_statistics()
        if "error" not in stats:
            print(
                f"✅ {name}: {stats['mean_time_ms']:.2f}ms avg, "
                f"{stats['throughput_ops_sec']:.1f} ops/sec"
            )
            if monitor_memory and "avg_memory_mb" in stats:
                print(
                    f"   Memory: {stats['avg_memory_mb']:.1f}MB avg, "
                    f"{stats['peak_memory_mb']:.1f}MB peak"
                )

        return result

    def compare_results(self, *names):
        """Compare benchmark results."""
        print("\n📊 Performance Comparison:")
        print("-" * 80)
        print(
            f"{'Test Name':<25} {'Time(ms)':<12} {'Throughput':<15} "
            f"{'Hit Rate':<12} {'Memory(MB)':<12}"
        )
        print("-" * 80)

        for name in names:
            if name in self.results:
                stats = self.results[name].get_statistics()
                if "error" not in stats:
                    memory_str = (
                        f"{stats.get('avg_memory_mb', 0):.1f}"
                        if "avg_memory_mb" in stats
                        else "N/A"
                    )
                    print(
                        f"{name:<25} {stats['mean_time_ms']:<12.2f} "
                        f"{stats['throughput_ops_sec']:<15.1f} "
                        f"{stats['cache_hit_rate'] * 100:<12.1f}% {memory_str:<12}"
                    )


# =============================================================================
# Stress Test Scenarios
# =============================================================================


def benchmark_backends_comparison():
    """Compare Memory vs Redis vs Memcached performance."""
    print("\n🏁 Backend Performance Comparison")
    print("=" * 50)

    benchmarker = StressBenchmarker()

    # Test parameters for comparison
    test_params = [(10, 50), (20, 100), (30, 150)]

    # Memory backend tests
    benchmarker.benchmark_function(
        "memory_cpu", lambda: [cached_cpu_memory(n, c) for n, c in test_params], iterations=200
    )

    benchmarker.benchmark_function("memory_io", lambda: cached_io_memory(0.005), iterations=100)

    # Redis backend tests (if available)
    if redis_enabled:
        benchmarker.benchmark_function(
            "redis_cpu", lambda: [cached_cpu_redis(n, c) for n, c in test_params], iterations=200
        )

        benchmarker.benchmark_function("redis_io", lambda: cached_io_redis(0.005), iterations=100)

    # Memcached backend tests (if available)
    if memcached_enabled:
        benchmarker.benchmark_function(
            "memcached_cpu",
            lambda: [cached_cpu_memcached(n, c) for n, c in test_params],
            iterations=200,
        )
        benchmarker.benchmark_function(
            "memcached_io", lambda: cached_io_memcached(0.005), iterations=100
        )

    compare_targets = ["memory_cpu", "memory_io"]
    if redis_enabled:
        compare_targets.extend(["redis_cpu", "redis_io"])
    if memcached_enabled:
        compare_targets.extend(["memcached_cpu", "memcached_io"])
    benchmarker.compare_results(*compare_targets)

    return benchmarker


def benchmark_memory_stress():
    """Stress test with large objects and memory pressure."""
    print("\n💾 Memory Stress Testing")
    print("=" * 35)

    benchmarker = StressBenchmarker()

    # Test with different object sizes
    for size in config.large_object_sizes:
        benchmarker.benchmark_function(
            f"large_objects_{size}",
            lambda s=size: cached_memory_large(s, "nested"),
            iterations=50,
            monitor_memory=True,
        )

    # Memory pressure test
    print("\n🔥 Memory Pressure Test")
    benchmarker.benchmark_function(
        "memory_pressure",
        lambda: [
            cached_memory_large(random.choice(config.memory_pressure_sizes), "binary")
            for _ in range(10)
        ],
        iterations=20,
        monitor_memory=True,
    )

    # Compare object sizes
    size_tests = [f"large_objects_{size}" for size in config.large_object_sizes]
    benchmarker.compare_results(*size_tests, "memory_pressure")

    return benchmarker


def benchmark_concurrent_stress():
    """Stress test with high concurrency."""
    print("\n🔀 Concurrent Stress Testing")
    print("=" * 40)

    benchmarker = StressBenchmarker()

    # Single-threaded baseline
    benchmarker.benchmark_function(
        "single_thread",
        lambda: [cached_cpu_memory(i % 20, 75) for i in range(50)],
        iterations=20,
        threads=1,
    )

    # Multi-threaded tests
    for thread_count in [2, 4, 8, 16]:
        benchmarker.benchmark_function(
            f"threads_{thread_count}",
            lambda: [cached_cpu_memory(i % 20, 75) for i in range(25)],
            iterations=40,
            threads=thread_count,
        )

    # High contention test
    benchmarker.benchmark_function(
        "high_contention",
        lambda: cached_cpu_memory(1, 100),  # Same key, high contention
        iterations=200,
        threads=8,
    )

    # Compare thread performance
    thread_tests = ["single_thread"] + [f"threads_{t}" for t in [2, 4, 8, 16]] + ["high_contention"]
    benchmarker.compare_results(*thread_tests)

    return benchmarker


def benchmark_cache_efficiency():
    """Test cache hit rates and efficiency."""
    print("\n📈 Cache Efficiency Testing")
    print("=" * 40)

    benchmarker = StressBenchmarker()

    # Clear caches to start fresh
    clear_cache()

    # High hit rate scenario (repeated keys)
    repeated_keys = [1, 2, 3, 4, 5] * 50
    benchmarker.benchmark_function(
        "high_hit_rate",
        lambda: [cached_cpu_memory(key, 50) for key in repeated_keys],
        iterations=10,
    )

    # Low hit rate scenario (random keys)
    benchmarker.benchmark_function(
        "low_hit_rate",
        lambda: [cached_cpu_memory(random.randint(1, 1000), 50) for _ in range(250)],
        iterations=10,
    )

    # Mixed scenario
    mixed_pattern = []
    for _ in range(100):
        if random.random() < 0.7:  # 70% chance of repeated key
            mixed_pattern.append(random.randint(1, 10))
        else:  # 30% chance of new key
            mixed_pattern.append(random.randint(100, 1000))

    benchmarker.benchmark_function(
        "mixed_pattern",
        lambda: [cached_cpu_memory(key, 50) for key in mixed_pattern],
        iterations=10,
    )

    benchmarker.compare_results("high_hit_rate", "low_hit_rate", "mixed_pattern")

    return benchmarker


def benchmark_cache_sizes():
    """Test performance with different cache sizes."""
    print("\n📏 Cache Size Performance")
    print("=" * 35)

    benchmarker = StressBenchmarker()

    for cache_size in config.cache_sizes:
        print(f"\n🧪 Testing cache size: {cache_size}")

        @memoize(maxsize=cache_size)
        def sized_cache_func(x, complexity=40):
            return expensive_cpu_operation(x, complexity)

        # Test with 2x cache size to force evictions
        test_range = cache_size * 2

        benchmarker.benchmark_function(
            f"cache_size_{cache_size}",
            lambda test_range=test_range: [sized_cache_func(i % test_range) for i in range(200)],
            iterations=25,
        )

    # Compare all cache sizes
    cache_tests = [f"cache_size_{size}" for size in config.cache_sizes]
    benchmarker.compare_results(*cache_tests)

    return benchmarker


# =============================================================================
# Main Stress Test Suite
# =============================================================================


def run_comprehensive_stress_tests():
    """Run the complete stress testing suite."""
    print("🏆 Comprehensive Stress Testing Suite")
    print("=" * 60)

    # System information
    print(f"💻 System: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total // 1024**3}GB RAM")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"🔧 Redis: {'Enabled' if redis_enabled else 'Disabled'}")
    print()

    all_benchmarkers = []

    try:
        # 1. Backend comparison
        all_benchmarkers.append(benchmark_backends_comparison())

        # 2. Memory stress testing
        all_benchmarkers.append(benchmark_memory_stress())

        # 3. Concurrent stress testing
        all_benchmarkers.append(benchmark_concurrent_stress())

        # 4. Cache efficiency testing
        all_benchmarkers.append(benchmark_cache_efficiency())

        # 5. Cache size testing
        all_benchmarkers.append(benchmark_cache_sizes())

    except KeyboardInterrupt:
        print("\n❌ Testing interrupted by user")
        return

    # Summary report
    print("\n📋 COMPREHENSIVE SUMMARY REPORT")
    print("=" * 60)

    # Collect best performers
    best_performers = {}

    for i, benchmarker in enumerate(all_benchmarkers, 1):
        print(f"\n📊 Test Suite {i} Results:")

        best_throughput = 0
        best_test = None

        for name, result in benchmarker.results.items():
            stats = result.get_statistics()
            if "error" not in stats:
                throughput = stats["throughput_ops_sec"]
                print(
                    f"  {name}: {stats['mean_time_ms']:.2f}ms, {throughput:.1f} ops/sec, "
                    f"{stats['cache_hit_rate'] * 100:.1f}% hit rate"
                )

                if throughput > best_throughput:
                    best_throughput = throughput
                    best_test = name

        if best_test:
            best_performers[f"Suite_{i}"] = (best_test, best_throughput)

    # Overall best performers
    print("\n🏆 TOP PERFORMERS:")
    for suite, (test, throughput) in best_performers.items():
        print(f"  {suite}: {test} ({throughput:.1f} ops/sec)")

    # Cache statistics
    try:
        final_stats = get_cache_stats()
        print("\n💾 Final Cache Statistics:")
        print(f"  {final_stats}")
    except Exception as e:
        print(f"⚠️ Could not retrieve cache stats: {e}")

    # Memory report
    memory_stats = MemoryMonitor().get_stats()
    print(f"\n🧠 Final Memory Usage: {memory_stats['current_mb']:.1f}MB")


# =============================================================================
# Advanced Async Tests (Bonus)
# =============================================================================


async def async_stress_test():
    """Bonus: Async performance testing."""
    print("\n⚡ Async Performance Testing")
    print("=" * 35)

    @cached(ttl=300, adapter="memory")
    async def async_cached_operation(n: int):
        await asyncio.sleep(0.001)  # Simulate async I/O
        return expensive_cpu_operation(n, 30)

    # Concurrent async operations
    start_time = time.time()
    tasks = [async_cached_operation(i % 20) for i in range(100)]
    await asyncio.gather(*tasks)
    end_time = time.time()

    async_throughput = 100 / (end_time - start_time)
    print(f"✅ Async operations: {async_throughput:.1f} ops/sec")


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    start_time = time.time()

    try:
        # Run comprehensive stress tests
        run_comprehensive_stress_tests()

        # Run async tests if possible
        try:
            asyncio.run(async_stress_test())
        except Exception as e:
            print(f"⚠️ Async tests skipped: {e}")

    except Exception as e:
        print(f"❌ Critical error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        total_time = time.time() - start_time
        print(f"\n✅ Complete stress testing suite finished in {total_time:.2f} seconds")
        print("📊 Check results above for performance insights and optimization opportunities!")

        # Cleanup
        if redis_enabled:
            try:
                redis_adapter = global_manager.get_adapter("redis")
                if redis_adapter and hasattr(redis_adapter, "clear"):
                    redis_adapter.clear()
                    print("🧹 Redis cache cleared")
            except Exception:
                pass
