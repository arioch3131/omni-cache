"""
Tests for MemoryAdapter statistics functionality including
hit/miss tracking, operation counters,
eviction statistics, and statistics management.
"""

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig


class TestMemoryAdapterStatistics:
    """Tests for statistics functionality."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter with statistics enabled."""
        config = MemoryAdapterConfig(enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_cache_hit_statistics(self, adapter):
        """Test cache hit statistics tracking."""
        key = "test_key"
        value = "test_value"

        # Initially no stats
        stats = adapter.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0

        # Cache miss
        result = adapter.get(key)
        assert result is None

        stats = adapter.get_stats()
        assert stats.misses == 1
        assert stats.hit_rate == 0.0

        # Set and get (cache hit)
        adapter.set(key, value)
        result = adapter.get(key)
        assert result == value

        stats = adapter.get_stats()
        assert stats.hits == 1
        assert stats.misses == 1
        assert stats.hit_rate == 0.5

    def test_cache_set_statistics(self, adapter):
        """Test cache set statistics tracking."""
        stats = adapter.get_stats()
        assert stats.sets == 0

        adapter.set("key1", "value1")
        adapter.set("key2", "value2")

        stats = adapter.get_stats()
        assert stats.sets == 2

    def test_cache_delete_statistics(self, adapter):
        """Test cache delete statistics tracking."""
        adapter.set("key", "value")

        stats = adapter.get_stats()
        assert stats.deletes == 0

        adapter.delete("key")

        stats = adapter.get_stats()
        assert stats.deletes == 1

    def test_cache_size_statistics(self, adapter):
        """Test cache size statistics tracking."""
        stats = adapter.get_stats()
        assert stats.size == 0

        adapter.set("key1", "value1")
        adapter.set("key2", "value2")

        # Size should be updated after operations
        adapter.get("key1")  # Trigger stats update
        stats = adapter.get_stats()
        assert stats.size == 2

    def test_eviction_statistics(self):
        """Test eviction statistics tracking."""
        config = MemoryAdapterConfig(max_size=2, eviction_policy="lru", enable_stats=True)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache
            adapter.set("key1", "value1")
            adapter.set("key2", "value2")

            stats = adapter.get_stats()
            assert stats.evictions == 0

            # Trigger eviction
            adapter.set("key3", "value3")

            stats = adapter.get_stats()
            assert stats.evictions == 1
        finally:
            adapter.disconnect()

    def test_reset_statistics(self, adapter):
        """Test resetting statistics."""
        # Generate some statistics
        adapter.set("key", "value")
        adapter.get("key")
        adapter.get("nonexistent")
        adapter.delete("key")

        stats = adapter.get_stats()
        assert stats.hits > 0 or stats.misses > 0 or stats.sets > 0

        # Reset statistics
        success = adapter.reset_stats()
        assert success

        stats = adapter.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0
        assert stats.evictions == 0

    def test_statistics_disabled(self):
        """Test that statistics can be disabled."""
        config = MemoryAdapterConfig(enable_stats=False)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            adapter.set("key", "value")
            adapter.get("key")

            stats = adapter.get_stats()
            assert stats is None
        finally:
            adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
