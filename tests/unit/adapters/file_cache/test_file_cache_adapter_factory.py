"""
Tests for the FileCacheAdapterFactory.
"""

import pytest

from omni_cache.adapters.file_cache.factory import FileCacheFactory
from omni_cache.adapters.file_cache.file_cache import FileCacheAdapter
from omni_cache.core.interfaces import CacheBackend

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def file_cache_factory():
    """Returns a FileCacheFactory instance."""
    return FileCacheFactory()


class TestFileCacheAdapterFactory:
    """Tests for the FileCacheAdapterFactory."""

    def test_get_default_metadata(self, file_cache_factory):
        """Test that the default metadata is correct."""
        metadata = file_cache_factory._get_default_metadata()
        assert metadata.backend == CacheBackend.FILE_CACHE.value
        assert metadata.factory_class == "FileCacheFactory"
        assert "FileCacheAdapter" in metadata.adapter_types

    def test_create_adapter(self, file_cache_factory, tmp_path):
        """Test that the factory creates a FileCacheAdapter correctly."""
        cache_dir = str(tmp_path / "test_cache")
        config = {"cache_dir": cache_dir}
        adapter = file_cache_factory._create_adapter(config)
        assert adapter is not None
        assert isinstance(adapter, FileCacheAdapter)
        assert adapter._config.cache_dir == cache_dir

    def test_supports_backend(self, file_cache_factory):
        """Test that the factory correctly reports supported backends."""
        assert file_cache_factory.supports(CacheBackend.FILE_CACHE) is True
        assert file_cache_factory.supports("file_cache") is True
        assert file_cache_factory.supports(CacheBackend.MEMORY) is False
        assert file_cache_factory.supports("redis") is False

    def test_get_config_schema(self, file_cache_factory):
        """Test that the config schema is returned correctly."""
        schema = file_cache_factory.get_config_schema()
        assert isinstance(schema, dict)
        assert "cache_dir" in schema["properties"]
        assert "cache_dir" in schema["required"]
