"""
This module implements a file-system-based cache adapter.

It provides a simple cache that stores each key-value pair as a separate JSON file
in a specified directory. This adapter is intended for demonstration purposes and
scenarios where a simple, persistent, file-based cache is sufficient.
"""

import json
import os
import shutil
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from omni_cache.adapters.base import AdapterConfig, BaseCacheAdapter
from omni_cache.core.interfaces import KeyValueInterface


@dataclass
class FileCacheConfig(AdapterConfig):
    """Configuration for the FileCache adapter."""

    cache_dir: str = "omni_cache_files"  # Default directory for cache files


# pylint: disable=too-many-ancestors
class FileCacheAdapter(BaseCacheAdapter, KeyValueInterface[str, Any]):
    """
    A simple file-system based cache adapter for demonstration purposes.
    Stores each key-value pair as a separate file in a specified directory.
    """

    _config: FileCacheConfig  # Annotation explicite

    def __init__(self, config: dict[str, Any] | FileCacheConfig | None = None):
        if isinstance(config, dict):
            super().__init__(FileCacheConfig(**config))
        elif isinstance(config, FileCacheConfig):
            super().__init__(config)
        else:
            super().__init__(FileCacheConfig())

        self._cache_dir = self._config.cache_dir
        self._logger.info("FileCacheAdapter initialized with cache_dir: %s", self._cache_dir)

    def _get_file_path(self, key: str) -> str:
        """Helper to get the full path for a given key."""
        return os.path.join(self._cache_dir, f"{key}.json")

    def _do_connect(self) -> bool:
        """Ensure the cache directory exists."""
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            self._logger.debug("Cache directory '%s' ensured.", self._cache_dir)
            return True
        except OSError as e:
            self._logger.error("Failed to create cache directory '%s': %s", self._cache_dir, e)
            return False

    def _do_disconnect(self) -> bool:
        """No specific disconnection logic needed for file system."""
        self._logger.debug("FileCacheAdapter disconnected.")
        return True

    def _do_health_check(self) -> bool:
        """Check if the cache directory is writable."""
        try:
            # Attempt to create a temporary file to check writability
            test_file = os.path.join(self._cache_dir, ".health_check")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except OSError as e:
            self._logger.error(
                "Health check failed for cache directory '%s': %s", self._cache_dir, e
            )
            return False

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Store a key-value pair in the cache."""
        return self._safe_operation(
            lambda: self._set_internal(key, value, ttl), "set", default=False
        )

    def _set_internal(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        file_path = self._get_file_path(key)
        try:
            expiration_timestamp = (time.time() + ttl) if ttl is not None else None
            data = {"value": value, "expiration_timestamp": expiration_timestamp}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            self._update_cache_stats("set")
            self._logger.debug("Set key '%s' in FileCache.", key)
            return True
        except (OSError, AttributeError, json.JSONDecodeError, UnicodeDecodeError) as e:
            self._logger.error("Failed to set key '%s' in FileCache: %s", key, e)
            return False

    def get(self, key: str, default: Any | None = None) -> Any:
        """Retrieve a value from the cache."""
        return self._safe_operation(
            lambda: self._get_internal(key, default), "get", default=default
        )

    def _get_internal(self, key: str, default: Any | None = None) -> Any:
        file_path = self._get_file_path(key)
        if not os.path.exists(file_path):
            self._update_cache_stats("get", success=False)
            self._logger.debug("Key '%s' not found in FileCache.", key)
            return default

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check expiration timestamp
            expiration_timestamp = data.get("expiration_timestamp")
            if expiration_timestamp is not None and time.time() > expiration_timestamp:
                os.remove(file_path)  # Expired, remove it
                self._update_cache_stats("get", success=False)
                self._logger.debug("Key '%s' expired in FileCache.", key)
                return default

            self._update_cache_stats("get", success=True)
            self._logger.debug("Retrieved key '%s' from FileCache.", key)
            return data["value"]
        except (OSError, json.decoder.JSONDecodeError) as e:
            self._logger.error("Failed to get key '%s' from FileCache: %s", key, e)
            self._update_cache_stats("get", success=False)
            return default

    def delete(self, key: str) -> bool:
        """Delete a key-value pair from the cache."""
        return self._safe_operation(lambda: self._delete_internal(key), "delete", default=False)

    def _delete_internal(self, key: str) -> bool:
        file_path = self._get_file_path(key)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                self._update_cache_stats("delete")
                self._logger.debug("Deleted key '%s' from FileCache.", key)
                return True
            except OSError as e:
                self._logger.error("Failed to delete key '%s' from FileCache: %s", key, e)
                return False
        self._logger.debug("Attempted to delete non-existent key '%s' from FileCache.", key)
        return False

    def clear(self) -> bool:
        """Clear all entries from the cache."""
        return self._safe_operation(self._clear_internal, "clear", default=False)

    def _clear_internal(self) -> bool:
        try:
            if os.path.exists(self._cache_dir):
                shutil.rmtree(self._cache_dir)
                self._logger.info(
                    "Cleared all entries from FileCache directory: %s", self._cache_dir
                )
            self._update_cache_stats("clear")  # Assuming clear is a cache stat operation
            return True
        except OSError as e:
            self._logger.error("Failed to clear FileCache directory '%s': %s", self._cache_dir, e)
            return False

    def exists(self, key: str) -> bool:
        """Check whether a key exists and is not expired."""
        return self._safe_operation(lambda: self._exists_internal(key), "exists", default=False)

    def _exists_internal(self, key: str) -> bool:
        file_path = self._get_file_path(key)
        if not os.path.exists(file_path):
            return False

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            expiration_timestamp = data.get("expiration_timestamp")
            if expiration_timestamp is not None and time.time() > expiration_timestamp:
                os.remove(file_path)
                self._update_cache_stats("delete", success=True)
                return False
            return True
        except (OSError, json.decoder.JSONDecodeError):
            return False

    def keys(self) -> Iterator[str]:
        """Iterate over non-expired keys currently stored in the cache directory."""
        return self._safe_operation(self._keys_internal, "keys", default=iter([]))

    def _keys_internal(self) -> Iterator[str]:
        if not os.path.exists(self._cache_dir):
            return iter([])

        valid_keys = []
        for filename in os.listdir(self._cache_dir):
            if not filename.endswith(".json"):
                continue
            key = filename[:-5]
            if self._exists_internal(key):
                valid_keys.append(key)
        return iter(valid_keys)

    def size(self) -> int:
        """Count non-expired keys in the cache."""
        return self._safe_operation(
            lambda: sum(1 for _ in self._keys_internal()), "size", default=0
        )


def create_file_cache_adapter(config: dict[str, Any]) -> FileCacheAdapter:
    """Factory function to create a FileCacheAdapter instance."""
    return FileCacheAdapter(FileCacheConfig(**config))
