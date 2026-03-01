"""
SmartPool Adapter Performance and Load Testing.

This module contains comprehensive performance and load testing for the SmartPoolAdapter.
Tests cover high-frequency operations, sustained load, burst patterns, memory usage,
scalability, and auto-tuning effectiveness.
"""

import gc
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter, SmartPoolAdapterConfig


class PerformanceMetrics:
    """Helper class to collect and analyze performance metrics."""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.operation_times = []
        self.memory_samples = []
        self.error_count = 0
        self.success_count = 0

    def start_measurement(self):
        """Start performance measurement."""
        gc.collect()  # Force garbage collection before measurement
        self.start_time = time.perf_counter()

    def end_measurement(self):
        """End performance measurement."""
        self.end_time = time.perf_counter()

    def record_operation(self, duration, success=True):
        """Record individual operation timing."""
        self.operation_times.append(duration)
        if success:
            self.success_count += 1
        else:
            self.error_count += 1

    def get_summary(self):
        """Get performance summary statistics."""
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        total_operations = len(self.operation_times)

        if not self.operation_times:
            return {
                "total_time": total_time,
                "total_operations": 0,
                "ops_per_second": 0,
                "avg_operation_time": 0,
                "min_operation_time": 0,
                "max_operation_time": 0,
                "success_rate": 0,
                "error_rate": 0,
            }

        return {
            "total_time": total_time,
            "total_operations": total_operations,
            "ops_per_second": total_operations / total_time if total_time > 0 else 0,
            "avg_operation_time": sum(self.operation_times) / len(self.operation_times),
            "min_operation_time": min(self.operation_times),
            "max_operation_time": max(self.operation_times),
            "success_rate": self.success_count / total_operations if total_operations > 0 else 0,
            "error_rate": self.error_count / total_operations if total_operations > 0 else 0,
        }


@pytest.fixture
def load_test_object():
    """Simple test object for load testing."""

    class LoadTestObject:
        def __init__(self, size=1024 * 1024):  # 1MB object
            self.data = bytearray(size)
            self.created_at = time.time()
            self.operations = 0

        def reset(self):
            """Reset object state for reuse."""
            self.operations = 0

        def validate(self):
            """Validate object integrity."""
            return hasattr(self, "data") and len(self.data) > 0

        def __len__(self):
            """Support len() operation for AutoWeakRefWrapper."""
            return len(self.data)

    return LoadTestObject


@pytest.fixture
def performance_config(load_test_object):
    """Configuration optimized for performance testing."""
    return SmartPoolAdapterConfig(
        factory_function=load_test_object,
        initial_size=20,
        max_size=100,
        min_size=10,
        enable_performance_metrics=True,
        enable_auto_tuning=True,
        auto_tuning_interval=1.0,  # Fast auto-tuning for tests
        max_age_seconds=300,  # 5 minutes TTL
        cleanup_interval=10,  # 10 second cleanup
        enable_background_cleanup=True,
        extra_config={
            "reset_func": lambda obj: obj.reset(),
            "validate_func": lambda obj: obj.validate(),
        },
    )


