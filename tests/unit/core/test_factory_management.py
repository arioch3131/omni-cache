"""
Unit tests for AdapterFactoryManager using pytest.

This module provides comprehensive test coverage for the factory management
functionality, including registration, creation, error handling, and logging.
"""

import logging
from unittest.mock import Mock, patch

import pytest

from omni_cache.core.exceptions import ConfigurationError
from omni_cache.core.factory_management import AdapterFactoryManager
from omni_cache.core.interfaces import AdapterInterface, CacheBackend, FactoryInterface


class TestAdapterFactoryManager:
    """Test suite for AdapterFactoryManager class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def factory_manager(self, mock_logger):
        """Create an AdapterFactoryManager instance for testing."""
        return AdapterFactoryManager(mock_logger)

    @pytest.fixture
    def mock_factory(self):
        """Create a mock factory for testing."""
        factory = Mock(spec=FactoryInterface)
        factory.create.return_value = Mock(spec=AdapterInterface)
        return factory

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter for testing."""
        return Mock(spec=AdapterInterface)

    def test_init_creates_factory_manager_with_logger(self, mock_logger):
        """Test that AdapterFactoryManager initializes correctly with a logger."""
        manager = AdapterFactoryManager(mock_logger)

        assert manager._logger is mock_logger
        assert isinstance(manager._factories, dict)
        assert len(manager._factories) == 0

    def test_init_creates_empty_factories_dict(self, factory_manager):
        """Test that initialization creates an empty factories dictionary."""
        assert isinstance(factory_manager._factories, dict)
        assert len(factory_manager._factories) == 0

    def test_register_factory_with_string_backend(self, factory_manager, mock_factory, mock_logger):
        """Test registering a factory with a string backend."""
        backend = "memory"

        factory_manager.register_factory(backend, mock_factory)

        assert backend in factory_manager._factories
        assert factory_manager._factories[backend] is mock_factory
        mock_logger.info.assert_called_once_with("Registered factory for backend: %s", backend)

    def test_register_factory_with_cache_backend_enum(
        self, factory_manager, mock_factory, mock_logger
    ):
        """Test registering a factory with a CacheBackend enum."""
        backend = CacheBackend.MEMORY

        factory_manager.register_factory(backend, mock_factory)

        expected_key = backend.value
        assert expected_key in factory_manager._factories
        assert factory_manager._factories[expected_key] is mock_factory
        mock_logger.info.assert_called_once_with("Registered factory for backend: %s", expected_key)

    def test_register_factory_overwrites_existing_factory(self, factory_manager, mock_logger):
        """Test that registering a factory overwrites an existing one for the same backend."""
        backend = "memory"
        factory1 = Mock(spec=FactoryInterface)
        factory2 = Mock(spec=FactoryInterface)

        # Register first factory
        factory_manager.register_factory(backend, factory1)
        assert factory_manager._factories[backend] is factory1

        # Register second factory (should overwrite)
        factory_manager.register_factory(backend, factory2)
        assert factory_manager._factories[backend] is factory2

        # Should have logged twice
        assert mock_logger.info.call_count == 2

    def test_create_adapter_with_string_backend_success(
        self, factory_manager, mock_factory, mock_adapter
    ):
        """Test successful adapter creation with string backend."""
        backend = "memory"
        name = "test_adapter"
        config = {"key": "value"}

        mock_factory.create.return_value = mock_adapter
        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend, config)

        assert result is mock_adapter
        mock_factory.create.assert_called_once_with(config)

    def test_create_adapter_with_cache_backend_enum_success(
        self, factory_manager, mock_factory, mock_adapter
    ):
        """Test successful adapter creation with CacheBackend enum."""
        backend = CacheBackend.REDIS
        name = "test_adapter"
        config = {"host": "localhost"}

        mock_factory.create.return_value = mock_adapter
        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend, config)

        assert result is mock_adapter
        mock_factory.create.assert_called_once_with(config)

    def test_create_adapter_with_none_config_uses_empty_dict(
        self, factory_manager, mock_factory, mock_adapter
    ):
        """Test that None config is converted to empty dictionary."""
        backend = "memory"
        name = "test_adapter"

        mock_factory.create.return_value = mock_adapter
        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend, None)

        assert result is mock_adapter
        mock_factory.create.assert_called_once_with({})

    def test_create_adapter_with_no_config_uses_empty_dict(
        self, factory_manager, mock_factory, mock_adapter
    ):
        """Test that missing config parameter defaults to empty dictionary."""
        backend = "memory"
        name = "test_adapter"

        mock_factory.create.return_value = mock_adapter
        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend)

        assert result is mock_adapter
        mock_factory.create.assert_called_once_with({})

    def test_create_adapter_raises_configuration_error_for_unregistered_backend(
        self, factory_manager, mock_logger
    ):
        """Test that ConfigurationError is raised for unregistered backend."""
        backend = "unknown"
        name = "test_adapter"

        with pytest.raises(
            ConfigurationError, match="No factory registered for backend: unknown"
        ) as exc_info:
            factory_manager.create_adapter(name, backend)

        mock_logger.error.assert_called_once_with(
            "Failed to create adapter %s: %s", name, exc_info.value
        )

    def test_create_adapter_logs_and_reraises_factory_creation_error(
        self, factory_manager, mock_factory, mock_logger
    ):
        """Test that factory creation errors are logged and re-raised."""
        backend = "memory"
        name = "test_adapter"
        config = {"key": "value"}

        # Make factory.create raise an exception
        creation_error = ValueError("Factory creation failed")
        mock_factory.create.side_effect = creation_error
        factory_manager.register_factory(backend, mock_factory)

        with pytest.raises(ValueError, match="Factory creation failed"):
            factory_manager.create_adapter(name, backend, config)

        mock_logger.error.assert_called_once_with(
            "Failed to create adapter %s: %s", name, creation_error
        )

    def test_create_adapter_logs_and_reraises_configuration_error(
        self, factory_manager, mock_logger
    ):
        """Test that ConfigurationError is logged and re-raised."""
        backend = "nonexistent"
        name = "test_adapter"

        with pytest.raises(ConfigurationError) as exc_info:
            factory_manager.create_adapter(name, backend)

        mock_logger.error.assert_called_once_with(
            "Failed to create adapter %s: %s", name, exc_info.value
        )

    def test_multiple_backend_types_can_be_registered(self, factory_manager, mock_logger):
        """Test that multiple different backend types can be registered."""
        memory_factory = Mock(spec=FactoryInterface)
        redis_factory = Mock(spec=FactoryInterface)

        factory_manager.register_factory("memory", memory_factory)
        factory_manager.register_factory(CacheBackend.REDIS, redis_factory)

        assert len(factory_manager._factories) == 2
        assert factory_manager._factories["memory"] is memory_factory
        assert factory_manager._factories[CacheBackend.REDIS.value] is redis_factory
        assert mock_logger.info.call_count == 2

    def test_backend_enum_value_conversion(self, factory_manager, mock_factory):
        """Test that CacheBackend enum values are properly converted to strings."""
        backend = CacheBackend.SMARTPOOL
        factory_manager.register_factory(backend, mock_factory)

        # Should be stored with string key
        assert backend.value in factory_manager._factories
        assert factory_manager._factories[backend.value] is mock_factory

    def test_create_adapter_handles_complex_config(
        self, factory_manager, mock_factory, mock_adapter
    ):
        """Test adapter creation with complex configuration objects."""
        backend = "memory"
        name = "complex_adapter"
        config = {
            "host": "localhost",
            "port": 6379,
            "database": 0,
            "options": {"timeout": 30, "retry_attempts": 3},
            "features": ["compression", "encryption"],
        }

        mock_factory.create.return_value = mock_adapter
        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend, config)

        assert result is mock_adapter
        mock_factory.create.assert_called_once_with(config)

    def test_error_handling_preserves_original_exception_chain(
        self, factory_manager, mock_factory, mock_logger
    ):
        """Test that exception chaining is preserved during error handling."""
        backend = "memory"
        name = "test_adapter"

        original_error = ValueError("Original error")
        chained_error = RuntimeError("Chained error")
        chained_error.__cause__ = original_error

        mock_factory.create.side_effect = chained_error
        factory_manager.register_factory(backend, mock_factory)

        with pytest.raises(RuntimeError) as exc_info:
            factory_manager.create_adapter(name, backend)

        assert exc_info.value.__cause__ is original_error

    @patch("omni_cache.core.factory_management.logging")
    def test_integration_with_real_logging(self, mock_logging_module):
        """Test integration with real logging module."""
        real_logger = logging.getLogger("test_factory_manager")
        manager = AdapterFactoryManager(real_logger)

        # Should not raise any exceptions
        assert manager._logger is real_logger
        assert isinstance(manager._factories, dict)

    def test_concurrent_registration_safety(self, factory_manager):
        """Test that factory registration works correctly with different factory instances."""
        factory1 = Mock(spec=FactoryInterface)
        factory2 = Mock(spec=FactoryInterface)
        factory3 = Mock(spec=FactoryInterface)

        # Register multiple factories rapidly
        factory_manager.register_factory("backend1", factory1)
        factory_manager.register_factory("backend2", factory2)
        factory_manager.register_factory("backend3", factory3)

        # All should be registered correctly
        assert len(factory_manager._factories) == 3
        assert factory_manager._factories["backend1"] is factory1
        assert factory_manager._factories["backend2"] is factory2
        assert factory_manager._factories["backend3"] is factory3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def factory_manager(self, mock_logger):
        """Create an AdapterFactoryManager instance for testing."""
        return AdapterFactoryManager(mock_logger)

    def test_empty_string_backend_registration(self, factory_manager, mock_logger):
        """Test registration with empty string backend."""
        backend = ""
        factory = Mock(spec=FactoryInterface)

        factory_manager.register_factory(backend, factory)

        assert "" in factory_manager._factories
        assert factory_manager._factories[""] is factory
        mock_logger.info.assert_called_once_with("Registered factory for backend: %s", "")

    def test_create_adapter_with_empty_string_backend(self, factory_manager, mock_logger):
        """Test adapter creation with empty string backend."""
        backend = ""
        name = "test_adapter"

        with pytest.raises(ConfigurationError, match="No factory registered for backend: "):
            factory_manager.create_adapter(name, backend)

    def test_factory_that_returns_none(self, factory_manager, mock_logger):
        """Test behavior when factory returns None instead of adapter."""
        backend = "memory"
        name = "test_adapter"
        factory = Mock(spec=FactoryInterface)
        factory.create.return_value = None

        factory_manager.register_factory(backend, factory)

        result = factory_manager.create_adapter(name, backend)
        assert result is None  # Should return what factory returns

    def test_create_adapter_with_very_long_backend_name(self, factory_manager):
        """Test adapter creation with very long backend name."""
        backend = "a" * 1000  # Very long backend name
        name = "test_adapter"

        mock_factory = Mock(spec=FactoryInterface)
        adapter = Mock(spec=AdapterInterface)
        mock_factory.create.return_value = adapter

        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend)
        assert result is adapter

    def test_special_characters_in_backend_name(self, factory_manager, mock_logger):
        """Test registration and creation with special characters in backend name."""
        backend = "backend-with_special.chars@123"
        name = "test_adapter"

        mock_factory = Mock(spec=FactoryInterface)
        adapter = Mock(spec=AdapterInterface)
        mock_factory.create.return_value = adapter

        factory_manager.register_factory(backend, mock_factory)

        result = factory_manager.create_adapter(name, backend)
        assert result is adapter
        mock_logger.info.assert_called_once_with("Registered factory for backend: %s", backend)
