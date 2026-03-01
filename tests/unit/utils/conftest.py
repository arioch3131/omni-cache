from unittest.mock import patch

import pytest

from omni_cache.adapters.memory.factory import MemoryAdapterFactory
from omni_cache.core.manager import CacheManager


@pytest.fixture
def configured_cache_manager():
    """Create a CacheManager with registered memory adapters."""
    manager = CacheManager()
    manager.register_factory("memory", MemoryAdapterFactory())
    manager.create_adapter(backend="memory", name="default")
    manager.create_adapter(backend="memory", name="memory")
    manager.create_adapter(backend="memory", name="redis")  # Mock redis with memory
    with patch("omni_cache.utils.decorators.get_global_manager", return_value=manager):
        yield manager
