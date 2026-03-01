import json
from unittest.mock import Mock, patch

import pytest

from omni_cache.core.exceptions import PoolEmptyError
from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import CacheConfig, KeyGenerator, cached, invalidate_cache, pooled


# Helper class to mock a context manager
class MockContextManager(Mock):
    def __enter__(self):
        return self  # Return self as the pooled object

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


# Mock CacheManager and CacheAdapter for testing
@pytest.fixture
def mock_cache_manager():
    manager = Mock(spec=CacheManager)
    # _get_cache_adapter should return a mock that has keys and delete methods
    mock_adapter_for_manager = Mock()
    mock_adapter_for_manager.keys = Mock(
        return_value=[]
    )  # Ensure it returns an iterable when called
    mock_adapter_for_manager.delete.return_value = True
    manager._get_cache_adapter.return_value = mock_adapter_for_manager

    manager.get.return_value = None
    manager.set.return_value = None
    manager.delete.return_value = True
    manager.clear.return_value = 0

    # Mock the borrow method to return an instance of our MockContextManager
    manager.borrow.return_value = MockContextManager()

    return manager


@pytest.fixture
def mock_cache_adapter():
    # Mock an adapter that has keys and delete methods
    adapter = Mock()
    adapter.keys = Mock(return_value=[])  # Ensure it returns an iterable when called
    adapter.delete.return_value = True
    adapter.clear.return_value = None
    adapter.size.return_value = 0
    return adapter


# Global test function for invalidate_all tests
@cached(manager=Mock())
def global_test_func():
    return "data"


