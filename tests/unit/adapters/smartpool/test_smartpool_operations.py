"""
Unit tests for SmartPoolAdapter operations - Basic pool operations and standard interface.

This module contains comprehensive unit tests for the SmartPoolAdapter pool operations,
including size, is_empty, clear, get, and put methods, using mocks to isolate
unit behavior and test error handling.
"""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter
from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper
from omni_cache.core.exceptions import AdapterNotConnectedError


# Fixtures for testing
@pytest.fixture
def mock_factory_function():
    """Mock factory function for creating test objects."""
    return Mock(return_value=Mock())


@pytest.fixture
def mock_smart_object_manager():
    """Mock SmartObjectManager for unit testing."""
    mock_manager = MagicMock()
    mock_manager.acquire.return_value = ("mock_id_123", "mock_key_456", Mock(name="mock_obj"))
    mock_manager.get_basic_stats.return_value = {
        "counters": {
            "pooled_objects": 3,
            "active_objects": 2,
            "total_pooled_objects": 5,
            "hits": 15,
            "misses": 3,
            "creates": 5,
            "reuses": 10,
            "destroys": 1,
            "borrows": 18,
            "releases": 16,
        }
    }
    mock_manager.get_health_status.return_value = {"status": "healthy", "issues": []}
    mock_manager.shutdown.return_value = None
    mock_manager.release.return_value = None
    return mock_manager


@pytest.fixture
def smartpool_config(mock_factory_function):
    """SmartPoolAdapterConfig instance for testing."""
    return SmartPoolAdapterConfig(
        factory_function=mock_factory_function,
        initial_size=0,  # Prevent prepopulation in tests
        max_size=10,
        min_size=1,
        enable_stats=True,
        name="test_adapter",
    )


@pytest.fixture
def connected_adapter(smartpool_config, mock_smart_object_manager):
    """Connected SmartPoolAdapter instance for testing."""
    with patch(
        "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
        return_value=mock_smart_object_manager,
    ):
        adapter = SmartPoolAdapter(smartpool_config)
        adapter.connect()  # Changed from _do_connect()
        yield adapter


@pytest.fixture
def disconnected_adapter(smartpool_config):
    """Disconnected SmartPoolAdapter instance for testing."""
    return SmartPoolAdapter(smartpool_config)


