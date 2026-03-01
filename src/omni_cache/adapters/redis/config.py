"""
Redis adapter implementation for omni-cache.

This module provides a Redis-based cache adapter that implements the KeyValueInterface.
Supports connection pooling, automatic serialization, TTL, and provides comprehensive
error handling and monitoring capabilities.
"""

from dataclasses import dataclass, field
from typing import Any

from omni_cache.adapters.base import AdapterConfig
from omni_cache.core.interfaces import CacheBackend


@dataclass
class RedisAdapterConfig(AdapterConfig):
    """Configuration specific to the Redis adapter."""

    # Connection settings
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    username: str | None = None

    # Timeout settings
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    socket_keepalive: bool = True
    socket_keepalive_options: dict[str, int] = field(default_factory=dict)

    # Connection pool settings
    connection_pool_max_connections: int = 10
    connection_pool_retry_on_timeout: bool = True

    # Serialization settings
    serialization_method: str = "json"  # "json", "string"
    encoding: str = "utf-8"
    decode_responses: bool = True

    # Key settings
    key_prefix: str = ""
    key_separator: str = ":"

    # Retry settings
    retry_on_error: bool = True
    retry_backoff_factor: float = 1.0

    # Health check settings
    health_check_key: str = "_omni_cache_health_check"

    def __post_init__(self) -> None:
        """Set the backend to Redis after initialization."""
        self.backend = CacheBackend.REDIS

    def get_redis_kwargs(self) -> dict[str, Any]:
        """Get Redis connection keyword arguments."""
        kwargs = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "socket_timeout": self.socket_timeout,
            "socket_connect_timeout": self.socket_connect_timeout,
            "socket_keepalive": self.socket_keepalive,
            "socket_keepalive_options": self.socket_keepalive_options,
            "retry_on_timeout": self.connection_pool_retry_on_timeout,
            "encoding": self.encoding,
            "decode_responses": (
                self.decode_responses if self.serialization_method != "pickle" else False
            ),
        }

        # Add optional parameters
        if self.password:
            kwargs["password"] = self.password
        if self.username:
            kwargs["username"] = self.username

        return kwargs
