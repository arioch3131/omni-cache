from unittest.mock import Mock

import pytest

from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import cached


class TestCachedDecorator:
    """Test cached decorator functionality."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager."""
        manager = Mock(spec=CacheManager)
        manager.get.return_value = None
        manager.set.return_value = True
        return manager

    def test_cached_decorator_basic(self, mock_cache_manager):
        """Test basic cached decorator functionality."""
        call_count = 0

        @cached(manager=mock_cache_manager)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # First call
        result1 = expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1
        mock_cache_manager.get.assert_called_once()
        mock_cache_manager.set.assert_called_once()

    def test_cached_decorator_with_ttl(self, mock_cache_manager):
        """Test cached decorator with TTL."""

        @cached(ttl=300, manager=mock_cache_manager)
        def func_with_ttl(x):
            return x * 2

        result = func_with_ttl(5)
        assert result == 10

        # Verify TTL was passed to cache.set
        call_args = mock_cache_manager.set.call_args
        assert call_args[1]["ttl"] == 300

    def test_cached_decorator_cache_hit(self, mock_cache_manager):
        """Test cached decorator with cache hit."""
        # Mock cache hit
        mock_cache_manager.get.return_value = "cached_result"

        call_count = 0

        @cached(manager=mock_cache_manager)
        def func(x):
            nonlocal call_count
            call_count += 1
            return x

        result = func(10)
        assert result == "cached_result"
        assert call_count == 0  # Function should not be called

    def test_cached_decorator_with_callbacks(self, mock_cache_manager):
        """Test cached decorator with hit/miss callbacks."""
        hit_calls = []
        miss_calls = []

        def on_hit(key, value):
            hit_calls.append((key, value))

        def on_miss(key):
            miss_calls.append(key)

        # Cache miss scenario
        mock_cache_manager.get.return_value = None

        @cached(on_hit=on_hit, on_miss=on_miss, manager=mock_cache_manager)
        def func(x):
            return x * 2

        result = func(5)
        assert result == 10
        assert len(miss_calls) == 1
        assert len(hit_calls) == 0

        # Cache hit scenario
        mock_cache_manager.get.return_value = 20
        result = func(10)
        assert result == 20
        assert len(hit_calls) == 1
        assert hit_calls[0][1] == 20

    def test_cached_decorator_error_handling(self, mock_cache_manager):
        """Test cached decorator error handling."""
        mock_cache_manager.get.side_effect = Exception("Cache error")

        error_calls = []

        def on_error(exc):
            error_calls.append(exc)
            return "fallback_result"

        @cached(on_error=on_error, manager=mock_cache_manager)
        def func(x):
            return x * 3

        result = func(5)
        assert result == "fallback_result"
        assert len(error_calls) == 1

    def test_cached_decorator_ignore_parameters(self, mock_cache_manager):
        """Test cached decorator with ignored parameters."""

        @cached(ignore_args={1}, ignore_kwargs={"debug"}, manager=mock_cache_manager)
        def func(a, b, debug=False):
            return a * 2

        func(5, 100, debug=True)
        func(5, 999, debug=False)  # Different b and debug, but should use same cache key

        # Both calls should generate the same cache key
        assert mock_cache_manager.get.call_count == 2
        call_keys = [call[0][0] for call in mock_cache_manager.get.call_args_list]
        assert call_keys[0] == call_keys[1]
