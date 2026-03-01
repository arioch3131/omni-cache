import json
from unittest.mock import MagicMock, Mock

import pytest

from omni_cache.core.interfaces import KeyValueInterface
from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import (
    CacheConfig,
    KeyGenerator,
    clear_cache,
    get_cache_stats,
    invalidate_cache,
)


class TestUtilityFunctions:
    """Test utility functions like cache_key, invalidate_cache, etc."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager for utility function tests."""
        manager = Mock(spec=CacheManager)
        return manager

    def test_cache_key_generation(self):
        """Test cache_key function."""

        def sample_func(a, b):
            return a + b

        config = CacheConfig()
        key = KeyGenerator.default_key_generator(sample_func, (1, 2), {"c": 3}, config)
        args_hash = KeyGenerator._hash_string(json.dumps([1, 2], sort_keys=True, default=str))
        kwargs_hash = KeyGenerator._hash_string(json.dumps({"c": 3}, sort_keys=True, default=str))
        expected_key = (
            f"{sample_func.__module__}.{sample_func.__qualname__}:"
            f"args:{args_hash}:kwargs:{kwargs_hash}"
        )
        assert key == expected_key

    def test_invalidate_cache(self, mock_cache_manager):
        """Test invalidate_cache function."""
        mock_cache_manager._get_cache_adapter.return_value = Mock(spec=KeyValueInterface)
        mock_cache_manager._get_cache_adapter.return_value.keys.return_value = [
            "test:key1",
            "test:key2",
        ]
        mock_cache_manager._get_cache_adapter.return_value.delete.return_value = True
        mock_cache_manager.delete.return_value = True

        result = invalidate_cache(namespace="test", manager=mock_cache_manager)
        assert result >= 0  # Should return number of invalidated entries
        mock_cache_manager._get_cache_adapter.return_value.delete.assert_called()

    def test_clear_cache_by_adapter(self, mock_cache_manager):
        """Test clear_cache function with adapter."""
        mock_adapter = MagicMock()
        mock_adapter.clear.return_value = None
        mock_adapter.size.return_value = 0
        mock_cache_manager._get_cache_adapter.return_value = mock_adapter

        result = clear_cache(adapter="redis", manager=mock_cache_manager)
        assert result == 0
        mock_adapter.clear.assert_called_once()
        mock_cache_manager._get_cache_adapter.assert_called_once_with(adapter_name="redis")

    def test_clear_cache_all(self, mock_cache_manager):
        """Test clear_cache function without parameters (clear all)."""
        mock_cache_manager.clear.return_value = True

        result = clear_cache(manager=mock_cache_manager)
        assert result is True
        mock_cache_manager.clear.assert_called_once()

    def test_get_cache_stats_function(self, mock_cache_manager):
        """Test get_cache_stats function."""
        mock_cache_manager.get_global_stats.return_value = {"hits": 10, "misses": 5}

        stats = get_cache_stats(manager=mock_cache_manager)
        assert stats == {"hits": 10, "misses": 5}
        mock_cache_manager.get_global_stats.assert_called_once()

    def test_get_cache_stats_by_adapter(self, mock_cache_manager):
        """Test get_cache_stats function for specific adapter."""
        mock_cache_manager.get_adapter_stats.return_value = {"hits": 5, "misses": 2}

        stats = get_cache_stats(adapter="redis", manager=mock_cache_manager)
        assert stats == {"hits": 5, "misses": 2}
        mock_cache_manager.get_adapter_stats.assert_called_once_with("redis")

    def test_get_cache_stats_with_function_cache_info(self):
        """Test get_cache_stats with function that has cache_info."""
        mock_func = Mock()
        mock_func.cache_info.return_value = {"function_hits": 3}

        stats = get_cache_stats(func=mock_func)
        assert stats == {"function_hits": 3}
        mock_func.cache_info.assert_called_once()
