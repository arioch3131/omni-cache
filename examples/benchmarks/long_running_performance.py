"""
Example 09 PROPRE: Long-Running Performance Tests.

SEULEMENT les imports standards omni-cache - aucun import artificiel !
"""

import gc
import random
import string
import time
from collections.abc import Callable
from typing import Any

import psutil

from omni_cache import create_adapter, setup
from omni_cache.core.interfaces import CacheBackend

# --- Configuration ---
TEST_DURATION_SECONDS = 60  # Run tests for 1 minutes
REPORT_INTERVAL_SECONDS = 30  # Report every 30 seconds
ITERATIONS_PER_REPORT = 1000  # Number of operations between reports


# --- Helper Functions ---
def generate_random_string(length: int) -> str:
    """Generates a random string of specified length."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


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


class PooledData:
    def __init__(self, initial_data: dict[str, Any]):
        self._internal_data = initial_data  # Store the actual data
        self.data = self._internal_data  # Provide a 'data' attribute

    def __getitem__(self, key):
        return self._internal_data[key]

    def __setitem__(self, key, value):
        self._internal_data[key] = value

    def get(self, key, default=None):
        return self._internal_data.get(key, default)

    def keys(self):
        return self._internal_data.keys()


def smartpool_borrow_release(adapter: Any) -> Callable[[str, Any], None]:
    """Helper function to borrow and release an object from SmartPool."""

    def _operation(key: str, value: Any):
        my_key_num = int(key[28:]) % int(key[-1]) if int(key[-1]) != 0 else 0
        with adapter.borrow("key" + str(my_key_num)) as obj:
            # Simuler une opération sur l'objet
            if hasattr(obj, "data"):
                obj.data = value  # [:100] if isinstance(value, str) else str(value)[:100]

    return _operation


def run_long_benchmark(
    adapter_name: str,
    adapter_instance: Any,
    operation: Callable[[str, Any], None],
    data_generator: Callable[[], Any],
    duration_seconds: int,
    report_interval_seconds: int,
    iterations_per_report: int,
    memory_monitor: MemoryMonitor,
    key_space_size: int | None = None,
) -> None:
    """Runs a benchmark for a given adapter for an extended duration."""
    key_mode = f"bounded keyspace={key_space_size}" if key_space_size else "unbounded keys"
    header = (
        f"\n--- Running long-term benchmark for {adapter_name} "
        f"({duration_seconds}s, {key_mode}) ---"
    )
    print(header)
    start_test_time = time.time()
    last_report_time = time.time()
    total_operations = 0
    total_duration = 0.0

    memory_monitor.start()

    while (time.time() - start_test_time) < duration_seconds:
        iter_start_time = time.perf_counter()
        for i in range(iterations_per_report):
            key_index = total_operations + i
            if key_space_size and key_space_size > 0:
                key_index %= key_space_size
            key = f"long_test_{adapter_name}_{key_index}"
            data = data_generator()
            operation(key, data)
        iter_end_time = time.perf_counter()

        total_operations += iterations_per_report
        total_duration += iter_end_time - iter_start_time
        memory_monitor.update()

        if (time.time() - last_report_time) >= report_interval_seconds:
            elapsed_seconds = time.time() - start_test_time
            elapsed_minutes = elapsed_seconds / 60.0 if elapsed_seconds > 0 else 0.0
            avg_time_ms = (total_duration / total_operations) * 1000 if total_operations > 0 else 0
            ops_per_sec = total_operations / elapsed_seconds if elapsed_seconds > 0 else 0
            mem_stats = memory_monitor.get_stats()
            mem_growth_mb_min = (
                mem_stats["delta_mb"] / elapsed_minutes if elapsed_minutes > 0 else 0.0
            )

            print(
                f"[{int(time.time() - start_test_time)}s] {adapter_name}: "
                f"Avg: {avg_time_ms:.2f}ms, Throughput: {ops_per_sec:.1f} ops/sec, "
                f"Mem Peak: {mem_stats['peak_mb']:.1f}MB, "
                f"Mem Delta: {mem_stats['delta_mb']:.1f}MB, "
                f"Mem Growth: {mem_growth_mb_min:.1f}MB/min"
            )
            last_report_time = time.time()

    elapsed_seconds = time.time() - start_test_time
    elapsed_minutes = elapsed_seconds / 60.0 if elapsed_seconds > 0 else 0.0
    final_avg_time_ms = (total_duration / total_operations) * 1000 if total_operations > 0 else 0
    final_ops_per_sec = total_operations / elapsed_seconds if elapsed_seconds > 0 else 0
    final_mem_stats = memory_monitor.get_stats()
    final_mem_growth_mb_min = (
        final_mem_stats["delta_mb"] / elapsed_minutes if elapsed_minutes > 0 else 0.0
    )

    print(f"\n--- {adapter_name} Final Results ---")
    print(f"Total Operations: {total_operations}")
    print(f"Average Time: {final_avg_time_ms:.2f}ms")
    print(f"Overall Throughput: {final_ops_per_sec:.1f} ops/sec")
    print(f"Final Memory Peak: {final_mem_stats['peak_mb']:.1f}MB")
    print(f"Final Memory Delta: {final_mem_stats['delta_mb']:.1f}MB")
    print(f"Final Memory Growth: {final_mem_growth_mb_min:.1f}MB/min")

    # Clear adapter for next test - SAUF pour SmartPool
    if adapter_name == "smartpool_objects":
        # adapter_instance.disconnect()
        print("Disable for smartpool to get statistics")
    elif hasattr(adapter_instance, "clear"):
        adapter_instance.clear()
    elif hasattr(adapter_instance, "disconnect"):
        adapter_instance.disconnect()


def main():
    print("🚀 Omni-Cache Long-Running Performance Benchmarking (Version PROPRE)")
    print("=" * 70)

    # --- Setup Adapters ---
    print("🔧 Setting up adapters...")

    # Use the setup() function to initialize the CacheManager
    manager = setup(log_level="WARNING")  # RÉDUIRE le niveau de logs

    # Get the default memory adapter
    memory_adapter = manager.get_adapter("memory")
    memory_bounded_adapter = create_adapter(
        CacheBackend.MEMORY,
        {
            "name": "memory_bounded",
            "max_size": 20_000,
            "eviction_policy": "lru",
            "enable_stats": True,
        },
    )
    manager.register_adapter("memory_bounded", memory_bounded_adapter)

    # Redis Adapter
    redis_adapter = None
    try:
        redis_adapter = create_adapter(
            CacheBackend.REDIS,
            {
                "name": "redis",
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "socket_timeout": 5.0,
                "connection_pool_max_connections": 20,
                "enable_stats": True,
            },
        )
        manager.register_adapter("redis", redis_adapter)
        if redis_adapter.is_connected():
            print("✅ Redis adapter configured and connected")
        else:
            raise Exception("Redis adapter failed to connect.")
    except Exception as e:
        print(f"❌ Could not connect to Redis: {e}. Redis benchmarks will be skipped.")
        redis_adapter = None

    # Memcached Adapter
    memcached_adapter = None
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
        manager.register_adapter("memcached", memcached_adapter)
        if memcached_adapter.is_connected():
            print("✅ Memcached adapter configured and connected")
        else:
            raise Exception("Memcached adapter failed to connect.")
    except Exception as e:
        print(f"❌ Could not connect to Memcached: {e}. Memcached benchmarks will be skipped.")
        memcached_adapter = None

    # SmartPool Adapter - SYNTAXE PROPRE
    smartpool_adapter = None
    try:
        # Factory function simple
        def create_simple_data_object(key: str | None = None):
            """Factory function qui crée des objets de données simples."""
            initial_data = {
                "data": generate_random_string(1024),
                "timestamp": time.time(),
                "id": random.randint(1, 1000000),
            }
            return PooledData(initial_data)

        def validate_data(obj: Any):
            return (
                obj.get("id", 0) >= 1
                and obj.get("id", 0) < 1000000
                and len(obj.get("data", "")) == 1024
            )

        # Configuration dict simple
        smartpool_config = {
            "name": "smartpool_objects",
            "factory_function": create_simple_data_object,
            "factory_validate_function": validate_data,
            "initial_size": 2,
            "min_size": 2,
            "max_size": ITERATIONS_PER_REPORT,
            "enable_auto_tuning": True,
            "enable_performance_metrics": True,
            "memory_preset": "HIGH_THROUGHPUT",
            "backend": CacheBackend.SMARTPOOL.value,
        }

        # Create adapter avec la fonction standard
        smartpool_adapter = create_adapter(CacheBackend.SMARTPOOL, smartpool_config)
        manager.register_adapter("smartpool_objects", smartpool_adapter)

        # Test de connexion
        if smartpool_adapter.connect() and smartpool_adapter.is_connected():
            print("✅ SmartPool adapter configured successfully")
            print(f"    - Auto-tuning: {smartpool_config.get('enable_auto_tuning', False)}")
            print(f"    - Memory preset: {smartpool_config.get('memory_preset', 'None')}")
        else:
            raise Exception("SmartPool adapter failed to connect.")

    except Exception as e:
        print(f"❌ SmartPool not available: {e}. SmartPool benchmarks will be skipped.")
        smartpool_adapter = None

    print("✅ Adapters configured successfully")

    print("\nStarting long-running performance tests...")
    print("=" * 60)

    memory_monitor = MemoryMonitor()

    # Run benchmarks for each adapter
    if memory_adapter:
        run_long_benchmark(
            "memory",
            memory_adapter,
            lambda k, v: memory_adapter.set(k, v),
            lambda: generate_random_string(1024),  # 1KB data
            TEST_DURATION_SECONDS,
            REPORT_INTERVAL_SECONDS,
            ITERATIONS_PER_REPORT,
            memory_monitor,
            key_space_size=None,
        )

    if memory_bounded_adapter:
        run_long_benchmark(
            "memory_bounded",
            memory_bounded_adapter,
            lambda k, v: memory_bounded_adapter.set(k, v),
            lambda: generate_random_string(1024),  # 1KB data
            TEST_DURATION_SECONDS,
            REPORT_INTERVAL_SECONDS,
            ITERATIONS_PER_REPORT,
            memory_monitor,
            key_space_size=20_000,
        )

    if redis_adapter:
        run_long_benchmark(
            "redis",
            redis_adapter,
            lambda k, v: redis_adapter.set(k, v),
            lambda: generate_random_string(1024),  # 1KB data
            TEST_DURATION_SECONDS,
            REPORT_INTERVAL_SECONDS,
            ITERATIONS_PER_REPORT,
            memory_monitor,
            key_space_size=None,
        )

    if memcached_adapter:
        run_long_benchmark(
            "memcached",
            memcached_adapter,
            lambda k, v: memcached_adapter.set(k, v),
            lambda: generate_random_string(1024),  # 1KB data
            TEST_DURATION_SECONDS,
            REPORT_INTERVAL_SECONDS,
            ITERATIONS_PER_REPORT,
            memory_monitor,
            key_space_size=None,
        )

    # SmartPool simplifié
    if smartpool_adapter:
        run_long_benchmark(
            "smartpool_objects",
            smartpool_adapter,
            smartpool_borrow_release(smartpool_adapter),
            lambda: generate_random_string(1024),
            TEST_DURATION_SECONDS,
            REPORT_INTERVAL_SECONDS,
            ITERATIONS_PER_REPORT,
            memory_monitor,
            key_space_size=ITERATIONS_PER_REPORT,
        )

    print("\n✅ All long-running tests completed!")

    # # Test final du health check
    if smartpool_adapter:
        print("\n🔍 Warming up pool before health check...")
        # Faire quelques opérations pour générer des statistiques
        for i in range(5):
            try:
                with smartpool_adapter.borrow() as obj:
                    if hasattr(obj, "data"):
                        obj.data = f"warmup_{i}"
                print(f"Warmup operation {i}: ✅ Success")
            except Exception as e:
                print(f"Warmup operation {i} failed: {e}")

        print("🔍 Testing health check...")
        is_healthy = smartpool_adapter.health_check()
        print(f"SmartPool health status: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")

        # Statistiques finales détaillées
        print("\n📊 Final SmartPool Statistics:")
        backend_info = smartpool_adapter.get_backend_info()

        print("Pool Status:")
        print(f"  - Connection State: {backend_info.get('state', 'Unknown')}")
        print(f"  - Health Status: {backend_info.get('pool_health_status', 'Unknown')}")
        print(f"  - Current Pool Size: {backend_info.get('current_size', 'N/A')}")
        print(f"  - Active Objects: {backend_info.get('active_objects', 'N/A')}")
        print(f"  - Total Objects: {backend_info.get('total_objects', 'N/A')}")
        print(f"  - Hit Rate: {backend_info.get('hit_rate', 0):.1%}")

        print("Configuration:")
        print(f"  - Max Size: {backend_info.get('max_size', 'N/A')}")
        print(f"  - Initial Size: {backend_info.get('initial_size', 'N/A')}")
        print(f"  - Memory Preset: {backend_info.get('memory_preset', 'N/A')}")
        print(f"  - Auto-tuning: {backend_info.get('auto_tuning_enabled', 'N/A')}")

        # Statistiques détaillées si disponibles
        if hasattr(smartpool_adapter, "get_detailed_smartpool_stats"):
            try:
                detailed_stats = smartpool_adapter.get_detailed_smartpool_stats()
                print(f"Detailed stats: {detailed_stats}")
                if "computed_metrics" in detailed_stats:
                    metrics = detailed_stats["computed_metrics"]
                    print("Performance Metrics:")
                    print(f"  - Total Requests: {metrics.get('total_requests', 'N/A')}")
                    print(f"  - Reuse Efficiency: {metrics.get('reuse_efficiency', 0):.2f}")
                    print(f"  - Pool Utilization: {metrics.get('pool_utilization', 0):.1%}")
            except Exception as e:
                print(f"  ⚠️ Could not get detailed stats: {e}")

        # Afficher les stats brutes SmartPool
        if "smartpool_stats" in backend_info:
            stats = backend_info["smartpool_stats"]
            print(stats)
            print("Raw SmartPool Stats:")
            print(f"  - Creates: {stats.get('creates', 0)}")
            print(f"  - Hits: {stats.get('hits', 0)}")
            print(f"  - Misses: {stats.get('misses', 0)}")
            print(f"  - Reuses: {stats.get('reuses', 0)}")

        dashboard = smartpool_adapter.get_dashboard_summary()
        print(f"Dashboard: {dashboard}")


if __name__ == "__main__":
    main()
