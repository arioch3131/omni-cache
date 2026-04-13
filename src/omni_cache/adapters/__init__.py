"""
Declares all Adapters.

This module provides all available cache and pool adapters for omni-cache.
Adapters are imported conditionally based on available dependencies.
"""

from typing import Any

from .base.base import BaseAdapter
from .disk import DiskAdapter, DiskAdapterConfig
from .memory import MemoryAdapter, MemoryAdapterConfig

# Always available adapters
__all__ = [
    "BaseAdapter",
    "MemoryAdapter",
    "MemoryAdapterConfig",
    "DiskAdapter",
    "DiskAdapterConfig",
]

# Conditionally import Redis adapter
RedisAdapter: Any = None
RedisAdapterConfig: Any = None
try:
    from .redis import RedisAdapter, RedisAdapterConfig

    __all__.extend(["RedisAdapter", "RedisAdapterConfig"])
    _ = RedisAdapterConfig
    HAS_REDIS_ADAPTER = True

except ImportError:
    HAS_REDIS_ADAPTER = False

# Conditionally import Memcached adapter
MemcachedAdapter: Any = None
MemcachedAdapterConfig: Any = None
try:
    from .memcached import MemcachedAdapter, MemcachedAdapterConfig

    __all__.extend(["MemcachedAdapter", "MemcachedAdapterConfig"])
    _ = MemcachedAdapterConfig
    HAS_MEMCACHED_ADAPTER = True

except ImportError:
    HAS_MEMCACHED_ADAPTER = False

# Conditionally import SmartPool adapter (if available)
SmartPoolAdapter: Any = None
SmartPoolAdapterConfig: Any = None
try:
    from .smartpool import SmartPoolAdapter, SmartPoolAdapterConfig

    __all__.extend(["SmartPoolAdapter", "SmartPoolAdapterConfig"])
    _ = SmartPoolAdapterConfig
    HAS_SMARTPOOL_ADAPTER = True

except ImportError:
    HAS_SMARTPOOL_ADAPTER = False

# Export availability flags for runtime checks
__all__.extend(
    [
        "HAS_REDIS_ADAPTER",
        "HAS_MEMCACHED_ADAPTER",
        "HAS_SMARTPOOL_ADAPTER",
    ]
)


def list_available_adapters() -> dict[str, type[Any]]:
    """
    List all available adapter classes.

    Returns:
        Dict[str, type]: Mapping of adapter names to adapter classes
    """
    adapters: dict[str, type[Any]] = {
        "memory": MemoryAdapter,
        "disk": DiskAdapter,
    }

    if HAS_REDIS_ADAPTER:
        adapters["redis"] = RedisAdapter

    if HAS_MEMCACHED_ADAPTER:
        adapters["memcached"] = MemcachedAdapter

    if HAS_SMARTPOOL_ADAPTER:
        adapters["smartpool"] = SmartPoolAdapter

    return adapters


def get_adapter_info() -> dict[str, dict[str, Any]]:
    """
    Get information about all available adapters.

    Returns:
        Dict[str, dict]: Information about each available adapter
    """
    info = {}

    # Memory adapter (always available)
    info["memory"] = {
        "class": "MemoryAdapter",
        "backend": "memory",
        "description": "In-memory cache using Python dictionaries",
        "dependencies": [],
        "features": ["ttl", "eviction_policies", "thread_safe", "size_limits"],
    }

    # Disk adapter (always available)
    info["disk"] = {
        "class": "DiskAdapter",
        "backend": "disk",
        "description": "Disk-backed cache (SQLite index + binary files)",
        "dependencies": [],
        "features": ["persistent", "ttl", "renew_on_hit", "thread_safe"],
    }

    # Redis adapter (conditional)
    if HAS_REDIS_ADAPTER:
        info["redis"] = {
            "class": "RedisAdapter",
            "backend": "redis",
            "description": "Redis-based distributed cache",
            "dependencies": ["redis"],
            "features": [
                "distributed",
                "persistent",
                "ttl",
                "atomic_operations",
                "connection_pooling",
                "serialization",
                "thread_safe",
            ],
        }

    # Memcached adapter (conditional)
    if HAS_MEMCACHED_ADAPTER:
        info["memcached"] = {
            "class": "MemcachedAdapter",
            "backend": "memcached",
            "description": "Memcached-based distributed cache",
            "dependencies": ["pymemcache"],
            "features": [
                "distributed",
                "ttl",
                "connection_pooling",
                "serialization",
                "thread_safe",
            ],
        }

    # SmartPool adapter (conditional)
    if HAS_SMARTPOOL_ADAPTER:
        info["smartpool"] = {
            "class": "SmartPoolAdapter",
            "backend": "adaptive",
            "description": "Adaptive memory pool for object reuse",
            "dependencies": ["smartpool"],
            "features": [
                "adaptive_sizing",
                "object_lifecycle",
                "health_checking",
                "performance_monitoring",
                "thread_safe",
            ],
        }

    return info
