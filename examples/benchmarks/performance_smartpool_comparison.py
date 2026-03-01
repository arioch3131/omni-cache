# =============================================================================
# EXAMPLE: Enhanced Performance Comparison with SmartPool
# File: examples/benchmarks/performance_smartpool_comparison.py
# =============================================================================

"""
Enhanced performance comparison including SmartPool adapter.

This example demonstrates:
- Memory vs Redis vs SmartPool performance comparison
- Object pooling vs traditional caching performance
- Connection pooling benchmarks
- Object lifecycle and reuse optimization
- Memory usage patterns comparison
- Concurrent object management performance
"""

import gc
import hashlib
import os
import random
import statistics
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import psutil

from omni_cache import (
    CacheBackend,
    cached,
    create_adapter,
    get_cache_stats,
    memoize,
    setup,
)

# =============================================================================
# SmartPool Integration
# =============================================================================


class ExpensiveObject:
    """Simulate an expensive-to-create object."""

    def __init__(self, size: int = 1024, computation_cost: int = 100):
        self.id = id(self)
        self.size = size
        self.data = self._generate_expensive_data(size, computation_cost)
        self.created_at = time.time()
        self.access_count = 0
        self.last_access = time.time()

    def _generate_expensive_data(self, size: int, cost: int) -> bytes:
        """Simulate expensive data generation."""
        # CPU-intensive computation
        result = 0
        for i in range(cost):
            result += sum(range(i + 1))

        # Memory allocation
        data = bytearray(size)
        for i in range(0, min(size, 1000)):
            data[i] = (result + i) % 256

        return bytes(data)

    def use(self) -> str:
        """Simulate using the object."""
        self.access_count += 1
        self.last_access = time.time()
        return f"Object_{self.id}_used_{self.access_count}_times"

    def reset(self):
        """Reset object state for reuse."""
        self.last_access = time.time()
        # Don't reset access_count to track total usage


class DatabaseConnectionMock:
    """Mock database connection for pooling tests."""

    def __init__(self, connection_cost: float = 0.1):
        print(
            f"[{threading.current_thread().name}] Creating DB connection (cost: {connection_cost}s)"
        )
        time.sleep(connection_cost)  # Simulate connection time

        self.connection_id = random.randint(1000, 9999)
        self.created_at = time.time()
        self.query_count = 0
        self.is_active = True

    def execute_query(self, query: str) -> list[dict]:
        """Simulate query execution."""
        if not self.is_active:
            raise Exception("Connection is closed")

        self.query_count += 1
        time.sleep(0.001)  # Simulate query time

        return [{"id": i, "value": f"result_{i}_{self.connection_id}"} for i in range(5)]

    def reset(self):
        """Reset connection state."""
        pass  # Connection ready for reuse

    def close(self):
        """Close connection."""
        print(f"[{threading.current_thread().name}] Closing DB connection {self.connection_id}")
        self.is_active = False


class WeakRefWrapper:
    """Generic wrapper for objects that don't support weak referencing."""

    def __init__(self, obj: Any):
        self.obj = obj

    def __getattr__(self, name):
        return getattr(self.obj, name)


# =============================================================================
# Enhanced Configuration and Setup
# =============================================================================


@dataclass
class StressTestConfig:
    """Enhanced configuration with SmartPool settings."""

    # Basic benchmark settings
    warmup_iterations: int = 50
    benchmark_iterations: int = 500
    concurrent_threads: int = 8

    # Memory stress settings
    large_object_sizes: list[int] = None
    memory_pressure_sizes: list[int] = None
    cache_sizes: list[int] = None

    # SmartPool settings
    pool_sizes: list[int] = None
    object_creation_costs: list[float] = None

    # Redis settings
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 3

    def __post_init__(self):
        if self.large_object_sizes is None:
            self.large_object_sizes = [1_000, 10_000, 100_000, 1_000_000]
        if self.memory_pressure_sizes is None:
            self.memory_pressure_sizes = [50_000, 100_000, 500_000, 1_000_000]
        if self.cache_sizes is None:
            self.cache_sizes = [100, 1_000, 5_000, 10_000]
        if self.pool_sizes is None:
            self.pool_sizes = [5, 10, 20, 50]
        if self.object_creation_costs is None:
            self.object_creation_costs = [0.01, 0.05, 0.1, 0.2]


config = StressTestConfig()

print("🚀 Enhanced Omni-Cache Performance Testing Suite with SmartPool")
print("=" * 70)

# =============================================================================
# Enhanced Adapter Setup with SmartPool
# =============================================================================


