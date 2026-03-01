"""Asynchronous Redis adapter for omni-cache."""

import json
from typing import Any, TypeVar, cast

from omni_cache.adapters.redis.config import RedisAdapterConfig
from omni_cache.core.interfaces import AsyncKeyValueInterface

redis_asyncio: Any = None
RedisOperationError: type[Exception] = Exception

try:
    import redis.asyncio as redis_asyncio_mod
    from redis.exceptions import RedisError as _RedisOperationError

    redis_asyncio = redis_asyncio_mod
    RedisOperationError = _RedisOperationError
    HAS_ASYNC_REDIS = True
except ImportError:
    HAS_ASYNC_REDIS = False

K = TypeVar("K")
V = TypeVar("V")


class AsyncRedisAdapter(AsyncKeyValueInterface[K, V]):
    """Async Redis adapter implementing AsyncKeyValueInterface."""

    def __init__(self, config: dict[str, Any] | RedisAdapterConfig | None = None):
        if isinstance(config, dict):
            self._config = RedisAdapterConfig(**config)
        elif isinstance(config, RedisAdapterConfig):
            self._config = config
        else:
            self._config = RedisAdapterConfig()

        self._pool: Any = None
        self._redis: Any = None

    async def connect(self) -> bool:
        """Create async Redis connection."""
        if not HAS_ASYNC_REDIS or redis_asyncio is None:
            return False

        try:
            redis_kwargs = self._config.get_redis_kwargs()
            self._pool = redis_asyncio.ConnectionPool(
                max_connections=self._config.connection_pool_max_connections,
                **redis_kwargs,
            )
            self._redis = redis_asyncio.Redis(connection_pool=self._pool)
            await cast(Any, self._redis).ping()
            return True
        except Exception:
            self._redis = None
            self._pool = None
            return False

    async def disconnect(self) -> bool:
        """Close async Redis connection."""
        try:
            if self._pool is not None:
                await cast(Any, self._pool).disconnect()
            self._redis = None
            self._pool = None
            return True
        except Exception:
            return False

    def is_connected(self) -> bool:
        """Check whether the async client has been created."""
        return self._redis is not None

    async def health_check(self) -> bool:
        """Ping Redis asynchronously."""
        if not self._redis:
            return False
        try:
            return bool(await cast(Any, self._redis).ping())
        except Exception:
            return False

    def _make_key(self, key: K) -> str:
        key_str = str(key)
        if self._config.key_prefix:
            return f"{self._config.key_prefix}{self._config.key_separator}{key_str}"
        return key_str

    def _unmake_key(self, redis_key: str) -> str:
        if self._config.key_prefix:
            prefix = f"{self._config.key_prefix}{self._config.key_separator}"
            if redis_key.startswith(prefix):
                return redis_key[len(prefix) :]
        return redis_key

    def _serialize_value(self, value: V) -> str | bytes:
        if self._config.serialization_method == "string":
            return str(value)
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize_value(self, raw_value: str | bytes) -> V:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        if self._config.serialization_method == "string":
            return cast(V, raw_value)
        return cast(V, json.loads(raw_value))

    @staticmethod
    def _normalize_ttl(ttl: int | float | None) -> int | None:
        if ttl is None:
            return None
        ttl_int = int(ttl)
        return ttl_int if ttl_int > 0 else None

    async def get(self, key: K, default: V | None = None) -> V | None:
        if not self._redis:
            return default

        try:
            raw_value = await cast(Any, self._redis).get(self._make_key(key))
            if raw_value is None:
                return default
            return self._deserialize_value(cast(str | bytes, raw_value))
        except RedisOperationError:
            return default

    async def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:
        if not self._redis:
            return False

        try:
            redis_key = self._make_key(key)
            serialized = self._serialize_value(value)
            ttl_int = self._normalize_ttl(ttl)
            redis_client = cast(Any, self._redis)

            if ttl_int is not None:
                result = await redis_client.setex(redis_key, ttl_int, serialized)
            else:
                result = await redis_client.set(redis_key, serialized)
            return bool(result)
        except RedisOperationError:
            return False

    async def delete(self, key: K) -> bool:
        if not self._redis:
            return False

        try:
            deleted = await cast(Any, self._redis).delete(self._make_key(key))
            return int(deleted) > 0
        except RedisOperationError:
            return False

    async def exists(self, key: K) -> bool:
        if not self._redis:
            return False

        try:
            count = await cast(Any, self._redis).exists(self._make_key(key))
            return int(count) > 0
        except RedisOperationError:
            return False

    async def clear(self) -> bool:
        if not self._redis:
            return False

        try:
            redis_client = cast(Any, self._redis)
            if self._config.key_prefix:
                keys = await redis_client.keys(
                    f"{self._config.key_prefix}{self._config.key_separator}*"
                )
                if keys:
                    await redis_client.delete(*keys)
            else:
                await redis_client.flushdb()
            return True
        except RedisOperationError:
            return False

    async def keys(self) -> list[K]:
        if not self._redis:
            return []

        try:
            redis_client = cast(Any, self._redis)
            if self._config.key_prefix:
                redis_keys = await redis_client.keys(
                    f"{self._config.key_prefix}{self._config.key_separator}*"
                )
            else:
                redis_keys = await redis_client.keys("*")

            parsed_keys: list[K] = []
            for item in redis_keys:
                as_str = item.decode("utf-8") if isinstance(item, bytes) else str(item)
                parsed_keys.append(cast(K, self._unmake_key(as_str)))
            return parsed_keys
        except RedisOperationError:
            return []

    async def size(self) -> int:
        if not self._redis:
            return 0

        try:
            redis_client = cast(Any, self._redis)
            if self._config.key_prefix:
                redis_keys = await redis_client.keys(
                    f"{self._config.key_prefix}{self._config.key_separator}*"
                )
                return len(redis_keys)
            return int(await redis_client.dbsize())
        except RedisOperationError:
            return 0

    async def get_many(self, keys: list[K]) -> dict[K, V | None]:
        if not keys:
            return {}
        return {key: await self.get(key, None) for key in keys}

    async def set_many(
        self,
        mapping: dict[K, V],
        ttl: int | float | None = None,
    ) -> dict[K, bool]:
        if not mapping:
            return {}
        return {key: await self.set(key, value, ttl) for key, value in mapping.items()}

    async def delete_many(self, keys: list[K]) -> dict[K, bool]:
        if not keys:
            return {}
        return {key: await self.delete(key) for key in keys}
