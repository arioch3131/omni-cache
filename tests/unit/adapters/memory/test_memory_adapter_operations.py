"""
Tests for the Memory Adapter.

This module contains comprehensive tests for the MemoryAdapter class,
covering all functionality including basic operations, TTL support,
eviction policies, statistics, and error handling.
"""

import pytest

from omni_cache.adapters.memory import MemoryAdapter


class TestMemoryAdapterOperations:
    """Tests for MemoryAdapter basic operations."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter for testing."""
        adapter = MemoryAdapter()
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_set_and_get_basic(self, adapter):
        """Test basic set and get operations."""
        key = "test_key"
        value = "test_value"

        # Set value
        success = adapter.set(key, value)
        assert success

        # Get value
        result = adapter.get(key)
        assert result == value

    def test_get_with_default(self, adapter):
        """Test get operation with default value."""
        result = adapter.get("nonexistent_key", "default_value")
        assert result == "default_value"

    def test_get_with_fifo_policy(self):
        """Test get operation with no evinction lru."""
        config_dict = {"name": "test_cache", "max_size": 100, "eviction_policy": "fifo"}
        adapter = MemoryAdapter(config_dict)
        adapter.connect()
        adapter.set("key", "default_value")
        result = adapter.get("key")
        assert result == "default_value"
        adapter.disconnect()

    def test_get_nonexistent_key(self, adapter):
        """Test get operation with nonexistent key."""
        result = adapter.get("nonexistent_key")
        assert result is None

    def test_set_and_get_different_types(self, adapter):
        """Test set and get with different data types."""
        test_cases = [
            ("string_key", "string_value"),
            ("int_key", 42),
            ("float_key", 3.14),
            ("bool_key", True),
            ("list_key", [1, 2, 3]),
            ("dict_key", {"nested": "value"}),
            ("none_key", None),
        ]

        for key, value in test_cases:
            adapter.set(key, value)
            result = adapter.get(key)
            assert result == value

    def test_get_item_info(self, adapter):
        """Test getting detailed item information."""
        key = "test_key"
        value = "test_value"

        # Non-existent key
        info = adapter.get_item_info(key)
        assert info is None

        # Set item and get info
        adapter.set(key, value, ttl=300)
        info = adapter.get_item_info(key)

        assert info is not None
        assert "created_at" in info
        assert "expires_at" in info
        assert "access_count" in info
        assert "last_accessed" in info
        assert "ttl_remaining" in info
        assert "size_bytes" in info
        assert info["ttl_remaining"] > 0

    def test_exists(self, adapter):
        """Test exists operation."""
        key = "test_key"

        # Key doesn't exist initially
        assert not adapter.exists(key)

        # Set key and check existence
        adapter.set(key, "value")
        assert adapter.exists(key)

        # Delete key and check non-existence
        adapter.delete(key)
        assert not adapter.exists(key)

    def test_delete(self, adapter):
        """Test delete operation."""
        key = "test_key"
        value = "test_value"

        # Delete non-existent key
        result = adapter.delete(key)
        assert result is False

        # Set, then delete existing key
        adapter.set(key, value)
        assert adapter.exists(key)

        result = adapter.delete(key)
        assert result is True
        assert not adapter.exists(key)

    def test_clear(self, adapter):
        """Test clear operation."""
        # Add multiple items
        for i in range(5):
            adapter.set(f"key_{i}", f"value_{i}")

        assert adapter.size() == 5

        # Clear all items
        success = adapter.clear()
        assert success
        assert adapter.size() == 0

    def test_size(self, adapter):
        """Test size operation."""
        assert adapter.size() == 0

        # Add items and check size
        for i in range(3):
            adapter.set(f"key_{i}", f"value_{i}")
            assert adapter.size() == i + 1

    def test_keys_iterator(self, adapter):
        """Test keys iterator."""
        # Empty cache
        keys_list = list(adapter.keys())
        assert len(keys_list) == 0

        # Add some items
        test_keys = ["key1", "key2", "key3"]
        for key in test_keys:
            adapter.set(key, f"value_{key}")

        # Check keys
        keys_list = list(adapter.keys())
        assert len(keys_list) == 3
        assert set(keys_list) == set(test_keys)


if __name__ == "__main__":
    pytest.main([__file__])
