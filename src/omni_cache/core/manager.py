"""
Main cache/pool manager for omni-cache.

This module provides the central CacheManager class that coordinates
all adapters and provides a unified interface for cache and pool operations.
"""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, TypeVar

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


@dataclass
class _LocalStats:
    """Thread-local stats buffer for low-contention global aggregation."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    pool_borrowed: int = 0
    pool_returned: int = 0
    pending_ops: int = 0
    get_counter: int = 0
    set_counter: int = 0
    delete_counter: int = 0
    pool_get_counter: int = 0
    pool_put_counter: int = 0


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
        self._enable_global_stats = self._config.enable_global_stats
        self._default_cache_adapter_ref: KeyValueInterface | None = None
        self._stats_lock = threading.RLock()
        self._global_stats_sample_rate = 1
        self._global_stats_flush_every = 64
        self._stats_local = threading.local()
        self._thread_registry_lock = threading.RLock()
        self._thread_locals: list[_LocalStats] = []
        self._refresh_stats_sampling_config()

        # Health monitoring
        self._health_monitor = HealthMonitor(self._config, self._registry, self._logger)

        # Routing
        self._router = CacheRouter(self._config, self._registry, self._logger)
        self._adapter_cache = self._router._cache_adapter_cache

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
            if isinstance(adapter, KeyValueInterface):
                self._router.register_cache_adapter(name, adapter)
            else:
                self._router.invalidate_cache_adapter(name)

            # Set as default if none set
            if self._config.default_adapter is None:
                self._config.default_adapter = name
            if isinstance(adapter, KeyValueInterface) and self._config.default_adapter == name:
                self._default_cache_adapter_ref = adapter

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
                self._router.invalidate_cache_adapter(name)

                # Update default if removed
                if self._config.default_adapter == name:
                    remaining = self._registry.list_all()
                    self._config.default_adapter = remaining[0] if remaining else None
                    if self._config.default_adapter is not None:
                        self._default_cache_adapter_ref = self._router.get_cached_cache_adapter(
                            self._config.default_adapter
                        )
                    else:
                        self._default_cache_adapter_ref = None

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

    def _resolve_cache_adapter(self, key: K, adapter: str | None) -> KeyValueInterface:
        """Resolve cache adapter with fast paths for common runtime cases."""
        if adapter is not None:
            cached = self._router.get_cached_cache_adapter(adapter)
            if cached is not None:
                return cached
            return self._get_cache_adapter(key, adapter)

        if self._default_cache_adapter_ref is not None and not self._router.has_routing_rules():
            return self._default_cache_adapter_ref
        return self._get_cache_adapter(key, None)

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

    def _refresh_stats_sampling_config(self) -> None:
        """Refresh stats sampling runtime configuration."""
        raw_rate = self._config.extra_config.get("global_stats_sample_rate", 1)
        try:
            rate = int(raw_rate)
        except Exception:  # pylint: disable=broad-exception-caught
            rate = 1
        self._global_stats_sample_rate = max(1, rate)

        raw_flush = self._config.extra_config.get("global_stats_flush_every", 64)
        try:
            flush_every = int(raw_flush)
        except Exception:  # pylint: disable=broad-exception-caught
            flush_every = 64
        self._global_stats_flush_every = max(1, flush_every)

    def _sampled_step_local(self, local: _LocalStats, counter_attr: str) -> int:
        """
        Return sample step for a thread-local counter.

        - 0 => skip this operation (not sampled)
        - N => apply +N to preserve approximate totals
        """
        if self._global_stats_sample_rate <= 1:
            return 1
        counter = getattr(local, counter_attr) + 1
        setattr(local, counter_attr, counter)
        if counter % self._global_stats_sample_rate == 0:
            return self._global_stats_sample_rate
        return 0

    def _get_local_stats(self) -> _LocalStats:
        """Return the current thread stats buffer."""
        local = getattr(self._stats_local, "stats", None)
        if local is None:
            local = _LocalStats()
            self._stats_local.stats = local
            with self._thread_registry_lock:
                self._thread_locals.append(local)
        return local

    def _reset_local_stats(self, local: _LocalStats) -> None:
        """Reset a local stats buffer including sampling counters."""
        local.hits = 0
        local.misses = 0
        local.sets = 0
        local.deletes = 0
        local.pool_borrowed = 0
        local.pool_returned = 0
        local.pending_ops = 0
        local.get_counter = 0
        local.set_counter = 0
        local.delete_counter = 0
        local.pool_get_counter = 0
        local.pool_put_counter = 0

    def _flush_local_stats(self, local: _LocalStats) -> None:
        """Flush a thread-local stats buffer into global stats."""
        if (
            local.hits == 0
            and local.misses == 0
            and local.sets == 0
            and local.deletes == 0
            and local.pool_borrowed == 0
            and local.pool_returned == 0
        ):
            local.pending_ops = 0
            return

        with self._stats_lock:
            cache_stats = self._cache_stats_ref()
            cache_stats.hits += local.hits
            cache_stats.misses += local.misses
            cache_stats.sets += local.sets
            cache_stats.deletes += local.deletes

            pool_stats = self._pool_stats_ref()
            pool_stats.borrowed += local.pool_borrowed
            pool_stats.returned += local.pool_returned

        local.hits = 0
        local.misses = 0
        local.sets = 0
        local.deletes = 0
        local.pool_borrowed = 0
        local.pool_returned = 0
        local.pending_ops = 0

    def _maybe_flush_local_stats(self, local: _LocalStats) -> None:
        """Flush local stats periodically to cap drift with low contention."""
        local.pending_ops += 1
        if local.pending_ops >= self._global_stats_flush_every:
            self._flush_local_stats(local)

    def _flush_all_local_stats(self) -> None:
        """Flush all known local buffers to global stats."""
        with self._thread_registry_lock:
            buffers = list(self._thread_locals)
        for local in buffers:
            self._flush_local_stats(local)

    def _reset_all_local_stats(self) -> None:
        """Reset all known local buffers."""
        with self._thread_registry_lock:
            buffers = list(self._thread_locals)
        for local in buffers:
            self._reset_local_stats(local)

    def _cache_stats_ref(self) -> CacheStats:
        """Typed accessor for cache global stats."""
        stats = self._global_stats["cache"]
        if not isinstance(stats, CacheStats):
            raise TypeError("Invalid cache stats object")
        return stats

    def _pool_stats_ref(self) -> PoolStats:
        """Typed accessor for pool global stats."""
        stats = self._global_stats["pool"]
        if not isinstance(stats, PoolStats):
            raise TypeError("Invalid pool stats object")
        return stats

    # KeyValueInterface implementation (with routing)
    def get(self, key: K, default: V | None = None, adapter: str | None = None) -> V | None:
        """Get value from cache with automatic adapter routing."""
        try:
            if adapter is None:
                if self._default_cache_adapter_ref is not None and not self._router._routing_rules:
                    cache_adapter = self._default_cache_adapter_ref
                else:
                    cache_adapter = self._get_cache_adapter(key, None)
            else:
                cached_adapter = self._adapter_cache.get(adapter)
                if cached_adapter is None:
                    cache_adapter = self._get_cache_adapter(key, adapter)
                else:
                    cache_adapter = cached_adapter
            result = cache_adapter.get(key, default)

            # Update global stats
            if self._enable_global_stats:
                try:
                    local_stats = self._stats_local.stats
                except AttributeError:
                    local_stats = _LocalStats()
                    self._stats_local.stats = local_stats
                    with self._thread_registry_lock:
                        self._thread_locals.append(local_stats)

                sample_rate = self._global_stats_sample_rate
                if sample_rate <= 1:
                    step = 1
                else:
                    counter = local_stats.get_counter + 1
                    if counter >= sample_rate:
                        local_stats.get_counter = 0
                        step = sample_rate
                    else:
                        local_stats.get_counter = counter
                        step = 0

                if step:
                    is_hit = (
                        result is not None
                        if default is None
                        else (result is not None and not self._safe_values_equal(result, default))
                    )
                    if is_hit:
                        local_stats.hits += step
                    else:
                        local_stats.misses += step

                local_stats.pending_ops += 1
                if local_stats.pending_ops >= self._global_stats_flush_every:
                    self._flush_local_stats(local_stats)

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
            if adapter is None:
                if self._default_cache_adapter_ref is not None and not self._router._routing_rules:
                    cache_adapter = self._default_cache_adapter_ref
                else:
                    cache_adapter = self._get_cache_adapter(key, None)
            else:
                cached_adapter = self._adapter_cache.get(adapter)
                if cached_adapter is None:
                    cache_adapter = self._get_cache_adapter(key, adapter)
                else:
                    cache_adapter = cached_adapter
            success = cache_adapter.set(key, value, ttl)

            # Update global stats
            if self._enable_global_stats and success:
                try:
                    local_stats = self._stats_local.stats
                except AttributeError:
                    local_stats = _LocalStats()
                    self._stats_local.stats = local_stats
                    with self._thread_registry_lock:
                        self._thread_locals.append(local_stats)

                sample_rate = self._global_stats_sample_rate
                if sample_rate <= 1:
                    step = 1
                else:
                    counter = local_stats.set_counter + 1
                    if counter >= sample_rate:
                        local_stats.set_counter = 0
                        step = sample_rate
                    else:
                        local_stats.set_counter = counter
                        step = 0

                if step:
                    local_stats.sets += step

                local_stats.pending_ops += 1
                if local_stats.pending_ops >= self._global_stats_flush_every:
                    self._flush_local_stats(local_stats)

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Set operation failed for key %s: %s", key, e)
            return False

    def delete(self, key: K, adapter: str | None = None) -> bool:
        """Delete key from cache with automatic adapter routing."""
        try:
            cache_adapter = self._resolve_cache_adapter(key, adapter)
            success = cache_adapter.delete(key)

            # Update global stats
            if self._enable_global_stats and success:
                local_stats = self._get_local_stats()
                step = self._sampled_step_local(local_stats, "delete_counter")
                if step:
                    local_stats.deletes += step
                self._maybe_flush_local_stats(local_stats)

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
            get_pool_object = getattr(pool_adapter, "_get_pool_object", None)
            if callable(get_pool_object):
                result = get_pool_object(timeout)
            else:
                result = pool_adapter.get(timeout)

            # Update global stats
            if self._enable_global_stats:
                local_stats = self._get_local_stats()
                step = self._sampled_step_local(local_stats, "pool_get_counter")
                if step:
                    local_stats.pool_borrowed += step
                self._maybe_flush_local_stats(local_stats)

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
            if self._enable_global_stats and success:
                local_stats = self._get_local_stats()
                step = self._sampled_step_local(local_stats, "pool_put_counter")
                if step:
                    local_stats.pool_returned += step
                self._maybe_flush_local_stats(local_stats)

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
        try:
            yield obj
        finally:
            self.put(obj, adapter=adapter)

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
        self._flush_all_local_stats()
        with self._stats_lock:
            self._cache_stats_ref().update_hit_rate()
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
            self._reset_all_local_stats()
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
            self._enable_global_stats = self._config.enable_global_stats
            if self._config.default_adapter is not None:
                self._default_cache_adapter_ref = self._router.get_cached_cache_adapter(
                    self._config.default_adapter
                )
            else:
                self._default_cache_adapter_ref = None

            # Reconfigure logger if level changed
            if "log_level" in config:
                self._logger.setLevel(
                    getattr(logging, self._config.log_level.upper(), logging.INFO)
                )
            self._refresh_stats_sampling_config()

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

            self._router.invalidate_cache_adapter()
            self._default_cache_adapter_ref = None
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