class TestDecoratorCoverage:
    # Tests for KeyGenerator.default_key_generator with serializer/deserializer and unhashable args
    def test_key_generator_with_serializer(self):
        def custom_serializer(obj):
            if isinstance(obj, dict):
                return json.dumps(obj, sort_keys=True)
            return str(obj)

        def func_with_dict(data: dict):
            return data

        config = CacheConfig(serializer=custom_serializer)
        args = ({"a": 1, "b": 2},)
        kwargs = {}
        key = KeyGenerator.default_key_generator(func_with_dict, args, kwargs, config)
        assert "args:" in key
        assert "func_with_dict" in key

    def test_key_generator_with_unhashable_args_no_serializer(self):
        def func_with_list(data: list):
            return data

        config = CacheConfig()  # No custom serializer
        args = ([1, 2, 3],)
        kwargs = {}
        key = KeyGenerator.default_key_generator(func_with_list, args, kwargs, config)
        assert "args:" in key
        assert "func_with_list" in key
        # Should fall back to str() and hash it

    def test_key_generator_with_unhashable_kwargs_no_serializer(self):
        def func_with_dict_kwarg(**kwargs):
            return kwargs

        config = CacheConfig()  # No custom serializer
        args = ()
        kwargs = {"data": {"a": 1, "b": 2}}
        key = KeyGenerator.default_key_generator(func_with_dict_kwarg, args, kwargs, config)
        assert "kwargs:" in key
        assert "func_with_dict_kwarg" in key
        # Should fall back to str() and hash it

    def test_cached_invalidate_all_error_during_keys(self, mock_cache_manager, mock_cache_adapter):
        global_test_func._cache_manager = mock_cache_manager
        global_test_func._cache_config.adapter = None

        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.side_effect = Exception(
            "Error getting keys"
        )  # Make keys a mock that raises exception

        global_test_func()  # Ensure decorated

        with patch("logging.getLogger") as mock_logger:
            count = global_test_func.invalidate_all()
            assert count == 0
            mock_logger.return_value.warning.assert_called_once()
            assert "Error during invalidate_all" in mock_logger.return_value.warning.call_args[0][0]

    def test_cached_invalidate_all_error_during_delete(
        self, mock_cache_manager, mock_cache_adapter
    ):
        global_test_func._cache_manager = mock_cache_manager
        global_test_func._cache_config.adapter = None

        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.return_value = [
            f"{global_test_func.__module__}.{global_test_func.__qualname__}:args:123"
        ]
        mock_cache_adapter.delete.side_effect = Exception(
            "Error deleting key"
        )  # This should trigger the warning

        global_test_func()  # Ensure decorated

        with patch("logging.getLogger") as mock_logger:
            count = global_test_func.invalidate_all()
            assert count == 0  # No keys successfully deleted
            mock_logger.return_value.warning.assert_called_once()
            assert "Error during invalidate_all" in mock_logger.return_value.warning.call_args[0][0]

    # Tests for pooled decorator's callbacks and retry logic
    def test_pooled_with_callbacks(self, mock_cache_manager):
        mock_on_borrow = Mock()
        mock_on_return = Mock()
        mock_on_error = Mock()

        @pooled(
            manager=mock_cache_manager,
            on_borrow=mock_on_borrow,
            on_return=mock_on_return,
            on_error=mock_on_error,
        )
        def test_func(obj, arg):
            return f"processed_{arg}"

        # Get the mock object that __enter__ returns from the fixture's setup
        mock_pooled_obj = mock_cache_manager.borrow.return_value.__enter__()
        result = test_func("value")
        assert result == "processed_value"
        mock_on_borrow.assert_called_once_with(mock_pooled_obj)
        mock_on_return.assert_called_once_with(mock_pooled_obj)
        mock_on_error.assert_not_called()

    def test_pooled_with_function_error_and_on_error_fallback(self, mock_cache_manager):
        mock_on_error = Mock(return_value="fallback_result")

        @pooled(manager=mock_cache_manager, on_error=mock_on_error)
        def test_func(obj, arg):
            raise ValueError("Function error")

        result = test_func("value")
        assert result == "fallback_result"
        mock_on_error.assert_called_once()
        assert isinstance(mock_on_error.call_args[0][0], ValueError)

    def test_pooled_retry_exhausted_raises_error(self, mock_cache_manager):
        mock_cache_manager.borrow.side_effect = PoolEmptyError("test_adapter", 1.0)

        @pooled(manager=mock_cache_manager, max_retries=0, retry_delay=0.01)  # No retries
        def test_func(obj, arg):
            return f"processed_{arg}"

        with pytest.raises(PoolEmptyError):
            test_func("value")
        assert mock_cache_manager.borrow.call_count == 1  # Only one attempt

    def test_pooled_retry_exhausted_with_on_error_callback(self, mock_cache_manager):
        mock_cache_manager.borrow.side_effect = PoolEmptyError("test_adapter", 1.0)
        mock_on_error = Mock(return_value=None)  # No fallback result

        @pooled(manager=mock_cache_manager, max_retries=0, retry_delay=0.01, on_error=mock_on_error)
        def test_func(obj, arg):
            return f"processed_{arg}"

        with pytest.raises(PoolEmptyError):
            test_func("value")
        mock_on_error.assert_called_once()
        assert isinstance(mock_on_error.call_args[0][0], PoolEmptyError)

    # Tests for invalidate_cache function
    def test_invalidate_cache_by_pattern_success(self, mock_cache_manager, mock_cache_adapter):
        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.return_value = ["user:123", "product:456", "user:789"]
        mock_cache_adapter.delete.return_value = True

        count = invalidate_cache(pattern="user:", manager=mock_cache_manager)
        assert count == 2
        mock_cache_adapter.keys.assert_called_once()
        assert mock_cache_adapter.delete.call_count == 2

    def test_invalidate_cache_by_namespace_success(self, mock_cache_manager, mock_cache_adapter):
        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.return_value = [
            "my_namespace:key1",
            "other_namespace:key2",
            "my_namespace:key3",
        ]
        mock_cache_adapter.delete.return_value = True

        count = invalidate_cache(namespace="my_namespace", manager=mock_cache_manager)
        assert count == 2
        mock_cache_adapter.keys.assert_called_once()
        assert mock_cache_adapter.delete.call_count == 2

    def test_invalidate_cache_error_during_keys(self, mock_cache_manager, mock_cache_adapter):
        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.side_effect = Exception(
            "Error getting keys for invalidation"
        )  # Make keys a mock that raises exception

        with patch("logging.getLogger") as mock_logger:
            count = invalidate_cache(pattern="test:", manager=mock_cache_manager)
            assert count == 0
            mock_logger.return_value.warning.assert_called_once()
            assert (
                "Error during cache invalidation"
                in mock_logger.return_value.warning.call_args[0][0]
            )

    def test_invalidate_cache_error_during_delete(self, mock_cache_manager, mock_cache_adapter):
        mock_cache_manager._get_cache_adapter.return_value = mock_cache_adapter
        mock_cache_adapter.keys.return_value = ["test:key1"]
        mock_cache_adapter.delete.side_effect = Exception("Error deleting key during invalidation")

        with patch("logging.getLogger") as mock_logger:
            count = invalidate_cache(pattern="test:", manager=mock_cache_manager)
            assert count == 0
            mock_logger.return_value.warning.assert_called_once()
            assert (
                "Error during cache invalidation"
                in mock_logger.return_value.warning.call_args[0][0]
            )

    def test_invalidate_cache_direct_function_invalidation_no_invalidate_all(self):
        def plain_func():
            return "data"

        count = invalidate_cache(plain_func)
        assert count == 0
