"""
Main cache/pool manager for omni-cache.

This module provides the central CacheManager class that coordinates
all adapters and provides a unified interface for cache and pool operations.
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypeVar, cast

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.exceptions import AdapterNotFoundError
from omni_cache.core.factory_management import AdapterFactoryManager
from omni_cache.core.health_monitoring import HealthMonitor
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
    CacheStats,
    Configurable,
    FactoryInterface,
    KeyValueInterface,
    ManagerInterface,
    PoolInterface,
    PoolStats,
)
from omni_cache.core.routing import CacheRouter

# Type variables
K = TypeVar("K")
V = TypeVar("V")


# pylint: disable=too-many-public-methods,protected-access
class CacheManager(ManagerInterface, KeyValueInterface[K, V], Configurable):
    """
    Main cache and pool manager for omni-cache.

    Provides a unified interface for managing multiple cache and pool adapters,
    with support for routing, statistics aggregation, and health monitoring.
    """

    def __init__(self, config: dict[str, Any] | ManagerConfig | None = None) -> None:
        """
        Initialize the cache manager.

        Args:
            config: Configuration dictionary or ManagerConfig instance
        """
        # Parse configuration
        if isinstance(config, dict):
            self._config = ManagerConfig(**config)
        elif isinstance(config, ManagerConfig):
            self._config = config
        else:
            self._config = ManagerConfig()

        # Setup logging
        self._logger = self._setup_logger()

        # Adapter management
        self._registry = AdapterRegistry()
        self._factory_manager = AdapterFactoryManager(self._logger)

        # Statistics
        self._global_stats: dict[str, CacheStats | PoolStats] = {
            "cache": CacheStats(),
            "pool": PoolStats(),
        }
        self._stats_lock = threading.RLock()

        # Health monitoring
        self._health_monitor = HealthMonitor(self._config, self._registry, self._logger)

        # Routing
        self._router = CacheRouter(self._config, self._registry, self._logger)

        self._logger.info("CacheManager initialized")

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for the manager."""
        logger = logging.getLogger("omni_cache.manager")
        logger.setLevel(getattr(logging, self._config.log_level.upper(), logging.INFO))
        logger.propagate = True  # Ensure propagation to root logger
        return logger

    # Factory management
    def register_factory(self, backend: str | CacheBackend, factory: FactoryInterface) -> None:
        """
        Register a factory for creating adapters.

        Args:
            backend: Backend type this factory supports
            factory: Factory instance
        """
        self._factory_manager.register_factory(backend, factory)

    def create_adapter(
        self, name: str, backend: str | CacheBackend, config: dict[str, Any] | None = None
    ) -> bool:
        """
        Create and register an adapter using a factory.

        Args:
            name: Name to register the adapter under
            backend: Backend type
            config: Configuration for the adapter

        Returns:
            True if successful, False otherwise
        """
        try:
            adapter = self._factory_manager.create_adapter(name, backend, config)
            return self.register_adapter(name, adapter, config)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to create adapter %s: %s", name, e)
            return False

    # ManagerInterface implementation
    def register_adapter(
        self, name: str, adapter: AdapterInterface, config: dict[str, Any] | None = None
    ) -> bool:
        """
        Register an adapter with the manager.

        Args:
            name: Name to register the adapter under
            adapter: The adapter instance
            config: Optional configuration for the adapter

        Returns:
            True if successful, False otherwise
        """
        try:
            if name in self._registry.list_all():
                self._logger.warning("Adapter %s already registered, replacing", name)

            # Auto-connect if configured
            if self._config.auto_connect and not adapter.is_connected():
                if not adapter.connect():
                    self._logger.error("Failed to connect adapter %s", name)
                    return False

            # Register in registry
            self._registry.register(name, adapter, config)

            # Set as default if none set
            if self._config.default_adapter is None:
                self._config.default_adapter = name

            # Start health monitoring if this is the first adapter
            if len(self._registry.list_all()) == 1:
                self._start_health_monitoring()

            self._logger.info("Registered adapter: %s (%s)", name, type(adapter).__name__)
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to register adapter %s: %s", name, e)
            return False

    def get_adapter(self, name: str) -> AdapterInterface | None:
        """
        Get a registered adapter by name.

        Args:
            name: Name of the adapter

        Returns:
            The adapter instance, or None if not found
        """
        return self._registry.get(name)

    def list_adapters(self) -> list[str]:
        """
        List all registered adapter names.

        Returns:
            List of adapter names
        """
        return self._registry.list_all()

    def remove_adapter(self, name: str) -> bool:
        """
        Remove an adapter from the manager.

        Args:
            name: Name of the adapter to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            adapter = self._registry.get(name)

            if adapter:
                # Disconnect adapter
                try:
                    adapter.disconnect()
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.warning("Error disconnecting adapter %s: %s", name, e)

                # Remove from registry
                self._registry.unregister(name)

                # Update default if removed
                if self._config.default_adapter == name:
                    remaining = self._registry.list_all()
                    self._config.default_adapter = remaining[0] if remaining else None

                # Stop health monitoring if no adapters left
                if not self._registry.list_all():
                    self._stop_health_monitoring()

                self._logger.info("Removed adapter: %s", name)
                return True

            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to remove adapter %s: %s", name, e)
            return False

    # Routing
    def add_routing_rule(self, namespace: str, adapter_name: str) -> None:
        """
        Add a routing rule for namespace-based adapter selection.

        Args:
            namespace: Namespace prefix (e.g., "user", "session")
            adapter_name: Target adapter name
        """
        self._router.add_routing_rule(namespace, adapter_name)

    def remove_routing_rule(self, namespace: str) -> bool:
        """
        Remove a routing rule.

        Args:
            namespace: Namespace to remove

        Returns:
            True if rule existed and was removed
        """
        return self._router.remove_routing_rule(namespace)

    def _route_adapter(self, key: K | None = None, adapter_name: str | None = None) -> str | None:
        """
        Determine which adapter to use based on routing rules.

        Args:
            key: Key to route (for namespace extraction)
            adapter_name: Explicit adapter name

        Returns:
            Adapter name to use
        """
        return self._router._route_adapter(key, adapter_name)

    def _get_cache_adapter(
        self, key: K | None = None, adapter_name: str | None = None
    ) -> KeyValueInterface:
        """Get a cache adapter with routing and fallback."""
        return self._router.get_cache_adapter(key, adapter_name)

    def _get_pool_adapter(self, adapter_name: str | None = None) -> PoolInterface:
        """Get a pool adapter with fallback."""
        return self._router.get_pool_adapter(adapter_name)

    def _safe_values_equal(self, value1: object, value2: object) -> bool:
        """Compare values safely, handling DataFrames and other complex types."""
        if value1 is value2:
            return True

        if value1 is None or value2 is None:
            return value1 is value2

        # Standard comparison for other types
        try:
            return bool(value1 == value2)
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    # KeyValueInterface implementation (with routing)
    def get(self, key: K, default: V | None = None, adapter: str | None = None) -> V | None:
        """Get value from cache with automatic adapter routing."""
        try:
            cache_adapter = self._get_cache_adapter(key, adapter)
            result = cache_adapter.get(key, default)

            # Update global stats
            if self._config.enable_global_stats:
                with self._stats_lock:
                    cache_stats = cast(CacheStats, self._global_stats["cache"])
                    if result is not None and not self._safe_values_equal(result, default):
                        cache_stats.hits += 1
                    else:
                        cache_stats.misses += 1
                    cache_stats.update_hit_rate()

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Get operation failed for key %s: %s", key, e)
            return default

    def set(
        self,
        key: K,
        value: V,
        ttl: int | float | None = None,
        adapter: str | None = None,
    ) -> bool:
        """Set value in cache with automatic adapter routing."""
        try:
            cache_adapter = self._get_cache_adapter(key, adapter)
            success = cache_adapter.set(key, value, ttl)

            # Update global stats
            if self._config.enable_global_stats and success:
                with self._stats_lock:
                    cast(CacheStats, self._global_stats["cache"]).sets += 1

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Set operation failed for key %s: %s", key, e)
            return False

    def delete(self, key: K, adapter: str | None = None) -> bool:
        """Delete key from cache with automatic adapter routing."""
        try:
            cache_adapter = self._get_cache_adapter(key, adapter)
            success = cache_adapter.delete(key)

            # Update global stats
            if self._config.enable_global_stats and success:
                with self._stats_lock:
                    cast(CacheStats, self._global_stats["cache"]).deletes += 1

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Delete operation failed for key %s: %s", key, e)
            return False

    def exists(self, key: K, adapter: str | None = None) -> bool:
        """Check if key exists in cache with automatic adapter routing."""
        try:
            cache_adapter = self._get_cache_adapter(key, adapter)
            return cache_adapter.exists(key)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Exists operation failed for key %s: %s", key, e)
            return False

    def clear(self, adapter: str | None = None) -> bool:
        """Clear cache with optional adapter specification."""
        try:
            if adapter:
                cache_adapter = self._registry.get_cache_adapter(adapter)
                if not cache_adapter:
                    raise AdapterNotFoundError(f"Cache adapter not found: {adapter}")
                return cache_adapter.clear()
            # Clear all cache adapters
            success = True
            for name in self._registry.list_cache_adapters():
                cache_adapter = self._registry.get_cache_adapter(name)
                if cache_adapter:
                    success &= cache_adapter.clear()
            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Clear operation failed: %s", e)
            return False

    def keys(self, adapter: str | None = None) -> Iterator[K]:
        """Get keys iterator with optional adapter specification."""
        try:
            if adapter:
                cache_adapter = self._registry.get_cache_adapter(adapter)
                if not cache_adapter:
                    raise AdapterNotFoundError(f"Cache adapter not found: {adapter}")
                return cache_adapter.keys()
            # Return keys from default adapter
            target_adapter = self._config.default_adapter
            if target_adapter:
                cache_adapter = self._registry.get_cache_adapter(target_adapter)
                if cache_adapter:
                    return cache_adapter.keys()

            return iter([])

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Keys operation failed: %s", e)
            return iter([])

    def size(self, adapter: str | None = None) -> int:
        """Get cache size with optional adapter specification."""
        try:
            if adapter:
                cache_adapter = self._registry.get_cache_adapter(adapter)
                if not cache_adapter:
                    return 0
                return cache_adapter.size()
            # Return total size across all cache adapters
            total_size = 0
            for name in self._registry.list_cache_adapters():
                cache_adapter = self._registry.get_cache_adapter(name)
                if cache_adapter:
                    total_size += cache_adapter.size()
            return total_size
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Size operation failed: %s", e)
            return 0

    # PoolInterface implementation
    def get_object_pool(
        self, timeout: float | None = None, adapter: str | None = None
    ) -> Any | None:
        """Get object from pool."""
        try:
            pool_adapter = self._get_pool_adapter(adapter)
            if hasattr(pool_adapter, "_get_pool_object"):
                result = cast(Any | None, cast(Any, pool_adapter)._get_pool_object(timeout))
            else:
                result = pool_adapter.get(timeout)

            # Update global stats
            if self._config.enable_global_stats:
                with self._stats_lock:
                    cast(PoolStats, self._global_stats["pool"]).borrowed += 1

            return result

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Pool get operation failed: %s", e)
            return None

    def put(self, obj: Any, timeout: float | None = None, adapter: str | None = None) -> bool:
        """Return object to pool."""
        try:
            pool_adapter = self._get_pool_adapter(adapter)
            success = pool_adapter.put(obj, timeout)

            # Update global stats
            if self._config.enable_global_stats and success:
                with self._stats_lock:
                    cast(PoolStats, self._global_stats["pool"]).returned += 1

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Pool put operation failed: %s", e)
            return False

    def is_empty(self, adapter: str | None = None) -> bool:
        """Check if pool is empty."""
        try:
            pool_adapter = self._get_pool_adapter(adapter)
            return pool_adapter.is_empty()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Pool is_empty operation failed: %s", e)
            return True

    @contextmanager
    def borrow(self, timeout: float | None = None, adapter: str | None = None) -> Iterator[Any]:
        """Context manager for borrowing objects from pool."""
        obj = self.get_object_pool(timeout, adapter)
        if obj is None:
            raise RuntimeError("No object available from pool")
        borrowed_obj = cast(Any, obj)
        try:
            yield borrowed_obj
        finally:
            self.put(borrowed_obj, adapter=adapter)

    # Health monitoring
    def _start_health_monitoring(self) -> None:
        """Start the health monitoring thread."""
        self._health_monitor.start()

    def _stop_health_monitoring(self) -> None:
        """Stop the health monitoring thread."""
        self._health_monitor.stop()

    # Statistics and monitoring
    def get_global_stats(self) -> dict[str, CacheStats | PoolStats]:
        """Get global statistics across all adapters."""
        with self._stats_lock:
            return {"cache": self._global_stats["cache"], "pool": self._global_stats["pool"]}

    def get_adapter_stats(self, name: str | None = None) -> dict[str, Any]:
        """Get statistics for specific adapter or all adapters."""
        if name:
            return self._registry.get_stats(name) or {}
        stats = {}
        for adapter_name in self._registry.list_all():
            adapter_stats = self._registry.get_stats(adapter_name)
            if adapter_stats:
                stats[adapter_name] = adapter_stats
        return stats

    def reset_global_stats(self) -> bool:
        """Reset global statistics."""
        try:
            with self._stats_lock:
                self._global_stats["cache"] = CacheStats()
                self._global_stats["pool"] = PoolStats()
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to reset global stats: %s", e)
            return False

    # Configuration
    def configure(self, config: dict[str, Any]) -> bool:
        """Update manager configuration."""
        try:
            for key, value in config.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                else:
                    self._config.extra_config[key] = value

            # Reconfigure logger if level changed
            if "log_level" in config:
                self._logger.setLevel(
                    getattr(logging, self._config.log_level.upper(), logging.INFO)
                )

            self._logger.info("Manager configuration updated")
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to update configuration: %s", e)
            return False

    def get_config(self) -> dict[str, Any]:
        """Get current manager configuration."""
        return {
            "default_adapter": self._config.default_adapter,
            "auto_connect": self._config.auto_connect,
            "enable_global_stats": self._config.enable_global_stats,
            "health_check_interval": self._config.health_check_interval,
            "adapter_timeout": self._config.adapter_timeout,
            "log_level": self._config.log_level,
            "namespace_separator": self._config.namespace_separator,
            "enable_routing": self._config.enable_routing,
            "fallback_adapter": self._config.fallback_adapter,
            **self._config.extra_config,
        }

    # Context manager support
    def __enter__(self) -> "CacheManager":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect_all()

    def disconnect_all(self) -> None:
        """Disconnect all adapters and cleanup resources."""
        try:
            self._stop_health_monitoring()

            for name in self._registry.list_all():
                adapter = self._registry.get(name)
                if adapter:
                    try:
                        adapter.disconnect()
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        self._logger.warning("Error disconnecting adapter %s: %s", name, e)

            self._logger.info("Disconnected all adapters")
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error during cleanup: %s", e)

    def __repr__(self) -> str:
        """String representation of the manager."""
        adapters = self._registry.list_all()
        return (
            f"CacheManager(adapters={len(adapters)}, "
            f"default='{self._config.default_adapter}', "
            f"adapters={adapters})"
        )


# pylint: disable=global-statement
# Global manager instance
_global_manager: CacheManager | None = None  # pylint: disable=invalid-name
_global_manager_lock = threading.Lock()


def get_global_manager() -> CacheManager:
    """
    Get the global CacheManager instance.

    Returns:
        Global CacheManager instance
    """
    global _global_manager

    if _global_manager is None:
        with _global_manager_lock:
            if _global_manager is None:
                _global_manager = CacheManager()

    return _global_manager


def set_global_manager(manager: CacheManager) -> None:
    """
    Set the global CacheManager instance.

    Args:
        manager: CacheManager instance to set as global
    """
    global _global_manager

    with _global_manager_lock:
        _global_manager = manager


__all__ = [
    "ManagerConfig",
    "AdapterRegistry",
    "CacheManager",
    "get_global_manager",
    "set_global_manager",
]