def setup_adapters():
    """Setup Memory, Redis, and SmartPool adapters."""
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
        print("   Continuing with memory-only tests")

    # Setup SmartPool adapters
    smartpool_available = False
    try:
        # SmartPool for expensive objects
        def create_expensive_object():
            return WeakRefWrapper(ExpensiveObject(size=2048, computation_cost=50))

        def reset_expensive_object(wrapper):
            wrapper.obj.reset()

        smartpool_expensive = create_adapter(
            CacheBackend.SMARTPOOL,
            {
                "name": "expensive_objects",
                "factory_function": create_expensive_object,
                "initial_size": 5,
                "max_size": 20,
                "memory_preset": "BALANCED",
                "enable_auto_tuning": True,
                "extra_config": {
                    "reset_func": reset_expensive_object,
                },
            },
        )
        manager.register_adapter("smartpool_expensive", smartpool_expensive)

        # SmartPool for database connections
        def create_db_connection():
            return WeakRefWrapper(DatabaseConnectionMock(connection_cost=0.05))

        def reset_db_connection(wrapper):
            wrapper.obj.reset()

        def destroy_db_connection(wrapper):
            wrapper.obj.close()

        smartpool_db = create_adapter(
            CacheBackend.SMARTPOOL,
            {
                "name": "db_connections",
                "factory_function": create_db_connection,
                "initial_size": 3,
                "max_size": 15,
                "memory_preset": "HIGH_THROUGHPUT",
                "enable_auto_tuning": False,
                "extra_config": {
                    "reset_func": reset_db_connection,
                    "destroy_func": destroy_db_connection,
                },
            },
        )
        manager.register_adapter("smartpool_db", smartpool_db)

        print("✅ SmartPool adapters configured successfully")
        smartpool_available = True

    except Exception as e:
        print(f"⚠️  SmartPool not available: {e}")
        print("   Continuing without SmartPool tests")

    # Set default adapter
    manager._config.default_adapter = "memory"

    # Configure routing rules
    manager.add_routing_rule("memory", "memory")
    manager.add_routing_rule("large", "large_memory")
    manager.add_routing_rule("redis", "redis")
    manager.add_routing_rule("pool", "smartpool_expensive")
    manager.add_routing_rule("db", "smartpool_db")

    print("✅ Adapters configured successfully")
    return manager, redis_available, smartpool_available


# Setup global manager and check availability
global_manager, redis_enabled, smartpool_enabled = setup_adapters()

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


def expensive_object_creation() -> ExpensiveObject:
    """Create expensive object without pooling."""
    return ExpensiveObject(size=2048, computation_cost=50)


def database_query_simulation(query: str = "SELECT * FROM users") -> list[dict]:
    """Simulate database query without connection pooling."""
    # Create new connection each time (expensive)
    conn = DatabaseConnectionMock(connection_cost=0.05)
    try:
        return conn.execute_query(query)
    finally:
        conn.close()


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


# SmartPool-based cached functions (if available)
if smartpool_enabled:

    def smartpool_expensive_object(obj_size: int = 2048) -> str:
        """Use expensive object from SmartPool."""
        adapter = global_manager.get_adapter("smartpool_expensive")
        with adapter.borrow() as wrapper:
            obj = wrapper.obj
            return obj.use()

    def smartpool_database_query(query: str = "SELECT * FROM users") -> list[dict]:
        """Execute query using pooled connection."""
        adapter = global_manager.get_adapter("smartpool_db")
        with adapter.borrow() as wrapper:
            conn = wrapper.obj
            return conn.execute_query(query)


# Memoized functions with different cache sizes
@memoize(maxsize=1000)
def memoized_cpu_small(n: int, complexity: int = 50) -> int:
    return expensive_cpu_operation(n, complexity)


@memoize(maxsize=10000)
def memoized_cpu_large(n: int, complexity: int = 50) -> int:
    return expensive_cpu_operation(n, complexity)


# =============================================================================
# Enhanced Benchmark Framework (unchanged from original)
# =============================================================================


class MemoryMonitor:
    """Monitor memory usage during tests."""

    def __init__(self):
        self.process = psutil.Process()
        self.start_memory = None
        self.peak_memory = None

    def start(self):
        """Start monitoring memory."""
        gc.collect()
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
        self.pool_reuses = 0
        self.pool_creates = 0
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
            return {"error": "No valid measurements"}

        mean_time = statistics.mean(self.times)
        median_time = statistics.median(self.times)

        stats = {
            "count": len(self.times),
            "mean_time_ms": mean_time * 1000,
            "median_time_ms": median_time * 1000,
            "min_time_ms": min(self.times) * 1000,
            "max_time_ms": max(self.times) * 1000,
            "throughput_ops_sec": 1.0 / mean_time if mean_time > 0 else 0,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": (
                self.cache_hits / (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses) > 0
                else 0
            ),
            "pool_reuses": self.pool_reuses,
            "pool_creates": self.pool_creates,
            "pool_reuse_rate": (
                self.pool_reuses / (self.pool_reuses + self.pool_creates)
                if (self.pool_reuses + self.pool_creates) > 0
                else None
            ),
            "errors": self.errors,
            "threads": self.thread_count,
        }

        if len(self.times) > 1:
            stats["stdev_ms"] = statistics.stdev(self.times) * 1000

        if self.memory_stats:
            avg_delta = statistics.mean([m["delta_mb"] for m in self.memory_stats])
            peak_memory = max([m["peak_mb"] for m in self.memory_stats])
            stats.update({"avg_memory_mb": avg_delta, "peak_memory_mb": peak_memory})

        return stats


