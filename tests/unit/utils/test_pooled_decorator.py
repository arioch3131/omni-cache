from unittest.mock import MagicMock, Mock

import pytest

from omni_cache.core.exceptions import OperationTimeoutError, PoolEmptyError
from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import pooled


class TestPooledDecorator:
    """Test pooled decorator."""

    @pytest.fixture
    def mock_pool_manager(self):
        """Create a mock pool manager with pool context."""
        manager = Mock(spec=CacheManager)

        # Mock pool context manager
        pool_context = MagicMock()
        pool_context.__enter__.return_value = "pooled_object"
        pool_context.__exit__.return_value = None

        manager.borrow.return_value = pool_context  # Changed from get_object_pool
        return manager

    def test_pooled_decorator_basic(self, mock_pool_manager):
        """Test basic pooled decorator functionality."""

        @pooled(manager=mock_pool_manager)
        def func_with_pool(pool_obj, x):
            return f"{pool_obj}:{x}"

        result = func_with_pool(5)
        assert result == "pooled_object:5"
        mock_pool_manager.borrow.assert_called_once()

    def test_pooled_decorator_with_callbacks(self, mock_pool_manager):
        """Test pooled decorator with callbacks."""
        borrow_calls = []
        return_calls = []

        def on_borrow(obj):
            borrow_calls.append(obj)

        def on_return(obj):
            return_calls.append(obj)

        @pooled(on_borrow=on_borrow, on_return=on_return, manager=mock_pool_manager)
        def func_with_pool(pool_obj):
            return pool_obj

        result = func_with_pool()
        assert result == "pooled_object"

    def test_pooled_decorator_with_retries(self, mock_pool_manager):
        """Test pooled decorator with retry logic."""
        # First two calls fail, third succeeds
        side_effects = [PoolEmptyError("Pool empty"), PoolEmptyError("Pool empty"), MagicMock()]

        pool_contexts = []
        for effect in side_effects:
            if isinstance(effect, Exception):
                context = MagicMock()
                context.__enter__.side_effect = effect
                pool_contexts.append(context)
            else:
                context = MagicMock()
                context.__enter__.return_value = "success_object"
                pool_contexts.append(context)

        mock_pool_manager.borrow.side_effect = pool_contexts

        @pooled(max_retries=3, retry_delay=0.01, manager=mock_pool_manager)
        def func_with_pool(pool_obj):
            return pool_obj

        result = func_with_pool()
        assert result == "success_object"
        assert mock_pool_manager.borrow.call_count == 3

    def test_pooled_decorator_error_handling(self, mock_pool_manager):
        """Test pooled decorator error handling."""
        mock_pool_manager.borrow.side_effect = OperationTimeoutError("Timeout", timeout=1.0)

        error_calls = []

        def on_error(exc):
            error_calls.append(exc)
            return None  # Changed to return None

        @pooled(on_error=on_error, max_retries=1, manager=mock_pool_manager)
        def func_with_pool(pool_obj):
            return pool_obj

        with pytest.raises(OperationTimeoutError, match="Timeout"):
            func_with_pool()
        assert len(error_calls) == 1
