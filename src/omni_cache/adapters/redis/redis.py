"""
Redis adapter implementation for omni-cache.

This module provides a Redis-based cache adapter that implements the KeyValueInterface.
Supports connection pooling, automatic serialization, TTL, and provides comprehensive
error handling and monitoring capabilities.
"""

import json
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, TypeVar, cast

from omni_cache.adapters.base import BaseCacheAdapter
from omni_cache.adapters.redis.config import RedisAdapterConfig
from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError
from omni_cache.core.exceptions.operation_exceptions import OperationFailedError
from omni_cache.core.interfaces import KeyValueInterface

# Optional Redis import with graceful fallback
try:
    from redis import ConnectionPool, Redis
    from redis.exceptions import ConnectionError as RedisConnectionError
    from redis.exceptions import (
        RedisError,
        ResponseError,
    )
    from redis.exceptions import TimeoutError as RedisTimeoutError

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    # Use Any for fallback types to avoid mypy issues
    Redis = type("Redis", (), {})  # type: ignore
    ConnectionPool = type("ConnectionPool", (), {})  # type: ignore
    # Use Exception as base for fallbacks
    RedisConnectionError = Exception  # type: ignore
    RedisError = Exception  # type: ignore
    ResponseError = Exception  # type: ignore
    RedisTimeoutError = Exception  # type: ignore

# Type variables
K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")