class StressBenchmarker:
    """Enhanced benchmarker with SmartPool support."""

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

    @staticmethod
    def _resolve_smartpool_adapter(name: str) -> str | None:
        """Map a benchmark name to the associated SmartPool adapter."""
        db_pool_scenarios = {"smartpool_db", "smartpool_connections", "concurrent_pooled"}
        obj_pool_scenarios = {"smartpool_objects", "smartpool_reuse"}

        if name in db_pool_scenarios:
            return "smartpool_db"
        if name in obj_pool_scenarios:
            return "smartpool_expensive"
        return None

    def _get_smartpool_counters(self, adapter_name: str | None) -> tuple[int, int]:
        """Read (reuses, creates) counters from a SmartPool adapter."""
        if not adapter_name:
            return 0, 0
        try:
            adapter = global_manager.get_adapter(adapter_name)
            if adapter is None or not hasattr(adapter, "get_detailed_smartpool_stats"):
                return 0, 0

            details = adapter.get_detailed_smartpool_stats()
            counters = details.get("basic_stats", {}).get("counters", {})
            reuses = int(counters.get("reuses", 0) or 0)
            creates = int(counters.get("creates", 0) or 0)
            return reuses, creates
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
        pool_adapter_name = self._resolve_smartpool_adapter(name)
        start_reuses, start_creates = self._get_smartpool_counters(pool_adapter_name)

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
        end_reuses, end_creates = self._get_smartpool_counters(pool_adapter_name)
        result.pool_reuses = max(0, end_reuses - start_reuses)
        result.pool_creates = max(0, end_creates - start_creates)

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
        print("-" * 96)
        print(
            f"{'Test Name':<25} {'Time(ms)':<12} {'Throughput':<15} "
            f"{'Cache Hit':<12} {'Pool Reuse':<12} {'Memory(MB)':<12}"
        )
        print("-" * 96)

        for name in names:
            if name in self.results:
                stats = self.results[name].get_statistics()
                if "error" not in stats:
                    memory_str = (
                        f"{stats.get('avg_memory_mb', 0):.1f}"
                        if "avg_memory_mb" in stats
                        else "N/A"
                    )
                    cache_hit_str = f"{stats['cache_hit_rate'] * 100:.1f}%"
                    pool_reuse_rate = stats.get("pool_reuse_rate")
                    pool_reuse_str = (
                        f"{pool_reuse_rate * 100:.1f}%" if pool_reuse_rate is not None else "N/A"
                    )
                    print(
                        f"{name:<25} {stats['mean_time_ms']:<12.2f} "
                        f"{stats['throughput_ops_sec']:<15.1f} "
                        f"{cache_hit_str:<12} {pool_reuse_str:<12} {memory_str:<12}"
                    )


# =============================================================================
# SmartPool-specific Benchmark Scenarios
# =============================================================================


def benchmark_object_pooling_vs_creation():
    """Compare object pooling vs direct creation."""
    if not smartpool_enabled:
        print("⚠️ SmartPool not available, skipping pooling tests")
        return None

    print("\n🏊 Object Pooling vs Direct Creation")
    print("=" * 45)

    benchmarker = StressBenchmarker()

    # Direct object creation (no pooling)
    benchmarker.benchmark_function(
        "direct_creation", lambda: expensive_object_creation().use(), iterations=100
    )

    # SmartPool object reuse
    benchmarker.benchmark_function(
        "smartpool_reuse", lambda: smartpool_expensive_object(), iterations=100
    )

    benchmarker.compare_results("direct_creation", "smartpool_reuse")

    return benchmarker


def benchmark_connection_pooling():
    """Compare connection pooling vs direct connections."""
    if not smartpool_enabled:
        print("⚠️ SmartPool not available, skipping connection tests")
        return None

    print("\n🔌 Connection Pooling vs Direct Connections")
    print("=" * 50)

    benchmarker = StressBenchmarker()

    # Direct database connections (no pooling)
    benchmarker.benchmark_function(
        "direct_connections",
        lambda: database_query_simulation(),
        iterations=50,  # Fewer iterations due to cost
    )

    # SmartPool connection reuse
    benchmarker.benchmark_function(
        "smartpool_connections", lambda: smartpool_database_query(), iterations=50
    )

    # Concurrent connection tests
    benchmarker.benchmark_function(
        "concurrent_direct", lambda: database_query_simulation(), iterations=100, threads=4
    )

    benchmarker.benchmark_function(
        "concurrent_pooled", lambda: smartpool_database_query(), iterations=100, threads=4
    )

    benchmarker.compare_results(
        "direct_connections", "smartpool_connections", "concurrent_direct", "concurrent_pooled"
    )

    return benchmarker