class TestSmartPoolAdapterBasicOperations:
    """Test basic pool operations: size, is_empty, clear."""

    def test_size_connected_success(self, connected_adapter, mock_smart_object_manager):
        """Test size() returns correct total when connected."""
        # Set up mock stats
        mock_smart_object_manager.get_basic_stats.return_value = {
            "pooled_objects": 3,
            "active_objects": 2,
            "total_pooled_objects": 5,
        }

        result = connected_adapter.size()

        assert result == 5  # pooled + active
        mock_smart_object_manager.get_basic_stats.assert_called_once()

    def test_size_connected_zero(self, connected_adapter, mock_smart_object_manager):
        """Test size() returns zero when pool is empty."""
        mock_smart_object_manager.get_basic_stats.return_value = {
            "pooled_objects": 0,
            "active_objects": 0,
            "total_pooled_objects": 0,
        }

        result = connected_adapter.size()

        assert result == 0

    def test_size_disconnected(self, disconnected_adapter):
        """Test size() raises AdapterNotConnectedError when adapter is not connected."""
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.size()

    def test_size_internal_exception(self, connected_adapter, mock_smart_object_manager):
        """Test _size_internal handles exceptions gracefully."""
        mock_smart_object_manager.get_stats.side_effect = Exception("Stats error")

        result = connected_adapter.size()

        assert result == 0

    def test_size_internal_missing_keys(self, connected_adapter, mock_smart_object_manager):
        """Test _size_internal handles missing stats keys."""
        mock_smart_object_manager.get_stats.return_value = {}

        result = connected_adapter.size()

        assert result == 0  # 0 + 0 when keys are missing

    def test_is_empty_true_no_objects(self, connected_adapter, mock_smart_object_manager):
        """Test is_empty() returns True when no objects in pool."""
        mock_smart_object_manager.get_basic_stats.return_value = {
            "pooled_objects": 0,
            "active_objects": 0,
            "total_pooled_objects": 0,
        }

        result = connected_adapter.is_empty()

        assert result is True

    def test_is_empty_false_with_objects(self, connected_adapter, mock_smart_object_manager):
        """Test is_empty() returns False when objects exist."""
        mock_smart_object_manager.get_basic_stats.return_value = {
            "pooled_objects": 2,
            "active_objects": 1,
            "total_pooled_objects": 3,
        }

        result = connected_adapter.is_empty()

        assert result is False

    def test_is_empty_disconnected(self, disconnected_adapter):
        """Test is_empty() raises AdapterNotConnectedError when adapter is not connected."""
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.is_empty()

    def test_is_empty_internal_exception(
        self, connected_adapter, mock_smart_object_manager, caplog
    ):
        """Test _is_empty_internal handles exceptions gracefully."""
        mock_smart_object_manager.get_basic_stats.side_effect = Exception("Stats error")

        with caplog.at_level(logging.ERROR):
            result = connected_adapter._is_empty_internal()

        assert result is True  # Default to True on error
        assert "Error checking if pool is empty: Stats error" in caplog.text

    def test_clear_success(self, connected_adapter, mock_smart_object_manager):
        """Test clear() successfully clears the pool."""
        # Add some borrowed objects to test cleanup
        test_obj = Mock()
        connected_adapter._borrowed_objects[id(test_obj)] = ("obj_id", "key", "obj")

        # Mock initial stats for tracking
        mock_smart_object_manager.get_basic_stats.return_value = {
            "active_objects": 2,
            "pooled_objects": 3,
            "total_pooled_objects": 5,
        }

        result = connected_adapter.clear()

        assert result is True
        mock_smart_object_manager.shutdown.assert_called_once()
        assert connected_adapter._borrowed_objects == {}

    def test_clear_disconnected(self, disconnected_adapter):
        """Test clear() raises AdapterNotConnectedError when adapter is not connected."""
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.clear()

    def test_clear_internal_exception(self, connected_adapter, mock_smart_object_manager):
        """Test _clear_internal handles exceptions gracefully."""
        mock_smart_object_manager.shutdown.side_effect = Exception("Shutdown error")

        result = connected_adapter.clear()

        assert result is False

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_clear_recreates_pool(
        self, mock_manager_class, connected_adapter, mock_smart_object_manager
    ):
        """Test clear() recreates the pool after shutdown."""
        mock_manager_class.return_value = mock_smart_object_manager
        mock_smart_object_manager.get_basic_stats.return_value = {
            "active_objects": 1,
            "pooled_objects": 2,
            "total_pooled_objects": 3,
        }

        result = connected_adapter.clear()

        assert result is True
        # Verify new pool was created (shutdown + new instance)
        assert mock_manager_class.call_count >= 1


