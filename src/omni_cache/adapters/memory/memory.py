"""
Memory adapter implementation for omni-cache.

This module provides a simple in-memory cache adapter using Python dictionaries.
Supports TTL (time-to-live) functionality and provides a reference implementation
for other adapters.
"""

import random
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from typing import Any, TypeVar, cast

from omni_cache.adapters.base import BaseCacheAdapter
from omni_cache.adapters.memory.config import CacheItem, MemoryAdapterConfig
from omni_cache.core.interfaces import KeyValueInterface

# Type variables
K = TypeVar("K")
V = TypeVar("V")


# pylint: disable=too-many-ancestors
class MemoryAdapter(BaseCacheAdapter, KeyValueInterface[K, V]):
    """
    In-memory cache adapter using Python dictionaries.

    Features:
    - Thread-safe operations
    - TTL (time-to-live) support
    - Size limits with configurable eviction policies
    - Automatic cleanup of expired items
    - LRU, FIFO, and random eviction policies
    """

    def __init__(self, config: dict[str, Any] | MemoryAdapterConfig | None = None):
        """
        Initialize the memory adapter.

        Args:
            config: Configuration dictionary or MemoryAdapterConfig instance
        """
        # Parse configuration
        self._config: MemoryAdapterConfig
        if isinstance(config, dict):
            self._config = MemoryAdapterConfig(**config)
        elif isinstance(config, MemoryAdapterConfig):
            self._config = config
        else:
            self._config = MemoryAdapterConfig()

        # Initialize base adapter
        super().__init__(self._config)

        # Storage
        self._data: dict[K, CacheItem] | OrderedDict[K, CacheItem] = {}
        if self._config.eviction_policy == "lru":
            self._data = OrderedDict()

        self._data_lock = threading.RLock()

        # Cleanup thread for expired items
        self._cleanup_thread: threading.Thread | None = None
        self._stop_cleanup = threading.Event()

        self._logger.info(
            "Memory adapter initialized with max_size=%d, eviction_policy=%s",
            self._config.max_size if self._config.max_size else 0,
            self._config.eviction_policy,
        )

    # Abstract methods from BaseAdapter
    def _do_connect(self) -> bool:
        """Establish connection (no-op for memory adapter)."""
        try:
            # Start cleanup thread if not running
            if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
                self._stop_cleanup.clear()
                self._cleanup_thread = threading.Thread(
                    target=self._cleanup_expired_items,
                    name=f"MemoryAdapter-{self._config.name}-Cleanup",
                    daemon=True,
                )
                self._cleanup_thread.start()
                self._logger.debug("Started cleanup thread")

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to start cleanup thread: %s", e)
            return False

    def _do_disconnect(self) -> bool:
        """Close connection (cleanup for memory adapter)."""
        try:
            # Stop cleanup thread
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                self._stop_cleanup.set()
                self._cleanup_thread.join(timeout=1.0)
                self._logger.debug("Stopped cleanup thread")

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error during disconnect: %s", e)
            return False

    def _do_health_check(self) -> bool:
        """Perform health check (simple for memory adapter)."""
        try:
            # Simple check: try to access the data structure
            with self._data_lock:
                _ = len(self._data)
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Health check failed: %s", e)
            return False

    # KeyValueInterface implementation
    def get(self, key: K, default: V | None = None) -> V | None:
        """
        Retrieve a value by key.

        Args:
            key: The key to lookup
            default: Default value if key not found

        Returns:
            The value associated with the key, or default if not found
        """

        def _get_operation() -> V | None:
            with self._data_lock:
                item = self._data.get(key)

                if item is None:
                    self._update_cache_stats("get", success=False, size=len(self._data))
                    return default

                # Check expiration
                if item.is_expired():
                    del self._data[key]
                    self._update_cache_stats("get", success=False, size=len(self._data))
                    return default

                # Update access info
                item.access()

                # Move to end for LRU
                if self._config.eviction_policy == "lru" and isinstance(self._data, OrderedDict):
                    self._data.move_to_end(key)

                self._update_cache_stats("get", success=True, size=len(self._data))
                return cast(V, item.value)

        return self._safe_operation(cast(Callable[[], V], _get_operation), "get", default)

    def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:
        """
        Store a key-value pair.

        Args:
            key: The key to store
            value: The value to associate with the key
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            True if successful, False otherwise
        """

        def _set_operation() -> bool:
            # Calculate expiration time
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self._config.default_ttl is not None:
                expires_at = time.time() + self._config.default_ttl

            with self._data_lock:
                # Check if we need to evict items
                if (
                    self._config.max_size is not None
                    and key not in self._data
                    and len(self._data) >= self._config.max_size
                ):
                    self._evict_items(1)

                # Store the item
                item = CacheItem(value=value, expires_at=expires_at)
                self._data[key] = item

                # Move to end for LRU
                if self._config.eviction_policy == "lru" and isinstance(self._data, OrderedDict):
                    self._data.move_to_end(key)

                self._update_cache_stats("set", success=True, size=len(self._data))
                return True

        return self._safe_operation(_set_operation, "set", False)

    def delete(self, key: K) -> bool:
        """
        Delete a key-value pair.

        Args:
            key: The key to delete

        Returns:
            True if key existed and was deleted, False otherwise
        """

        def _delete_operation() -> bool:
            with self._data_lock:
                if key in self._data:
                    del self._data[key]
                    self._update_cache_stats("delete", success=True, size=len(self._data))
                    return True
                return False

        return self._safe_operation(_delete_operation, "delete", False)

    def exists(self, key: K) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check

        Returns:
            True if key exists and not expired, False otherwise
        """

        def _exists_operation() -> bool:
            with self._data_lock:
                item = self._data.get(key)

                if item is None:
                    return False

                # Check expiration
                if item.is_expired():
                    del self._data[key]
                    return False

                return True

        return self._safe_operation(_exists_operation, "exists", False)

    def clear(self) -> bool:
        """
        Clear all key-value pairs.

        Returns:
            True if successful, False otherwise
        """

        def _clear_operation() -> bool:
            with self._data_lock:
                self._data.clear()
                self._update_cache_stats("delete", success=True, size=0)
                return True

        return self._safe_operation(_clear_operation, "clear", False)

    def keys(self) -> Iterator[K]:
        """
        Get an iterator over all non-expired keys.

        Returns:
            Iterator of all valid keys
        """

        def _keys_operation() -> Iterator[K]:
            with self._data_lock:
                # Get snapshot of keys and filter expired
                valid_keys = []
                expired_keys = []
                now = time.time()

                for key, item in self._data.items():
                    if item.is_expired(now):
                        expired_keys.append(key)
                    else:
                        valid_keys.append(key)

                # Remove expired keys
                for key in expired_keys:
                    del self._data[key]

                if expired_keys:
                    self._update_cache_stats("delete", success=True, size=len(self._data))

                return iter(valid_keys)

        return self._safe_operation(_keys_operation, "keys", iter([]))

    def size(self) -> int:
        """
        Get the number of key-value pairs.

        Returns:
            Number of stored key-value pairs
        """

        def _size_operation() -> int:
            with self._data_lock:
                return len(self._data)

        return self._safe_operation(_size_operation, "size", 0)

    # Enhanced batch operations
    def get_many(self, keys: list[K]) -> dict[K, V | None]:
        """
        Retrieve multiple values by keys.

        Args:
            keys: List of keys to lookup

        Returns:
            Dictionary mapping keys to values (only for existing keys)
        """

        def _get_many_operation() -> dict[K, V | None]:
            result: dict[K, V | None] = {}
            expired_keys = []
            now = time.time()

            with self._data_lock:
                for key in keys:
                    item = self._data.get(key)

                    if item is None:
                        self._update_cache_stats("get", success=False)
                        result[key] = None
                        continue

                    # Check expiration
                    if item.is_expired(now):
                        expired_keys.append(key)
                        self._update_cache_stats("get", success=False)
                        result[key] = None
                        continue

                    # Update access info
                    item.access()

                    # Move to end for LRU
                    if self._config.eviction_policy == "lru" and isinstance(
                        self._data, OrderedDict
                    ):
                        self._data.move_to_end(key)

                    result[key] = cast(V, item.value)
                    self._update_cache_stats("get", success=True)

                # Remove expired keys
                for key in expired_keys:
                    del self._data[key]

                if expired_keys:
                    self._update_cache_stats("delete", success=True, size=len(self._data))

            return result

        return self._safe_operation(_get_many_operation, "get_many", {})

    def set_many(self, mapping: dict[K, V], ttl: int | float | None = None) -> dict[K, bool]:
        """
        Store multiple key-value pairs.

        Args:
            mapping: Dictionary of key-value pairs to store
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            Number of successful sets
        """

        def _set_many_operation() -> dict[K, bool]:
            results: dict[K, bool] = {}

            # Calculate expiration time
            expires_at = None
            if ttl is not None:
                expires_at = time.time() + ttl
            elif self._config.default_ttl is not None:
                expires_at = time.time() + self._config.default_ttl

            with self._data_lock:
                for key, value in mapping.items():
                    try:
                        # Check if we need to evict items
                        if (
                            self._config.max_size is not None
                            and key not in self._data
                            and len(self._data) >= self._config.max_size
                        ):
                            self._evict_items(1)

                        # Store the item
                        item = CacheItem(value=value, expires_at=expires_at)
                        self._data[key] = item

                        # Move to end for LRU
                        if self._config.eviction_policy == "lru" and isinstance(
                            self._data, OrderedDict
                        ):
                            self._data.move_to_end(key)

                        results[key] = True
                        self._update_cache_stats("set", success=True)

                    except Exception as e:  # pylint: disable=broad-exception-caught
                        self._logger.warning("Failed to set key %s: %s", key, e)
                        results[key] = False

                self._update_cache_stats("set", success=True, size=len(self._data))

            return results

        return self._safe_operation(_set_many_operation, "set_many", {})

    def delete_many(self, keys: list[K]) -> dict[K, bool]:
        """
        Delete multiple key-value pairs.

        Args:
            keys: List of keys to delete

        Returns:
            Dictionary mapping keys to deletion status (True if deleted, False otherwise)
        """

        def _delete_many_operation() -> dict[K, bool]:
            results: dict[K, bool] = {}
            with self._data_lock:
                for key in keys:
                    if key in self._data:
                        del self._data[key]
                        results[key] = True
                        self._update_cache_stats("delete", success=True, size=len(self._data))
                    else:
                        results[key] = False
            return results

        return self._safe_operation(_delete_many_operation, "delete_many", {})

    # Internal methods
    def _evict_items(self, count: int) -> int:
        """
        Evict items according to the eviction policy.

        Args:
            count: Number of items to evict

        Returns:
            Number of items actually evicted
        """
        if not self._data:
            return 0

        evicted = 0

        try:
            if self._config.eviction_policy == "lru" and isinstance(self._data, OrderedDict):
                # Remove from beginning (least recently used)
                for _ in range(min(count, len(self._data))):
                    self._data.popitem(last=False)
                    evicted += 1
                    self._update_cache_stats("eviction")

            elif self._config.eviction_policy == "fifo":
                # Remove oldest items
                items_by_age = sorted(self._data.items(), key=lambda x: x[1].created_at)
                for i in range(min(count, len(items_by_age))):
                    key_to_evict = items_by_age[i][0]
                    if key_to_evict in self._data:
                        del self._data[key_to_evict]
                        evicted += 1
                        self._update_cache_stats("eviction")

            elif self._config.eviction_policy == "random":
                keys = list(self._data.keys())
                keys_to_remove = random.sample(keys, min(count, len(keys)))
                for key_to_remove in keys_to_remove:
                    if key_to_remove in self._data:
                        del self._data[key_to_remove]
                        evicted += 1
                        self._update_cache_stats("eviction")

            if evicted > 0:
                self._logger.debug(
                    "Evicted %d items using %s policy", evicted, self._config.eviction_policy
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error during eviction: %s", e)

        return evicted

    def _cleanup_expired_items(self) -> None:
        """Background thread to clean up expired items."""
        self._logger.debug("Cleanup thread started")

        while not self._stop_cleanup.wait(self._config.cleanup_interval):
            try:
                expired_count = 0
                now = time.time()

                with self._data_lock:
                    expired_keys = [key for key, item in self._data.items() if item.is_expired(now)]

                    for key in expired_keys:
                        del self._data[key]
                        expired_count += 1

                if expired_count > 0:
                    self._logger.debug("Cleaned up %d expired items", expired_count)
                    self._update_cache_stats("delete", success=True, size=len(self._data))

            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error("Error during cleanup: %s", e)

        self._logger.debug("Cleanup thread stopped")

    # Additional utility methods
    def get_item_info(self, key: K) -> dict[str, Any] | None:
        """
        Get detailed information about a cached item.

        Args:
            key: The key to inspect

        Returns:
            Dictionary with item information, or None if not found
        """

        def _get_item_info_operation() -> dict[str, Any] | None:
            with self._data_lock:
                item = self._data.get(key)

                if item is None:
                    return None

                # Check expiration
                if item.is_expired():
                    del self._data[key]
                    return None

                return {
                    "created_at": item.created_at,
                    "expires_at": item.expires_at,
                    "access_count": item.access_count,
                    "last_accessed": item.last_accessed,
                    "ttl_remaining": item.expires_at - time.time() if item.expires_at else None,
                    "size_bytes": len(str(item.value)),  # Rough estimate
                }

        return self._safe_operation(_get_item_info_operation, "get_item_info", None)

    def get_backend_info(self) -> dict[str, Any]:
        """
        Get detailed information about the memory backend.

        Returns:
            Dictionary containing backend information
        """
        info = super().get_backend_info()

        with self._data_lock:
            info.update(
                {
                    "storage_type": "python_dict",
                    "max_size": self._config.max_size,
                    "current_size": len(self._data),
                    "eviction_policy": self._config.eviction_policy,
                    "default_ttl": self._config.default_ttl,
                    "cleanup_interval": self._config.cleanup_interval,
                    "cleanup_thread_active": (
                        self._cleanup_thread.is_alive() if self._cleanup_thread else False
                    ),
                }
            )

        return info
