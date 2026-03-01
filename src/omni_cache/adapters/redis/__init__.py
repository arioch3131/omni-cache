"""This module provides Redis-based adapters for Omni-Cache."""

from .async_redis import AsyncRedisAdapter
from .redis import RedisAdapter, RedisAdapterConfig

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
    Redis = type("Redis", (), {})  # type: ignore
    ConnectionPool = type("ConnectionPool", (), {})  # type: ignore
    # Use Exception as base for fallbacks
    RedisConnectionError = Exception  # type: ignore
    RedisError = Exception  # type: ignore
    ResponseError = Exception  # type: ignore
    RedisTimeoutError = Exception  # type: ignore

__all__ = ["RedisAdapter", "RedisAdapterConfig", "AsyncRedisAdapter"]
