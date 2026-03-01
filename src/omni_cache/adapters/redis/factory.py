"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

from typing import Any, TypeVar

from omni_cache.core.exceptions import (
    FactoryCreationError,
)
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

try:
    from .redis import RedisAdapter, RedisAdapterConfig

    REDIS_ADAPTER_AVAILABLE = True
except ImportError:
    REDIS_ADAPTER_AVAILABLE = False

# Type variables
T = TypeVar("T", bound=AdapterInterface)


class RedisAdapterFactory(AbstractFactory):
    """Factory for creating Redis adapters."""

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=CacheBackend.REDIS,
            factory_class="RedisAdapterFactory",
            description="Factory for Redis cache adapters",
            version="1.0.0",
            dependencies=["redis"],
            adapter_types=["cache"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "redis"},
                    "host": {"type": "string", "default": "localhost"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 6379},
                    "db": {"type": "integer", "minimum": 0, "default": 0},
                    "password": {"type": ["string", "null"]},
                    "socket_timeout": {"type": "number", "minimum": 0, "default": 5.0},
                    "connection_pool_max_connections": {
                        "type": "integer",
                        "minimum": 1,
                        "default": 10,
                    },
                },
                "required": [],
            },
        )

    def _setup_config_validators(self) -> None:
        """Setup custom validators for Redis adapter configuration."""

        def validate_port(port: int) -> bool:
            return isinstance(port, int) and 1 <= port <= 65535

        def validate_db(db: int) -> bool:
            return isinstance(db, int) and db >= 0

        self.add_config_validator("port", validate_port)
        self.add_config_validator("db", validate_db)

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        """Create a Redis adapter instance."""
        if REDIS_ADAPTER_AVAILABLE:
            # Convert config to RedisAdapterConfig
            adapter_config = RedisAdapterConfig(**config)
            return RedisAdapter(adapter_config)

        backend = self._metadata.backend
        if isinstance(backend, CacheBackend):
            backend = backend.value

        raise FactoryCreationError(backend, config, Exception("Redis adapter not available"))
