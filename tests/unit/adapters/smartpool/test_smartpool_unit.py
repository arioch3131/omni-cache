"""
Unit tests for SmartPoolAdapter - Initialization and Connection management.

This module contains comprehensive unit tests for the SmartPoolAdapter class,
focusing on initialization, connection management, and basic functionality
using mocks to isolate unit behavior.
"""

import threading
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter
from omni_cache.core.exceptions import ConfigurationError


# Fixtures for testing
@pytest.fixture
def mock_factory_function():
    """Mock factory function for creating test objects."""
    return Mock(return_value=Mock())


@pytest.fixture
def mock_smart_object_manager():
    """Mock SmartObjectManager for unit testing."""
    mock_manager = MagicMock()
    mock_manager.acquire.return_value = (
        Mock(name="mock_id"),
        Mock(name="mock_key"),
        Mock(name="mock_obj"),
    )
    # Corrected: Mock get_basic_stats instead of get_stats
    mock_manager.get_basic_stats.return_value = {
        "pooled_objects": 2,
        "active_objects": 1,
        "total_managed_objects": 3,
        "counters": {
            "hits": 10,
            "misses": 2,
            "creates": 3,
            "reuses": 7,
            "destroys": 0,
            "borrows": 11,
            "releases": 10,
        },
    }
    mock_manager.get_health_status.return_value = {"status": "healthy", "issues": []}
    mock_manager.shutdown.return_value = None
    mock_manager.enable_auto_tuning.return_value = None

    # Mock performance_metrics (initially empty/default)
    mock_perf_metrics = MagicMock()
    mock_perf_metrics.create_snapshot.return_value = Mock(
        timestamp=Mock(isoformat=Mock(return_value="2025-01-01T12:00:00")),
        total_acquisitions=0,
        hit_rate=0.0,
        avg_acquisition_time_ms=0.0,
        min_acquisition_time_ms=0.0,
        max_acquisition_time_ms=0.0,
        p50_acquisition_time_ms=0.0,
        p95_acquisition_time_ms=0.0,
        p99_acquisition_time_ms=0.0,
        avg_lock_wait_time_ms=0.0,
        max_lock_wait_time_ms=0.0,
        lock_contention_rate=0.0,
        acquisitions_per_second=0.0,
        peak_concurrent_acquisitions=0,
        top_keys_by_usage=[],
        slowest_keys=[],
    )
    mock_perf_metrics.get_performance_report.return_value = {
        "trends": {},
        "alerts": [],
        "recommendations": [],
    }
    mock_manager.performance_metrics = mock_perf_metrics
    return mock_manager


@pytest.fixture
def basic_config_dict(mock_factory_function):
    """Basic configuration dictionary for testing."""
    return {
        "factory_function": mock_factory_function,
        "initial_size": 2,
        "max_size": 10,
        "min_size": 1,
        "enable_stats": True,
    }


@pytest.fixture
def smartpool_config(mock_factory_function):
    """SmartPoolAdapterConfig instance for testing."""
    return SmartPoolAdapterConfig(
        factory_function=mock_factory_function,
        initial_size=2,
        max_size=10,
        min_size=1,
        max_size_per_key=2,
        enable_stats=True,
    )


class TestSmartPoolAdapterInitialization:
    """Test SmartPoolAdapter initialization with different configuration types."""

    def test_init_with_dict_config(self, basic_config_dict):
        """Test initialization with dictionary configuration."""
        adapter = SmartPoolAdapter(basic_config_dict)

        assert isinstance(adapter.config, SmartPoolAdapterConfig)
        assert adapter.config.factory_function == basic_config_dict["factory_function"]
        assert adapter.config.initial_size == 2
        assert adapter.config.max_size == 10
        assert adapter.config.min_size == 1
        assert adapter.config.enable_stats is True
        assert adapter._pool is None
        assert adapter._factory is None
        expected_lock_type = type(threading.RLock())
        assert isinstance(adapter._lock, expected_lock_type)
        assert adapter._borrowed_objects == {}

    def test_init_with_smartpool_config(self, smartpool_config):
        """Test initialization with SmartPoolAdapterConfig instance."""
        adapter = SmartPoolAdapter(smartpool_config)

        assert adapter.config is smartpool_config
        assert adapter.config.factory_function == smartpool_config.factory_function
        assert adapter.config.initial_size == 2
        assert adapter._pool is None
        assert adapter._factory is None
        expected_lock_type = type(threading.RLock())
        assert isinstance(adapter._lock, expected_lock_type)
        assert adapter._borrowed_objects == {}

    def test_init_with_none_config(self):
        """Test initialization with None config raises ConfigError."""
        with pytest.raises(
            ConfigurationError, match="Configuration cannot be None for SmartPoolAdapter."
        ):
            SmartPoolAdapter(None)

    @patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", False)
    def test_init_without_smartpool_available(self, smartpool_config):
        """Test initialization fails when SmartPool library is not available."""
        with pytest.raises(ImportError, match="smartpool is not available"):
            SmartPoolAdapter(smartpool_config)

    def test_config_property_access(self, smartpool_config):
        """Test that config property is accessible."""
        adapter = SmartPoolAdapter(smartpool_config)

        assert adapter.config is smartpool_config
        # Test that config is read-only access to _config
        assert adapter.config is adapter._config

    with pytest.raises(
        ConfigurationError,
        match=(
            r"Invalid configuration type: <class 'int'>. "
            r"Expected dict or SmartPoolAdapterConfig."
        ),
    ):
        SmartPoolAdapter(123)  # Pass an integer, which is an invalid type


