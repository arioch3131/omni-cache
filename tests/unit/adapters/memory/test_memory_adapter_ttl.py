"""
Tests for MemoryAdapter TTL (Time To Live) functionality including explicit TTL,
default TTL, TTL overrides, expiration behavior, and cleanup of expired items.
"""

import time

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig


class TestMemoryAdapterTTL:
    """Tests for TTL (Time To Live) functionality."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter for testing."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)  # Fast cleanup for testing
        adapter = MemoryAdapter(config)
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_set_with_ttl(self, adapter):
        """Test setting items with TTL."""
        key = "test_key"
        value = "test_value"
        ttl = 0.5  # 500ms

        adapter.set(key, value, ttl=ttl)
        assert adapter.get(key) == value
        assert adapter.exists(key)

        # Wait for expiration
        time.sleep(ttl + 0.1)
        assert adapter.get(key) is None
        assert not adapter.exists(key)

    def test_default_ttl(self):
        """Test default TTL configuration."""
        config = MemoryAdapterConfig(default_ttl=0.3)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            key = "test_key"
            value = "test_value"

            adapter.set(key, value)  # Should use default TTL
            assert adapter.get(key) == value

            # Wait for expiration
            time.sleep(0.4)
            assert adapter.get(key) is None
        finally:
            adapter.disconnect()

    def test_ttl_overrides_default(self):
        """Test that explicit TTL overrides default TTL."""
        config = MemoryAdapterConfig(default_ttl=0.1)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            key = "test_key"
            value = "test_value"

            # Set with longer TTL than default
            adapter.set(key, value, ttl=0.3)

            # Should not expire with default TTL
            time.sleep(0.15)
            assert adapter.get(key) == value

            # Should expire with explicit TTL
            time.sleep(0.2)
            assert adapter.get(key) is None
        finally:
            adapter.disconnect()

    def test_no_ttl_persists(self, adapter):
        """Test that items without TTL persist indefinitely."""
        key = "test_key"
        value = "test_value"

        adapter.set(key, value)  # No TTL

        # Wait a reasonable amount of time
        time.sleep(0.2)

        assert adapter.get(key) == value
        assert adapter.exists(key)

    def test_expired_items_cleaned_on_access(self, adapter):
        """Test that expired items are cleaned up on access."""
        key = "test_key"
        value = "test_value"
        ttl = 0.1

        adapter.set(key, value, ttl=ttl)
        assert adapter.size() == 1

        # Wait for expiration
        time.sleep(ttl + 0.05)

        # Access should trigger cleanup
        result = adapter.get(key)
        assert result is None
        assert adapter.size() == 0

    def test_keys_filters_expired_items(self, adapter):
        """Test that keys() iterator filters out expired items."""
        # Set items with different TTLs
        adapter.set("persistent", "value1")  # No TTL
        adapter.set("short_lived", "value2", ttl=0.1)
        adapter.set("medium_lived", "value3", ttl=0.3)

        assert adapter.size() == 3

        # Wait for short-lived item to expire
        time.sleep(0.15)

        keys_list = list(adapter.keys())
        assert len(keys_list) == 2
        assert "persistent" in keys_list
        assert "medium_lived" in keys_list
        assert "short_lived" not in keys_list


if __name__ == "__main__":
    pytest.main([__file__])
