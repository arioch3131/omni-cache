"""
Declares all factories.
"""

from omni_cache.adapters.disk.factory import DiskAdapterFactory
from omni_cache.adapters.memcached.factory import MemcachedAdapterFactory
from omni_cache.adapters.memory.factory import MemoryAdapterFactory
from omni_cache.adapters.redis.factory import RedisAdapterFactory

from .abstract_factory import AbstractFactory
from .factory import (
    create_adapter,
    get_global_registry,
    list_available_backends,
    set_global_registry,
    temporary_factory,
)
from .factory_metadata import FactoryMetadata
from .factory_registry import FactoryRegistry

# Optional SmartPool factory export
SmartPoolAdapterFactory: type[AbstractFactory] | None
try:
    from omni_cache.adapters.smartpool.factory import SmartPoolAdapterFactory
except ImportError:
    SmartPoolAdapterFactory = None

__all__ = [
    # Core classes
    "FactoryMetadata",
    "AbstractFactory",
    "FactoryRegistry",
    # Built-in factories
    "MemoryAdapterFactory",
    "DiskAdapterFactory",
    "MemcachedAdapterFactory",
    "RedisAdapterFactory",
    "SmartPoolAdapterFactory",
    # Global registry functions
    "get_global_registry",
    "set_global_registry",
    # Utility functions
    "temporary_factory",
    "create_adapter",
    "list_available_backends",
]
