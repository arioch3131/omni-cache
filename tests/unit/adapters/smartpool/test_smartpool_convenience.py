"""
Tests for convenience functions in SmartPool adapter.

This module tests the convenience functions that simplify the creation
of SmartPoolAdapter instances for common use cases.
"""

from unittest.mock import Mock, patch

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.convenience import (
    create_connection_pool,
    create_smartpool_adapter,
)
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter


@pytest.fixture
def mock_factory_function():
    """Mock factory function for testing."""
    return Mock(return_value=Mock())


@pytest.fixture
def mock_connection_factory():
    """Mock connection factory function for testing."""
    mock = Mock()
    mock.return_value = Mock(name="mock_connection")
    return mock


@pytest.fixture
def mock_validate_function():
    """Mock validate function for testing."""
    return Mock(return_value=True)


class TestCreateSmartpoolAdapter:
    """Tests for create_smartpool_adapter function."""

    def test_create_with_default_parameters(self, mock_factory_function, mock_validate_function):
        """Test creating adapter with default parameters."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_smartpool_adapter(mock_factory_function, mock_validate_function)

            # Verify SmartPoolAdapter was called
            mock_adapter_class.assert_called_once()

            # Get the config that was passed
            config = mock_adapter_class.call_args[0][0]

            # Verify default values
            assert config.factory_function == mock_factory_function
            assert config.factory_validate_function == mock_validate_function
            assert config.initial_size == 5
            assert config.max_size == 20
            assert config.min_size == 2
            assert config.memory_preset is None
            assert config.enable_auto_tuning is False

    def test_create_with_custom_parameters(self, mock_factory_function, mock_validate_function):
        """Test creating adapter with custom parameters."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_smartpool_adapter(
                mock_factory_function,
                mock_validate_function,
                initial_size=3,
                max_size=15,
                min_size=1,
                memory_preset="HIGH_THROUGHPUT",
                enable_auto_tuning=True,
            )

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.factory_function == mock_factory_function
            assert config.factory_validate_function == mock_validate_function
            assert config.initial_size == 3
            assert config.max_size == 15
            assert config.min_size == 1
            assert config.memory_preset == "HIGH_THROUGHPUT"
            assert config.enable_auto_tuning is True

    def test_create_with_additional_kwargs(self, mock_factory_function, mock_validate_function):
        """Test creating adapter with additional configuration options."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_smartpool_adapter(
                mock_factory_function,
                mock_validate_function,
                enable_performance_metrics=True,
                auto_tuning_interval=30,
                cleanup_interval=60,
            )

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.factory_function == mock_factory_function
            assert config.factory_validate_function == mock_validate_function
            assert config.enable_performance_metrics is True
            assert config.auto_tuning_interval == 30
            assert config.cleanup_interval == 60

    def test_create_returns_smartpool_adapter(self, mock_factory_function, mock_validate_function):
        """Test that function returns a SmartPoolAdapter instance."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            mock_instance = Mock(spec=SmartPoolAdapter)
            mock_adapter_class.return_value = mock_instance

            result = create_smartpool_adapter(mock_factory_function, mock_validate_function)

            assert result == mock_instance

    def test_config_creation_with_smartpool_adapter_config(
        self, mock_factory_function, mock_validate_function
    ):
        """Test that SmartPoolAdapterConfig is properly created."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapterConfig"
        ) as mock_config_class:
            with patch("omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"):
                mock_config_instance = Mock(spec=SmartPoolAdapterConfig)
                mock_config_class.return_value = mock_config_instance

                create_smartpool_adapter(
                    mock_factory_function, mock_validate_function, initial_size=8
                )

                mock_config_class.assert_called_once_with(
                    factory_function=mock_factory_function,
                    factory_validate_function=mock_validate_function,
                    initial_size=8,
                    max_size=20,
                    min_size=2,
                    memory_preset=None,
                    enable_auto_tuning=False,
                )


class TestCreateConnectionPool:
    """Tests for create_connection_pool function."""

    def test_create_with_default_parameters(self, mock_connection_factory):
        """Test creating connection pool with default parameters."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_connection_pool(mock_connection_factory)

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.name == "connection_pool"
            assert config.factory_function == mock_connection_factory
            assert config.factory_kwargs == {}
            assert config.initial_size == 10
            assert config.max_size == 20
            assert config.memory_preset == "HIGH_THROUGHPUT"
            assert config.enable_auto_tuning is True
            assert config.enable_performance_metrics is True

    def test_create_with_custom_pool_sizes(self, mock_connection_factory):
        """Test creating connection pool with custom pool sizes."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_connection_pool(mock_connection_factory, pool_size=5, max_pool_size=15)

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.initial_size == 5
            assert config.max_size == 15

    def test_create_with_factory_kwargs(self, mock_connection_factory):
        """Test creating connection pool with factory kwargs."""
        factory_kwargs = {"host": "localhost", "port": 5432, "database": "test_db"}

        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_connection_pool(mock_connection_factory, **factory_kwargs)

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.factory_kwargs == factory_kwargs

    def test_create_returns_smartpool_adapter(self, mock_connection_factory):
        """Test that function returns a SmartPoolAdapter instance."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            mock_instance = Mock(spec=SmartPoolAdapter)
            mock_adapter_class.return_value = mock_instance

            result = create_connection_pool(mock_connection_factory)

            assert result == mock_instance

    def test_create_with_mixed_parameters(self, mock_connection_factory):
        """Test creating connection pool with mixed parameters."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_connection_pool(
                mock_connection_factory, pool_size=8, max_pool_size=25, timeout=30, ssl_enabled=True
            )

            mock_adapter_class.assert_called_once()
            config = mock_adapter_class.call_args[0][0]

            assert config.initial_size == 8
            assert config.max_size == 25
            assert config.factory_kwargs == {"timeout": 30, "ssl_enabled": True}

    def test_config_creation_with_smartpool_adapter_config(self, mock_connection_factory):
        """Test that SmartPoolAdapterConfig is properly created for connection pool."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapterConfig"
        ) as mock_config_class:
            with patch("omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"):
                mock_config_instance = Mock(spec=SmartPoolAdapterConfig)
                mock_config_class.return_value = mock_config_instance

                create_connection_pool(mock_connection_factory, pool_size=6, username="admin")

                mock_config_class.assert_called_once_with(
                    name="connection_pool",
                    factory_function=mock_connection_factory,
                    factory_kwargs={"username": "admin"},
                    initial_size=6,
                    max_size=20,
                    memory_preset="HIGH_THROUGHPUT",
                    enable_auto_tuning=True,
                    enable_performance_metrics=True,
                )


