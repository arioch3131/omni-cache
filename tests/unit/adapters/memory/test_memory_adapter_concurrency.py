"""
Tests for MemoryAdapter thread safety and concurrent operations
including concurrent reads, writes, mixed operations, and concurrent benchmarks.
"""

import threading

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig


class TestMemoryAdapterConcurrency:
    """Tests for thread safety and concurrent operations."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter for testing."""
        config = MemoryAdapterConfig(max_size=200)
        adapter = MemoryAdapter(config)
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_concurrent_set_operations(self, adapter):
        """Test concurrent set operations."""
        num_threads = 10
        items_per_thread = 20

        def worker(thread_id: int):
            for i in range(items_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"
                adapter.set(key, value)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all items were set
        expected_size = num_threads * items_per_thread
        assert adapter.size() == expected_size

    def test_concurrent_get_operations(self, adapter):
        """Test concurrent get operations."""
        # Set up test data
        test_data = {}
        for i in range(50):
            key = f"key_{i}"
            value = f"value_{i}"
            adapter.set(key, value)
            test_data[key] = value

        results = {}
        results_lock = threading.Lock()

        def worker(thread_id: int):
            thread_results = {}
            for key, _ in test_data.items():
                if int(key.split("_")[1]) % 10 == thread_id % 10:
                    result = adapter.get(key)
                    thread_results[key] = result

            with results_lock:
                results.update(thread_results)

        threads = []
        for i in range(10):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify results
        for key, value in results.items():
            assert value == test_data[key]

    def test_concurrent_mixed_operations(self, adapter):
        """Test concurrent mixed operations (set, get, delete)."""
        num_threads = 5
        operations_per_thread = 50

        def worker(thread_id: int):
            for i in range(operations_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                value = f"thread_{thread_id}_value_{i}"

                # Set
                adapter.set(key, value)

                # Get
                result = adapter.get(key)
                assert result == value

                # Delete (some items)
                if i % 3 == 0:
                    adapter.delete(key)

        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Adapter should still be functional
        adapter.set("test", "value")
        assert adapter.get("test") == "value"

    @pytest.mark.slow
    @pytest.mark.concurrent
    def test_concurrent_operations_benchmark(self, performance_timer):
        """Benchmark concurrent operations performance."""
        config = MemoryAdapterConfig(name="concurrent_benchmark", max_size=5000, enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            num_threads = 8
            operations_per_thread = 500
            total_operations = num_threads * operations_per_thread

            def worker(worker_id: int):
                """Worker function for concurrent operations."""
                for i in range(operations_per_thread):
                    key = f"concurrent_key_{worker_id}_{i}"
                    value = {"worker": worker_id, "iteration": i}

                    # Mix of operations
                    if i % 3 == 0:
                        adapter.set(key, value)
                    elif i % 3 == 1:
                        adapter.get(key)
                    else:
                        adapter.exists(key)

            # Run concurrent benchmark
            with performance_timer() as timer:
                threads = []
                for i in range(num_threads):
                    thread = threading.Thread(target=worker, args=(i,))
                    threads.append(thread)
                    thread.start()

                for thread in threads:
                    thread.join()

            concurrent_time = timer.elapsed
            concurrent_rate = total_operations / concurrent_time

            assert concurrent_rate > 1500, f"Concurrent rate too low: {concurrent_rate:.0f} ops/sec"

            print(f"Concurrent Operations Rate: {concurrent_rate:.0f} ops/sec")
            print(f"Operations per thread: {operations_per_thread}")
            print(f"Number of threads: {num_threads}")

        finally:
            adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
