"""
Main cache/pool manager for omni-cache.

This module provides the central CacheManager class that coordinates
all adapters and provides a unified interface for cache and pool operations.
"""

import copy
import threading
from dataclasses import dataclass, field
from typing import Any, TypeVar

from omni_cache.core.interfaces import (
    AdapterInterface,
    KeyValueInterface,
    PoolInterface,
)

# Type variables
K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


@dataclass
class ManagerConfig:
    """Configuration for the CacheManager."""

    default_adapter: str | None = None
    auto_connect: bool = True
    enable_global_stats: bool = True
    health_check_interval: float = 60.0
    adapter_timeout: float = 5.0
    log_level: str = "INFO"
    namespace_separator: str = ":"
    enable_routing: bool = True
    fallback_adapter: str | None = None
    extra_config: dict[str, Any] = field(default_factory=dict)


class AdapterRegistry:
    """Thread-safe registry for managing adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, AdapterInterface] = {}
        self._cache_adapters: dict[str, KeyValueInterface] = {}
        self._pool_adapters: dict[str, PoolInterface] = {}
        self._adapter_configs: dict[str, dict[str, Any]] = {}
        self._adapter_stats: dict[str, dict[str, Any]] = {}
        self._lock = threading.RWLock() if hasattr(threading, "RWLock") else threading.RLock()

    def register(
        self, name: str, adapter: AdapterInterface, config: dict[str, Any] | None = None
    ) -> None:
        """Register an adapter."""
        with self._lock:
            self._adapters[name] = adapter

            # Categorize adapter type
            if isinstance(adapter, KeyValueInterface):
                self._cache_adapters[name] = adapter
            if isinstance(adapter, PoolInterface):
                self._pool_adapters[name] = adapter

            # Store configuration
            if config:
                self._adapter_configs[name] = copy.deepcopy(config)

    def unregister(self, name: str) -> bool:
        """Unregister an adapter."""
        with self._lock:
            removed = False

            if name in self._adapters:
                del self._adapters[name]
                removed = True

            if name in self._cache_adapters:
                del self._cache_adapters[name]

            if name in self._pool_adapters:
                del self._pool_adapters[name]

            if name in self._adapter_configs:
                del self._adapter_configs[name]

            if name in self._adapter_stats:
                del self._adapter_stats[name]

            return removed

    def get(self, name: str) -> AdapterInterface | None:
        """Get an adapter by name."""
        with self._lock:
            return self._adapters.get(name)

    def get_cache_adapter(self, name: str) -> KeyValueInterface | None:
        """Get a cache adapter by name."""
        with self._lock:
            return self._cache_adapters.get(name)

    def get_pool_adapter(self, name: str) -> PoolInterface | None:
        """Get a pool adapter by name."""
        with self._lock:
            return self._pool_adapters.get(name)

    def list_all(self) -> list[str]:
        """List all registered adapter names."""
        with self._lock:
            return list(self._adapters.keys())

    def list_cache_adapters(self) -> list[str]:
        """List cache adapter names."""
        with self._lock:
            return list(self._cache_adapters.keys())

    def list_pool_adapters(self) -> list[str]:
        """List pool adapter names."""
        with self._lock:
            return list(self._pool_adapters.keys())

    def get_stats(self, name: str) -> dict[str, Any] | None:
        """Get adapter statistics."""
        with self._lock:
            adapter = self._adapters.get(name)
            if adapter and hasattr(adapter, "get_stats") and callable(adapter.get_stats):
                stats = adapter.get_stats()
                return stats.__dict__ if stats else None
            return None
