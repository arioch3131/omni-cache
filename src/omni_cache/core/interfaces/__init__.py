"""Interfaces for omni-cache."""

from .adapter_interface import AdapterInterface
from .async_key_value_interface import AsyncKeyValueInterface
from .async_pool_interface import AsyncPoolInterface
from .enum_dataclasses import CacheBackend, CacheStats, PoolStats
from .factory_interface import FactoryInterface
from .interfaces import AnyAdapter, CacheAdapter, Configurable, PoolAdapter, Serializable
from .key_value_interface import KeyValueInterface
from .manager_interface import ManagerInterface
from .pool_interface import PoolInterface
from .statistic_interface import StatisticsInterface

__all__ = [
    # Enums
    "CacheBackend",
    # Data classes
    "CacheStats",
    "PoolStats",
    # Main interfaces
    "KeyValueInterface",
    "PoolInterface",
    "AdapterInterface",
    "StatisticsInterface",
    "FactoryInterface",
    "ManagerInterface",
    # Async interfaces
    "AsyncKeyValueInterface",
    "AsyncPoolInterface",
    # Protocols
    "Serializable",
    "Configurable",
    # Type aliases
    "CacheAdapter",
    "PoolAdapter",
    "AnyAdapter",
]
