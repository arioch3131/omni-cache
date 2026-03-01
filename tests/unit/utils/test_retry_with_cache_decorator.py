from unittest.mock import Mock

import pytest

from omni_cache.core.exceptions.cache_exceptions import CacheError
from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import retry_with_cache


class TestRetryWithCacheDecorator:
    """Test retry_with_cache decorator."""

    def test_retry_with_cache_success(self):  # ← Supprimer mock_get_manager
        """Test retry_with_cache decorator with successful execution."""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get = Mock(return_value=None)

        call_count = 0

        @retry_with_cache(max_retries=3, manager=mock_manager)  # ← Déjà correct !
        def sometimes_failing_func(x):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ValueError("Temporary failure")
            return x * 2

        result = sometimes_failing_func(5)
        assert result == 10
        assert call_count == 3

    def test_retry_with_cache_cached_result(self):
        """Test retry_with_cache decorator with cached result on failure."""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get.return_value = "cached_fallback"

        @retry_with_cache(max_retries=2, manager=mock_manager)
        def failing_func(x):
            raise ValueError("Always fails")

        with pytest.raises(CacheError, match="Cached failure"):
            failing_func(5)

    def test_retry_with_cache_no_fallback(self):
        """Test retry_with_cache decorator without cached fallback."""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get = Mock(return_value=None)

        @retry_with_cache(max_retries=2, manager=mock_manager)
        def failing_func(x):
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            failing_func(5)
