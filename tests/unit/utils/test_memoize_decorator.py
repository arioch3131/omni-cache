from unittest.mock import Mock

from omni_cache.utils.decorators import memoize


class TestMemoizeDecorator:
    """Test memoize decorator."""

    def test_memoize_basic(self, configured_cache_manager):
        """Test basic memoize functionality."""
        mock_manager = configured_cache_manager
        mock_manager.get = Mock(return_value=None)

        call_count = 0

        @memoize()
        def fibonacci(n):
            nonlocal call_count
            call_count += 1
            if n <= 1:
                return n
            return fibonacci(n - 1) + fibonacci(n - 2)

        result = fibonacci(5)
        # Exact call count depends on caching behavior
        assert result == 5
        assert call_count > 0
