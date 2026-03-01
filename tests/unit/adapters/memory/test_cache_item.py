"""
Tests for CacheItem class functionality and expiration logic.
"""

import time

import pytest

from omni_cache.adapters.memory import CacheItem


# Cache Item Tests
class TestCacheItemBehavior:
    """Test CacheItem functionality and expiration logic."""

    def test_cache_item_creation_without_ttl(self):
        """Test cache item creation with default values."""
        value = "test_value"
        item = CacheItem(value=value)

        assert item.value == value
        assert item.access_count == 0
        assert item.expires_at is None
        assert isinstance(item.created_at, float)
        assert isinstance(item.last_accessed, float)
        assert item.created_at <= item.last_accessed

    def test_cache_item_creation_with_ttl(self):
        """Test cache item creation with explicit expiration time."""
        value = "test_value"
        expires_at = time.time() + 300
        item = CacheItem(value=value, expires_at=expires_at)

        assert item.value == value
        assert item.expires_at == expires_at

    def test_item_never_expires_without_ttl(self):
        """Test that items without TTL never expire."""
        item = CacheItem(value="test")
        assert not item.is_expired()

        # Even with future time
        future_time = time.time() + 1000
        assert not item.is_expired(future_time)

    def test_item_expiration_with_future_ttl(self):
        """Test that items with future expiration are not expired."""
        expires_at = time.time() + 300
        item = CacheItem(value="test", expires_at=expires_at)
        assert not item.is_expired()

    def test_item_expiration_with_past_ttl(self):
        """Test that items with past expiration are expired."""
        expires_at = time.time() - 1
        item = CacheItem(value="test", expires_at=expires_at)
        assert item.is_expired()

    def test_item_expiration_with_custom_time(self):
        """Test expiration check with custom current time."""
        expires_at = time.time() + 100
        item = CacheItem(value="test", expires_at=expires_at)

        # Not expired with earlier time
        assert not item.is_expired(expires_at - 1)

        # Expired with later time
        assert item.is_expired(expires_at + 1)

    def test_access_updates_tracking_data(self):
        """Test that access method correctly updates tracking information."""
        item = CacheItem(value="test")
        initial_last_accessed = item.last_accessed
        initial_count = item.access_count

        # Small delay to ensure time difference
        time.sleep(0.001)
        item.access()

        assert item.access_count == initial_count + 1
        assert item.last_accessed > initial_last_accessed

        # Multiple accesses
        item.access()
        assert item.access_count == initial_count + 2


if __name__ == "__main__":
    pytest.main([__file__])
