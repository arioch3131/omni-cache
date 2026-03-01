"""
Tests for the statistics functionality of the BaseAdapter.
"""

from unittest.mock import ANY, MagicMock, patch

from omni_cache.core.interfaces import (
    CacheStats,
    PoolStats,
)


class TestBaseAdapterStats:
    """Tests for the BaseAdapter statistics functionality."""

    def test_get_stats_cache_stats(self, mock_base_adapter):
        """Test getting cache statistics."""
        stats = mock_base_adapter.get_stats()

        assert isinstance(stats, CacheStats)
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0
        assert stats.deletes == 0

    def test_get_stats_disabled(self, mock_base_adapter):
        """Test getting statistics when disabled."""
        mock_base_adapter._config.enable_stats = False

        stats = mock_base_adapter.get_stats()

        assert stats is None

    def test_get_stats_none_stats(self, mock_base_adapter):
        """Test getting statistics when _cache_stats and _pool_stats are None."""
        mock_base_adapter._cache_stats = None
        mock_base_adapter._pool_stats = None
        mock_base_adapter._config.enable_stats = True  # Ensure stats are enabled

        stats = mock_base_adapter.get_stats()

        assert stats is None

    def test_reset_stats_success(self, mock_base_adapter):
        """Test resetting statistics."""
        # First update some stats
        mock_base_adapter._update_cache_stats("get", success=True)
        stats_before = mock_base_adapter.get_stats()
        assert stats_before.hits == 1

        # Reset stats
        result = mock_base_adapter.reset_stats()

        assert result is True
        stats_after = mock_base_adapter.get_stats()
        assert stats_after.hits == 0

    def test_reset_stats_disabled(self, mock_base_adapter):
        """Test resetting statistics when disabled."""
        mock_base_adapter._config.enable_stats = False

        result = mock_base_adapter.reset_stats()

        assert result is False

    def test_reset_stats_cache_none(self, mock_base_adapter):
        """Test resetting statistics when _cache_stats is None."""
        mock_base_adapter._cache_stats = None
        mock_base_adapter._pool_stats = PoolStats()  # Ensure pool stats exist
        mock_base_adapter._pool_stats.created = 5

        result = mock_base_adapter.reset_stats()

        assert result is True
        assert mock_base_adapter._cache_stats is None  # Should remain None
        assert mock_base_adapter._pool_stats.created == 0  # Pool stats should be reset

    def test_reset_stats_pool_none(self, mock_base_adapter):
        """Test resetting statistics when _pool_stats is None."""
        mock_base_adapter._cache_stats = CacheStats()  # Ensure cache stats exist
        mock_base_adapter._cache_stats.hits = 5
        mock_base_adapter._pool_stats = None

        result = mock_base_adapter.reset_stats()

        assert result is True
        assert mock_base_adapter._cache_stats.hits == 0  # Cache stats should be reset
        assert mock_base_adapter._pool_stats is None  # Should remain None

    def test_reset_stats_exception(self, mock_base_adapter):
        """Test reset_stats with an exception."""
        original_stats_lock = mock_base_adapter._stats_lock
        mock_base_adapter._stats_lock = MagicMock()
        mock_base_adapter._stats_lock.__enter__.side_effect = Exception("Test exception")

        try:
            with patch.object(mock_base_adapter._logger, "error") as mock_error:
                result = mock_base_adapter.reset_stats()

                assert result is False
                mock_error.assert_called_once_with("Failed to reset statistics: %s", ANY)
        finally:
            mock_base_adapter._stats_lock = original_stats_lock  # Restore original

    def test_update_cache_stats(self, mock_base_adapter):
        """Test updating cache statistics."""
        # Test get hit
        mock_base_adapter._update_cache_stats("get", success=True, size=10)
        stats = mock_base_adapter.get_stats()
        assert stats.hits == 1
        assert stats.size == 10

        # Test get miss
        mock_base_adapter._update_cache_stats("get", success=False, size=10)
        stats = mock_base_adapter.get_stats()
        assert stats.misses == 1

        # Test set
        mock_base_adapter._update_cache_stats("set", success=True)
        stats = mock_base_adapter.get_stats()
        assert stats.sets == 1

        # Test delete
        mock_base_adapter._update_cache_stats("delete", success=True)
        stats = mock_base_adapter.get_stats()
        assert stats.deletes == 1

        # Test eviction
        mock_base_adapter._update_cache_stats("eviction")
        stats = mock_base_adapter.get_stats()
        assert stats.evictions == 1

    def test_update_cache_stats_empty_operation_with_size(self, mock_base_adapter):
        """Test updating cache statistics with empty operation and size in kwargs."""
        initial_hits = mock_base_adapter.get_stats().hits
        initial_misses = mock_base_adapter.get_stats().misses
        initial_sets = mock_base_adapter.get_stats().sets
        initial_deletes = mock_base_adapter.get_stats().deletes
        initial_evictions = mock_base_adapter.get_stats().evictions

        mock_base_adapter._update_cache_stats(operation="", size=100)
        stats = mock_base_adapter.get_stats()

        assert stats.hits == initial_hits
        assert stats.misses == initial_misses
        assert stats.sets == initial_sets
        assert stats.deletes == initial_deletes
        assert stats.evictions == initial_evictions
        assert stats.size == 100


