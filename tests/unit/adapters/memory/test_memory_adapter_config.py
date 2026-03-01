"""
Tests for MemoryAdapterConfig class behavior and validation.
"""

import pytest

from omni_cache.adapters.memory import MemoryAdapterConfig
from omni_cache.core.interfaces import CacheBackend


# Configuration Tests
class TestMemoryAdapterConfiguration:
    """Test MemoryAdapterConfig behavior and validation."""

    def test_default_configuration_values(self):
        """Test that default configuration values are set correctly."""
        config = MemoryAdapterConfig()

        assert config.name == "default"
        assert config.backend == CacheBackend.MEMORY
        assert config.max_size is None
        assert config.default_ttl is None
        assert config.cleanup_interval == 60.0
        assert config.eviction_policy == "lru"
        assert config.enable_stats is True

    def test_custom_configuration_values(self):
        """Test custom configuration parameter assignment."""
        config = MemoryAdapterConfig(
            name="custom_cache",
            max_size=500,
            default_ttl=300.0,
            cleanup_interval=30.0,
            eviction_policy="fifo",
            enable_stats=False,
        )

        assert config.name == "custom_cache"
        assert config.max_size == 500
        assert config.default_ttl == 300.0
        assert config.cleanup_interval == 30.0
        assert config.eviction_policy == "fifo"
        assert config.enable_stats is False

    def test_backend_always_set_to_memory(self):
        """Test that backend is always set to MEMORY regardless of input."""
        config = MemoryAdapterConfig(backend="redis")  # Should be overridden
        assert config.backend == CacheBackend.MEMORY

    @pytest.mark.parametrize("eviction_policy", ["lru", "fifo", "random"])
    def test_valid_eviction_policies(self, eviction_policy: str):
        """Test that valid eviction policies are accepted."""
        config = MemoryAdapterConfig(eviction_policy=eviction_policy)
        assert config.eviction_policy == eviction_policy


if __name__ == "__main__":
    pytest.main([__file__])
