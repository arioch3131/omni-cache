#!/usr/bin/env python3
"""
REFACTORED PERFORMANCE COMPARISON - Clean SmartPool Parameter Handling

This version properly handles parameter passing to SmartPool factories,
ensures clean adapter management, and provides consistent benchmarking
across all cache/pool adapters.
"""

import gc
import random
import string
import time
from collections.abc import Callable

import psutil

# Omni-cache imports
from omni_cache import create_adapter, setup
from omni_cache.core.interfaces import CacheBackend

# --- Configuration ---
ITERATIONS = 200  # Manageable load for testing
DATA_SIZES = {"1KB": 1024, "10KB": 10 * 1024, "100KB": 100 * 1024, "1MB": 1000 * 1024}


# --- Helper Functions ---
def generate_random_string(length: int) -> str:
    """Generates a random string of specified length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def get_memory_usage():
    """Returns current memory usage in MB."""
    try:
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


class BenchmarkResult:
    """Enhanced benchmark result with clear metrics."""

    def __init__(
        self,
        adapter_type: str,
        category: str,
        operation: str,
        data_size: str,
        avg_time: float,
        ops_per_sec: float,
        memory_delta: float,
        success_rate: float,
    ):
        self.adapter_type = adapter_type
        self.category = category
        self.operation = operation
        self.data_size = data_size
        self.avg_time = avg_time
        self.ops_per_sec = ops_per_sec
        self.memory_delta = memory_delta
        self.success_rate = success_rate


def run_benchmark(
    adapter_name: str,
    category: str,
    operation: str,
    data_size: str,
    func: Callable,
    data_generator: Callable,
    iterations: int,
) -> BenchmarkResult:
    """Enhanced benchmark runner with better error handling."""

    print(f"   🔄 Running {adapter_name} {operation} benchmark...")

    # Warmup
    for _ in range(min(10, iterations // 10)):
        try:
            test_data = data_generator()
            func(f"warmup_{random.randint(1, 1000)}", test_data)
        except Exception:
            pass

    # Force garbage collection before measurement
    gc.collect()
    start_memory = get_memory_usage()

    # Main benchmark
    times = []
    successes = 0

    start_time = time.time()

    for i in range(iterations):
        iteration_start = time.time()
        try:
            test_data = data_generator()
            func(f"key_{i}", test_data)
            successes += 1
        except Exception as e:
            print(f"   ⚠️ Iteration {i} failed: {e}")

        times.append(time.time() - iteration_start)

    total_time = time.time() - start_time
    end_memory = get_memory_usage()

    # Calculate metrics
    avg_time = (total_time / iterations) * 1000  # Convert to ms
    ops_per_sec = iterations / total_time if total_time > 0 else 0
    memory_delta = end_memory - start_memory
    success_rate = successes / iterations if iterations > 0 else 0

    print(
        f"   ✅ {adapter_name}: {avg_time:.2f}ms avg, "
        f"{ops_per_sec:.1f} ops/sec, {success_rate:.1%} success"
    )

    return BenchmarkResult(
        adapter_type=adapter_name,
        category=category,
        operation=operation,
        data_size=data_size,
        avg_time=avg_time,
        ops_per_sec=ops_per_sec,
        memory_delta=memory_delta,
        success_rate=success_rate,
    )


def create_smartpool_factory_function():
    """Create a flexible factory function that accepts various parameters."""

    def create_smart_pooled_object(size: int = 1024, **kwargs):
        """
        Enhanced factory function that accepts size and ignores extra parameters.
        Extra parameters (operation_type, buffer_type, etc.) are used for key generation only.
        """
        return {
            "size": size,
            "buffer": bytearray(size),
            "operations": 0,
            "created_at": time.time(),
            "metadata": {},
            "last_operation": None,
            "data_length": 0,
        }

    return create_smart_pooled_object


def setup_adapters(manager):
    """Setup all adapters with proper configuration."""
    adapters = {}

    # Memory adapter
    try:
        memory_adapter = create_adapter(
            CacheBackend.MEMORY, {"name": "memory", "max_size": 1000, "enable_stats": True}
        )
        if manager.register_adapter("memory", memory_adapter):
            adapters["memory"] = memory_adapter
            print("✅ Memory adapter configured")
        else:
            print("❌ Memory adapter registration failed")
    except Exception as e:
        print(f"❌ Memory adapter failed: {e}")

    # Redis adapter (optional)
    try:
        redis_adapter = create_adapter(
            CacheBackend.REDIS,
            {
                "name": "redis",
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "socket_timeout": 5.0,
                "enable_stats": True,
            },
        )
        if manager.register_adapter("redis", redis_adapter):
            adapters["redis"] = redis_adapter
            print("✅ Redis adapter configured")
        else:
            print("❌ Redis adapter registration failed")
    except Exception as e:
        print(f"❌ Redis unavailable: {e}")

    # Memcached adapter (optional)
    try:
        memcached_adapter = create_adapter(
            CacheBackend.MEMCACHED,
            {
                "name": "memcached",
                "host": "localhost",
                "port": 11211,
                "timeout": 3.0,
                "connect_timeout": 2.0,
                "enable_stats": True,
            },
        )
        if manager.register_adapter("memcached", memcached_adapter):
            adapters["memcached"] = memcached_adapter
            print("✅ Memcached adapter configured")
        else:
            print("❌ Memcached adapter registration failed")
    except Exception as e:
        print(f"❌ Memcached unavailable: {e}")

    # SmartPool adapter - single, properly configured instance
    try:
        smartpool_config = {
            "name": "smartpool",
            "factory_function": create_smartpool_factory_function(),
            "initial_size": 5,
            "max_size": 50,
            "memory_preset": "HIGH_THROUGHPUT",
            "enable_auto_tuning": False,
            "enable_performance_metrics": True,
            "auto_wrap_objects": True,
        }

        smartpool_adapter = create_adapter(CacheBackend.SMARTPOOL, smartpool_config)
        if manager.register_adapter("smartpool", smartpool_adapter):
            adapters["smartpool"] = smartpool_adapter
            print("✅ SmartPool adapter configured")
        else:
            print("❌ SmartPool adapter registration failed")
    except Exception as e:
        print(f"❌ SmartPool setup failed: {e}")

    return adapters


def benchmark_caching_performance(
    manager, data_size: str, size_bytes: int
) -> list[BenchmarkResult]:
    """Benchmark pure caching operations (Memory and Redis strengths)."""
    results = []
    test_data = generate_random_string(size_bytes)

    print(f"   📊 Caching Performance Test for {data_size}")

    # Memory Adapter - Caching benchmark
    if "memory" in manager.list_adapters():
        try:
            memory_adapter = manager.get_adapter("memory")

            def memory_cache_operation(key: str, data: str) -> str:
                memory_adapter.set(key, data, ttl=300)
                retrieved = memory_adapter.get(key)
                return retrieved

            results.append(
                run_benchmark(
                    "memory",
                    "caching",
                    "set+get",
                    data_size,
                    memory_cache_operation,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

            memory_adapter.clear()
        except Exception as e:
            print(f"   ❌ Memory caching benchmark failed: {e}")

    # Redis Adapter - Caching benchmark
    if "redis" in manager.list_adapters():
        try:
            redis_adapter = manager.get_adapter("redis")

            def redis_cache_operation(key: str, data: str) -> str:
                redis_adapter.set(key, data, ttl=300)
                retrieved = redis_adapter.get(key)
                return retrieved

            results.append(
                run_benchmark(
                    "redis",
                    "caching",
                    "set+get",
                    data_size,
                    redis_cache_operation,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

            redis_adapter.clear()
        except Exception as e:
            print(f"   ❌ Redis caching benchmark failed: {e}")

    # Memcached Adapter - Caching benchmark
    if "memcached" in manager.list_adapters():
        try:
            memcached_adapter = manager.get_adapter("memcached")

            def memcached_cache_operation(key: str, data: str) -> str:
                memcached_adapter.set(key, data, ttl=300)
                retrieved = memcached_adapter.get(key)
                return retrieved

            results.append(
                run_benchmark(
                    "memcached",
                    "caching",
                    "set+get",
                    data_size,
                    memcached_cache_operation,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

            memcached_adapter.clear()
        except Exception as e:
            print(f"   ❌ Memcached caching benchmark failed: {e}")

    return results


def benchmark_object_pooling(manager, data_size: str, size_bytes: int) -> list[BenchmarkResult]:
    """Benchmark object pooling operations (SmartPool strength)."""
    results = []
    test_data = generate_random_string(size_bytes)

    print(f"   🏊 Object Pooling Performance Test for {data_size}")

    if "smartpool" not in manager.list_adapters():
        print("   ⚠️ SmartPool adapter not available for pooling benchmark")
        return results

    try:
        smartpool_adapter = manager.get_adapter("smartpool")

        # Check initial pool health
        initial_health = smartpool_adapter.health_check()
        print(f"   📊 Pre-benchmark pool health: {'✅ GOOD' if initial_health else '❌ POOR'}")

        # Inspect pool configuration
        print("   🔍 Inspecting pool configuration...")
        try:
            # Use size parameter for proper key generation
            with smartpool_adapter.borrow(size=size_bytes) as sample_obj:
                obj_type = (
                    type(sample_obj._obj) if hasattr(sample_obj, "_obj") else type(sample_obj)
                )
                print(f"   📋 Sample object type: {obj_type}")
                if hasattr(sample_obj, "_obj") and hasattr(sample_obj._obj, "get"):
                    print(f"   📋 Sample object size: {sample_obj._obj.get('size', 'N/A')}")
        except Exception as e:
            print(f"   ⚠️ Could not inspect sample object: {e}")

        # Enhanced pooling operation with proper parameter handling
        def smartpool_pooling_operation(key: str, data: str) -> int:
            """SmartPool operation with proper parameter passing for key generation."""
            try:
                data_length = len(data)
                # Calculate size bucket for consistent pooling
                size_bucket = ((data_length // 1024) + 1) * 1024  # Round up to next KB

                # Pass parameters that will be used by both get_key() and create()
                with smartpool_adapter.borrow(
                    size=size_bucket,
                ) as obj:
                    if obj is None:
                        raise ValueError("Pool returned None object")

                    # Work with the object (whether wrapped or not)
                    if hasattr(obj, "_obj"):
                        # Object is wrapped in AutoWeakRefWrapper
                        actual_obj = obj._obj
                    else:
                        actual_obj = obj

                    # Update object state
                    actual_obj["last_operation"] = f"process_{key}"
                    actual_obj["data_length"] = data_length
                    actual_obj["operations"] = actual_obj.get("operations", 0) + 1

                    # Simulate some processing
                    # if 'buffer' in actual_obj:
                    #     buffer_size = min(len(actual_obj['buffer']), data_length)
                    #     actual_obj['buffer'][:buffer_size] = data.encode('utf-8')[:buffer_size]

                    return data_length

            except Exception as e:
                print(f"   🔍 Pool operation error: {str(e)[:60]}")
                raise e

        # Run benchmark
        print("   🚀 Running SmartPool benchmark...")

        results.append(
            run_benchmark(
                "smartpool",
                "pooling",
                "borrow+process+return",
                data_size,
                smartpool_pooling_operation,
                lambda: test_data,
                ITERATIONS,
            )
        )

        # Post-benchmark analysis
        final_health = smartpool_adapter.health_check()
        print(f"   📊 Post-benchmark pool health: {'✅ GOOD' if final_health else '❌ DEGRADED'}")

        try:
            backend_info = smartpool_adapter.get_backend_info()
            hit_rate = backend_info.get("hit_rate", 0)
            print(f"   📈 Final hit rate: {hit_rate:.1%}")

            performance_metrics = smartpool_adapter.get_performance_metrics()
            if "error" not in performance_metrics and "current_snapshot" in performance_metrics:
                key_metrics = performance_metrics["current_snapshot"].get("key_metrics", {})
                top_keys = key_metrics.get("top_keys_by_usage", [])
                if top_keys:
                    print(f"   🔑 Top Keys by Usage: {top_keys[:10]}")
        except Exception as e:
            print(f"   ⚠️ Could not get final stats: {e}")

    except Exception as e:
        print(f"   ❌ SmartPool pooling benchmark failed: {e}")
        import traceback

        traceback.print_exc()

    return results


def benchmark_unified_data_processing(
    manager, data_size: str, size_bytes: int
) -> list[BenchmarkResult]:
    """Unified benchmark: all adapters perform the same data processing task."""
    results = []
    test_data = generate_random_string(size_bytes)

    print(f"   ⚖️ Unified Data Processing Test for {data_size}")

    # Memory Adapter - Data processing
    if "memory" in manager.list_adapters():
        try:
            memory_adapter = manager.get_adapter("memory")

            def memory_process_data(key: str, data: str) -> int:
                # Process and cache result
                checksum = sum(ord(c) for c in data) % 1000000
                memory_adapter.set(f"proc_{key}", {"checksum": checksum, "length": len(data)})
                result = memory_adapter.get(f"proc_{key}")
                memory_adapter.delete(f"proc_{key}")
                return result["checksum"] if result else 0

            results.append(
                run_benchmark(
                    "memory",
                    "unified",
                    "process_data",
                    data_size,
                    memory_process_data,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

        except Exception as e:
            print(f"   ❌ Memory unified benchmark failed: {e}")

    # Redis Adapter - Data processing
    if "redis" in manager.list_adapters():
        try:
            redis_adapter = manager.get_adapter("redis")

            def redis_process_data(key: str, data: str) -> int:
                # Process and cache result
                checksum = sum(ord(c) for c in data) % 1000000
                redis_adapter.set(f"proc_{key}", {"checksum": checksum, "length": len(data)})
                result = redis_adapter.get(f"proc_{key}")
                redis_adapter.delete(f"proc_{key}")
                return result["checksum"] if result else 0

            results.append(
                run_benchmark(
                    "redis",
                    "unified",
                    "process_data",
                    data_size,
                    redis_process_data,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

        except Exception as e:
            print(f"   ❌ Redis unified benchmark failed: {e}")

    # Memcached Adapter - Data processing
    if "memcached" in manager.list_adapters():
        try:
            memcached_adapter = manager.get_adapter("memcached")

            def memcached_process_data(key: str, data: str) -> int:
                checksum = sum(ord(c) for c in data) % 1000000
                memcached_adapter.set(f"proc_{key}", {"checksum": checksum, "length": len(data)})
                result = memcached_adapter.get(f"proc_{key}")
                memcached_adapter.delete(f"proc_{key}")
                return result["checksum"] if result else 0

            results.append(
                run_benchmark(
                    "memcached",
                    "unified",
                    "process_data",
                    data_size,
                    memcached_process_data,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

        except Exception as e:
            print(f"   ❌ Memcached unified benchmark failed: {e}")

    # SmartPool Adapter - Data processing
    if "smartpool" in manager.list_adapters():
        try:
            smartpool_adapter = manager.get_adapter("smartpool")

            def smartpool_process_data(key: str, data: str) -> int:
                """Process data using SmartPool with proper parameter handling."""
                data_length = len(data)
                size_bucket = ((data_length // 1024) + 1) * 1024

                with smartpool_adapter.borrow(
                    size=size_bucket, processing_type="unified_benchmark"
                ) as processor:
                    # Get actual object
                    actual_obj = processor._obj if hasattr(processor, "_obj") else processor

                    # Process data in the pooled object
                    checksum = sum(ord(c) for c in data) % 1000000
                    actual_obj["current_data"] = data[:100]  # Store sample
                    actual_obj["checksum"] = checksum
                    actual_obj["processed_length"] = data_length
                    actual_obj["operations"] = actual_obj.get("operations", 0) + 1

                    return checksum

            results.append(
                run_benchmark(
                    "smartpool",
                    "unified",
                    "process_data",
                    data_size,
                    smartpool_process_data,
                    lambda: test_data,
                    ITERATIONS,
                )
            )

        except Exception as e:
            print(f"   ❌ SmartPool unified benchmark failed: {e}")

    return results


def print_category_results(results: list[BenchmarkResult], category: str):
    """Print results for a specific benchmark category."""
    category_results = [r for r in results if r.category == category]
    if not category_results:
        return

    print(f"\n📊 {category.upper()} PERFORMANCE RESULTS")
    print("-" * 50)

    for result in category_results:
        efficiency = (
            "🟢" if result.ops_per_sec > 1000 else "🟡" if result.ops_per_sec > 100 else "🔴"
        )
        print(
            f"{efficiency} {result.adapter_type:12} {result.data_size:6}: "
            f"{result.avg_time:6.2f}ms avg, {result.ops_per_sec:8.1f} ops/sec, "
            f"{result.success_rate:5.1%} success"
        )


def print_recommendations(results: list[BenchmarkResult]):
    """Provide performance recommendations based on results."""
    print("\n💡 PERFORMANCE RECOMMENDATIONS")
    print("-" * 50)

    # Group by category
    by_category = {}
    for result in results:
        if result.category not in by_category:
            by_category[result.category] = []
        by_category[result.category].append(result)

    for category, category_results in by_category.items():
        if not category_results:
            continue

        # Find best performer
        best = max(category_results, key=lambda r: r.ops_per_sec)

        print(f"\n{category.upper()} Best: {best.adapter_type} ({best.ops_per_sec:.1f} ops/sec)")

        # Category-specific recommendations
        if category == "caching":
            print(
                "  💡 For caching: Use Memory for speed, Redis for persistence, "
                "Memcached for lightweight distributed cache"
            )
        elif category == "pooling":
            print("  💡 For object pooling: SmartPool excels at object reuse")
        elif category == "unified":
            print("  💡 For mixed workloads: Consider adapter strengths")


def main():
    """Main benchmark execution."""
    print("🚀 Omni-Cache Performance Comparison - REFACTORED VERSION")
    print("=" * 60)
    print("Clean parameter handling and proper adapter management")

    # Setup
    print("\n🔧 Setting up adapters...")
    manager = setup(log_level="WARNING")  # Reduce log noise
    setup_adapters(manager)

    if not manager.list_adapters():
        print("❌ No adapters available for benchmarking")
        return

    print(f"✅ {len(manager.list_adapters())} adapters ready for benchmarking")

    # Run benchmarks for each data size
    all_results = []

    for size_name, size_bytes in DATA_SIZES.items():
        print(f"\n{'=' * 60}")
        print(f"🏃 BENCHMARKING {size_name} DATA SIZE ({size_bytes:,} bytes)")
        print(f"{'=' * 60}")

        # 1. Caching benchmark
        print(f"\n🗄️  Caching Performance Test ({size_name})")
        all_results.extend(benchmark_caching_performance(manager, size_name, size_bytes))

        # 2. Object pooling benchmark
        print(f"\n🏊 Object Pooling Performance Test ({size_name})")
        all_results.extend(benchmark_object_pooling(manager, size_name, size_bytes))

        # 3. Unified comparison
        print(f"\n⚖️  Unified Data Processing Test ({size_name})")
        all_results.extend(benchmark_unified_data_processing(manager, size_name, size_bytes))

    # Results and recommendations
    print("\n\n🏁 FINAL RESULTS & ANALYSIS")
    print("=" * 60)

    print_category_results(all_results, "caching")
    print_category_results(all_results, "pooling")
    print_category_results(all_results, "unified")

    print_recommendations(all_results)

    print("\n✅ Refactored benchmarking completed!")
    print("📝 Clean parameter handling with single SmartPool adapter")


if __name__ == "__main__":
    main()