# pylint: disable=too-many-ancestors
class RedisAdapter(BaseCacheAdapter, KeyValueInterface[K, V]):
    """
    Redis cache adapter implementing KeyValueInterface.

    Features:
    - Thread-safe operations using Redis connection pooling
    - Multiple serialization methods (JSON, String)
    - TTL (time-to-live) support with Redis expiration
    - Comprehensive error handling and retry logic
    - Health checking with configurable intervals
    - Key prefixing and namespacing
    - Batch operations for improved performance
    - Connection pool management
    """

    def __init__(self, config: dict[str, Any] | RedisAdapterConfig | None = None):
        """
        Initialize the Redis adapter.

        Args:
            config: Configuration dictionary or RedisAdapterConfig instance

        Raises:
            ImportError: If Redis is not available
        """
        # Parse configuration
        self._config: RedisAdapterConfig
        if isinstance(config, dict):
            self._config = RedisAdapterConfig(**config)
        elif isinstance(config, RedisAdapterConfig):
            self._config = config
        else:
            self._config = RedisAdapterConfig()

        # Initialize base adapter
        super().__init__(self._config)

        # Redis connection objects
        self._connection_pool: ConnectionPool | None = None
        self._redis: Redis | None = None
        self._connection_lock = threading.RLock()

        # Serialization handlers
        self._serializers = {
            "json": self._serialize_json,
            "string": self._serialize_string,
        }

        self._deserializers = {
            "json": self._deserialize_json,
            "string": self._deserialize_string,
        }

        self._logger.info(
            "Redis adapter initialized for %s:%d (db=%d)",
            self._config.host,
            self._config.port,
            self._config.db,
        )

    # Abstract methods from BaseAdapter
    def _do_connect(self) -> bool:
        """Establish connection to Redis server."""
        try:
            with self._connection_lock:
                # Create connection pool
                redis_kwargs = self._config.get_redis_kwargs()
                self._connection_pool = ConnectionPool(
                    max_connections=self._config.connection_pool_max_connections, **redis_kwargs
                )

                # Create Redis client
                self._redis = Redis(connection_pool=self._connection_pool)

                # Test connection
                self._redis.ping()

                self._logger.info(
                    "Successfully connected to Redis at %s:%d", self._config.host, self._config.port
                )
                return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to connect to Redis: %s", e)
            self._cleanup_connection()
            return False

    def _do_disconnect(self) -> bool:
        """Close connection to Redis server."""
        try:
            with self._connection_lock:
                if self._connection_pool:
                    self._connection_pool.disconnect()

                self._cleanup_connection()
                self._logger.info("Disconnected from Redis")
                return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error during Redis disconnection: %s", e)
            return False

    def _cleanup_connection(self) -> None:
        """Clean up connection objects."""
        self._redis = None
        self._connection_pool = None

    def _do_health_check(self) -> bool:
        """Perform health check on Redis server."""
        if not self._redis:
            return False

        try:
            # Try to set and get a health check key
            health_key = self._make_key(cast(K, self._config.health_check_key))
            test_value = f"health_check_{time.time():.1f}"

            serialized_value = self._serialize_value(test_value)  # type: ignore
            self._redis.setex(health_key, 10, serialized_value)

            raw_result = self._redis.get(health_key)
            if raw_result is not None:
                # Cast to ensure mypy knows it's not awaitable
                raw_result = cast(str | bytes, raw_result)
                result = self._deserialize_value(raw_result)
                return result == test_value
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.warning("Redis health check failed: %s", e)
            return False

    def _make_key(self, key: K) -> str:
        """Create Redis key with optional prefix."""
        key_str = str(key)
        if self._config.key_prefix:
            return f"{self._config.key_prefix}{self._config.key_separator}{key_str}"
        return key_str

    def _unmake_key(self, redis_key: str) -> str:
        """Extract original key from Redis key."""
        if self._config.key_prefix:
            prefix = f"{self._config.key_prefix}{self._config.key_separator}"
            if redis_key.startswith(prefix):
                return redis_key[len(prefix) :]
            return redis_key
        return redis_key

    # Serialization methods
    def _serialize_value(self, value: V) -> str | bytes:
        """Serialize value for Redis storage."""
        serializer = self._serializers.get(self._config.serialization_method)
        if not serializer:
            raise ValueError(f"Unknown serialization method: {self._config.serialization_method}")
        return serializer(value)

    def _deserialize_value(self, raw_value: str | bytes) -> V:
        """Deserialize value from Redis storage."""
        deserializer = self._deserializers.get(self._config.serialization_method)
        if not deserializer:
            raise ValueError(f"Unknown serialization method: {self._config.serialization_method}")
        return deserializer(raw_value)

    def _serialize_json(self, value: V) -> str:
        """Serialize value using JSON."""
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize_json(self, raw_value: str | bytes) -> V:
        """Deserialize value from JSON."""
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)  # type: ignore

    def _serialize_string(self, value: V) -> str:
        """Serialize value as string."""
        return str(value)

    def _deserialize_string(self, raw_value: str | bytes) -> V:
        """Deserialize value from string."""
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return raw_value  # type: ignore

    # Retry decorator with corrected signature
    def _safe_operation(
        self, operation: Callable[[], T], operation_name: str, default: T | None = None
    ) -> T:
        """Execute operation with retry logic and error handling."""
        if not self._redis:
            self._logger.error("Redis client not available for operation: %s", operation_name)
            raise AdapterNotConnectedError(f"Redis adapter not connected for {operation_name}")

        last_exception = None
        max_retries = self._config.max_retries if self._config.retry_on_error else 1

        for attempt in range(max_retries):
            try:
                return operation()

            except (RedisConnectionError, RedisTimeoutError, ConnectionError) as e:
                last_exception = e
                self._logger.warning(
                    "Redis operation %s failed (attempt %d/%d): %s",
                    operation_name,
                    attempt + 1,
                    max_retries,
                    e,
                )

                if attempt < max_retries - 1:
                    delay = self._config.retry_delay * (self._config.retry_backoff_factor**attempt)
                    time.sleep(delay)
                    continue

                # Last attempt failed
                break

            except RedisError as e:
                self._logger.error("Unexpected error in Redis operation %s: %s", operation_name, e)
                raise OperationFailedError(f"Redis operation {operation_name} failed: {e}") from e

        # All retries exhausted
        self._logger.error(
            "Redis operation %s failed after %d attempts", operation_name, max_retries
        )
        if default is not None:
            return default
        raise OperationFailedError(f"Redis operation {operation_name} failed: {last_exception}")

    # KeyValueInterface implementation
    def get(self, key: K, default: V | None = None) -> V | None:
        """
        Get value by key.

        Args:
            key: The key to lookup
            default: Default value if key not found

        Returns:
            The value associated with the key, or default if not found
        """

        def _get_operation() -> V | None:
            if not self._redis:
                return default

            redis_key = self._make_key(key)
            raw_value = self._redis.get(redis_key)

            if raw_value is None:
                self._update_cache_stats("get", success=False)
                return default

            try:
                # Cast to ensure mypy knows it's not awaitable
                raw_value = cast(str | bytes, raw_value)
                value = self._deserialize_value(raw_value)
                self._update_cache_stats("get", success=True)
                return value

            except (RedisError, TypeError, ValueError) as e:
                self._logger.warning("Failed to deserialize value for key %s: %s", key, e)
                self._update_cache_stats("get", success=False)
                return default

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
            if not self._redis:
                return False

            redis_key = self._make_key(key)

            try:
                serialized_value = self._serialize_value(value)

                if ttl is not None:
                    # Set with expiration
                    if isinstance(ttl, float):
                        # Use PSETEX for millisecond precision
                        result = self._redis.psetex(redis_key, int(ttl * 1000), serialized_value)
                    else:
                        # Use SETEX for second precision
                        result = self._redis.setex(redis_key, ttl, serialized_value)
                else:
                    # Set without expiration
                    result = self._redis.set(redis_key, serialized_value)

                success = bool(result)
                self._update_cache_stats("set", success=success)
                return success

            except (RedisError, TypeError, ValueError) as e:
                self._logger.warning("Failed to serialize/set value for key %s: %s", key, e)
                self._update_cache_stats("set", success=False)
                return False

        return self._safe_operation(_set_operation, "set", False)

    def delete(self, key: K) -> bool:
        """
        Delete a key-value pair.

        Args:
            key: The key to delete

        Returns:
            True if key was deleted, False otherwise
        """

        def _delete_operation() -> bool:
            if not self._redis:
                return False

            redis_key = self._make_key(key)
            result = self._redis.delete(redis_key)

            # Cast to int to handle Union[Awaitable[Any], Any]
            success = cast(int, result) > 0
            self._update_cache_stats("delete", success=success)
            return success

        return self._safe_operation(_delete_operation, "delete", False)

    def exists(self, key: K) -> bool:
        """
        Check if key exists.

        Args:
            key: The key to check

        Returns:
            True if key exists, False otherwise
        """

        def _exists_operation() -> bool:
            if not self._redis:
                return False

            redis_key = self._make_key(key)
            return bool(self._redis.exists(redis_key))

        return self._safe_operation(_exists_operation, "exists", False)

    def clear(self) -> bool:
        """
        Clear all keys (with optional prefix filtering).

        Returns:
            True if successful, False otherwise
        """

        def _clear_operation() -> bool:
            if not self._redis:
                return False

            if self._config.key_prefix:
                # Clear only prefixed keys
                pattern = f"{self._config.key_prefix}{self._config.key_separator}*"
                keys = self._redis.keys(pattern)
                # Cast to list to handle Union[Awaitable[Any], Any]
                keys = cast(list[str], keys)
                if keys:
                    result = self._redis.delete(*keys)
                    return cast(int, result) > 0
                return True

            # Clear entire database
            self._redis.flushdb()
            return True

        return self._safe_operation(_clear_operation, "clear", False)

    def size(self) -> int:
        """
        Get number of keys.

        Returns:
            Number of stored key-value pairs
        """

        def _size_operation() -> int:
            if not self._redis:
                return 0

            if self._config.key_prefix:
                pattern = f"{self._config.key_prefix}{self._config.key_separator}*"
                keys = self._redis.keys(pattern)
                # Cast to list to handle Union[Awaitable[Any], Any]
                keys = cast(list[str], keys)
                return len(keys)

            result = self._redis.dbsize()
            return cast(int, result)

        return self._safe_operation(_size_operation, "size", 0)

    # Enhanced batch operations
    def get_many(self, keys: list[K]) -> dict[K, V | None]:
        """
        Retrieve multiple values by keys.

        Args:
            keys: List of keys to lookup

        Returns:
            Dictionary mapping keys to values (None for missing keys)
        """

        def _get_many_operation() -> dict[K, V | None]:
            if not keys or not self._redis:
                return {}

            redis_keys = [self._make_key(key) for key in keys]
            raw_values = self._redis.mget(redis_keys)
            # Cast to list to handle Union[Awaitable[Any], Any]
            raw_values = cast(list[str | bytes | None], raw_values)

            result: dict[K, V | None] = {}
            for key, raw_value in zip(keys, raw_values, strict=False):
                if raw_value is not None:
                    try:
                        value = self._deserialize_value(raw_value)
                        result[key] = value
                        self._update_cache_stats("get", success=True)
                    except (RedisError, TypeError, ValueError) as e:
                        self._logger.warning("Failed to deserialize value for key %s: %s", key, e)
                        result[key] = None
                        self._update_cache_stats("get", success=False)
                else:
                    result[key] = None
                    self._update_cache_stats("get", success=False)

            return result

        return self._safe_operation(_get_many_operation, "get_many", {})

    def set_many(self, mapping: dict[K, V], ttl: int | float | None = None) -> dict[K, bool]:
        """
        Store multiple key-value pairs.

        Args:
            mapping: Dictionary of key-value pairs to store
            ttl: Time to live in seconds (None for no expiration)

        Returns:
            Dictionary mapping keys to success status
        """

        def _set_many_operation() -> dict[K, bool]:
            if not mapping or not self._redis:
                return {}

            result: dict[K, bool] = {}

            try:
                # Prepare data for Redis MSET
                redis_mapping = {}
                for key, value in mapping.items():
                    redis_key = self._make_key(key)
                    serialized_value = self._serialize_value(value)
                    redis_mapping[redis_key] = serialized_value

                # Use MSET for batch operation
                success = self._redis.mset(redis_mapping)

                # Set TTL for each key if specified
                if success and ttl is not None:
                    for key in mapping.keys():
                        redis_key = self._make_key(key)
                        if isinstance(ttl, float):
                            self._redis.pexpire(redis_key, int(ttl * 1000))
                        else:
                            self._redis.expire(redis_key, ttl)

                # Update result for all keys
                for key in mapping.keys():
                    result[key] = bool(success)
                    self._update_cache_stats("set", success=bool(success))

            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.error("Failed to set multiple keys: %s", e)
                # Mark all as failed
                for key in mapping.keys():
                    result[key] = False
                    self._update_cache_stats("set", success=False)

            return result

        return self._safe_operation(_set_many_operation, "set_many", {})

    def delete_many(self, keys: list[K]) -> dict[K, bool]:
        """
        Delete multiple keys.

        Args:
            keys: List of keys to delete

        Returns:
            Dictionary mapping keys to success status
        """

        def _delete_many_operation() -> dict[K, bool]:
            if not keys or not self._redis:
                return {}

            redis_keys = [self._make_key(key) for key in keys]
            deleted_count = self._redis.delete(*redis_keys)
            # Cast to int to handle Union[Awaitable[Any], Any]
            deleted_count = cast(int, deleted_count)

            result: dict[K, bool] = {}

            # For simplicity, assume all were successful if any were deleted
            success = deleted_count > 0
            for key in keys:
                result[key] = success
                self._update_cache_stats("delete", success=success)

            return result

        return self._safe_operation(_delete_many_operation, "delete_many", {})

    def get_ttl(self, key: K) -> float | None:
        """
        Get time to live for a key.

        Args:
            key: The key to check

        Returns:
            TTL in seconds, or None if key doesn't exist or has no expiration
        """

        def _get_ttl_operation() -> float | None:
            if not self._redis:
                return None

            redis_key = self._make_key(key)

            # Use PTTL for millisecond precision
            ttl_ms = self._redis.pttl(redis_key)
            # Cast to int to handle Union[Awaitable[Any], Any]
            ttl_ms = cast(int, ttl_ms)

            if ttl_ms in (-2, -1):  # Key doesn't exist or has no expiration
                return None
            return float(ttl_ms) / 1000.0

        return self._safe_operation(_get_ttl_operation, "get_ttl", None)

    def get_backend_info(self) -> dict[str, Any]:
        """Get information about the Redis backend."""
        if not self._redis:
            return {
                "backend": "redis",
                "status": "disconnected",
                "host": self._config.host,
                "port": self._config.port,
                "db": self._config.db,
                "serialization_method": self._config.serialization_method,
                "key_prefix": self._config.key_prefix,
                "connection_pool_max_connections": self._config.connection_pool_max_connections,
            }

        try:
            info = self._redis.info()
            # Cast to dict to handle Union[Awaitable[Any], Any]
            info = cast(dict[str, Any], info)
            server_info = {
                "redis_version": info.get("redis_version"),
                "uptime_in_seconds": info.get("uptime_in_seconds"),
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
            }
        except Exception:  # pylint: disable=broad-exception-caught
            server_info = {}

        return {
            "backend": "redis",
            "status": "connected" if self.is_connected() else "disconnected",
            "host": self._config.host,
            "port": self._config.port,
            "db": self._config.db,
            "serialization_method": self._config.serialization_method,
            "key_prefix": self._config.key_prefix,
            "connection_pool_max_connections": self._config.connection_pool_max_connections,
            "server_info": server_info,
        }

    def is_healthy(self) -> bool:
        """Check if the Redis backend is healthy."""
        try:
            return self._do_health_check()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    def keys(self) -> Iterator[K]:
        """
        Get an iterator over all keys.

        Returns:
            Iterator of all keys (unprefixed)
        """

        def _keys_operation() -> Iterator[K]:
            if not self._redis:
                return iter([])

            if self._config.key_prefix:
                pattern = f"{self._config.key_prefix}{self._config.key_separator}*"
                redis_keys = self._redis.keys(pattern)
                # Cast to list to handle Union[Awaitable[Any], Any]
                redis_keys = cast(list[str | bytes], redis_keys)
                # Remove prefix from each key
                unprefixed_keys = [
                    self._unmake_key(key.decode() if isinstance(key, bytes) else key)
                    for key in redis_keys
                ]
                return iter(cast(list[K], unprefixed_keys))

            redis_keys = self._redis.keys("*")
            # Cast to list to handle Union[Awaitable[Any], Any]
            redis_keys = cast(list[str | bytes], redis_keys)
            # Convert bytes to string if needed
            keys = [key.decode() if isinstance(key, bytes) else key for key in redis_keys]
            return iter(cast(list[K], keys))

        return self._safe_operation(_keys_operation, "keys", iter([]))

    def increment(self, key: K, amount: int | float = 1) -> int | float | None:
        """
        Increment a numeric value.

        Args:
            key: The key to increment
            amount: Amount to increment by (default 1)

        Returns:
            New value after increment, or None if error
        """

        def _increment_operation() -> int | float | None:
            if not self._redis:
                return None

            redis_key = self._make_key(key)

            try:
                if isinstance(amount, float):
                    result = self._redis.incrbyfloat(redis_key, amount)
                    return cast(float, result)
                result = self._redis.incrby(redis_key, amount)
                return cast(int, result)
            except ResponseError:  # pylint: disable=broad-exception-caught
                # Key contains non-numeric value
                return None

        return self._safe_operation(_increment_operation, "increment", None)

    def ttl(self, key: K) -> float | None:
        """
        Get time-to-live for a key in seconds.

        Args:
            key: The key to check

        Returns:
            TTL in seconds, or None if key doesn't exist or has no expiration
        """

        def _ttl_operation() -> float | None:
            if not self._redis:
                return None

            redis_key = self._make_key(key)
            result = self._redis.pttl(redis_key)
            result = cast(int, result)

            if result in (-2, -1):  # Key doesn't exist or has no expiration
                return None
            return result / 1000.0

        return self._safe_operation(_ttl_operation, "ttl", None)

    def expire(self, key: K, ttl: int | float) -> bool:
        """
        Set expiration for a key.

        Args:
            key: The key to set expiration for
            ttl: Time to live in seconds

        Returns:
            True if successful, False if key doesn't exist
        """

        def _expire_operation() -> bool:
            if not self._redis:
                return False

            redis_key = self._make_key(key)

            if isinstance(ttl, float):
                # Use PEXPIRE for millisecond precision
                result = self._redis.pexpire(redis_key, int(ttl * 1000))
            else:
                # Use EXPIRE for second precision
                result = self._redis.expire(redis_key, ttl)

            return bool(result)

        return self._safe_operation(_expire_operation, "expire", False)

    def ping(self) -> bool:
        """
        Check Redis connection with ping.

        Returns:
            True if ping successful, False otherwise
        """
        if not self._redis:
            return False

        try:
            return bool(self._redis.ping())
        except Exception:  # pylint: disable=broad-exception-caught
            return False