class TestSmartPoolAdapterStandardInterface:
    """Test standard pool interface: get and put methods."""

    def test_get_success(self, connected_adapter, mock_smart_object_manager):
        """Test get() successfully retrieves an object."""
        mock_obj = Mock(name="test_object")
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        result = connected_adapter.get()

        assert result is not None
        assert isinstance(result, AutoWeakRefWrapper)
        assert result._obj is mock_obj

        # Verify object is tracked
        assert id(result) in connected_adapter._borrowed_objects
        mock_smart_object_manager.acquire.assert_called_once()

    def test_get_with_args_kwargs(self, connected_adapter, mock_smart_object_manager):
        """Test get() passes args and kwargs to SmartPool acquire."""
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        result = connected_adapter.get("arg1", "arg2", param1="value1", param2="value2")

        assert result is not None
        mock_smart_object_manager.acquire.assert_called_once_with(
            "arg1", "arg2", param1="value1", param2="value2"
        )

    def test_get_uses_config_defaults(self, connected_adapter, mock_smart_object_manager):
        """Test get() uses config defaults when no args provided."""
        connected_adapter.config.factory_args = ("default_arg",)
        connected_adapter.config.factory_kwargs = {"default_key": "default_value"}
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        result = connected_adapter.get()

        assert result is not None
        mock_smart_object_manager.acquire.assert_called_once_with(
            "default_arg", default_key="default_value"
        )

    def test_get_kwargs_override_config(self, connected_adapter, mock_smart_object_manager):
        """Test get() kwargs override config kwargs."""
        connected_adapter.config.factory_kwargs = {"param": "config_value", "other": "unchanged"}
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        result = connected_adapter.get(param="override_value")

        assert result is not None
        expected_kwargs = {"param": "override_value", "other": "unchanged"}
        mock_smart_object_manager.acquire.assert_called_once_with(**expected_kwargs)

    def test_get_disconnected_raises_error(self, disconnected_adapter):
        """Test get() raises AdapterNotConnectedError when not connected."""
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.get()

    def test_get_pool_empty_returns_none(self, connected_adapter, mock_smart_object_manager):
        """Test get() returns None when pool is empty."""
        mock_smart_object_manager.acquire.return_value = 0  # SmartPool returns 0 for empty

        result = connected_adapter.get()

        assert result is None

    def test_get_internal_exception_returns_none(
        self, connected_adapter, mock_smart_object_manager
    ):
        """Test _get_internal handles exceptions and returns None."""
        mock_smart_object_manager.acquire.side_effect = Exception("Acquire error")

        result = connected_adapter.get()

        assert result is None

    def test_get_wrapping_disabled(self, smartpool_config, mock_smart_object_manager):
        """Test get() without object wrapping."""
        smartpool_config.auto_wrap_objects = False

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()  # Changed from _do_connect()

            mock_obj = Mock()
            mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

            result = adapter.get()

            # Should return the object directly, not wrapped
            assert result is mock_obj
            assert not isinstance(result, AutoWeakRefWrapper)

    def test_put_success(self, connected_adapter, mock_smart_object_manager):
        """Test put() successfully returns an object to the pool."""
        # First get an object
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)
        retrieved_obj = connected_adapter.get()

        # Now put it back
        result = connected_adapter.put(retrieved_obj)

        assert result is True
        mock_smart_object_manager.release.assert_called_once_with("obj_id", "key", mock_obj)

        # Verify object is no longer tracked
        assert id(retrieved_obj) not in connected_adapter._borrowed_objects

    def test_put_untracked_object_fails(self, connected_adapter, mock_smart_object_manager):
        """Test put() fails for untracked objects."""
        untracked_obj = Mock()

        result = connected_adapter.put(untracked_obj)

        assert result is False
        mock_smart_object_manager.release.assert_not_called()

    def test_put_disconnected_returns_false(self, disconnected_adapter):
        """Test put() raises AdapterNotConnectedError when adapter is not connected."""
        mock_obj = Mock()

        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.put(mock_obj)

    def test_put_internal_exception_returns_false(
        self, connected_adapter, mock_smart_object_manager
    ):
        """Test _put_internal handles exceptions and returns False."""
        # Get an object first
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)
        retrieved_obj = connected_adapter.get()

        # Make release fail
        mock_smart_object_manager.release.side_effect = Exception("Release error")

        result = connected_adapter.put(retrieved_obj)

        assert result is False

    def test_get_put_cycle(self, connected_adapter, mock_smart_object_manager):
        """Test complete get-put cycle."""
        mock_obj = Mock(name="cycled_object")
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        # Get object
        retrieved_obj = connected_adapter.get()
        assert retrieved_obj is not None
        assert isinstance(retrieved_obj, AutoWeakRefWrapper)
        assert len(connected_adapter._borrowed_objects) == 1

        # Put object back
        result = connected_adapter.put(retrieved_obj)
        assert result is True
        assert len(connected_adapter._borrowed_objects) == 0

        # Verify correct calls
        mock_smart_object_manager.acquire.assert_called_once()
        mock_smart_object_manager.release.assert_called_once_with("obj_id", "key", mock_obj)

    def test_borrow_release_exception(self, connected_adapter, mock_smart_object_manager, caplog):
        """Test borrow context manager handles exceptions during release gracefully."""
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)
        mock_smart_object_manager.release.side_effect = Exception("Simulated borrow release error")

        with caplog.at_level(logging.ERROR):
            with connected_adapter.borrow() as borrowed_obj:
                assert borrowed_obj is not None
                # No explicit action needed, just ensure context manager exits

        # Verify that an error was logged and no exception was propagated from release
        assert "Error releasing object: Simulated borrow release error" in caplog.text
        mock_smart_object_manager.acquire.assert_called_once()
        mock_smart_object_manager.release.assert_called_once_with("obj_id", "key", mock_obj)

    def test_multiple_get_put_tracking(self, connected_adapter, mock_smart_object_manager):
        """Test tracking multiple borrowed objects."""
        # Setup multiple acquire results
        objects = [
            ("id1", "key1", Mock(name="obj1")),
            ("id2", "key2", Mock(name="obj2")),
            ("id3", "key3", Mock(name="obj3")),
        ]
        mock_smart_object_manager.acquire.side_effect = objects

        # Get multiple objects
        retrieved_objs = []
        for _ in range(3):
            obj = connected_adapter.get()
            retrieved_objs.append(obj)

        assert len(connected_adapter._borrowed_objects) == 3

        # Put back middle object
        result = connected_adapter.put(retrieved_objs[1])
        assert result is True
        assert len(connected_adapter._borrowed_objects) == 2

        # Verify correct release call
        mock_smart_object_manager.release.assert_called_with("id2", "key2", objects[1][2])

    def test_timeout_parameter_ignored(self, connected_adapter, mock_smart_object_manager):
        """Test that timeout parameter is ignored (not passed to SmartPool)."""
        mock_obj = Mock()
        mock_smart_object_manager.acquire.return_value = ("obj_id", "key", mock_obj)

        # Get with timeout
        result = connected_adapter.get(timeout=30.0)
        assert result is not None

        # Put with timeout
        success = connected_adapter.put(result, timeout=30.0)
        assert success is True

        # Verify timeout was not passed to SmartPool methods
        mock_smart_object_manager.acquire.assert_called_once_with()
        mock_smart_object_manager.release.assert_called_once_with("obj_id", "key", mock_obj)

    def test_internal_operations_pool_none(self, disconnected_adapter, caplog):
        """Test all internal operations behavior when _pool is None."""
        # Test _size_internal returns 0
        size_result = disconnected_adapter._size_internal()
        assert size_result == 0

        # Test _is_empty_internal returns True
        is_empty_result = disconnected_adapter._is_empty_internal()
        assert is_empty_result is True

        # Test _clear_internal returns False
        clear_result = disconnected_adapter._clear_internal()
        assert clear_result is False

        # Test _get_internal raises AdapterNotConnectedError
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter._get_internal()

        # Test _put_internal returns False
        mock_obj = Mock()
        put_result = disconnected_adapter._put_internal(mock_obj)
        assert put_result is False

        # Test _prepopulate_pool logs error when _pool is None
        disconnected_adapter._factory = Mock()  # Mock factory to bypass factory check
        with caplog.at_level(logging.ERROR):
            disconnected_adapter._prepopulate_pool()

        assert "Pool not initialized for pre-population." in caplog.text

        # Test get_performance_metrics returns error when _pool is None
        performance_result = disconnected_adapter.get_performance_metrics()
        assert performance_result == {"error": "Pool not initialized"}

        # Test get_dashboard_summary returns error when _pool is None
        dashboard_result = disconnected_adapter.get_dashboard_summary()
        assert dashboard_result == {"error": "Pool not initialized", "status": "disconnected"}

        # Test get_health_report returns disconnected status when _pool is None
        health_result = disconnected_adapter.get_health_report()
        assert health_result == {"status": "disconnected", "issues": ["Pool not initialized"]}

        # Test enable_performance_monitoring returns False when _pool is None
        with caplog.at_level(logging.ERROR):
            monitoring_result = disconnected_adapter.enable_performance_monitoring()

        assert monitoring_result is False
        assert "Cannot enable performance monitoring: pool not initialized" in caplog.text

        # Test get_detailed_smartpool_stats returns error when _pool is None
        detailed_stats_result = disconnected_adapter.get_detailed_smartpool_stats()
        assert detailed_stats_result == {"error": "Pool not initialized"}

    def test_internal_operations_factory_none(
        self, connected_adapter, mock_smart_object_manager, caplog
    ):
        """Test internal operations behavior when _factory is None."""
        # Ensure _pool is not None but set _factory to None
        connected_adapter._pool = mock_smart_object_manager
        connected_adapter._factory = None

        # Test _clear_internal returns False and logs error when _factory is None
        with caplog.at_level(logging.ERROR):
            clear_result = connected_adapter._clear_internal()

        assert clear_result is False
        assert "Factory not initialized for clear operation." in caplog.text

        # Test _prepopulate_pool logs error when _factory is None
        with caplog.at_level(logging.ERROR):
            connected_adapter._prepopulate_pool()

        assert "Factory not initialized for pre-population." in caplog.text
