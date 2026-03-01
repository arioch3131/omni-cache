"""
Tests for Redis adapter implementation.

This module contains comprehensive tests for the RedisAdapter class,
including connection management, CRUD operations, serialization,
error handling, and performance tests.
"""

import time

import pytest

# Test the adapter import
try:
    from omni_cache.adapters.redis import RedisAdapter, RedisAdapterConfig

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisAdapter = None
    RedisAdapterConfig = None

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name


@pytest.mark.integration
@pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
class TestRedisAdapterIntegration:
    """Integration tests for RedisAdapter (requires running Redis)."""

    @pytest.fixture
    def real_adapter(self):
        """Create RedisAdapter with real Redis connection."""
        config = RedisAdapterConfig(
            host="localhost",
            port=6379,
            db=15,  # Use db 15 for tests to avoid conflicts
            key_prefix="test",
        )

        adapter = RedisAdapter(config)

        try:
            if adapter.connect():
                adapter.clear()  # Clean up before test
                yield adapter
                adapter.clear()  # Clean up after test
                adapter.disconnect()
            else:
                pytest.skip("Cannot connect to Redis server")
        except Exception as e:  # pylint: disable=broad-exception-caught
            pytest.skip(f"Redis server not available: {e}")

    def test_real_connection(self, real_adapter):
        """Test real connection to Redis."""
        assert real_adapter.is_connected()
        assert real_adapter.health_check()
        assert real_adapter.ping()

    def test_real_crud_operations(self, real_adapter):
        """Test real CRUD operations."""
        # Set
        assert real_adapter.set("test_key", {"data": "value"}) is True

        # Get
        result = real_adapter.get("test_key")
        assert result == {"data": "value"}

        # Exists
        assert real_adapter.exists("test_key") is True

        # Delete
        assert real_adapter.delete("test_key") is True
        assert real_adapter.exists("test_key") is False

    def test_real_ttl_operations(self, real_adapter):
        """Test real TTL operations."""
        # Set with TTL
        assert real_adapter.set("ttl_key", "value", ttl=2) is True

        # Check TTL
        ttl = real_adapter.ttl("ttl_key")
        assert ttl is not None
        assert 0 < ttl <= 2

        # Wait for expiration
        time.sleep(2.1)
        assert real_adapter.get("ttl_key") is None

    def test_real_batch_operations(self, real_adapter):
        """Test real batch operations."""
        # Set many
        mapping = {"batch1": "value1", "batch2": "value2", "batch3": "value3"}
        count = real_adapter.set_many(mapping)
        assert len(count) == 3
        assert all(count.values())

        # Get many
        result = real_adapter.get_many(["batch1", "batch2", "batch3", "nonexistent"])
        assert len(result) == 4
        assert result["batch1"] == "value1"
        assert result["nonexistent"] is None

        # Delete many
        delete_result = real_adapter.delete_many(["batch1", "batch2"])
        assert len(delete_result) == 2

    def test_real_increment_operations(self, real_adapter):
        """Test real increment operations."""
        # Integer increment
        real_adapter.set("counter", 0)
        result = real_adapter.increment("counter", 5)
        assert result == 5

        # Float increment
        real_adapter.set("float_counter", 0.0)
        result = real_adapter.increment("float_counter", 1.5)
        assert result == 1.5
