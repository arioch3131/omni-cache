import asyncio
from unittest.mock import Mock

import pytest

from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import async_cached


class TestAsyncCachedDecorator:
    """Test async_cached decorator."""

    @pytest.fixture
    def mock_cache_manager(self):
        """Create a mock cache manager for async tests."""
        manager = Mock(spec=CacheManager)
        manager.get.return_value = None
        manager.set.return_value = True
        return manager

    @pytest.mark.asyncio
    async def test_async_cached_basic(self, mock_cache_manager):
        """Test basic async cached decorator functionality."""
        call_count = 0

        @async_cached(manager=mock_cache_manager)
        async def async_expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate async work
            return x + y

        result = await async_expensive_function(1, 2)
        assert result == 3
        assert call_count == 1
        mock_cache_manager.get.assert_called_once()
        mock_cache_manager.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_cached_cache_hit(self, mock_cache_manager):
        """Test async cached decorator with cache hit."""
        mock_cache_manager.get.return_value = "cached_async_result"

        call_count = 0

        @async_cached(manager=mock_cache_manager)
        async def async_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result = await async_func(10)
        assert result == "cached_async_result"
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_async_cached_with_callbacks(self, mock_cache_manager):
        """Test async cached decorator with callbacks."""
        hit_calls = []
        miss_calls = []

        def on_hit(key, value):
            hit_calls.append((key, value))

        def on_miss(key):
            miss_calls.append(key)

        @async_cached(on_hit=on_hit, on_miss=on_miss, manager=mock_cache_manager)
        async def async_func(x):
            return x * 3

        await async_func(5)
        assert len(miss_calls) == 1
        assert len(hit_calls) == 0
