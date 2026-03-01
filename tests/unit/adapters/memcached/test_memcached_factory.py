"""Tests for Memcached adapter factory."""

import pytest

from omni_cache.adapters.memcached.factory import MemcachedAdapterFactory
from omni_cache.core.exceptions import FactoryCreationError, InvalidConfigurationError
from omni_cache.core.interfaces import CacheBackend


class TestMemcachedAdapterFactory:
    """Unit tests for MemcachedAdapterFactory."""

    def test_factory_metadata_backend(self):
        factory = MemcachedAdapterFactory()
        metadata = factory.get_metadata()
        assert metadata.backend == CacheBackend.MEMCACHED.value
        assert "pymemcache" in metadata.dependencies

    def test_create_adapter(self):
        factory = MemcachedAdapterFactory()

        def _always_available():
            return []

        factory._validate_dependencies = _always_available
        adapter = factory.create({"host": "localhost", "port": 11211})
        assert adapter is not None

    def test_create_fails_when_adapter_unavailable(self, monkeypatch):
        factory = MemcachedAdapterFactory()
        factory._validate_dependencies = lambda: []
        monkeypatch.setattr(
            "omni_cache.adapters.memcached.factory.MEMCACHED_ADAPTER_AVAILABLE",
            False,
        )

        with pytest.raises(FactoryCreationError):
            factory.create({"host": "localhost", "port": 11211})

    def test_invalid_serialization_method_is_rejected(self):
        factory = MemcachedAdapterFactory()
        factory._validate_dependencies = lambda: []

        with pytest.raises(InvalidConfigurationError):
            factory.create(
                {
                    "host": "localhost",
                    "port": 11211,
                    "serialization_method": "pickle",
                }
            )

    def test_create_adapter_handles_enum_backend_when_unavailable(self, monkeypatch):
        factory = MemcachedAdapterFactory()
        factory._metadata.backend = CacheBackend.MEMCACHED
        monkeypatch.setattr(
            "omni_cache.adapters.memcached.factory.MEMCACHED_ADAPTER_AVAILABLE",
            False,
        )

        with pytest.raises(FactoryCreationError):
            factory._create_adapter({"host": "localhost", "port": 11211})