class TestConvenienceFunctionsIntegration:
    """Integration tests for convenience functions."""

    def test_both_functions_return_different_configurations(
        self, mock_factory_function, mock_connection_factory, mock_validate_function
    ):
        """Test that both convenience functions return adapters with different configurations."""
        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            # Create standard adapter
            create_smartpool_adapter(mock_factory_function, mock_validate_function)

            # Create connection pool
            create_connection_pool(mock_connection_factory)

            # Verify both adapters were created
            assert mock_adapter_class.call_count == 2

            # Get configurations
            config1 = mock_adapter_class.call_args_list[0][0][0]
            config2 = mock_adapter_class.call_args_list[1][0][0]

            # Verify different configurations
            assert config1.initial_size == 5  # default for create_smartpool_adapter
            assert config2.initial_size == 10  # default for create_connection_pool

            assert config1.enable_auto_tuning is False  # default for create_smartpool_adapter
            assert config2.enable_auto_tuning is True  # forced for create_connection_pool

            assert not hasattr(config1, "name") or config1.name != "connection_pool"
            assert config2.name == "connection_pool"

    def test_functions_with_callable_factory_functions(self, mock_validate_function):
        """Test that functions work with actual callable factory functions."""

        def sample_factory():
            return "sample_object"

        def connection_factory():
            return "connection_object"

        with patch(
            "omni_cache.adapters.smartpool.convenience.SmartPoolAdapter"
        ) as mock_adapter_class:
            create_smartpool_adapter(sample_factory, mock_validate_function)
            create_connection_pool(connection_factory)

            config1 = mock_adapter_class.call_args_list[0][0][0]
            config2 = mock_adapter_class.call_args_list[1][0][0]

            assert config1.factory_function == sample_factory
            assert config2.factory_function == connection_factory

            # Verify factories are callable
            assert callable(config1.factory_function)
            assert callable(config2.factory_function)