class TestBaseCacheAdapter:
    """Tests for the BaseCacheAdapter class."""

    def test_should_track_stats(self, mock_cache_adapter):
        """Test that cache adapter tracks cache stats."""
        assert mock_cache_adapter._should_track_cache_stats() is True
        assert mock_cache_adapter._should_track_pool_stats() is False

        # Check that cache stats are initialized
        assert mock_cache_adapter._cache_stats is not None
        assert mock_cache_adapter._pool_stats is None

        # Check stats type
        stats = mock_cache_adapter.get_stats()
        assert isinstance(stats, CacheStats)


class TestBasePoolAdapter:
    """Tests for the BasePoolAdapter class."""

    def test_should_track_stats(self, mock_pool_adapter):
        """Test that pool adapter tracks pool stats."""
        assert mock_pool_adapter._should_track_cache_stats() is False
        assert mock_pool_adapter._should_track_pool_stats() is True

        # Check that pool stats are initialized
        assert mock_pool_adapter._cache_stats is None
        assert mock_pool_adapter._pool_stats is not None

        # Check stats type
        stats = mock_pool_adapter.get_stats()
        assert isinstance(stats, PoolStats)

    def test_update_pool_stats_disabled(self, mock_pool_adapter):
        """Test updating pool statistics when stats are disabled or pool_stats is None."""
        mock_pool_adapter._config.enable_stats = False
        mock_pool_adapter._pool_stats = None

        # Should not raise exception and return early
        mock_pool_adapter._update_pool_stats("create")
        assert mock_pool_adapter._pool_stats is None

    def test_update_pool_stats(self, mock_pool_adapter):
        """Test updating pool statistics."""
        # Test create
        mock_pool_adapter._update_pool_stats("create", active=1, idle=0)
        stats = mock_pool_adapter.get_stats()
        assert stats.created == 1
        assert stats.active == 1
        assert stats.idle == 0

        # Test borrow
        mock_pool_adapter._update_pool_stats("borrow", active=1, idle=0)
        stats = mock_pool_adapter.get_stats()
        assert stats.borrowed == 1

        # Test return
        mock_pool_adapter._update_pool_stats("return", active=0, idle=1)
        stats = mock_pool_adapter.get_stats()
        assert stats.returned == 1
        assert stats.active == 0
        assert stats.idle == 1

        # Test destroy
        mock_pool_adapter._update_pool_stats("destroy", active=0, idle=0)
        stats = mock_pool_adapter.get_stats()
        assert stats.destroyed == 1

    def test_update_pool_stats_destroy(self, mock_pool_adapter):
        """Test updating pool statistics for 'destroy' operation."""
        mock_pool_adapter._update_pool_stats("destroy")
        stats = mock_pool_adapter.get_stats()
        assert stats.destroyed == 1

    def test_update_pool_stats_no_operation_active_kwargs(self, mock_pool_adapter):
        """Test updating pool statistics with no operation and 'active' in kwargs."""
        mock_pool_adapter._update_pool_stats(operation=None, active=10)
        stats = mock_pool_adapter.get_stats()
        assert stats.active == 10

    def test_update_pool_stats_no_operation_idle_kwargs(self, mock_pool_adapter):
        """Test updating pool statistics with no operation and 'idle' in kwargs."""
        mock_pool_adapter._update_pool_stats(operation=None, idle=5)
        stats = mock_pool_adapter.get_stats()
        assert stats.idle == 5

    def test_update_pool_stats_no_operation_no_kwargs(self, mock_pool_adapter):
        """Test updating pool statistics with no operation and no relevant kwargs."""
        initial_active = mock_pool_adapter.get_stats().active
        initial_idle = mock_pool_adapter.get_stats().idle

        mock_pool_adapter._update_pool_stats(operation=None)
        stats = mock_pool_adapter.get_stats()

        assert stats.active == initial_active
        assert stats.idle == initial_idle