def benchmark_backends_comparison():
    """Compare Memory vs Redis vs SmartPool performance."""
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

    # SmartPool tests (if available)
    if smartpool_enabled:
        benchmarker.benchmark_function(
            "smartpool_objects", lambda: smartpool_expensive_object(), iterations=200
        )

        benchmarker.benchmark_function(
            "smartpool_db", lambda: smartpool_database_query(), iterations=100
        )

    # Compare all available backends
    comparison_tests = ["memory_cpu", "memory_io"]
    if redis_enabled:
        comparison_tests.extend(["redis_cpu", "redis_io"])
    if smartpool_enabled:
        comparison_tests.extend(["smartpool_objects", "smartpool_db"])

    benchmarker.compare_results(*comparison_tests)

    return benchmarker


# =============================================================================
# Main Test Suite with SmartPool
# =============================================================================


def run_comprehensive_stress_tests():
    """Run the complete stress testing suite including SmartPool."""
    print("🏆 Comprehensive Stress Testing Suite with SmartPool")
    print("=" * 70)

    # System information
    print(f"💻 System: {psutil.cpu_count()} CPUs, {psutil.virtual_memory().total // 1024**3}GB RAM")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"🔧 Redis: {'Enabled' if redis_enabled else 'Disabled'}")
    print(f"🏊 SmartPool: {'Enabled' if smartpool_enabled else 'Disabled'}")
    print()

    all_benchmarkers = []

    try:
        # 1. Backend comparison (including SmartPool)
        all_benchmarkers.append(benchmark_backends_comparison())

        # 2. SmartPool-specific tests
        if smartpool_enabled:
            all_benchmarkers.append(benchmark_object_pooling_vs_creation())
            all_benchmarkers.append(benchmark_connection_pooling())

        # 3. Traditional cache tests (adapt existing functions as needed)
        # ... (rest of the existing benchmark functions)

    except KeyboardInterrupt:
        print("\n❌ Testing interrupted by user")
        return

    # Enhanced summary report with SmartPool insights
    print("\n📋 COMPREHENSIVE SUMMARY REPORT")
    print("=" * 70)

    # Collect best performers by category
    best_performers = {}

    for i, benchmarker in enumerate(all_benchmarkers, 1):
        if benchmarker is None:  # Skip disabled benchmarks
            continue

        print(f"\n📊 Test Suite {i} Results:")

        best_throughput = 0
        best_test = None

        for name, result in benchmarker.results.items():
            stats = result.get_statistics()
            if "error" not in stats:
                throughput = stats["throughput_ops_sec"]
                pool_reuse_rate = stats.get("pool_reuse_rate")
                pool_reuse_text = (
                    f", {pool_reuse_rate * 100:.1f}% pool reuse"
                    if pool_reuse_rate is not None
                    else ""
                )
                print(
                    f"  {name}: {stats['mean_time_ms']:.2f}ms, {throughput:.1f} ops/sec, "
                    f"{stats['cache_hit_rate'] * 100:.1f}% cache hit{pool_reuse_text}"
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

    # SmartPool specific insights
    if smartpool_enabled:
        print("\n🏊 SmartPool Insights:")
        try:
            expensive_adapter = global_manager.get_adapter("smartpool_expensive")
            db_adapter = global_manager.get_adapter("smartpool_db")

            expensive_info = expensive_adapter.get_backend_info()
            db_info = db_adapter.get_backend_info()

            print(
                f"  Expensive Objects Pool: {expensive_info['current_size']} objects, "
                f"{expensive_info['active_objects']} active"
            )
            print(
                f"  DB Connections Pool: {db_info['current_size']} connections, "
                f"{db_info['active_objects']} active"
            )
        except Exception as e:
            print(f"  Could not retrieve SmartPool stats: {e}")

    # Final cache and memory statistics
    try:
        final_stats = get_cache_stats()
        print("\n💾 Final Cache Statistics:")
        print(f"  {final_stats}")
    except Exception as e:
        print(f"⚠️ Could not retrieve cache stats: {e}")

    # Memory report
    memory_stats = MemoryMonitor().get_stats()
    print(f"\n🧠 Final Memory Usage: {memory_stats['current_mb']:.1f}MB")


if __name__ == "__main__":
    print("Starting comprehensive performance tests...")
    run_comprehensive_stress_tests()
    print("\n✅ All tests completed!")
