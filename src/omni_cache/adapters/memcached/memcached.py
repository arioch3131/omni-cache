"""
Memcached adapter implementation for omni-cache.

This adapter implements KeyValueInterface using `pymemcache`.
"""

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, TypeVar, cast

from omni_cache.adapters.base import BaseCacheAdapter
from omni_cache.adapters.memcached.config import MemcachedAdapterConfig
from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError
from omni_cache.core.exceptions.operation_exceptions import OperationFailedError
from omni_cache.core.interfaces import KeyValueInterface

try:
    from pymemcache.client.base import Client
    from pymemcache.exceptions import MemcacheClientError, MemcacheServerError, MemcacheUnknownError

    HAS_MEMCACHED = True
except ImportError:
    HAS_MEMCACHED = False
    Client = type("Client", (), {})
    MemcacheClientError = Exception
    MemcacheServerError = Exception
    MemcacheUnknownError = Exception

K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


# pylint: disable=too-many-ancestors
class MemcachedAdapter(BaseCacheAdapter, KeyValueInterface[K, V]):
    """Memcached cache adapter implementing KeyValueInterface."""

    def __init__(self, config: dict[str, Any] | MemcachedAdapterConfig | None = None):
        self._config: MemcachedAdapterConfig
        if isinstance(config, dict):
            self._config = MemcachedAdapterConfig(**config)
        elif isinstance(config, MemcachedAdapterConfig):
            self._config = config
        else:
            self._config = MemcachedAdapterConfig()

        super().__init__(self._config)

        self._client: Client | None = None
        self._connection_lock = threading.RLock()
        self._known_keys: set[str] = set()

        self._serializers: dict[str, Callable[[V], str | bytes]] = {
            "json": self._serialize_json,
            "string": self._serialize_string,
        }
        self._deserializers: dict[str, Callable[[str | bytes], V]] = {
            "json": self._deserialize_json,
            "string": self._deserialize_string,
        }

        self._logger.info(
            "Memcached adapter initialized for %s:%d", self._config.host, self._config.port
        )

    def _do_connect(self) -> bool:
        """Establish Memcached connection."""
        if not HAS_MEMCACHED:
            self._logger.error("pymemcache dependency not available")
            return False

        try:
            with self._connection_lock:
                self._client = Client(
                    (self._config.host, self._config.port),
                    connect_timeout=self._config.connect_timeout,
                    timeout=self._config.timeout,
                    no_delay=self._config.no_delay,
                    ignore_exc=self._config.ignore_exc,
                )

                # Health ping via set/get/delete cycle.
                health_key = self._make_key(cast(K, self._config.health_check_key))
                health_value = "ping"
                self._client.set(health_key, health_value.encode(self._config.encoding), expire=10)
                read_back = self._client.get(health_key)
                self._client.delete(health_key)
                return read_back is not None
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to connect to Memcached: %s", e)
            self._client = None
            return False

    def _do_disconnect(self) -> bool:
        """Close Memcached connection."""
        try:
            with self._connection_lock:
                if self._client is not None:
                    self._client.close()
                self._client = None
                self._known_keys.clear()
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error during Memcached disconnection: %s", e)
            return False

    def _do_health_check(self) -> bool:
        """Perform health check on Memcached backend."""
        if not self._client:
            return False

        try:
            health_key = self._make_key(cast(K, self._config.health_check_key))
            health_value = f"health_check_{time.time():.1f}"
            self._client.set(
                health_key,
                health_value.encode(self._config.encoding),
                expire=10,
            )
            result = self._client.get(health_key)
            self._client.delete(health_key)
            if result is None:
                return False
            raw_result = cast(str | bytes, result)
            if isinstance(raw_result, bytes):
                decoded_result = raw_result.decode(self._config.encoding)
            else:
                decoded_result = raw_result
            return decoded_result == health_value
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.warning("Memcached health check failed: %s", e)
            return False

    def _serialize_value(self, value: V) -> str | bytes:
        serializer = self._serializers.get(self._config.serialization_method)
        if serializer is None:
            raise ValueError(f"Unknown serialization method: {self._config.serialization_method}")
        return serializer(value)

    def _deserialize_value(self, raw_value: str | bytes) -> V:
        deserializer = self._deserializers.get(self._config.serialization_method)
        if deserializer is None:
            raise ValueError(f"Unknown serialization method: {self._config.serialization_method}")
        return deserializer(raw_value)

    def _serialize_json(self, value: V) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize_json(self, raw_value: str | bytes) -> V:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode(self._config.encoding)
        return json.loads(raw_value)  # type: ignore

    def _serialize_string(self, value: V) -> str:
        return str(value)

    def _deserialize_string(self, raw_value: str | bytes) -> V:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode(self._config.encoding)
        return raw_value  # type: ignore

    def _normalize_ttl(self, ttl: int | float | None) -> int:
        if ttl is None:
            return int(self._config.default_ttl or 0)
        return max(0, int(ttl))

    def _make_key(self, key: K) -> str:
        key_str = str(key)
        if self._config.key_prefix:
            return f"{self._config.key_prefix}{self._config.key_separator}{key_str}"
        return key_str

    def _safe_operation(
        self, operation: Callable[[], T], operation_name: str, default: T | None = None
    ) -> T:
        if not self._client:
            raise AdapterNotConnectedError(f"Memcached adapter not connected for {operation_name}")

        last_exception: Exception | None = None
        max_retries = self._config.max_retries if self._config.retry_on_error else 1

        for attempt in range(max_retries):
            try:
                return operation()
            except (MemcacheClientError, MemcacheServerError, MemcacheUnknownError) as e:
                last_exception = e
                self._logger.warning(
                    "Memcached operation %s failed (attempt %d/%d): %s",
                    operation_name,
                    attempt + 1,
                    max_retries,
                    e,
                )
                if attempt < max_retries - 1:
                    delay = self._config.retry_delay * (self._config.retry_backoff_factor**attempt)
                    time.sleep(delay)
                    continue
                break
            except Exception as e:  # pylint: disable=broad-exception-caught
                last_exception = e
                break

        if default is not None:
            return default
        raise OperationFailedError(
            f"Memcached operation {operation_name} failed: {last_exception}"
        ) from last_exception

    def get(self, key: K, default: V | None = None) -> V | None:
        def _get_operation() -> V | None:
            if not self._client:
                return default

            mem_key = self._make_key(key)
            raw_value = self._client.get(mem_key)
            if raw_value is None:
                self._update_cache_stats("get", success=False)
                return default

            value = self._deserialize_value(cast(str | bytes, raw_value))
            self._update_cache_stats("get", success=True)
            return value

        return self._safe_operation(cast(Callable[[], V], _get_operation), "get", default)

    def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:
        def _set_operation() -> bool:
            if not self._client:
                return False

            mem_key = self._make_key(key)
            serialized = self._serialize_value(value)
            encoded = (
                serialized.encode(self._config.encoding)
                if isinstance(serialized, str)
                else serialized
            )
            success = bool(self._client.set(mem_key, encoded, expire=self._normalize_ttl(ttl)))
            if success:
                self._known_keys.add(mem_key)
            self._update_cache_stats("set", success=success, size=len(self._known_keys))
            return success

        return self._safe_operation(_set_operation, "set", False)

    def delete(self, key: K) -> bool:
        def _delete_operation() -> bool:
            if not self._client:
                return False
            mem_key = self._make_key(key)
            deleted = bool(self._client.delete(mem_key))
            self._known_keys.discard(mem_key)
            if deleted:
                self._update_cache_stats("delete", success=True, size=len(self._known_keys))
            return deleted

        return self._safe_operation(_delete_operation, "delete", False)

    def exists(self, key: K) -> bool:
        def _exists_operation() -> bool:
            if not self._client:
                return False
            mem_key = self._make_key(key)
            return self._client.get(mem_key) is not None

        return self._safe_operation(_exists_operation, "exists", False)

    def clear(self) -> bool:
        def _clear_operation() -> bool:
            if not self._client:
                return False
            # We only clear keys known by this adapter instance.
            success = True
            for mem_key in list(self._known_keys):
                deleted = bool(self._client.delete(mem_key))
                if deleted:
                    self._known_keys.discard(mem_key)
                else:
                    success = False
            self._update_cache_stats("delete", success=success, size=len(self._known_keys))
            return success

        return self._safe_operation(_clear_operation, "clear", False)

    def keys(self) -> Iterator[K]:
        def _keys_operation() -> Iterator[K]:
            if not self._client:
                return iter([])
            live_keys: list[str] = []
            for mem_key in list(self._known_keys):
                if self._client.get(mem_key) is not None:
                    live_keys.append(mem_key)
                else:
                    self._known_keys.discard(mem_key)
            return iter(cast(list[K], live_keys))

        return self._safe_operation(_keys_operation, "keys", iter([]))

    def size(self) -> int:
        def _size_operation() -> int:
            if not self._client:
                return 0
            live_count = 0
            for mem_key in list(self._known_keys):
                if self._client.get(mem_key) is not None:
                    live_count += 1
                else:
                    self._known_keys.discard(mem_key)
            return live_count

        return self._safe_operation(_size_operation, "size", 0)

    def get_many(self, keys: list[K]) -> dict[K, V | None]:
        def _get_many_operation() -> dict[K, V | None]:
            result: dict[K, V | None] = {}
            for key in keys:
                result[key] = self.get(key, None)
            return result

        return self._safe_operation(_get_many_operation, "get_many", {})

    def set_many(self, mapping: dict[K, V], ttl: int | float | None = None) -> dict[K, bool]:
        def _set_many_operation() -> dict[K, bool]:
            result: dict[K, bool] = {}
            for key, value in mapping.items():
                result[key] = self.set(key, value, ttl)
            return result

        return self._safe_operation(_set_many_operation, "set_many", {})

    def delete_many(self, keys: list[K]) -> dict[K, bool]:
        def _delete_many_operation() -> dict[K, bool]:
            result: dict[K, bool] = {}
            for key in keys:
                result[key] = self.delete(key)
            return result

        return self._safe_operation(_delete_many_operation, "delete_many", {})
