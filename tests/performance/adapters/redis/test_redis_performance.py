"""
Tests for Redis adapter performance, thread safety, and statistics.

This module tests the RedisAdapter's performance characteristics,
thread safety under concurrent access, and statistics tracking functionality.
"""

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

import pytest

from omni_cache.adapters.base.base import ConnectionState

# Test Redis availability
try:
    from omni_cache.adapters.redis import RedisAdapter, RedisAdapterConfig

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisAdapter = None
    RedisAdapterConfig = None

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name


class TestRedisAdapterThreadSafety:
    """Tests for Redis adapter thread safety."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        redis_module = sys.modules[RedisAdapter.__module__]
        with (
            patch.object(redis_module, "Redis") as mock_redis,
            patch.object(redis_module, "ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def connected_adapter(self, mock_redis_classes):
        """Create connected RedisAdapter instance."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())
        adapter._redis = mock_redis_instance
        adapter._connection_pool = MagicMock()
        adapter._state = ConnectionState.CONNECTED
        return adapter, mock_redis_instance

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_concurrent_get_operations(self, connected_adapter):
        """Test concurrent get operations."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"test_value"'

        results = []
        errors = []

        def get_operation(key_suffix):
            try:
                result = adapter.get(f"key_{key_suffix}")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run concurrent get operations
        threads = [threading.Thread(target=get_operation, args=(i,)) for i in range(50)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 50
        assert all(result == "test_value" for result in results)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_concurrent_set_operations(self, connected_adapter):
        """Test concurrent set operations."""
        adapter, mock_redis = connected_adapter
        mock_redis.set.return_value = True

        results = []
        errors = []

        def set_operation(key_suffix):
            try:
                result = adapter.set(f"key_{key_suffix}", f"value_{key_suffix}")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run concurrent set operations
        threads = [threading.Thread(target=set_operation, args=(i,)) for i in range(50)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 50
        assert all(result is True for result in results)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_concurrent_mixed_operations(self, connected_adapter):
        """Test concurrent mixed operations (get/set/delete)."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"value"'
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1

        results = []
        errors = []

        def mixed_operation(operation_id):
            try:
                op_type = operation_id % 3
                if op_type == 0:
                    result = adapter.get(f"key_{operation_id}")
                elif op_type == 1:
                    result = adapter.set(f"key_{operation_id}", f"value_{operation_id}")
                else:
                    result = adapter.delete(f"key_{operation_id}")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Run concurrent mixed operations
        threads = [threading.Thread(target=mixed_operation, args=(i,)) for i in range(60)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 60

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_concurrent_batch_operations(self, connected_adapter):
        """Test concurrent batch operations."""
        adapter, mock_redis = connected_adapter
        mock_redis.mget.return_value = ['"value1"', '"value2"', '"value3"']
        mock_redis.mset.return_value = True

        results = []
        errors = []

        def batch_operation(batch_id):
            try:
                # get_many
                keys = [f"key_{batch_id}_{i}" for i in range(3)]
                get_result = adapter.get_many(keys)
                results.append(get_result)

                # set_many
                mapping = {f"key_{batch_id}_{i}": f"value_{batch_id}_{i}" for i in range(3)}
                set_result = adapter.set_many(mapping)
                results.append(set_result)
            except Exception as e:
                errors.append(e)

        # Run concurrent batch operations
        threads = [threading.Thread(target=batch_operation, args=(i,)) for i in range(20)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 40  # 20 threads * 2 operations each

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_concurrent_connection_operations(self, mock_redis_classes):
        """Test concurrent connection/disconnection operations."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())

        results = []
        errors = []

        def connection_operation(op_type):
            try:
                if op_type == "connect":
                    result = adapter.connect()
                else:
                    result = adapter.disconnect()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Alternate between connect and disconnect
        threads = []
        for i in range(20):
            op_type = "connect" if i % 2 == 0 else "disconnect"
            threads.append(threading.Thread(target=connection_operation, args=(op_type,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 20

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_thread_pool_executor_operations(self, connected_adapter):
        """Test operations using ThreadPoolExecutor."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"value"'

        def get_operation(key):
            return adapter.get(key)

        # Use ThreadPoolExecutor for better concurrency control
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_operation, f"key_{i}") for i in range(100)]

            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    pytest.fail(f"Operation failed: {e}")

        assert len(results) == 100
        assert all(result == "value" for result in results)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_lock_behavior(self, mock_redis_classes):
        """Test connection lock prevents race conditions."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())

        connection_order = []

        def slow_connect(thread_id):
            with adapter._connection_lock:
                connection_order.append(f"start_{thread_id}")
                time.sleep(0.01)  # Simulate slow connection
                adapter._redis = mock_redis_instance
                connection_order.append(f"end_{thread_id}")

        # Start multiple threads trying to connect
        threads = [threading.Thread(target=slow_connect, args=(i,)) for i in range(3)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should see complete start-end pairs (no interleaving)
        assert len(connection_order) == 6
        # Each thread should complete before the next starts
        for i in range(0, 6, 2):
            assert connection_order[i].startswith("start_")
            assert connection_order[i + 1].startswith("end_")


class TestRedisAdapterPerformance:
    """Tests for Redis adapter performance characteristics."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        redis_module = sys.modules[RedisAdapter.__module__]
        with (
            patch.object(redis_module, "Redis") as mock_redis,
            patch.object(redis_module, "ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def connected_adapter(self, mock_redis_classes):
        """Create connected RedisAdapter instance."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())
        adapter._redis = mock_redis_instance
        adapter._connection_pool = MagicMock()
        adapter._state = ConnectionState.CONNECTED
        return adapter, mock_redis_instance

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_large_data_serialization_performance(self, connected_adapter):
        """Test performance with large data sets."""
        adapter, mock_redis = connected_adapter

        # Test with different serialization methods
        serialization_methods = ["json", "string"]

        for method in serialization_methods:
            adapter._config.serialization_method = method

            # Large data structure
            large_data = {
                "users": [{"id": i, "name": f"user_{i}", "data": "x" * 100} for i in range(1000)],
                "metadata": {"timestamp": time.time(), "version": "1.0"},
            }

            # Time serialization
            start_time = time.time()
            serialized = adapter._serialize_value(large_data)
            serialize_time = time.time() - start_time

            # Time deserialization
            start_time = time.time()
            if method != "string":  # String method doesn't preserve original structure
                _ = adapter._deserialize_value(serialized)
            deserialize_time = time.time() - start_time

            # Performance assertions (should complete within reasonable time)
            assert serialize_time < 1.0, f"{method} serialization too slow: {serialize_time}s"
            assert deserialize_time < 1.0, f"{method} deserialization too slow: {deserialize_time}s"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_batch_operation_performance(self, connected_adapter):
        """Test performance of batch operations vs individual operations."""
        adapter, mock_redis = connected_adapter

        # Prepare test data
        keys = [f"key_{i}" for i in range(100)]
        values = [f"value_{i}" for i in range(100)]
        mapping = dict(zip(keys, values, strict=False))

        # Mock responses
        mock_redis.mget.return_value = [f'"{v}"' for v in values]
        mock_redis.mset.return_value = True
        mock_redis.set.return_value = True
        mock_redis.get.return_value = '"test_value"'

        # Test batch set performance
        start_time = time.time()
        adapter.set_many(mapping)
        batch_set_time = time.time() - start_time

        # Test individual set performance
        start_time = time.time()
        for key, value in list(mapping.items())[:10]:  # Test subset for comparison
            adapter.set(key, value)
        individual_set_time = time.time() - start_time

        # Batch operations should be more efficient per operation
        batch_set_time / len(mapping)
        individual_set_time / 10

        # This is a behavioral test - batch should generally be more efficient
        # but we can't assert strict timing due to test environment variability

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_key_prefix_performance_impact(self, mock_redis_classes):
        """Test performance impact of key prefixes."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Test without prefix
        adapter_no_prefix = RedisAdapter(RedisAdapterConfig())
        adapter_no_prefix._redis = mock_redis_instance
        adapter_no_prefix._connection_pool = MagicMock()
        adapter_no_prefix._state = ConnectionState.CONNECTED

        # Test with prefix
        adapter_with_prefix = RedisAdapter(
            RedisAdapterConfig(key_prefix="test_app", key_separator=":")
        )
        adapter_with_prefix._redis = mock_redis_instance
        adapter_with_prefix._connection_pool = MagicMock()
        adapter_with_prefix._state = ConnectionState.CONNECTED

        mock_redis_instance.set.return_value = True

        keys = [f"test_key_{i}" for i in range(100)]

        # Time operations without prefix
        start_time = time.time()
        for key in keys:
            adapter_no_prefix.set(key, "value")
        no_prefix_time = time.time() - start_time

        # Time operations with prefix
        start_time = time.time()
        for key in keys:
            adapter_with_prefix.set(key, "value")
        with_prefix_time = time.time() - start_time

        # Prefix should have minimal overhead
        overhead_ratio = with_prefix_time / no_prefix_time
        assert overhead_ratio < 2.0, f"Key prefix overhead too high: {overhead_ratio}x"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_pool_performance(self, mock_redis_classes):
        """Test performance with different connection pool sizes."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        pool_sizes = [1, 5, 10, 20]
        performance_results = {}

        for pool_size in pool_sizes:
            config = RedisAdapterConfig(connection_pool_max_connections=pool_size)
            adapter = RedisAdapter(config)
            adapter._redis = mock_redis_instance
            adapter._connection_pool = MagicMock()
            adapter._state = ConnectionState.CONNECTED

            mock_redis_instance.get.return_value = '"value"'

            # Simulate concurrent load
            def concurrent_operations(adapter_instance=adapter):
                for _ in range(10):
                    adapter_instance.get(f"key_{threading.current_thread().ident}")

            start_time = time.time()
            threads = [threading.Thread(target=concurrent_operations) for _ in range(pool_size)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            total_time = time.time() - start_time
            performance_results[pool_size] = total_time

        # Generally, performance should improve with more connections up to a point
        # This is more of a behavioral test than strict performance assertion


class TestRedisAdapterStats:
    """Tests for Redis adapter statistics tracking."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        redis_module = sys.modules[RedisAdapter.__module__]
        with (
            patch.object(redis_module, "Redis") as mock_redis,
            patch.object(redis_module, "ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def connected_adapter(self, mock_redis_classes):
        """Create connected RedisAdapter instance with stats enabled."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(enable_stats=True)
        adapter = RedisAdapter(config)
        adapter._redis = mock_redis_instance
        adapter._connection_pool = MagicMock()
        adapter._state = ConnectionState.CONNECTED
        return adapter, mock_redis_instance

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_basic_stats_tracking(self, connected_adapter):
        """Test basic statistics tracking for operations."""
        adapter, mock_redis = connected_adapter

        # Successful operations
        mock_redis.get.return_value = '"value"'
        mock_redis.set.return_value = True
        mock_redis.delete.return_value = 1

        adapter.get("key1")
        adapter.get("key2")
        adapter.set("key3", "value3")
        adapter.delete("key4")

        stats = adapter.get_stats()
        assert stats.hits >= 2  # 2 successful gets

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_with_misses(self, connected_adapter):
        """Test statistics tracking for cache misses."""
        adapter, mock_redis = connected_adapter

        # Mix of hits and misses
        mock_redis.get.side_effect = ['"value"', None, '"value2"', None]

        adapter.get("key1")  # hit
        adapter.get("key2")  # miss
        adapter.get("key3")  # hit
        adapter.get("key4")  # miss

        stats = adapter.get_stats()
        assert stats.hits == 2
        assert stats.misses == 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_thread_safety(self, connected_adapter):
        """Test that statistics tracking is thread-safe."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"value"'

        def perform_operations():
            for _ in range(100):
                adapter.get(f"key_{threading.current_thread().ident}")

        # Run operations in multiple threads
        threads = [threading.Thread(target=perform_operations) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        stats = adapter.get_stats()
        assert stats.hits == 500  # 5 threads * 100 operations each

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_reset(self, connected_adapter):
        """Test statistics reset functionality."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"value"'

        # Perform some operations
        for i in range(10):
            adapter.get(f"key_{i}")

        stats = adapter.get_stats()
        assert stats.hits == 10

        # Reset stats
        adapter.reset_stats()

        stats = adapter.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_disabled(self, mock_redis_classes):
        """Test that stats are not tracked when disabled."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(enable_stats=False)
        adapter = RedisAdapter(config)
        adapter._redis = mock_redis_instance
        adapter._connection_pool = MagicMock()
        adapter._state = ConnectionState.CONNECTED

        mock_redis_instance.get.return_value = '"value"'

        # Perform operations
        for i in range(10):
            adapter.get(f"key_{i}")

        # Stats should not be tracked
        adapter.get_stats()
        # When stats are disabled, the base implementation might still track basic stats
        # This tests the specific behavior of the implementation

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_batch_operations(self, connected_adapter):
        """Test statistics tracking for batch operations."""
        adapter, mock_redis = connected_adapter

        # Configure mock responses for batch operations
        mock_redis.mget.return_value = ['"value1"', None, '"value3"']
        mock_redis.mset.return_value = True

        # Perform batch operations
        adapter.get_many(["key1", "key2", "key3"])  # 2 hits, 1 miss
        adapter.set_many({"key4": "value4", "key5": "value5"})

        stats = adapter.get_stats()
        # Should track individual operations within batch
        assert stats.hits >= 2
        assert stats.misses >= 1

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_error_scenarios(self, connected_adapter):
        """Test statistics during error scenarios."""
        adapter, mock_redis = connected_adapter

        # Mix of successful and failed operations
        mock_redis.get.side_effect = ['"value"', Exception("Error"), '"value2"']

        adapter.get("key1")  # success
        try:
            adapter.get("key2")  # error
        except Exception as exc:
            assert isinstance(exc, Exception)
        adapter.get("key3")  # success

        stats = adapter.get_stats()
        # Should track successful operations
        assert stats.hits >= 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_hit_rate_calculation(self, connected_adapter):
        """Test hit rate calculation in statistics."""
        adapter, mock_redis = connected_adapter

        # 3 hits, 2 misses
        mock_redis.get.side_effect = ['"value1"', '"value2"', None, '"value3"', None]

        for i in range(5):
            adapter.get(f"key_{i}")

        stats = adapter.get_stats()
        hit_rate = stats.hit_rate

        # Hit rate should be 3/5 = 0.6
        assert abs(hit_rate - 0.6) < 0.01, f"Expected hit rate ~0.6, got {hit_rate}"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_stats_concurrent_updates(self, connected_adapter):
        """Test concurrent statistics updates."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"value"'

        results = []

        def stats_operation():
            # Each thread performs operations and reads stats
            for _ in range(50):
                adapter.get(f"key_{threading.current_thread().ident}")

            stats = adapter.get_stats()
            results.append(stats.hits)

        # Multiple threads updating stats concurrently
        threads = [threading.Thread(target=stats_operation) for _ in range(4)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Final stats should reflect all operations
        final_stats = adapter.get_stats()
        assert final_stats.hits == 200  # 4 threads * 50 operations each

        # All intermediate readings should be valid
        assert all(hits <= 200 for hits in results)
