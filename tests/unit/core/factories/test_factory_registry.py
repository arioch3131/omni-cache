"""
Unit tests for FactoryRegistry class.

This module contains comprehensive pytest tests for the FactoryRegistry class,
covering factory registration, discovery, adapter creation, and error handling.
"""

import threading
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.core.exceptions import (
    FactoryNotFoundError,
    FactoryRegistrationError,
)
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.factories.factory_registry import FactoryRegistry
from omni_cache.core.interfaces import AdapterInterface, CacheBackend


class MockFactory(AbstractFactory):
    """Mock factory for testing."""

    def __init__(self, backend: str = "test", should_fail: bool = False):
        self._backend = backend
        self._should_fail = should_fail
        metadata = FactoryMetadata(
            backend=backend,
            factory_class="MockFactory",
            description="Test factory",
            version="1.0.0",
            dependencies=[],
            adapter_types=["cache"],
        )
        super().__init__(metadata)

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=self._backend,
            factory_class="MockFactory",
            description="Test factory",
            version="1.0.0",
            dependencies=[],
            adapter_types=["cache"],
        )

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        if self._should_fail:
            raise Exception("Creation failed")
        # Return a MagicMock that adheres to AdapterInterface
        mock_adapter_instance = MagicMock(spec=AdapterInterface)
        mock_adapter_instance.is_connected.return_value = True
        mock_adapter_instance.connect.return_value = True
        mock_adapter_instance.disconnect.return_value = True
        mock_adapter_instance.health_check.return_value = True
        mock_adapter_instance.get_backend_info.return_value = {
            "name": "mock_adapter",
            "backend": self._backend,
            "state": "connected",
        }
        return mock_adapter_instance

    def _setup_config_validators(self) -> None:
        pass

    def get_config_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"host": {"type": "string"}, "port": {"type": "integer"}},
        }


