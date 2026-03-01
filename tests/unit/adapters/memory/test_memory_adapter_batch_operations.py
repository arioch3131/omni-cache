"""
Tests for MemoryAdapter batch operations including
get_many, set_many, and bulk operations.
"""

import time

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig

# pylint: disable=protected-access


class TestMemoryAdapterBatchOperations:
    """Tests for batch operations."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter for testing."""
        adapter = MemoryAdapter()
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_get_many(self, adapter):
        """Test get_many operation."""
        # Set up test data
        test_data = {"key1": "value1", "key2": "value2", "key3": "value3"}

        for key, value in test_data.items():
            adapter.set(key, value)

        # Test get_many with existing keys
        keys = ["key1", "key2", "key3"]
        result = adapter.get_many(keys)

        assert len(result) == 3
        for key in keys:
            assert key in result
            assert result[key] == test_data[key]

    def test_get_many_with_nonexistent_keys(self, adapter):
        """Test get_many with mix of existing and non-existing keys."""
        adapter.set("key1", "value1")
        adapter.set("key3", "value3")

        keys = ["key1", "key2", "key3", "key4"]
        result = adapter.get_many(keys)

        # Should only return existing keys
        assert len(result) == 4
        assert result["key1"] == "value1"
        assert result["key3"] == "value3"
        assert result["key2"] is None
        assert result["key4"] is None

    def test_get_many_with_expired_keys(self, adapter):
        """Test get_many filters out expired keys."""
        adapter.set("persistent", "value1")  # No TTL
        adapter.set("expires", "value2", ttl=0.1)

        # Wait for expiration
        time.sleep(0.15)

        keys = ["persistent", "expires"]
        result = adapter.get_many(keys)

        assert len(result) == 2
        assert result["persistent"] == "value1"
        assert result["expires"] is None

    def test_set_many(self, adapter):
        """Test set_many operation."""
        data = {"key1": "value1", "key2": "value2", "key3": "value3"}

        result = adapter.set_many(data)
        assert all(result.values())
        assert adapter.size() == 3

        # Verify all items were set
        for key, value in data.items():
            assert adapter.get(key) == value

    def test_set_many_with_ttl(self, adapter):
        """Test set_many operation with TTL."""
        data = {"key1": "value1", "key2": "value2"}

        result = adapter.set_many(data, ttl=0.2)
        assert all(result.values())

        # Verify items exist initially
        for key in data:
            assert adapter.exists(key)

        # Wait for expiration
        time.sleep(0.25)

        # Verify items are expired
        for key in data:
            assert not adapter.exists(key)

    def test_set_many_with_size_limit(self):
        """Test set_many with size limit and eviction."""
        config = MemoryAdapterConfig(max_size=3, eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache partially
            adapter.set("existing", "value")

            # Try to add more items than available space
            data = {"key1": "value1", "key2": "value2", "key3": "value3"}

            result = adapter.set_many(data)
            assert all(result.values())
            assert adapter.size() == 3  # Should evict the existing item

            # The existing item should be evicted
            assert not adapter.exists("existing")
        finally:
            adapter.disconnect()

    def test_delete_many(self, adapter):
        """Test delete_many operation."""
        # Set up test data
        for i in range(5):
            adapter.set(f"key{i}", f"value{i}")

        assert adapter.size() == 5

        # Delete multiple keys
        keys_to_delete = ["key1", "key3", "key5"]  # Include non-existent key
        result = adapter.delete_many(keys_to_delete)

        assert result["key1"] is True
        assert result["key3"] is True
        assert result["key5"] is False  # Non-existent
        assert adapter.size() == 3

    def test_get_many_with_no_evinct_lru(self):
        """Test get_many operation with default value."""
        config_dict = {"name": "test_cache", "max_size": 100, "eviction_policy": "fifo"}
        adapter = MemoryAdapter(config_dict)
        adapter.connect()
        adapter.set("key1", "default_value1")
        adapter.set("key2", "default_value2")
        result = adapter.get_many(["key1", "key2"])
        assert result["key1"] == "default_value1"
        assert result["key2"] == "default_value2"
        adapter.disconnect()

    def test_set_many_with_ttl_none_default_ttl_not_none(self):
        """Test set_many with a ttl to none and a default ttl to not none"""
        config_dict = {
            "name": "test_cache",
            "max_size": 100,
            "eviction_policy": "lru",
            "default_ttl": 100,
        }
        adapter = MemoryAdapter(config_dict)
        adapter.connect()
        set_keys_values = {"key1": "default_value1", "key2": "default_value2"}
        result = adapter.set_many(set_keys_values, None)
        assert all(result.values())
        adapter.disconnect()

    def test_set_many_with_eviction_policy_not_lru(self):
        """Test set_many with eviction policy not lru."""
        config_dict = {"name": "test_cache", "max_size": 100, "eviction_policy": "fifo"}
        adapter = MemoryAdapter(config_dict)
        adapter.connect()
        set_keys_values = {"key1": "default_value1", "key2": "default_value2"}
        result = adapter.set_many(set_keys_values, None)
        assert all(result.values())
        adapter.disconnect()

    def test_set_many_fails_with_exception(self):
        """Test set_many fails with exception."""
        config_dict = {"name": "test_cache", "max_size": 100, "eviction_policy": "fifo"}
        adapter = MemoryAdapter(config_dict)
        adapter.connect()
        set_keys_values = {"key1": "default_value1", "key2": "default_value2"}

        class FailingDict:
            """Class Failing Dict to generate an exception with len"""

            def __len__(self):
                raise RuntimeError("Length operation failed")

        adapter._data = FailingDict()
        result = adapter.set_many(set_keys_values, None)
        assert not any(result.values())

        adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
