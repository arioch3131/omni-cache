"""Tests for Memcached adapter configuration."""

from omni_cache.adapters.memcached.config import MemcachedAdapterConfig
from omni_cache.core.interfaces import CacheBackend


class TestMemcachedAdapterConfig:
    """Tests for MemcachedAdapterConfig behavior."""

    def test_default_backend_is_memcached(self):
        config = MemcachedAdapterConfig()
        assert config.backend == CacheBackend.MEMCACHED
        assert config.host == "localhost"
        assert config.port == 11211
