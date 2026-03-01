"""
Integration tests for Redis adapter with real Redis instances.

This module contains integration tests that require a running Redis server.
Tests verify real-world behavior, data persistence, and actual Redis
interactions without mocking.

Requirements:
- Running Redis server (default: localhost:6379)
- Redis database 15 reserved for testing
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

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


class TestRedisAdapterIntegration:
    """Integration tests with real Redis server."""

    @pytest.fixture
    def real_redis_config(self):
        """Configuration for real Redis testing."""
        return RedisAdapterConfig(
            host="localhost",
            port=6379,
            db=15,  # Use database 15 for testing to avoid conflicts
            key_prefix="integration_test",
            key_separator=":",
            connection_timeout=5.0,
            socket_timeout=3.0,
        )

    @pytest.fixture
    def real_adapter(self, real_redis_config):
        """Create RedisAdapter with real Redis connection."""
        adapter = RedisAdapter(real_redis_config)

        try:
            if adapter.connect():
                # Clean up any existing test data
                adapter.clear()
                yield adapter
                # Clean up after test
                adapter.clear()
                adapter.disconnect()
            else:
                pytest.skip("Cannot connect to Redis server at localhost:6379")
        except Exception as e:
            pytest.skip(f"Redis server not available: {e}")

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_connection_and_ping(self, real_adapter):
        """Test real connection and ping with Redis server."""
        assert real_adapter.is_connected()
        assert real_adapter.ping()

        # Test health check
        health_result = real_adapter.health_check()
        assert health_result is True

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_basic_operations(self, real_adapter):
        """Test basic CRUD operations with real Redis."""
        # Test set and get
        assert real_adapter.set("test_key", "test_value") is True
        assert real_adapter.get("test_key") == "test_value"

        # Test exists
        assert real_adapter.exists("test_key") is True
        assert real_adapter.exists("nonexistent_key") is False

        # Test delete
        assert real_adapter.delete("test_key") is True
        assert real_adapter.get("test_key") is None
        assert real_adapter.exists("test_key") is False

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_complex_data_types(self, real_adapter):
        """Test complex data types with real Redis."""
        # Test complex dictionary
        complex_data = {
            "users": [
                {"id": 1, "name": "Alice", "active": True},
                {"id": 2, "name": "Bob", "active": False},
            ],
            "metadata": {
                "version": "1.0",
                "timestamp": time.time(),
                "features": ["auth", "caching", "logging"],
            },
            "settings": {"debug": True, "max_connections": 100, "timeout": 30.5},
        }

        assert real_adapter.set("complex_data", complex_data) is True
        retrieved_data = real_adapter.get("complex_data")
        assert retrieved_data == complex_data

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_ttl_operations(self, real_adapter):
        """Test TTL operations with real Redis and time."""
        # Set key with 2 second TTL
        assert real_adapter.set("ttl_key", "expires_soon", ttl=2) is True

        # Key should exist immediately
        assert real_adapter.exists("ttl_key") is True

        # Check TTL is set
        ttl = real_adapter.ttl("ttl_key")
        assert ttl is not None
        assert 0 < ttl <= 2

        # Wait for expiration
        time.sleep(2.5)

        # Key should be expired
        assert real_adapter.get("ttl_key") is None
        assert real_adapter.exists("ttl_key") is False

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_expire_operation(self, real_adapter):
        """Test expire operation with real Redis."""
        # Set key without TTL
        assert real_adapter.set("expire_test", "value") is True

        # Set expiration
        assert real_adapter.expire("expire_test", 1) is True

        # Check TTL
        ttl = real_adapter.ttl("expire_test")
        assert ttl is not None
        assert 0 < ttl <= 1

        # Wait for expiration
        time.sleep(1.5)

        # Key should be expired
        assert real_adapter.get("expire_test") is None

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_increment_operations(self, real_adapter):
        """Test increment operations with real Redis."""
        # Test increment starting from non-existent key
        result = real_adapter.increment("counter")
        assert result == 1

        # Test increment by specific amount
        result = real_adapter.increment("counter", 5)
        assert result == 6

        # Test float increment
        result = real_adapter.increment("float_counter", 2.5)
        assert result == 2.5

        result = real_adapter.increment("float_counter", 1.5)
        assert result == 4.0

        # Test increment on string value (should return None)
        real_adapter.set("string_key", "not_a_number")
        result = real_adapter.increment("string_key")
        assert result is None

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_batch_operations(self, real_adapter):
        """Test batch operations with real Redis."""
        # Prepare test data
        test_data = {f"batch_key_{i}": f"batch_value_{i}" for i in range(10)}

        # Test set_many
        result = real_adapter.set_many(test_data)
        assert len(result) == 10
        assert all(result.values())

        # Test get_many
        keys = list(test_data.keys())
        retrieved = real_adapter.get_many(keys)
        assert len(retrieved) == 10
        assert retrieved == test_data

        # Test delete_many
        delete_keys = keys[:5]
        result = real_adapter.delete_many(delete_keys)
        assert len(result) == 5
        assert all(result.values())  # All deletions successful

        # Verify deletions
        remaining = real_adapter.get_many(keys)
        assert len(remaining) == 10
        for key in delete_keys:
            assert remaining[key] is None
        for key in keys[5:]:
            assert remaining[key] == test_data[key]

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_keys_and_size(self, real_adapter):
        """Test keys and size operations with real Redis."""
        # Start with empty database
        assert real_adapter.size() == 0
        assert list(real_adapter.keys()) == []

        # Add some keys
        test_keys = [f"size_test_{i}" for i in range(5)]
        for key in test_keys:
            real_adapter.set(key, f"value_{key}")

        # Check size
        assert real_adapter.size() == 5

        # Check keys (should be unprefixed)
        keys = list(real_adapter.keys())
        assert len(keys) == 5
        for key in test_keys:
            assert key in keys

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_serialization_methods(self, real_redis_config):
        """Test different serialization methods with real Redis."""
        serialization_methods = ["json", "string"]

        test_data = {"simple": "string_value", "complex": {"nested": {"data": [1, 2, 3]}}}

        for method in serialization_methods:
            config = real_redis_config
            config.serialization_method = method

            adapter = RedisAdapter(config)
            if not adapter.connect():
                pytest.skip("Cannot connect to Redis")

            try:
                if method == "string":
                    # String method converts everything to string
                    adapter.set("test_key", test_data["simple"])
                    result = adapter.get("test_key")
                    assert result == test_data["simple"]
                else:
                    # JSON preserves structure
                    adapter.set("test_key", test_data["complex"])
                    result = adapter.get("test_key")
                    assert result == test_data["complex"]
            finally:
                adapter.clear()
                adapter.disconnect()

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_concurrent_operations(self, real_adapter):
        """Test concurrent operations with real Redis."""
        results = []
        errors = []

        def concurrent_worker(worker_id):
            try:
                # Each worker performs multiple operations
                for i in range(10):
                    key = f"concurrent_{worker_id}_{i}"
                    value = f"value_{worker_id}_{i}"

                    # Set, get, and verify
                    assert real_adapter.set(key, value) is True
                    retrieved = real_adapter.get(key)
                    assert retrieved == value

                    results.append((worker_id, i, True))
            except Exception as e:
                errors.append((worker_id, str(e)))

        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(concurrent_worker, worker_id) for worker_id in range(5)]

            for future in as_completed(futures):
                future.result()  # Will raise if any worker failed

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations each

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_data_persistence(self, real_redis_config):
        """Test data persistence across connections."""
        # First connection - set data
        adapter1 = RedisAdapter(real_redis_config)
        if not adapter1.connect():
            pytest.skip("Cannot connect to Redis server at localhost:6379")

        test_data = {"persistent": "data", "number": 42}
        assert adapter1.set("persistence_test", test_data) is True
        adapter1.disconnect()

        # Second connection - retrieve data
        adapter2 = RedisAdapter(real_redis_config)
        assert adapter2.connect()

        retrieved_data = adapter2.get("persistence_test")
        assert retrieved_data == test_data

        # Cleanup
        adapter2.delete("persistence_test")
        adapter2.disconnect()

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_connection_recovery(self, real_redis_config):
        """Test connection recovery scenarios."""
        adapter = RedisAdapter(real_redis_config)
        if not adapter.connect():
            pytest.skip("Cannot connect to Redis server at localhost:6379")

        # Set some data
        assert adapter.set("recovery_test", "initial_value") is True
        assert adapter.get("recovery_test") == "initial_value"

        # Simulate disconnection and reconnection
        adapter.disconnect()
        assert not adapter.is_connected()

        # Reconnect
        assert adapter.connect()
        assert adapter.is_connected()

        # Data should still be there (Redis persistence)
        assert adapter.get("recovery_test") == "initial_value"

        # Cleanup
        adapter.delete("recovery_test")
        adapter.disconnect()

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_large_data_performance(self, real_adapter):
        """Test performance with large data sets."""
        # Create large data structure
        large_data = {
            "users": [
                {
                    "id": i,
                    "name": f"user_{i}",
                    "email": f"user_{i}@example.com",
                    "profile": {
                        "bio": "A" * 100,  # 100 character bio
                        "preferences": list(range(50)),
                        "metadata": {"created": time.time(), "active": True},
                    },
                }
                for i in range(100)  # 100 users
            ]
        }

        # Time the operation
        start_time = time.time()
        assert real_adapter.set("large_data", large_data) is True
        set_time = time.time() - start_time

        start_time = time.time()
        retrieved_data = real_adapter.get("large_data")
        get_time = time.time() - start_time

        # Verify data integrity
        assert retrieved_data == large_data

        # Performance should be reasonable (adjust thresholds as needed)
        assert set_time < 5.0, f"Set operation too slow: {set_time}s"
        assert get_time < 5.0, f"Get operation too slow: {get_time}s"

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_batch_performance(self, real_adapter):
        """Test batch operation performance with real Redis."""
        # Prepare large batch
        batch_size = 1000
        batch_data = {f"perf_key_{i}": f"performance_value_{i}" for i in range(batch_size)}

        # Time batch set
        start_time = time.time()
        result = real_adapter.set_many(batch_data)
        batch_set_time = time.time() - start_time

        assert len(result) == batch_size
        assert all(result.values())

        # Time batch get
        keys = list(batch_data.keys())
        start_time = time.time()
        retrieved = real_adapter.get_many(keys)
        batch_get_time = time.time() - start_time

        assert len(retrieved) == batch_size
        assert retrieved == batch_data

        # Performance benchmarks
        set_per_second = batch_size / batch_set_time
        get_per_second = batch_size / batch_get_time

        # Should achieve reasonable throughput
        assert set_per_second > 100, f"Batch set too slow: {set_per_second} ops/sec"
        assert get_per_second > 100, f"Batch get too slow: {get_per_second} ops/sec"

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_error_conditions(self, real_redis_config):
        """Test real error conditions with Redis."""
        # Test connection to non-existent server
        bad_config = RedisAdapterConfig(
            host="nonexistent.redis.server", port=6379, connection_timeout=1.0
        )

        adapter = RedisAdapter(bad_config)
        result = adapter.connect()
        assert result is False
        assert not adapter.is_connected()

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_backend_info(self, real_adapter):
        """Test backend info with real Redis."""
        info = real_adapter.get_backend_info()

        # Verify expected fields are present
        assert "server_info" in info
        assert "host" in info
        assert "port" in info
        assert "db" in info
        assert "serialization_method" in info

        # Verify values
        assert info["host"] == "localhost"
        assert info["port"] == 6379
        assert info["db"] == 15
        assert info["serialization_method"] == "json"

        # Redis-specific fields should be present
        server_info = info.get("server_info", {})
        if "redis_version" in server_info:
            assert isinstance(server_info["redis_version"], str)
        if "used_memory" in server_info:
            assert isinstance(server_info["used_memory"], int)
        if "connected_clients" in server_info:
            assert isinstance(server_info["connected_clients"], int)

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_unicode_and_special_characters(self, real_adapter):
        """Test Unicode and special characters with real Redis."""
        unicode_tests = [
            ("unicode_key_한글", "한글 값"),
            ("unicode_key_中文", "中文值"),
            ("unicode_key_العربية", "قيمة عربية"),
            ("unicode_key_русский", "русское значение"),
            ("emoji_key_🔑", "emoji_value_🎉"),
            ("special_chars", "!@#$%^&*()_+-=[]{}|;:,.<>?"),
            ("mixed_unicode", "Hello 世界 🌍 مرحبا Привет"),
        ]

        for key, value in unicode_tests:
            assert real_adapter.set(key, value) is True
            retrieved = real_adapter.get(key)
            assert retrieved == value, f"Failed for key: {key}"

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_clear_with_prefix(self, real_redis_config):
        """Test clear operation with key prefix on real Redis."""
        # Use adapter with prefix
        adapter = RedisAdapter(real_redis_config)
        if not adapter.connect():
            pytest.skip("Cannot connect to Redis server at localhost:6379")

        try:
            # Add some data
            for i in range(5):
                adapter.set(f"clear_test_{i}", f"value_{i}")

            # Verify data exists
            assert adapter.size() == 5

            # Clear all data with prefix
            assert adapter.clear() is True

            # Verify all data is gone
            assert adapter.size() == 0
            assert list(adapter.keys()) == []

        finally:
            adapter.disconnect()

    @pytest.mark.integration
    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_real_stress_test(self, real_adapter):
        """Stress test with real Redis operations."""
        operations = 1000
        errors = []

        def stress_worker(start_idx, end_idx):
            try:
                for i in range(start_idx, end_idx):
                    key = f"stress_{i}"
                    value = f"stress_value_{i}"

                    # Set
                    if not real_adapter.set(key, value):
                        errors.append(f"Failed to set {key}")
                        continue

                    # Get and verify
                    retrieved = real_adapter.get(key)
                    if retrieved != value:
                        errors.append(
                            f"Value mismatch for {key}: expected {value}, got {retrieved}"
                        )
                        continue

                    # Delete
                    if not real_adapter.delete(key):
                        errors.append(f"Failed to delete {key}")

            except Exception as e:
                errors.append(f"Exception in worker {start_idx}-{end_idx}: {str(e)}")

        # Run stress test with multiple threads
        chunk_size = operations // 4
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(4):
                start = i * chunk_size
                end = start + chunk_size if i < 3 else operations
                futures.append(executor.submit(stress_worker, start, end))

            for future in as_completed(futures):
                future.result()

        # Should have no errors
        assert len(errors) == 0, f"Stress test failures: {errors[:10]}"  # Show first 10 errors

        # Database should be clean
        assert real_adapter.size() == 0