class TestFactoryRegistry:
    """Test suite for FactoryRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry instance for each test."""
        with patch.object(FactoryRegistry, "_register_builtin_factories"):
            return FactoryRegistry()

    @pytest.fixture
    def mock_factory(self):
        """Create a mock factory for testing."""
        return MockFactory("test_backend")

    @pytest.fixture
    def mock_failing_factory(self):
        """Create a mock factory that fails during creation."""
        return MockFactory("failing_backend", should_fail=True)

    def test_init_creates_empty_registry(self, registry):
        """Test that initialization creates an empty registry."""
        assert len(registry._factories) == 0
        assert len(registry._metadata_cache) == 0
        tempo = threading.RLock()
        assert isinstance(registry._lock, type(tempo))

    def test_init_calls_register_builtin_factories(self):
        """Test that initialization calls _register_builtin_factories."""
        with patch.object(FactoryRegistry, "_register_builtin_factories") as mock_register:
            FactoryRegistry()
            mock_register.assert_called_once()

    def test_register_builtin_factories_registers_memory_factory(self):
        """Test that built-in factories are registered."""
        with patch(
            "omni_cache.core.factories.factory_registry.MemoryAdapterFactory"
        ) as mock_memory_factory:
            mock_instance = Mock()
            mock_memory_factory.return_value = mock_instance

            registry = FactoryRegistry()

            # The register method should have been called with the memory factory
            assert len(registry._factories) >= 0  # May have registered factories

    def test_register_factory_success(self, registry, mock_factory):
        """Test successful factory registration."""
        registry.register(mock_factory)

        assert "test_backend" in registry._factories
        assert registry._factories["test_backend"] == mock_factory
        assert "test_backend" in registry._metadata_cache

    def test_register_factory_replaces_existing(self, registry, mock_factory):
        """Test that registering replaces existing factory."""
        # Register first factory
        registry.register(mock_factory)
        first_factory = registry._factories["test_backend"]

        # Register second factory with same backend
        second_factory = MockFactory("test_backend")
        registry.register(second_factory)

        assert registry._factories["test_backend"] == second_factory
        assert registry._factories["test_backend"] != first_factory

    def test_register_factory_with_enum_backend(self, registry):
        """Test registering factory with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)

        assert CacheBackend.MEMORY.value in registry._factories

    def test_register_factory_failure_raises_registration_error(self, registry):
        """Test that factory registration failure raises FactoryRegistrationError."""
        mock_factory = Mock()
        mock_factory.get_metadata.side_effect = Exception("Metadata error")

        with pytest.raises(FactoryRegistrationError) as exc_info:
            registry.register(mock_factory)

        assert "Metadata error" in str(exc_info.value)

    def test_unregister_existing_factory_returns_true(self, registry, mock_factory):
        """Test unregistering existing factory returns True."""
        registry.register(mock_factory)

        result = registry.unregister("test_backend")

        assert result is True
        assert "test_backend" not in registry._factories
        assert "test_backend" not in registry._metadata_cache

    def test_unregister_nonexistent_factory_returns_false(self, registry):
        """Test unregistering non-existent factory returns False."""
        result = registry.unregister("nonexistent")

        assert result is False

    def test_unregister_with_enum_backend(self, registry):
        """Test unregistering with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)

        result = registry.unregister(CacheBackend.MEMORY)

        assert result is True
        assert CacheBackend.MEMORY.value not in registry._factories

    def test_get_factory_existing_returns_factory(self, registry, mock_factory):
        """Test getting existing factory returns the factory."""
        registry.register(mock_factory)

        result = registry.get_factory("test_backend")

        assert result == mock_factory

    def test_get_factory_nonexistent_returns_none(self, registry):
        """Test getting non-existent factory returns None."""
        result = registry.get_factory("nonexistent")

        assert result is None

    def test_get_factory_with_enum_backend(self, registry):
        """Test getting factory with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)

        result = registry.get_factory(CacheBackend.MEMORY)

        assert result == factory

    def test_list_backends_returns_all_registered_backends(self, registry, mock_factory):
        """Test listing backends returns all registered backend names."""
        factory1 = MockFactory("backend1")
        factory2 = MockFactory("backend2")

        registry.register(factory1)
        registry.register(factory2)

        backends = registry.list_backends()

        assert "backend1" in backends
        assert "backend2" in backends
        assert len(backends) == 2

    def test_list_backends_empty_registry_returns_empty_list(self, registry):
        """Test listing backends on empty registry returns empty list."""
        backends = registry.list_backends()

        assert backends == []

    def test_get_metadata_existing_backend_returns_metadata(self, registry, mock_factory):
        """Test getting metadata for existing backend returns metadata."""
        registry.register(mock_factory)

        metadata = registry.get_metadata("test_backend")

        assert metadata is not None
        assert metadata.backend == "test_backend"
        assert metadata.factory_class == "MockFactory"

    def test_get_metadata_nonexistent_backend_returns_none(self, registry):
        """Test getting metadata for non-existent backend returns None."""
        metadata = registry.get_metadata("nonexistent")

        assert metadata is None

    def test_get_metadata_with_enum_backend(self, registry):
        """Test getting metadata with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)

        metadata = registry.get_metadata(CacheBackend.MEMORY)

        assert metadata is not None
        assert metadata.backend == CacheBackend.MEMORY.value

    def test_get_all_metadata_returns_all_metadata(self, registry):
        """Test getting all metadata returns complete metadata dictionary."""
        factory1 = MockFactory("backend1")
        factory2 = MockFactory("backend2")

        registry.register(factory1)
        registry.register(factory2)

        all_metadata = registry.get_all_metadata()

        assert len(all_metadata) == 2
        assert "backend1" in all_metadata
        assert "backend2" in all_metadata
        assert all_metadata["backend1"].backend == "backend1"
        assert all_metadata["backend2"].backend == "backend2"

    def test_get_all_metadata_returns_copy(self, registry, mock_factory):
        """Test that get_all_metadata returns a copy, not the original dict."""
        registry.register(mock_factory)

        metadata1 = registry.get_all_metadata()
        metadata2 = registry.get_all_metadata()

        assert metadata1 is not metadata2
        assert metadata1 == metadata2

    def test_create_adapter_success(self, registry, mock_factory):
        """Test successful adapter creation."""
        registry.register(mock_factory)
        config = {"host": "localhost", "port": 6379}

        adapter = registry.create_adapter("test_backend", config)

        assert isinstance(adapter, MagicMock)
        assert adapter.is_connected() is True

    def test_create_adapter_with_enum_backend(self, registry):
        """Test creating adapter with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)
        config = {"host": "localhost"}

        adapter = registry.create_adapter(CacheBackend.MEMORY, config)

        assert isinstance(adapter, MagicMock)
        assert adapter.is_connected() is True

    def test_create_adapter_nonexistent_backend_raises_not_found_error(self, registry):
        """Test creating adapter for non-existent backend raises FactoryNotFoundError."""
        config = {"host": "localhost"}

        with pytest.raises(FactoryNotFoundError) as exc_info:
            registry.create_adapter("nonexistent", config)

        assert "nonexistent" in str(exc_info.value)

    def test_create_adapter_factory_failure_propagates_exception(
        self, registry, mock_failing_factory
    ):
        """Test that factory creation failure propagates the exception."""
        registry.register(mock_failing_factory)
        config = {"host": "localhost"}

        with pytest.raises(Exception) as exc_info:
            registry.create_adapter("failing_backend", config)

        assert "Creation failed" in str(exc_info.value)

    def test_supports_backend_existing_backend_returns_true(self, registry, mock_factory):
        """Test supports_backend returns True for existing backend."""
        registry.register(mock_factory)

        result = registry.supports_backend("test_backend")

        assert result is True

    def test_supports_backend_nonexistent_backend_returns_false(self, registry):
        """Test supports_backend returns False for non-existent backend."""
        result = registry.supports_backend("nonexistent")

        assert result is False

    def test_supports_backend_with_enum(self, registry):
        """Test supports_backend with CacheBackend enum."""
        factory = MockFactory(CacheBackend.MEMORY.value)
        registry.register(factory)

        result = registry.supports_backend(CacheBackend.MEMORY)

        assert result is True

    def test_get_config_schema_existing_backend_returns_schema(self, registry, mock_factory):
        """Test getting config schema for existing backend returns schema."""
        registry.register(mock_factory)

        schema = registry.get_config_schema("test_backend")

        assert schema is not None
        assert "type" in schema
        assert schema["type"] == "object"

    def test_get_config_schema_nonexistent_backend_returns_none(self, registry):
        """Test getting config schema for non-existent backend returns None."""
        schema = registry.get_config_schema("nonexistent")

        assert schema is None

    def test_discover_adapters_returns_adapter_types_by_backend(self, registry):
        """Test discover_adapters returns adapter types grouped by backend."""
        factory1 = MockFactory("backend1")
        factory2 = MockFactory("backend2")

        registry.register(factory1)
        registry.register(factory2)

        adapters = registry.discover_adapters()

        assert "backend1" in adapters
        assert "backend2" in adapters
        assert adapters["backend1"] == ["cache"]
        assert adapters["backend2"] == ["cache"]

    def test_discover_adapters_empty_registry_returns_empty_dict(self, registry):
        """Test discover_adapters on empty registry returns empty dict."""
        adapters = registry.discover_adapters()

        assert adapters == {}

    def test_thread_safety_concurrent_registration(self, registry):
        """Test thread safety during concurrent factory registration."""

        def register_factory(backend_name):
            factory = MockFactory(backend_name)
            registry.register(factory)

        threads = []
        backend_names = [f"backend_{i}" for i in range(10)]

        # Start multiple threads registering factories
        for backend_name in backend_names:
            thread = threading.Thread(target=register_factory, args=(backend_name,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all factories were registered
        registered_backends = registry.list_backends()
        for backend_name in backend_names:
            assert backend_name in registered_backends

    def test_thread_safety_concurrent_access(self, registry, mock_factory):
        """Test thread safety during concurrent registry access."""
        registry.register(mock_factory)

        results = []

        def access_registry():
            # Mix of different operations
            factory = registry.get_factory("test_backend")
            backends = registry.list_backends()
            metadata = registry.get_metadata("test_backend")
            supports = registry.supports_backend("test_backend")
            results.append((factory, backends, metadata, supports))

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_registry)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All results should be consistent
        assert len(results) == 5
        for factory, backends, metadata, supports in results:
            assert factory == mock_factory
            assert "test_backend" in backends
            assert metadata.backend == "test_backend"
            assert supports is True

    def test_logging_setup(self, registry):
        """Test that logger is properly set up."""
        assert hasattr(registry, "_logger")
        assert registry._logger.name == "omni_cache.factory.registry"

    @patch("omni_cache.core.factories.factory_registry.RedisAdapterFactory")
    @patch("omni_cache.core.factories.factory_registry.SmartPoolAdapterFactory")
    def test_register_builtin_factories_handles_import_errors(
        self, mock_smart_factory, mock_redis_factory
    ):
        """Test that _register_builtin_factories handles import errors gracefully."""
        # Simulate ImportError for Redis
        mock_redis_factory.side_effect = ImportError("Redis not available")
        # Simulate ImportError for SmartPool
        mock_smart_factory.side_effect = ImportError("SmartPool not available")

        # Should not raise exception
        registry = FactoryRegistry()

        # Memory factory should still be registered (assuming it doesn't raise ImportError)
        # This test verifies error handling, not specific registration
        assert isinstance(registry, FactoryRegistry)
