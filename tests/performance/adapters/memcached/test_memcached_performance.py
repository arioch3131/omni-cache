"""
Performance tests for Memcached adapter with a real Memcached instance.

These tests focus on throughput, latency, and concurrent workload stability.
"""

import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

try:
    from omni_cache.adapters.memcached import MemcachedAdapter, MemcachedAdapterConfig

    HAS_MEMCACHED = True
except ImportError:
    HAS_MEMCACHED = False
    MemcachedAdapter = None
    MemcachedAdapterConfig = None

# Skip by default unless slow tests are requested.
pytestmark = pytest.mark.slow


class TestMemcachedAdapterPerformance:
    """Performance and concurrency tests against a live Memcached server."""

    @pytest.fixture
    def performance_config(self):
        """Config tuned for performance scenarios."""
        return MemcachedAdapterConfig(
            host="localhost",
            port=11211,
            key_prefix="performance_test",
            key_separator=":",
            connect_timeout=2.0,
            timeout=2.0,
            default_ttl=120,
            serialization_method="json",
            retry_on_error=True,
            max_retries=2,
        )

    @pytest.fixture
    def performance_adapter(self, performance_config):
        """Connected Memcached adapter for performance tests."""
        if not HAS_MEMCACHED:
            pytest.skip("Memcached dependency not available")

        adapter = MemcachedAdapter(performance_config)

        try:
            if not adapter.connect():
                pytest.skip("Cannot connect to Memcached server at localhost:11211")
            adapter.clear()
            yield adapter
        except Exception as error:  # pylint: disable=broad-exception-caught
            pytest.skip(f"Memcached server not available: {error}")
        finally:
            if adapter.is_connected():
                adapter.clear()
                adapter.disconnect()

    @pytest.mark.integration
    def test_bulk_set_get_throughput(self, performance_adapter):
        """Validate bulk set/get throughput on a real Memcached server."""
        adapter = performance_adapter
        operation_count = 2000

        start_set = time.perf_counter()
        for index in range(operation_count):
            assert adapter.set(f"bulk:{index}", {"value": index}) is True
        set_duration = time.perf_counter() - start_set

        start_get = time.perf_counter()
        for index in range(operation_count):
            assert adapter.get(f"bulk:{index}") == {"value": index}
        get_duration = time.perf_counter() - start_get

        set_rate = operation_count / set_duration
        get_rate = operation_count / get_duration

        # Conservative thresholds to avoid flaky failures on slower environments.
        assert set_rate > 100
        assert get_rate > 150

    @pytest.mark.integration
    def test_batch_operations_throughput(self, performance_adapter):
        """Validate set_many/get_many/delete_many throughput and correctness."""
        adapter = performance_adapter
        batch_size = 500
        payload = {f"batch:{index}": {"index": index} for index in range(batch_size)}
        keys = list(payload.keys())

        start_set_many = time.perf_counter()
        set_result = adapter.set_many(payload)
        set_many_duration = time.perf_counter() - start_set_many

        start_get_many = time.perf_counter()
        get_result = adapter.get_many(keys)
        get_many_duration = time.perf_counter() - start_get_many

        start_delete_many = time.perf_counter()
        delete_result = adapter.delete_many(keys)
        delete_many_duration = time.perf_counter() - start_delete_many

        assert all(set_result.values())
        assert get_result == payload
        assert all(delete_result.values())

        assert (batch_size / set_many_duration) > 100
        assert (batch_size / get_many_duration) > 100
        assert (batch_size / delete_many_duration) > 100

    @pytest.mark.integration
    def test_get_latency_distribution(self, performance_adapter):
        """Validate latency distribution for hot-key read access."""
        adapter = performance_adapter
        key_count = 1000
        sample_count = 3000

        for index in range(key_count):
            assert adapter.set(f"latency:{index}", {"index": index}) is True

        latencies = []
        for index in range(sample_count):
            key = f"latency:{index % key_count}"
            start_time = time.perf_counter()
            value = adapter.get(key)
            latencies.append(time.perf_counter() - start_time)
            assert value is not None

        average_latency = statistics.mean(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        assert average_latency < 0.01
        assert p95_latency < 0.03

    @pytest.mark.integration
    def test_concurrent_mixed_workload_stability(self):
        """Validate concurrent mixed workload using one Memcached connection per worker."""
        if not HAS_MEMCACHED:
            pytest.skip("Memcached dependency not available")

        worker_count = 8
        operations_per_worker = 300
        errors = []
        lock = threading.Lock()
        adapters = []

        for worker_id in range(worker_count):
            adapter = MemcachedAdapter(
                MemcachedAdapterConfig(
                    host="localhost",
                    port=11211,
                    key_prefix=f"performance_concurrent:{worker_id}",
                    connect_timeout=2.0,
                    timeout=2.0,
                    default_ttl=120,
                    serialization_method="json",
                )
            )

            if not adapter.connect():
                for connected_adapter in adapters:
                    connected_adapter.disconnect()
                pytest.skip("Cannot create concurrent Memcached connections")

            adapters.append(adapter)

        def worker(worker_id: int) -> int:
            adapter = adapters[worker_id]
            operations_done = 0

            for index in range(operations_per_worker):
                key = f"key:{index}"
                value = {"worker": worker_id, "index": index}

                assert adapter.set(key, value) is True
                operations_done += 1

                read_value = adapter.get(key)
                assert read_value == value
                operations_done += 1

                if index % 4 == 0:
                    adapter.delete(key)
                    operations_done += 1

            return operations_done

        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(worker, worker_id) for worker_id in range(worker_count)]

            total_operations = 0
            for future in as_completed(futures):
                try:
                    total_operations += future.result()
                except Exception as error:  # pylint: disable=broad-exception-caught
                    with lock:
                        errors.append(error)

        total_duration = time.perf_counter() - start_time

        for adapter in adapters:
            adapter.clear()
            adapter.disconnect()

        assert errors == []
        assert total_duration > 0

        operations_per_second = total_operations / total_duration
        assert operations_per_second > 200