class TestSmartPoolAdapterConnection:
    """Test SmartPoolAdapter connection and disconnection functionality."""

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_do_connect_success(
        self, mock_manager_class, smartpool_config, mock_smart_object_manager
    ):
        """Test successful connection to SmartPool backend."""
        mock_manager_class.return_value = mock_smart_object_manager

        adapter = SmartPoolAdapter(smartpool_config)
        result = adapter._do_connect()

        assert result is True
        assert adapter._pool is mock_smart_object_manager
        assert adapter._factory is not None

        # Verify SmartObjectManager was created with correct parameters
        mock_manager_class.assert_called_once()
        call_kwargs = mock_manager_class.call_args[1]
        assert "factory" in call_kwargs
        assert "default_config" in call_kwargs
        assert "pool_config" in call_kwargs

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_do_connect_with_auto_tuning(
        self, mock_manager_class, mock_factory_function, mock_smart_object_manager
    ):
        """Test connection with auto-tuning enabled."""
        config = SmartPoolAdapterConfig(
            factory_function=mock_factory_function, enable_auto_tuning=True, auto_tuning_interval=60
        )
        mock_manager_class.return_value = mock_smart_object_manager

        adapter = SmartPoolAdapter(config)
        result = adapter._do_connect()

        assert result is True
        mock_smart_object_manager.enable_auto_tuning.assert_called_once_with(60)

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_do_connect_failure(self, mock_manager_class, smartpool_config):
        """Test connection failure handling."""
        mock_manager_class.side_effect = Exception("Connection failed")

        adapter = SmartPoolAdapter(smartpool_config)
        result = adapter._do_connect()

        assert result is False
        assert adapter._pool is None

    def test_do_disconnect_success(self, smartpool_config, mock_smart_object_manager):
        """Test successful disconnection from SmartPool backend."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter._do_connect()

            # Add some borrowed objects to test cleanup
            adapter._borrowed_objects[123] = ("obj_id", "key", "obj")

            result = adapter._do_disconnect()

            assert result is True
            assert adapter._pool is None
            assert adapter._factory is None
            assert adapter._borrowed_objects == {}
            mock_smart_object_manager.shutdown.assert_called_once()

    def test_do_disconnect_without_connection(self, smartpool_config):
        """Test disconnection when not connected."""
        adapter = SmartPoolAdapter(smartpool_config)

        result = adapter._do_disconnect()

        assert result is True
        assert adapter._pool is None

    def test_do_disconnect_failure(self, smartpool_config, mock_smart_object_manager):
        """Test disconnection failure handling."""
        mock_smart_object_manager.shutdown.side_effect = Exception("Shutdown failed")

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter._do_connect()

            result = adapter._do_disconnect()

            assert result is False

    def test_do_health_check_success(self, smartpool_config, mock_smart_object_manager):
        """Test successful health check."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter._do_connect()

            result = adapter._do_health_check()

            assert result is True
            mock_smart_object_manager.get_health_status.assert_called_once()

    def test_do_health_check_disconnected(self, smartpool_config):
        """Test health check when disconnected."""
        adapter = SmartPoolAdapter(smartpool_config)

        result = adapter._do_health_check()

        assert result is False

    def test_do_health_check_failure(self, smartpool_config, mock_smart_object_manager):
        """Test health check failure handling."""
        mock_smart_object_manager.get_health_status.side_effect = Exception("Health check failed")

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter._do_connect()

            result = adapter._do_health_check()

            assert result is False

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_prepopulate_pool(
        self, mock_manager_class, mock_factory_function, mock_smart_object_manager
    ):
        """Test pool pre-population during connection."""
        config = SmartPoolAdapterConfig(factory_function=mock_factory_function, initial_size=3)
        mock_manager_class.return_value = mock_smart_object_manager

        adapter = SmartPoolAdapter(config)
        adapter._do_connect()

        # Verify release was called initial_size times
        assert mock_smart_object_manager.release.call_count == 3

    @patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager")
    def test_prepopulate_pool_failure(
        self, mock_manager_class, mock_factory_function, mock_smart_object_manager
    ):
        """Test pool pre-population failure handling."""
        config = SmartPoolAdapterConfig(factory_function=mock_factory_function, initial_size=2)
        mock_manager_class.return_value = mock_smart_object_manager
        mock_smart_object_manager.acquire_context.side_effect = Exception("Prepopulate failed")

        adapter = SmartPoolAdapter(config)
        # Should not raise exception, just log warning
        result = adapter._do_connect()

        assert result is True  # Connection should still succeed

    def test_create_memory_config(self, smartpool_config):
        """Test memory configuration creation."""
        adapter = SmartPoolAdapter(smartpool_config)
        memory_config = adapter._create_memory_config()

        assert memory_config.max_objects_per_key == smartpool_config.initial_size
        assert memory_config.ttl_seconds == smartpool_config.max_age_seconds
        assert memory_config.cleanup_interval_seconds == smartpool_config.cleanup_interval
        assert memory_config.enable_background_cleanup == smartpool_config.enable_background_cleanup
        assert (
            memory_config.enable_performance_metrics == smartpool_config.enable_performance_metrics
        )
        assert memory_config.enable_logging is False  # Explicitly disabled

    def test_create_pool_config(self, smartpool_config):
        """Test pool configuration creation."""
        adapter = SmartPoolAdapter(smartpool_config)
        pool_config = adapter._create_pool_config()

        assert pool_config.max_total_objects == smartpool_config.max_size
        assert pool_config.enable_monitoring == smartpool_config.enable_performance_metrics
        assert pool_config.register_atexit is False

    def test_create_factory(self, smartpool_config):
        """Test factory creation with configuration."""
        extra_config = {"reset_func": Mock(), "validate_func": Mock(), "destroy_func": Mock()}
        smartpool_config.extra_config = extra_config

        adapter = SmartPoolAdapter(smartpool_config)
        factory = adapter._create_factory()

        assert factory is not None
        assert factory.factory_func == smartpool_config.factory_function
        assert factory.factory_args == smartpool_config.factory_args
        assert factory.factory_kwargs == smartpool_config.factory_kwargs
        assert factory.auto_wrap == smartpool_config.auto_wrap_objects

    def test_create_factory_with_none_factory_function(self):
        """Test that _create_factory raises ValueError if factory_function is None."""
        config = SmartPoolAdapterConfig(factory_function=None)  # Set factory_function to None
        adapter = SmartPoolAdapter(config)
        with pytest.raises(ValueError, match="Factory function cannot be None."):
            adapter._create_factory()

    def test_do_connect_without_auto_tuning(self, mock_factory_function, mock_smart_object_manager):
        """Test connection when auto-tuning is disabled."""
        config = SmartPoolAdapterConfig(
            factory_function=mock_factory_function, enable_auto_tuning=False
        )
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(config)
            result = adapter._do_connect()

            assert result is True
            mock_smart_object_manager.enable_auto_tuning.assert_not_called()

    def test_do_connect_already_connected(self, smartpool_config, mock_smart_object_manager):
        """Test _do_connect returns True immediately if already connected."""
        adapter = SmartPoolAdapter(smartpool_config)
        adapter._pool = mock_smart_object_manager  # Manually set _pool to simulate connected state

        with (
            patch.object(adapter, "_create_factory") as mock_create_factory,
            patch.object(adapter, "_create_memory_config") as mock_create_memory_config,
            patch.object(adapter, "_create_pool_config") as mock_create_pool_config,
            patch(
                "omni_cache.adapters.smartpool.smartpool.SmartObjectManager"
            ) as mock_smart_object_manager_class,
        ):
            result = adapter._do_connect()

            assert result is True
            mock_create_factory.assert_not_called()
            mock_create_memory_config.assert_not_called()
            mock_create_pool_config.assert_not_called()
            mock_smart_object_manager_class.assert_not_called()
