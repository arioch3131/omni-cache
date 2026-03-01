"""
Tests for the factory functions.
"""

import pytest

from omni_cache.core.exceptions.factory_exceptions import FactoryNotFoundError
from omni_cache.core.factories import factory
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.factories.factory_registry import FactoryRegistry


class DummyFactory(AbstractFactory):
    """Minimal concrete factory for helper tests."""

    def __init__(self, backend: str):
        self._backend = backend
        super().__init__()

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=self._backend,
            factory_class="DummyFactory",
            description="Dummy test factory",
            dependencies=[],
            adapter_types=["cache"],
        )

    def _setup_config_validators(self) -> None:
        return None

    def _create_adapter(self, config):
        return object()


class TestFactoryFunctions:
    def test_get_global_registry(self):
        # Ensure _global_registry is initially None for this test
        factory._global_registry = None
        registry = factory.get_global_registry()
        assert isinstance(registry, FactoryRegistry)
        assert factory._global_registry is not None

    def test_set_global_registry(self):
        new_registry = FactoryRegistry()
        factory.set_global_registry(new_registry)
        assert factory.get_global_registry() is new_registry

    def test_create_adapter_memory(self):
        adapter = factory.create_adapter(backend="memory", config={})
        from omni_cache.adapters.memory import MemoryAdapter

        assert isinstance(adapter, MemoryAdapter)

    def test_create_adapter_unsupported(self):
        with pytest.raises(FactoryNotFoundError):
            factory.create_adapter(backend="unsupported", config={})

    def test_list_available_backends(self):
        backends = factory.list_available_backends()
        assert isinstance(backends, list)
        assert "memory" in backends

    def test_create_adapter_with_none_registry(self):
        # Ensure _global_registry is initialized for this test
        factory._global_registry = FactoryRegistry()
        adapter = factory.create_adapter(backend="memory", config={}, registry=None)
        from omni_cache.adapters.memory import MemoryAdapter

        assert isinstance(adapter, MemoryAdapter)

    def test_list_available_backends_with_none_registry(self):
        # Ensure _global_registry is initialized for this test
        factory._global_registry = FactoryRegistry()
        backends = factory.list_available_backends(registry=None)
        assert isinstance(backends, list)
        assert "memory" in backends

    def test_create_adapter_with_explicit_registry(self):
        registry = FactoryRegistry()
        adapter = factory.create_adapter(backend="memory", config={}, registry=registry)
        from omni_cache.adapters.memory import MemoryAdapter

        assert isinstance(adapter, MemoryAdapter)

    def test_list_available_backends_with_explicit_registry(self):
        registry = FactoryRegistry()
        backends = factory.list_available_backends(registry=registry)
        assert isinstance(backends, list)
        assert "memory" in backends

    def test_temporary_factory_unregisters_when_no_existing_factory(self):
        registry = FactoryRegistry()
        factory.set_global_registry(registry)
        temporary = DummyFactory("temp_backend")

        assert registry.get_factory("temp_backend") is None

        with factory.temporary_factory(temporary):
            assert registry.get_factory("temp_backend") is temporary

        assert registry.get_factory("temp_backend") is None

    def test_temporary_factory_restores_existing_factory(self):
        registry = FactoryRegistry()
        factory.set_global_registry(registry)
        existing = DummyFactory("restore_backend")
        temporary = DummyFactory("restore_backend")

        registry.register(existing)
        assert registry.get_factory("restore_backend") is existing

        with factory.temporary_factory(temporary):
            assert registry.get_factory("restore_backend") is temporary

        assert registry.get_factory("restore_backend") is existing

    def test_get_global_registry_double_check_lock_inner_false_branch(self, monkeypatch):
        factory._global_registry = None

        class FakeLock:
            def __enter__(self):
                factory._global_registry = FactoryRegistry()
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        monkeypatch.setattr(factory, "_global_registry_lock", FakeLock())

        registry = factory.get_global_registry()
        assert isinstance(registry, FactoryRegistry)
