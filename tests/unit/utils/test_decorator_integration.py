from unittest.mock import Mock

from omni_cache.core.interfaces import KeyValueInterface
from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import cached, memoize, retry_with_cache


class TestDecoratorIntegration:
    """Integration tests combining multiple decorators and scenarios."""

    def test_multiple_decorators(self):
        """Test function with multiple decorators."""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get = Mock(return_value=None)
        mock_adapter = Mock(spec=KeyValueInterface)
        mock_manager._get_cache_adapter.return_value = mock_adapter

        @memoize(ttl=300)
        @retry_with_cache(max_retries=2)
        def complex_func(x, y):
            if x < 0:
                raise ValueError("Negative input")
            return x + y

        result = complex_func(5, 10)
        assert result == 15

    def test_decorator_preserves_function_metadata(self):
        """Test that decorators preserve function metadata."""

        @cached()
        def documented_function(x):
            """This is a documented function."""
            return x * 2

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."

    def test_performance_with_heavy_computation(self):
        """Test decorator performance with computationally heavy function."""
        mock_manager = Mock(spec=CacheManager)
        # First call misses cache, second hits
        mock_manager.get.side_effect = [None, "cached_result"]

        call_count = 0

        @cached(manager=mock_manager)
        def heavy_computation(n):
            nonlocal call_count
            call_count += 1
            # Simulate heavy computation
            return sum(i * i for i in range(n))

        # First call
        heavy_computation(1000)
        assert call_count == 1

        # Second call should use cache
        result2 = heavy_computation(1000)
        assert result2 == "cached_result"
        assert call_count == 1  # Function not called again