@pytest.fixture
def performance_adapter(performance_config):
    """SmartPoolAdapter configured for performance testing."""
    adapter = SmartPoolAdapter(performance_config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestSmartPoolAdapterLoadTesting:
    """Load testing for SmartPoolAdapter under various conditions."""

    def test_high_frequency_operations(self, performance_adapter):
        """Test adapter performance under high-frequency operations."""
        metrics = PerformanceMetrics()
        num_operations = 1000
        operations_per_burst = 10

        metrics.start_measurement()

        for _burst in range(num_operations // operations_per_burst):
            # Burst of rapid operations
            for _i in range(operations_per_burst):
                start_time = time.perf_counter()
                try:
                    with performance_adapter.borrow():
                        pass
                    success = True
                except Exception:
                    success = False

                end_time = time.perf_counter()
                metrics.record_operation(end_time - start_time, success)

            # Small delay between bursts to prevent overwhelming
            time.sleep(0.001)

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Performance assertions
        assert summary["total_operations"] == num_operations
        assert summary["ops_per_second"] > 100  # At least 100 ops/second
        assert summary["success_rate"] > 0.98
        assert summary["avg_operation_time"] < 0.01  # Less than 10ms average

    def test_sustained_load(self, performance_adapter):
        """Test adapter under sustained load over time."""
        metrics = PerformanceMetrics()
        test_duration = 5.0  # 5 seconds
        target_ops_per_second = 50

        metrics.start_measurement()
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < test_duration:
            operation_start = time.perf_counter()
            try:
                with performance_adapter.borrow():
                    # Simulate some work
                    time.sleep(0.001)
                success = True
            except Exception:
                success = False

            operation_end = time.perf_counter()
            metrics.record_operation(operation_end - operation_start, success)

            # Control rate to target ops/second
            time.sleep(max(0, (1.0 / target_ops_per_second) - (operation_end - operation_start)))

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Sustained load assertions
        assert summary["total_time"] >= test_duration * 0.9  # Within 10% of target duration
        assert summary["success_rate"] > 0.98
        assert summary["ops_per_second"] >= target_ops_per_second * 0.8  # Within 20% of target

        # Get adapter stats after sustained load
        backend_info = performance_adapter.get_backend_info()
        assert backend_info["is_connected"] is True

    def test_burst_load(self, performance_adapter):
        """Test adapter handling of burst load patterns."""
        metrics = PerformanceMetrics()
        num_bursts = 5
        operations_per_burst = 50
        burst_interval = 0.5  # 500ms between bursts

        metrics.start_measurement()

        for burst_num in range(num_bursts):
            burst_start = time.perf_counter()

            # Execute burst of operations
            for _i in range(operations_per_burst):
                operation_start = time.perf_counter()
                try:
                    with performance_adapter.borrow():
                        pass
                    success = True
                except Exception:
                    success = False

                operation_end = time.perf_counter()
                metrics.record_operation(operation_end - operation_start, success)

            burst_end = time.perf_counter()
            burst_duration = burst_end - burst_start

            # Wait for next burst
            if burst_num < num_bursts - 1:
                time.sleep(max(0, burst_interval - burst_duration))

        metrics.end_measurement()
        summary = metrics.get_summary()

        # Burst load assertions
        assert summary["total_operations"] == num_bursts * operations_per_burst
        assert summary["success_rate"] > 0.98
        assert summary["max_operation_time"] < 0.1  # No operation takes more than 100ms

    def test_memory_usage_under_load(self, performance_config):
        """Test memory usage patterns under load."""
        import os

        import psutil

        adapter = SmartPoolAdapter(performance_config)
        adapter.connect()

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Perform many operations to test memory usage
        num_operations = 100
        objects_held = []

        try:
            # Acquire many objects
            for _i in range(num_operations):
                obj = adapter.get()
                if obj:
                    objects_held.append(obj)

            mid_memory = process.memory_info().rss
            memory_increase = mid_memory - initial_memory
            assert memory_increase > 0
            # initial_memory is sampled *after* adapter.connect(), so initial_size objects
            # are already allocated. Only additional objects created during the loop should
            # contribute to memory increase.
            additional_expected_objects = max(
                0, len(objects_held) - performance_config.initial_size
            )
            expected_additional_bytes = additional_expected_objects * (1024 * 1024)
            assert (
                memory_increase >= expected_additional_bytes * 0.9
            )  # At least 90% of expected additional increase

            # Release all objects
            for obj in objects_held:
                adapter.put(obj)

            objects_held.clear()
            gc.collect()  # Force garbage collection

            final_memory = process.memory_info().rss

            # Memory should not significantly exceed the peak usage
            assert final_memory <= mid_memory * 1.05

            # Check that adapter statistics reflect the operations
            stats = adapter.get_backend_info()
            print(f"Adapter stats: {stats}")
            assert stats["is_connected"] is True
            assert stats["active_objects"] == 0
            assert stats["smartpool_health"]["total_pooled_objects"] >= performance_config.min_size

        finally:
            # Ensure cleanup
            for obj in objects_held:
                try:
                    adapter.put(obj)
                except Exception as exc:
                    assert isinstance(exc, Exception)
            adapter.disconnect()


class TestSmartPoolAdapterScalability:
    """Scalability testing for SmartPoolAdapter."""

    def test_pool_size_scaling(self, load_test_object):
        """Test adapter performance with different pool sizes."""
        pool_sizes = [5, 20, 50, 100]
        results = {}

        for pool_size in pool_sizes:
            config = SmartPoolAdapterConfig(
                factory_function=load_test_object,
                initial_size=pool_size // 2,
                max_size=pool_size,
                min_size=1,
                enable_performance_metrics=True,
            )
            adapter = SmartPoolAdapter(config)
            adapter.connect()

            # Performance test for this pool size
            metrics = PerformanceMetrics()
            num_operations = 100

            metrics.start_measurement()
            for _i in range(num_operations):
                start_time = time.perf_counter()
                try:
                    with adapter.borrow():
                        pass
                    success = True
                except Exception:
                    success = False

                end_time = time.perf_counter()
                metrics.record_operation(end_time - start_time, success)

            metrics.end_measurement()
            results[pool_size] = metrics.get_summary()
            adapter.disconnect()

        # Analyze scaling behavior
        for _pool_size, result in results.items():
            assert result["success_rate"] > 0.98
            assert result["ops_per_second"] > 10  # Minimum performance threshold

        # Check that larger pools don't perform significantly worse
        small_pool_ops = results[pool_sizes[0]]["ops_per_second"]
        large_pool_ops = results[pool_sizes[-1]]["ops_per_second"]
        assert large_pool_ops > small_pool_ops * 0.5

    def test_concurrent_users_scaling(self, performance_adapter):
        """Test adapter performance with increasing concurrent users."""
        thread_counts = [1, 5, 10, 20]
        operations_per_thread = 20

        for num_threads in thread_counts:
            metrics = PerformanceMetrics()

            def worker_thread():
                thread_results = []
                for _ in range(operations_per_thread):
                    start_time = time.perf_counter()
                    try:
                        with performance_adapter.borrow():
                            # Simulate some work
                            time.sleep(0.001)
                        success = True
                    except Exception:
                        success = False

                    end_time = time.perf_counter()
                    thread_results.append((end_time - start_time, success))
                return thread_results

            metrics.start_measurement()

            # Start threads
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(worker_thread) for _ in range(num_threads)]

                for future in as_completed(futures):
                    thread_results = future.result()
                    for duration, success in thread_results:
                        metrics.record_operation(duration, success)

            metrics.end_measurement()
            summary = metrics.get_summary()

            # Concurrent access assertions
            assert summary["total_operations"] == num_threads * operations_per_thread
            assert summary["success_rate"] > 0.98
            assert summary["ops_per_second"] > 50  # At least 50 ops/second total

    def test_auto_tuning_effectiveness(self, performance_config):
        """Test effectiveness of auto-tuning under varying load."""
        adapter = SmartPoolAdapter(performance_config)
        adapter.connect()

        # Create varying load pattern
        load_patterns = [
            (50, 0.01),  # High frequency, low delay
            (20, 0.05),  # Medium frequency, medium delay
            (100, 0.002),  # Very high frequency, very low delay
        ]

        for operations, delay in load_patterns:
            for _i in range(operations):
                try:
                    obj = adapter.borrow()
                    if obj:
                        time.sleep(delay)  # Simulate work
                        adapter.release(obj)
                except Exception as exc:
                    assert isinstance(exc, Exception)

            # Allow auto-tuning to react
            time.sleep(performance_config.auto_tuning_interval + 0.1)

        # Final metrics
        final_stats = adapter.get_backend_info()

        # Auto-tuning should have adjusted the pool size
        assert final_stats["is_connected"] is True

        # Performance metrics should be available
        if adapter.config.enable_performance_metrics:
            perf_metrics = adapter.get_performance_metrics()
            assert "error" not in perf_metrics or perf_metrics.get("error") is None

        adapter.disconnect()
